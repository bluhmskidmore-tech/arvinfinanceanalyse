# 2026-06-10 MOSS Owner Review Brief

## 用途

这份 brief 用于把系统审计转成业务 owner 可开会裁决的议程。它只重组已有审计证据，不批准任何指标、页面、治理记录或 owner 签核。

当前状态覆盖至 `2026-08-06T22:30:00+08:00`。文件名保留 2026-06-10 审计来源；当时的 10 项状态仅作历史基线，当前会议只处理 8 项未决事项。

## 会议应输出什么

| 输出项 | 必填内容 | 不可替代项 |
| --- | --- | --- |
| 8 个剩余计算/展示 P1 裁决 | 每个剩余 P1 选择一个权威口径，或要求补充源数据证据 | 不能用当前测试通过替代口径裁决；P1-07、P1-09 已按 owner 选择实现并验证，P1-08 也已有工程验证证据，三项均不再占用 owner 口径会 |
| 7 个页面 owner approval | owner 姓名、角色、审批决定、日期、签名、页面证据复核确认 | 不能用 smoke/test 通过替代 owner approval |
| Ledger PnL 治理记录处理意见 | 选择写入、定位已有记录、或正式延期，并记录责任人与日期 | dry-run candidate 不是 written record |
| 真实后端 smoke 结果确认 | 当前已记录 full real-backend browser smoke `47 passed`；会议只需确认未来 route/data-source 变化后是否重跑 | smoke 结果不是指标批准、页面认证或 owner approval |
| 本地 secret hygiene 处理 | 环境 owner 确认轮换、接受或隔离本地 secret | 不得把 secret 值写入仓库或审计文件 |

## 当前不得签为闭环

- `business_contract_certified_routes=0`。
- 7 个高风险页面仍为 `approval_status=pending`。
- Ledger PnL 只有 dry-run direct-record candidate，没有写入 `cache_manifest.jsonl` 的 direct page/API record。
- 8 个计算/展示 P1 仍未取得 owner 口径裁决（P1-01 至 P1-06、P1-10、P1-11）；P1-07、P1-09 已按 owner 选择实现并验证关闭，P1-08 保持工程验证关闭。
- full real-backend browser smoke 已有 `47 passed` 证据，但只关闭 browser-smoke lane。
- direct Codex App MCP / GitNexus evidence 尚未在当前工具面复核。
- 本地 `config/.env` secret hygiene 仍需环境 owner 处理；审计只记录 secret 名称，不读取或暴露值。

## 先裁决的 8 个剩余 P1

| 顺序 | P1 | Owner 需要回答的问题 | 推荐会议处理 |
| --- | --- | --- | --- |
| 1 | P1-10 Frontend formal aggregation | 正式 PnL、收益率、ADB 聚合能否在前端补算？ | 建议正式指标只由后端提供，前端只做非正式 UI 辅助。 |
| 2 | P1-11 Credit spread rating-tenor matrix | 评级-期限矩阵由后端治理，还是前端硬编码聚合？ | 建议后端提供治理矩阵。 |
| 3 | P1-02 Bond analytics rate unit | `ytm_value` 和票息率的权威单位是什么？ | 建议源数据显式携带单位，正式路径移除启发式。 |
| 4 | P1-01 Campisi coupon income | `coupon_rate` 存储和计算单位是小数还是百分数？ | 建议先用真实 ZQTZ 数据确认，再统一一个 rate-unit helper。 |
| 5 | P1-05 Period yield denominator | 季度/年度收益率分母用期间平均规模、月末快照求和，还是日均？ | 建议避免月末快照求和作为规模口径。 |
| 6 | P1-03 Roll-down sign | 曲线 roll-down 采用哪个业务符号约定？ | 建议写入 `docs/calc_rules.md` 后统一实现。 |
| 7 | P1-06 PnL bridge zero-actual residual | `actual_pnl=0` 且解释项非零时应 warning/undefined 还是 ok？ | 建议 fail-loud，不能隐藏 residual。 |
| 8 | P1-04 QDB position-vs-ledger reconciliation | 当前同源比较是控制项还是诊断项？ | 建议若声称控制，必须使用独立 position 和 ledger source anchor。 |

## 7 个页面审批顺序

| 顺序 | 页面 | 当前处理建议 |
| --- | --- | --- |
| 1 | `pnl-attribution` | MCP packet 已有 UI/API payload 与 live-smoke evidence 可复核；先补 owner review/signoff。 |
| 2 | `product-category-pnl` | formal use 已允许且有 live-smoke evidence，但 action list 最大，需逐项复核。 |
| 3 | `balance-analysis` | formal use 已允许，但仍需 UI/API、live-smoke、golden sample 和 formal-balance boundary 复核。 |
| 4 | `bond-analysis` | 需要 fixed-income convention/rule review、UI/API、live-smoke 和 owner approval。 |
| 5 | `average-balance` | 需要 candidate boundary、formal balance truth boundary、monthly ADB/NIM boundary 复核。 |
| 6 | `stock-analysis` | 需要 not-trading-instruction review、UI/API、live-smoke 和 owner approval。 |
| 7 | `ledger-pnl` | 放最后；direct page/API governance record 缺口未清前，即使 owner 签字也不能闭环。 |

## Ledger PnL 单独结论

当前 dry-run candidate 字段齐全：

- `page_id=PAGE-LEDGER-PNL-001`
- `primary_api=/api/ledger-pnl/summary`
- `cache_key=ledger_pnl.summary:2026-05-31:ALL`
- `validation_status=ready_for_audit_review`
- `record_write_status=not_requested`
- `existing_record_line=null`
- `formal_use_allowed=false`

会议只能决定治理流程下一步，不能把 dry-run 当成正式记录。批准闭环前必须写入或定位 direct page/API record，并重新跑治理验证。

## 会后执行顺序

1. 记录 8 个剩余 P1 的 owner 裁决结果。
2. 把裁决写入 `docs/calc_rules.md`、metric dictionary 或 page contract。
3. 按裁决修改权威实现层和当前冻结错误口径的测试。
4. 通过 approved workflow 处理 Ledger PnL direct record。
5. 逐页补 owner approval packet，Ledger PnL 最后处理。
6. 工具面可用后补 direct App MCP / GitNexus evidence。
7. route/data-source 或后端目标变化后，按真实后端 smoke runbook 重跑并追加结果。

## 非批准声明

- 本 brief 不批准任何计算口径。
- 本 brief 不批准任何页面。
- 本 brief 不写治理记录。
- 本 brief 不捕获 owner 签字。
- 本 brief 不替代主审计报告、manifest、MCP evidence 或测试输出。
