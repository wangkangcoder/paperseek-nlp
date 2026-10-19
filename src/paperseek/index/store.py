"""索引存储层：语料文档库、语料哈希与索引清单管理。

SRS 5.2 索引生命周期 / NFR-08 存储一致性：
- ``documents.jsonl`` 保存该语料范围内全部检索单位（Document）；
- ``corpus_manifest.json`` 保存语料哈希、规模与创建时间；
- 各检索器目录下的 ``manifest.json`` 引用的 corpus_hash 必须与语料清单一致，
  否则加载时拒绝使用，避免“旧索引配新语料”。
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

from ..errors import DataFormatError, IndexNotBuiltError
from ..schemas import Document, IndexManifest, utc_now_iso

CORPUS_MANIFEST_FILE = "corpus_manifest.json"
DOCUMENTS_FILE = "documents.jsonl"
RETRIEVER_MANIFEST_FILE = "manifest.json"


def compute_corpus_hash(documents: Iterable[Document]) -> str:
    """计算语料内容哈希。

    规则：按 ``doc_id`` 排序后，对 ``doc_id\\ttitle\\ttext`` 逐行做 sha256。
    与文件路径、机器、时间无关，保证不同机器上同一语料哈希一致。
    """
    digest = hashlib.sha256()
    for doc in sorted(documents, key=lambda d: d.doc_id):
        digest.update(doc.doc_id.encode("utf-8"))
        digest.update(b"\t")
        digest.update(doc.title.encode("utf-8"))
        digest.update(b"\t")
        digest.update(doc.text.encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def write_json(path: Path, payload: Dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def read_json(path: Path) -> Dict:
    if not path.exists():
        raise IndexNotBuiltError(f"缺少文件：{path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DataFormatError(f"JSON 文件损坏：{path}：{exc}") from exc


def write_documents(path: Path, documents: Sequence[Document]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as handle:
        for doc in documents:
            handle.write(json.dumps(doc.to_dict(), ensure_ascii=False) + "\n")
    tmp.replace(path)


def read_documents(path: Path) -> List[Document]:
    if not path.exists():
        raise IndexNotBuiltError(f"缺少语料文件：{path}，请先运行 scripts/build_index.py")
    documents: List[Document] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                documents.append(Document.from_dict(json.loads(line)))
            except (json.JSONDecodeError, KeyError) as exc:
                raise DataFormatError(f"{path}:{line_no} 文档记录损坏：{exc}") from exc
    return documents


@dataclass
class DocumentStore:
    """某个检索范围内（scifact / local_pdf）的语料文档库。"""

    scope: str
    corpus_name: str
    documents: List[Document] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._by_id: Dict[str, Document] = {doc.doc_id: doc for doc in self.documents}
        if len(self._by_id) != len(self.documents):
            raise DataFormatError(f"语料 {self.scope} 中存在重复 doc_id")

    @property
    def corpus_hash(self) -> str:
        return compute_corpus_hash(self.documents)

    def __len__(self) -> int:
        return len(self.documents)

    def get(self, doc_id: str) -> Optional[Document]:
        return self._by_id.get(doc_id)

    # ------------------------------------------------------------------ 持久化
    def save(self, scope_dir: Path) -> Path:
        scope_dir = Path(scope_dir)
        scope_dir.mkdir(parents=True, exist_ok=True)
        write_documents(scope_dir / DOCUMENTS_FILE, self.documents)
        write_json(
            scope_dir / CORPUS_MANIFEST_FILE,
            {
                "scope": self.scope,
                "corpus_name": self.corpus_name,
                "n_documents": len(self.documents),
                "corpus_hash": self.corpus_hash,
                "created_at": utc_now_iso(),
                "schema_version": "1",
            },
        )
        return scope_dir

    @classmethod
    def load(cls, scope_dir: Path) -> "DocumentStore":
        scope_dir = Path(scope_dir)
        manifest_path = scope_dir / CORPUS_MANIFEST_FILE
        if not manifest_path.exists():
            raise IndexNotBuiltError(
                f"语料清单不存在：{manifest_path}。请先运行 scripts/build_index.py。"
            )
        meta = read_json(manifest_path)
        documents = read_documents(scope_dir / DOCUMENTS_FILE)
        store = cls(
            scope=str(meta.get("scope", scope_dir.name)),
            corpus_name=str(meta.get("corpus_name", "")),
            documents=documents,
        )
        actual_hash = store.corpus_hash
        expected_hash = str(meta.get("corpus_hash", ""))
        if expected_hash and actual_hash != expected_hash:
            raise DataFormatError(
                f"语料文件与清单哈希不一致（清单={expected_hash[:12]}…，实际={actual_hash[:12]}…），"
                f"请重新运行 scripts/build_index.py 重建。"
            )
        return store


def read_retriever_manifest(directory: Path) -> IndexManifest:
    directory = Path(directory)
    manifest_path = directory / RETRIEVER_MANIFEST_FILE
    if not manifest_path.exists():
        raise IndexNotBuiltError(
            f"检索器索引清单不存在：{manifest_path}。请先构建该检索器的索引。"
        )
    return IndexManifest.from_dict(read_json(manifest_path))
