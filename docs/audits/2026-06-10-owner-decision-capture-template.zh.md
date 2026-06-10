# 2026-06-10 MOSS Owner Decision Capture Template

## 边界

这是一份 owner 决策采集模板。填写本模板不等于完成页面审批、治理记录写入、route certification 或 metric approval。正式闭环仍以各页面 owner approval template、治理记录、MCP evidence、测试输出和 strict checker 为准。

## 会议记录

| 字段 | 填写 |
| --- | --- |
| 会议日期 |  |
| 主持人 |  |
| 业务 owner |  |
| Metric governance 代表 |  |
| Engineering owner |  |
| QA / evidence owner |  |
| 记录人 |  |
| 本次结论状态 | draft / approved-for-implementation / deferred / rejected |

## 10 个剩余计算/展示 P1 口径裁决

填写规则：

- `selected_decision` 必须引用候选项，或写明需要补充的源数据证据。
- `owner_rationale` 不能为空；如果只是沿用现状，也必须说明为什么。
- `implementation_owner` 和 `verification_gate` 不能为空，否则不能进入工程实现。

| P1 | 决策主题 | selected_decision | owner_rationale | implementation_owner | verification_gate | status |
| --- | --- | --- | --- | --- | --- | --- |
| P1-01 | Campisi coupon income: `coupon_rate` 单位 |  |  |  | `docs/calc_rules.md` + numeric golden tests | pending |
| P1-02 | Bond analytics rate unit: `ytm_value` / coupon rate 单位 |  |  |  | source contract evidence + sub-1% regression | pending |
| P1-03 | Roll-down sign convention |  |  |  | shared rule/helper + losing-side tests updated | pending |
| P1-04 | QDB position-vs-ledger reconciliation control status |  |  |  | independent source anchors or non-control label | pending |
| P1-05 | Quarterly/yearly yield denominator |  |  |  | monthly/quarterly/yearly numeric tests | pending |
| P1-06 | PnL bridge zero-actual residual quality |  |  |  | zero-actual nonzero-explained warning regression | pending |
| P1-07 | Macro liquidity score polarity |  |  |  | isolated liquidity movement test + contract copy | pending |
| P1-09 | Balance movement share source |  |  |  | model/component tests proving backend value wins | pending |
| P1-10 | Frontend formal aggregation boundary |  |  |  | backend DTO / frontend removal tests | pending |
| P1-11 | Credit spread rating-tenor matrix owner |  |  |  | API contract + frontend renders provided matrix | pending |

## 7 个页面 owner approval 采集

填写规则：

- 本表是聚合追踪，不替代 `docs/pnl/*business-owner-approval-template.md`。
- 只有对应单页模板、证据复核项、strict checker 同时满足后，页面才可进入闭环判断。
- `ledger-pnl` 必须等 direct page/API governance record 缺口清除后再签。

| 页面 | business_owner_name | business_owner_role | approval_decision | approval_date | business_owner_signature | evidence_review_complete | strict_checker_result | status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `product-category-pnl` |  |  |  |  |  | no | pending | pending |
| `balance-analysis` |  |  |  |  |  | no | pending | pending |
| `average-balance` |  |  |  |  |  | no | pending | pending |
| `ledger-pnl` |  |  |  |  |  | no | blocked-by-direct-record-gap | pending |
| `pnl-attribution` |  |  |  |  |  | no | pending | pending |
| `bond-analysis` |  |  |  |  |  | no | pending | pending |
| `stock-analysis` |  |  |  |  |  | no | pending | pending |

## Ledger PnL direct-record 决定

| 字段 | 填写 |
| --- | --- |
| 选择 | write-approved-record / locate-existing-record / defer-with-owner-acknowledgement |
| 责任人 |  |
| 目标完成日期 |  |
| 依据 |  |
| 必须复跑的验证 | governance validation + `scripts/check_ledger_pnl_business_owner_approval.py --require-captured` after owner packet is complete |
| 备注 | dry-run candidate 不能作为 written record；`formal_use_allowed=false` 仍然有效，直到 approved workflow 和后续 review 改变它 |

## 真实后端 smoke 结果确认

| 字段 | 填写 |
| --- | --- |
| 当前结果 | `47 passed` |
| 结果文件 | `docs/audits/2026-06-10-real-backend-smoke-result.md` |
| live backend URL / port | `http://127.0.0.1:7888` |
| frontend URL / port | `http://127.0.0.1:5888` |
| data source | real |
| 下一次重跑触发条件 | route scope、backend target、frontend data-source setup 或 smoke contract 变化 |
| 非批准边界 | smoke 结果不批准指标、页面、治理记录、owner approval 或 direct App MCP/GitNexus closure |

## Secret hygiene 处理

| 字段 | 填写 |
| --- | --- |
| `MOSS_TUSHARE_TOKEN` | rotate / accepted-local-only / removed / not-applicable |
| `STITCH_API_KEY` | rotate / accepted-local-only / removed / not-applicable |
| 环境 owner |  |
| 处理日期 |  |
| 备注 | 不得把 secret 值写入仓库、报告或审批材料 |

## 会后工程准入检查

| 检查 | 状态 |
| --- | --- |
| 每个剩余 P1 都有 owner 裁决或明确延期原因；P1-08 已由 formatter/page 测试证据关闭 | pending |
| 每个待实现 P1 都有 implementation owner | pending |
| 每个待实现 P1 都有 verification gate | pending |
| `ledger-pnl` direct-record 处理路径已确定 | pending |
| 7 个页面审批字段已进入对应单页模板 | pending |
| full real-backend smoke `47 passed` 结果已复核，且未被当成业务审批 | pending |
| secret hygiene 处理路径已确定 | pending |

## 非批准声明

- 本模板不批准任何计算口径。
- 本模板不批准任何页面。
- 本模板不写治理记录。
- 本模板不替代单页 owner approval template。
- 本模板不替代 direct MCP / GitNexus evidence。
- 本模板不替代测试输出或 strict checker。
