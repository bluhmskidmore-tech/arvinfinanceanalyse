# V2_TO_V3_MIGRATION_INVENTORY

## 1. 目的

本清单用于固化：

- 哪些模块已经从 `MOSS-V2` 迁入 `MOSS-V3`
- 这些模块在 `V3` 中属于什么层级
- 它们当前是“基础库可用”、还是“已接入主流程”

本清单是迁移资产台账，不等同于“全部已上线”或“全部已进入 formal 主口径”。

---

## 2. 状态定义

- `library`：已迁入、可导入、可复用，但未必已接入主流程
- `wired`：已接入 `route -> service -> repository/core_finance -> frontend` 或等价主链路
- `candidate`：已迁入但当前仅作为后续能力储备，暂未纳入主链路

## 2.1 V3 实现状态定义

- `库级实现`：代码已在 `V3` 仓库中落成，可导入、可复用
- `主流程实现`：已接入 `backend` 主流程中的 service / repository / task / core_finance 主链路之一
- `端到端实现`：已形成 `route -> service -> repository/core_finance -> frontend` 或等价完整链路

---

## 3. 基础工具层（V2 -> V3）

以下文件带有明确的 `自 MOSS-V2 ... 迁入` 标记，定位为 `core_finance` 基础工具层。

| 文件 | 角色 | 当前状态 | V3实现状态 |
| --- | --- | --- | --- |
| `backend/app/core_finance/safe_decimal.py` | Decimal 安全转换；防御 `NaN / Inf / numpy` | `library` | `库级实现` |
| `backend/app/core_finance/decimal_utils.py` | `to_decimal / fmt_yuan / fmt_yi / fmt_money` | `library` | `库级实现` |
| `backend/app/core_finance/rate_units.py` | 利率单位换算：`pct <-> decimal <-> bp`；含启发式归一 | `library` | `库级实现` |
| `backend/app/core_finance/var_engine.py` | 参数法 VaR：`DV01 × z_score × vol` | `library` | `库级实现` |
| `backend/app/core_finance/reconciliation_checks.py` | `Position vs Ledger vs PnL` 对账纯函数 | `library` | `库级实现` |
| `backend/app/core_finance/fx_rates.py` | USD/CNY 汇率回溯取值；30 天回看；默认值 `7.25` | `library` | `库级实现` |

说明：

- 这 6 个文件属于“已迁入的基础模块库”。
- 它们当前是否被 `V3` 正式主流程全面消费，是单独问题；不影响其作为有效迁移资产登记。

---

## 4. 业务计算与配置层（V2 -> V3）

以下文件带有明确的 `自 MOSS-V2 core_finance/config 迁入` 标记，定位为业务规则/配置库。

| 文件 | 角色 | 当前状态 | V3实现状态 |
| --- | --- | --- | --- |
| `backend/app/core_finance/config/classification_rules.py` | 资产/负债/同业/投资类型分类规则 | `library` | `库级实现` |
| `backend/app/core_finance/config/product_category_mapping.py` | 产品类别科目映射表 | `library` | `库级实现` |
| `backend/app/core_finance/config/__init__.py` | 对外导出上述规则和映射 | `library` | `库级实现` |

当前说明：

- 这组文件已迁入 `V3`，但当前产品分类任务主链路仍实际使用 `backend/app/config/product_category_mapping.py`。
- 因此它们目前应视为“已迁入可用规则库”，不应误判为“已成为唯一权威入口”。

治理要求：

- 后续若要在 `V3` 正式主链路启用该组配置，必须先明确唯一权威入口。
- 在唯一权威入口未确定前，禁止并行扩散两套配置来源。

---

## 5. API 已接线实现（V2 迁移资产在 V3 落地）

以下链路已确认属于“已落地并接线”的实现层。

### 5.1 Liability Analytics

| 文件 | 角色 | 当前状态 | V3实现状态 |
| --- | --- | --- | --- |
| `backend/app/core_finance/liability_analytics_compat.py` | 负债分析核心计算 | `wired` | `主流程实现` |
| `backend/app/services/liability_analytics_service.py` | 负债分析服务编排 | `wired` | `主流程实现` |
| `backend/app/repositories/liability_analytics_repo.py` | DuckDB 只读查询封装 | `wired` | `主流程实现` |
| `backend/app/api/routes/liability_analytics.py` | API 路由入口 | `wired` | `端到端实现` |
| `frontend/src/api/client.ts` 中 liability 相关接口 | 前端 API 消费层 | `wired` | `端到端实现` |
| `frontend/src/features/liability-analytics/pages/LiabilityAnalyticsPage.tsx` | 前端页面 | `wired` | `端到端实现` |

当前已确认链路：

`route -> service -> repository + core_finance -> frontend`

当前已验证：

- 后端相关测试通过
- 前端 API client / route registry 相关测试通过

说明：

- `liability_analytics_compat.py` 文件头未显式写出 `自 MOSS-V2 迁入`，但当前作为迁移资产已在 `V3` 形成完整落地链路。

---

## 6. 非 V2 迁移但已迁入能力

以下模块已迁入 `V3`，但其注释显示来源不是 `MOSS-V2`，而主要是旧版宏观分析代码。

### 6.1 Macro 分析能力

目录：

- `backend/app/core_finance/macro/`

当前说明：

- 该组文件主要标注为 `自 V1 macro_analysis ... 迁入`
- 当前应与 `V2 -> V3` 迁移资产分开记录
- 其定位更适合标记为 `candidate`

换言之：

- 它们是“已迁入 V3 的可用能力”
- 但不是“本清单中的 V2 -> V3 迁移资产主体”

---

## 7. 当前结论

截至本清单固化时，`V2 -> V3` 迁移资产可按下述方式理解：

1. 基础工具层已经到位：
   `safe_decimal / decimal_utils / rate_units / var_engine / reconciliation_checks / fx_rates`
2. 业务规则与配置层已经迁入：
   `core_finance/config/*`
3. 已经真正接入 `V3` 主流程并形成落地链路的代表切片是：
   `liability analytics`
4. `macro/*` 这批能力应单独记录为“非 V2 主体迁移来源”

---

## 8. 后续使用规则

- 新功能优先复用本清单内已迁入基础工具，不重复造同类函数。
- 在 `library` 升级为 `wired` 前，必须先定义：
  - 唯一权威入口
  - 上下游调用链
  - 验证方式
- 不允许把“文件已迁入”表述成“功能已上线”。
- 不允许把“可导入基础库”表述成“formal 主口径已采用”。

---

## 9. 变更维护规则

当后续发生以下任一情况时，应更新本清单：

- 某个 `library` 模块被接入主流程
- 某个 `candidate` 模块被正式纳入 API / service / frontend 链路
- 某个重复配置源被废弃并确立唯一权威入口
- 某个迁移模块被明确判定为不再使用
