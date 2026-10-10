# PnL 计算源分类与复用边界

本文只整理仓库已经存在的 PnL 计算权威和复用边界，不新增业务规则或指标。

## 1. 复用判定

PnL 函数只有在以下属性全部一致时才能共用一个计算源：

- 输入事实与 `source_kind`
- `report_date`、期间起止和 monthly / QTD / YTD 窗口
- `currency_basis` 与 FX 顺序
- formal / standardized / analytical / diagnostic 语义
- 514 / 516 / 517 会计确认矩阵
- realized / unrealized、累计 / 当期语义
- VAT 税基、金额单位、精度、舍入和 `null` 规则

函数体当前相同、页面标签相同或结果碰巧相等，都不足以证明同口径。

## 2. 权威计算族

| 计算族 | 唯一权威 | 允许复用范围 | 明确不得混用 |
| --- | --- | --- | --- |
| Formal 514 / 516 / 517 与正式总损益 | `backend/app/core_finance/pnl.py` | `/pnl` formal fact、overview/data 读面及需要正式实际损益的下游 | standardized total、未批准 adjustment、OCI 516、未满足 realized/event 语义的 517 |
| PnL Bridge | `backend/app/core_finance/pnl_bridge.py` | 桥接行和桥接汇总 | `unrealized_fv` 是解释对象，不得再次计入 `explained_pnl`；桥接分解项不得替代 formal actual PnL |
| 产品分类损益与利差 | `backend/app/core_finance/product_category_pnl.py` | 产品分类页面、正式产品分类读模型 | monthly 与 YTD、含 TPL 与生息资产利差不得互换；不得回写为 Formal PnL 事实 |
| 业务种类正式洞察 | `backend/app/core_finance/pnl_by_business_insights.py` | `MTR-PNLBIZ-001`~`007` 对应读面 | diagnostic-only 的 `MTR-PNLBIZ-006` 不得作为业务贡献结论 |
| Service 叶子工具 | `backend/app/services/pnl_service_shared_utils.py` | 无业务口径的日期、文本、Decimal、JSON 和幂等辅助 | 不承载 514/516/517、VAT、收益率、FTP 或期间业务公式 |

## 3. 本轮已收敛的完全重复项

| 兼容消费方 | 原重复函数 | 当前复用源 | 语义 |
| --- | --- | --- | --- |
| `pnl_bond_bucket_merge.py` | `_calendar_days` | `pnl_service_shared_utils._calendar_days` | 闭区间自然日计数；仅为 service 参数准备 |
| `pnl_by_business_unallocated.py` | `_decimal_value` | `pnl_service_shared_utils._decimal_value` | `None` / 空值按现有服务契约转 `Decimal(0)` |
| `pnl_by_business_unallocated.py` | `_norm_text` | `pnl_service_shared_utils._norm_text` | 文本去首尾空白；空值转空串 |
| `pnl_by_business_candidate_insights.py` | `_trailing_month_keys` | `pnl_by_business_insights.trailing_month_keys` | `MTR-PNLBIZ-003/004` 使用的升序滚动自然月窗口 |

`tests/test_pnl_service_utility_reuse.py` 锁定函数对象同一性，防止这些适配模块
重新复制工具实现。

## 4. 已发现但暂不合并的候选

| 候选 | 当前判断 | 后续门槛 |
| --- | --- | --- |
| `_coerce_date`（formal PnL / bridge） | 实现相同，但处于两个正式模型边界，且 formal PnL 正有在途修改 | 稳定后冻结异常、时区和输入类型契约，再决定共享 core helper |
| `_quantize_amount` / `_quantize_decimal` / `_quantize_pct` | 当前实现相似或相同，但分别代表金额和百分比精度 | 先冻结单位、精度及舍入契约；不得按函数体直接合并 |
| `_period_label_cn`（workbench / service） | 展示文本重复，不属于正式金融公式 | 可在独立展示适配层清理，不与本轮业务计算混合 |
| refresh 幂等与 stale-run helpers | 操作流程重复，不属于指标口径 | 应单独做 refresh workflow 收敛，不能借指标重构顺带修改 |

## 5. 变更纪律

- 正式金融公式只进入 `backend/app/core_finance/`。
- service 只编排、适配并复用权威结果，不复制正式公式。
- 前端只格式化和展示，不重新计算正式总额、收益率、FTP 或桥接残差。
- 正在修改的 PnL 口径文件必须先完成自身合同验证，再进入下一轮复用收敛。
