# PRD：MOSS 统一发布控制面

- 状态：Approved，待 owner 指派
- 日期：2026-08-31
- 文档类型：专项产品与架构需求
- 适用范围：repo-wide Phase 2 正式计算主链中的发布治理
- 业务 owner：`PENDING`
- 技术 owner：`PENDING`
- 治理/发布 owner：`PENDING`

## 1. 请示决定

建议批准建设“MOSS 统一发布控制面 v1”，把数据库就绪、正式计算版本、API/页面契约、前端精确数值和业务审批证据绑定为同一个可校验的发布对象。v1 不新建独立平台服务，继续采用模块化单体，在现有迁移、物化、契约校验、数值协议和治理仓储之上补齐统一编排。

本 PRD 建议同时确认三项实施原则：业务域按逻辑 lane 维护唯一 `current`，共享 DuckDB 则以 `duckdb-main` 物理整库 bundle 统一切换和追踪；生产启动只读校验，不自动迁移或重算；候选产物经过机器验证和独立业务审批后才能切换，回滚恢复兼容的逻辑版本、物理数据 bundle 及应用/前端构建，不改写历史记录。

本文件从属于仓库根 [MOSS Agent Analytics OS PRD](../prd-moss-agent-analytics-os.md)，不改变 [DOCUMENT_AUTHORITY.md](DOCUMENT_AUTHORITY.md)、[CURRENT_EFFECTIVE_ENTRYPOINT.md](CURRENT_EFFECTIVE_ENTRYPOINT.md) 和现行 Phase 2 边界，也不构成生产迁移、数据重物化、业务批准或正式使用授权。

本 PRD 只覆盖剩下五项系统问题，不含第一个 auth/RBAC 课题。五项分别是：数据库就绪、正式计算版本编排、API 与页面契约、前端精度边界、治理与审批证据。

## 2. 问题与现状

剩余五项风险的共同问题是发布事实分散。各模块已经分别具备版本、校验或审批能力，但系统还不能用一个发布编号回答“这次上线用了哪版代码、哪版 schema、哪套计算规则、哪批物化结果、哪份接口契约、谁依据什么批准，以及应回滚到哪里”。

当前证据表明这是“已有部件尚未编排”，不是需要重写平台：

- [storage_bootstrap.py](../backend/app/storage_bootstrap.py) 已区分开发环境迁移与非开发环境校验，但非开发环境目前只断言 DuckDB current；[postgres_migrations.py](../backend/app/postgres_migrations.py) 只有显式升级入口，缺少对等的只读 current 断言。
- [backend_release_suite.py](../scripts/backend_release_suite.py) 已提供正式计算主链的有界发布门，但运行于隔离存储，并显式跳过启动存储迁移，不能代替目标生产环境 readiness。
- [formal_compute_lineage.py](../backend/app/governance/formal_compute_lineage.py)、`cache_build_run` 和 `cache_manifest` 已记录正式物化血缘；债券计算、债券物化和风险张量仍分别持有版本语义，尚未组成可提升、可回退的发布单元。
- [api_contract_check.py](../scripts/api_contract_check.py) 已具备 OpenAPI 基线和 breaking-change 检查；严格 DTO、前端契约与业务批准尚未统一挂到同一次发布上。
- [numeric.ts](../frontend/src/api/numeric.ts) 已识别 `raw_text`，但正式消费路径仍存在向 JavaScript `number` 收敛的双轨；[format.ts](../frontend/src/utils/format.ts) 也明确要求按页面逐步迁移，不能全站一次性替换。
- [check_average_balance_business_owner_approval.py](../scripts/check_average_balance_business_owner_approval.py) 已能 fail-closed 检查审批证据，但“材料已捕获”“业务已批准”“允许正式使用”仍是不同状态，不能相互代替。

[2026-06-10-system-audit-manifest.json](audits/2026-06-10-system-audit-manifest.json) 只能作为 2026-06-10 的历史基线；实施前必须重新生成当前证据，不能把其中的页面数、待办数或认证数当作 2026-08-31 的实时事实。

### WP0 当前基线与阻断项

以下基线截至 2026-08-31，只描述当前本地工作区或代码来源。除明确标为代码来源的事实外，不得外推为生产环境状态。

| 证据状态 | 当前基线 | 对后续工作的影响 |
| --- | --- | --- |
| 已验证：本地开发拓扑 | 一个约 3.04 GB、至少 74 张跨固定收益、损益、股票、宏观和余额表的 DuckDB 文件，由 API、worker 和多个调度入口共用或硬编码引用 | 否定按固定收益 lane 独立切换整库文件；生产拓扑仍待确认 |
| 已验证：代码来源 | PostgreSQL Alembic script head 为 `c2e94f6a8b10`；readiness 实际从 Alembic revision graph 动态读取全部 heads，不依赖此处硬编码值 | 生产 applied heads 仍为 `PENDING`，目标环境 readiness 回执缺失 |
| 已验证：本地 DuckDB | 普通迁移期望 v1—v45；受控 v46 未应用；本地账本却有未在现行 manifest 注册的 v47、v48 | 必须先解释并登记额外版本，确定 v46 和惰性 schema 的治理顺序，才能冻结 schema baseline |
| 已验证：校验缺口 | 当前 DuckDB current 断言只阻断缺失的期望版本，允许未知额外版本；部分惰性 ensure 也不在主断言覆盖内 | WP2 必须补齐 unknown-extra、描述/checksum 和惰性 schema 校验 |
| 已验证：本地固定收益 | 代码中债券引擎、债券物化和风险张量版本分层且有重复定义；本地风险事实混有 v5/v6，修复记录、现状和新增质量字段物化状态不一致 | 规则版本号、负收益率/票息语义、历史重物化范围和黄金样本均待 owner 决定，阻断 WP4/WP7 |
| 已验证：本地契约 | OpenAPI default/full 快照已漂移，未发现 breaking change；严格响应保真测试仍有 1 个 ADB 月度样本因缺少顶层 `calibration` 和 `result_meta.trace_id` 失败 | 先落地独立基线并解决 producer/sample 契约，再形成 contract receipt |
| 已验证：本地数值 | 公共 Numeric 边界已保留 `raw_text`；债券仪表盘卡片/tooltip 优先 `raw_text`，图表坐标仍停在 `number` 边界，raw-only fallback 兼容，mixed backend/fallback 占比按 fallback 子集市值分摊且 40/40 反例已通过，分桶/排序/正式计算未改；现金流与 PnL Bridge 本地后端 wire、Risk Home、PnL 量价闭合、Risk Tensor 判断与金额缩放、Decision Items 十进制金额文本，以及 Balance Analysis 直接字符串展示已有 Decimal 路径与反例；TPL 市场端点主链保持原 float/correlation/interpretation/quality/raw/display 不变，仅在全 exact 时追加 `raw_text` sidecar，mixed/null/invalid/nonfinite fail-closed，10001 条 `DECIMAL(24,8)` 极值样本已覆盖，前端 card/tooltip 与 ProductCategory 字符串 exact，series 和 legacy number 保持旧行为；受控 registry、AST 守卫和 Manifest numeric policy digest 已落地 | Balance Analysis 正式对账/排序、Cashflow/PnL Golden、Campisi 正式 producer/规则版本、其他页面及 14 项 pending 兼容基线仍未闭合，`controlled_paths` 已从 24 增至 27、`release_eligible=false` 仍保持，仍不足以认定 WP5 或全站 exact-numeric 完成 |
| 已验证：本地审批 | 8 个页面审批 checker 合计 103 项待办；8 项计算口径决定全部待批准；严格 `--require-captured` 尚未成为 promote gate | 结构检查可进入 PR 门，真实批准只能阻断对应 lane 的 promote，不能由脚本代签 |
| 推论：高置信度 | 基于共享单文件、跨域表和共同写路径，按固定收益 lane 直接切换或回退整库会连带影响其他域 | 物理范围应为 `duckdb-main` whole bundle；这是设计推论，不是生产状态或执行授权 |
| 待 owner/环境确认 | 生产副本数、挂载方式、调度 owner、队列排空方式、RTO/RPO、审批权威载体及 GitHub required checks | 阻断生产切换设计和 WP7，不阻断本 PRD 的文档修正 |

### 五项问题与对应处理

| 剩余问题 | 核心处理 | 对应需求 |
| --- | --- | --- |
| 数据库就绪 | 把生产启动的只读 current 断言与显式迁移拆开，非开发环境 fail-closed | FR-2 |
| 正式计算版本 | 用 Release Manifest、逻辑 lane current、`duckdb-main` 物理 bundle 和 shadow candidate 把版本、来源、物化和回滚绑在一起 | FR-1、FR-3 |
| API 与页面契约 | 用 OpenAPI 基线、严格 DTO 和 contract receipt 阻断 breaking change | FR-4 |
| 前端精度边界 | 以 `raw_text` 为无损权威，Decimal 只在需要时进入前端运算 | FR-5 |
| 治理与审批证据 | 机器验证、业务批准和正式使用分层，所有证据都回写到不可变账本 | FR-6、FR-7 |

## 3. 产品目标与成功定义

v1 要把“测试通过”提升为“发布对象完整、机器门禁通过、业务批准有效、运行环境可消费、上一版本可恢复”。具体目标是：

1. 任一正式结果都能由一个 `release_id` 追溯到代码、schema、规则、来源、物化产物、接口契约、前端数值策略和审批证据。
2. 任一子门失败时保持上一 `current` 不变，并给出可操作的阻断原因，不留下半迁移、半物化或半批准状态。
3. 正式计算候选、机器验证和业务批准严格分层。验证通过不得自动产生业务批准，证据补录不得静默改变正式使用状态。
4. 发布与回滚留下不可覆盖的事件链，能复原切换前后版本、操作主体、依据和失败原因。

## 4. 非目标

本期不处理生产认证、网关、JWT、session 或统一身份链。由于仓库当前没有可证明调用方身份的认证层，v1 不把应用内 `user_id` 当成有效签名；业务审批必须引用受控的外部签批、GitHub 受保护环境审批或其他 owner 明确认可的权威载体。

本期也不包含以下工作：

- 不拆微服务，不建设新的通用工作流平台或管理后台。
- 不重构无关数据库 schema、队列、缓存基础设施或全局前端状态。
- 不借发布治理改变正式金融口径；规则变化仍须独立业务决策和黄金样本审批。
- 不一次性迁移所有历史页面、formatter、治理脚本或 excluded surfaces。
- 不承诺跨 PostgreSQL、DuckDB、对象存储和进程内缓存的分布式事务。
- 不自动清洗历史脏数据，不用回滚动作覆盖或删除既有审计记录。

## 5. 用户与职责

| 角色 | 主要职责 |
| --- | --- |
| 发布 owner | 组装发布包、发起验证、执行切换和回滚 |
| 平台/运维 owner | 执行显式迁移、确认目标环境 readiness |
| 金融规则 owner | 确认规则含义、版本、生效日期和差异影响 |
| 数据 owner | 确认来源版本、物化完整性、对账和保留策略 |
| API/前端 owner | 确认契约兼容、精度边界和页面消费一致性 |
| 业务 owner | 审阅结果差异和证据，独立作出批准或驳回 |
| 审计/复核角色 | 查询发布事件、审批依据、回滚记录和例外 |

具体人员及替补人选为 `PENDING`。同一人可以承担多个研发角色，但发布发起人不得自行完成业务批准；审批载体应具备防自审能力。

## 6. 核心产品模型

### 6.1 逻辑 lane 与物理 bundle

`Release Lane` 是最小逻辑治理单元，按可以独立验证、审批和追踪的业务范围划分，例如固定收益分析、正式余额、ADB 契约或某组正式页面。同一 lane 在任一环境只能有一个逻辑 `current`。这个定义不表示 lane 对应的数据库产物能够独立切换或回滚；物理发布边界必须由实际存储隔离能力决定。

当前本地开发证据显示，API、worker 和调度脚本共同使用一个承载多个业务域的 DuckDB 文件。v1 因此把这份共享文件定义为 `duckdb-main` 物理整库 bundle。每个 `duckdb-main` artifact 必须记录冻结时点包含的全部 lane 版本，lane Alias 不得直接充当整库文件指针。在业务表尚未物理拆分或版本化之前，任何涉及 DuckDB 文件的激活都是 whole-bundle 操作，不能表述为固定收益 lane 独立热切换或独立整库回滚。

`Release Bundle` 表示一次系统部署或联合发布，引用一个或多个逻辑 lane candidate、`duckdb-main` 等物理 artifact，并绑定共同的代码、schema 和前端构建。它提供系统级追踪，但不强行把所有逻辑审批合并为一个决定。跨 lane 或共享物理 artifact 的发布默认整体切换；只有兼容性矩阵和物理隔离证据同时证明安全时，才允许单 lane 物理回滚。涉及代码或 DTO 的回滚仍须恢复 Manifest 绑定的后端和前端构建。

### 6.2 Release Manifest

Manifest 是机器可校验的不可变发布清单。至少包含以下字段组：

| 字段组 | 必含内容 |
| --- | --- |
| 标识 | `release_id`、`target_environment`、全部逻辑 lane 与物理 bundle 的 scope binding、`created_at` |
| 构建 | `git_sha`、后端构建标识、前端构建标识、内容摘要 |
| 存储 | PostgreSQL head、DuckDB head、迁移回执、验证时间、read/write 角色 |
| 计算 | module、report date、source/vendor/rule/cache version |
| 产物 | artifact id、artifact kind、位置引用、行数、校验和、build run id；`duckdb-main` 还要列出全部 contained lane versions |
| 契约 | OpenAPI baseline hash、DTO/page contract hash、例外引用 |
| 数值 | numeric policy version、受控页面清单、兼容白名单 |
| 治理 | 必需机器门禁清单、逐门禁验证回执、owner 决定、证据引用、批准内容摘要 |
| 回滚 | previous release、兼容性结论、回滚验证要求 |

Manifest 只保存摘要和引用，不保存生产密钥、客户数据、账户数据或大体量业务明细。每个必需机器门禁都必须有结构化通过状态和独立回执摘要；空回执、漏门禁或缺少摘要均不得进入 `validated`。任何受审批字段发生变化都必须产生新的 candidate 和内容摘要，原审批自动失效。

### 6.3 状态机

| 状态 | 含义 | 允许动作 |
| --- | --- | --- |
| `draft` | 清单尚未完整 | 补字段、取消 |
| `candidate` | 候选产物和字段已冻结 | 执行机器验证 |
| `validated` | 全部机器门禁通过 | 发起业务审批 |
| `approved` | 业务批准与证据已绑定 | 执行受控提升 |
| `current` | 当前正式消费版本 | 监测、发起后继版本或回滚 |
| `deprecated` | 已被替代但仍保留 | 审计、按策略清理 |
| `rejected` | 验证或审批拒绝 | 查看原因、创建新 candidate |
| `rolled_back` | 曾为 current，现已回退 | 审计、问题复盘 |

状态转换必须追加事件，不允许改写历史事件。`candidate`、`validated`、`approved` 和 `rejected` 表示候选生命周期；`current`、`deprecated` 和 `rolled_back` 必须结合目标环境、作用域 Alias 与事件推导，不能作为 Manifest 上可覆盖的全局状态字段。逻辑 lane 与物理 bundle 分别维护作用域明确的 Alias；提升 `current` 使用带 revision 的 compare-and-swap 或等价锁语义，防止两个并发 candidate 同时成为 current。涉及共享 DuckDB 时，一次 promote 必须携带 `duckdb-main` 和全部 contained logical lane 的完整 revision 期望，在同一 PostgreSQL 事务中先校验并更新物理 Alias、再更新全部逻辑 Alias并追加事件；任一步失败全部回滚，不能形成悬空或部分 current。

## 7. 功能需求

### FR-1 统一发布清单与事件账本

系统必须提供 `prepare`、`validate`、`approve-record`、`promote`、`rollback` 和 `show` 等受控动作。命令名称可在实现阶段调整，但状态语义不得变化。共享 DuckDB 的 `promote` 和 `rollback` 只接受完整 Release Bundle 计划，不开放单 scope 切换入口。每个动作必须输出结构化回执和稳定退出码，重复执行应保持幂等；`blocked`、`conflict` 和 `error` 只表示动作结果，不得混入发布状态机。

生产权威建议落在 PostgreSQL：Manifest 保存不可变候选和完整 scope plan，Event 保存追加式状态转换，Alias 以 `target_environment`、`scope_kind` 和 `scope_key` 区分逻辑 lane 与物理 bundle，并保存 current、previous 和 revision。`duckdb-main` 是 v1 必须支持的物理作用域。现有 `GovernanceRepository`、`cache_build_run` 和 `cache_manifest` 继续保存模块物化事实，不重复建设第二套物化账本。新增表及迁移属于受保护边界，实施前必须完成 GitNexus 影响分析和专项评审。

### FR-2 双存储 readiness

开发环境可以沿用显式自动升级策略；非开发环境的 API 和 worker 启动只能通过只读方式校验 PostgreSQL 与 DuckDB head。任一 head 不一致、迁移账本缺失或目标存储不可读，readiness 必须失败，并给出 applied、expected 和显式迁移命令。DuckDB 不能只检查“期望版本是否缺失”，还必须拒绝未登记的额外版本、描述不一致，以及受控或惰性 schema 与声明策略不一致。现有 DuckDB 历史账本没有 checksum 列，v1 必须把“版本/描述精确核对”和“registry source digest / governed catalog fingerprint”分别披露，不能伪称完成了历史迁移 checksum 校验。

迁移只能由发布步骤执行。PostgreSQL 采用 expand/migrate/contract 兼容顺序，破坏性删除不得与首次使用新字段的代码同批发布。数据库 schema 原则上前滚；应用或数据回滚只有在兼容矩阵证明旧版本仍能读取新 schema 时才允许。

`schema current` 的判定必须与部署拓扑一致：单实例维护窗口可以要求目标 release 的 heads 精确匹配；滚动部署则要验证新旧应用共同支持的兼容集合，不能让旧实例在 expand migration 后被无条件误杀。生产拓扑未确认前，v1 不宣称支持无停机滚动迁移。

### FR-3 正式计算候选、提升与回滚

正式物化成功只产生 `candidate artifact`，不自动成为正式 current。每个产物必须绑定 `source_version`、`vendor_version`、`engine_rule_version`、`materialize_rule_version`、`cache_version`、`report_date`、行数、校验和和 build run。

固定收益首个试点采用 `duckdb-main` 影子整库产物，而不是固定收益专属文件。候选从最新冻结的整库静止点复制，只重建固定收益目标切片；除逐报告日验证债券分析和风险张量外，还必须证明全部非目标表没有被意外替换或回退。候选 Manifest 记录整库 checksum、全部 contained lane versions、固定收益差异回执和不可变来源引用。

首次试点只支持单实例、whole-bundle 维护窗口，不支持热替换、滚动发布或 lane 级文件切换。操作顺序固定为：

1. 暂停 keepalive、Windows Scheduler、外部 supervisor、新任务入队及其他写库入口，并等待队列和活动 writer 排空。
2. 停止 worker，再停止 API；确认目标文件没有活动连接，且不存在待处理 WAL。
3. 从最新静止点构建版本化 `duckdb-main` 候选，运行 schema、全库非目标表、固定收益逐日、黄金样本、契约和治理校验。
4. 审批与 Manifest 摘要一致后先追加 activation-intent 事件，把部署配置写成候选文件的绝对路径，并以隔离验收模式重启 API；此时不得把 candidate 对外宣告为正式 `current`。
5. worker 和所有调度入口继续保持停止，只用隔离的只读 API 完成 candidate readiness、页面/API smoke 和观察窗口。验收通过后，使用一次 PostgreSQL 事务对 `duckdb-main` 与全部 contained logical lane Alias 执行 compare-and-swap，并追加 current 事件；失败时保持原 current，恢复原配置并复验。
6. Alias 原子切换及 current readiness 复验通过后才恢复 worker 与调度。由于恢复写入会立即改变活动文件 checksum，这个试点只能证明维护窗口切换机制，不能宣称已经实现持续不可变的发布快照。

长期目标是“单写者工作库 + 不可变只读发布快照”：worker 只写 workspace，发布任务从冻结输入生成并封存 snapshot，API 只读已发布 snapshot。届时 write path 与 read path 必须使用不同配置，所有 scheduler、CLI 和 MCP 入口统一解析写路径，禁止继续硬编码 `data/moss.duckdb`。

回滚必须尊重共享整库边界。在 writer 尚未恢复且没有其他域前进的同一维护窗口内，可以重新激活 previous sealed bundle；一旦其他域已经产生新写入，不得直接指向旧整库文件。此时应以最新整库为底，恢复上一已批准的固定收益切片，生成并校验一个新的 `duckdb-main` rollback bundle，再按同一流程提升。若规则变化同时改变服务或前端契约，还必须恢复 Manifest 对应的兼容构建；只切数据 Alias 不构成完整回滚。

### FR-4 API、DTO 与页面契约门禁

OpenAPI breaking diff 必须相对于受保护基线或目标分支执行，不能通过同一变更静默刷新基线来绕过。新增字段等兼容变化可以正常通过；删除字段、增加必填字段、缩窄类型和改变响应语义等 breaking change，必须采用新版本或具有 owner、原因、到期日和迁移计划的显式例外。

ADB 等受控链路保持严格 response model，不得为了兼容历史脏缓存放宽 `extra="forbid"`。后端 schema、真实服务输出、OpenAPI、前端 DTO 和代表性黄金样本必须在同一个 contract gate 中对齐。

### FR-5 精确数值边界

后端仍是正式金融计算唯一入口。受治理数值使用 `raw_text` 作为无损权威表示，`display` 用于直接展示；前端只有在比较、缩放或可视化确有需要时才使用十进制库解析。JavaScript `number` 只能作为图表坐标或近似排序值，不能参与正式聚合、正式分桶或正式口径重算。

v1 优先治理正式 Phase 2 页面和共享客户端。旧 `DecimalLike`、私有 formatter 或 `Number(raw_text)` 路径进入有 owner、有到期日的兼容清单，禁止新增。简单文本展示无需重复解析；需要十进制运算的路径建议采用 `decimal.js`，依赖引入须单独评审。

### FR-6 审批与证据

机器验证、材料捕获、业务批准、正式使用和页面 closure 必须保持不同状态。审批记录必须绑定 manifest 内容摘要、scope、决定、owner、日期、证据引用和失效条件；任何摘要变化都触发重新审批。

由于认证不在本期范围内，应用不能自行证明审批人的真实身份。v1 只引用 GitHub 受保护环境、受控工单/签批系统或 owner 明确认可的线下签批记录。页面审批脚本继续负责页面证据校验，统一控制面只做注册、汇总和阻断，不自动生成“批准”。

### FR-7 运行时与观测

API、worker 和页面必须能披露当前 `release_id`、逻辑 lane、`duckdb-main` 物理 bundle、规则版本、数据日期和质量状态，但不得把内部工程明细堆到业务首屏。健康检查区分 liveness 与 readiness；schema、current alias、物理路径或正式血缘不一致时 readiness 失败，进程存活状态仍可供运维诊断。

## 8. 非功能与控制要求

- **Fail-closed：** 证据缺失、版本不一致、读取失败或例外过期时不得猜测放行。
- **不可变与可追溯：** Manifest 和 Event 追加保存；审计记录不因回滚删除。
- **物理完整性：** sealed artifact 的 checksum 只对不可再写入的文件成立；共享可写文件不得伪装成持续不可变的发布 snapshot。
- **幂等与并发安全：** 重试不得重复提升；并发提升只能有一个成功。
- **最小权限：** 运行时只读查询发布状态；迁移、提升和回滚使用独立运维身份。认证能力完成前，不宣称应用已满足该项的身份真实性要求。
- **可重放：** 当前正式版本及上一已批准版本至少能够从保留的代码、来源快照、规则和产物恢复。更长期限为 `PENDING`。
- **兼容优先：** schema 和 API 默认向后兼容；破坏性变化必须显式版本化。
- **敏感信息隔离：** 发布清单仅记录摘要和受控引用，不复制内部业务明细到 GitHub 日志或外部系统。
- **不替代业务判断：** 自动门禁只能证明契约和证据完整，不能自行裁定金融口径正确。

## 9. 验收标准

满足以下条件，v1 才能视为完成：

1. 任一正式发布可用单个 `release_id` 查询全部必填字段和状态事件；缺少任一必填字段时不能进入 `candidate`。
2. 非开发环境 PostgreSQL 或 DuckDB 任一 schema 落后、出现未知额外迁移、checksum/描述不一致或受控/惰性 schema 缺口时，API/worker readiness 失败且没有写操作；声明策略完全一致时正常通过。
3. 候选物化在构建、写入、校验或缓存失效阶段失败，上一逻辑 current、`duckdb-main` 物理 Alias 和正式数据均保持不变。
4. 同一逻辑 lane 或物理 bundle 无法产生两个 current；并发 promote 只有一个成功，失败方得到明确 revision conflict。
5. `rule_version`、`source_version`、`cache_version` 或 artifact checksum 与 Manifest 不一致时，正式读路径拒绝将结果标记为可用。
6. 未批准的 OpenAPI breaking change 在 PR 或发布验证阶段失败；基线刷新与例外批准有独立记录。
7. 正式数值用例覆盖 `9007199254740993.00005`、超长小数、尾零、负值、零、`null`、空串、非法 token、科学计数法和非有限值，并有明确接受或拒绝语义。
8. 业务证据完整但批准缺失时，状态最多到 `validated`；审批后 Manifest 任一受控字段变化，原批准自动失效。
9. 至少完成一次 `approved -> current -> rolled_back` 演练，审计查询可以还原切换前的逻辑 lane 与 `duckdb-main` current、回滚原因和回滚后 current。
10. 固定收益试点完成全报告日影子重物化和逐日对账，并证明候选整库的非目标表没有意外变化；实际报告日数量、版本号及差异阈值以执行时重新盘点和 owner 决定为准。
11. 演练能够区分“同一停写窗口内回切 previous sealed bundle”和“其他域前进后构建新 rollback bundle”，后者不得直接激活旧整库文件。
12. 涉及后端或前端构建变化的演练能够恢复上一 Bundle 绑定的兼容构建，不能只证明数据 Alias 可回切。

## 10. 一票否决条件

出现以下任一情况，不得提升为 `current`：

- PostgreSQL 或 DuckDB readiness 未通过，或只用隔离测试库结果代替目标环境检查。
- DuckDB 迁移账本存在未解释的额外版本、受控/惰性 schema 缺口，或 sealed checksum 对应的文件仍会被 worker 写入。
- Manifest、artifact、规则、来源、契约或前端构建摘要不一致。
- 正式金融规则仍有影响结论的 `PENDING`，或黄金样本变化未经规则 owner 审阅。
- breaking change 通过同 PR 静默刷新基线绕过。
- 受治理数值丢失无损表示，或前端重新计算正式指标。
- 业务批准缺少权威载体，或批准内容摘要与 candidate 不一致。
- 发布必须依靠生产启动自动迁移、自动重物化或修改历史审计记录才能成功。
- 没有可验证的上一数据产物、兼容应用/前端构建、回滚目标或兼容性结论。
- 其他业务域已经前进，却仍计划直接把共享 DuckDB 指向旧整库文件。

## 11. 目标指标

以下均为建设目标，不代表当前达成情况：

- Phase 2 正式发布 100% 生成有效 Manifest 和 release event。
- 非开发环境启动 100% 同时校验 PostgreSQL 与 DuckDB schema current。
- 正式计算规则变更 100% 绑定规则版本、差异报告、黄金样本和 owner 决定。
- 受控 API breaking change 100% 在合并或发布前被阻断或取得显式例外。
- 新增正式前端数值路径 100% 使用受控 Numeric/Decimal 边界。
- 每次 current 切换 100% 生成 promotion receipt 和可定位的 previous release。
- 每个正式 lane 至少保留一个已验证的逻辑回滚目标；`duckdb-main` 同时保留可恢复的 sealed bundle 或可重建切片，回滚恢复时间目标为 `PENDING`。

### 实施状态与边界

截至 2026-09-01，本 PRD 对应的控制面能力已经建成，但正式推广未完成。WP1、WP2、WP5、WP6 已形成代码能力和隔离测试。WP1 的 PostgreSQL 真并发入口已在工作区内新建的临时 PostgreSQL 17 实例完成实测：实例使用随机隔离数据目录和端口，专用 `moss_release_control_test` 数据库先迁移到 Alembic head，再运行两项 whole-bundle compare-and-swap 竞态测试，结果为 2 项通过、0 项跳过；测试后实例正常停止，临时目录已送入回收站。该证据证明本机 PostgreSQL 事务与 revision CAS 能稳定收敛，仍不是生产推广、目标环境回执或 `current` 开放授权。WP3 只完成 OpenAPI/release-eligible gate 与 `calibration` 必填契约代码，captured ADB golden 仍待 owner 决定并重新捕获；该失败已定位为历史样本只保存选定字段，缺少一直由 producer 返回且模型要求的 `result_meta.trace_id` 与顶层 `calibration`，当前完整候选相对样本有 24 个新增路径、0 个删除和 0 个既有值变化，不能只手填两个字段代替受控重捕获。WP4 已把 engine rule、Bond/Risk materialize descriptor、cache identity 和动态 source/observed vendor/upstream/liability lineage 分层建模，并用同一规则在 task、candidate 与 receipt 三层精确闭合 Risk 复合来源摘要。single-report-date harness 使用 `moss.bond-risk-shadow-candidate-receipt/v1` 封存完整版本片段，多日期批次入口使用 `moss.bond-risk-shadow-batch-receipt/v1`，从同一冻结源为显式日期清单分别创建独立 candidate 并聚合不可放行的证据。Bond/Risk 读端的 configured-current 身份已接同一版本真源，历史 Golden 证据继续 pin 在历史版本；Bond 与 Risk 的 freshness 行为仍不一致，不能宣称读链已完成统一政策。两类回执都固定披露 `financial_golden_validated=false`、`wp7_eligible=false` 和 `release_gate_eligible=false`。这只证明版本披露、逐日隔离和失败聚合，不证明 canonical manifest 已单独记录 engine rule，也不证明一个 candidate 已完成全历史 materialization；当前负收益率、闰日现金流版本提升、Bond/Risk freshness 政策及 financial golden 仍待 owner 决定。

WP5 已完成现金流、债券仪表盘、Risk Home、PnL 量价闭合、Risk Tensor 独立页、Decision Items 和 Balance Analysis 展示层七个前端切片。现金流页面的月度符号、极值、1bp 敏感度语义及风险读数亿元展示会优先消费 `raw_text`，同时保留 raw-only 旧响应兼容和 `number | null` 图表边界；后端通过 shared `numeric_json` 的默认关闭 opt-in 把原始 `Decimal` 保真送入本服务的 Numeric 构造，顶层 KPI、质量披露金额、月度 bucket 和到期资产列表都会把 `raw_text` 带入 API 响应对象，且不改变既有公式、`raw` 或 `display`。冻结的 `GS-CASHFLOW-PROJECTION-A` 会因此新增 111 个 `raw_text` 字段，Cashflow Golden owner 审阅和重新批准前，门禁继续保持红色。

债券仪表盘后端原本已输出 Q8 `raw_text`，本次把信用债比例阈值、环比百分比/基点/亿元显示、资产结构占比和尾差迁到 Decimal-first 页面逻辑，并保留纯 raw 旧响应的既有行为；卡片/tooltip 现在优先 `raw_text`，图表坐标仍停在 `number` 边界，raw-only fallback 兼容，mixed backend/fallback 占比按 fallback 子集市值分摊，40/40 反例已通过，分桶、排序和正式计算都没有改。Risk Home adapter 进一步把正式摘要、阈值、峰值和文本缩放与 chart-only number 分流；PnL 量价 view model 则让闭合、覆盖率和 1 万元容差在 exact/mixed 输入时使用 Decimal，并让组件直接复用判定结果。TPL 市场端点的原 float/correlation/interpretation/quality/raw/display 主链保持不变，仅在全 exact 时追加 `raw_text` sidecar；mixed/null/invalid/nonfinite fail-closed，10001 条 `DECIMAL(24,8)` 极值样本已覆盖，前端 card/tooltip 与 ProductCategory 字符串 exact，series 和 legacy number 保持旧行为。Risk Tensor 独立页的 30 日流动性结论、主风险桶绝对值排序、投影质量、久期排除、scenario tone 和正式万元/亿元金额展示都已切到 Decimal/raw fallback，KRD 雷达与图表 magnitudes 仍保持 number 边界。Decision Items 只对后端 reason 中的 plain-decimal 万元片段做 Decimal 缩放；没有虚构 Numeric `raw_text`，队列排序仍保持状态、严重度、标题和 decision key 的原契约。Balance Analysis 的真实契约是 `DecimalLike` 精确字符串，不是 Numeric 对象；本轮只把 overview/grid/workbook、元或万元到亿元、后端 share 文本等直接展示路径改为 Decimal ROUND_HALF_UP，并保留 number、科学计数法和非法值的旧兼容行为。页面前端拼接 AC/OCI/TPL bridge、计算 residual/ratio、套用 1 亿元或 0.05% 阈值、部分求和及绝对值 Top-N 排序均未获口径 owner 批准，继续保持 owner-blocked。

Campisi 审计进一步证明，纯前端迁移无法恢复源精度。formal-bridge 主路径此前在 PnL Bridge Numeric 构造时把 Decimal 降为兼容 float，model fallback 也会在持仓合并阶段降格；因此本轮先让 PnL Bridge 在既有可选 `raw_text` 字段中增量保留源 Decimal，并保持 `raw`、`display`、顺序与 Campisi 当前只读 `raw` 的行为不变。另有一项不改金额的质量中继修复：formal bridge 只有在期初、期末应计利息都存在时才标记该口径可用；期末缺失只让 availability/diagnostic 降级，totals、selection 和 formal closure 保持不变。Campisi 的金额、排序、占比、阈值和 rule/cache version 均未修改。四效应、六效应、到期桶、决策级面板及 Dashboard Home 消费适配器已进入受控 registry，详细 owner 决策包见 `docs/pnl/campisi-exact-numeric-owner-decision.md`。

此前十八个组合前端测试文件共 430 项通过；本轮 Balance Analysis 影响面另外以 8 个文件、145 项测试覆盖本页及 Balance Movement、Market Finance、Operations 三条共享消费链，定向 ESLint 与锁定版本 TypeScript 检查均为绿色。四项 Chromium 精度证据分别验证债券仪表盘、现金流、Risk Tensor 的 `raw_text` 行为，以及 Balance Analysis 超过 `2^53` 的 plain-decimal 元/万元金额和高精度 share 在概览卡、驾驶舱 KPI、workbook 评级金额和风险文案中保持精确展示；Decision Items 路由 smoke 另有 1 项通过。专用 exact-numeric registry 当前覆盖 8 个页面和 27 条生产路径；AST 守卫新增 `frontend/src/utils/format.ts` 和 `dashboardHome` 两个视图，`controlled_paths` 由 24 增至 27、`pending_migrations` 由 11 增至 14，说明新增受控面而不是回退；TPL 仍有 `DecimalLike` count4 和 literal `/1e8` count2，因此 policy 继续固定 `release_eligible=false`；Manifest 的 numeric policy digest 已绑定 policy version、受控页面/路径和完整 registry SHA。Balance Analysis 正式对账/排序、Campisi 无损 producer 与正式判断、工作台已登记但未迁移的首页兼容路径和其余页面仍待迁移，部署状态和全站 exact-numeric 也均未完成。

WP7 已新增独立的非生产演练器 `scripts/wp7_release_rehearsal.py`，其 9 项测试也已纳入默认后端发布套件。它只在新建绝对路径下生成合成 DuckDB 和临时 SQLite 台账，完成基线 whole-bundle promote、候选 promote、checksum 篡改拒绝、不完整 scope 拒绝、`sealed_bundle_reactivate` 回切和幂等重放，并对回执与固定 artifact 路径重新验签。隔离测试与实际本地演练均证明三条 scope 可以从 revision 2 整体回到 revision 3，负向探针不会改变临时 Alias/Event；所有回执固定披露 `rehearsal_only=true`、`synthetic_evidence=true`、`structure_only=true`、`integrity_only=true`、`authenticity_attested=false`、`release_gate_eligible=false`、`wp7_production_eligible=false` 和 `production_writes=false`。纳入默认套件只让该机械闭环成为持续回归证据，仍没有外部权威签名、生产试点、真实 Alias 切换、真实 writer 停写或恢复。

同日补上了 `scripts/wp7_fixed_income_pilot_preflight.py` 这一条只读试点预检入口。它只消费结构化交接包 JSON，不连接生产、不读取正式 DuckDB，也不接受 Markdown 模板冒充授权；任何 owner、路径、停写证明、备份 checksum、五态审批、GitHub/authority 证据、维护/观察窗口、RTO/RPO 或 rollback branch 字段仍为 `PENDING`、占位符、缺失或格式非法时，都固定返回 `blocked`。即使所有结构字段都填齐，回执状态最多也只是 `awaiting_owner_execution`，并继续强制 `release_eligible=false`、`authorizes_pilot=false` 与 `production_writes=false`。对应回归已纳入默认后端发布套件，持续守住“结构完整不等于生产授权”的边界。

同日完成最新一轮 `backend_release_suite.py --mcp-profile fast`，结果为 751 项通过、10 项失败、2 项按 profile 排除。前端守卫、本轮 WP6 审计回执、WP7 合成演练和只读试点预检均已通过；剩余失败全部是契约或黄金证据阻断：1 项 ADB 旧样本不是完整响应，9 项黄金样本分别涉及普通十进制 `raw_text`、固收规则版本、PnL v4 血缘、Decimal 精确闭合及股票宏观证据术语。其中 `raw_text` 科学计数法缺陷已经修复并通过跨端回归；其他样本不得在 owner 确认前自动重捕获。由于这些门仍为红色，当前工作树不是发布候选。

剩余 9 项黄金阻断已由固收、PnL 和股票宏观三个只读专项复核，并由 `scripts/release_control_golden_blocker_review.py` 汇总。该工具只消费精确节点运行产生的 JUnit XML，输出测试状态、断言路径、规范原因码、owner 路由、成对处理关系及四件套 SHA-256；它不复制失败中的实际业务值，不运行测试，也不写黄金样本、治理记录或生产状态。即使所有节点以后转绿，回执仍保持 `release_eligible=false`，状态只能进入 `awaiting_owner_decisions`，不能由机器生成审批。对应的 7 项安全与契约测试已纳入默认 fast backend release suite，持续检查缺失/重复节点、外部路径脱敏、安全输出根、独占写入、审批隔离及“全绿仍不可自动放行”。

| 待决事项 | 状态 |
| --- | --- |
| 16 个 authority/scope mapping | PENDING |
| 生产 verifier / topology / paths / RTO / RPO / owner | PENDING |
| 全历史 financial golden | PENDING |
| 10 项 captured contract/golden 阻断的 owner 决策与重捕获 | PENDING |
| GitHub 平台 required settings（required checks、ruleset、environment reviewers、attestation） | PENDING |

这些项未闭合前，任何“已上线”“已完成治理闭环”或“已具备正式推广授权”的表述都不成立；现阶段只能写“控制面能力已建、正式推广未完成”。

## 12. 待 owner 决策

| 决策 | 当前推荐或结论 | 状态与最晚确认点 |
| --- | --- | --- |
| 首批逻辑 release lane | `bond-analytics-risk-tensor` | `PENDING OWNER DECISION`；WP4 开工前 |
| 首次空环境受控 scope 清单 | 由 owner 冻结 `duckdb-main` 及全部受控逻辑 lane；历史 Alias 只可作为非空环境的闭包基线 | `PENDING OWNER DECISION`；首次 bootstrap promote 前 |
| DuckDB 物理发布范围 | `duckdb-main` whole bundle；lane Alias 不直接指向整库文件 | `WP0 DESIGN CONCLUSION`；不构成生产授权 |
| 首次物理切换模式 | 单实例维护窗口、绝对版本路径、进程重启；不支持热替换或滚动 | `WP0 DESIGN CONCLUSION`；生产拓扑确认后才能执行 |
| 长期 DuckDB 目标 | worker 单写 workspace，API 只读 immutable published snapshot | `PENDING OWNER DECISION`；持续生产设计前 |
| schema 基线处置 | 解释/登记本地 v47、v48，确定受控 v46 与惰性 schema 的顺序 | `PENDING OWNER DECISION`；WP2/WP4 前 |
| 固收规则与重物化范围 | 冻结 engine/materialize/risk 版本、负收益率/票息语义、报告日范围和 golden 差异阈值 | `PENDING OWNER DECISION`；WP4 前 |
| ADB 月度契约 | 默认保持顶层 `calibration` 与 `result_meta.trace_id` 必填并重新捕获确定性样本 | `PENDING API/BUSINESS OWNER DECISION`；WP3 前 |
| 固收闰日现金流修正 | 保留 ACT/365 整期归并修正，提升 Bond Analytics 与 Risk Tensor 规则/cache 版本后再审阅 `GS-RISK-WARN-B` | `PENDING FINANCE/RISK OWNER DECISION`；任何 golden 重捕获前 |
| PnL v4 黄金证据 | DATA、OVERVIEW 成对重捕获；已批准的 BUSINESS-INSIGHTS 必须重新审阅上游 v4 血缘；Bridge 与归因样本仍保持待批准 | `PENDING PNL/BUSINESS OWNER DECISION`；发布套件转绿前 |
| 股票宏观缺失证据术语 | 明确主序列为社融存量同比、fallback 为 M2 同比，并冻结“相邻月同比变化代理”的最终表述 | `PENDING PRODUCT/BUSINESS OWNER DECISION`；`GS-STOCK-ANALYSIS-OBS-A` 重捕获前 |
| exact-numeric 首批页面 | 现金流与 PnL Bridge 本地后端 wire、现金流/债券判断、Risk Home adapter、PnL 量价闭合、Risk Tensor 判断与金额缩放、Decision Items 金额文本、Balance Analysis 直接字符串展示，以及 registry/AST guard/Manifest digest 已有受控证据 | `PENDING FRONTEND/FINANCE OWNER DECISION`；Balance Analysis 正式对账/排序、Cashflow/PnL Golden 重捕获、Campisi producer/规则版本、14 项 pending 兼容基线与其余页面迁移前 |
| 审批权威载体 | GitHub 受保护环境或现有正式签批系统 | `PENDING OWNER DECISION`；WP6 前 |
| 历史保留与回滚目标 | current 与上一 approved 逻辑切片必须可恢复；整库回滚遵守共享 bundle 规则 | `PENDING OWNER DECISION`；WP7 前 |
| 生产拓扑、RTO/RPO、门禁时限 | 不从本地开发环境推断 | `PENDING`；生产演练前 |

这些决策影响实现细节，但不改变统一 Manifest、候选不覆盖 current、验证与审批分离三项基本原则。

## 13. 外部参考

本方案借鉴的是机制，不引入对应平台：

- Apache Airflow 将显式数据库迁移与启动前 migration check 分离：[Setting up the database](https://airflow.apache.org/docs/apache-airflow/stable/installation/setting-up-the-database.html)。
- Flyway 用已执行迁移、可用迁移和 checksum 做 fail-fast 校验：[Validate](https://documentation.red-gate.com/flyway/reference/commands/validate)。
- dbt 把公共数据模型作为带契约和并存版本的 API：[Model contracts](https://docs.getdbt.com/docs/mesh/govern/model-contracts)、[Model versions](https://docs.getdbt.com/docs/mesh/govern/model-versions)。
- OpenLineage 用 Run、Job、Dataset 和 facets 记录统一血缘事件：[OpenLineage specification](https://github.com/OpenLineage/OpenLineage/blob/main/spec/OpenLineage.md)。
- Apache Iceberg 和 MLflow 分别展示不可变 snapshot、版本与 alias 切换思路：[Iceberg format](https://github.com/apache/iceberg/blob/main/format/spec.md)、[MLflow registry workflow](https://github.com/mlflow/mlflow/blob/master/docs/docs/classic-ml/model-registry/workflow.mdx)。
- oasdiff 在 CI 中区分 breaking、warning 和兼容变更：[Breaking changes](https://github.com/oasdiff/oasdiff/blob/main/docs/BREAKING-CHANGES.md)。
- decimal.js 建议从字符串构造高精度十进制，避免先经过二进制浮点：[decimal.js](https://github.com/MikeMcl/decimal.js)。
- GitHub Environments 支持 required reviewers 和 deployment protection rules：[Deployments and environments](https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments)。
