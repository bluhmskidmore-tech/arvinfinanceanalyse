# System Boundary Governance Operating Model

## Status

- document type: operating model
- scope: future feature delivery and page/workflow promotion
- current intent: keep feature delivery fast while preventing boundary drift
- authority: does not override `AGENTS.md`, `docs/DOCUMENT_AUTHORITY.md`, `docs/CURRENT_EFFECTIVE_ENTRYPOINT.md`, or `docs/REPO_WIDE_PHASE2_CUTOVER_DEFINITION.md`
- last reviewed: 2026-04-24

## Core Thesis

后续开发的核心主旨是：

> 以系统功能快速上线为目标，但每个上线功能必须先被归入唯一边界类型，并用最小契约、最小测试和可追踪证据证明没有越界。

换句话说，本轮治理不是做平台重构，也不是把所有历史模块一次性整理完。它只做一件事：

> 让每个新页面、接口、指标、样本在上线前都知道自己是 `formal live`、`analytical overlay`、`reserved fail-closed`，还是 `placeholder`。

## Non-Goals

本模型不授权以下工作：

- 后端平台重构
- 全局状态架构改造
- 数据库 schema 大重构
- Agent MVP 或真实 agent query 启用
- broad frontend rollout
- 未纳入 cutover 的 preview / vendor / analytical surface 晋升
- 为单次使用场景新增通用框架

## Boundary Classes

每个新功能进入开发前必须先归类。

| class | 含义 | 是否可上线 | 必需证据 |
| --- | --- | --- | --- |
| `formal live` | 正式业务真值或正式金融读面 | 可上线 | `core_finance` 口径、`result_meta`、lineage、targeted tests、页面状态 |
| `analytical overlay` | 管理层/研究分析消费面，不是 formal truth | 可上线 | `basis=analytical`、`formal_use_allowed=false`、fallback/stale 可见 |
| `reserved fail-closed` | 代码资产保留，但公开面未晋升 | 可保留 | public route 显式 `503`，不得返回 governed envelope |
| `placeholder` | 前端入口、导航或空壳，用于后续恢复 | 可保留 | 页面明确不是 live，不展示伪指标或 mock 真值 |

如果一个功能无法归类，默认按 `reserved fail-closed` 或 `placeholder` 处理，直到有新的明确授权。

## Decision Checklist

每个开发任务开工前只问五个问题：

1. 这个功能回答哪个业务问题？
2. 它属于 `formal live`、`analytical overlay`、`reserved fail-closed`、还是 `placeholder`？
3. 是否展示业务指标？如果是，`metric_id`、单位、精度、时间语义在哪里？
4. 数据链路是否能追到 `API response -> adapter/transformer -> store/state -> selector/computed -> component`？
5. 哪个最小测试能证明它没有越界？

只要这五个问题答不出来，就先补 contract 或降级为 placeholder，不进入 live 发布。

## User Responsibilities

用户只需要负责少量高价值决策：

- 指定下一批要上线的页面或 workflow 优先级。
- 指定业务 owner / reviewer，尤其是指标口径审批人。
- 对需要晋升的 excluded/reserved surface 做明确授权。
- 确认 ambiguous metric definition，例如单位、日期、分母、汇率、是否 YTD。
- 在 Cursor Ultra 并行工作时，避免把同一个文件同时交给多个执行者。

用户不需要手工做：

- repo 搜索
- contract 草拟
- 测试定位
- Cursor prompt 编写
- diff 整合
- release gate 选择

## Codex Responsibilities

Codex 负责主线整合和验证：

- 读取当前权威文档，判断任务是否在边界内。
- 为每个上线功能补最小 page/workflow contract。
- 把任务拆成互不冲突的 Codex / Cursor 工作包。
- 给 Cursor 生成可直接执行的 prompt，包含读文档、写范围、禁止范围、测试命令、输出格式。
- 接收 Cursor 结果后复核 diff，补齐遗漏测试或文档。
- 运行窄验证，必要时运行 release gate。
- 最终汇报 root cause、changed files、validation、remaining risks。

Codex 是边界治理的“交通控制塔”：不必亲手做所有切片，但必须拥有最终集成和验证。

## Cursor Ultra Responsibilities

Cursor Ultra 适合做并行的、文件范围明确的执行切片：

- 单页面前端 adapter/selector/component 收敛。
- 单 endpoint / service 的 contract test 与 fail-closed 修复。
- 单样本包的 `request/response/assertions/approval` 对齐。
- 单文档的 page contract 或 metric binding 补齐。

Cursor 任务必须满足：

- 只给一个 owner lane。
- 明确 write scope。
- 明确禁止触碰文件。
- 明确 verification commands。
- 完成后停下，返回 changed files / tests / risks。

## Fast Delivery Loop

每个功能按这个顺序走：

1. `Classify`
   - 确定 boundary class。
   - verify: contract 中写出 class 和禁止范围。

2. `Contract`
   - 写页面或 workflow 的最小 contract。
   - verify: endpoint / DTO / metric / state / tests 都有锚点。

3. `Implement`
   - 只改当前页面或 workflow 的必要文件。
   - verify: targeted tests pass。

4. `Bind`
   - 绑定 `metric_id`、`sample_id`、现有测试。
   - verify: docs/sample contract tests pass。

5. `Gate`
   - 跑窄验证；需要发布时跑 named release gate。
   - verify: 结果可复现，风险可说明。

## Minimum Evidence By Change Type

| change type | minimum evidence |
| --- | --- |
| 页面展示指标 | adapter/selector/component test + metric dictionary/page contract link |
| formal 后端读面 | core_finance/service/API tests + result_meta lineage |
| analytical overlay | basis/formal_use_allowed tests + fallback/stale visible UI |
| reserved route | `503` route test + no `result_meta` envelope |
| golden sample | four-file sample package + `test_golden_samples_capture_ready.py` |
| docs-only contract | grep/readback check + no authority conflict |

## First Operating Priority

第一批工作不应扩范围，而应收紧“即将上线功能”的默认动作：

1. 建立一份可执行任务拆分包。
2. 选一个页面或 workflow 做完整闭环样板。
3. 把样板中的 prompt、测试、验收方式复用到后续页面。

推荐第一个样板页面从已接近 live 的页面中选择，而不是从 excluded surface 开始。
