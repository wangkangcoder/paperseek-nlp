# PaperSeek GitHub 协作说明

> 远端仓库：<https://github.com/wangkangcoder/paperseek-nlp>（公开）
> 认证方式：Windows Git Credential Manager（已存凭据），无需在仓库中保存 token。

## 1. 分支策略

| 分支 | 用途 | 规则 |
| --- | --- | --- |
| `main` | 可交付、可运行版本 | 只接受通过 CI 的合并；每个里程碑在此打 tag |
| `dev` | 日常集成分支 | 功能与修复先合入 `dev`，稳定后合入 `main` |
| `backup/pre-rollback-*` | 回退前自动备份 | 由 `tools/rollback.py restore` 创建，不推送 |
| `feature/*` | 可选的功能分支 | 大改动时使用，完成后合入 `dev` |

当前阶段（W1-W5）由单人开发 + 多 Agent 并行，采用“**Lead 统一提交**”模式：
各模块开发者只改文件，不执行 git；Lead 在每个里程碑检查测试后提交、打 tag、推送。

## 2. 提交信息规范

```
<type>(<scope>): <摘要> [CHG-xxx]

type: feat|fix|docs|test|refactor|chore|exp
scope: data|preprocess|retrieval|eval|index|service|pdf|ui|docs|ci|tools
```

示例：

```
feat(retrieval): 实现 BM25 检索器与测试 [CHG-010]
fix(index): 校验语料哈希，避免旧索引误用 [CHG-014]
exp(eval): SciFact 四组检索实验，产出指标表 [CHG-021]
docs(report): 课程设计报告初稿 [CHG-030]
```

每次提交必须在 `docs/03_修改记录.md` 有对应 CHG 记录（或标注 `[tracking]` 的纯文档提交）。

## 3. 里程碑同步流程

```powershell
# 1) 查看状态并跑测试
.\.venv\Scripts\python.exe tools\rollback.py status
.\.venv\Scripts\python.exe -m pytest -q

# 2) 检查点提交 + 打里程碑 tag（--test 会自动跑测试门禁）
.\.venv\Scripts\python.exe tools\rollback.py checkpoint -m "feat(retrieval): W2 稀疏检索可用 [CHG-010]" --tag v0.2.0-w2 --test

# 3) 推送分支与 tag
.\.venv\Scripts\python.exe tools\rollback.py publish
# 等价于：git push -u origin main && git push origin --tags
```

## 4. 换机器 / 灾备恢复

```powershell
git clone https://github.com/wangkangcoder/paperseek-nlp.git
cd paperseek-nlp
powershell -ExecutionPolicy Bypass -File tools\setup_env.ps1   # 建 venv + 依赖 + 数据 + 模型
.\.venv\Scripts\python.exe scripts\download_data.py
.\.venv\Scripts\python.exe scripts\build_index.py
.\.venv\Scripts\python.exe -m pytest -q
```

数据（`data/raw`、`data/index`）与 PDF 语料不入库，由脚本重建；论文库 PDF 通过
`scripts/download_local_corpus.py` + `scripts/import_pdfs.py` 重建。

## 5. CI 说明

- 工作流：`.github/workflows/ci.yml`，push/PR 到 `main`/`dev` 触发；
- 矩阵：Python 3.11 与 3.13；
- 只安装 `requirements-ci.txt`（numpy/pandas/scikit-learn/pytest），
  重型依赖相关测试用 `pytest.importorskip` 自动跳过；
- 一旦 CI 失败，禁止合入 `main`。

## 6. 安全与合规

- 不提交 `HF_TOKEN`、GitHub token、个人隐私数据；
- 论文 PDF 只在本地（`data/local_pdfs/` 已 gitignore），引用遵循开放获取许可；
- 公开实验数据只使用 BEIR SciFact 等公开基准。
