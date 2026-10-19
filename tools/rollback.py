# -*- coding: utf-8 -*-
"""PaperSeek 版本控制、回退与检查点工具（跨平台，Windows PowerShell 5.1 兼容）。

设计目标（对应 docs/04_回退机制说明.md 的五层回退体系）：
  L1 细粒度 commit        -> checkpoint
  L2 里程碑 annotated tag -> checkpoint --tag
  L3 文件级快照           -> snapshot（含未提交改动，zip 归档到 backups/）
  L4 回退前自动备份分支   -> restore 自动创建 backup/pre-rollback-<时间>，可用 undo 撤销
  L5 GitHub 远端          -> publish（推送分支与 tag）

常用命令：
    python tools/rollback.py status
    python tools/rollback.py list
    python tools/rollback.py snapshots
    python tools/rollback.py snapshot -m "重构前快照"
    python tools/rollback.py checkpoint -m "feat: xxx [CHG-010]" --tag v0.2.0-w2 --test
    python tools/rollback.py restore v0.2.0-w2 --yes
    python tools/rollback.py undo
    python tools/rollback.py diff v0.2.0-w2
    python tools/rollback.py publish
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKUP_DIR = ROOT / "backups"
GIT_DIR = ROOT / ".git"
ROLLBACK_STATE = GIT_DIR / "paperseek_rollback.json"
SNAPSHOT_SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", "node_modules"}


# --------------------------------------------------------------------------- 基础
def _reconfigure_stdout() -> None:
    """Windows 控制台默认 GBK，统一成 UTF-8 输出避免中文乱码。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            pass


def git(*args: str, check: bool = True, capture: bool = True) -> subprocess.CompletedProcess:
    """执行 git 命令，工作目录固定为项目根。"""
    result = subprocess.run(
        ["git", *args],
        cwd=str(ROOT),
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=capture,
    )
    if check and result.returncode != 0:
        message = (result.stderr or result.stdout or "").strip()
        raise SystemExit(f"[错误] git {' '.join(args)} 失败：{message}")
    return result


def ensure_repo() -> None:
    if not GIT_DIR.exists():
        raise SystemExit("[错误] 当前目录不是 git 仓库，请先在项目根目录执行 git init。")


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def short(text: str, limit: int = 60) -> str:
    text = " ".join((text or "").split())
    return text[:limit] + ("…" if len(text) > limit else "")


# --------------------------------------------------------------------------- 查询
def cmd_status(_: argparse.Namespace) -> int:
    ensure_repo()
    branch = git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    head = git("rev-parse", "--short", "HEAD").stdout.strip()
    describe = git("describe", "--tags", "--always", check=False).stdout.strip()
    status = git("status", "--porcelain").stdout.strip()
    tags = [line for line in git("tag", "--list").stdout.splitlines() if line.strip()]

    print("=" * 68)
    print("PaperSeek 版本状态")
    print("=" * 68)
    print(f"分支        : {branch}")
    print(f"HEAD        : {head}  ({describe})")
    print(f"里程碑 tag  : {', '.join(sorted(tags)) if tags else '（无）'}")
    print(f"工作区      : {'干净 ✔' if not status else '有未提交改动 ⚠'}")
    if status:
        for line in status.splitlines()[:20]:
            print(f"    {line}")
        total = len(status.splitlines())
        if total > 20:
            print(f"    … 共 {total} 个变更")
    print("-" * 68)
    print("最近提交：")
    log = git("log", "--oneline", "-n", "8", "--decorate").stdout.strip()
    print(log if log else "（还没有提交）")
    print("=" * 68)
    return 0


def cmd_list(_: argparse.Namespace) -> int:
    ensure_repo()
    fmt = "%(refname:short)\t%(creatordate:short)\t%(subject)"
    out = git("for-each-ref", "refs/tags", f"--format={fmt}", "--sort=-creatordate").stdout
    print("里程碑 tag（新→旧）：")
    if not out.strip():
        print("  （无 tag）")
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) == 3:
            print(f"  {parts[0]:20s} {parts[1]}  {short(parts[2])}")
    print("\n最近 15 次提交：")
    print(git("log", "--oneline", "-n", "15", "--decorate").stdout.strip() or "  （无）")
    return 0


def cmd_snapshots(_: argparse.Namespace) -> int:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    items = sorted(BACKUP_DIR.glob("snapshot-*.zip"), reverse=True)
    print(f"文件级快照目录：{BACKUP_DIR}")
    if not items:
        print("  （暂无快照）")
        return 0
    for path in items:
        meta_path = path.with_suffix(".json")
        meta = {}
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                meta = {}
        print(
            f"  {path.name}  {path.stat().st_size / 1e6:6.2f} MB  "
            f"HEAD={meta.get('head', '?')}  说明={short(meta.get('message', ''))}"
        )
    return 0


# --------------------------------------------------------------------------- 快照
def collect_files() -> list[Path]:
    """收集需要备份的文件：git 已跟踪 + 未忽略的新文件。"""
    tracked = git("ls-files", "-z", "--cached").stdout
    untracked = git("ls-files", "-z", "--others", "--exclude-standard").stdout
    names = {name for name in (tracked + untracked).split("\0") if name}
    files: list[Path] = []
    for name in sorted(names):
        path = ROOT / name
        if not path.is_file():
            continue
        if any(part in SNAPSHOT_SKIP_DIRS for part in path.relative_to(ROOT).parts):
            continue
        files.append(path)
    return files


def create_snapshot(message: str) -> Path:
    """把工作区源码打包为 zip，返回归档路径。"""
    ensure_repo()
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = now_stamp()
    archive = BACKUP_DIR / f"snapshot-{stamp}.zip"
    files = collect_files()
    info = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "message": message,
        "head": git("rev-parse", "HEAD", check=False).stdout.strip() or "",
        "head_short": git("rev-parse", "--short", "HEAD", check=False).stdout.strip() or "",
        "branch": git("rev-parse", "--abbrev-ref", "HEAD", check=False).stdout.strip() or "",
        "dirty": bool(git("status", "--porcelain").stdout.strip()),
        "n_files": len(files),
    }
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in files:
            zf.write(path, arcname=str(path.relative_to(ROOT)).replace("\\", "/"))
        zf.writestr("SNAPSHOT_INFO.json", json.dumps(info, ensure_ascii=False, indent=2))
    archive.with_suffix(".json").write_text(
        json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[快照完成] {archive}  （{len(files)} 个文件）")
    print(f"            HEAD={info['head_short']}  工作区{'有' if info['dirty'] else '无'}未提交改动")
    return archive


def cmd_snapshot(args: argparse.Namespace) -> int:
    create_snapshot(args.message or "手动快照")
    return 0


# --------------------------------------------------------------------------- 检查点
def cmd_checkpoint(args: argparse.Namespace) -> int:
    ensure_repo()
    if args.test:
        print("[门禁] 运行测试：python -m pytest -q")
        proc = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=str(ROOT))
        if proc.returncode != 0:
            raise SystemExit("[阻止提交] 测试未通过，请修复后再 checkpoint。")
        print("[门禁] 测试通过 ✔")

    changed = git("status", "--porcelain").stdout.strip()
    if changed:
        git("add", "-A")
        commit_message = args.message or "chore: 检查点"
        git("commit", "-m", commit_message)
        head = git("rev-parse", "--short", "HEAD").stdout.strip()
        print(f"[提交完成] {head}  {short(commit_message)}")
    else:
        print("[提交] 工作区没有变更，跳过提交。")

    if args.tag:
        exists = git("rev-parse", "--verify", f"refs/tags/{args.tag}", check=False)
        if exists.returncode == 0:
            raise SystemExit(f"[错误] tag {args.tag} 已存在，不允许覆盖。")
        git("tag", "-a", args.tag, "-m", args.tag_message or args.message or args.tag)
        print(f"[打标签] {args.tag}")

    if args.push:
        cmd_publish(argparse.Namespace())
    return 0


# --------------------------------------------------------------------------- 回退
def cmd_restore(args: argparse.Namespace) -> int:
    ensure_repo()
    ref = args.ref
    if git("rev-parse", "--verify", ref, check=False).returncode != 0:
        raise SystemExit(f"[错误] 找不到版本：{ref}（可用 tag 或提交哈希）")

    print(f"[回退] 目标版本：{ref}")
    print(f"       当前 HEAD：{git('rev-parse', '--short', 'HEAD').stdout.strip()}")
    if not args.yes:
        answer = input("确认回退？未提交改动会先自动快照并备份到分支（y/N）：").strip().lower()
        if answer not in {"y", "yes"}:
            print("已取消。")
            return 1

    archive = create_snapshot(f"restore 前自动快照 -> {ref}")
    backup_branch = f"backup/pre-rollback-{now_stamp()}"
    head = git("rev-parse", "HEAD").stdout.strip()
    git("branch", backup_branch, head)
    ROLLBACK_STATE.write_text(
        json.dumps(
            {
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "target": ref,
                "from_head": head,
                "backup_branch": backup_branch,
                "snapshot": str(archive),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    git("reset", "--hard", ref)
    print(f"[已回退] 现在处于 {ref}（{git('rev-parse', '--short', 'HEAD').stdout.strip()}）")
    print(f"[备份] 回退前分支：{backup_branch}")
    print(f"[备份] 文件快照：{archive}")
    print("如需撤销本次回退：python tools/rollback.py undo")
    return 0


def cmd_undo(_: argparse.Namespace) -> int:
    ensure_repo()
    if not ROLLBACK_STATE.exists():
        raise SystemExit("[错误] 没有可撤销的回退记录（仅 restore 会生成记录）。")
    state = json.loads(ROLLBACK_STATE.read_text(encoding="utf-8"))
    branch = state["backup_branch"]
    if git("rev-parse", "--verify", branch, check=False).returncode != 0:
        raise SystemExit(f"[错误] 备份分支已不存在：{branch}")
    git("reset", "--hard", branch)
    print(f"[已撤销回退] 回到 {branch}（{git('rev-parse', '--short', 'HEAD').stdout.strip()}）")
    print(f"  原回退目标：{state['target']}  时间：{state['created_at']}")
    ROLLBACK_STATE.rename(ROLLBACK_STATE.with_suffix(".done.json"))
    return 0


def cmd_diff(args: argparse.Namespace) -> int:
    ensure_repo()
    print(f"[差异统计] 当前工作区 vs {args.ref}")
    print(git("diff", "--stat", args.ref).stdout.strip() or "  （无差异）")
    if args.full:
        print(git("diff", args.ref, "--", "src", "scripts", "app", "tests").stdout)
    return 0


# --------------------------------------------------------------------------- 远端
def cmd_publish(_: argparse.Namespace) -> int:
    ensure_repo()
    remotes = git("remote").stdout.split()
    if "origin" not in remotes:
        raise SystemExit("[错误] 尚未配置 origin 远端，请先执行 git remote add origin <url>")
    branch = git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    print(f"[推送] origin/{branch} ...")
    result = git("push", "-u", "origin", branch, check=False)
    print(result.stdout.strip() or result.stderr.strip())
    if result.returncode != 0:
        raise SystemExit("[错误] 推送失败，请检查网络或凭据。")
    print("[推送] tags ...")
    tags = git("push", "origin", "--tags", check=False)
    print(tags.stdout.strip() or tags.stderr.strip())
    if tags.returncode != 0:
        raise SystemExit("[错误] tag 推送失败。")
    print("[完成] 远端已同步：https://github.com/wangkangcoder/paperseek-nlp")
    return 0


# --------------------------------------------------------------------------- CLI
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="PaperSeek 版本控制与回退工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="查看分支/HEAD/tag/工作区状态").set_defaults(func=cmd_status)
    sub.add_parser("list", help="列出里程碑 tag 与最近提交").set_defaults(func=cmd_list)
    sub.add_parser("snapshots", help="列出文件级快照").set_defaults(func=cmd_snapshots)

    p_snap = sub.add_parser("snapshot", help="创建文件级快照（含未提交改动）")
    p_snap.add_argument("-m", "--message", default="", help="快照说明")
    p_snap.set_defaults(func=cmd_snapshot)

    p_ckpt = sub.add_parser("checkpoint", help="跑测试 -> 提交 ->（可选）打 tag")
    p_ckpt.add_argument("-m", "--message", default="", help="提交信息")
    p_ckpt.add_argument("--tag", default="", help="附带创建的 annotated tag，如 v0.2.0-w2")
    p_ckpt.add_argument("--tag-message", default="", help="tag 说明")
    p_ckpt.add_argument("--test", action="store_true", help="提交前运行 pytest 作为门禁")
    p_ckpt.add_argument("--push", action="store_true", help="提交成功后推送远端")
    p_ckpt.set_defaults(func=cmd_checkpoint)

    p_restore = sub.add_parser("restore", help="回退到指定 tag/提交")
    p_restore.add_argument("ref", help="目标 tag 或提交哈希")
    p_restore.add_argument("--yes", action="store_true", help="跳过交互确认")
    p_restore.set_defaults(func=cmd_restore)

    sub.add_parser("undo", help="撤销上一次 restore").set_defaults(func=cmd_undo)

    p_diff = sub.add_parser("diff", help="查看与指定版本的差异统计")
    p_diff.add_argument("ref")
    p_diff.add_argument("--full", action="store_true", help="输出完整代码 diff")
    p_diff.set_defaults(func=cmd_diff)

    sub.add_parser("publish", help="推送当前分支与全部 tag 到 origin").set_defaults(func=cmd_publish)
    return parser


def main(argv: list[str] | None = None) -> int:
    _reconfigure_stdout()
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
