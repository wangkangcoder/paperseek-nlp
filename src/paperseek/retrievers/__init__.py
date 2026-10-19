"""检索器注册表与工厂（延迟导入，某个检索器模块缺失时不影响其余功能与测试）。"""

from __future__ import annotations

import importlib
from typing import Dict, List, Tuple, Type

from ..errors import RetrieverNotFoundError
from .base import BaseRetriever

#: 检索器注册名 -> (模块路径, 类名)
_REGISTRY: Dict[str, Tuple[str, str]] = {
    "tfidf": ("paperseek.retrievers.tfidf", "TfidfRetriever"),
    "bm25": ("paperseek.retrievers.bm25", "BM25Retriever"),
    "sbert": ("paperseek.retrievers.sbert", "SBERTRetriever"),
    "rrf": ("paperseek.retrievers.hybrid", "RRFRetriever"),
}


def registered_names() -> List[str]:
    """返回全部已注册检索器名称（按注册顺序）。"""
    return list(_REGISTRY.keys())


def available_retrievers() -> List[str]:
    """返回当前环境中真实可导入的检索器名称（缺少依赖时自动跳过）。"""
    names: List[str] = []
    for key in _REGISTRY:
        try:
            _load_class(key)
        except Exception:  # noqa: BLE001 - 依赖缺失/模块未实现均视为不可用
            continue
        names.append(key)
    return names


def _load_class(name: str) -> Type[BaseRetriever]:
    key = (name or "").strip().lower()
    if key not in _REGISTRY:
        raise RetrieverNotFoundError(
            f"未知检索器 {name!r}，可选：{', '.join(_REGISTRY)}"
        )
    module_path, class_name = _REGISTRY[key]
    try:
        module = importlib.import_module(module_path)
    except ImportError as exc:  # 依赖未安装（如 sentence-transformers）
        raise RetrieverNotFoundError(
            f"检索器 {key} 依赖的模块无法导入：{exc}"
        ) from exc
    return getattr(module, class_name)


def create_retriever(name: str) -> BaseRetriever:
    """按名称创建检索器实例。"""
    return _load_class(name)()


__all__ = [
    "BaseRetriever",
    "available_retrievers",
    "create_retriever",
    "registered_names",
]
