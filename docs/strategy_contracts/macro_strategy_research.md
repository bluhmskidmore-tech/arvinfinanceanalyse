# 宏观策略研究 V1 合同

- 状态：`V1 contract frozen; P0 evidence gaps open`
- 适用路由：`/macro-toolkit`、`/macro-observation`
- 生效范围：统一只读研究目录与研究结果的业务语义；不授权 schema、权限框架、公式、依赖、写接口或实盘链路变更。
- 页面合同：`docs/page_contracts.md` §13.9 `PAGE-MACRO-TOOLKIT-001`、§13.10 `PAGE-MACRO-OBS-001`。
- 实施边界：`.omx/plans/2026-07-18-macro-strategy-research-cockpit-implementation.md` §3、§5、§6、§17，以及其最终覆盖文件 §3—§6。

## 1. 页面主问题与 V1 边界

两个路由共享的只读研究面首先回答：

> 今天哪些研究信号可用、该先看什么，以及哪些结论因为数据或治理问题不能用于正式决策？

V1 只标准化仓库已有研究能力，不改变现有公式，不新增量化框架，不产生正式投资信号、订单或实盘执行指令。所有 catalog 和 result 必须固定为：

- `observation_only=true`
- `formal_use_allowed=false`

这两个字段不得被页面模式、成功状态、回测结果或 admission 结论覆盖。任何从 observation-only 晋升为正式指标或投资信号的动作都需另行审批；本合同不提供该授权（实施计划 §3.3、§17）。

## 2. V1 策略目录

下表冻结策略家族、当前仓库来源和允许的展示模式。来源只证明仓库已有实现或注册入口，不证明数据血缘、日期、最小历史、stale SLA 或 admission 已通过。

| 策略家族 | V1 策略 | 当前来源锚点 | V1 展示模式 |
| --- | --- | --- | --- |
| A 股趋势 | 均线、均值回归 + 动量 | `backend/app/core_finance/macro/equity_strategies.py`（`mean_reversion_momentum_strategy` 等现有纯函数）；实施计划 §3.1 | `observation` |
| A 股横截面 | 多因子、行业中性、低拥挤多因子 | `backend/app/core_finance/macro/equity_strategies.py`（`multi_factor_selection`、`low_crowding_multifactor_selection`）；Choice 股票与因子表见实施计划 §2.2 | `observation` / `shadow` |
| A 股风险 | 踩踏风险、拥挤、涨跌停质量 | `backend/app/core_finance/macro/equity_strategies.py` 的 crowding 计算入口及现有宏观工具页证据；实施计划 §3.1 | `observation` |
| A 股组合 | 影子组合及成本情景 | `backend/app/core_finance/macro/equity_shadow_portfolio.py`（现有 `0/10/20/50bp` 成本情景）；实施计划 §2.2、§5.4 | `shadow` / `backtest` |
| 宏观状态 | Merrill Clock、经济周期、领先指标、流动性/利率状态 | `backend/app/core_finance/macro/toolkit/runner.py` 的现有脚本注册入口；实施计划 §2.2、§3.1 | `observation` |
| 趋势/波动 | CTA Trend、Regime Switch、GARCH/DCC | `backend/app/core_finance/macro/toolkit/runner.py` 的现有脚本注册入口；实施计划 §2.2、§3.1 | `observation` / `backtest` |
| 资产配置 | Risk Parity、风险预算、再平衡 | `backend/app/core_finance/macro/toolkit/runner.py` 的现有脚本注册入口；实施计划 §2.2、§3.1 | `shadow` |
| 风险聚合 | Crisis Score、Crowding、Final Signal、Risk Monitor | `backend/app/core_finance/macro/toolkit/runner.py` 的现有脚本注册入口；实施计划 §2.2、§3.1 | `observation` |
| 债券/跨资产 | 债券期货基差、IRR、安全边际、信用 carry、曲线趋势 | `backend/app/core_finance/macro/toolkit/scripts/bond_futures_data.py`、`credit_bond_data.py`；实施计划 §2.2、§3.1 | `observation` / `candidate` |

V2 候选策略不属于 V1 主矩阵。Qlib、PCA、事件意外、跨国相对价值及其他高级策略必须逐项通过数据、PIT/vintage、许可证、回测和 admission 闸门后才能进入（实施计划 §3.2、§9、§10 P5）。

## 3. Strategy Catalog 必填合同

每个策略必须登记以下字段；字段缺失、空 owner、无证据的占位值或未确认的关键业务值，均不得进入主策略矩阵：

- 身份与归属：`strategy_id`、`strategy_family`、`asset_scope`、`display_name`、`description`、`owner`。
- 计算与展示：`calculation_mode`（`library` / `script` / `external_adapter`）、`result_modes`（`observation` / `shadow` / `backtest` / `admission_candidate`）。
- 数据门槛：`required_inputs`、`minimum_history`、`update_frequency`。
- 版本与许可证：`rule_version`、`code_version`、`license_mode`。
- 治理：`observation_only=true`、`formal_use_allowed=false`。

`strategy_id` 必须稳定；`required_inputs` 必须能追到输入表/字段与日期语义；`rule_version` 和 `code_version` 不得用页面版本代替。Catalog 字段集合来自实施计划 §5.1。本轮未冻结每条策略的 `owner`、`minimum_history`、`update_frequency` 或输入矩阵的具体值；这些值必须在 P0 由证据和业务 owner 确认，禁止用统一默认值补齐。

## 4. Research Result 必填合同

API DTO 与未来持久化 manifest 至少包含：

- 身份：`result_id`、`strategy_id`、`run_id`、`result_kind`。
- 日期：`report_date`、`signal_as_of`、`price_as_of`、`factor_as_of`、`macro_as_of`、`generated_at`。
- 时点：`pit_mode`、`release_timestamp_basis`、`fallback_date`。
- 结果：`raw_signal`、`normalized_state`、`confidence`、`exposure_hint`。
- 版本：`rule_version`、`code_version`、`parameter_hash`、`source_versions`、`vendor_versions`。
- 证据：`tables_used`、`input_evidence`、`artifact_ids`、`warnings`。
- 治理：`status`、`quality_flag`、`admission_status`、`observation_only`、`formal_use_allowed`。

必填表示字段必须出现在合同中，不表示可以伪造业务值。无法证明的值必须为显式空值并带 `warnings`、非 `ready` 状态和相应阻塞原因；不得用 `0`、空字符串、当前日期或前端 fallback 冒充已确认值。字段集合来自实施计划 §5.2。

### 4.1 日期分离

- `price_as_of`、`factor_as_of`、`macro_as_of` 必须分别展示和传递，不得合并为单个“最新日期”。
- `factor_as_of <= signal_as_of`；无法证明时不得输出 `ready`。
- 宏观输入用于历史决策或回测时，必须证明 `available_at <= decision_at`，并记录首次可用值或指定 vintage。
- `fallback_date` 非空时必须与源日期、`quality_flag` 和 `warnings` 同时可见。
- `generated_at` 只是生成时间，不替代价格、因子、宏观或信号日期。

这些规则与页面合同 §13.9 D、§13.10 D 及实施计划 §6.2、§10 P2/P4 一致。

### 4.2 信号比较边界

- `raw_signal` 是模型内部量纲，只能在同一策略、同一规则版本和明确参数语义下解释。
- `normalized_state` 是受控展示状态，不得与 `raw_signal` 混为同一数轴、分数或排序键。
- 跨策略页面可以并列展示 `normalized_state` 类别，但不得把它转成无规则数值排名；`raw_signal` 也不得跨模型横向排名。
- V1 不提供跨资产家族“总分”“最优策略”或自动投资建议。

## 5. 状态枚举

Research Result 的 `status` 只允许以下值，且不得统一折叠为 `--`：

| 状态 | 最低语义 |
| --- | --- |
| `ready` | 所需输入、日期、版本和本合同门禁均已满足；仍保持 observation-only / non-formal |
| `degraded` | 结果可作为受限观察证据，但存在明确 warning、fallback 或部分证据缺口 |
| `stale` | 已超过该策略经 P0 冻结的 stale SLA；必须显示源日期与超期原因 |
| `insufficient_history` | 可用历史短于该策略经 P0 冻结的 `minimum_history` |
| `missing_input` | 必需输入、日期、版本或证据缺失 |
| `registered_not_runnable` | 已登记，但当前依赖、数据或运行入口不满足 |
| `run_failed` | 已尝试运行且失败；必须保留安全错误与运行身份 |
| `permission_denied` | 后端拒绝了受控读取或操作；前端不得伪装为成功或空数据 |
| `not_admitted` | 未通过或尚未完成适用的 backtest/admission 门禁 |

`quality_flag`、`admission_status` 和 `status` 是不同维度，不得互相代替。Job Receipt 另用 §7 的作业状态，不得塞入 Research Result 状态。

## 6. 回测与 admission 最低合同

回测结果必须与即时观察结果分区显示。每个 backtest/admission 至少记录：

- 样本区间、基准、调仓频率、执行延迟。
- 交易成本与滑点情景。
- 股票池以及 ST、停牌、涨跌停、退市处理；期货策略另需连续合约、换月和价格调整规则。
- 年化收益、波动、最大回撤、换手、命中率及稳定性。
- PIT 完整率、修订敏感度、压力窗口表现。
- `admission_status`：`admitted` / `conditional` / `rejected`，以及可审计理由。

现有影子组合的 `0/10/20/50bp` 只可作为 A 股影子组合 V1 基线，不授权跨资产家族直接比较，也不自动产生 `admitted` 结论（实施计划 §5.4）。基准、延迟、样本、成本、资产家族处理规则和通过阈值尚待 P0 证据与 owner 冻结；本合同不猜默认值。

## 7. Read / Refresh / Execute 与 Job Receipt 边界

| 能力 | 权限语义 | `/macro-observation` | `/macro-toolkit` |
| --- | --- | --- | --- |
| 研究结果读取 | 复用既有 `read` scope；只读 summary/catalog/results/backtests | 允许；只请求共享只读研究合同 | 允许；复用同一只读合同 |
| 运维/作业状态读取 | 只用于 toolkit operations shell，不因“只读 GET”而自动成为 observation 能力 | 不请求 | 允许，仍受后端授权与审计约束 |
| 数据刷新 | 复用既有 `refresh` scope 与既有 owner/锁/idempotency | 不注册、不请求、不展示 | 仅显式动作；不得在页面加载时自动触发 |
| 模型/脚本执行 | 复用既有 `execute` scope 与既有执行 owner | 不注册、不请求、不展示 | 仅显式动作；不得创建下单或实盘指令 |

前端隐藏按钮不构成权限控制；后端必须判定 scope。`/macro-observation` 在 loading、empty、degraded、error 和 success 状态都不得请求 scripts、refresh、execute、job/receipt 等 operations 能力。最终执行覆盖 §3—§6 要求 P1 只新增只读 research endpoints；统一 `POST /research/jobs` 延后到 P3，且必须适配既有唯一 owner，不得复制执行、队列、锁或刷新链。

统一 Research Job Receipt 的最低字段为：

- `job_id/run_id`、`job_type`、`target_scope`。
- `queued_at`、`started_at`、`finished_at`。
- `status`：`queued` / `running` / `conflict` / `completed` / `partial` / `failed` / `dry_run`。
- `idempotency_key`、`lock_key`。
- `result_manifest_ids`、`artifact_ids`。
- `error_category`、`safe_message`、`audit_reference`。

该 receipt 合同是 P3 的兼容目标，不授权 MCR-001 新增写接口。

## 8. PIT / vintage fail-closed

- 事件意外、修订敏感回归、历史宏观回测或任何声称历史时点可复现的结果，若缺少可靠 `release_at/available_at/vintage/revision` 证据，必须 fail closed：不输出 `ready`、不进入回测/admission、不中途用最新修订值回填历史。
- 仅做当前观察且不具备完整 PIT/vintage 时，最多可作为显式 `degraded` 观察证据；必须说明缺口，保持 `observation_only=true`、`formal_use_allowed=false`，不得展示为历史可复现结果。
- 因子可用时点无法证明、价格/因子/宏观日期错位无法解释、必需来源版本缺失时，同样不得静默成功。
- V1 不接入依赖可靠发布时点的跨国宏观与事件意外策略（实施计划 §2.3、§3.3、§6.2）。

## 9. P0 待证据冻结项

以下业务值须由证据与业务 owner 确认，禁止从页面文案、样例、脚本默认值或当前最新日期猜测。签核记录见 `docs/strategy_contracts/macro_strategy_p0_owner_signoff_packet_2026-07-19.md`（2026-07-19 晚 owner 拍板，工程按证据上限代录；挂起项仍开放）：

- 每条策略的正式 `owner` 与审批责任人。→ **已冻结（家族级）**：均为 arvin（见签核包第 2 节 Owner 栏）。
- 每条策略的 `required_inputs` 表/字段/单位/精度/币种、source/vendor version 与 fallback 规则。→ **部分冻结**：签核包第 2 节已确认证据表内清单；逐策略字段级矩阵与单位逐序列核对仍开放/挂起。
- 每条策略的 `minimum_history`；不同资产和策略不得共用未经证明的统一门槛。→ **部分冻结（宣称上限）**：签核包第 2 节已按输入族代录（均 ≤ 证据上限）；标注「挂起」的腿（NCD、因子连续窗、Choice 信用等）仍开放。NCD 与主要 Choice 信用历史已于 2026-07-20 回补，但数据行数增加不自动冻结 minimum_history 或 proxy/单位口径（见签核包 §5.4）。**语义澄清（2026-07-20）**：该值是 catalog/`catalog_history_ceiling`，不是运行时 bar 门禁；代码仍用 CTA80/DCC120/RP100 等 `runtime_min_bars`（见签核包 §1.2.1）。未另冻 runtime 门槛前，不得把年限直接实现为合同 §5 `insufficient_history` 统一闸门。
- 股票、宏观、债券/期货各自的 stale SLA 与 `update_frequency`。→ **部分冻结**：见签核包第 2 节 stale SLA 栏（保守 T+5/T+10/T+35/T+45）。
- 交易日/自然日、复权、股票池、退市、停牌、涨跌停、期货换月和价格调整规则。→ **挂起**（签核包 §4.4）。
- 回测基准、样本区间、执行延迟、成本/滑点、压力窗口和 admission 阈值。→ **部分**：A 股影子组合成本情景确认 0/10/20/50bp 为 V1 基线；其余（基准、admission 等）**挂起**（签核包 §4.1—§4.3）。
- 宏观 `release_at/available_at/vintage/revision` 完整率及可支持的 PIT 模型范围。→ **已证据冻结**：完整率 0%；历史时点复现 fail-closed（见证据审计 §1 / 签核包 §3）。

凡仍开放或挂起的项：不得把占位值写成已冻结事实；受影响策略不得标记 `ready` 或 `admitted`，并应使用最贴近原因的显式状态与 warning。`observation_only=true` / `formal_use_allowed=false` 不被本次签核覆盖。

## 10. 证据范围与残余风险

本轮使用的本地证据为：页面合同 §13.9/§13.10、宏观策略研究实施计划 §2—§17、最终执行覆盖 §3—§6、签核包（2026-07-19 owner 代录）、以及表中列出的当前代码/脚本注册锚点。本轮 `moss-metric-contracts`、`moss-lineage-evidence`、`moss-data-catalog` 均不可用；**家族级 owner / 宣称上限型 minimum_history / 保守 stale SLA 已在签核包第 2 节部分冻结**（见上 §9），但**未**据此冻结逐策略字段级指标定义、单位、source lineage、报告日覆盖，也未冻结 runtime bar 门禁或 admission 阈值。

残余风险：当前来源锚点只能证明实现入口存在，不能证明输入可用性、PIT 正确性、数据新鲜度或 admission readiness。P0 证据补齐前，本合同只冻结字段、枚举、页面/权限边界和 fail-closed 行为，不冻结任何新公式或正式业务真值。

### 10.1 P0 证据审计进展（2026-07-19）

`docs/strategy_contracts/macro_strategy_p0_evidence_2026-07-19.md` 完成了首轮只读数据面审计（MCP 不可用，采用等价本地只读 DuckDB 查询）：

- **已证据冻结**：全部 8 张系统源表无 `release_at/available_at/vintage/revision` 列，PIT 完整率为 0；依赖历史时点复现的结果必须按 §8 fail closed。
- **部分证据化**：各输入族可用历史深度、当前新鲜度滞后基线、源表 schema 已量化；首轮发现的 NCD 与主要 `EMM*` 历史缺口已于 2026-07-20 回补，当前明细见签核包 §5.4。
- **仍开放 / 挂起**：回测基准、admission 阈值、交易日历/复权/换月细则、逐策略字段级输入矩阵、因子连续窗，以及 NCD proxy 语义、Choice 单位/catalog 准入等；历史行数增加不自动冻结这些业务口径，详见签核包 §4 / §5.4。
- **owner 签核代录（同日晚）**：`macro_strategy_p0_owner_signoff_packet_2026-07-19.md` 已写入家族级 owner、`minimum_history`、stale SLA 与可代录项；数值均 ≤ 证据上限，不改变 observation-only 边界。
- **minimum_history 语义复核（2026-07-20）**：代码映射确认第 2 节年限为宣称上限，非 runtime 门禁；详见签核包 §1.2.1。
- **输入契约诚实化（同日续）**：`M0041653` 运行时优先 Choice `EMM00088132`（616 行，2024-01-02～2026-07-20），legacy 仅保留历史观测且 Choice 失败不再静默 carry-forward；`M0017126` PMI 别名已登记并落在 `fact_choice_macro_daily`（约 13 个月频点）。详见签核包 §2.5 / §4.6 第 1、7 项。
- **观察能力接线（同日续）**：M13 利率拐点、M12 跨市场联动均已 `wired/visible`；无可算相关腿时 M12 输出 `unavailable/UNKNOWN`，不再伪装「常态」。Merrill Clock 审计 C-1/H-1/M-2/M-4 已修（见 `docs/audits/2026-07-19-merrill-clock-calc-audit.md`）。
- **M12 美债腿（2026-07-20）**：`CA.US_GOV_10Y` → 首选 `E1003238`（次选 `EMG00001310`）已登记并写入宽表/曲线 enrich；实测约 125 日点。VIX 无 catalog/落库序列，股债(VIX)相关腿继续 `unavailable`，待数据准入后再登记。
- **M7 政策利率 freshness（2026-07-20）**：`EMM00088132` 已进入 Choice `stable_daily` catalog 与 `macro_toolkit_freshness_refresh_v3` required step；45 日窗口刷新后最新为 1.40% / 2026-07-20，`POLICY_RATE_7D_STALE` 消失。刷新拒答会 fail closed，不用旧值续写新日期。
- **M7 共同可算日对齐（同日续）**：估值日优先「能算 10Y−1Y 国债斜率」的最新日（否则资金锚点日），输出顶层 `as_of_date`；AA−AAA 仅同期限。只读实库复核 `as_of=2026-07-17`，`GOVERNMENT_SLOPE_MISSING` / `AAA_SPREAD_MISSING` 消失，能力 `complete`。
- **M10 缺月诚实性（同日续）**：生产宽表为前向填充值保留逐字段 `*_source_date`；M10 不再把跨月 carry 当成新观测，并为整月无真实观测的日历空洞保留 `None`。均值仅用有效月，`history_samples.used/total` 与 `*_HISTORY_MISSING_MONTHS` 披露真实缺口；合法 0 按公式评分，当前缺失分项从加权中剔除，空输入不再伪装为中性 50，结果固定 `observation_only=true / formal_use_allowed=false`。
- **M10 共同月 / 窗口 / provenance（2026-07-20 收口）**：对齐策略为严格 6/6 最新共同可算经济月（`alignment_policy=latest_common_computable_month`）；主窗 12 个完整日历月、challenger `shadow_24m` 24 月；日频腿取月内末日真实观测，跨月 forward-fill 不计分。派生利差 `input_evidence` 须 value/date/unit/legs 同源（`curve_derived`），禁止 July 值配 April alias 日。只读实库 `report_date=2026-07-20`：`as_of_month=2026-06`、`available_component_count=component_count=6`、`lei_index≈50.29`、`lookback_months=12` / `shadow_24m.lookback_months=24`、`observation_only=true` / `formal_use_allowed=false`；warnings 含 `LEI_UNIT_CONTRACT_UNFROZEN`、`PIT_METADATA_UNAVAILABLE`、`LEI_AS_OF_MONTH_LAGGED`、`LEI_NEWER_COMPONENT_DATA_EXCLUDED`；July 市腿仅出现在 `latest_available_component_evidence`（`used=false`），不再出现 1/6 单腿主结论。单位与 PIT 仍未冻结，不改变 formal 边界。残余：无 provenance 时 alias `series_id`/`source` 回填身份（Quality Important #2）本轮未硬修。
- **回补后能力复核（2026-07-20）**：NCD.SHIBOR 五期限各 632 行，主要国债/信用 `EMM*` 节点各 632 行；daily freshness 已接入 NCD 刷新。M9/M7 均改为按国债可算日对齐并输出 `as_of_date`，AA-AAA 只做同期限比较；M7/M9 只读实库均为 `complete`（`as_of=2026-07-17`）。能力健康度现为 11 `complete` / 4 `degraded` / 0 `unavailable`。Choice 回补行 unit 元数据仍待逐序列冻结，因此继续维持 observation-only / non-formal。
