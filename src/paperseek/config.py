"""全局配置与路径约定。

所有路径默认相对项目根目录推导，便于在任意机器上复现（NFR-03）。
环境变量 ``PAPERSEEK_HF_ENDPOINT`` 或 ``HF_ENDPOINT`` 可覆盖 HuggingFace 下载端点；
默认走 hf-mirror 镜像以适配国内网络。
"""

from __future__ import annotations

import os
from pathlib import Path

# 项目根目录：src/paperseek/config.py -> 上三级
ROOT_DIR: Path = Path(__file__).resolve().parents[2]

DATA_DIR: Path = ROOT_DIR / "data"
RAW_DIR: Path = DATA_DIR / "raw"
INDEX_DIR: Path = DATA_DIR / "index"
PROCESSED_DIR: Path = DATA_DIR / "processed"
LOCAL_PDF_DIR: Path = DATA_DIR / "local_pdfs"

SCIFACT_DIR: Path = RAW_DIR / "scifact"
EXPERIMENTS_DIR: Path = ROOT_DIR / "experiments"
RUNS_DIR: Path = EXPERIMENTS_DIR / "runs"
FIGURES_DIR: Path = EXPERIMENTS_DIR / "figures"
LOGS_DIR: Path = ROOT_DIR / "logs"

# 默认语义模型：轻量、可在 16GB 内存/CPU 上运行（SRS 1.4 约束）
DEFAULT_SBERT_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
# 可选对照模型（科学文献领域专用，体积更大，P1 拓展实验用）
SCIENTIFIC_SBERT_MODEL: str = "sentence-transformers/allenai-specter"

DEFAULT_TOP_K: int = 10
DEFAULT_SCOPES = ("scifact", "local_pdf")
DEFAULT_RETRIEVERS = ("tfidf", "bm25", "sbert", "rrf")

# 评价默认截断：SRS 6.2 要求 NDCG@10、Recall@10、MRR@10，辅以 P@5/R@5
DEFAULT_CUTOFFS = (5, 10)

# 检索器可调参数默认值（写入 IndexManifest.params，保证实验可复现）
BM25_PARAMS = {"k1": 1.5, "b": 0.75}
TFIDF_PARAMS = {
    "ngram_range": (1, 2),
    "min_df": 1,
    "sublinear_tf": True,
    "analyzer": "word",
}
RRF_PARAMS = {"k": 60, "depth": 100, "components": ("bm25", "sbert")}

# SBERT 编码批大小（GPU/CPU 通用保守值）
SBERT_BATCH_SIZE = 64
# PDF 片段切分参数
CHUNK_MAX_CHARS = 1000
CHUNK_OVERLAP = 150


def configure_hf_mirror() -> str:
    """在下载/加载 HuggingFace 模型前调用，返回实际使用的 HF 端点。

    优先使用已显式设置的 ``HF_ENDPOINT``；否则使用 ``PAPERSEEK_HF_ENDPOINT``；
    最后默认 hf-mirror 镜像。已设置的环境变量不会被覆盖。
    """
    endpoint = (
        os.environ.get("HF_ENDPOINT")
        or os.environ.get("PAPERSEEK_HF_ENDPOINT")
        or "https://hf-mirror.com"
    )
    os.environ["HF_ENDPOINT"] = endpoint
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    return endpoint


def ensure_directories() -> None:
    """创建运行时需要的目录（幂等）。"""
    for path in (
        DATA_DIR,
        RAW_DIR,
        INDEX_DIR,
        PROCESSED_DIR,
        LOCAL_PDF_DIR,
        EXPERIMENTS_DIR,
        RUNS_DIR,
        FIGURES_DIR,
        LOGS_DIR,
    ):
        path.mkdir(parents=True, exist_ok=True)
