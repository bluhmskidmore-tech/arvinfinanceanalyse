# TESTING

## 测试布局

仓库当前有两套主要测试面：

- 后端 / repo 级测试：`tests/`
- 前端组件与页面测试：`frontend/src/test/`

另外还有两类辅助验证资产：

- `tests/golden_samples/`: golden sample 数据和断言
- `sample_data/`: 示例运行数据

## 后端测试

`pytest.ini` 把默认测试根固定在 `tests/` 和 `backend/tests/`，并排除了 `.omx`、`.venv`、`tmp*` 等目录。

### 先确定解释器（重要）

**不要用裸 `python`。** 开发机上 `python` 常被无关 venv 遮蔽——本机实测解析到一个 agent 用的
venv，里面根本没有 pytest。更危险的情况是它解析到另一个**装了 pytest 但依赖版本不同**的环境：
命令不报错，跑出一片绿灯，而这个绿灯与本仓库的实际状态无关。

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

- POSIX 下对应 `.venv/bin/python -m pytest -q`。
- CI 里 `uv sync --frozen` 已把 venv 前置进 `PATH`/`VIRTUAL_ENV`，所以 `.github/workflows/ci.yml`
  里的裸 `python` 是安全的；本机没有这层保障。
- 同一纪律见 `scripts/README.md`（「本机 `python` 可能被无关 venv 遮蔽，故脚本从不直接调 `python`」）、
  `scripts/dev-python.ps1::Resolve-DevPython` 和 `docs/GLOBAL_DATA_REFRESH_RUNBOOK.md`。

### 跑窄范围

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_balance_analysis_api.py
.\.venv\Scripts\python.exe -m pytest -q tests/test_pnl_api_contract.py tests/test_pnl_bridge_core.py
.\.venv\Scripts\python.exe -m pytest -q tests/test_product_category_pnl_flow.py
```

### 关于 `pytest.ini` 里的 marker 子集

`pytest.ini` 顶部提到的 `-m "unit and not materialize"` **不是**提交前自查门禁：全仓 9882 个用例里
它只选中 116 个（约 1.2%，2026-08-13 实测；只有 9 个测试文件带 `@pytest.mark.unit`）。它适合在改
那几个文件时做快速回路，跑绿说明不了其余 ~9700 个用例的任何事情。同段的 `-n 4` 并行提示是准确的
（`pytest-xdist` 已安装）。

## Canonical backend gate

当前仓库明确把下面这个脚本作为 repo-wide Phase 2 formal-compute mainline 的 canonical backend gate：

```powershell
.\.venv\Scripts\python.exe scripts/backend_release_suite.py
```

`scripts/backend_release_suite.py` 默认只运行隔离、可重复的有界测试；治理 lineage 由
`tests/test_governance_lineage_audit.py` 的临时夹具覆盖，不读取本机 `data/governance`。

### 套件成员清单去哪儿看

**唯一权威源是脚本里的常量** `RELEASE_SUITE_TESTS` / `GOVERNANCE_MCP_FAST_SUITE_TESTS` /
`GOVERNANCE_MCP_FULL_SUITE_TESTS`。本文不再抄一份会漂移的副本——之前抄的那份只有 13 项，而
实际是 30 项。要看当前清单，直接打印执行计划：

```powershell
.\.venv\Scripts\python.exe scripts/backend_release_suite.py --dry-run
```

输出 JSON 的 `pytest_args` 就是第一阶段的文件序列，`governance_mcp_suite.pytest_args` 是第二阶段。

带说明的受控镜像见 [ci-release-suite.md](ci-release-suite.md)：它按「基 / 保护面」分组解释每个文件
为什么在套件里，并自带一条与脚本常量比对的一致性校验命令。（注意：该文件当前的中文正文存在编码
损坏，表格里的测试文件路径仍然可读且准确——见下方「已知问题」。）

如果你在做 repo-wide formal-compute 主线变更，这个门禁比“跑一次全量 pytest”更接近仓库定义的发布标准。

只有在明确要审计某个本机/部署运行目录时，才使用实时模式：

```powershell
.\.venv\Scripts\python.exe scripts/backend_release_suite.py `
  --live-governance-dir data/governance `
  --governance-audit-output governance-lineage-audit.json
```

实时模式在未扫描到治理文件时会失败，避免“空目录绿灯”。

## 前端测试

前端命令定义在 `frontend/package.json`：

```bash
cd frontend
npm run lint
npm run typecheck
npm run test
npm run debt:audit
npm run build
```

对应含义（与 `frontend/package.json` 的 `scripts` 逐字对齐）：

| 命令 | 实际执行 | 说明 |
| --- | --- | --- |
| `npm run lint` | `eslint .` | |
| `npm run typecheck` | `tsc --noEmit -p tsconfig.app.json && tsc --noEmit -p tsconfig.node.json` | 两个 tsconfig 都跑，不是单个 `tsc --noEmit` |
| `npm run test` | `node scripts/vitest-safe.mjs run` | 经 wrapper 调 Vitest，不是直接 `vitest run` |
| `npm run debt:audit` | `node ../scripts/audit_frontend_debt.mjs && node ../scripts/audit_visual_tokens.mjs` | **CI `frontend` job 的必过步骤**，`frontend/AGENTS.md` 也要求它；改前端时别漏 |
| `npm run build` | `tsc -b && vite build && npm run guard:candidate-financial-indicators` | 构建后还有一道候选金融指标守卫 |

`frontend/package.json` 里还有 `test:a11y-smoke`（Playwright，CI 也跑）、`guard:*` 系列启动包守卫、
`style:audit` / `style:inventory` 等；需要时直接看该文件的 `scripts` 段，不要依赖二手转述。

## 推荐验证策略

### 页面显示逻辑改动

至少覆盖：

- 前端 adapter / formatter / selector 测试
- 对应页面或组件测试
- 若后端返回语义变动，再补 API contract / service / core tests

### 后端 formal compute 改动

至少覆盖：

- `backend/app/core_finance/` 对应单测
- 相关 service / API contract 测试
- 必要时跑 `.\.venv\Scripts\python.exe scripts/backend_release_suite.py`

### 文档或边界文档改动

仓库里已有一批文档契约测试可直接使用，例如：

- `tests/test_backend_release_gate_docs.py`
- `tests/test_balance_analysis_docs_contract.py`
- `tests/test_fx_docs_contract.py`

## Golden samples

`tests/golden_samples/` 下已经按场景拆出多组样本，例如：

- `GS-BAL-OVERVIEW-A`
- `GS-BRIDGE-A`
- `GS-PNL-DATA-A`
- `GS-PNL-OVERVIEW-A`
- `GS-RISK-A`

如果你在改输出语义、页面结论或图表结果，这些目录是回归检查的天然对照面。

## CI

`.github/workflows/ci.yml` 当前有 **10 个 job**（2026-08-13 核对）。触发面：`push` 到 `main` /
`codex/**`、`pull_request` → `main`、以及每日 `18:00 UTC` 的 schedule。后端各 job 统一用
`uv sync --frozen --project backend --extra dev` 装依赖并把该 venv 前置进 `PATH`。

| Job | 名称 | 何时跑 | 内容 |
| --- | --- | --- | --- |
| `backend` | Backend Tests | 全部 | `uv lock --check` → `scripts/backend_release_suite.py` → 10 个 agent harness / caliber 映射测试 → **caliber path-trigger gate**（仅 PR：diff 触及 `CALIBER_GATE_MAP` 里的口径源文件时，强制跑对应红线测试；拿不到 base-ref 即 fail-closed） |
| `agent-eval-replay` | Agent Eval Replay | 仅 PR | 按 diff 与任务 `allowed_scope` 交集选任务跑重放评测，scorecard 发到 step summary + PR 评论。**评测 fail/void 不阻塞合并**；此 job 变红只代表编排自身故障 |
| `backend-full-pytest` | Backend Full Pytest | 仅 schedule 或 push→`main` | 全量 `python -m pytest -q`，产出 junit XML + 控制台日志；schedule 失败时自动开/追评 `ci-full-pytest-failure` issue |
| `backend-lint` | Backend Ruff | 全部 | `ruff check backend scripts tests --select S110,S112` 硬门禁（静默异常，存量已清零）+ BLE001 棘轮报数（不阻断） |
| `mypy-ratchet` | Backend Mypy Ratchet | 全部 | `scripts/check_mypy_baseline.py`，mypy 钉在 1.20.1。**当前 `continue-on-error: true`**，属观察模式，红了不拦 |
| `frontend` | Frontend Tests | 全部 | typecheck → Vitest → **`npm run debt:audit`** → `VITE_DATA_SOURCE=real npm run build` → a11y smoke → stock-analysis mock smoke（后两项走 Playwright/Chromium） |
| `lint` | Frontend Lint | 全部 | `node scripts/check_surface_naming.mjs` + `npx eslint .` |
| `api-contract` | API Contract | 全部 | `scripts/api_contract_check.py export-openapi` → `spectral lint ... -r .spectral.yaml` |
| `secrets` | Secret Scan | 全部 | Gitleaks（`scripts/supply_chain_security_scan.py --tool gitleaks`）+ 供应链扫描计划 dry-run，报告上传为 artifact |
| `osv` | OSV Dependency Scan | 全部 | OSV-Scanner 2.3.0 取证 → SARIF 转换与上传 → `scripts/osv_reconciliation_gate.py evaluate` 只按 `docs/audits/osv-reconciliation-records.json` 里的精确元组对账，其余判红 |

要点：

- **本地能覆盖的只是其中一部分。** 密钥扫描、OSV、spectral 契约、Ruff 硬门禁、mypy 棘轮、
  定时全量 pytest、caliber 路径触发这些门禁，`scripts/backend_release_suite.py` 一条都不包含。
  跑完 release suite 只等于 `backend` job 的主步骤通过。
- 本地验证要与 CI 同向：至少覆盖你实际改动那一面对应的 job，而不是随手挑一个与 CI 无关的自定义命令。
- 这张表是 `ci.yml` 的镜像，会漂移。判断当前真实门禁以 `.github/workflows/ci.yml` 为准。

## 已知问题

- `docs/ci-release-suite.md` 的中文正文处于**双重编码损坏**状态（UTF-8 被按 GBK 误读后再存为
  UTF-8，且带 BOM），且自引入该文件的 commit `ec531070` 起就是坏的——不是后来的回归。反向还原
  时部分字符落在私用区/替换符，无法完全无损恢复。ASCII 部分——测试文件路径、命令、表结构——
  仍然完整可读可用。修复需要人工重写受损段落，尚未处理。
