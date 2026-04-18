# 指标字典模板

## 1. 使用边界

本模板只服务于当前仓库已经进入治理范围的页面与读链路。

它不是新的平台模型，也不是为了生成一套“漂亮但没人维护”的元数据表。它只要求把一个页面上出现的数字，落到一条完整链路上：

- 页面展示名称
- 业务定义
- 口径边界
- 权威字段或计算入口
- 展示规则
- freshness / fallback / 数据质量
- 页面契约
- 黄金样本
- 自动化测试

## 2. 必填字段总表

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `metric_id` | 是 | 全局唯一 ID，建议 `MTR-{DOMAIN}-{NNN}` |
| `metric_name_zh` | 是 | 页面展示中文名 |
| `metric_name_en` | 否 | 英文名或开发名 |
| `domain` | 是 | `balance` / `pnl` / `bridge` / `risk` / `bond_analytics` / `executive` / `market` / `operations` / `governance` |
| `status` | 是 | `active` / `candidate` / `excluded` |
| `priority` | 是 | `P0` / `P1` / `P2` |
| `owner` | 是 | 页面 owner 或口径 owner |
| `reviewer` | 是 | 业务复核人或审批人 |
| `last_reviewed_at` | 是 | 最后复核日期 |
| `page_scope` | 是 | 当前在哪些页面、哪些 section 展示 |
| `sample_scope` | 否 | 关联的 `sample_id` |

## 3. 单指标模板

---

## `{{metric_id}}` `{{metric_name_zh}}`

### A. 基本信息

- 指标 ID：`{{metric_id}}`
- 中文名：`{{metric_name_zh}}`
- 英文名：`{{metric_name_en}}`
- 所属域：`{{domain}}`
- 当前状态：`{{status}}`
- 优先级：`{{priority}}`
- Owner：`{{owner}}`
- Reviewer：`{{reviewer}}`
- Last reviewed：`{{last_reviewed_at}}`

### B. 业务定义

- 回答的业务问题：
  - `{{这个指标回答什么问题}}`
- 一句话定义：
  - `{{不写代码实现，只写业务定义}}`
- 非目标：
  - `{{哪些相近指标不能混入本指标}}`

### C. 口径与边界

- basis：
  - `{{formal / analytical / scenario / mixed}}`
- `formal_use_allowed`：
  - `{{true / false / not_applicable}}`
- `scenario_flag`：
  - `{{true / false}}`
- 适用对象：
  - `{{asset / liability / all / executive overlay / market / ops}}`
- 不适用对象：
  - `{{明确列出不能误用的范围}}`
- 与哪些指标必须区分：
  - `{{metric_id list or names}}`

### D. 权威来源

- 权威文档：
  - `{{docs/calc_rules.md section}}`
  - `{{docs/data_contracts.md section}}`
  - `{{其他权威文档}}`
- 权威计算入口：
  - `{{backend/app/core_finance/...}}`
  - `{{backend/app/services/...}}`
- 对外字段：
  - `{{backend/app/schemas/...}}`
  - `{{frontend/src/api/contracts.ts field}}`

### E. 输入与依赖

- 上游数据表 / 来源：
  - `{{table_1}}`
  - `{{table_2}}`
- 关键筛选：
  - `{{report_date / position_scope / currency_basis / view / tenor ...}}`
- 关键维度：
  - `{{accounting_basis / invest_type_std / rating / source_family ...}}`
- 影响结果的前置条件：
  - `{{materialize run / cache version / source freshness / feature flag ...}}`

### F. 计算与对账规则

- 计算逻辑摘要：
  - `{{如果是字段透传，写“字段透传”；如果是聚合，写聚合规则}}`
- 对账对象：
  - `{{另一个页面 / workbook / export / golden sample}}`
- 对账方式：
  - `{{字段相等 / 汇总一致 / 差额阈值 / 只允许方向一致}}`
- 已知例外：
  - `{{例如 analytical overlay、latest snapshot、汇率换算差异}}`

### G. 展示规则

- 展示单位：
  - `{{元 / 万元 / 亿元 / % / bp / count / ratio / text}}`
- 精度：
  - `{{整数 / 1 位 / 2 位 / 4 位}}`
- 正负号规则：
  - `{{always / negative_only / signed_if_nonzero}}`
- 空值规则：
  - `{{— / 0 / hidden / fail_closed}}`
- stale / fallback 文案：
  - `{{页面必须怎样提示}}`
- 不允许的展示方式：
  - `{{例如不得前端自行缩放、不得把 bp 当成 %}}`

### H. 时间与 freshness

- `requested_report_date`：
  - `{{页面传给后端的日期}}`
- `resolved_report_date`：
  - `{{页面真正展示的日期}}`
- `as_of_date`：
  - `{{业务数据生效日；若当前无统一字段，显式写缺口}}`
- `generated_at`：
  - `{{接口生成时间}}`
- freshness 判定：
  - `{{exact / latest_snapshot / carry_forward / latest available}}`

### I. 数据质量与 fallback

- `quality_flag`：
  - `{{ok / warning / error / stale}}`
- `vendor_status`：
  - `{{ok / vendor_stale / vendor_unavailable / not_applicable}}`
- `fallback_mode`：
  - `{{none / latest_snapshot / carry_forward / not_applicable}}`
- fail-closed 条件：
  - `{{什么情况下不能展示这个指标}}`
- 页面可见性要求：
  - `{{这个 degraded 状态必须出现在首屏 / meta panel / error banner}}`

### J. 页面映射

- 页面：
  - `{{PAGE-...}}`
- route / section：
  - `{{/balance-analysis -> overview}}`
  - `{{/pnl -> summary cards}}`
- 是否为首屏结论指标：
  - `{{true / false}}`

### K. 黄金样本与测试

- `sample_id`：
  - `{{GS-...}}`
- 黄金样本断言：
  - `{{哪些字段必须冻结}}`
- 现有测试：
  - `{{tests/...}}`
- 待补测试：
  - `{{tests/... or TODO}}`

### L. 变更记录

- 最近一次变化：
  - `{{改了什么，为什么改}}`
- 后续修改注意：
  - `{{不要改什么，改之前必须核对什么}}`

## 4. 录入检查清单

- 没有 `metric_id` 的页面数字，不进入 governed 页面首屏。
- 没有权威字段或权威计算入口的指标，只能标记为 `candidate` 或 `excluded`。
- 没有页面映射的指标，不允许写成“全局通用指标”。
- 没有 `quality_flag / fallback_mode` 说明的指标，不允许标记为 `active`。
- 没有 `sample_id` 或现有测试挂点的 P0 指标，不算冻结完成。
- 同一个数字如果在两个页面出现，必须复用同一 `metric_id`，或显式写明为何不能复用。
