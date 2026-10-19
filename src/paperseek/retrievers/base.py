"""检索器统一接口（SRS 5.4 检索器接口草案 / FR-06 统一检索接口）。

所有检索器必须实现 ``build_index``、``search``、``save``、``load`` 四个方法，
输入输出只使用 :mod:`paperseek.schemas` 中冻结的数据结构。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional, Sequence, Tuple

from ..errors import EmptyQueryError, IndexNotBuiltError
from ..schemas import Document, IndexManifest, SearchResult


class BaseRetriever(ABC):
    """检索器抽象基类。"""

    #: 注册名，与 `paperseek.retrievers.create_retriever` 使用的小写名称一致
    name: ClassVar[str] = "base"

    def __init__(self) -> None:
        self._documents: List[Document] = []
        self._doc_ids: List[str] = []
        self._index: Dict[str, Document] = {}
        self._manifest: Optional[IndexManifest] = None

    # ------------------------------------------------------------------ 属性
    @property
    def manifest(self) -> Optional[IndexManifest]:
        return self._manifest

    @property
    def is_ready(self) -> bool:
        return self._manifest is not None

    @property
    def documents(self) -> Sequence[Document]:
        return self._documents

    def params(self) -> Dict[str, Any]:
        """返回当前检索器的可复现参数，写入 IndexManifest.params。"""
        return {}

    # ------------------------------------------------------------------ 契约
    @abstractmethod
    def build_index(
        self,
        documents: Sequence[Document],
        config: Optional[Dict[str, Any]] = None,
    ) -> IndexManifest:
        """在全量语料上构建索引，返回索引清单。

        实现方必须：校验文档 ID 唯一、文本非空；把 ``config`` 与 ``params()`` 写入 manifest。
        """

    @abstractmethod
    def search(self, query: str, top_k: int = 10) -> List[SearchResult]:
        """检索并返回按得分降序排列的 Top-K 结果。

        返回的 ``rank`` 从 1 开始；``score`` 只表示该方法的相对得分，不得解释为概率。
        """

    @abstractmethod
    def save(self, directory: Path) -> None:
        """把索引与 manifest 持久化到目录（目录不存在时自动创建）。"""

    @classmethod
    @abstractmethod
    def load(cls, directory: Path) -> "BaseRetriever":
        """从目录恢复索引；目录缺失或 manifest 缺失时抛出 IndexNotBuiltError。"""

    # ------------------------------------------------------------------ 工具
    def _set_documents(self, documents: Sequence[Document]) -> None:
        self._documents = list(documents)
        self._doc_ids = [doc.doc_id for doc in self._documents]
        self._index = {doc.doc_id: doc for doc in self._documents}
        if len(self._index) != len(self._doc_ids):
            duplicates = len(self._doc_ids) - len(self._index)
            raise ValueError(f"{self.name}: 语料中存在 {duplicates} 个重复 doc_id")

    def _make_manifest(
        self,
        corpus_hash: str,
        corpus_name: str,
        model_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> IndexManifest:
        params: Dict[str, Any] = dict(self.params())
        if config:
            params.update({k: v for k, v in config.items() if k != "documents"})
        manifest = IndexManifest(
            retriever=self.name,
            corpus_hash=corpus_hash,
            n_documents=len(self._documents),
            params=params,
            model_id=model_id,
            corpus_name=corpus_name,
        )
        self._manifest = manifest
        return manifest

    def _require_ready(self) -> None:
        if self._manifest is None:
            raise IndexNotBuiltError(
                f"检索器 {self.name} 尚未构建索引。请先运行脚本建立索引，或调用 build_index()。"
            )

    def _clean_query(self, query: str) -> str:
        text = (query or "").strip()
        if not text:
            raise EmptyQueryError("查询内容不能为空，请输入检索问题。")
        return text

    def _normalize_top_k(self, top_k: int) -> int:
        if top_k is None or int(top_k) <= 0:
            raise ValueError(f"top_k 必须为正整数，收到 {top_k!r}")
        return min(int(top_k), max(len(self._documents), 1))

    def _document(self, doc_id: str) -> Optional[Document]:
        return self._index.get(doc_id)

    def _build_results(
        self,
        ranked: Sequence[Tuple[str, float]],
        query: str = "",
        snippet_chars: int = 240,
    ) -> List[SearchResult]:
        """把 ``(doc_id, score)`` 列表转换为统一的 SearchResult（不含片段 enrichment）。"""
        results: List[SearchResult] = []
        for rank, (doc_id, score) in enumerate(ranked, start=1):
            doc = self._index.get(doc_id)
            title = doc.title if doc else ""
            snippet = ""
            if doc is not None:
                snippet = doc.text[:snippet_chars].replace("\n", " ").strip()
            results.append(
                SearchResult(
                    doc_id=doc_id,
                    rank=rank,
                    score=float(score),
                    title=title,
                    snippet=snippet,
                    source=doc.source if doc else "",
                )
            )
        return results
