# MOSS 开发债务修复与主代理验收

验收收口日期：2026-09-23。本批行为修复和门禁自身回归通过；当前全仓 mypy 与 BLE001 仍阻断，不能据此签认全部技术债已清除。

本批由五个子代理分别处理发布重试、利差状态、请求复用、读取契约和类型门禁，主代理检查连接处并独立验收。发布重试与利差状态属于行为缺陷；重复请求实现、核心字段契约、类型门禁属于已确认技术债。本批没有按文件长度展开结构重构。

本文记录当前工作区的实现与本地验证。共享工作区还有其他任务同时修改，本批保留了这些修改，没有提交、部署或写入正式业务数据。原始盘点与分类依据见 开发债务解决方案（执行证据仅保存在本地）。

## 已闭合的业务范围

财务主体执行完毕后，`publish` 或 `system_read_publish` 失败不再进入整链自动重试。已经保存发布失败回执的旧 `retrying` 请求也会在预检之前停止重放，保留原 run、attempt、步骤与失败回执。`source_preview` 仍要求主体已完成才停止重试，主体执行前的临时故障继续沿用既有重试。停止重放表示发布尚未完成，不表示已经恢复成功。

产品损益利差归因现在检查上期利差、资产收益率和负债成本是否齐备。缺少任一字段时展示 incomplete 原因；真实零值继续有效。改动位于前端状态判定，不改变金融计算或用零填补缺失。

余额变动客户端删除了重复的请求实现，读取接入已有 transport 的 envelope 校验与超时控制，刷新仍按原有普通 JSON 响应处理。HTTP 200 加空对象已经不能穿过读取边界。后续另一并行任务在同一文件补充了调用方 signal 透传和页面反馈，本批保留并在汇合源码上验证，但不将这些追加工作归为本批独立完成。

产品损益日期、主读取、历史三个端点使用现有业务 payload 加命名 envelope。`response_model_exclude_unset=True` 保留原来省略可选字段的行为；Decimal 字符串、null、报告日和质量元数据通过序列化等价检查。另一任务继续补齐归因与刷新端点，本批仅认领上述三个读取端点。

## 主代理验收证据

主代理将后端源码、所选测试及测试隔离守卫复制到独立目录，并保留 SHA-256 清单。第一次收集发现副本漏带 SQL schema，补齐源码资产后重新验证；最终模块路径探针确认任务、API 和 DuckDB 守卫均从副本导入。整个过程保留测试隔离守卫，使用合成数据，不连接业务数据库。

| 验收项 | 实际结果 |
| --- | --- |
| 独立源码副本：发布、重试、读取契约 | 29 项通过 |
| 独立源码副本：物化、服务与 HTTP 序列化等价 | 1 项通过 |
| 当前前端：余额客户端、利差状态 | 31 项通过 |
| 当前前端：共享 transport | 33 项通过 |
| 浏览器：上期三个必要字段分别缺失 | 3 项通过 |
| 类型检查器、导入边界与 CI 配置回归 | 84 项通过 |
| 前端全量 typecheck | 通过 |
| 前端 real 模式生产构建 | 通过，输出至独立证据目录 |
| 前端 lint | 通过，1 条 Fast Refresh 警告 |
| 聚合 debt:audit | 六段通过 |

浏览器在独立 loopback Vite 入口运行，业务 API 全部由合成响应接管，未接真实后端。最初用过宽路由模式误拦截了 Vite 源码模块，三项没有进入页面；改为只拦截根路径 `/api/` 和 `/ui/` 后全部通过。验收查看了缺失原因截图，未将最初失败删除或记为业务修复前失败。真正的改前失败由所属单元和组件反例提供。

子代理另完成数据更新完整模块 66 项、产品损益 flow 75 项，以及前端模型、页面和客户端组合回归。它们与主代理所跑用例有重叠，因此不相加为总覆盖数。接口子代理的 75 项结果仅保存在会话工具输出；主代理补存了独立副本的契约和物化序列化验证日志。

本地证据目录为 [debt-remediation-20260922-task01a0c999](../.codex-tmp/debt-remediation-20260922-task01a0c999/)。其中 `source-acceptance-manifest.json` 保存受测源文件指纹，`root-acceptance-final.log`、`root-materialized-api-acceptance.log`、`root-frontend-acceptance.log`、`root-transport-acceptance.log` 和 `browser-final2.log` 对应上表。源码副本不是完整发布包，只证明所选工作流和必要测试依赖在该副本中闭合。

生产构建使用 `VITE_DATA_SOURCE=real`，输出位于证据目录的 `frontend-dist`，未覆盖日常服务目录。构建成功仅证明打包可用；本机 Node 24 与 CI Node 22 不同，托管 CI 仍需在其指定环境实际执行。

## 类型门禁与尚未通过的检查

类型门禁已由逐文件数量比较改为诊断身份比较，包含源码路径、错误类别、消息、语句和控制分支上下文。同数量换错、相同语句跨分支替换、配置或依赖锁放宽均有失败反例。更新只允许删除已解决身份，有新增或替换时拒绝写入；检查前后核对配置和依赖锁。CI 已移除观察模式，先显式加载 DuckDB 守卫并运行检查器测试，再执行阻断门禁。

历史冻结集合来自提交 `643496ad93ebc8d8fafd33389351ab4729b484f7` 的完整 backend 和 scripts 源码，在专用 Python 3.11.9、mypy 1.20.1 环境下非增量重放。971 个文件与 Git 原字节一致，运行前后指纹一致；原 229 文件的 1,591 条诊断逐文件计数、逐条路径/错误码/消息及最终身份均已核对。独立复核接受 `mypy-identity-baseline.complete-candidate.json`，正式基线 SHA-256 为 `8a54a3d538774e3f095814f7bb5ef07593fff8995b801bf5bb2d35a3f2068433`。此前两份候选未采用。

主代理实际执行当前树门禁，退出码为 1：当前 2,043 条、冻结 1,591 条，未被豁免的新增或身份变化为 667 条，移除或身份变化为 215 条。后两项不能直接等同于新增和修复的业务缺陷数。失败前后基线字节不变；日志为 `root-mypy-current-gate.log`，执行命令和当前指纹分别保存在 `root-mypy-current-exit.json`、`final-gate-fingerprints.json`。新检查器及 CI 回归用例为 84 项通过，含另一任务补充的 11 项导入边界测试；最终命令与日志为 `root-mypy-ci-tests-command.json`、`root-mypy-ci-tests-final.log`。

mypy 的显式目标仍为 `backend/app`，沿用锁定版本的默认导入策略。两个非目标 `backend.scripts.backfill_*` 模块在专用 editable 环境中被作为安装包导入而静默；旧环境将它们当成本地导入，多报告了六条。两次都读取历史源码，不能把差异归因为读到当前源码。原 229 文件的 1,591 条诊断内容完全一致，六条从未进入豁免。本批没有宣称所有导入脚本均获检查；这项剩余覆盖债务应通过逐个加入明确脚本目标并修复诊断处理，不扩大到全部第三方库。

已恢复 Python 3.11.9、锁定运行依赖、mypy 1.20.1 和 Ruff 0.15.7 的独立验证环境。BLE001 门禁已真正执行，结果为当前 170 条、冻结 149 条，33 条新增或身份变化、12 条移除或身份变化，检查失败。冻结基线未改，不能声称全仓门禁通过。

发布任务的归因另在修改前副本上核对：修改前后均有 7 项 BLE001，原冻结基线对该文件没有登记。6 项身份完全相同，1 项因本批修复重试分支改变了 handler 指纹，受保护的 try 主体未变。本批没有新增宽泛 except，但这不构成该门禁通过；证据保存在 `backend-debt/ble001-attribution.json`。

当前 OpenAPI 静态扫描为 115/287 个操作有字段结构，其中包含其他任务增加的四个端点；本批贡献三个。该比例仅代表扫描器识别的响应结构，不代表全系统正确率。

## 交付与边界

本批代码集中在 `backend/app/tasks/data_update_center.py`、产品损益路由及 schema、`frontend/src/api/balanceMovementClient.ts`、产品损益模型和各自回归测试。类型门禁另涉及脚本、基线、CI 及检查器测试。测试环境与操作说明同步在 `docs/TESTING.md`。

GitNexus 对余额客户端聚合入口给出 CRITICAL，修改前已提示；直接调用位于 API composition 和首页补充客户端，均有测试。发布任务与利差模型的局部影响较低，仍核对了当前定义、调用及页面消费者。索引不能覆盖所有并行改动，因此没有把低风险或零调用当作无影响证明。

本批未做正式业务对账、真实更新或发布恢复、托管 CI 执行及部署验收。热点职责拆分仍是待验证收益的候选；其他页面契约、存量类型问题、治理记录逐页签认及多人身份接入未因此自动关闭。后续应按具体工作流接续，不启动无证据的平台重构。

下一批应按工作流归属处理 667 条未豁免类型身份和 33 条 BLE001 身份，先核对真实触发条件与业务边界，再修类型或明确异常处理意图。只有既有问题真正消失且没有新增时才能收紧基线。导入脚本检查覆盖单独登记，不因本次门禁实现通过而关闭。

## 2026年10月1日审计后续修复方案

本节是新增批次，不修改上文 9 月验收结论。用户已要求制定修复方案并由 GPT-6.1-sol 执行；本批包含当前源码修复、隔离回归和确定的冗余清理。先恢复计算、契约与回执的一致性，再处理维护债务。业务历史重算、真实更新、运行发布、外部认证体系建设和 Git 提交推送不在本批执行范围。

接手时 HEAD 为 `124a3f2d5af5e299ef6b86edd9ab0b679468a09e`，工作树有 836 个已跟踪文件变更和 459 个未跟踪文件。审计依据是这些当前文件，不是 HEAD 的干净副本。执行代理必须保留他人改动，记录本批文件指纹或差异；先读根与路径规则，修改符号前做 GitNexus 影响分析并补查索引未覆盖的现源调用。高风险结果应说明影响和验证范围，不因此重复请求已有授权。

### 执行顺序与交付规则

由 GPT-6.1-sol 作为实现负责人，可将互不重叠的金融计算、后端契约与 Agent、前端、验证脚本分配给同模型子代理，明确文件归属；主代理只检查连接处和遗漏。复用已有 helper、schema、adapter、测试模块和 Python 3.11 验证环境。不得为局部修复重建平台、放宽守卫、提高债务基线，或把观察面提升为正式金融结果。

用户补充要求：不要过度防御式编程。实现只针对已经证明的失效条件；边界校验集中在现有可信边界，内部使用已成立的类型和不变量。禁止增加通用 fallback、重复判空、吞异常返回空值、无证据的重试、配置开关或通用框架；不为假设性的未来输入扩大兼容范围。优先删除或复用代码，只有多处现用调用确实需要时才提取局部 helper。金额精度、真实缺失语义、权限、写入隔离、原子发布及取消终态保护属于必要正确性约束，应以最小实现保留。类型夹具、依赖声明、文案等轻量改动复用现有检查，不另造镜像测试；尚未证实收益的历史读取优化和大型架构拆分维持后续项。

行为缺陷先把下述合成反例落入所属测试，记录当前代码失败，再实施最小修复并验证通过。每批结束更新本节状态和实际命令；不能把历史报告、测试文件存在、mock 检查或构建成功替代真实运行证据。必要验证受阻时记录具体阻断，继续其他独立项。

| 工作范围 | 完成条件 | 实际状态 |
| --- | --- | --- |
| 曲线原始节点与重复拟合 | 认可节点保留，跨读取路径一致 | 源码与隔离回归通过；保留重复拟合 |
| 主页资产收益率及净息差 | 空分类输入下 SQL 与 Python 一致 | 源码与隔离回归通过 |
| 宏观刷新产物发布 | 并发运行不混用产物或回退最新指针 | 源码与隔离回归通过 |
| 高级归因契约 | Numeric 与不可用状态正确传递 | 源码与隔离回归通过 |
| 前端类型与读取客户端 | 类型检查通过，共享读取保护有效 | 源码、类型与隔离验收通过；fixture接手已有 |
| Agent 取消及失败回执 | 子进程停止可验证，无效结果立即失败 | 源码与116项隔离回归通过 |
| 回归选择器与债务门禁 | 关键反例在合并前执行，基线扩大可检测 | 选择器、最终mypy/BLE001均通过；基线未变 |
| 冗余与调度交付 | 确定的重复被收敛，现用入口可追溯 | 限定旧链、调度隔离回归与入口核对通过；未提交 |
| 需裁决的金融口径 | 保留证据和裁决事项，不擅自改变历史语义 | PENDING |

### 曲线节点及收益率计算

`backend/app/core_finance/bond_analytics/common.py::build_full_curve` 认可 `1M`、`15Y`，却在固定 13 点输出时丢掉它们。`bond_analytics/read_models.py::_CurveRateLookup` 与 `core_finance/pnl_bridge.py::_CurveRateLookup` 随后重新拟合，导致原始节点信息损失。先保留所有已认可源期限；只在证明保持既有其他结果时收敛重复拟合，不顺带改变 DV01 面值基数、付息频率或插值方法。

最小反例为百分数曲线 `{1Y:2, 5Y:2.5, 10Y:3, 15Y:4, 20Y:3.5, 30Y:4}`。直接曲线引擎在 15 年返回 4%，现用两个读取路径返回约 3.35691611%。仅将 15Y 改为 4.1%，当前读取变动仅约 0.859871bp。验收必须包含原始 15Y、1M 节点再现、非线性曲线、缺失节点插值、两条读取链一致性及既有线性黄金结果；节点值与变化应来自独立预期，不复制实现作为 oracle。按当前规则评估缓存/规则版本是否须更新，并记录未做历史重算。

`backend/app/repositories/liability_analytics_repo.py::fetch_yield_kpis_for_dates` 的 SQL 漏掉 `core_finance/liability_analytics_compat.py::is_interest_bearing_bond_asset` 对空资产分类的排除。补齐分子与分母的同义过滤，复用现有归一化语义。用空分类 H 资产 100、利率 5%，同业资产 100、利率 3%，同业负债 100、利率 2% 的内存输入，当前 Python 得到资产收益率 3%、净息差 1%，SQL 得到 4%、2%。验收覆盖 None、空串、空白分类、真实零利率、缺失利率和已有 30 组边界，追踪 `executive_service.py` 主页与负债页调用，但保持 E1 披露边界。

### 宏观产物与高级归因

`backend/app/tasks/macro_toolkit_refresh.py::run_macro_toolkit_allocation_refresh` 在退出锁后才捕获产物和发布 latest。修复应使写入、快照和发布属于同一完整互斥范围，并核对 `api/routes/macro_toolkit.py` 单脚本入口、`services/macro_toolkit_service.py` 整链入口对相同目录的写入。优先复用已有锁，避免嵌套同锁死锁；确需并行时采用各运行独立目录和顺序约束。测试要真实交错两个隔离运行，覆盖写完但尚未捕获、捕获失败、发布失败及不同入口竞争；断言 manifest 内容属于该 run、指针不会退回旧运行，不能只模拟锁直接抛错。不得运行真实供应商脚本。

`backend/app/services/advanced_attribution_service.py` 当前将 PnL 桥的 Numeric JSON 直接 `str()`，丢弃 availability，并把 `quality_flag` 算作归因组件。按真实 `PnlBridgeSummarySchema` 适配金额与缺失状态，逐组件计算 available/blocked；真实零和缺失占位零必须不同。同步核对 `get_return_decomposition` 是否透传显式数据路径，避免混读。回归从真实 schema 构造上游响应，覆盖曲线不可用、部分可用、全缺失、零值及异常。前端余额页当前主要显示状态和提示，验证其披露一致，不宣称页面金额已有错误或改动正式工作簿。

### 前端类型、客户端与恢复入口

`frontend/src/test/CampisiAttributionPanel.test.tsx` 的闭合 fixture 漏掉 `formal_closure.residual_ratio`，当前 typecheck 报 TS2741。按夹具的零残差语义补齐字段，不降低类型约束。

`frontend/src/api/homeSupplementalClient.ts` 私有请求函数绕过 `transport.ts` 的 envelope 校验和默认超时。复用现有 transport，并保留调用方 signal、错误详情和延迟加载要求。与 `bondAnalyticsClient.ts` 中 token 完全相同的 concentration、credit spread migration、portfolio headline 三组归一化应落到同一个局部领域实现，避免把重型模块拉进首屏。回归覆盖 null result_meta 被拒绝、200 非法信封、timeout、abort、HTTP 错误详情及现有正常结果；核对首页实际 deferred 分发入口和启动包守卫。

`OperationsAnalysisPage.tsx` 在证据缺失时推荐 `/source-preview`，但该路由是明确保留的 placeholder。将动作接到已有可用数据中心并保留失败来源上下文；若现有入口无法承接，则准确披露未开放状态。测试触发错误/空结果并核对实际目标路由，不启用保留功能。7 个生产模块直接使用 dayjs 而 package.json 未声明直接依赖，应在核对 lockfile 当前版本后补齐声明，避免无关升级。

### Agent 生命周期

Dexter 未接入已有 `cancel_event` 协议，CLI 使用阻塞 subprocess.run。沿用 Hermes 和监督循环的既有取消约定，让 CLI 子进程能够停止并可验证，覆盖 Windows 进程树、正常退出、超时、取消与重试；bridge 按已有协议明确停止是否确认，不能把本地线程返回当作远端已停。禁止调用外部模型进行验证。

`agent_run_service.py` 对 executor 的 None、错误形状或无效 envelope 只告警返回，留下 running。改为立即经过现有失败状态和审计收口，保护取消/成功并发终态不被覆盖。用内存和隔离存储证明无效返回后立即 failed、有对应审计，审计失败维持既有 fail-closed 行为。

run/delta 全历史复制属于已确认增长债务。先测量隔离合成历史下实际读路径；若已有缓存可最小化扩展，则提供按 run_id/sequence 的定向读取并验证追加、压缩、跨进程文件替换后的正确失效，保持锁和 owner 校验。没有足够收益证据时保留为待优化项，不新建存储平台。开发身份头信任的多人部署风险只记录当前边界，本批不建设认证体系或放宽权限。

### 门禁与验证环境

补齐 `scripts/backend_release_suite.py` 和 `scripts/check_caliber_gate.py` 的精确选择关系，至少覆盖 `test_system_online_read_boundary.py`、`test_system_online_publication_concurrency.py`、`test_system_read_publication_process_crash.py`、`test_campisi_formal_bridge_coverage.py`、`test_product_category_read_boundary.py` 及发布选择器自身测试。保证测试文件自身变化和对应生产路径变化均能选择必要用例，继续保持既有 acceptance 排除规则，不把标记覆盖等同于正式化。

BLE001 当前逐身份检查有效，但基线本身可同步扩大。参考现有可信 base/豁免模式核对 PR 基线变更，使未经明确例外的新身份失败；不要新增庞大审批框架。覆盖直接增加身份、同数量替换、正常删减和基线读取失败，禁止提高基线。前端覆盖率在明确的定期/完整 CI 路径启用并保留报告，避免把未执行的历史阈值当现有保证。去掉全量 pytest 对 `test_duckdb_write_boundary.py` 别名的四项重复收集，保留必要兼容入口。

仓库默认 `.venv` 是 Python 3.14.2，当前 mypy 和 BLE001 基线要求 3.11。本批先查找并验证现有 3.11 环境、editable 源路径、锁定依赖和守卫，复用后执行；不能只因路径存在就认定正确。找不到可用环境时可建立本任务唯一隔离环境，但不得替换日常运行 venv；不能取得合格环境则如实报告门禁未验证。存量基线为 mypy 1591 条、BLE001 149 条，这些不是当前扫描值，禁止为全绿批量抬基线。

### 确定冗余与调度交付

前端审计发现 46 个生产入口不可达候选，分别为 12 个无模块引用、25 个仅测试引用、9 个被其他不可达模块引用。从 `BondAnalyticsOverviewRateChart`、`BondAnalyticsHeadlineZone`、`MarketDataMacroSeriesDeck` 三条旧链开始，重新核对 main、路由、动态 import、测试和保留计划。只删除已被实际入口替代且无保留用途的实现，并迁移必要行为断言；保留 SourcePreview、stock pretrade 及任何用途不明模块，不能按 46 的数量目标清理。

日常维护脚本与 `run_scoped_stock_recovery_20260924.ps1` 共享 1117 行，相似度约 97.5%；PIT 入口还解析 host AST 并 Invoke-Expression。核对一次性脚本的外部调用和恢复用途，优先把当前各入口真正共用的进程识别/维护逻辑放入已有合适模块或一个局部 helper，三个入口直接调用。保留日期特定恢复行为及进程归属、写锁、取消和恢复守卫，使用已有 PowerShell harness 验证，禁止停启真实 API/worker。

本机注册的 MOSS-DailyDataRefresh 使用 `run_daily_data_refresh_host.ps1`，MOSS-DataUpdateQueue 使用 `drain_data_updates.ps1`，当前均未跟踪。应核对安装器与实际入口一致，列出完整交付依赖和配套测试；不得 git add 全工作区。源码纳管与提交状态要如实记录，本批不擅自提交他人改动或宣称未提交文件可从 HEAD 重建。

宏观路由反向 builder 依赖、18 个脚本导入 MCP 单体、约1959行备用金融模块列入后续维护范围。本批仅在已验证的缺陷修复必需时调整连接，不为消除文件行数大拆架构。备用模型的动态/外部使用、保留人和退役条件未核实前维持原状。

### 需要业务裁决的边界

Campisi 的实际付息方式迁移会改变历史模型归因，`docs/calc_rules.md` 已要求 owner 裁决及全期回归/重算。无到期日的工作簿短期限代理与负债页“到期日未提供”分类也存在不同用途。执行代理应修正“两个口径一致”的不实披露并补充当前差异证据，保留算法行为，形成最小裁决事项；不得用统一 helper 顺带改历史金融口径。这些条目维持 PENDING，不阻塞其他已授权修复。

### 本批验收回执

执行中更新此处，写明每项实际修改、改前失败与改后通过、精确命令及其环境、必要浏览器或启动包检查、残余问题。主代理需要检查金融输入到服务/页面的连接、锁覆盖的所有写入口、Agent 终态竞争以及 CI 选择器；不重复无变化的全部测试。最终区分源码修复、隔离验证、业务重算和运行发布，仅完成并核验的层次可称通过。

实施使用现有 `backend/.venv/Scripts/python.exe`，已验证 Python 3.11.9、editable 分发 `moss-agent-analytics-os-backend` 指向 `file:///F:/MOSS-V3/backend`，`backend.app.__file__` 指向当前工作区；Ruff 0.15.7、pytest 9.0.3、DuckDB 1.5.2。`uv pip check --python backend/.venv/Scripts/python.exe` 检查 82 个已安装包并通过兼容性检查；该结果不等同于重新执行 frozen 安装。测试显式启用 `_pytest_duckdb_guard`，本批后续临时根统一为 `.codex-tmp/debt-repair-20261001`。

门禁反例首先验证了 12 项读取、发布与测试自身选择遗漏，改前均失败；BLE001 的可信 PR 基线新增、同数量替换、读取失败与正常删减四例在改前因缺少可信基线参数失败。修复后命令 `backend/.venv/Scripts/python.exe -m pytest -p _pytest_duckdb_guard tests/test_backend_debt_gate.py tests/test_backend_release_suite.py tests/test_caliber_gate_mapping.py -q` 取得 178 项通过。发布套件保留 `not excluded_surface_acceptance`，选择器补入在线读取、并发、进程崩溃、Campisi 桥覆盖及产品分类只读边界。BLE001 在 PR CI 使用 checkout 的完整历史和不可变 `github.event.pull_request.base.sha`，工作树基线新增身份直接失败，未修改基线。完整/定期前端 CI 使用已有 `npm test -- --coverage` 并上传 coverage；本机未执行完整覆盖率扫描，不把配置写入视为 CI 已跑。DuckDB 写边界别名保留导入兼容，设置 `__test__=False` 后与所属模块联合 collection 为 30 项，不再重复四项。

宏观验证出现了一次实施错误，必须保留其边界。最初新增 `test_artifact_capture_keeps_all_writer_entries_excluded[script]` 调用旧的实际单脚本函数，启动 `risk_parity_cn.py`、`argv=[]`，输出目录为随后被现有 pytest 清理机制清理的 `pytest-basetemp-44584` 下隔离目录；该测试没有显式 DuckDB 路径，不能证明没有读取默认库。随后 `macro-chain` 会话的旧链测试仍 mock 公共函数，改为内部执行后 mock 没有命中。`test_macro_toolkit_script_chain_manual_run_rejects_concurrent_run` 使用合成 `moss.duckdb`；`test_macro_toolkit_script_chain_manual_run_reconciles_expected_outputs` 未显式配置库，实际运行链的本地脚本把九个 CSV 写入 `.codex-tmp/debt-repair-20261001/macro-chain/test_macro_toolkit_script_chai3/macro_toolkit_output`：merrill clock、crisis score、bond futures、bond signals 和 crowding 的历史/最新产物。该目录及 guard 回执保留，误执行不计入验收。

当前源码可确认这些宏观脚本通过 `MOSS_MACRO_TOOLKIT_OUTPUT_DIR` 写隔离输出与其资产子目录；`system_sources.py` 的两个连接和 crowding 连接均显式 `read_only=True`，本地 `toolkit/akshare.py` 为读取系统序列的 shim。不能确认的默认库读取仍作为本次验证边界，不宣称完全隔离。误执行会话已结束，按 PID 48256、44584 及其子进程、脚本路径核对，没有残留进程；没有停止任何日常 API/worker。后续 refresh 非 integration 与 script chain 测试已增加测试专属 fail-fast subprocess 替身，修正现有 mock 指向内部执行函数；该替身只在测试，未加生产防御框架。

宏观源码修复由 `macro_toolkit_service.py` 的现有链锁统一约束实际 `output_dir.resolve()`；单脚本、整链及 allocation 不再使用不同治理目录形成互斥假象。公共单脚本入口持锁，批次内复用唯一 `_run_macro_toolkit_script_unlocked`；allocation 的脚本执行、捕获、不可变 manifest 与 latest 发布在同一锁内。路由冲突返回 409。GitNexus 对 allocation 入口给出 HIGH，直接依赖 16 个测试；公共 runner/chain 的 LOW 零调用未覆盖现源，补查 `_run_step`、链内和 HTTP 路由调用作为覆盖缺口证据。最小修改未拆宏观 builder 或 MCP。

修正测试隔离后命令 `backend/.venv/Scripts/python.exe -m pytest -p _pytest_duckdb_guard --basetemp=.codex-tmp/debt-repair-20261001/macro-final-fixed tests/test_macro_toolkit_refresh.py tests/test_macro_toolkit_scripts.py -q -k 'not real_performance and (test_macro_toolkit_refresh or script_chain or run_script_ or single_script_)'` 得到 33 项通过、160 项不选。覆盖写后未捕获的真实线程交错、不同治理参数的批次/整链/单脚本竞争、捕获失败与发布失败、旧 manifest 不变、后续 latest 不回退、HTTP 409及原有输出目录隔离。真实供应商/日常刷新 integration 明确不执行。这组数量包含此前单独取得的 21/13 项，不累加。

类型门禁最初实际扫描得到 mypy 当前 1298 条、基线 1591 条，新身份五条均在 `scripts/dev_runtime_control.py`：fcntl 的三个平台属性、空集合类型和 HTML src 可空类型。该文件是 daily/PIT/recovery 维护入口直接依赖，保留接手源码后仅用 `sys.platform == 'win32'` 表达已有平台分支、`actual: set[str]` 和 src 局部变量收窄类型，未增加检查或 fallback。GitNexus operation_lock 风险 MEDIUM、直接调用六处，verify_build LOW、直接调用 frontend_plan 与交接快照；parser 为 HTMLParser 动态回调，补查现源。命令 `backend/.venv/Scripts/python.exe -m pytest -p _pytest_duckdb_guard --basetemp=.codex-tmp/debt-repair-20261001/runtime-control tests/test_dev_runtime_control.py tests/test_dev_runtime_maintenance_scripts.py -q` 得到 38 项通过。

Agent 收口前的 `backend/.venv/Scripts/python.exe scripts/check_mypy_baseline.py` 为当前 1293/基线 1591、新增或变化 0、消失或变化 298；`backend/.venv/Scripts/python.exe scripts/check_ruff_ble001_baseline.py` 为当前 129/基线 149、新增或变化 0、消失或变化 20，均通过，未更新任何基线。`data_update_center.py` 的 publication-only 捕获仅补齐既有持久失败边界的 reasoned noqa，运行逻辑未改；高级归因将上游读取异常收窄，不以新身份扩大冻结债务。CI 三文件回归在新增金融选择关系后最终再跑仍为 178 项通过。本批脚本、宏观 task/routes、相关测试的 Ruff 检查通过；宏观 service 有 67 项存量诊断、DuckDB 导入兼容别名有四项存量诊断，经 before 源码通过 Ruff `--stdin-filename` 对比同配置，数量与诊断不变，不声称这些文件全绿。

后续连接检查发现 CI 的受控静态镜像需随成员更新，已将 `docs/ci-release-suite.md` 从 41 项同步为 48 项，并把 Dexter、run lifecycle、cancellation hook 三个修复模块加入合并前 Agent harness；顺序与实际清单一致。原 `test_ci_workflow_contents.py` 的前端断言同步为保留独立执行条件、仅 schedule/main 开 coverage 的行为。命令 `backend/.venv/Scripts/python.exe -m pytest -p _pytest_duckdb_guard --basetemp=.codex-tmp/debt-repair-20261001/ci-workflow-verified tests/test_ci_workflow_contents.py -q` 得到 15 项通过；发布失败注释的两项现有 recovery 回归通过，未重新执行财务计算。`node scripts/audit_encoding_integrity.mjs` 扫描 4717 文件、U+FFFD 0/0，无新编码损坏。

临时清理仅列本代理已结束验证的九个明确目录，核对共 39,543,314 字节可重建文件，计划先保留 guard receipts，再使用原生 PowerShell `Remove-Item -LiteralPath`。执行工具的自动安全审查以 `blocked by policy` 拒绝该清理命令，命令未执行，未改用其他工具绕过。相应测试目录仍保留；before 源码、宏观误执行 `macro-chain` 目录及唯一回执本来就不在删除范围。

前端按现源复用 transport 与局部领域归一化。新增 `bondAnalyticsNormalization.ts` 收敛 concentration、credit migration 与 headline 三组既有实现；两个读取 client 调用它，首页不导入重型领域模块。`homeSupplementalClient` 使用 transport 的信封校验、默认 timeout 和 json-detail，保留 signal。经营分析恢复动作接现用 `/platform-config`，保留来源披露。dayjs 按现有 lockfile 的 1.11.21 补直接依赖。Campisi fixture 的四处 residual_ratio 在接手现源已有，不记作本轮修改。

前端改前 `npm run test -- src/test/HomeStartupClient.test.ts src/test/OperationsAnalysisPage.test.tsx` 得到五项失败、15 项通过，证明非法信封两例、timeout 与空结果/读取失败恢复入口。改后命令 `npm run test -- src/test/HomeStartupClient.test.ts src/test/OperationsAnalysisPage.test.tsx src/test/OperationsAnalysisPage.governed.test.tsx src/test/BondAnalyticsClient.test.ts src/test/transport.test.ts src/api/balanceMovementClient.test.ts src/test/StartupPerformanceGuards.test.ts src/test/CampisiAttributionPanel.test.tsx` 得到 143 项通过。旧链仅删除已由实际入口替代的 OverviewRateChart、HeadlineZone 和 MacroSeriesDeck/ThemeCard 链共八个实现及专属测试文件，同步 debt 保护条目、CSS 配置、page contracts 和镜像测试。替代入口回归 `npm run test -- src/test/BondAnalyticsInstitutionalCockpit.test.tsx src/test/BondAnalyticsView.test.tsx src/test/MarketDataPage.test.tsx src/features/market-data/lib/marketDataMacroThemeGroups.test.ts` 为 96 项通过；`tests/test_debt_baseline_updates.py` 为 72 项通过，不提高债务基线。typecheck、lint 与六段 debt:audit 均通过，lint 保留 PnlByBusiness 原警告。隔离 real Vite build 和 home startup bundle guard 通过；1440×900 纯 mock 浏览器核对恢复 href/source 披露通过，截图在本任务 frontend 目录，未验证日常真实 API。

Agent 仅修改 `dexter_agent_service.py`、`agent_run_service.py` 及三个所属测试模块。Dexter CLI 接入现有 cancel_event，使用有界 communicate，按本机 Windows 进程树停止、wait 和 finally 关闭 PIPE；取消不触发 fallback 审计。bridge 取消保留远端停止未确认的边界。Run service 将现有 envelope 校验移到原执行异常收口内，None、错误形状与无效模型返回立即走既有 failed 和 audit；保护 cancelled/completed 终态，不建立第二个失败框架。现有 tasks resolver/inspect hook 已传 event，无须改 task。

Agent 改前命令 `backend/.venv/Scripts/python.exe -m pytest -p _pytest_duckdb_guard tests/test_agent_run_service_lifecycle.py tests/test_agent_run_cancellation_hook.py tests/test_dexter_agent_service.py -q -k 'invalid_executor_result or cancelled_dexter_request or dexter_cli_cancel or only_providers_declaring' --basetemp=.codex-tmp/debt-repair-20261001/agent/pytest-before` 得到六项失败、94 项不选。最终四模块加 `tests/test_agent_run_worker.py`，使用 `-q -W error::ResourceWarning --basetemp=.codex-tmp/debt-repair-20261001/agent/pytest`，116 项通过，无 ResourceWarning。覆盖三种无效结果、cancelled/completed 竞争、审计写失败 fail-closed，以及本机合成 Python 父子树取消、正常/timeout 句柄关闭、bridge cancel 成功/错误均不追加 fallback audit。审计存储本身不可写时沿原约定抛错并保留 running，不宣称该情形可持久化 failed。Windows 已实际验证，Linux 停止/僵尸分支待 CI；未调用真实 Dexter 或外部模型。两 production 与三 test Ruff 通过，Agent 与前端的 before 和 source manifest 均保留。

主代理汇合复核对照 before 检查 frontend transport/normalizer 与宏观锁，并检查金融 Numeric/availability、显式路径、缓存版本与 PENDING 披露，以及 Agent failed/audit 复用、取消管道关闭和 bridge 取消分支；没有重复无变化的全部测试。额外独立复核代理因总线程限制未能创建，不声称完成独立代理复审。本批只证明源码及所列隔离行为，不证明日常 URL、业务重算或运行发布。

金融最终修改 `common.py` 保留认可原始节点，`pnl_bridge.py` 与 `pnl_bridge_service.py`、`bond_analytics_service.py` 的读取缓存追加 `cv_source_nodes_v2`，不改变原始事实物化版本，不做历史重算；重复拟合保留，以免改变没有源节点的非线性结果。`liability_analytics_repo.py` 在 SQL 分子、分母均排除 None、空串和空白分类。高级归因版本由 v0 到 v1，按真实 Numeric 优先读取 `raw_text`，保留 precision 和真实零；quality_flag 不再列为组件，缺失、partial 或没有结构化 availability 的市场效应 blocked。显式 DuckDB/治理路径贯穿收益分解，绕开默认结果缓存。新增 consumer symmetry 测试覆盖两条读取链的 15Y/1M、非线性及缺失插值；现有 linear goldens 保留。相关反例在改前确认原始15Y节点未再现、源10bp变化被削弱，以及空分类SQL/Python差异；真实 DTO 反例确认 dict 被当作金额字符串、缺失被当可用，改后均通过。

金融窄验证命令均为 `backend/.venv/Scripts/python.exe -m pytest` 且启用既有隔离守卫。`tests/test_yield_curve_consumer_symmetry.py tests/test_repository_support_contracts.py -k 'read_curve or home_nim_rate_boundaries' -q` 为 122 项通过；`tests/test_bond_analytics_service.py -k return_decomposition -q` 为 10 项通过；`tests/test_advanced_attribution_contract.py tests/test_advanced_attribution_runtime_cache.py -q` 为 15 项通过，无 deselect。工作簿 FX 夹具补合成输入的 observed_trade_date，未改正式 FX 守卫。宽命令 `tests/test_pnl_bridge_with_curve.py tests/test_pnl_bridge_curve_effects.py tests/test_bond_analytics_curve_effects.py tests/test_repository_support_contracts.py -q --tb=short` 为 193 项通过、一项准备夹具失败；修正为先有效物化再注入原 vendor_name 冲突后，`tests/test_bond_analytics_curve_effects.py -k corrupt -q` 单独一项通过。原读取 fail-closed 断言不变，复用其余 193 项证据，不声称一次 194 项全绿，也不累加与窄验证重叠的数量。金融修改文件 Ruff 全通过。

金融宽验证也出现了隔离失误。旧 fixture 只 monkeypatch 父进程 VendorAdapter，当前精确读取通过 `subprocess.Popen` 启动另一个解释器，补丁没有跨进程。节点 `test_return_decomposition_marks_result_meta_stale_when_aaa_curve_uses_latest_fallback` 在准备阶段启动真实 `backend.app.tasks.yield_curve_fetch`，合成请求为 cdb、anchor_date 2026-03-01，179.828 秒超时；是否发出外部网络请求无法确认，超时不算算法反例，也不能证明未调用供应商。测试数据库及治理目录属于 `finance-wide*` 临时根，无成功供应商结果。实施者按精确命令行和父子归属停止了自己的测试进程树，未停止日常进程。现将 fixture 替换点改为 `fetch_curve_snapshot_with_timeout`，fail-fast 在 Popen 前阻断，并用标为 sv_materialization_preparation 的合成节点完成准备后移除，保留原缺失/fallback断言。全部测试进程已结束；事故证据在 `finance-vendor-attempt.txt`，保留不删。

调度将真正共用函数放入 `scripts/scheduling/market_refresh_host_common.ps1`，日常 host 从 1163 行降为 240 行、20260924 recovery 从 1130 行降为 220 行，PIT 直接 dot-source 并删除生产 AST/Invoke-Expression 加载；helper 只有函数定义，解析无错误。历史 recovery 的严格 Get-ApiProcessTree 覆盖、日期日志与 `G:/MOSS-stock-recovery/20260924/run_scoped_recovery.ps1` 外部调用保留。安装器的日常动作改为实际 `run_daily_data_refresh_host.ps1`，已有 VendorSourceIp 参数由 wrapper 透传。只读任务查询核对 MOSS-DailyDataRefresh 与 MOSS-DataUpdateQueue 的动作/工作目录一致，没有重注册或启停真实 API/worker。

调度命令 `backend/.venv/Scripts/python.exe -m pytest tests/test_market_refresh_host_runtime.py tests/test_choice_stock_pit_request_host.py tests/test_daily_data_refresh_scheduler.py -q` 为 67 项通过、446.73 秒；`tests/test_register_scheduled_tasks.py tests/test_data_update_queue_launcher_logging.py` 为九项通过。安装器与 publication-only 最终子集另有 12 项通过，与前述重叠，不累加。完整交付需包括本轮的三个 host、common helper、register installer，以及 `scripts/scheduling/daily_data_refresh.ps1`、`install_data_update_queue.ps1`、`drain_data_updates.ps1`、`pit_request_process.py`；开发运行依赖为 `scripts/dev-env.ps1`、`dev-python.ps1`、`dev-runtime-common.ps1`、`dev_runtime_control.py`、`dev_postgres_cluster.py`、`dev-api.ps1`、`dev-agent-api.ps1`、`dev-keepalive.ps1`、`balance_movement_freshness_watch.py`。日常链还依赖 `backend.app.tasks.system_read_market_publication`、`backend.app.tasks.stock_limit_price_daily_refresh`、PIT/queue 依赖 `backend.app.tasks.data_update_center` 与 `data_update_choice_stock_pit`，六个脚本为 `choice_stock_daily_refresh.py`、`run_livermore_daily_pretrade_refresh.py`、`stock_adjustment_factor_daily_refresh.py`、`macro_toolkit_freshness_refresh.py`、`refresh_tushare_news_backup.py`、`macro_toolkit_daily_chain.py`。三个 host、helper、queue installer/launcher、pit_request_process 和相应隔离测试目前仍有未跟踪文件；本批没有 git add、提交或推送，不能称这些文件由 HEAD 可重建。

Agent 的最后类型检查发现两处 object.model_dump 新身份；仅按已有 AgentExecutor 契约用 `cast(AgentEnvelope, outcome.get('envelope'))` 收窄类型，运行时 isinstance/model_validate、failed/audit完整保留，无 ignore 或重复校验。此静态修改不重复116项行为测试。所有源码稳定后，最终 `backend/.venv/Scripts/python.exe scripts/check_mypy_baseline.py` 为 1292/1591、新增或变化 0、消失或变化 299；最终 `backend/.venv/Scripts/python.exe scripts/check_ruff_ble001_baseline.py` 为 128/149、新增或变化 0、消失或变化 21，均通过，基线未变。

未执行项仍维持清楚边界：Campisi 实际付息方式迁移和缺到期日用途差异为 PENDING，仅在 calc_rules 与余额工作簿披露中纠正“口径一致”，算法保留；run/delta 全历史读取优化、宏观 builder 反向依赖、MCP 单体拆分、备用金融模块退役为后续维护。本轮不构建外部认证体系、不放宽开发身份头权限，不做业务重算或日常运行发布。前端隔离 Vite 已停止，所有测试进程已结束；before、source manifests、浏览器截图和误执行证据保留。唯一未完成的任务清理由自动安全审查拒绝，属于环境阻断，不影响已列源码与隔离验收结果。

### 提交前 review 修正

独立 review 又确认三处本轮问题，已由原 GPT-6.1-sol 实施者修正。高级归因的收益分解上游实际经 `_bond_analytics_api_payload` 返回 Q8 字符串，只有 PnL bridge 使用 Numeric；原适配错误地让两者都经过 Numeric 校验。现在收益分解保持真实字符串，bridge 保留原 Numeric/raw_text 精度处理，测试的收益分解 fixture 经过真实 serializer，不增字符串与 Numeric 混用兼容层。负债 SQL 原默认 trim 不排 tab、换行等空分类，现在两个金额条件共用显式的 Python `str.strip` 全部29个空白字符作 trim 第二参数，原利率与分类条件不变；内存参数覆盖每个字符、CRLF 和夹有 tab/CRLF 的非空 AC。

Windows Dexter 的 launcher 已退出而子进程继承 PIPE 时，原 communicate reader 线程让 finally 关闭等待 reader 锁，导致取消无界。临时文件方案会过早截断晚输出，因此仍保留 PIPE，仅 Windows 使用带正确 HANDLE/BOOL 签名的 PeekNamedPipe 查询可读字节，再用同步 os.read 收集完整 bytes 后 UTF-8 decode；broken pipe 109 表示所有继承写端关闭，其他错误抛出。无 reader 线程关闭锁，所有 EOF 但根仍存活时继续接受 cancel/timeout。根退出后的 taskkill 不能确认子树停止仍披露 stop_unconfirmed，不引入 JobObject 平台。

review 前六个源码/测试快照保存在 `.codex-tmp/debt-repair-20261001/review`。GitNexus 对 `_build_upstream_summaries` 为 LOW，直接依赖 bundle 和余额路由；SQL 动态调用不在图中，补查 executive `_fetch_nim_context_uncached`；新增 Dexter private runner 不在旧索引，补查 `run_dexter_agent` 唯一调用及所属测试。改前金融命令 `backend/.venv/Scripts/python.exe -m pytest -p _pytest_duckdb_guard tests/test_advanced_attribution_contract.py tests/test_repository_support_contracts.py -q -k 'return_market_zero or upstream or home_nim_rate_boundaries' --basetemp=.codex-tmp/debt-repair-20261001/review/pytest-finance-before` 得到107项失败、946项通过、43项不选；其中三个真实字符串反例失败，其余为空白过滤反例。改后相同选择加 `--tb=short` 并使用 `review/pytest-finance-after` 得到1053项通过、43项不选。数量为扩展参数化单独一批，不与前文金融宽组累加。

Windows 改前 `backend/.venv/Scripts/python.exe -m pytest -p _pytest_duckdb_guard tests/test_dexter_agent_service.py -q -k exited_launcher --basetemp=.codex-tmp/debt-repair-20261001/review/pytest-dexter-before` 为取消一项失败、正常晚输出一项通过；取消线程1.5秒后仍未返回，finally 只终止该合成测试的 child。改后 `backend/.venv/Scripts/python.exe -m pytest -p _pytest_duckdb_guard tests/test_dexter_agent_service.py -q -W error::ResourceWarning --tb=short --basetemp=.codex-tmp/debt-repair-20261001/review/pytest-dexter-full` 为47项通过，无 ResourceWarning，含父先退出后的取消、晚输出分段中文完整性、所有 EOF 后根仍存活的超时及既有父子树取消。没有调用真实 Dexter、供应商、宏观脚本或默认数据库。

此次实际差异为 `backend/app/services/advanced_attribution_service.py`、`backend/app/repositories/liability_analytics_repo.py`、`backend/app/services/dexter_agent_service.py` 及对应 `tests/test_advanced_attribution_contract.py`、`tests/test_repository_support_contracts.py`、`tests/test_dexter_agent_service.py` 六个文件；目标 Ruff 全通过。再次必要门禁 mypy 1292/1591、新增或变化0，BLE001 128/149、新增或变化0，均退出0且基线未变。该实施者未 stage 或提交，提交范围由主代理另行收口。

修正后两名独立 reviewer 分别通过金融契约/空白过滤和 Windows 管道生命周期复核，限定范围未发现新的可行动缺陷。金融额外纯内存核对确认显式29字符集合等于当前 Python.strip 集合、SQL 参数正确、非空分类保留；Windows 复核确认晚输出与分段中文保留，EOF 后根进程存活仍受取消/超时约束。主代理核对六文件 after 指纹均与交付 manifest 一致，复用已执行测试，不重复整组验证。

提交尚未执行。工作树共有1295条状态项，其中432条未跟踪，索引为空；40个具有本批 before 的变更路径中，19个 before 与 HEAD 一致、19个已包含接手改动、2个在 HEAD 中不存在。部分 Agent、前端数据更新中心、CI 和调度修复依赖尚未纳入 HEAD 的前置实现，金融部分也缺完整接手快照。当前验证针对工作树，不能据此保证只摘取本批差异得到的提交树可运行。已向用户请求选择是否连同必要前置改动审查并提交，或先交付可独立拆出的部分；在范围明确之前保留全部改动，不整体暂存，不声称已提交。后续实际提交仍需对候选树闭合依赖、执行相关验证及 GitNexus change detection。
