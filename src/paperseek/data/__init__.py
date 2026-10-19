"""数据处理层：公开基准（SciFact/BEIR）与本地 PDF 论文库的读取与规范化。

模块职责（由数据组实现，接口在本项目契约中冻结）：
- ``paperseek.data.scifact``：读取 BEIR SciFact 的 corpus / queries / qrels；
- ``paperseek.data.normalize``：数据校验（ID 非空、无重复、文本非空）。
"""
