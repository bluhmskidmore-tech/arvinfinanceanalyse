# 08 — 启动、测试与环境（脱敏）

## 前端

| 项目 | 命令 / 路径 |
|------|----------------|
| 开发服务器 | `cd frontend && npm run dev`（Vite：**5888**，代理默认 **7888**）|
| 类型检查（单项目） | `npm run typecheck` → **`tsc --noEmit`** |
| 构建 | `npm run build` → **`tsc -b && vite build`** |
| Lint | `npm run lint` → **ESLint 9** |
| 单元测试 | `npm run test` → **Vitest** |
| Debt / style audit | `npm run debt:audit`、`npm run style:audit` |

## 后端

| 项目 | 命令 / 说明 |
|------|-------------|
| 依赖安装 | **`pip install -e backend/[dev]`**（以 pyproject optional `dev` 为准；无顶层 requirements.txt）|
| 单次 import | **`python -c "import backend.app.main"`** — 本项目执行 **Success** |
| Pytest | 仓库根目录：`python -m pytest` |

## 数据库 / Broker

| 组件 | 说明 |
|------|------|
| Postgres | README dev：`postgresql://moss:moss@127.0.0.1:55432/moss`（**示例，非本项目真实凭证录入**）；compose 常为 `5432` |
| DuckDB | `MOSS_DUCKDB_PATH` 默认 **`data/moss.duckdb`** |
| Redis | `MOSS_REDIS_DSN` |

## 环境变量（脱敏清单 — 名称级）

取自 `backend/app/governance/settings.py`（`MOSS_` 前缀为主的 `BaseSettings` 字段）；**默认值与完整清单以源文件为准**。

| 变量域 | 例（名称） |
|--------|-------------|
| 运行环境与特性开关 | `MOSS_ENVIRONMENT`, `MOSS_AGENT_ENABLED`, `MOSS_FORMAL_PNL_ENABLED`, `MOSS_FORMAL_PNL_SCOPE_JSON` |
| 存储 | `MOSS_POSTGRES_DSN`, `MOSS_GOVERNANCE_SQL_DSN`, `MOSS_JOB_STATE_DSN`, `MOSS_REDIS_DSN`, `MOSS_DUCKDB_PATH`, `MOSS_GOVERNANCE_PATH`, `MOSS_LOCAL_ARCHIVE_PATH` |
| MinIO | `MOSS_OBJECT_STORE_MODE`, `MOSS_MINIO_*` |
| 外部数据 | `MOSS_CHOICE_*`, `MOSS_TUSHARE_*`, `MOSS_FX_*`, `CHOICE_*`（兼容前缀）|
| FTP / 归因 | `MOSS_FTP_RATE_PCT`（Decimal）|
| HTTP / CORS | `MOSS_CORS_ORIGINS`（逗号分隔）|
| 身份 hints | **`MOSS_USER_ID`**, **`MOSS_USER_ROLE`**（辅助 `AuthContext`）|

**前端 Vite：`MOSS_VITE_API_PROXY`**（后端代理目标）。

**脱敏拷贝位置**：`audit_pack/source_snapshot/redacted_env/*_redacted.txt` + 模板 `config/.env.example`、`frontend/.env.example`。  
勿将真实密钥重新贴入聊天记录。

---

## 本次会话执行记录（摘要）

### 1）`frontend`：`npm run typecheck`

退出码：**0**。输出仅显示运行 `tsc --noEmit`，无报错行。

### 2）`frontend`：`npm run lint`

退出码：**1**。

```
F:/MOSS-V3/frontend/src/components/GridContainer.tsx — unused import designTokens
F:/MOSS-V3/frontend/src/features/average-balance/components/AverageBalanceView.tsx — react-refresh/only-export-components (warning)
F:/MOSS-V3/frontend/src/features/executive-dashboard/components/OverviewSection.tsx — no-explicit-any
```

### 3）仓库根：`python -m pytest -q`

**收集阶段失败**。示例错误：

```
ImportError: cannot import name '_HOME_SNAPSHOT_DOMAINS'
from backend.app.services.executive_service'
(in tests/test_home_snapshot_endpoint.py)
```

→ 测试模块与 **`executive_service` 导出** 脱节；需在修复测试或恢复符号后再跑全套。

### 4）`frontend`：`npm run build`

**`tsc -b` 阶段失败**。代表性 TS 报错（截取）：

- `KpiCard.tsx`：`CSSProperties` 与 `FlexDirection`、`OverflowWrap` 等字面量联合类型不匹配。  
- `crossAssetTrendChart.ts`：`legend.animationType` 非 ECharts 类型定义字段。  
- `DashboardBondHeadlineSection.tsx`：`GridContainer` 传入未知 `gap`；tone prop 字面量不匹配。  
- `LiabilityAnalyticsPage.tsx`：`'getCockpitWarnings'`、`'getContributionSplit'` 存在于调用但 **`ApiClient` 类型无上此成员**。
- **`BalanceAnalysisPage.test.tsx`**：mock **`AdbComparisonResponse`** 缺 `calendar_days_inclusive`、`adb_denominator_basis`。

### 5）后端 import smoke

命令：`python -c "import backend.app.main"`

结果：**退出码 0**，打印 `import ok`。

### 环境与版本注记

本会话 pytest 运行在 **Python 3.14.2**（栈追踪所示），而 **`pyproject.toml` 申明 `requires-python = ">=3.11"`**。**3.14** 对部分原生 wheel / 运行时行为可能异于团队基线 CI，需在正式 CI 对齐版本后复测 pytest。

---

## 建议门禁顺序（复核用）

1. 固定 **`Python` 次要版本** 与 locks。  
2. `pytest tests/...` — 先修 `executive_service`/`test_home_snapshot_endpoint` ImportError，再全集。  
3. `npm run build` — 先于 `vite build` 清掉 `tsc -b` 错误。  
4. `npm run lint` — 对齐 ESLint baseline。  
