"""PaperSeek 统一异常定义。

所有自定义异常都继承 :class:`PaperSeekError`，便于界面层统一捕获并展示可理解的错误提示
（对应 NFR-04 健壮性、FR-02/FR-07 的错误反馈要求）。
"""

from __future__ import annotations


class PaperSeekError(Exception):
    """所有 PaperSeek 业务异常的基类。"""


class DataFormatError(PaperSeekError):
    """数据文件缺失、格式错误或字段为空/重复。"""


class IndexNotBuiltError(PaperSeekError):
    """索引尚未构建，或索引文件缺失。"""


class ManifestMismatchError(PaperSeekError):
    """索引与当前语料/模型版本不匹配（对应 NFR-08 存储一致性）。"""


class EmptyQueryError(PaperSeekError):
    """查询文本为空（对应 FR-07 自然语言查询校验）。"""


class RetrieverNotFoundError(PaperSeekError):
    """请求的检索器名称未注册。"""


class PDFParseError(PaperSeekError):
    """PDF 无法解析或无可提取文本（对应 FR-12、TC-10）。"""
