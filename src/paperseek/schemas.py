"""PaperSeek 契约层：全项目统一的数据结构与索引清单定义。

设计原则（对应 SRS 5.3 数据结构草案）：
- 数据处理、检索器、评价器、界面四个层次只依赖本模块定义的结构；
- 字段命名和语义在开发前冻结，避免各模块各自定义导致集成失败；
- 相关性标注（Qrels）只能来自人工标注数据，绝不由检索分数推断。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional, Sequence

# 相关性标注：query_id -> {doc_id: relevance}（relevance 为 0/1/2 整数等级）
Qrels = Dict[str, Dict[str, int]]
# 检索结果：query_id -> 按排名排序的 doc_id 列表
Run = Dict[str, List[str]]


def utc_now_iso() -> str:
    """返回带时区的 ISO-8601 UTC 时间字符串，用于记录实验与索引创建时间。"""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class Document:
    """文献级检索单位。

    对应 SRS 5.3 的 Document 实体。SciFact 场景下 ``doc_id`` 直接使用原始 _id；
    本地 PDF 场景下检索单位是片段（Chunk），此时 ``doc_id`` 为片段 ID，
    父文献 ID、页码、文件路径放在 ``metadata`` 中，以保持统一检索接口（FR-06/FR-13）。
    """

    doc_id: str
    title: str
    text: str
    source: str = "scifact"  # "scifact" | "local_pdf"
    path: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Document":
        return cls(
            doc_id=str(data["doc_id"]),
            title=str(data.get("title", "")),
            text=str(data.get("text", "")),
            source=str(data.get("source", "scifact")),
            path=data.get("path"),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass
class Chunk:
    """PDF 片段级检索单位（SRS 5.3 的 Chunk 实体）。"""

    chunk_id: str
    doc_id: str
    page: int
    text: str
    title: str = ""
    path: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_document(self) -> Document:
        """转换为统一的 Document，供检索器/索引层使用。"""
        meta = dict(self.metadata)
        meta.update({"chunk_id": self.chunk_id, "page": self.page, "parent_doc_id": self.doc_id})
        return Document(
            doc_id=self.chunk_id,
            title=self.title or self.doc_id,
            text=self.text,
            source="local_pdf",
            path=self.path,
            metadata=meta,
        )


@dataclass
class Query:
    """检索查询（标准实验查询或用户临时查询）。"""

    query_id: str
    text: str
    language: str = "en"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SearchResult:
    """统一检索输出（FR-06）。"""

    doc_id: str
    rank: int
    score: float
    title: str = ""
    snippet: str = ""
    source: str = ""
    chunk_id: Optional[str] = None
    page: Optional[int] = None
    path: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class IndexManifest:
    """索引清单：记录语料哈希、模型、参数与创建时间，用于版本校验与实验复现。

    对应 SRS 5.3 的 IndexManifest 与 NFR-03/NFR-08。
    """

    retriever: str
    corpus_hash: str
    n_documents: int
    params: Dict[str, Any] = field(default_factory=dict)
    model_id: Optional[str] = None
    corpus_name: str = ""
    created_at: str = field(default_factory=utc_now_iso)
    schema_version: str = "1"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "IndexManifest":
        return cls(
            retriever=str(data["retriever"]),
            corpus_hash=str(data["corpus_hash"]),
            n_documents=int(data["n_documents"]),
            params=dict(data.get("params") or {}),
            model_id=data.get("model_id"),
            corpus_name=str(data.get("corpus_name", "")),
            created_at=str(data.get("created_at", utc_now_iso())),
            schema_version=str(data.get("schema_version", "1")),
        )

    def verify(self, corpus_hash: str, model_id: Optional[str] = None) -> None:
        """校验索引与当前语料/模型是否匹配，不匹配时抛出 ManifestMismatchError。

        参数
        ----
        corpus_hash: 当前语料库内容哈希。
        model_id: 当前使用的语义模型标识（稀疏检索器传 None，表示不校验模型）。
        """
        from .errors import ManifestMismatchError

        problems: List[str] = []
        if self.corpus_hash != corpus_hash:
            problems.append(
                f"语料哈希不一致（索引={self.corpus_hash[:12]}…，当前={corpus_hash[:12]}…）"
            )
        if model_id is not None and self.model_id is not None and self.model_id != model_id:
            problems.append(f"模型不一致（索引={self.model_id}，当前={model_id}）")
        if problems:
            raise ManifestMismatchError(
                f"检索器 {self.retriever} 的索引与当前数据不匹配：" + "；".join(problems)
                + "。请运行 `python scripts/build_index.py --force` 重建索引。"
            )


def summarize_run(results: Sequence[SearchResult], max_items: int = 5) -> str:
    """把检索结果格式化为便于命令行/日志展示的简短文本。"""
    lines = []
    for r in results[:max_items]:
        lines.append(f"#{r.rank:<2d} [{r.score:.4f}] {r.doc_id}  {r.title[:70]}")
    return "\n".join(lines)
