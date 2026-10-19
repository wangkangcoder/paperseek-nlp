"""测试公共配置：把 src 加入导入路径，提供小样本夹具。

注意：重型依赖（sentence-transformers / torch / PyMuPDF）在具体测试中用
``pytest.importorskip`` 跳过，保证 CI 环境（requirements-ci.txt）也能跑通轻量测试。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@pytest.fixture()
def tiny_documents():
    """4 篇小语料，覆盖同义词、术语差异等检索场景。"""
    from paperseek.schemas import Document

    return [
        Document(
            doc_id="d1",
            title="Time-Frequency Analysis of Nonstationary Signals",
            text="This paper studies time-frequency resolution using short-time Fourier transform "
            "and wavelet transform for nonstationary signals.",
        ),
        Document(
            doc_id="d2",
            title="Deep Learning for Speech Enhancement",
            text="A neural network improves speech enhancement in noisy environments using "
            "spectrogram masking and recurrent layers.",
        ),
        Document(
            doc_id="d3",
            title="Wavelet Transform in Biomedical Signal Processing",
            text="Wavelet transform is applied to electrocardiogram denoising and biomedical "
            "signal analysis, improving time-frequency localization.",
        ),
        Document(
            doc_id="d4",
            title="Information Retrieval with BM25",
            text="The BM25 ranking function combines term frequency and inverse document "
            "frequency for document retrieval.",
        ),
    ]


@pytest.fixture()
def tiny_qrels():
    """与 tiny_documents 对应的人工标注（query -> {doc_id: relevance}）。"""
    return {"q1": {"d1": 1, "d3": 1}, "q2": {"d4": 1}}
