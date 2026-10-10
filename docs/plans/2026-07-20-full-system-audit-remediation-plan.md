# MOSS-V3 全系统审计整改方案

> **For implementation agents:** 逐工作包执行前必须读取 `executing-plans`；涉及多个独立工作包时读取 `subagent-driven-development`。本方案不授权自动 commit。

**目标：** 修复已确认的正式数字、API 写边界和前端正式指标问题，再按依赖收敛 stale/null、单位、日期、血缘、测试与结构债。

**架构方案：** 保持 `frontend -> api -> services -> (repositories / core_finance / governance) -> storage`。route 只校验/**授权**/调用 service，service 只编排，正式计算留在 core_finance，DuckDB 写入只在 tasks；前端只消费后端权威指标。（原文此处写的是「鉴权」；准确说法是授权，边界见 §R-04 的说明。）

**技术栈：** FastAPI、Python Decimal、DuckDB、Dramatiq/现有任务代理、React、TypeScript、Vitest、pytest、治理 JSONL/result_meta。

- 日期：2026-07-20
- 状态：审计完成，待按波次实施
- 审计方式：8 个专项子代理完成只读审计；PnL 专项中断，但其最高风险发现已由主代理按当前代码重新闭合证据链
- 审计快照：当前 `codex/V1` 工作区，包含现有未提交改动
- 审计边界：未修改业务代码、未运行测试、未写入 DuckDB、未执行 git 写操作
- 交付目标：把分散发现收敛为可独立评审、可逐项验证、不会重复打开已关单问题的整改路线图

---

## 0. 执行结论

当前系统不是“整体不可用”，但也不满足无条件发布门槛。

正式计算主链中的 H/A/T、514/516/517、FX fail-closed、Formal/Scenario 隔离、余额闭合与黄金样本体系总体稳健；主要风险集中在四个边界：

1. PnL Bridge 的曲线适配器发生确定性类型断裂，正式曲线贡献被静默归零，并被 Campisi 吸收到 selection effect。
2. 四条刷新路径仍在 API 请求进程内写 DuckDB，破坏单写者边界。
3. 负债页由前端重算 Top10/HHI，且缺数据时展示为 0。
4. stale/fallback、null、单位、日期和指纹语义在分析层仍有多处静默降级。

原始专项报告共列出：

- 6 个 P0：1 个 PnL 正式数字错误、4 个 API 写路径泄漏、1 个前端正式指标补算。
- 43 个 P1：条件性数字错误、日期/单位/缺失语义、血缘与测试强度问题。
- 约 57 个 P2：重复实现、结构债、休眠代码、可观测性与测试组织问题。

不同专项使用的严重度定义略有差异，因此本方案不把原始数量当作质量评分；执行优先级以“是否影响正式数字、是否破坏写边界、是否会把无数据伪装为正常值”为主。

### 发布判断

- PnL Bridge / Campisi：阻断发布，必须先完成 WP-01。
- 涉及四个刷新端点的生产部署：阻断发布，必须先完成 WP-02。
- 负债集中度页面：阻断作为正式风险指标使用，必须先完成 WP-03。
- 其他正式主链：可在现有保护下继续运行，但必须保留 stale/fallback 与 owner 决策闸门。
- 分析/策略页面：仅可作为带披露的研究或候选结果，不能把未整改风险指标升级为正式决策口径。

---

## 1. 证据等级与覆盖边界

### 1.1 证据等级

- E1：当前代码直接复核，证据链完整。P0 项均要求达到 E1。
- E2：专项代理逐文件静态审计，有具体文件和行号，但本轮未执行测试。
- E3：中断审计留下的推断或旧报告遗留项，未重新闭合；只进入“待验证”，不直接进入修复。

### 1.2 九条审计线

1. PnL 与归因：专项中断；`_curve_points` 类型断裂已由主代理按当前代码复核为 E1。
2. 余额与会计口径：完成。
3. 固收与曲线/风险引擎：完成。
4. 宏观联动与策略信号：完成。
5. 共享计算基础设施：完成。
6. 后端 API 分层与写边界：完成。
7. 治理、血缘与缓存：完成。
8. 前端数据显示链路：完成。
9. 测试体系健康度：完成。

### 1.3 未覆盖或不能由静态审计回答

- 未查询正式 DuckDB，因此不能量化部分条件性问题的当前暴露金额或持仓占比。
- 未运行 pytest、Vitest、typecheck、debt audit 或浏览器验收。
- 未逐个验证 602 个顶层后端测试和 360 个前端测试的运行状态。
- 未完成 PnL 中断审计留下的所有次级候选项；这些只列入附录的 E3 待验证队列。
- MCP 合约/数据目录在部分子审计中不可用，相关结论使用当前代码、权威本地文档和测试源码交叉取证。

---

## 2. 已确认 P0：发布阻断项

### SYS-P0-01：PnL Bridge 曲线快照类型断裂

证据：

- `backend/app/repositories/yield_curve_repo.py:360-367` 返回 `curve: dict[str, Decimal]`。
- `backend/app/services/pnl_bridge_service.py:636-642` 的 `_curve_points` 只接受 `list`，遇到仓储返回的 dict 固定返回 `None`。
- `backend/app/core_finance/pnl_bridge.py:115-120` 明确要求 dict 曲线。
- `backend/app/core_finance/pnl_bridge.py:340-424` 在曲线为空时将 roll-down、treasury curve、credit spread 全部置零。
- `backend/app/services/campisi_attribution_service.py:1033-1054` 用 `total - income - treasury - spread` 计算 selection，缺失的曲线贡献因此被并入 selection。
- `tests/test_pnl_bridge_curve_effects.py:52-168` 种入真实曲线快照，但只断言 warning、lineage 和 fallback 元数据，没有断言曲线贡献值。

失败机制：

1. 仓储正确读取曲线。
2. 服务适配器因错误类型检查丢弃曲线。
3. 核心计算按“无曲线”分支返回 0。
4. 结果仍可闭合，因此常规闭合测试不会报警。
5. Campisi 把漏掉的市场贡献归入 selection，形成“闭合但分类错误”。

业务影响：

- PnL Bridge 的 roll-down、利率曲线和信用利差贡献错误。
- Campisi 的 selection effect 被系统性污染。
- 页面会给出看似闭合的错误解释，风险高于普通空值。

最小修复：

- 将 `_curve_points` 契约改为 `dict[str, Decimal] | None`。
- 只接受映射；逐值严格转 Decimal，非法值 fail-closed，不再兼容历史 list 形状。
- 不修改 `build_pnl_bridge_rows` 公式。

测试先行：

1. 在 service/API 层种入当前、上期 treasury/CDB/AAA 曲线。
2. 断言至少一项 roll-down、treasury curve、credit spread 为非零且与 core 直接调用一致。
3. 断言 Campisi selection 不再吸收这三项差额。
4. 保留缺曲线时归零并披露 warning 的既有行为。

验收：

- E2E 服务测试覆盖真实仓储 dict 形状。
- 核心直接测试与服务路径测试输出一致。
- PnL Bridge summary 与行级分项闭合。
- Campisi total = income + treasury + spread + selection，且 selection 只含真正残余。

### SYS-P0-02：Macro source backfill 在 API 请求线程内写 DuckDB

证据：

- `backend/app/api/routes/macro_toolkit.py:743-761,1034-1073`。
- 路由同步调用 `backfill_macro_series(..., dry_run=False)` 或 `backfill_crisis_score_inputs(..., dry_run=False)`。
- 写连接位于任务/脚本实现，但实际执行进程仍是 API 请求进程。

影响：

- DuckDB 单写者锁竞争。
- vendor 网络请求与写事务占用 API 线程。
- 进程重启、超时和客户端重试会扩大不确定性。

最小修复：

- 复用现有 actor/任务链路，API 只创建治理 run、派发任务并返回 `202 + run_id`。
- 现有 refresh-status 作为查询面。
- 不新建队列基础设施。

验收：

- API 调用不打开写连接。
- 任务进程完成实际写入。
- 重复 idempotency key 不重复物化。
- production 不允许同步 fallback。

### SYS-P0-03：CFFEX member rank 刷新同步抓取 vendor 并写 DuckDB

证据：

- `backend/app/api/routes/macro_toolkit.py:634-647`。
- `backend/app/services/macro_toolkit_service.py:470-488`。
- `backend/app/services/cffex_member_rank_service.py:37-88`。
- service 同步调用 `backend/app/tasks/cffex_member_rank.py` 的写函数。

最小修复：

- 将现有 CFFEX materialize 流包装为 actor。
- route/service 只派发，不直接 import 写函数。
- vendor 失败、部分成功和重试状态写入治理流。

验收：

- `backend/app/services/` 不再同步调用 `persist_cffex_member_rank_rows`。
- refresh 返回 queued。
- worker 失败不会使 API 请求持锁或长时间阻塞。

### SYS-P0-04：Livermore gate supplement 刷新在请求线程内计算并物化

证据：

- `backend/app/api/routes/market_data_livermore.py:543-571`。
- `backend/app/services/livermore_gate_supplement_compute_service.py:63-111`。
- service 顶层 import 两个 tasks，并在请求路径中调用物化函数。

最小修复：

- 将计算与两个物化步骤移入单一任务。
- service 使用延迟任务代理，避免只读 import 注册 actor。
- API 返回 queued，状态与治理记录由同一 run_id 串联。

验收：

- route/service import 不触发 task 模块副作用。
- API 路径 DuckDB 只读。
- 两个物化步骤要么同 run 成功，要么明确记录部分失败。

### SYS-P0-05：Bond analytics refresh 入队前先在 API 进程写曲线

证据：

- `backend/app/services/bond_analytics_service.py:910-911,971-978`。
- `_prepare_yield_curve_inputs_for_refresh` 在 actor `.send` 之前调用写入型曲线准备逻辑。

最小修复：

- 把收益率曲线输入准备移到 bond analytics materialize 任务开头。
- service 只做参数校验、治理记录和派发。

验收：

- refresh 请求不写 yield curve snapshot。
- worker 在同一 run 内先准备曲线，再物化 bond analytics。
- 曲线准备失败时主物化不继续，并保留可追溯错误。

### SYS-P0-06：负债页前端重算 Top10/HHI，且空数据展示为 0

证据：

- `frontend/src/features/liability-analytics/utils/concentration.ts:1-16`。
- `frontend/src/features/liability-analytics/components/LiabilityCounterpartyBlock.tsx:86-91,179-181`。
- 页面从可截断的 counterparty rows 重算 Top10 share 和 HHI。
- 空数组或总和小于等于 0 时返回两个 0。

失败机制：

- rows 不是全量时，HHI 与 Top10 占比口径改变。
- topN 等于 10 时，Top10 share 可恒为 100%。
- 无数据被显示为“0% / HHI 0”，伪装成极度分散。

最小修复：

- 后端在全量数据上计算并返回 `top10_share`、`hhi`、`population_count`、`is_truncated`。
- 前端只消费 Numeric 字段，不再重算。
- 空数据保留 null，显示“—”和明确空态。

验收：

- 后端黄金样本覆盖全量与截断输入。
- 前端删掉正式指标计算，仅保留格式化。
- API 空数据返回 null，不返回 0。
- 页面在 `is_truncated=true` 时不把截断集合冒充全量口径。

---

## 3. 八个跨域根因

### R-01：缺失值被当成正常零值

命中：

- PnL 曲线被适配器丢弃后归零。
- 前端 balance movement、PnL attribution、balance analysis 把 null 转 0。
- `safe_decimal`、月度分析汇总、ADB trend 存在静默归零。
- 会计资产变动 `quality_flag="ok"` 硬编码。

治理原则：

- null、0、undefined、NaN、缺表、缺行必须有不同语义。
- 只有业务确认的“真零”可以进入正式计算。
- 任何 fallback 或 partial aggregate 必须携带机器字段并在首屏披露。

### R-02：单位与舍入口径没有单一权威

命中：

- pct raw/display 边界仍有 auto heuristic。
- ADB 与 rate_units 对脏数据行为不同。
- 多处裸 `Decimal.quantize` 使用隐式 HALF_EVEN。
- HHI 存在 0-1 与 0-10000 两种量纲。
- DV01 面值与情景 PnL 市值口径同屏。

治理原则：

- 单位由字段契约声明，禁止根据绝对值猜单位。
- 舍入策略按指标签核，禁止全仓机械替换。
- 同屏双口径必须改名或显式披露，不以相同标签展示。

### R-03：日期、窗口与 fallback 语义分叉

命中：

- PnL lineage 可能取另一个报告日的最新 manifest。
- `percentile_1y` 实际使用全历史。
- GDP 当季值相邻差分携带季节性。
- 政策工具集合在当前日和回看日不一致。
- ADB 使用观测日、自然日、快照日多种分母。
- future date 被 freshness 标为 fresh。

治理原则：

- 所有日期型结果同时携带 requested/resolved/source/fallback 日期。
- 窗口字段名必须与真实窗口一致。
- 月度、季度和日频对齐必须在 core_finance 入口显式定义。

### R-04：API、service、core_finance 边界被穿透

命中：

- 四条 API 写路径。
- 4740 行 macro route 内嵌统计与策略编排。
- route 直接 import repository。
- core_finance 反向 import repository/governance/schema。
- service 内保留正式金融公式与 task 顶层 import。

治理原则：

- route 只做校验、**授权**、service 调用和 response。
  - 原文此处写的是「鉴权」。准确说法是**授权**（authorization / RBAC）：仓库**有授权、没有认证**——
    `backend/app/security/auth_context.py::ensure_user_allowed` 的 RBAC 判定经 `backend/app/api/deps.py`
    接进路由依赖，但全仓没有 `HTTPBearer` / `OAuth2` / `APIKeyHeader` / JWT / session，调用方身份未经校验。
    完整边界见 [README.md](../../README.md)「关键约束」一节与
    [SYSTEM_STACK_SPEC_FOR_CODEX.md](../SYSTEM_STACK_SPEC_FOR_CODEX.md) 第 1 节。
  - 因此本条只约束 route 的**动作类型**，不构成安全声明；整改 R-04 时不要把它读成「身份已校验」，
    也不要在它之上做安全性判断或对外暴露。
- service 编排，core_finance 纯计算，repository 读，task 写。
- 不借助“函数定义在 tasks 模块”伪装 API 进程写入。

### R-05：重复实现与 canonical 声明漂移

命中：

- balance workbook 单体与包版。
- bond duration 与 common duration。
- FX carry-forward 校验双份。
- calibers 声明的 canonical 与生产调用点不一致。
- NIM、日均、付息方式存在多路径。

治理原则：

- 先标记权威实现，再迁移调用方；没有 owner 决策时不改正式历史数值。
- 休眠实现不得继续宣称 canonical。
- 重复实现必须有等价性测试或明确弃用期。

### R-06：测试数量高，但关键断言不总是验证正确性

命中：

- PnL service 曲线测试只测元数据，不测数值。
- KRD DV01 用被测输出重算期望值。
- bond duration 多为范围断言。
- matched baseline 固定 seed 却不锁 CI 数值。
- attribution 个别断言容差达到 1%。

治理原则：

- 金融公式至少有一个独立手算或黄金样本。
- 服务适配器必须用真实仓储 DTO 形状做契约测试。
- 闭合性不能替代分项正确性。

### R-07：指纹与 stale/fallback 证据链存在弱点

命中：

- FTP 费率未进入 precompute 指纹。
- source version 只哈希文件名、大小、mtime。
- manifest 的 report_date 不是强制合同字段。
- accounting movement 读路径吞 stale。
- lineage 无对应日期时回落最新记录。

治理原则：

- 指纹覆盖数据、参数、规则和关键代码版本。
- 内容变化必须改变 source version。
- 按日报表的 manifest 必须强制 report_date。

### R-08：巨型文件扩大回归半径

命中：

- `macro_toolkit.py` 约 4740 行。
- 多个 service 超过 150KB。
- `BalanceMovementAnalysisPage.tsx` 3617 行。
- `productCategoryPnlPageModel.ts` 5278 行。
- 测试分散于双后端根和集中/同址双前端根。

治理原则：

- 只在修复命中的边界做小步拆分。
- 不先做通用平台重构。
- 每次拆分必须用同一测试集证明行为不变。

---

## 4. P1 整改登记

以下 43 项保留专项编号。它们不是同一优先级：先处理“正式数字或 stale 证据错误”，再处理分析口径，最后处理披露型问题。

### 4.1 后端分层与写边界

- API-P1-01：`macro_toolkit.py` 路由内含相关性、z-score、回测摘要与线程池编排。拆到 service/core_finance；路由只保留 DTO 边界。
- API-P1-02：macro/executive route 直接 import repository。下沉为 service 工厂或读方法。
- API-P1-03：core_finance 反向依赖 repository/governance/schema。改为调用方注入纯数据。
- API-P1-04：`pnl_service.py`、credit spread service、scenario stress service 保留金融公式。逐公式迁回 core_finance。
- API-P1-05：三个 service 顶层 import tasks。改用已有延迟任务代理模式。
- API-P1-06：choice-stock 使用 FastAPI BackgroundTasks 写库。改为 worker actor。

### 4.2 治理、血缘与缓存

- GOV-P1-01：`pnl_repo.py:210-272` 的 precompute 指纹遗漏生效 FTP 费率。构建与校验两侧都加入解析后的费率值。
- GOV-P1-02：`accounting_asset_movement_service.py:296-322` 硬编码 `quality_flag="ok"`。读路径执行 stale 检查并透出日期列表。
- GOV-P1-03：PnL lineage 无当日记录时取最新 manifest，可能日期错配。优先按 report_date 查找，fallback 必须打标。
- GOV-P1-04：`source_preview_parsers.py:50-53` 只用文件名、大小、mtime 生成 source version。加入内容 SHA256。

### 4.3 共享计算基础设施

- SHARED-P1-01：正式模块中裸 quantize 与 HALF_UP 混用。先做指标级 owner 决策，再逐模块迁移。
- SHARED-P1-02：ADB rate normalization 与 `rate_units` 对负值和异常上限不一致。统一委托显式单位函数。
- SHARED-P1-03：future business date 被 freshness 标为 fresh，消费端又丢弃 notes。新增 lookahead 状态或强制透出 notes。

### 4.4 余额与会计分析

- BAL-P1-01：`qdb_gl_monthly_analysis.py:1359-1380` 的时点同业资产未扣 14004/14005。时点分支复用 11 位科目求和。
- BAL-P1-02：`compute_industry_gap` 对无存款行业调用 None.get。改为显式空映射并补边界测试。
- BAL-P1-03：单日 ADB 默认用 MD5 因子生成模拟日均。默认关闭，缺口返回 null 和原因。
- BAL-P1-04：compat 债券利率启发式会把 0.3% 当 30%。改用显式 percent/decimal 输入模式。
- BAL-P1-05：日均分母在观测日、自然日和快照日间不一致。每个 payload 输出 denominator_basis，并由 owner 统一同名指标。
- BAL-P1-06：缺 maturity 在两个模块落入“已到期”和“3 个月内”。统一为“未知期限”或单一规则常量。
- BAL-P1-07：结构性存款组件取整个 21601/21602，合计只取单个 11 位科目。先增加 residual 披露，再由会计 owner 决定口径。
- BAL-P1-08：期限缺口 high/medium 阈值使用 20/5 万元，银行体量下退化为恒 high。按亿元或资产比例重新标定。
- BAL-P1-09：HQLA Level 2B 计入系数与 Basel 口径不一致。必须先确认这是监管口径还是内部口径，禁止直接改数值。

### 4.5 固收与风险引擎

- FI-P1-01：风险张量未透传 value_date，bullet 利息固定按一年。engine 与 risk tensor 透传起息日。
- FI-P1-02：cashflow service 重算 Macaulay 并覆盖物化值，且频率默认 1。优先使用正式物化值，缺失才回退。
- FI-P1-03：同页 DV01 用面值、情景 PnL 用市值。先改名/披露，统一口径必须 owner 签核。
- FI-P1-04：service `_normalize_rate` 恢复数值启发式。删除猜测，声明输入为 decimal。

### 4.6 宏观与策略

- MACRO-P1-01：factor screen 未剔除非正 PE/PB/PS，亏损股获得高价值分。与 Livermore 过滤规则对齐。
- MACRO-P1-02：GDP 现价当季值做相邻差分，Q1 季节性系统性拉低 growth。改为同比序列或四期差分。
- MACRO-P1-03：`percentile_1y` 实际使用全历史。截取 252 观测或日历一年。
- MACRO-P1-04：政策利率当前日与回看日使用不同候选工具集合。只计算交集。
- MACRO-P1-05：horizon backtest 按成本计价却计算日 Sharpe/回撤。至少披露 valuation_basis，根治需价格路径。
- MACRO-P1-06：cycle proxy 混合 next-open 与 same-close fallback。披露 fallback 占比并提供 strict 模式。
- MACRO-P1-07：实时候选不执行流动性地板，回测执行。统一宇宙或提供并列版本。

### 4.7 前端数据链路

- FE-P1-01：balance movement 把缺失总变动转 0，生成“持平 0.00 亿”。缺数据时禁止形成方向结论。
- FE-P1-02：PnL attribution 瀑布图与 composition 图 null→0；同页其他图正确留空。统一 rawOrNull。
- FE-P1-03：bond dashboard 负基数 MoM 符号反向。使用绝对分母或改显示差值。
- FE-P1-04：balance analysis 单边缺失仍计算净缺口，partial sum 冒充 total。输出 isPartial，净缺口留空。
- FE-P1-05：PnL Excel YTD 父级由前端 `?? 0` 求和，月度 sheet 用后端 summary。改用后端 YTD summary。
- FE-P1-06：负债/余额变动页 stale/fallback 只在证据面板或表尾。增加首屏横幅与 fallback date。

### 4.8 测试强度

- TEST-P1-01：KRD/DV01 断言自引用。增加独立手算黄金值。
- TEST-P1-02：bond duration 主要使用范围断言。增加标准券精确对照。
- TEST-P1-03：matched baseline 固定 seed 但不锁 bootstrap CI。锁定 low/high。
- TEST-P1-04：`test_attribution_daily.py` 个别 1% 相对容差无说明。确认业务依据或收紧。

---

## 5. P2 / 结构与可观测性登记

P2 不进入首轮批量重构。只有在对应 P0/P1 修复触达同一文件时，才做最小相关清理。

### 5.1 后端边界

- API-P2-01：巨型 route/service/repository 文件；按端点域渐进拆分。
- API-P2-02：API 启动阶段执行 DuckDB schema migration；部署流程应固定先迁移后启动。
- API-P2-03：dev/staging 同步 fallback 与 production 行为不同；保留保护并加环境披露。
- API-P2-04：source preview repository 写函数缺 task write guard；补 guard。

### 5.2 治理与缓存

- GOV-P2-01：lock ttl 配置无效，OSError 根因被 timeout 掩盖，append 超时短于 read。
- GOV-P2-02：materialize 原始异常可能被失败记录追加异常替换。
- GOV-P2-03：product category Formal/Scenario 共用 cache_version 字符串。
- GOV-P2-04：cache manifest 合同不强制 report_date。
- GOV-P2-05：executive DuckDB edge hash 只覆盖首尾块和大小。
- GOV-P2-06：JSONL 读缓存只做浅拷贝。

### 5.3 共享工具

- SHARED-P2-01：calibers canonical 声明与生产实现漂移。
- SHARED-P2-02：正式 FX carry-forward 校验双份复制。
- SHARED-P2-03：safe_decimal 对缺失/非有限值静默归零且缺可观测性。
- SHARED-P2-04：USD/CNY 非营业日包含美国联邦假日，需要 CFETS owner 确认。
- SHARED-P2-05：H/A/T 末字符启发式会误分 CASH/TRUST 等英文值。
- SHARED-P2-06：币种维度二值化，EUR/HKD 等可能落入 CNY。
- SHARED-P2-07：FTP 费率表 2027 起静默回退默认值。
- SHARED-P2-08：未知付息方式回退年付，调用方丢失 fallback 标志。
- SHARED-P2-09：FX 同日重复值取首/末不一致、module registry 无锁、闰年年化、春节 freshness、Numeric float 边界等小项。

### 5.4 余额与会计分析

- BAL-P2-01：balance_workbook 包中存在休眠且漂移的实现。
- BAL-P2-02：治理调整 ADD 对非空值实际等价 OVERRIDE；未知算子也覆盖。
- BAL-P2-03：乱码死函数仍留在 service。
- BAL-P2-04：月度分析与共享格式器舍入策略不同。
- BAL-P2-05：显式科目缺失被当 0，缺少 missing-account 检查。
- BAL-P2-06：ADB trend 用自然日补 0 稀释 MA5/MA20。
- BAL-P2-07：liability cockpit 同页两个 NIM 使用不同成本分母。
- BAL-P2-08：OCI GL 映射只识别 1440101 前缀。
- BAL-P2-09：科目号硬编码与规则 JSON 双轨维护。
- BAL-P2-10：分桶 365 与加权期限 365.25 并存。
- BAL-P2-11：交叉分析动态列未进入 columns 声明。

### 5.5 固收与风险

- FI-P2-01：休眠 krd.py 丢弃短端桶；接线前必须修。
- FI-P2-02：risk_tensor 内有同样一年 bullet 近似的死代码。
- FI-P2-03：bond_duration 与 common 的碎期、凸性双实现分叉。
- FI-P2-04：TENOR_YEARS 缺 8Y/9Y/25Y/40Y/50Y，未知点静默忽略。
- FI-P2-05：浮息券按固定票面投影且无披露。
- FI-P2-06：缺 maturity 的券 DV01 记 0，应披露排除规模。
- FI-P2-07：weighted_avg_spread 实为 AAA 基准代理，字段名误导。
- FI-P2-08：interest mode 告警去重集合为进程级可变状态。
- FI-P2-09：var_engine/risk_metrics 休眠，参数硬编码且 HHI 双量纲。
- FI-P2-10：scenario stress service 用 float 做审查型金融计算。

### 5.6 宏观与策略

- MACRO-P2-01：composite 分项缺失时记 0 而不重归一。
- MACRO-P2-02：economic cycle 各相位分数上限不一致。
- MACRO-P2-03：当前相位与历史时间轴使用不同分类规则。
- MACRO-P2-04：基本面缺失候选绕过 top-fraction 过滤。
- MACRO-P2-05：leading indicator 各分项对缺失使用两种语义。
- MACRO-P2-06：中英文相位标签跨模块字符串耦合。
- MACRO-P2-07：gate `_safe_float` 不接受 Decimal/数字字符串。
- MACRO-P2-08：信用利差情景冲击施加到全部久期桶。
- MACRO-P2-09：期末价缺失行被剔除，存在幸存者偏差。
- MACRO-P2-10：cross-market correlation 在价格水平上计算。

### 5.7 前端

- FE-P2-01：LedgerPnLPage 约 45 处重复内联布局样式。
- FE-P2-02：金额固定小数位、空字符串 Number 转换、percent 绕行格式化不一致。
- FE-P2-03：concentration、AttributionWaterfallChart、TPL/Campisi、balance movement 结论链测试不足。

### 5.8 测试组织

- TEST-P2-01：`tests/` 与 `backend/tests/` 双根容易漏跑。
- TEST-P2-02：fx_rates 行为测试寄居 caliber 文件，可发现性差。
- TEST-P2-03：settings LRU 缓存依赖测试手工 clear。
- TEST-P2-04：模块级可变告警状态需要测试手工复位。
- TEST-P2-05：session 级共享 seed 已有 SHA 守卫；新 fixture 必须复用该模式。

---

## 6. 整改工作包与依赖

### Wave 0：发布阻断修复

#### WP-01：PnL Bridge 曲线契约修复

- 范围：`pnl_bridge_service.py`、相关 API/service 测试、Campisi bridge 消费测试。
- 不触碰：核心曲线公式、历史事实表、schema。
- 预计：0.5–1 天。
- 依赖：无。
- 风险：修复后历史页面分项数值会变化，但 total PnL 不应变化。
- DoD：SYS-P0-01 全部验收项通过。

#### WP-02：API 写路径隔离

- 范围：source backfill、CFFEX member rank、Livermore gate supplement、bond analytics curve prepare、choice-stock BackgroundTasks。
- 不触碰：队列/调度基础设施、数据库 schema。
- 预计：2–3 天，可拆为两个 PR。
- 依赖：复用已有 actor、run status 和 idempotency 机制。
- 风险：从同步响应改为异步 202，前端/调用方可能依赖旧响应形状；需保留兼容字段或同步更新客户端。
- DoD：API/service 路径没有 DuckDB write；生产无同步 fallback。

#### WP-03：集中度指标后端权威化

- 范围：liability core/service/schema/API、前端 component/model/tests。
- 不触碰：全局状态、client.ts、其他页面。
- 预计：1–1.5 天。
- 依赖：先登记指标单位与 HHI 量纲。
- 风险：现有页面数字可能变化；需用全量 golden sample 解释差异。
- DoD：前端不再计算 Top10/HHI，空数据不显示 0。

### Wave 1：正式正确性与证据完整性

#### WP-04：治理 stale、lineage 与 fingerprint

- 先做：FTP 参数入指纹、accounting movement stale 透传、按日报表 lineage、内容 SHA。
- 后做：manifest contract、lock 观测性、异常链保留。
- 预计：2–3 天。
- 风险：内容指纹升级会使旧缓存判 stale；需明确一次性重建计划。
- DoD：参数/内容变化能使缓存失效；旧日期不会引用新日期血缘。

#### WP-05：固收现金流与久期接线

- 先做：value_date 透传、物化 duration 优先、删除 service rate heuristic。
- 披露：DV01/情景双口径、浮息代理、缺 maturity 规模。
- 预计：2 天。
- 风险：value_date 修复会改变 30/90 日 liquidity gap；应先跑真实数据差异报告，再决定是否重物化历史。
- DoD：同一券在 cashflow 页面与 risk tensor 使用同一起息日和付息频率。

#### WP-06：前端 null/fallback 诚实呈现

- 范围：balance movement、PnL attribution、bond dashboard、balance analysis、PnL export、liability stale banner。
- 预计：2–3 天，可按页面拆 PR。
- 依赖：不改正式计算，只消费后端权威字段。
- DoD：缺数据不形成数字结论；partial aggregate 明确标记；stale/fallback 首屏可见。

### Wave 2：分析口径修正

#### WP-07：余额分析快速正确性

- 无 owner 阻塞：BAL-P1-01、02、03、04。
- 需要 owner：日均分母、未知期限、结构性存款粒度、阈值标定、HQLA。
- 预计：无阻塞项 2 天；owner 项另排。
- DoD：先用真实数据量化每项影响，再修改口径。

#### WP-08：宏观/策略信号

- 第一批：负 PE、1Y 窗口、政策工具交集、fallback 比例。
- 第二批：GDP 季节性、horizon 估值、实时/回测流动性宇宙。
- 预计：3–4 天。
- DoD：所有回测结果披露 execution basis、valuation basis、cost basis、fallback share。

#### WP-09：共享单位、舍入与 canonical

- 无 owner 阻塞：删 service auto heuristic、future freshness 披露、FTP 2027 fail-loud。
- 需要 owner：正式指标 HALF_UP/HALF_EVEN、CFETS 对美国假日、CNH/CNY 归并。
- 预计：2–4 天，按口径拆 PR。
- DoD：字段单位由契约声明；没有 `abs(value)>threshold` 的正式单位猜测。

### Wave 3：结构债与测试基础

#### WP-10：边界收敛

- macro route 按端点域迁移编排。
- 清除 route→repo、core→repo/governance/schema 反向依赖。
- service 公式迁回 core_finance。
- 不做全仓通用重构。

#### WP-11：重复实现与休眠代码

- 先建立生产调用图与等价性测试。
- 再处理 balance workbook、duration、FX validation、KRD/var 休眠实现。
- 正式历史口径变化必须有 owner 与重物化决策。

#### WP-12：测试门与工作区卫生

- 增加 service DTO 形状测试、独立黄金值和 null/stale 测试。
- 为 settings cache 增加 autouse 清理。
- 文档化双测试根。
- 将 `.codex-tmp`、pyc、截图和根目录异常文件从提交面隔离；只清理经确认的生成物。

---

## 7. 推荐 PR 切片

为了避免当前大工作区继续扩大，实施应使用独立 worktree/分支，并禁止 `git add .`。

1. PR-01：PnL Bridge curve dict contract + Campisi 回归。
2. PR-02：macro source backfill + CFFEX 改 actor。
3. PR-03：Livermore gate supplement + bond curve prepare + choice-stock 改 actor。
4. PR-04：liability concentration 后端契约 + 前端只读消费。
5. PR-05：FTP fingerprint + accounting movement stale + report-date lineage。
6. PR-06：source content hash + manifest contract。
7. PR-07：risk tensor value_date + duration 优先级 + rate heuristic。
8. PR-08：前端 null→0 第一批（balance movement + PnL attribution）。
9. PR-09：前端 partial/stale/export 第二批。
10. PR-10：QDB/ADB 无 owner 阻塞修复。
11. PR-11：macro signal 无 owner 阻塞修复。
12. PR-12：test goldens/settings fixture/hygiene。

每个 PR 只包含一个可解释的业务原因；owner 决策项不与无争议 bugfix 混在同一 PR。

---

## 8. 验证矩阵

本节是实施后的命令，不代表本轮审计已执行。

### 8.1 PnL Bridge / Campisi

```powershell
python -m pytest tests/test_pnl_bridge_curve_effects.py tests/test_pnl_bridge_with_curve.py tests/test_pnl_api_contract.py tests/test_campisi_attribution_service.py -q
```

必须新增：

- service 真实仓储 dict 曲线形状测试。
- 非零 roll-down/treasury/spread 数值断言。
- Campisi selection 不吸收曲线贡献断言。

### 8.2 API 写边界

```powershell
python -m pytest tests/test_service_storage_boundaries.py tests/test_lazy_task_import_constants.py tests/test_write_refresh_idempotency_contract.py -q
```

必须新增：

- 四个 refresh endpoint 只调用 `.send`。
- production 无 sync fallback。
- worker 才进入 repository task write scope。

### 8.3 治理与缓存

```powershell
python -m pytest tests/test_pnl_by_business_precompute.py tests/test_result_meta_required.py tests/test_result_meta_source_surface_followup.py -q
```

必须新增：

- FTP 费率变化使缓存 stale。
- 同大小同 mtime 但内容变化使 source version 变化。
- 旧报告日只读取旧日期 lineage。
- accounting movement 缺正式行时 quality 非 ok。

### 8.4 固收

```powershell
python -m pytest tests/test_risk_tensor.py tests/test_cashflow_projection.py tests/test_bond_analytics_engine.py -q
```

必须新增：

- 两年以上 bullet 券进入 30/90 日窗口的全存续期利息。
- service 优先采用物化 duration。
- 半年付息频率不被回退年付覆盖。

### 8.5 余额与会计

```powershell
python -m pytest tests/test_qdb_gl_monthly_analysis_core.py tests/test_adb_comparison_rows.py tests/test_liability_compat_rate_precision.py -q
```

必须新增：

- 14004/14005 时点扣减。
- 有贷款无存款行业。
- 单日 ADB 不生成伪随机值。
- 0.3% 低票息显式单位。

### 8.6 宏观与策略

```powershell
python -m pytest tests/test_factor_screen_candidates.py tests/test_macro_bond_linkage.py tests/test_portfolio_backtest.py tests/test_cycle_macro_score.py -q
```

必须新增：

- 负 PE/PB/PS。
- 真正一年窗口。
- 工具集合交集。
- horizon valuation basis。
- proxy fallback share。

### 8.7 前端

```powershell
Set-Location frontend
npm run test -- LiabilityCounterpartyBlock BalanceMovementAnalysisPage AttributionWaterfallChart balanceAnalysisPageModel bond-dashboard pnlByBusinessExport
npm run typecheck
npm run debt:audit
```

页面/API client/model/formatter 改动后必须执行 debt audit；修复 P0/P1 页面时再做浏览器级首屏 stale/null 验收。

### 8.8 扩大验证的触发条件

只有出现以下情况才扩大到全量：

- 共享 Numeric、rate_units、Decimal helper 被修改。
- schema 或跨页 client 被修改。
- actor/任务调度公共代理被修改。
- targeted tests 暴露跨域回归。

---

## 9. 口径 owner 决策闸门

以下事项不得由实现者自行选择：

1. HQLA Level 2B 是监管口径还是内部管理口径；同业存单如何分类。
2. 日均分母统一为自然日、观测日还是按产品分别定义。
3. 缺 maturity 进入未知桶、已到期桶还是最短期限桶。
4. 正式金额与收益率使用 HALF_UP 还是保留现有 HALF_EVEN。
5. 面值 DV01 与市值情景 PnL 是否统一；若不统一，字段和页面文案如何命名。
6. CFETS 中间价营业日是否受美国联邦假日影响。
7. CNH 是否继续归入 CNY。
8. 结构性存款组件/合计应覆盖全 21601/21602 家族还是指定 11 位科目。
9. 期限缺口严重度使用绝对亿元阈值还是资产比例阈值。

每个决策包必须包含：

- 当前实现与替代方案。
- 至少一个真实日期的数据差异。
- 受影响页面、事实表和黄金样本。
- 是否需要历史重物化。
- owner 签核与生效日期。

---

## 10. 已关单事项：不得重复返工

对照 `docs/audits/2026-07-19-system-calculation-audit.md`，以下事项已经修复或已有明确裁决，本方案不重新打开：

- zqtz ytm/coupon 百分数口径与主引擎显式归一。
- CFETS 2024–2026 假日与长假 carry-forward 主问题。
- QDB `startswith("2026")` 年份硬编码。
- vol target / benchmark gate 同日前视。
- `yield_by_period` 季/年分母。
- `bond_four_effects` 跨付息日票息。
- KRD 读模型字段披露型改名。
- balance workbook CNY 请求口径。
- PnL volume-rate 余额规模重复消费与后端 recon。
- 514/517 VAT 2026H1 截止是已文档化业务决定；仅保留首次 2026-07 物化后的人工量级核对。
- PnL roll-down 期末曲线、期末剩余期限、上斜为正的现行口径。
- 信用利差按实际剩余期限插值。
- H/A/T、发行类剔除、FX、514/516/517、Formal/Scenario 五类高风险测试已存在。

如果新修复触及这些代码，只做回归验证，不在同一 PR 中重新设计口径。

---

## 11. E3 待验证队列

PnL 中断审计曾提出以下候选，但没有完成最终证据闭合，暂不作为确认缺陷：

- V1 `capital_gain_517` 与正式路径的事件类型/日期 gating 是否分叉。
- workbench 量价规模 key 是否仍遗漏 accounting_basis/currency_basis。
- benchmark excess 的收益率单位是否存在特定调用路径错配。
- product category scenario 零基数比率语义。
- Campisi 与 bridge 的质量阈值是否需要统一。

验证顺序：

1. 先对照 2026-07-19 已修复清单，排除旧结论。
2. 只读追踪当前生产调用方和输入单位。
3. 能构造独立反例时才升级为 P1/P0。
4. 只有升级后才创建实现工作包。

---

## 12. 最终完成定义

全系统整改不以“所有 P2 清零”为目标，而以以下可验证状态为完成：

1. 正式 PnL Bridge 曲线贡献在真实 service 路径中可计算、可闭合、可追溯。
2. API 和 service 请求路径对 DuckDB 全部只读，所有物化都由任务进程执行。
3. 前端不补算正式金融指标，空数据不展示为 0，partial/stale/fallback 首屏可见。
4. 指纹覆盖正式数据、关键参数与规则，按日报表 lineage 不跨日期。
5. 正式单位不再依赖数值大小猜测。
6. 每个高风险公式有独立黄金值，适配器测试使用真实 DTO 形状。
7. owner 决策项都有签核、差异报告和是否重物化的结论。
8. targeted tests、typecheck、frontend debt audit 全部通过；共享边界变化时再扩大验证。
9. 每个 PR 都能说明“修了哪个业务风险”，且不包含当前工作区其他未提交改动。

