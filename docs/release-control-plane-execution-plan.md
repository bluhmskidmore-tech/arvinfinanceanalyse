# MOSS 统一发布控制面执行方案

- 状态：Active，按已批准 PRD 实施；owner 指派待补齐
- 日期：2026-08-31
- 上位需求：[PRD：MOSS 统一发布控制面](prd-release-control-plane.md)
- 执行边界：repo-wide Phase 2 正式计算主链
- 计划性质：实施参考，不单独构成生产变更或业务批准授权

## 1. 执行结论

建议分七个可独立评审的代码 PR 和一次受控试点完成。第一个 PR 只建立 Manifest、事件和分作用域 Alias 的最小骨架；此后数据库 readiness、API 契约和前端精度可以按逻辑 lane 推进，固定收益候选物化在基础骨架稳定后实施，最后再接审批与 CI。共享 DuckDB 的物理发布对象统一为 `duckdb-main` whole bundle，不能把固定收益 lane 直接等同为可独立切换或回滚的整库文件。

首次试点采用单实例 whole-bundle 维护窗口，且不与代码 PR 混在一起。它必须另有停写、队列排空、迁移、备份、审批、绝对路径切换、进程重启和回滚回执；本计划不授权任何生产执行。长期目标是 worker 单写 workspace、API 只读 immutable published snapshot，首次试点不虚构当前系统已经具备这种隔离能力。

整个计划不新建独立服务，不开放新的公共管理 API，也不把控制面放进业务查询热路径。API 和 worker 启动时只读取 schema/current 状态；正式计算继续位于 `core_finance`，DuckDB 写入继续只走 `tasks`。

这份执行方案只对应 PRD 里的五个非 auth 课题，顺序是先把控制面骨架和门禁做稳，再把正式计算、前端精度和审批证据接上去。

| 课题 | 主要工作包 | 结果 |
| --- | --- | --- |
| 数据库就绪 | WP2 | 启动时只读校验 PostgreSQL / DuckDB current，迁移和 readiness 分离 |
| 正式计算版本 | WP1、WP4、WP7 | Manifest、alias、candidate、promote、rollback 和影子试点形成闭环 |
| API 与页面契约 | WP3、WP6 | OpenAPI / ADB / DTO / approval receipt 统一门禁 |
| 前端精度边界 | WP5 | `raw_text`、Decimal 和 `number` 的边界收口 |
| 治理与审批证据 | WP6、WP7 | 机器验证、业务批准和正式使用分层，证据可追溯 |

## 2. 开工前条件

以下事项未完成时，只能推进文档、测试骨架和不涉及物理切换的基础能力：

1. owner 确认 [PRD 待决策项](prd-release-control-plane.md#12-待-owner-决策)，至少明确首批逻辑 lane、生产部署拓扑、审批权威载体、schema 基线处置和固定收益规则版本；`duckdb-main` whole-bundle 是当前共享文件下的设计边界，不替代生产授权。
2. 以 2026-08-31 WP0 本地盘点作为当前候选基线，逐项解决下文阻断；2026-06-10 的审计文件只作为历史比较基线。
3. 冻结一个可复现的 Git 基线，记录当前 `HEAD`、工作树既有改动和首批受控文件。不得把其他在途改动混入发布控制面 PR。
4. 核对 `.gitnexus/meta.json` 的 `lastCommit` 与 `git rev-parse HEAD`。索引过期时先执行 `npx gitnexus analyze --skip-agents-md`；修改函数、类或方法前完成 upstream impact 分析。
5. 指定发布 owner、金融规则 owner、数据 owner、业务审批人和独立复核人。未指派的角色保留为 `PENDING`，不得用执行方代签。

## 3. 交付结构与依赖

| 工作包 | 主要交付 | 前置依赖 | 可并行性 |
| --- | --- | --- | --- |
| WP0 | 决策冻结、基线和 ADR | 无 | 先行 |
| WP1 | Manifest、Event、Alias 基础骨架 | WP0 | 先行 |
| WP2 | PostgreSQL/DuckDB readiness | WP1 | 可与 WP3 并行 |
| WP3 | API、ADB、页面契约门 | WP1 | 可与 WP2 并行 |
| WP4 | 固收 candidate 与 `duckdb-main` handoff | WP1、WP2 | 与 WP5 部分并行 |
| WP5 | 前端 exact-numeric 收口 | WP1、WP3 | 与 WP4 部分并行 |
| WP6 | 审批聚合、CI 与发布保护 | WP2—WP5 | 集成阶段 |
| WP7 | 影子重建、试点切换和回滚演练 | WP6 | 最后执行 |

WP2—WP5 每个工作包只拥有自己的文件 lane。共享文件如 `scripts/backend_release_suite.py`、`.github/workflows/ci.yml` 和 `frontend/src/utils/format.ts` 必须指定单一 owner，避免并行覆盖。

## 4. 工作包明细

### WP0：决策冻结与基线

本工作包不修改运行代码。目标是消除会改变实现路线的歧义，并把当前版本、契约、审批和生产拓扑固定为可复核输入。

截至 2026-08-31，证据采集已经完成，但 WP0 尚未达到决策冻结。以下内容只代表本地工作区或代码来源，不代表生产状态：

| 状态 | 基线结论 | 后续动作或阻断 |
| --- | --- | --- |
| `VERIFIED LOCAL` | 一个约 3.04 GB、至少 74 张跨域表的 DuckDB 文件由 API、worker 和调度入口共用或硬编码引用 | 物理范围冻结为 `duckdb-main`；生产拓扑和调度 owner 仍为 `PENDING` |
| `VERIFIED SOURCE` | PostgreSQL Alembic script head 为 `c2e94f6a8b10`；实现从 revision graph 动态读取全部 heads | 生产 applied heads 未核对，阻断 live readiness 与 WP7 |
| `VERIFIED LOCAL` | 普通 DuckDB 迁移期望 v1—v45；受控 v46 未应用；本地账本存在未登记 v47、v48 | owner 必须决定 v46、v47/v48 与惰性 schema 的治理顺序，阻断 WP2/WP4 |
| `VERIFIED LOCAL` | current 断言只检查缺失的期望版本，允许未知额外版本，且未覆盖全部惰性 ensure | WP2 补 unknown-extra、描述/checksum 和惰性 schema 校验 |
| `VERIFIED LOCAL` | 固收 engine/materialize/risk 版本分层且有重复定义；风险事实混有 v5/v6，修复记录、质量字段和当前物化存在漂移 | 规则 owner 冻结版本、负收益率/票息语义、历史范围和 golden 阈值，阻断 WP4/WP7 |
| `VERIFIED LOCAL` | OpenAPI default/full 快照 stale、当前 diff 无 breaking；ADB response preservation 有 1 个月度样本缺少 `calibration` 和 `result_meta.trace_id` | 先单独落地可信基线并解决 producer/sample 契约，阻断 WP3 完成 |
| `VERIFIED LOCAL` | `raw_text` 仍被 `Number(raw_text)` 有损转换；现有 Numeric 测试接受该行为 | WP5 必须增加精度守卫和真实 exact-numeric 证明 |
| `VERIFIED LOCAL` | 8 个页面 checker 合计 103 项待办，8 项计算决定全部 pending；严格审批命令尚未接入 promote | 结构门可进 PR，真实批准只阻断对应 promote，阻断 WP6/WP7 完成 |
| `INFERENCE` | 共享单文件、跨域表和共同写路径使 lane 级整库切换无法隔离其他域 | `duckdb-main` whole bundle 是当前安全物理边界；这是设计推论，不是生产状态或授权 |
| `PENDING` | 生产副本、挂载、队列排空命令、RTO/RPO、审批权威载体、GitHub required checks | 不从本地开发环境推断，生产试点前必须补齐 |
| `PENDING` | 首次空环境没有历史 Alias 可证明完整受控 scope 集合 | owner 必须在 bootstrap promote 前冻结 `duckdb-main` 与全部逻辑 lane 清单；后续环境才可用现有 Alias 集合作为闭包基线 |

WP0 还要形成一份部署 ADR，把以下结论冻结为提案：逻辑 lane 与物理 bundle 分离；`duckdb-main` 是当前唯一 DuckDB 物理切换范围；首次试点只支持单实例维护窗口；热替换和滚动迁移不在 v1 试点范围；长期采用单写者 workspace 与不可变只读 snapshot。

退出标准是影响 WP1 数据模型的作用域定义已经明确，影响 WP2/WP4/WP7 的每项决定都有 owner、日期和结论。仍为 `PENDING` 的事项必须标明阻断工作包；不得把“证据已采集”写成“owner 已批准”。

### WP1：发布对象与最小控制面

目标是建立不可变 Manifest、追加式 Event，以及逻辑 lane 与物理 bundle 各自唯一的作用域 Alias，不接业务页面，不改变正式读结果。

建议新增或调整的文件：

- `backend/app/schemas/release_control.py`
- `backend/app/models/release_control.py`
- `backend/app/repositories/release_control_repo.py`
- `backend/app/governance/release_control.py`
- `backend/alembic/versions/<revision>_add_release_control_tables.py`
- `scripts/release_control.py`
- `tests/test_release_control_schema.py`
- `tests/test_release_control_repo.py`
- `tests/test_release_control_state_machine.py`
- `tests/test_release_control_cli.py`

建议的 PostgreSQL 数据模型为三张小表：`release_manifest` 保存不可变 payload 和内容摘要；`release_event` 保存验证、批准、提升、驳回和回滚事件；`release_alias` 用 `scope_kind`、`scope_key` 保存逻辑 lane 或物理 bundle 的 current/previous release 和 revision。Manifest 不复制 `cache_build_run`、`cache_manifest` 的事实，只引用其 run id、版本和校验摘要；`duckdb-main` artifact 另需记录整库 checksum 和全部 contained lane versions。

关键实现要求：

- `release_id`、lane 和内容摘要唯一；candidate 冻结后不得原地修改。
- Manifest 必须冻结非空且唯一的 `required_validation_gates`；每个门禁只有在结构化通过状态和 64 位回执摘要同时存在时才算完成。
- Event 只追加；批准事件必须绑定 Manifest 摘要。
- 逻辑 lane Alias 与 `duckdb-main` 物理 Alias 分开校验；lane Alias 不得直接保存整库文件路径。
- Alias 提升使用数据库事务和 revision compare-and-swap；涉及共享 DuckDB 时，`promote`/`rollback` 必须接收包含 `duckdb-main` 与全部 contained logical lane 的完整 scope plan，在同一事务内更新全部 Alias 并追加事件，任一步失败都不得留下部分 current。
- `promote` 重试幂等；两个并发提升只能有一个成功。
- 非空环境的 promote/rollback 还必须覆盖目标环境当前全部受控 Alias；首次空环境必须引用 owner 冻结的 bootstrap scope 清单，不能把空 Alias 集误当成系统权威目录。
- `blocked`、`conflict` 和 `error` 只属于动作回执；Manifest/事件状态仍限定为已定义的发布生命周期。
- v1 仅提供 CLI/内部 Python 接口，不新增公共 HTTP 管理路由。

目标测试：

```powershell
.\.venv\Scripts\python.exe -m pytest -q `
  tests/test_release_control_schema.py `
  tests/test_release_control_repo.py `
  tests/test_release_control_state_machine.py `
  tests/test_release_control_cli.py
```

退出标准是状态机、摘要失效、并发提升、幂等重试和完整审计链全部由自动测试证明。该 PR 不启用生产 `current` 读取。

截至 2026-08-31，WP1 的 PostgreSQL 真并发入口已经实测通过。验证在工作区内新建的临时 PostgreSQL 17 实例上进行，使用随机隔离数据目录和端口，只创建专用 `moss_release_control_test` 数据库；Alembic 全量迁移到 head 后，两项 whole-bundle revision compare-and-swap 测试均通过且没有 skip。实例随后正常停止，临时目录已送入回收站。该结果补齐本机真实事务竞态证据，但不代表生产推广、目标环境切换或 `current` 已开放。

### WP2：双存储 readiness

目标是把“启动时迁移”和“启动时 readiness”分开，补齐非开发环境 PostgreSQL current 断言，同时收紧 DuckDB 只读校验。现有业务写路径中的 runtime lazy DDL 退役不在本工作包内；它跨越多个正式写流程，须作为独立 HIGH 风险后续逐 lane 迁移，不能把启动链路收口表述成全系统已经没有运行期 DDL。

主要改动：

- 在 `backend/app/postgres_migrations.py` 增加 `assert_postgres_schema_current()`，读取数据库当前 heads 与 Alembic script heads；支持多 head 集合，不把单个字符串写死。单实例维护窗口可以要求目标 heads 精确匹配；如 owner 选择滚动部署，必须另行实现并测试 ancestor/compatibility policy，不能直接复用精确相等判断。
- 在 `backend/app/storage_migration_flags.py` 拆分“跳过自动迁移”和“跳过 readiness”语义。测试环境可以显式跳过目标存储检查，但 `MOSS_SKIP_POSTGRES_MIGRATIONS` 不得连带关闭 DuckDB 校验。
- 在 `backend/app/storage_bootstrap.py` 的非开发分支依次执行 PostgreSQL 和 DuckDB 只读断言。DuckDB 断言除 missing expected 外，还要验证 unknown extra、迁移描述、受控 cohort 和登记的惰性 schema；历史账本无 checksum 列，改用单独披露的 registry source digest 与 governed catalog fingerprint，不得伪称历史 checksum 已验证。本地 v46/v47/v48 未解决前不能生成 current receipt。
- worker 的“跳过自动迁移”不能连带跳过独立 readiness；API 健康通过也不能替代 worker 对目标存储的只读断言。
- 评估 `health` 端点是否应分离 liveness/readiness；只在现有健康检查契约允许时调整，不扩展无关运维框架。
- 让 release validate 记录目标环境 schema heads 和检查回执，隔离 fixture suite 不能替代该回执。

主要测试文件：

- `tests/test_storage_bootstrap.py`
- `tests/test_duckdb_schema_bootstrap.py`
- `tests/test_alembic_migrations.py`
- `tests/test_health_endpoints.py`（仅在 readiness 契约变化时）
- 新增 `tests/test_postgres_schema_bootstrap.py`

目标测试：

```powershell
.\.venv\Scripts\python.exe -m pytest -q `
  tests/test_storage_bootstrap.py `
  tests/test_duckdb_schema_bootstrap.py `
  tests/test_postgres_schema_bootstrap.py `
  tests/test_alembic_migrations.py
```

退出标准是 stale、missing、multiple-head mismatch 和数据库不可达均能稳定 fail-closed；schema current 时检查不产生 DDL/DML。显式迁移仍由 `backend/scripts/migrate_storage.py` 负责。

截至 2026-08-31，WP2 代码能力已经落地：PostgreSQL 使用动态 multi-head 精确集合比较；DuckDB 对历史版本/描述、声明的惰性 schema、ledger-neutral 列及受治理对象内部额外列/索引 fail-closed；显式迁移命令会在普通迁移后以单事务物化声明式 readiness DDL，非开发启动仍只读。该结论来自隔离测试，不是生产环境 current 回执；本地 v47/v48、受控 v46 的正式期望以及 runtime lazy DDL 退役仍保持 `PENDING`。

### WP3：API、ADB 与页面契约门

目标是把现有 OpenAPI 基线检查、严格 response model、前端 DTO 和代表性样本汇总为 Manifest contract receipt。

主要改动：

- 保留 `scripts/api_contract_check.py` 为 OpenAPI 基线唯一权威，增加或复用 JSON 输出供 Manifest 引用。
- 首次可信 OpenAPI snapshot 单独落到受保护主分支；在主分支尚无旧 baseline 时，明确标记 bootstrap，不把同一 PR 新建 baseline 当成历史比较证据。
- CI 必须对 PR base ref 执行 `baseline-check --baseline-ref origin/<base>`；不允许同 PR 更新 snapshot 后只和新 snapshot 比较。
- 核对 `backend/app/schemas/adb_analysis.py` 与 `backend/app/services/adb_analysis_service.py` 的真实输出。当前月度黄金样本缺少严格信封必填的顶层 `calibration`；默认保留严格 schema，由 API/业务 owner 决定修正 producer 或从确定性链路重新捕获样本，不为旧样本把字段改为 optional。
- 让受控后端 schema、OpenAPI、前端 DTO、golden sample 和页面 contract sync 输出同一个 contract receipt。
- breaking 例外必须含 owner、原因、受影响消费者、迁移方案和到期日；过期例外 fail-closed。

主要测试文件：

- `tests/test_api_contract_baseline_gate.py`
- `tests/test_api_contract_tooling.py`
- `tests/test_api_response_model_field_preservation.py`
- ADB schema/service/API 定向测试
- 对应前端 contract sync 测试

目标命令：

```powershell
.\.venv\Scripts\python.exe scripts\api_contract_check.py export-openapi `
  --surface default --output .codex-tmp/openapi.json

.\.venv\Scripts\python.exe scripts\api_contract_check.py baseline-check `
  --baseline-ref origin/main --json .codex-tmp/openapi-baseline-check.json

.\.venv\Scripts\python.exe -m pytest -q `
  tests/test_api_contract_baseline_gate.py `
  tests/test_api_contract_tooling.py `
  tests/test_api_response_model_field_preservation.py
```

退出标准是兼容变化正常通过，breaking change 无显式批准时失败，same-PR baseline rewrite 不能消除失败，严格 DTO 与真实输出无字段丢失或额外字段。

截至 2026-08-31，OpenAPI/release-eligible gate 已将 base ref 固定解析为 commit，缺失基线只允许显式 diagnostic bootstrap；working-tree、allow-stale 和 bootstrap 回执均不能标记为发布通过。`calibration` 与 `result_meta.trace_id` 必填契约已由响应模型锁定，但 captured ADB golden 仍缺少这两个字段。新增的非权威候选工具只在临时 DuckDB 中重放确定性 producer，并拒绝权威 golden 树、既存目录及 symlink/junction/reparse 绕过；它已生成完整模型有效的候选与机器差异，同时固定披露 `authoritative=false`、`captures_approval=false`、`writes_golden_sample=false` 和 `production_writes=false`。owner 仍须审阅完整差异后重新捕获；页面 badge 来源及 CNY/CNX 语义也仍待决定。这里只能写 WP3 的门禁、契约和安全重捕获准备能力已建，不能写 WP3 已通过或 golden 已批准。

### WP4：固定收益候选物化与可回滚提升

这是风险最高的工作包，必须在修改版本常量、物化任务、repository 或正式计算函数前运行 GitNexus upstream impact analysis，并明确直接调用者、受影响流程和风险等级。若为 HIGH 或 CRITICAL，开工前先告知 owner。

主要改动范围：

- 将债券引擎、债券正式物化和风险张量的版本定义收敛到一个不反向依赖 task/service 的领域版本模块。
- Manifest 同时记录 engine rule、materialize rule、upstream source、cache 和 downstream risk 版本，不再用一个 `rule_version` 混指不同层次。
- 增加固定收益 shadow rebuild 入口，复用现有 materialize task，不调用会刷新无关业务域的 global refresh。入口接收显式 `duckdb_path` 和冻结的 governance/source 引用。
- 从最新冻结的整库静止点复制并构建版本化 `duckdb-main` candidate，只替换固定收益目标切片；当前库不得先 purge 再等待候选完成。
- 逐报告日验证自然键、行数、空日期、版本三元组、DV01/KRD/CS01、总市值、债券数和治理 terminal，同时对全部非目标表执行 identity/允许差异校验，防止其他业务域被回退。
- 所有 golden 变化从确定性生产链路重新捕获，规则 owner 审阅差异后才能更新 approval；禁止手改 JSON 使测试变绿。
- WP4 只产出、验证并批准候选，不执行固定收益 lane 的独立文件切换。物理 promote/rollback 必须交给 WP7 的 `duckdb-main` whole-bundle 维护窗口，不删除候选或历史事件。

重点文件预计包括：

- `backend/app/core_finance/bond_analytics/`
- `backend/app/tasks/bond_analytics_materialize.py`
- `backend/app/tasks/risk_tensor_materialize.py`
- `backend/app/services/bond_analytics_service.py`
- `backend/app/services/risk_tensor_service.py`
- `backend/app/repositories/bond_analytics_repo.py`
- `backend/app/repositories/risk_tensor_repo.py`
- 相应 DuckDB schema registry 文件（只有血缘字段确需调整时）
- `tests/golden_samples/` 中经 owner 批准的受影响样本

目标测试：

```powershell
.\.venv\Scripts\python.exe -m pytest -q `
  tests/test_bond_analytics_engine.py `
  tests/test_bond_duration.py `
  tests/test_bond_duration_goldens.py `
  tests/test_krd.py `
  tests/test_krd_golden.py `
  tests/core_finance/test_bond_analytics_dv01.py

.\.venv\Scripts\python.exe -m pytest -q `
  tests/test_bond_analytics_materialize_flow.py `
  tests/test_bond_analytics_purge_interruption.py `
  tests/test_risk_tensor_core.py `
  tests/test_risk_tensor_materialize.py `
  tests/test_risk_tensor_service.py `
  tests/test_risk_tensor_api.py

.\.venv\Scripts\python.exe -m pytest -q `
  tests/test_golden_samples_capture_ready.py `
  tests/test_golden_sample_release_matrix.py
```

退出标准是候选构建失败不会影响 current，全历史影子物化无空日期、重复自然键或活动旧版本；风险张量逐日血缘等于对应债券完成记录；整库非目标表校验通过，candidate receipt 能供 WP7 使用。确切报告日数量、版本号和差异阈值以 WP0 owner 决定为准。

截至 2026-08-31，WP4 已增加 import-safe 的 `FixedIncomeVersionSet`，把 engine rule、Bond/Risk materialize descriptor 与 cache identity 按层披露，并保留动态 source、observed vendor、upstream 和 liability lineage 由每次真实构建注入。Risk 的复合 `source_version` 由统一函数生成，并在 task、candidate 行和 receipt runtime fragment 三层精确复算，不能再出现 liability 字段存在而总摘要遗漏的假闭合。当前版本状态明确叫 `configured_current`，不表示 owner 已批准或已经冻结；负收益率与闰日现金流算法已有数值变化，而 v1/v2/v6 尚未提升，下一版编号仍由 finance/risk owner 决定。single-report-date structure-only harness 使用 `moss.bond-risk-shadow-candidate-receipt/v1` 回执，把完整静态 descriptor、动态 lineage 和版本片段摘要交叉绑定到 seal intent，并继续固定 `financial_golden_validated=false`、`wp7_eligible=false` 和 `release_gate_eligible=false`。

同日新增的 `bond_risk_shadow_batch.py` 只接受显式日期文件，并对每个日期从同一冻结源创建独立 candidate，逐一复用现有真实 materialize task、验证 child receipt 后再生成 `moss.bond-risk-shadow-batch-receipt/v1` 聚合回执。日期文件、child 路径、child run id、输出白名单和两阶段回执最终化均 fail-closed。Bond/Risk service 与 Risk repository 的 configured-current rule/cache/job/lock 身份也已改为从同一版本集派生，历史 Golden 治理脚本继续显式 pin 在原版本，避免旧证据随 current 漂移。这只能说明当前身份真源已统一：Bond 读端仍允许采用旧 completed lineage，Risk 读端则严格按 current rule/cache 判 stale，freshness 政策尚待 owner 统一。多日期入口证明的是 `multi_report_date_structural_shadow_only`、失败隔离和逐日非目标漂移约束，不证明一个 candidate 已完成全历史重建。因此 canonical manifest 的 engine rule 独立披露、Bond/Risk freshness 政策、单 candidate 全历史 materialization、金融差异门、financial golden、正式 candidate receipt 和生产试点仍未完成。

### WP5：前端 exact-numeric 边界

目标是收正式页面和共享入口，不进行全站 formatter 重写。该工作属于 Tier 3 shared/cross-page business logic，修改共享 symbol 前必须完成 GitNexus impact 分析。

主要改动：

- 明确 `Numeric` 的 `raw_text`、`display` 和近似 `raw` 的用途；正式文本直接使用 `display`，精确比较/缩放通过 Decimal，图表边界才转换为 `number`。
- 把当前 `Number(raw_text)` 及接受该结果的测试列为待迁移基线；绿色测试本身不作为 exact-numeric 已闭合的证据。
- 为需要浏览器十进制运算的正式路径引入或封装 `decimal.js`；先做依赖评审，再更新 `frontend/package.json` 和锁文件。
- 禁止新增 `Number(raw_text)`、`parseFloat(raw_text)`、组件内 `/1e8`、正式聚合和正式分桶；守卫仅覆盖受控目录，避免一次性误伤全部 legacy 页面。
- 逐页迁移当前正式 Phase 2 页面，adapter/selector 输出受控 view model，component 只消费预制 display 或 chart value。
- 兼容路径登记 owner、原因、影响页面和到期日，新增正式页面不得加入白名单。

首批文件预计包括：

- `frontend/src/api/numeric.ts`
- `frontend/src/api/contracts/core.ts`
- `frontend/src/utils/format.ts`
- `frontend/src/pageModel/`
- 经盘点确认的正式页面 adapter/selector/component
- `frontend/src/api/numeric.test.ts`
- `frontend/src/test/numeric.test.ts`
- 受影响页面测试和 Playwright smoke

在 `frontend/` 目录执行：

```powershell
npm.cmd run test -- src/api/numeric.test.ts src/test/numeric.test.ts
npm.cmd run typecheck
npm.cmd run lint
npm.cmd run debt:audit
npm.cmd run test:a11y-smoke
```

除单元测试外，增加端到端精度样本，覆盖 PRD §9 所列输入，并验证 Chromium 等目标浏览器。退出标准是正式受控页面不依赖二进制浮点重新形成业务结论，现存兼容项有可追踪清单，numeric policy digest 可进入 Manifest。

截至 2026-09-01，WP5 公共边界已经落地：`raw_text` 保持无损权威，`raw` 只作近似兼容，Decimal helper 只从受控 plain-decimal 文本构造，图表通过具名边界显式降为 `number`；`decimal.js@10.6.0` 已成为锁定的生产依赖并通过 omit-dev 与依赖审计。生产代码已没有字面量 `Number(raw_text)` 或 `parseFloat(raw_text)`。首个页面切片已在现金流页面模型内完成：月度负值计数、最弱累计月份、最大负债流出月份、1bp 敏感度语义和风险读数亿元展示优先按 `raw_text` 做 Decimal 判断或缩放，旧的 raw-only 响应显式回退兼容；反例覆盖了近似值跨零、相同 `raw` 对应不同 `raw_text`、两位小数舍入、精确并列和缺数。图表序列仍保持 `number | null`，共享 `pageModel.numericRaw` 未改。

现金流链路在本地代码路径中已经闭合到 API 响应对象：shared `numeric_json` 新增默认关闭、仅限显式调用方启用的 `preserve_decimal` 选项，原有调用行为不变；`cashflow_projection_service` 通过本服务局部 helper 传入原始 `Decimal`，避免先收敛为 float。定向回归证明顶层 KPI、质量披露金额、月度 bucket 和到期资产列表都会输出 `raw_text`。这次改动不改变公式、`raw` 或 `display`，但会给冻结的 `GS-CASHFLOW-PROJECTION-A` 增加 111 个 `raw_text` 字段，现有 capture-ready 门仍会按完整字典比较转红，所以 Cashflow Golden owner 仍必须审阅并重新批准。

第二个页面切片已覆盖债券仪表盘。当前后端响应本来就为受控 Numeric 输出 Q8 `raw_text`，本次只在页面模型和格式层收口：信用债占比的 30%/50% 结论阈值、环比百分比/基点/亿元显示、资产结构占比与尾差优先使用 Decimal；纯 raw 旧响应仍走原逻辑，混合输入、零基数、负零、半值舍入和部分后端百分比都有独立反例。

第三、第四个切片分别落在 Risk Home adapter 与 PnL 量价闭合 view model。Risk Home 把正式摘要、阈值、峰值和文本缩放保持在 Decimal 路径，KRD 宽度等 chart-only 数值继续在显式 number 边界处理；同一 `raw`、但 `raw_text` 差异小于 JavaScript Number 分辨率的反例证明峰值不会在结论前降格。PnL 在任一闭合字段出现 `raw_text` 时以 Decimal 处理整组输入，其余有限 `raw` 只作兼容补位；全部 raw-only 时完整保留原算法。组件复用 view model 的闭合状态与占比资格，不再二次用浮点重算 1 万元容差。该切片只闭合前端量价判断，Campisi producer、个体金额精确展示和 Golden/规则版本仍待后续 owner 决策。

第五个切片落在 Risk Tensor 独立页。新增页面模型统一承接 `raw_text` 优先、raw-only 回退的正式判定，30 日流动性结论、主风险桶绝对值排序、投影质量、久期排除和 scenario tone 不再直接依赖兼容 float；精确并列仍保留第一项。正式万元/亿元金额缩放也已进入 Decimal helper，覆盖半值舍入、符号和超过 `2^53` 的冲突反例；KRD 雷达与图表 magnitudes 继续停留在显式 number 边界。

第六个切片落在 Decision Items。真实契约只提供后端 reason 叙述串，没有 Numeric DTO；页面模型因此只把其中 plain-decimal 万元片段改为 Decimal 缩放，覆盖 1 亿元阈值、负数、半值舍入和超过 `2^53` 的金额，并原样保留科学计数法或畸形片段。该切片没有依据 reason 金额新增排序，正式顺序继续使用状态、严重度、标题和 decision key。

第七个切片落在 Balance Analysis 的直接展示层。该页金额契约是后端 Decimal 序列化得到的 `DecimalLike` 精确字符串，不是 Numeric `raw_text`；overview/grid/workbook 两位小数、元或万元到亿元、以及后端 share 文本现在对 plain-decimal string 使用 Decimal ROUND_HALF_UP，number、科学计数法和非法值仍保留原兼容路径。GitNexus 将 `formatBalanceAmountToYiFromYuan` 判为 HIGH，直接影响 Balance Analysis、Balance Movement、Market Finance 和 Operations 四条 process，因此验证不能只停在本页。会计审计同时确认，前端 AC/OCI/TPL bridge、residual/ratio、1 亿元或 0.05% 状态阈值、部分求和和绝对值 Top-N 都是未经 owner 批准的正式判断；本切片没有把这些路径机械 Decimal 化，也没有把展示修复写成对账闭合。

Campisi 专项审计确认，真正的首断点在页面之前。formal-bridge 此前在 PnL Bridge Numeric 构造时把 Decimal 转为 float，model fallback 也会在持仓合并时降格；前端再用 Decimal 只能精确显示近似值。本轮因此先完成默认关闭的 wire-only 前置步骤：PnL Bridge 行与汇总在既有 `Numeric.raw_text` 可选字段中保留源 Decimal，同时兼容 `raw`、`display`、状态与顺序不变，Campisi 继续只读 `raw`。这一步不改变 selection、closure、排序或版本；一旦 Campisi 改为消费 `raw_text`，就必须让 Decimal 贯穿行、分组、总计和 closure，并由 finance owner 决定 rule/cache version 与 Golden。

审计还识别出与精度迁移相互耦合、不能机械修正的正式口径风险：任意请求区间可能被贴上单月 PnL 并仍显示 closed；model fallback 会把进出持仓余额变化承接为 selection；整条正值曲线的最大值低于 0.5 个百分点时可能被启发式放大 100 倍；Campisi 可能不继承 Bond Analytics 已确认的合法负 YTM 口径；权威付息频率未透传；coupon/face/MV 缺失可能无质量披露地折成 0；闭合阈值、舍入点与 Campisi v1 身份尚未进入受治理版本决策。这些发现及分阶段验收条件已写入 `docs/pnl/campisi-exact-numeric-owner-decision.md`。可执行的 SAFE 范围只包括无损线传、已有核心语义的不改金额中继和治理登记；本轮已完成三者，其中 formal bridge 的应计利息 availability 改为同时检查期初和期末，并由反例证明 totals、selection 与 formal closure 不变。其他 warning/quality 状态会改变页面解释，仍须先取得 owner 决定。

此前十八个组合前端测试文件共 430 项通过；本轮 Balance Analysis 影响面另外以 8 个文件、145 项测试覆盖四条共享 process，定向 ESLint、锁定版本 TypeScript 检查均为绿色。独立 Chromium 精度证据现为 4 项：债券仪表盘、现金流和 Risk Tensor 继续验证 `raw_text` 冲突；Balance Analysis 通过 route 拦截把超过 `2^53` 的 plain-decimal 元/万元金额和高精度 share 送入真实路由，概览卡、驾驶舱 KPI、workbook 评级金额和风险文案均显示精确结果。Decision Items 路由 smoke 另有 1 项通过。专用 registry 现覆盖 8 个页面、27 条生产路径；AST 守卫新增 `frontend/src/utils/format.ts` 和 `dashboardHome` 两个视图，`controlled_paths` 由 24 增至 27、`pending_migrations` 由 11 增至 14，说明新增受控面而不是回退；TPL 仍有 `DecimalLike` count4 和 literal `/1e8` count2，因此 policy 继续固定 `release_eligible=false`；WP7 rehearsal Manifest 的 numeric policy digest 已绑定受控页面/路径和完整 registry SHA。本轮验证已完成：PnL attribution 九文件 134 passed，后端 TPL+policy 60 passed，前端组合 7 文件 213 passed，frontend typecheck、全量 lint、debt:audit 通过，TPL 独立计算复核 PASS。其余高风险迁移包括 Balance Analysis 正式对账/排序、Campisi producer 与正式判断、工作台已登记但未迁移的首页兼容路径及其他正式页面。因此当前可以写“现金流与 PnL Bridge 本地后端 wire、七个前端切片和兼容治理基础已有受控证据”，但仍不能写“Campisi exact 已完成”“Balance Analysis 正式对账已批准”“Golden 已批准”“pending 兼容项已获 owner 批准”“该变更已部署”或“全站 exact-numeric 已完成”。

### WP6：审批聚合、CI 和发布保护

目标是把既有页面审批 checker 注册为统一 gate，并用 GitHub required checks/受保护环境阻止绕过；不重写所有页面脚本，不在应用内伪造审批身份。

主要改动：

- 建立受控 lane/page 的 approval registry，记录 checker 命令、required evidence、owner role 和允许的状态转换。
- registry 首批覆盖当前 8 个页面 checker 和 8 项计算口径决定；103 项页面待办是本地起始基线，不从历史审计文件复制。
- Manifest 汇总 `evidence_captured`、`machine_validated`、`business_approved`、`formal_use_allowed` 和 `closure_approved`，保持这些字段互不推导。
- `approve-record` 只导入权威审批引用并校验内容摘要，不代表应用验证了审批人的真实身份。
- 更新 `scripts/backend_release_suite.py` 与 [ci-release-suite.md](ci-release-suite.md)，只加入能够在限定时间内稳定运行的发布保护面；生产 live readiness 作为部署 gate，不塞进隔离 fixture suite。
- 更新 `.github/workflows/ci.yml`，把 Manifest、OpenAPI、正式计算、前端精度和审批材料结构映射为独立 checks。外部 GitHub ruleset、CODEOWNERS 和 Environment reviewers 由仓库管理员配置并留截图/导出回执；仓库内 workflow 不能证明这些 checks 已被平台设置为 required。
- PR 只校验审批材料结构、命令注册和摘要绑定；`--require-captured` 在对应 lane promote 时严格执行，不能把当前全部未批准事项挂成所有普通 PR 的永久失败门。
- 安全扫描结果只作为证据引用，不把敏感报告正文复制进 Manifest。

目标测试与命令：

```powershell
.\.venv\Scripts\python.exe -m pytest -q `
  tests/test_backend_release_suite.py `
  tests/test_backend_release_gate_docs.py `
  tests/test_system_audit_manifest_contract.py

.\.venv\Scripts\python.exe scripts\check_average_balance_business_owner_approval.py `
  --require-captured

.\.venv\Scripts\python.exe scripts\backend_release_suite.py --mcp-profile fast
```

页面 owner checker 的实际清单由 WP0 当前盘点生成，不能从历史审计文件直接复制。退出标准是 required approval 缺失、摘要漂移、例外过期或 governance record 缺失均阻断 promote；执行方不能通过重跑脚本自动产生批准。

截至 2026-08-31，WP6 的结构闭环与回执链路已经落地：统一 registry 覆盖当前 8 个页面 checker 和 8 项计算 P1 决定，审批只选择与 Manifest scopes 精确匹配的 applicable 条目；五个状态保持独立，`business_approved` 只接受外部权威事实，其他本地可观测状态也必须逐项与权威回执一致。`approve-record`、promote、forward rebuild 和 sealed bundle reactivation 都会重新校验 Manifest、冻结 registry、authority/gate receipt、过期与撤销状态，校验失败时不写 Event 或 Alias。通过的 gate receipt 会与目标 activation Event 和 Alias 在同一事务中持久化；同一幂等键即使带入不同 `checked_at`，也只重放首次提交的回执。CLI 对阻断只输出规范 reason codes 和可选 gate receipt，不泄露外部 verifier 异常正文。当前 16 项 authority policy 与 scope mapping 仍为 `PENDING`，生产 authority attestation verifier 也未配置，因此运行结果是安全地 fail-closed，并不具备实际放行能力。

CI 已新增独立的 `Release Control Structure (not approval)` job，只验证 schema、状态机、registry 结构、固定收益 configured-current 版本集合、单日期 shadow wrapper 和多日期结构证据聚合，并强制回执披露 `structure_only=true`、`approval_decision=not_evaluated`、`release_gate_eligible=false`。它不会因为尚未指派真实审批人而让普通 PR 永久失败，也不能被解释为全历史重建、业务审批通过或生产授权。GitHub required checks、ruleset、Environment reviewers 和 attestation 策略仍需仓库管理员在平台侧配置并留存回执，workflow 文件本身不能证明这些外部设置已经生效。

### WP7：固定收益试点与回滚演练

试点属于独立运维变更，必须使用单实例 whole-bundle 维护窗口；本计划本身不授权生产执行。建议顺序如下：

1. 暂停 keepalive、Windows Scheduler、外部 supervisor、新任务入队及所有可能写入共享 DuckDB 的入口；等待队列和活动 writer 排空，并备份当前整库、治理账本、部署配置和逻辑/物理 current 引用。
2. 停止 worker，再停止 API；确认没有目标库连接且不存在待处理 WAL。只停止两个主进程不足以进入维护窗口。
3. 从最新静止点复制整个 DuckDB，使用冻结的来源快照在版本化路径中生成 `duckdb-main` candidate；只重建固定收益切片，不重新抓取或改写外部曲线。
4. 运行 schema、整库非目标表、固定收益全历史逐日对账、golden、API contract、前端 numeric、目标环境 readiness 和治理审计，生成 immutable receipts。
5. 由金融规则 owner、数据 owner 和业务 owner 审阅差异，审批绑定 candidate 内容摘要；生产拓扑、RTO/RPO、观察窗口和恢复步骤仍为 `PENDING` 时不得继续。
6. 发布 owner 先追加 activation-intent 事件，把部署配置写成候选文件的绝对路径，部署 Manifest 绑定的兼容后端/前端构建，并以隔离验收模式启动 API；此时原 Alias 仍是正式 current。
7. worker、调度和其他 writer 继续停止；确认隔离进程披露目标 candidate `release_id` 和 `duckdb-main`，完成 candidate readiness、API、页面和治理 smoke 及观察窗口。验收通过后，使用一次 compare-and-swap 事务原子提升 `duckdb-main` 与全部 contained logical lane Alias并追加 current 事件，再执行 current readiness 复验。
8. Alias 切换与 current readiness 均通过后才恢复 worker、调度和 keepalive。恢复写入会改变活动文件 checksum，因此本试点只能证明 whole-bundle 维护切换，不能被表述为已经实现长期 immutable read snapshot。

切换失败时不继续修补 current。若仍处于同一停写窗口且其他域没有前进，可以 compare-and-swap 回切 previous sealed `duckdb-main`，恢复兼容构建并复验。writer 恢复后或其他域已有新写入时，不得直接激活旧整库文件；应从最新整库生成新的 rollback bundle，恢复上一 approved 固定收益切片，通过完整校验和审批后再按同一维护流程提升。所有失败 candidate、回滚原因和事件均保留，数据库破坏性 schema 不在同一次试点内实施。

持续生产的后续目标是增加独立写路径和发布路径：worker 只写 workspace，发布任务封存 immutable snapshot，API 只读 snapshot；scheduler、CLI 和 MCP 入口统一解析写路径，禁止硬编码 `data/moss.duckdb`。在这个边界实现前，不宣称支持 lane 级物理回滚、热替换、蓝绿或零停机发布。

截至 2026-08-31，WP7 的非生产机械演练已经落地。`scripts/wp7_release_rehearsal.py` 不读取系统配置中的 PostgreSQL DSN，不接受既有工作目录，只在新建绝对路径中创建合成 DuckDB 和临时 SQLite 权威；它完整执行基线 promote、候选 promote、两类写前负向探针、`sealed_bundle_reactivate` 回切、回滚幂等重放和 artifact/receipt 复验。合成 validation receipt 本身固定为 structure-only，标准 `ReleaseControlService` 会拒绝，只有绑定演练目录内 SQLite 的私有适配层可以推进临时状态机。固定路径校验同时拒绝 symlink、junction 和 reparse point；verify 模式也不再依赖 DuckDB runtime。`tests/test_wp7_release_rehearsal.py` 的 8 项测试已经进入默认后端发布套件，不再是旁路检查；安全收紧后的手工隔离运行 `wp7-manual-20260831-v3` 及其独立 verify 也通过，候选阶段三条 Alias 均为 revision 2，回切后均为 revision 3。

该结果只证明 whole-bundle 状态机、checksum 阻断和恢复不变量在合成隔离环境中闭合。演练回执还固定声明 `integrity_only=true`、`authenticity_attested=false`；自哈希只能检查一致性，不能替代尚未确定的外部权威签名。`structure_only=true`、`release_gate_eligible=false`、`wp7_production_eligible=false` 和 `production_writes=false` 使它不能进入正式 validation gate。生产拓扑、真实绝对路径、维护与观察窗口、RTO/RPO、owner、外部审批载体、兼容构建和全历史金融 golden 仍为 `PENDING`；没有执行生产试点、真实 Alias 切换、writer 停写或恢复，这些字段未闭合前 runbook 继续保持 `BLOCKED`。

## 5. PR 拆分

建议按以下顺序提交，名称可调整：

| PR | 内容 | 主要风险 | 合并条件 |
| --- | --- | --- | --- |
| PR-01 | Manifest/Event、分作用域 Alias 与 CLI | 新治理对象漂移 | 逻辑 lane/物理 bundle 状态机、摘要、并发测试通过 |
| PR-02 | PostgreSQL/DuckDB readiness | 生产误阻断 | stale/current/只读测试通过 |
| PR-03 | OpenAPI、ADB、DTO contract receipt | 基线绕过 | base-ref breaking gate 通过 |
| PR-04 | `duckdb-main` fixed-income candidate 与 shadow rebuild | 跨域整库污染 | 故障注入、逐日对账和非目标表校验通过 |
| PR-05 | frontend exact-numeric | 跨页面回归 | Tier 3 影响分析和前端门通过 |
| PR-06 | approval registry 与 evidence gate | 形式审批 | 独立批准与摘要失效测试通过 |
| PR-07 | CI、runbook、隔离 rehearsal 与组合 release verify | 门禁过慢、演练误触正式环境或可绕过 | required checks 映射、生产环境写前拒绝、回执与 artifact 防篡改测试通过 |

PR-02 与 PR-03 可在 PR-01 合并后并行。PR-04 与 PR-05 文件所有权分离后可并行。PR-06、PR-07 等前述 receipt 形状稳定后再合并。WP7 的隔离演练工具和测试可以进入 PR-07，但任何真实环境试点仍是独立运维变更，不作为普通代码 PR 执行。

## 6. 责任矩阵

| 工作 | 执行 | 批准/负责 | 复核 |
| --- | --- | --- | --- |
| Manifest 与状态机 | 后端/治理开发 | 技术 owner | 审计/架构复核 |
| schema 迁移与 readiness | 平台/后端 | 平台 owner | 发布 owner |
| 固收规则和黄金样本 | 固收开发/数据 | 金融规则 owner | 独立模型复核人 |
| 影子重物化与对账 | 数据运维 | 数据 owner | 金融规则 owner |
| API/DTO 契约 | 后端/前端 | API owner | 消费方代表 |
| exact-numeric | 前端 | 前端 owner | 金融计算复核人 |
| 业务批准 | 业务 owner | 业务 owner | 治理/审计见证 |
| promote/rollback | 发布 owner | 变更授权人 | 平台与业务共同确认 |

具体姓名、替补和升级路径均为 `PENDING`。任何生产动作必须有唯一执行人和独立批准人。

## 7. 风险与控制

| 风险 | 控制措施 |
| --- | --- |
| 控制面过度设计 | v1 只做 CLI、三类记录和 receipt 聚合，不建 UI/服务 |
| 逻辑 lane 与物理范围混淆 | lane 只表达验证/审批作用域；共享 DuckDB 统一由 `duckdb-main` whole bundle 切换 |
| 控制面自身不可用 | 已运行进程继续使用启动时固定的 current；新进程 readiness 失败，禁止自动切 candidate |
| PostgreSQL 误迁移 | 生产启动只读 assert，迁移使用独立命令和身份 |
| DuckDB 非原子替换 | whole-bundle 维护窗口、绝对版本路径和进程重启；不热替换已打开文件 |
| promoted 文件恢复写入后 checksum 漂移 | 首次试点明确为过渡机制；长期分离 worker workspace 与 API immutable snapshot |
| 旧整库回滚其他域 | 其他域前进后构建新的 rollback bundle，不直接指向旧文件 |
| 调度脚本继续写旧路径 | 维护窗口覆盖 keepalive/scheduler/supervisor；长期统一解析 read/write artifact path |
| 数据与代码错配 | Manifest 绑定 Git SHA、schema、rule、artifact、contract hash |
| 审批流于形式 | 批准绑定摘要，禁止自审，摘要变化自动失效 |
| GitHub 门禁绕过 | base-ref diff、required checks、受保护环境和到期例外 |
| 前端精度回归 | `raw_text` 权威、Decimal 边界、守卫测试、逐页迁移 |
| CI 运行时间失控 | 窄门先行，live readiness 留在 deployment gate |
| 工作树混入在途改动 | 每 PR 锁定文件 lane，提交前审查 `git diff` 和变更检测 |

## 8. 集成验收与停止条件

所有 PR 合并后先执行窄门，再执行仓库规范总门：

```powershell
.\.venv\Scripts\python.exe scripts\backend_release_suite.py --mcp-profile full
```

前端共享数值或受控页面有改动时，在 `frontend/` 执行：

```powershell
npm.cmd run test -- src/api/numeric.test.ts src/test/numeric.test.ts
npm.cmd run lint
npm.cmd run typecheck
npm.cmd run debt:audit
npm.cmd run test:a11y-smoke
```

发布候选必须同时满足 PRD §9 和以下集成条件：

- Manifest validator、目标环境 readiness、formal receipts、OpenAPI base-ref diff、前端 numeric receipt 和 required approvals 全部为通过状态。
- 没有使用 `--allow-stale-baseline`、全局 migration skip 或临时关闭门禁作为正式放行依据。
- 目标逻辑 lane 的 previous approved slice 和 `duckdb-main` previous/current 均可定位；回滚策略能区分停写窗口内回切与其他域前进后的新 bundle 重建。
- 生产切换前后的 `release_id`、逻辑 lane versions、`duckdb-main`、schema heads、artifact checksum 和页面/API smoke 能相互勾稽。
- API smoke 与观察窗口内所有 writer 保持停止；恢复写入后的文件不得继续冒充 sealed immutable artifact。

出现以下情况立即停止提升并回到 candidate：目标环境与证据包不一致；任何正式口径未获 owner 决定；影子数据存在空日期、重复自然键或对账残差超出批准阈值；审批摘要失效；无法确认 previous release 可恢复；必须扩大到认证、无关 schema 或 excluded surface 才能继续。

### 8.1 当前发布门状态（2026-08-31）

最新完整 fast profile 得到 751 项通过、10 项失败、2 项按 profile 排除。四处前端展示文案造成的守卫误报已经用文件级精确片段收口，共享 Numeric 已把 Decimal 的指数形式规范为普通十进制，本轮 WP6 审计回执、WP7 合成演练与只读试点预检也均为绿色。剩余 10 项与定向复核一致，都需要规则版本治理或 owner 审阅，不能以重录 JSON 代替批准，因此当前不得创建 release-eligible receipt。

| 阻断组 | 样本 | 下一动作 |
| --- | --- | --- |
| ADB 完整信封 | `GS-AVERAGE-BALANCE-MONTHLY-A` | 保持 `trace_id`、`calibration` 必填；API 与业务 owner 审阅完整响应后重新捕获 |
| 固收精确数值 | `GS-BOND-HEADLINE-A` | 普通十进制代码缺陷已修；owner 审阅新增 `raw_text` 后重新捕获 |
| 固收规则版本 | `GS-RISK-WARN-B` | 保留正确的闰日现金流修正，提升 Bond Analytics/Risk Tensor 规则与 cache 版本，再做模型复核和批准 |
| PnL v4 血缘 | `GS-BRIDGE-A`、`GS-BRIDGE-WARN-B`、`GS-PNL-DATA-A`、`GS-PNL-OVERVIEW-A`、`GS-PNL-BUSINESS-INSIGHTS-A` | 成对重捕获待批样本；已批准的业务洞察必须重新审阅上游 v4 血缘 |
| PnL Decimal 闭合 | `GS-PNL-ATTR-WB-A` | 确认浮点伪残差归零及归因公式精确闭合后重新捕获并审批 |
| 股票证据术语 | `GS-STOCK-ANALYSIS-OBS-A` | owner 冻结社融主序列、M2 fallback 与信用扩张代理表述后重新捕获 |

这 9 项阻断现在有独立的机器审阅入口：先对表中精确 pytest 节点生成 JUnit XML，再运行 `scripts/release_control_golden_blocker_review.py --junit-xml <path>`。输出只保留测试状态、断言路径、原因码、owner 路由、成对样本关系和当前四件套摘要，固定声明 `authoritative=false`、`captures_approval=false`、`writes_golden_sample=false`、`writes_governance_records=false`、`production_writes=false`、`release_eligible=false`。缺节点、重复节点、error 或 skip 都保持阻断；全部测试通过也只说明可以进入 owner 决策，不能自动刷新 golden 或继承旧审批。2026-08-31 的本地基线为 9 项失败、0 项 error、0 项 skip，其中已批准的 `GS-PNL-BUSINESS-INSIGHTS-A` 被单独标记为必须重新审批。审阅包的 7 项回归已进入默认 fast backend release suite；这只把非审批边界变成持续门禁，不改变当前 9 项业务阻断状态。

WP7 还新增了固定收益生产试点的结构化预检器 `scripts/wp7_fixed_income_pilot_preflight.py`。它只读取 JSON 交接包，要求 owner、绝对规范化路径、停写证明、备份 SHA-256、五态审批、GitHub/authority 证据、维护与观察窗口、RTO/RPO，以及 `sealed_bundle_reactivate`/`forward_rebuild` 两类回滚分支字段全部闭合；任何 `PENDING`、占位、缺字段、非法摘要或非绝对路径都 fail-closed。该工具即使在字段齐全时也不会授予生产授权，回执固定保持 `release_eligible=false`、`authorizes_pilot=false` 与 `production_writes=false`，状态最多推进到 `awaiting_owner_execution`。对应回归同样已进入默认 fast backend release suite，用来持续证明 runbook 仍停留在“结构可核对、授权未发生”的边界。

### 8.2 工作包验收矩阵（2026-08-31）

| 工作包 | 当前结论 | 尚未闭合的退出条件 |
| --- | --- | --- |
| WP1 发布记录与状态机 | 本地验收完成 | 目标环境部署与生产 `current` 授权不在本次范围 |
| WP2 存储 readiness | 本地验收完成 | 目标生产环境 readiness 回执仍需平台 owner 提供 |
| WP3 API / ADB 契约 | 部分完成 | ADB 完整响应重新捕获、API 与业务 owner 审阅 |
| WP4 固收 shadow materialization | configured-current 分层版本、读端身份真源、v1 回执、单日期候选和多日期结构证据已完成 | owner 确认版本提升与规则语义、canonical engine lineage、Bond/Risk freshness 政策、单 candidate 全历史物化、金融差异/golden 门和正式候选回执 |
| WP5 前端 exact-numeric | 公共能力、现金流与 PnL Bridge 本地后端 wire、Campisi 应计利息两端可用性中继、七个前端切片、Risk Tensor 金额缩放、Balance Analysis 直接展示、8 页面 registry、AST guard、Manifest policy digest 及 4 项 Chromium 精度证据完成 | Balance Analysis 正式对账/排序、Cashflow/PnL Golden owner 审批、Campisi producer/规则版本与金额展示、14 项 pending 兼容基线的 owner/expiry、其余逐页迁移 |
| WP6 审批与证据门 | 结构闭环完成 | 16 项 authority/scope mapping、生产 verifier 与 GitHub 平台设置 |
| WP7 试点与回滚 | 合成演练和只读预检完成 | 获授权生产试点、真实停写/备份/观察窗口、成功提升与可审计回滚 |

这张矩阵只用于说明代码与证据到了哪一步。它不把“本地验收完成”解释成生产上线，也不把“结构闭环完成”解释成 owner 已批准。

## 9. 完成定义

本计划只有在下列结果同时成立时才完成：代码与文档门禁已接入，固定收益试点按 `duckdb-main` whole-bundle 方式完成一次成功提升和一次可审计回滚演练，业务 owner 对试点结果作出有效决定，运行环境能够披露逻辑 lane 与物理 bundle，且剩余风险有 owner、时点和触发条件。

如果只能完成代码和测试，而未取得业务批准或未执行获授权的试点，应把状态写为“控制面能力已建、正式推广未完成”。如果试点后 API 与 worker 仍共享可写文件，则只能写“维护窗口切换已验证、持续不可变发布未完成”，不得表述为系统已完成治理闭环。
