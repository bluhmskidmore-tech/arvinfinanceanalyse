# TESTING

## 测试布局

仓库当前有两套主要测试面：

- 后端 / repo 级测试：`tests/`
- 前端组件与页面测试：`frontend/src/test/`

另外还有两类辅助验证资产：

- `tests/golden_samples/`: golden sample 数据和断言
- `sample_data/`: 示例运行数据

## 后端测试

`pytest.ini` 把默认测试根固定在 `tests/`，并排除了 `.omx`、`.venv`、`tmp*` 等目录。

### 直接运行

```bash
python -m pytest -q
```

### 跑窄范围

```bash
python -m pytest -q tests/test_balance_analysis_api.py
python -m pytest -q tests/test_pnl_api_contract.py tests/test_pnl_bridge_core.py
python -m pytest -q tests/test_product_category_pnl_flow.py
```

## Canonical backend gate

当前仓库明确把下面这个脚本作为 repo-wide Phase 2 formal-compute mainline 的 canonical backend gate：

```bash
python scripts/backend_release_suite.py
```

`scripts/backend_release_suite.py` 会先跑治理 lineage audit，再执行一组有界测试文件，包括：

- `tests/test_settings_contract.py`
- `tests/test_health_endpoints.py`
- `tests/test_positions_api_contract.py`
- `tests/test_pnl_api_contract.py`
- `tests/test_risk_tensor_api.py`
- `tests/test_balance_analysis_api.py`
- `tests/test_bond_analytics_api.py`
- `tests/test_executive_dashboard_endpoints.py`
- `tests/test_cube_query_api.py`
- `tests/test_liability_analytics_api.py`
- `tests/test_result_meta_on_all_ui_endpoints.py`
- `tests/test_governance_doc_contract.py`
- `tests/test_golden_samples_capture_ready.py`

如果你在做 repo-wide formal-compute 主线变更，这个门禁比“跑一次全量 pytest”更接近仓库定义的发布标准。

## 前端测试

前端命令定义在 `frontend/package.json`：

```bash
cd frontend
npm run lint
npm run typecheck
npm run test
npm run build
```

对应含义：

- `npm run lint`: ESLint
- `npm run typecheck`: `tsc --noEmit`
- `npm run test`: `vitest run`
- `npm run build`: `tsc -b && vite build`

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
- 必要时跑 `python scripts/backend_release_suite.py`

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

`.github/workflows/ci.yml` 当前包含三个 job：

- `backend`: 安装 `./backend[dev]` 并运行 `python scripts/backend_release_suite.py`
- `frontend`: 安装前端依赖并运行 TypeScript type check + Vitest
- `lint`: 运行 `node scripts/check_surface_naming.mjs` 和 ESLint

本地验证最好与 CI 方向保持一致，不要只跑一个与 CI 完全无关的自定义命令。
