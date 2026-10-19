"""统一检索服务（SRS 5.1 服务层 / FR-06、FR-08）。

职责：
1. 加载指定范围（scifact / local_pdf）的语料文档库与各检索器索引；
2. 用 ``IndexManifest`` 校验索引与语料版本一致（NFR-08）；
3. 对外提供统一的 ``search`` / ``compare`` / ``status`` 接口；
4. 为检索结果补齐标题、片段、页码、来源等可展示字段。

界面层（Streamlit）与脚本层只调用本模块，不直接处理向量或文件路径。
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence

from .. import config
from ..errors import IndexNotBuiltError, RetrieverNotFoundError
from ..index import DocumentStore, read_retriever_manifest
from ..retrievers import create_retriever, registered_names
from ..schemas import Document, SearchResult


class SearchService:
    """面向界面/脚本的检索服务门面。"""

    def __init__(
        self,
        scope: str = "scifact",
        index_root: Optional[Path] = None,
        snippet_chars: int = 240,
    ) -> None:
        self.scope = scope
        self.index_root = Path(index_root) if index_root is not None else config.INDEX_DIR
        self.scope_dir = self.index_root / scope
        self.snippet_chars = snippet_chars
        self._store: Optional[DocumentStore] = None
        self._retrievers: Dict[str, object] = {}

    # ------------------------------------------------------------------ 状态
    def _load_store(self) -> DocumentStore:
        if self._store is None:
            self._store = DocumentStore.load(self.scope_dir)
        return self._store

    @property
    def store(self) -> DocumentStore:
        return self._load_store()

    def available(self) -> List[str]:
        """返回当前范围下已构建索引且依赖可导入的检索器名称。"""
        names: List[str] = []
        for name in registered_names():
            if (self.scope_dir / name / config.RETRIEVER_MANIFEST_FILE).exists():
                try:
                    create_retriever(name)
                except RetrieverNotFoundError:
                    continue
                names.append(name)
        return names

    def manifests(self) -> Dict[str, Mapping]:
        """返回各已构建检索器的索引清单摘要。"""
        out: Dict[str, Mapping] = {}
        for name in self.available():
            manifest = read_retriever_manifest(self.scope_dir / name)
            out[name] = {
                "retriever": manifest.retriever,
                "n_documents": manifest.n_documents,
                "model_id": manifest.model_id,
                "params": manifest.params,
                "created_at": manifest.created_at,
                "corpus_hash": manifest.corpus_hash[:12] + "…",
            }
        return out

    def status(self) -> Dict[str, object]:
        store = self._load_store()
        return {
            "scope": self.scope,
            "scope_dir": str(self.scope_dir),
            "corpus_name": store.corpus_name,
            "n_documents": len(store),
            "corpus_hash": store.corpus_hash[:12] + "…",
            "available_retrievers": self.available(),
            "manifests": self.manifests(),
        }

    # ------------------------------------------------------------------ 检索
    def load_retriever(self, name: str):
        """加载并缓存某个检索器；校验索引清单与语料哈希。"""
        key = (name or "").strip().lower()
        if key in self._retrievers:
            return self._retrievers[key]
        store = self._load_store()
        directory = self.scope_dir / key
        if not (directory / config.RETRIEVER_MANIFEST_FILE).exists():
            raise IndexNotBuiltError(
                f"检索器 {key} 在范围 {self.scope} 下还没有索引。"
                f"请先运行：python scripts/build_index.py --scope {self.scope} --retrievers {key}"
            )
        retriever = create_retriever(key)
        loaded = retriever.load(directory)
        manifest = read_retriever_manifest(directory)
        # 只校验语料版本；语义模型的版本由 IndexManifest.model_id 在加载时固定，
        # 避免更换模型配置后误用旧模型（NFR-08）。
        manifest.verify(store.corpus_hash)
        self._retrievers[key] = loaded
        return loaded

    def search(
        self,
        query: str,
        retriever: str = "bm25",
        top_k: int = config.DEFAULT_TOP_K,
    ) -> List[SearchResult]:
        """执行一次检索并返回补齐展示字段的结果。"""
        engine = self.load_retriever(retriever)
        results = engine.search(query, top_k=top_k)
        return self._enrich(results)

    def compare(
        self,
        query: str,
        retrievers: Optional[Sequence[str]] = None,
        top_k: int = config.DEFAULT_TOP_K,
    ) -> Dict[str, List[SearchResult]]:
        """同一查询依次运行多个检索器，用于算法对比页面（P-03）。"""
        names = list(retrievers) if retrievers is not None else self.available()
        if not names:
            raise IndexNotBuiltError(
                f"范围 {self.scope} 下没有任何可用索引，请先运行 scripts/build_index.py。"
            )
        return {name: self.search(query, retriever=name, top_k=top_k) for name in names}

    # ------------------------------------------------------------------ 内部
    def _enrich(self, results: Sequence[SearchResult]) -> List[SearchResult]:
        """用语料文档库补齐 title/snippet/source/page/path（不修改 rank 与 score）。"""
        store = self._load_store()
        for item in results:
            doc = store.get(item.doc_id)
            if doc is None:
                continue
            item.title = item.title or doc.title
            if not item.snippet:
                item.snippet = doc.text[: self.snippet_chars].replace("\n", " ").strip()
            item.source = item.source or doc.source
            item.path = item.path or doc.path
            page = doc.metadata.get("page")
            if page is not None:
                item.page = int(page)
            chunk_id = doc.metadata.get("chunk_id")
            if chunk_id:
                item.chunk_id = str(chunk_id)
            parent = doc.metadata.get("parent_doc_id")
            if parent:
                item.metadata.setdefault("parent_doc_id", parent)
        return list(results)
