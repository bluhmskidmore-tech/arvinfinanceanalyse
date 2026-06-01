# 页面契约模板

## 1. 使用目的

页面契约不是视觉稿，不是接口文档替代品，也不是产品 PRD 的拷贝。

它要回答的是：

- 这个页面为什么存在。
- 它必须先回答哪个业务问题。
- 它允许展示哪些 section、哪些指标、哪些 endpoint。
- 它如何展示 freshness / fallback / stale / error / excluded。
- 它如何被指标字典、黄金样本和自动化回归保护。

## 2. 使用边界

- 只给当前治理范围内的页面编写页面契约。
- `placeholder` / `gated` / `excluded` 页面也可以有契约，但必须明确写“不是 live governed page”。
- 页面契约必须引用指标字典和黄金样本；不能单独存在。

## 3. 关键字段

- `page_id`
- `metric_id`
- `sample_id`
- `requested_report_date`
- `resolved_report_date`
- `as_of_date`
- `quality_flag`
- `vendor_status`
- `fallback_mode`

## 4. 页面契约模板

---

# `{{page_id}}` `{{page_name_zh}}`

## A. 页面身份

- 页面 ID：`{{page_id}}`
- 页面名称：`{{page_name_zh}}`
- 页面状态：
  - `active` / `candidate` / `placeholder` / `excluded`
- 前端路由：
  - `{{frontend_route}}`
- 后端接口：
  - `{{api_routes}}`
- 当前边界来源：
  - `{{AGENTS.md / cutover doc / handoff doc / authority doc}}`
- Owner：
  - `{{owner}}`
- Reviewer：
  - `{{reviewer}}`
- Last reviewed：
  - `{{last_reviewed_at}}`

## B. 页面目标

- 主要使用者：
  - `{{管理层 / 研究 / 中后台 / 运营 / 风控}}`
- 页面首屏必须先回答的问题：
  1. `{{问题 1}}`
  2. `{{问题 2}}`
  3. `{{问题 3}}`
- 页面不负责回答的问题：
  - `{{明确写出不该在本页解决的问题}}`
- 页面一句话结论格式：
  - `{{用户进入页面 5 秒内应该知道什么}}`

## C. 页面 basis 与数据边界

- 页面默认 basis：
  - `{{formal / analytical / scenario / mixed}}`
- 是否允许 formal truth：
  - `{{true / false / partial}}`
- 是否允许 analytical overlay：
  - `{{true / false}}`
- 是否允许 mock 数据：
  - `{{true / false}}`
- mock 的允许范围：
  - `{{只允许 placeholder、只允许 CTA、完全禁止等}}`
- excluded / compat 模块：
  - `{{列出明确不能被当成 live 的 section 或 route}}`

## D. 信息架构

### 必须有的 section

| section_key | 名称 | 业务目的 | 数据来源 | 是否首屏 |
| --- | --- | --- | --- | --- |
| `{{overview}}` | `{{概览}}` | `{{先回答什么}}` | `{{endpoint}}` | `{{true/false}}` |

### 可选 section

| section_key | 名称 | 启用条件 | 数据来源 | 备注 |
| --- | --- | --- | --- | --- |
| `{{optional_section}}` | `{{可选模块}}` | `{{何时允许出现}}` | `{{endpoint}}` | `{{备注}}` |

### 禁止 section

- `{{未来规划但当前禁止放回页面的 section}}`
- `{{compat / placeholder / unrelated module}}`

## E. 筛选与时间语义

- 页面主筛选：
  - `report_date`
  - `position_scope`
  - `currency_basis`
  - `{{其他必要筛选}}`
- `requested_report_date`：
  - `{{页面向 API 请求的日期}}`
- `resolved_report_date`：
  - `{{页面真正展示的报告日}}`
- `as_of_date`：
  - `{{业务数据生效日；如果当前仓库没有统一 outward 字段，要明确写缺口}}`
- `generated_at`：
  - `{{接口生成时间}}`
- latest / fallback 语义：
  - `{{exact / latest_snapshot / carry_forward / latest available}}`

## F. Endpoint / DTO 契约

| section_key | Endpoint | Request | Response DTO | basis | 现有测试 |
| --- | --- | --- | --- | --- | --- |
| `{{overview}}` | `{{/api/...}}` | `{{query/body}}` | `{{PayloadType}}` | `{{formal}}` | `{{tests/...}}` |

### 统一要求

- 所有 governed endpoint 必须明确是否返回 `{ result_meta, result }`。
- 所有页面必须标记哪些调用不是 result envelope，例如 refresh / action endpoint。
- 所有 DTO 都要写明是否允许 `extra` 字段。

## G. 页面指标映射

| 页面指标名 | `metric_id` | 数据字段 | 展示规则 | 对账对象 |
| --- | --- | --- | --- | --- |
| `{{总损益}}` | `{{MTR-PNL-005}}` | `{{result.total_pnl}}` | `{{亿元 / 2 位 / signed}}` | `{{GS-PNL-OVERVIEW-A}}` |

### 约束

- 首屏 KPI 必须全部映射到 `metric_id`。
- 页面不得显示未登记口径的 headline KPI。
- 页面内存在两个同名数字时，必须写清它们是否复用同一 `metric_id`。

## H. freshness / 数据质量 / fallback 可见性

- 页面必须显示的 `result_meta` 字段：
  - `basis`
  - `result_kind`
  - `formal_use_allowed`
  - `scenario_flag`
  - `quality_flag`
  - `vendor_status`
  - `fallback_mode`
  - `trace_id`
  - `source_version`
  - `rule_version`
  - `cache_version`
  - `generated_at`
- 页面是否必须显示 `as_of_date`：
  - `{{true / false / 当前缺口}}`
- degraded 状态出现位置：
  - `{{首屏 badge / banner / meta panel / section header}}`

## I. 空态、错误态、fail-closed

### Loading

- `{{页面加载时的合法占位形式}}`

### Empty

- `{{什么叫 empty，用户看见什么}}`

### Stale / fallback

- 触发条件：
  - `{{quality_flag != ok}}`
  - `{{fallback_mode != none}}`
  - `{{vendor_status != ok}}`
- 页面要求：
  - `{{必须有显式标识，不允许静默降级}}`

### Error / fail-closed

- `404`：
  - `{{什么情况下出现}}`
- `503`：
  - `{{什么情况下出现}}`
- fail-closed 文案：
  - `{{用户应该看到的解释}}`

## J. 黄金样本与对账

- 关联 `sample_id`：
  - `{{GS-...}}`
- 样本范围：
  - `{{overview / workbook / full page / section level}}`
- 对账对象：
  - `{{另一个页面 / export / workbook / source table}}`
- 对账规则：
  - `{{字段相等 / 聚合一致 / 差额阈值}}`

## K. 自动化测试

- 现有测试：
  - `{{tests/...}}`
- 必须补的测试：
  - `{{tests/...}}`
- 文档回归：
  - `{{是否需要 docs contract test}}`

## L. 运行与交接

- 运行 owner：
  - `{{谁负责判断页面可上线}}`
- 故障排查入口：
  - `{{trace_id / governance audit / runbook / release suite}}`
- 修改注意事项：
  - `{{改 section / endpoint / metric 时先改哪里}}`

## 4. 页面契约检查清单

- 页面首屏问题写清楚了。
- 页面不该回答的问题写清楚了。
- 所有首屏 KPI 都有 `metric_id`。
- 所有 section 都有 endpoint / DTO / tests。
- `requested_report_date / resolved_report_date / as_of_date / generated_at` 写清楚了。
- `quality_flag / vendor_status / fallback_mode` 的页面可见性写清楚了。
- `placeholder` / `excluded` 模块没有被伪装成 live。
- 至少有一个 `sample_id` 或明确写出为什么当前不能冻结样本。
