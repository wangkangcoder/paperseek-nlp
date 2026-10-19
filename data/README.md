# data 目录说明

本目录存放数据与索引，**除本说明外均不入库**（见 `.gitignore`），由脚本按需重建。

```
data/
├── raw/                 # 原始数据（BEIR SciFact 解压结果、下载的 zip）
│   └── scifact/
│       ├── corpus.jsonl
│       ├── queries.jsonl
│       └── qrels/{train,dev,test}.tsv
├── local_pdfs/          # 本地 PDF 论文库（arXiv 开放论文，运行时下载）
├── processed/           # 中间产物（PDF 解析缓存、导入报告）
└── index/               # 检索索引
    ├── scifact/
    │   ├── documents.jsonl        # 语料文档库（检索单位）
    │   ├── corpus_manifest.json   # 语料哈希/规模/时间
    │   ├── build_report.json      # 本次构建汇总
    │   ├── tfidf/                 # TF-IDF 索引
    │   ├── bm25/                  # BM25 索引
    │   ├── sbert/                 # 句向量索引
    │   └── rrf/                   # RRF 融合索引（含 bm25/、sbert/ 子索引）
    └── local_pdf/                 # 本地 PDF 片段索引（同结构）
```

重建命令：

```powershell
.\.venv\Scripts\python.exe scripts\download_data.py
.\.venv\Scripts\python.exe scripts\build_index.py --scope scifact
.\.venv\Scripts\python.exe scripts\import_pdfs.py
.\.venv\Scripts\python.exe scripts\build_index.py --scope local_pdf
```

注意：索引与语料版本通过 `corpus_hash` 绑定；语料变化后必须重建索引，否则服务层会拒绝加载
（`ManifestMismatchError`）。
