"""索引层：语料文档库与索引清单持久化。"""

from __future__ import annotations

from .store import (
    CORPUS_MANIFEST_FILE,
    DOCUMENTS_FILE,
    RETRIEVER_MANIFEST_FILE,
    DocumentStore,
    compute_corpus_hash,
    read_documents,
    read_json,
    read_retriever_manifest,
    write_documents,
    write_json,
)

__all__ = [
    "CORPUS_MANIFEST_FILE",
    "DOCUMENTS_FILE",
    "RETRIEVER_MANIFEST_FILE",
    "DocumentStore",
    "compute_corpus_hash",
    "read_documents",
    "read_json",
    "read_retriever_manifest",
    "write_documents",
    "write_json",
]
