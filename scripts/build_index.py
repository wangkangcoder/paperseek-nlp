"""建立检索索引（对应 FR-03/04/05/15、SRS 5.2 索引生命周期）。

流程：
1. 读取语料（scifact 用 BEIR 数据；local_pdf 用本地 PDF 库切分后的片段）；
2. 计算语料哈希并保存 ``documents.jsonl`` + ``corpus_manifest.json``；
3. 依次构建所选检索器索引，保存到 ``data/index/<scope>/<retriever>/``；
4. 校验每个索引清单的 corpus_hash 与语料库一致。

用法：
    python scripts/build_index.py                                  # SciFact + 全部检索器
    python scripts/build_index.py --retrievers tfidf,bm25          # 只建稀疏检索
    python scripts/build_index.py --scope local_pdf --force
    python scripts/build_index.py --limit 300                      # 冒烟测试（不可用于正式评价）
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Sequence

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from paperseek import config  # noqa: E402
from paperseek.errors import PaperSeekError  # noqa: E402
from paperseek.index import (  # noqa: E402
    RETRIEVER_MANIFEST_FILE,
    DocumentStore,
    write_json,
)
from paperseek.retrievers import create_retriever, registered_names  # noqa: E402
from paperseek.schemas import Document  # noqa: E402


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="构建 PaperSeek 检索索引")
    parser.add_argument("--scope", default="scifact", choices=list(config.DEFAULT_SCOPES))
    parser.add_argument(
        "--retrievers",
        default=",".join(config.DEFAULT_RETRIEVERS),
        help=f"逗号分隔的检索器名称，可选：{','.join(registered_names())}",
    )
    parser.add_argument("--index-dir", default=None, help="索引根目录（默认 data/index）")
    parser.add_argument("--limit", type=int, default=0, help="只使用前 N 篇文档（仅冒烟测试）")
    parser.add_argument("--force", action="store_true", help="覆盖已存在的索引")
    parser.add_argument(
        "--sbert-model",
        default=config.DEFAULT_SBERT_MODEL,
        help="Sentence-BERT 模型名（默认轻量 MiniLM）",
    )
    parser.add_argument("--batch-size", type=int, default=config.SBERT_BATCH_SIZE)
    return parser.parse_args(argv)


def load_documents(scope: str, limit: int = 0) -> tuple[List[Document], str]:
    """按范围加载语料，返回 (documents, corpus_name)。"""
    if scope == "scifact":
        from paperseek.data.scifact import load_corpus

        documents = load_corpus(config.SCIFACT_DIR)
        corpus_name = "BEIR-SciFact"
    elif scope == "local_pdf":
        from paperseek.pdf.library import build_library_documents

        documents = build_library_documents(config.LOCAL_PDF_DIR)
        corpus_name = "Local-PDF-Library"
    else:  # pragma: no cover - argparse 已限制
        raise PaperSeekError(f"未知语料范围：{scope}")

    documents = sorted(documents, key=lambda d: d.doc_id)
    if limit and limit > 0:
        documents = documents[:limit]
        corpus_name += f"-limit{limit}"
    if not documents:
        raise PaperSeekError(
            f"范围 {scope} 没有可用文档。scifact 请先运行 scripts/download_data.py；"
            f"local_pdf 请先运行 scripts/import_pdfs.py 导入 PDF。"
        )
    return documents, corpus_name


def build_one(
    name: str,
    documents: Sequence[Document],
    scope_dir: Path,
    args: argparse.Namespace,
) -> Dict:
    index_dir = scope_dir / name
    manifest_path = index_dir / config.RETRIEVER_MANIFEST_FILE
    if manifest_path.exists() and not args.force:
        meta = json.loads(manifest_path.read_text(encoding="utf-8"))
        print(f"[跳过] {name}: 索引已存在（n={meta.get('n_documents')}, {meta.get('created_at')}）")
        return {"retriever": name, "status": "skipped", "elapsed_s": 0.0}

    retriever = create_retriever(name)
    retriever_config: Dict = {}
    if name in {"sbert", "rrf"}:
        retriever_config["model_name"] = args.sbert_model
        retriever_config["batch_size"] = args.batch_size

    started = time.perf_counter()
    manifest = retriever.build_index(documents, retriever_config)
    elapsed = time.perf_counter() - started
    retriever.save(index_dir)
    print(
        f"[完成] {name}: {manifest.n_documents} 篇, 用时 {elapsed:.1f}s, "
        f"模型={manifest.model_id or '-'}, 参数={manifest.params}"
    )
    return {
        "retriever": name,
        "status": "built",
        "elapsed_s": round(elapsed, 2),
        "n_documents": manifest.n_documents,
        "model_id": manifest.model_id,
        "params": manifest.params,
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    config.ensure_directories()
    index_root = Path(args.index_dir) if args.index_dir else config.INDEX_DIR
    scope_dir = index_root / args.scope

    documents, corpus_name = load_documents(args.scope, limit=args.limit)
    store = DocumentStore(scope=args.scope, corpus_name=corpus_name, documents=documents)
    store.save(scope_dir)
    print(
        f"[语料] scope={args.scope} 文档数={len(documents)} 哈希={store.corpus_hash[:12]}… "
        f"名称={corpus_name}"
    )

    retrievers = [name.strip().lower() for name in args.retrievers.split(",") if name.strip()]
    unknown = [name for name in retrievers if name not in registered_names()]
    if unknown:
        raise SystemExit(f"未知检索器：{unknown}，可选：{registered_names()}")

    results = []
    for name in retrievers:
        results.append(build_one(name, documents, scope_dir, args))

    # 校验所有索引清单与语料哈希一致（NFR-08）
    problems = []
    for item in results:
        manifest_path = scope_dir / item["retriever"] / config.RETRIEVER_MANIFEST_FILE
        if not manifest_path.exists():
            continue
        meta = json.loads(manifest_path.read_text(encoding="utf-8"))
        if meta.get("corpus_hash") != store.corpus_hash:
            problems.append(item["retriever"])
    if problems:
        raise SystemExit(f"以下检索器索引的语料哈希与当前语料不一致：{problems}")

    summary = {
        "scope": args.scope,
        "corpus_name": corpus_name,
        "n_documents": len(documents),
        "corpus_hash": store.corpus_hash,
        "index_dir": str(scope_dir),
        "retrievers": results,
    }
    write_json(scope_dir / "build_report.json", summary)
    print(f"\n[汇总] 索引目录：{scope_dir}")
    for item in results:
        print(f"  - {item['retriever']:6s} {item['status']:7s} {item.get('elapsed_s', 0):7.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
