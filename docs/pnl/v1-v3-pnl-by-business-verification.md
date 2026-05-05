# 业务种类损益：V1（3888）与 V3（5888）核对证据

本文档落实「PnL by business：V1 与 V3 差异核实计划」的可复现证据与结论归类（不修改计划原文）。

## 1. V1 侧「Network」等价证据（仓库内文档）

本仓库不包含 3888 旧前端源码；V1 行为以产品/迁移文档为准：

- [docs/superpowers/specs/2026-04-18-v1-v3-parity-matrix.md](../superpowers/specs/2026-04-18-v1-v3-parity-matrix.md)：`/pnl-by-business` 对应 **`/api/pnl/by-business`** 与年度汇总等。
- [audit_pack/source_snapshot/docs/handoff/2026-04-18-backend-endpoint-handoff.md](../../audit_pack/source_snapshot/docs/handoff/2026-04-18-backend-endpoint-handoff.md)：V1 路由含 **`/api/pnl/by-business`**、**`/api/pnl/yearly-summary`**。

**你在本机 3888 仍应做一次 Network 截图/导出**，确认实际路径是否为 `by-business` / `yearly-summary` / 其它，以排除部署差异。

## 2. V3 后端：同一报表日两条 API 对照命令

在 API 已启动（例如 `127.0.0.1:7888`）且 DuckDB 有数据时执行：

```powershell
# 单日 formal 汇总（与 fact_formal_pnl_fi 物化口径一致）
curl -s "http://127.0.0.1:7888/api/pnl/by-business?report_date=2025-12-31" | jq ".result.summary, .result.rows[0:3]"

# 年累计 YTD（刷新包 + ZQTZ 拆桶；行可加总≠总损益属设计说明）
curl -s "http://127.0.0.1:7888/api/pnl/by-business-ytd?year=2025&as_of_date=2025-12-31" | jq ".result.total_pnl, .result.period_label, .result.items[0:3]"
```

自动化契约（不依赖本机服务）：见 `tests/test_pnl_api_contract.py` 中 `test_pnl_by_business_traces_formal_fi_to_zqtz_business_type_primary`、`test_pnl_by_business_ytd_*`。

## 3. 差异归类（结论）

| 类别 | 说明 |
|------|------|
| **时间维** | V3 原默认页仅用 **`/api/pnl/by-business-ytd`**（当年多报表日刷新包累加）；V1 常见为 **`/api/pnl/by-business` 单日**——直接比数字会错。 |
| **总 vs 行** | YTD 的 `result.total_pnl` 与各行 `items[].total_pnl` 之和可不等（多桶重叠）；单日 formal 表以 `summary.total_pnl` 与 SQL 聚合行为为准。 |
| **VAT / 符号** | YTD 路径经 `_iter_v1_compatible_pnl_records`（见 `backend/app/services/pnl_service.py`）；单日 formal 直接读物化事实列。 |
| **日均与年化** | 原 YTD 页用 `getAdbComparison` 区间 + 前端年化公式；单日 formal 用行内 **`yield_pct`**（损益/规模×100 语义，见仓库测试断言）。 |

## 4. 产品对齐（已实施）

在 **方案 A** 下，工作台 `/pnl-by-business` 增加 **「报表日 formal」** 视图，调用已有 **`getPnlByBusiness`**，便于与 V1 Network 中的 `by-business` 逐字段对照；默认仍为 **年累计（YTD）**。

若需 **方案 B**（仅强化文案、不增加 formal 视图），可再收敛 UI。

## 5. 本实施验证输出（2026-05-05）

```text
pytest tests/test_pnl_api_contract.py -k "by_business" -q --tb=no
# 5 passed, 47 deselected

npx vitest run src/test/PnlRoutesSmoke.test.tsx
# 3 passed（含 /pnl-by-business 默认 YTD + 切换 formal 后 getPnlByBusiness 调用断言）

npm run debt:audit
# Frontend debt audit passed (no growth over baseline).
```
