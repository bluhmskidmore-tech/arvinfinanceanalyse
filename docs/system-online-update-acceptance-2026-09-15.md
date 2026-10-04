# 系统在线更新第二周期验收清单

## 当前结论

本文件只准备第二周期的本地验收矩阵和合成故障验证清单，不改变实现方案，也不执行正式更新。当前没有证据表明存在新的报告日或源文件版本差异；既有 2026-08-31 财务成功请求不可为本轮重跑。因此“真实在线正常更新”门槛保持 `PENDING`，不能用已有成功回执替代。

第二周期代码尚待父任务明确 ready 后再执行目标测试。API、worker、监督线程和计划任务的正式在线并发验收也保持 `PENDING`；本文件中的断言是执行入口和预期结果，不是已通过的运行回执。

## 证据边界

本清单只承接以下本地材料：

- `docs/system-online-update-plan-2026-09-15.md`
- `docs/system-online-update-read-paths-2026-09-15.md`
- `.codex-tmp/system-online-update-20260915/boundary-audit.json`
- `docs/page_contracts.md` 中首页、余额、风险、经营分析、债券分析和跨资产条款

首轮底座已证明共享入口在选定快照上读取时，另一个进程可以持有既有 writer lock 并写活动库；首轮证据不证明 API 已解析完整 read pack，也不证明五域已经脱离活动库。第二周期不得把底座测试改写成端到端验收结论。

## 固定本地验收矩阵

以下请求沿用 plan 中固定的代表入口和参数。请求只读，不触发刷新；每一行应记录 HTTP 状态、响应中的报告日/质量/回退状态、读取 generation（若第二周期契约已提供）及是否出现混代。除 `data-updates` 的实时队列状态外，业务读面必须来自同一有效 read pack。

| 领域 | 固定入口 | 最小通过断言 | 必须失败或可见的情况 |
| --- | --- | --- | --- |
| 首页 | `GET /ui/home/snapshot`（默认严格交集） | `result.report_date`、`result_meta`、`domains_effective_date` 和 `domains_missing` 可核对；strict 模式不带缺域成功返回；同一请求内 generation 不变化；补充读面只有在报告日一致时才可用 | 没有有效 pack、缺域、fallback、旧/新 generation 混合时不得伪装正常；online-required 应明确 fail closed |
| 余额 | `GET /ui/balance-analysis/overview?report_date=2026-08-31` | 返回的 `report_date` 与请求一致；`position_scope`、`currency_basis` 可核对；资产端与负债端分列，`total_*` 只作兼容毛额，不冒充单侧或净额；不静默换日 | 无该日数据为 `404`；lineage/runtime/prerequisite 不满足为 `503`；fallback 或 warning 必须可见 |
| 债券 | `GET /api/bond-analytics/portfolio-headlines?report_date=2026-08-31` | 返回报告日与请求一致；`result_meta.quality_flag`/`fallback_mode` 可见；加权 YTM 与加权修正久期只在 `rate`/`credit` 投资范围内核对，排除 `other`，不在前端重算 | 直接 active 读取、无 pack、陈旧/降级、日期不一致不得变成成功空结果；错误状态必须可见 |
| 风险 | `GET /api/risk/tensor?report_date=2026-08-31` | 返回报告日与请求一致；`portfolio_dv01`、`regulatory_dv01`、KRD、CS01、凸性及久期适用范围沿用正式字段和单位；`quality_flag` 异常可见，不用一个 DV01 字段回填另一个 | 无该日数据为 `404`；governed prerequisite 缺失为 `503`；前端不得补算或把 scenario 结果混入 formal tensor |
| 损益 | `GET /api/pnl/by-business-insights?year=2026&as_of_date=2026-08-31` | `year` 与精确 `as_of_date` 原样生效；正式结构面板仅在 formal v2、无 fallback、日期一致、组件证据齐全时可用；`001/002/003/006` 按 `%`、`004` 按月、`005` 按百分点、`007` 按描述性 quadrant 展示；诊断项单独保留 | non-formal、fallback、stale/error、日期错配、缺组件、null/insufficient/source unavailable 不得转成零或成功结论；诊断项不得混入管理结论 |
| 更新状态 | `GET /api/data-updates` | `financial_dates` 只来自当前有效 read pack；队列 runs、状态、取消和审计继续读取 live 状态；响应应能区分“旧 pack 可读”和“新请求正在执行” | 不得把旧日期与 live running 标签拼成“已刷新可见”；本轮没有新 source delta 时不得出现人为完成的更新请求 |

### 跨域最小核对

跨域核对只记录布尔结果、状态和元数据，不把业务金额复制到外部服务。首页继续使用最新严格交集和 `domains_effective_date`；其他页面按各自的 `report_date` 或精确 `as_of_date` 合同读取，不强行改成一个全局日期。余额的 `currency_basis` 与 `position_scope`、损益的 `year/as_of_date` 等请求口径必须以各自 payload 和页面合同为准，不能仅凭字段名推断跨域可比。五个代表入口在同一交互或同一 read pack 下不得出现 generation 混用；无法证明共同 generation、日期、币种、范围和单位时，金额级核对明确保持 `PENDING`。

## 合成故障验证清单

这些场景在临时数据库、临时 read-pack 目录和临时 lock 目录中执行；每个场景使用独立进程、事件/管道或等价 barrier 证明重叠，不用无界 sleep。清理范围仅限本次测试创建的进程和临时目录。

| 场景 | 预期结果 |
| --- | --- |
| 旧 pack 请求持续读取，writer 全程写活动库 | 旧请求始终读同一 generation；writer 可完成；请求退出后新请求才可见新 pack |
| 无 selection 的活动库 reader 对照 | writer 被既有活动库锁阻断并返回明确 DuckDB IOException；该反向组证明正向隔离确实有效 |
| pointer/CAS 提交前 | 新请求继续读取旧 pack；候选失败不得改变 current pointer 或 completed 状态 |
| exact run terminal 缺失、run id 不符或 status 非 completed | publisher fail closed，保留旧 pack，并保留可追溯失败原因；不得用 latest completed 猜来源 |
| 域 coverage、source version、governance digest 或 PnL generation 不匹配 | 候选不激活；旧 pack 继续服务；不把部分覆盖写成全局完整 |
| 候选 snapshot 写失败、关闭后只读校验失败、磁盘容量不足 | 保留旧 pack，释放候选句柄和锁，外层请求不得报告成功 |
| CAS 冲突、pointer 提交后回执写入中断 | 依据已提交 pointer 和回执恢复元数据；不得重跑已成功财务步骤或生成双 current |
| 线程池/native prewarm 延迟结果 | 延迟任务只能写入其开始时固定的 generation；无 selection 时不得回落活动库 |
| task/CLI 从 API context 继承 selection | 外层显式 active scope 后必须写活动库；任务完成后 reader context 恢复或清空 |
| API 在 writer 运行或重启期间启动 | API 只校验有效 snapshot/read pack；不得对活动库做启动写入或把启动异常吞成空数据 |

每个故障场景至少记录：旧 pointer 是否保留、外层请求状态、活动库是否被误读、句柄/锁是否释放、generation 是否混用，以及是否留下可追溯 failure receipt。

## 第二周期 partial audit（本地）

在父任务完成 `coverage_dates` 类型和 `location.key` 生命周期修正后，前端固定边界命令通过 `7` 个测试文件、`236` 项测试。root 五仓储与 harness 组合通过 `48` 项 pytest；这两项只证明声明范围内的单元/仓储边界，不等于真实 API 联调或完整 publisher 验收。

只读 probe 以 `5` 个 client、`5` 轮、每轮包含首页、余额、债券、风险、损益和 `data-updates` 六个 GET，共 `150` 次本地 GET。`150/150` 返回 HTTP 200 且 envelope 有效，无 file-lock 或其他网络/解析错误；各域在当前运行中各自保持单一业务 hash。但以 `--require-generation` 执行时，`150` 次均缺少 `X-MOSS-Read-Generation` 响应头，因此 probe 退出码为 `1`，这一代际握手阻断必须修复后才可继续声称在线读边界闭合。完整 publisher/API 接线仍在进行，真实在线更新门槛保持 `PENDING`。

本轮冻结的前端四文件、root 五仓储和 probe 脚本的 SHA-256、编码检查、命令输出与失败明细均保存在 `.codex-tmp/system-online-update-20260915/independent-cycle2-partial-audit.json`。金额级跨域对账仍需共同 generation、日期、币种、范围和单位的可比证据，不能由本轮 hash 稳定性推导。

新增 `tests/test_system_online_publication_concurrency.py` 与冻结的五仓储/harness 合并运行通过 `50` 项（其中新增测试为 `2` 项），并对新增测试单独运行 Ruff 通过。测试用独立 spawn 进程持有真实 DuckDB writer lock，使用 `ready/release` 事件与 writer 更新后的活动库状态确认读写重叠；5/10 worker pool 的 HTTP 读在 writer 保持存活期间均返回旧 generation 的稳定内容。测试还覆盖 pointer commit 前、pointer 已提交后的注入中断，以及按当前 pointer 重试恢复。

这仍是合成生命周期证明，不是正式五域更新验收。测试没有模拟进程在 CAS/回执持久化中的真实 crash，也没有覆盖 coverage/source/governance 不匹配、磁盘容量不足、CAS 竞败、native prewarm 或全应用真实部署；每个 pool 实际提交的请求数为 worker 数的两倍（10/20），因此不应表述为恰好 5/10 请求。新增测试 hash 为 `a279211d92653820fcd2424e36ccd3b4e10c5829f45df29638ec8df65cb1405f`。

## 读取侧最终独立整合复核（本地）

按读取侧冻结范围运行指定 pytest 组合，包含 `system_online_publication_concurrency` 这一明确列出的合成边界测试，共 `188 passed in 54.34s`；仍在编辑且未列入命令的 publisher 测试不在本轮结论内。本轮只证明读取侧和合成边界，不能替代完整 publisher 或 API 联调验收。前端最新 boundary7 独立运行 `7` 个文件、`236` 项测试通过；typecheck/build 采用父任务另存的最终回执，本审计未重复执行。

读取侧窄 Ruff（main、API 初始化及 system-read/PnL 路由、governance settings、governance/system-read/yield 仓储、response/runtime cache、PnL publication/service、market-home warmup 及本轮测试）全部通过。四个旧 facade 只按 `E9,F821` 门槛检查通过；全量 Ruff 债务保留为 `107` 条，其中 `executive_service.py` 有 `38` 条 `F401`，`macro_toolkit_service.py` 有 `68` 条 `F401` 与 `1` 条 `I001`，`market_overview_service.py` 和 `macro_vendor_service.py` 没有全量错误。本轮没有修复这笔既有债务。

独立静态核对显示 `executive_service.py` 的 `6` 个线程池 `submit` 和 `market_overview_service.py` 的 `1` 个 `submit` 均直接使用独立的 `copy_context().run`；测试也按 AST 对每个提交点做了同一断言。首页 settings/direct-service 代表性 leaf recording 共记录 `6` 条，均解析到选定 snapshot，active path 不在记录中；这只是六类读取入口的代表性证明，不是所有 repository/endpoint 的穷举清单。完整逐文件 SHA-256、BOM 与 U+FFFD 检查写入 `.codex-tmp/system-online-update-20260915/independent-cycle2-read-side-final-audit.json`。

本轮未执行正式数据中心预检、生产服务/数据库操作、在线更新或旧的 `--require-generation` API probe；没有新的报告日或 source/version delta，且先前 `X-MOSS-Read-Generation` 缺失的本地 probe 阻断仍需由完整 API 接线修复。因此真实在线正常更新和完整发布验收继续保持 `PENDING`。

## 正式在线更新门槛

在出现经预检确认的真实新报告日或 source/version delta 之前，下面的门槛保持 `PENDING`：

1. 通过既有数据中心预检并明确变更日期、范围和输入来源；不因已有 2026-08-31 成功回执重跑。
2. API、worker、预热线程和计划任务保持在线，覆盖更新前、中、后以及 5/10 并发读；无文件占用、非预期 HTTP/契约错误或混代。
3. 更新完成后只在完整 pack、冻结 lineage、域 coverage 和既有 PnL generation 全部核验通过时切换 pointer；失败保留旧 pack 和失败回执。
4. 五域响应逐项核对日期、单位、范围、质量和来源；技术 hash 只证明一致性，不替代独立会计对账。

父任务通知 Cycle 2 代码 ready 后，才执行对应目标测试和本地合成故障项，并把实际命令、状态、回执路径和残余风险追加到本文件或独立本地证据中。

## 未覆盖范围

本段保留早期检查时点的范围；后续读取入口和 publisher 实现进展见下方 Cycle 3 记录及当前接续文档。所有自定义 repository、正式在线运行和独立会计对账仍未全量覆盖。未发现真实 source delta 时，在线正常更新结论必须保持 `PENDING`。

## Cycle 3 生命周期与产物保留独立审计（本地）

读取侧独立核对了 generic financial publisher、financial publication repository 和 system-read publication repository。代表性 retention 测试命令为 `.venv/Scripts/python.exe -m pytest -q tests/test_financial_result_publication.py::test_old_connection_stays_pinned_and_new_connection_reads_new_generation tests/test_financial_result_publication.py::test_disk_capacity_preflight_leaves_no_candidate_or_pointer tests/test_pnl_by_business_page_read_hotpath.py::test_retained_catalog_rechecks_selected_generation_after_pointer_rotation tests/test_pnl_by_business_page_read_hotpath.py::test_pinned_history_read_rejects_generation_evicted_after_status`，结果为 `4 passed in 2.41s`。它证明旧连接在 pointer 轮换后仍保持原 generation，显式超出 retention window 的 generation 会被拒绝，容量预检失败不留下 candidate 或 current pointer。

在临时合成 source DuckDB、PnL publication root 和 system-read publication root 中，直接使用 generic `FinancialPublicationPlan`/`publish_financial_result` 及读取仓储构造 P0→P1→P2。该 probe 没有保留独立脚本文件，使用的是一次性 inline 命令，并有意绕开当时仍在编辑的 `system_read_publication` orchestration。两次推进后 PnL pointer 为 `current=P2`、`retained=[P2,P1]`；generic resolver 拒绝超窗 P0，但引用 P0 的 system bundle 仍能读取，且 P0、P1、P2 的 database 与 manifest 文件均仍在物理目录中。

新增真实进程崩溃测试命令为 `.venv/Scripts/python.exe -m pytest -q tests/test_system_read_publication_process_crash.py`，结果为 `2 passed in 14.09s`。静态核对确认测试使用 `multiprocessing.spawn` 和 Pipe 阶段屏障，在 `before_pointer_commit` 与 `pointer_committed` 两个真实边界暂停；父进程 bounded `terminate/join` 并以 `kill/join` 兜底，子进程必须非零退出。测试在子进程存活时确认 source writer lock 被持有，退出后重新取得 source writer lock 与 publication lock；CAS 前检查旧 pointer、sealed candidate 和禁止重建后的恢复，CAS 后检查新 pointer、禁止 source revalidation/candidate rebuild 以及 `already_published` 元数据恢复。

本次针对三份实现文件的有限静态检查未发现 generation database 或 manifest 的自动 GC/删除调用。`_write_atomic_json` 的唯一 `unlink` 只清理临时 `.tmp` 文件；invalidation 只写 `invalidations/*.json` 并使读者拒绝该 generation，不物理删除产物。因而 pointer retention window（最多两代）与 physical retention（至少在本 probe 中保留三代）是两条不同边界；`_require_capacity` 只在候选构建前保护可用空间，不是历史产物 GC，持续发布可能带来目录增长的运维风险。独立证据写入 `.codex-tmp/system-online-update-20260915/independent-cycle3-lifecycle-audit.json`，SHA-256 为 `464f1ff887d371d20b88542dc141f5266dee61a5bea7d20d4aa6130e21adbe47`。本审计使用合成临时数据，没有生产服务、正式数据库或正式更新操作，不能替代五域在线更新验收；真实在线正常更新门槛仍为 `PENDING`。

## Cycle 3 publisher 与首页增量独立回归（本地）

在父任务声明 publisher mapping 冻结后，五个后端文件分别用独立的 `.venv/Scripts/python.exe` 进程运行，全部通过：`test_system_read_publication.py` 为 `23 passed in 4.70s`，`test_financial_result_publication.py` 为 `25 passed in 15.41s`，`test_global_data_refresh.py` 为 `18 passed in 1.90s`，`test_data_updates.py` 为 `55 passed in 5.44s`，`test_formal_pnl_source_version_identity.py` 为 `2 passed in 0.77s`，累计 `123 passed`。分进程执行是为了隔离已知的旧 `tests.helpers.load_module` 对 `sys.modules` 和父包属性的污染；本轮没有修改旧 helper。

前端原 boundary7 加 `DashboardHomePage.test.tsx` 的组合命令为 `npm.cmd run test -- SystemReadGenerationBoundary.test.tsx ApiClientCompositionBoundary.test.ts ApiClient.test.ts HomeStartupClient.test.ts PositionsRiskDeferredClient.test.ts routes.test.tsx RouteRegistry.test.tsx DashboardHomePage.test.tsx`，结果为 `8` 个文件、`279 passed`（`13.20s`）。针对首页两份实现文件和 system-read boundary 两份实现/测试文件的定向 ESLint 通过且无输出。后端 publisher、读取仓储、五份回归测试以及本轮前端测试文件均完成 SHA-256 与 BOM/U+FFFD 检查，完整清单写入 `.codex-tmp/system-online-update-20260915/independent-cycle3-final-regressions.json`，其 SHA-256 为 `dc4e98ee16633faf265b5b9e09bf454caf7e2e5dd3b646b9c465569561c3e976`。

这些结果是冻结范围的本地回归证据，不是正式五域在线更新或生产部署证明。父代理勘误：source-preview 的连续两次预检都失败，两候选均因空 batch 合法 producer 分支尚未覆盖而返回 `None`，不是“合格 candidates”。初始化和上线仍暂停。独立审计代理未执行正式预检、生产服务、端口或正式数据库操作；父代理另有两次纯只读预检，均未 COPY、发布或重算财务。正式资格与在线更新继续保持 `PENDING`。原独立 JSON 回执未改写，勘误同时保存在 `root-final-freeze.json`。

## 第三轮网页复核后的父代理收口

网页 Pro 第三轮返回 `REVISE`，要求补合法空批次资格分支和经过真实 bootstrap 入口的集成回归。前两轮的读取/交互局部 ACCEPT 不等于发布器或全局上线批准。按继承的三轮预算，本轮停止继续执行；正式配置未启用，已成功财务请求未重跑。运行状态、五域实际覆盖、源码/构建冻结以及下一项精确修复见 `docs/system-online-update-continuation-2026-09-15.md`。
