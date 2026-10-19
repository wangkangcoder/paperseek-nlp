"""下载并解压公开基准数据集 SciFact（BEIR 版本）。

用法：
    python scripts/download_data.py                # 下载到 data/raw/scifact
    python scripts/download_data.py --force        # 强制重新下载

数据来源（公开、可引用）：
- BEIR 数据集发布页：https://github.com/beir-cellar/beir/wiki/Datasets-available
- 直接下载地址：https://public.ukp.informatik.tu-darmstadt.de/thakur/BEIR/datasets/scifact.zip
"""

from __future__ import annotations

import argparse
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from paperseek import config  # noqa: E402

SCIFACT_URL = "https://public.ukp.informatik.tu-darmstadt.de/thakur/BEIR/datasets/scifact.zip"
REQUIRED_FILES = ("corpus.jsonl", "queries.jsonl")


def download(url: str, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".part")
    print(f"[下载] {url}")
    with urllib.request.urlopen(url, timeout=120) as response, tmp.open("wb") as handle:
        total = int(response.headers.get("Content-Length") or 0)
        downloaded = 0
        while True:
            block = response.read(1 << 20)
            if not block:
                break
            handle.write(block)
            downloaded += len(block)
            if total:
                print(f"\r  {downloaded / 1e6:6.2f} / {total / 1e6:.2f} MB", end="")
    print()
    tmp.replace(target)


def ensure_scifact(force: bool = False) -> Path:
    config.ensure_directories()
    target_dir = config.SCIFACT_DIR
    if all((target_dir / name).exists() for name in REQUIRED_FILES) and not force:
        print(f"[跳过] SciFact 已存在：{target_dir}")
        return target_dir

    archive = config.RAW_DIR / "scifact.zip"
    if force or not archive.exists() or archive.stat().st_size < 1_000_000:
        download(SCIFACT_URL, archive)
    else:
        print(f"[缓存] 复用已下载压缩包：{archive}")

    if target_dir.exists() and force:
        shutil.rmtree(target_dir)
    print(f"[解压] {archive} -> {config.RAW_DIR}")
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(config.RAW_DIR)

    missing = [name for name in REQUIRED_FILES if not (target_dir / name).exists()]
    if missing:
        raise SystemExit(f"数据集不完整，缺少：{missing}（目录内容：{list(target_dir.glob('*'))}）")
    return target_dir


def describe(data_dir: Path) -> None:
    print("\n=== SciFact 数据集概况 ===")
    for name in ("corpus.jsonl", "queries.jsonl"):
        path = data_dir / name
        if path.exists():
            n = sum(1 for line in path.open("r", encoding="utf-8") if line.strip())
            print(f"  {name:16s} {n:6d} 行  {path.stat().st_size / 1e6:6.2f} MB")
    qrel_dir = data_dir / "qrels"
    if qrel_dir.exists():
        for path in sorted(qrel_dir.glob("*")):
            n = sum(1 for line in path.open("r", encoding="utf-8") if line.strip()) - 1
            print(f"  qrels/{path.name:12s} {n:6d} 条标注")


def main() -> int:
    parser = argparse.ArgumentParser(description="下载 SciFact（BEIR）公开数据集")
    parser.add_argument("--force", action="store_true", help="强制重新下载并解压")
    args = parser.parse_args()
    data_dir = ensure_scifact(force=args.force)
    describe(data_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
