# PaperSeek · 科研文献智能语义检索系统

> 自然语言处理课程设计项目
> 依据《PaperSeek 软件需求规格说明书与系统概要设计 V1.0》实现
> 基于 **多特征表示 + 混合检索** 的离线科研文献检索原型

[![CI](https://github.com/wangkangcoder/paperseek-nlp/actions/workflows/ci.yml/badge.svg)](https://github.com/wangkangcoder/paperseek-nlp/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.11%20%7C%203.13-blue)
![License](https://img.shields.io/badge/license-coursework-lightgrey)

## 1. 项目简介

PaperSeek 面向高校师生“文献调研”场景：用户输入自然语言问题，系统在文献库中检索相关论文，
返回标题、排名、得分与原文片段；对本地 PDF 论文库还可定位到具体页码与文件。

项目包含四组可对照的检索方法，并在公开基准 **BEIR SciFact** 上做可复现评价：

| 组别 | 方法 | 文本表示 | 排序 |
| --- | --- | --- | --- |
| A | TF-IDF | 词级 n-gram + 子线性 TF | 余弦相似度 |
| B | BM25 | 词项统计 | Okapi BM25（k1/b 可记录） |
| C | Sentence-BERT | 预训练句向量（MiniLM-L6-v2） | 余弦相似度 |
| D | RRF 混合 | B 与 C 的排名融合 | Reciprocal Rank Fusion |

评价指标：`NDCG@10`、`Recall@10`、`MRR@10`，辅以 `Precision@5`、`Recall@5`、检索延迟与索引时间。

## 2. 主要功能

- **公开基准评价**：SciFact 文献级检索，四组方法同口径对比，指标表 + 图表自动生成；
- **本地 PDF 检索**：导入文本型 PDF，按页切块、保留页码，检索结果可追溯到文件与页；
- **算法对比**：同一问题并排展示不同检索器的 Top-K 与排名差异；
- **可视化界面**：Streamlit 四页面（智能检索 / 论文库管理 / 算法对比 / 实验分析）；
- **可复现与可回退**：数据下载、索引构建、实验运行全部脚本化；git 里程碑 tag + 文件级快照。

## 3. 快速开始

```powershell
# 0) 环境要求：Windows 10/11、Python 3.11+、git；建议 16GB 内存；GPU 可选
# 1) 创建虚拟环境并安装依赖（含 torch；本机可继承已装 torch）
powershell -ExecutionPolicy Bypass -File tools\setup_env.ps1

# 2) 下载公开数据（BEIR SciFact，约 2.8MB）
.\.venv\Scripts\python.exe scripts\download_data.py

# 3) 构建索引（首次约数分钟，SBERT 会下载轻量模型）
.\.venv\Scripts\python.exe scripts\build_index.py

# 4) 运行实验评价，生成指标表与图
.\.venv\Scripts\python.exe scripts\run_evaluation.py --scope scifact --retrievers tfidf,bm25,sbert,rrf
.\.venv\Scripts\python.exe scripts\make_figures.py --run-dir experiments\runs\<最新目录>

# 5) 启动界面
.\.venv\Scripts\streamlit.exe run app\streamlit_app.py

# 6) 跑测试
.\.venv\Scripts\python.exe -m pytest -q
```

> 国内网络说明：模型下载默认走 `HF_ENDPOINT=https://hf-mirror.com`（见 `config.configure_hf_mirror()`），
> 可通过环境变量覆盖为官方端点。

## 4. 目录结构

```
1019/
├── 产品设计.docx              # 原始需求文档（SRS V1.0）
├── README.md
├── requirements.txt           # 运行依赖
├── requirements-ci.txt        # CI 最小依赖
├── src/paperseek/             # 主代码包
│   ├── schemas.py             # 冻结数据结构（Document/SearchResult/IndexManifest…）
│   ├── config.py              # 路径与默认参数
│   ├── data/                  # SciFact 读取与校验
│   ├── preprocessing/         # 文本清洗/分词/停用词/词干
│   ├── retrievers/            # TF-IDF / BM25 / SBERT / RRF
│   ├── evaluation/            # 指标与评价器
│   ├── index/                 # 语料哈希、文档库、索引清单
│   ├── service/               # 统一检索服务
│   └── pdf/                   # PDF 解析、分块、论文库
├── app/streamlit_app.py       # 可视化界面
├── scripts/                   # 数据下载、建索引、实验、图表、导入 PDF
├── tests/                     # pytest 测试
├── docs/                      # 需求/契约/进度/变更/回退/实验/运行说明
├── experiments/               # 实验运行结果与图表
├── tools/                     # 环境搭建、版本回退工具
└── data/                      # 数据与索引（不入库，脚本重建）
```

## 5. 文档索引

| 文档 | 内容 |
| --- | --- |
| [需求基线说明](docs/01_需求基线说明.md) | 从 SRS 提炼的可执行需求与 W1 决策 |
| [接口契约](docs/00_接口契约.md) | 模块接口、数据结构、协作规则（冻结版） |
| [进度文档](docs/02_进度文档.md) | 里程碑、今日进展、需求追踪、风险 |
| [修改记录](docs/03_修改记录.md) | CHG 变更审计与版本/tag 对照 |
| [回退机制](docs/04_回退机制说明.md) | 五层回退体系与典型剧本 |
| [GitHub 协作](docs/07_GitHub协作说明.md) | 分支策略、提交规范、灾备恢复 |
| [运行说明](docs/06_运行说明.md) | 环境、依赖、逐步运行与常见问题 |
| [实验报告](docs/05_实验报告.md) | 真实指标、图表与结果分析 |

## 6. 数据来源

- **BEIR SciFact**（公开基准，BEIR 官方发布）：
  <https://public.ukp.informatik.tu-darmstadt.de/thakur/BEIR/datasets/scifact.zip>
  - corpus 5183 篇 / test qrels 809 条 / 多查询；
  - 引用：Thakur et al., *BEIR: A Heterogenous Benchmark for Zero-shot Evaluation of Information Retrieval Models*, NeurIPS 2021.
- **本地 PDF 论文库**：arXiv 开放获取论文（运行时下载，不入库，遵循各论文许可）。

## 7. 环境

| 项 | 值 |
| --- | --- |
| 操作系统 | Windows 11 |
| Python | 3.13（兼容 3.11+） |
| 深度学习 | torch 2.7.1+cu118，CUDA 可用（RTX 4060 Laptop 8GB） |
| 主要库 | scikit-learn、sentence-transformers、PyMuPDF、streamlit、rank-bm25 |
| 内存 | 16GB |

## 8. 致谢与参考

- BEIR / SciFact 数据集与评测协议；
- Sentence-Transformers、scikit-learn、PyMuPDF、Streamlit 开源项目；
- 课程《自然语言处理》关于文本表示、检索模型与评价指标的教学内容。

## 9. 许可证

课程设计用途。第三方数据与预训练模型遵循其原始许可。
