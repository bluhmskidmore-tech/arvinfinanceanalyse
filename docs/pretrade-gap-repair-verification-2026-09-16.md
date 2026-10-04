# 盘前补齐分支与宏观写入协调验收（2026-09-16）

用户在得知全局仍不可正式切换后同意继续。当前交付是核实并验证旧失败调用真正使用的 Tushare gap-repair 分支，再依据精确日期的当前覆盖证据决定必要恢复；不以新增测试替代真实盘前或原五域在线验收。本轮采用 goal-based 工作方式，最多三次执行复核，同时最多三个子代理，由 Sol 实现、Luna max 独立核验、父代理最终验收。

## 起点和不变边界

沿用 `docs/pretrade-live-recovery-2026-09-15.md` 的真实异常栈、已成功的唯一一次 daily_basic 身份查询及已接受的三项主源隔离测试，不重复这些真实操作。原失败日和历史起日均为 `2026-09-15`，跨日不构成扩大补算范围的依据。8 月 31 日成功财务和成功 bootstrap 禁止重放；不改公式、成熟度、权限、网络、调度或全局开关，不中断正常服务、不提交、不清理。

Luna 的独立起点见 `.codex-tmp/pretrade-gap-repair-20260916/start-state.json`。北京时间 08:46，正常 API／前端健康均为 200，正常发布发现接口为 `enabled=false`，活动库元数据和完整 pointer 身份与上一轮相同。原 26 文件中 25 份匹配，`backend/app/services/market_data_livermore_service.py` 已发生非本轮计划内漂移：当前 SHA-256 为 `ad2f8bae9453700fe1da4b6013c295a687be1e0c3143fdf6002823b08bc29754`。该改动保留，不回退或顺手修改；其旧冻结验收不自动适用于当前版本。本轮直接使用的测试、materializer、task wrapper 和 macro service 仍匹配上一轮源码。

页面继续受 `GAP-STOCK-ANALYSIS-PAGE` 约束，只允许观察、复核和来源披露，不把恢复数据解释为交易批准。指标／血缘／目录 MCP 本轮仍不可调用，使用本地页面合同、既有任务代码、具名回执和原始日志替代。正式金融计算路径 `backend/app/core_finance/` 本轮影响为无。

## 第一次执行方案

原网页会话已核实可见 6 Pro，并返回 PLAN_READY。父代理只发送脱敏技术摘要，没有原始日志、银行数据、金额、私有地址、凭据或源文件上传。第一处代码修改只在 `tests/test_stock_refresh_isolated_execution.py`，复用已有任务、catalog 和 owned-storage 测试保护，新增成功和 daily_basic 失败两个用例。产品文件先保持不动。

必须验证真实参数映射，而不是把两个 flag 名称直接视为同义词：既有 CLI 将 `tushare_gap_repair` 转为 `allow_cross_era_backfill` 并传递显式 history_start_date，materializer 只有在两项同时满足时才进入 gap-repair。测试保留原 preflight、existing-key coverage guard、Tushare cache、实际物化和治理写入；Choice CSD 禁止调用，用独立 fake Tushare 响应原请求字段和日期。因子、overlay、后续盘前链和 broker retry 继续排除并保留具名哨兵。

非空 synthetic fixture 用于真正验证替换保护：目标日旧 Tushare observation 与区间外事实先落入测试拥有的临时库。成功时核对目标事实确实更新、区间外事实不变，以及实际成功审计和运行／完成治理回执；失败时在真实 `_daily_basic_by_key` 路径注入 ConnectionError，比较业务表的实际行，并核对允许新增的失败审计和治理记录。失败不等于零数据库写入。原 preflight 合法接受无库或缺表场景，本次选择非空 fixture 不改变该语义。

新测试不重现历史失败审计的操作系统占用错误；它验证临时库可写时真实 failure handler 的正确持久化行为。原错误证明仍来自旧日志。真实重试逻辑保留，仅在测试局部替换等待并核对次数，不为测试关闭正常重试或替换失败处理器。

GitNexus 正确项目 `moss-v3-main-current-20260809` 的 lastCommit 与 HEAD 相同。既有未跟踪测试 helper `_owned_storage_boundary` 的 upstream 查询返回 target-not-found、risk UNKNOWN，不能表述为零影响。现有调用均在这份单文件测试中，产品符号暂不改动；若测试揭示产品缺陷，先保留失败证明并对具体符号做影响分析，再决定最小修复。

最窄证明先运行该文件的 `-k gap_repair`，再用另一全新临时根运行完整单文件，均显式 `-p _pytest_duckdb_guard`；随后做定向 Ruff、编译及编码检查。Sol 冻结源码后，由 Luna 在新的独立临时根分别复验。等待实际结果，不预填通过状态。

## 当前覆盖证据的独立门槛

已有 Choice `refresh-status` GET 只返回所选视图的 latest/max 日期与全表统计，不能证明指定日 history、factor、limit、gate 的完整覆盖。其 freshness 规则允许一定日期偏差，也不能替代精确日期证据。该入口会打开所选只读库并使用进程内缓存，本轮没有调用；未伪造身份或改变正常 RBAC／运行归属校验。

父代理另行沿已知盘前依赖检查路径核对是否已有精确日期只读 GET。这个问题与合成分支证明分开，不为缺少证据直接重跑整链，不把旧封存 generation 当成当前活动库，也不做未经协调的活动库文件复制。若没有合格现成入口，保留具体缺口，不在首改里另造读取框架。

已查明的既有盘前 GET 返回工作台、策略合流或封存资格，不是完整源表检查。`scripts/run_livermore_daily_pretrade_refresh.py::inspect_livermore_daily_refresh_state` 可按明确日期复用单个只读连接检查四张 Choice 历史表、因子、复权覆盖、gate 与三条基准序列；它没有注册为 GET，不调用供应商或业务写入，结果也不自带 generation。该函数仍未覆盖独立 `stock_limit_price_daily` 数值表或完整来源血缘，不能把其名称等同于全依赖资格。

直接脚本上下文没有 selected scope 时，该函数会打开显式活动库；在已有 selected scope 中才读取对应封存库。普通 writer lock 并未证明覆盖所有域 writer，取得它还会创建技术锁文件。当前缺口是缺少可证明安全的最新来源覆盖读取边界，而不是用户没有授权只读诊断。父代理已把“核实空闲后短时单次检查”的残余竞争风险提交 Pro 挑战；尚未打开活动库或派发真实补数。

## 根验收退回的中间版本

Sol 首版新增两项及原三项均通过，Luna 用两个独立全新临时根复跑也分别为 2 项和 5 项通过。父代理仍退回中间 SHA `0bb3cdac44700be1eeb1a7bd1f64c6f2137519859f30cbffdbaa88f66f966554`：请求 fields 没有明确断言、日期允许缺值，供应商工厂替身未提供真实 HTTP 的具名禁入计数，成功物化和治理记录的运行关联检查也不足。这些是测试证明缺口，不是已发现的产品缺陷。Luna 独立确认后由 Sol 仅补强同一测试文件。

精确中间命令、警告和停止接受理由见 `.codex-tmp/pretrade-gap-repair-20260916/root-intermediate-test-review.json`。两次重复运行不相加成新用例。最初 fake 的统一 `query` 与真实具名 endpoint 协议不匹配造成的失败也保留，不包装成产品红测。CLI 只实际运行 parser，再由测试按已审查的真实映射调用 wrapper；没有执行全 CLI，更没有执行真实恢复。

## 最新覆盖读取的具体协调缺口

Pro 对只读操作补充方案返回 BLOCKER，拒绝把“确认当前空闲”当成整个检查区间的保障。只读连接仍可能使后来启动的 writer 打开活动库失败。其要求是核对具体在用入口能否在数据库打开前协作等待、连接先于协调锁释放，以及有界超时清理，而非重新索取用户已给出的本机只读授权。父代理没有执行该活动库检查。

获批的两项任务精确只读查询见 `current-task-entrypoints.json`：`MOSS-DailyDataRefresh` 与 `MOSS-DataUpdateQueue` 当时均为 enabled、Ready，实际脚本分别为 `run_daily_data_refresh_host.ps1` 和 `drain_data_updates.ps1`。普通沙箱拒绝 CIM 访问的原结果单独保留；后续精确查询成功，不将前次工具权限错误写成计划任务异常。任务没有启动、停止或修改。

Sol 沿已知股票 producer 查明：历史主写、factor 主写和 `_persist_failed_materialization` 均在写连接前取得 `resolve_duckdb_writer_lock(duckdb_file)`，不能把它们写成绕锁根因。真正发现的不一致在盘前 driver 已直接调用的 `choice_macro.refresh_public_cross_asset_headlines`：它与同模块其他两个写入口只取得 `CHOICE_MACRO_LOCK` 专用锁，未取得相同的库路径级 writer admission。因而只给 inspector 加普通 writer lock 不能阻止这个宏观 writer 同时开库。这已是具体运行链内的阻断证据，不再扩大扫描仓库。

`read_only_connection` 默认最多三次 native open，重试的是 `OSError` 或 `duckdb.Error`，不是只针对文件锁；它已有 `retries=1` 参数。一次 inspector 调用不能宣称只有一次原生打开。现有 `acquire_lock` 超时会抛异常，宏观子步没有把它转换成队列 defer，因此尚不能声称临时读锁不会造成任务失败。

下一项有界方案只评估为 `choice_macro.py` 三个已知写入口补接现有路径级锁，保持专用锁、事务和数据含义不变；先做准确符号的 upstream 影响分析及隔离竞争证明设计，再交 Pro。未获方案复核前不编辑产品，不以这个发现自动派发真实数据恢复。

## 第一轮最终接受的测试版本

最终测试 SHA-256 为 `b602e0c1252ff6b1cf92476f0ebc61b87170f3355826efa77497a91cd65defa5`。父代理另发现中间 HTTP 哨兵不接受 Requests 实际使用的 `method=`／`url=` 关键字，异常可能在计数前发生；Sol 已仅修正测试签名，并在业务阶段零计数断言之后增加一次被禁止的关键字调用自检。每例后置自检计数为一，未进入真实传输，也不计作 producer 调用。原中间 `luna-final-proof.json` 已明确标为未接受，不覆盖其记录。

成功例实际完成七条关联请求审计和四行业务结果，四个 CSD 角色的状态为 `completed_tushare_gap_repair`，物化与 wrapper 的运行身份分别核实，治理结果中的历史条数与 source/vendor 标识和真实返回一致。失败例执行 daily_basic 三次尝试和两次被记录替代的等待，六张业务事实表完整 typed rows 保持不变；实际失败物化、三条请求审计和 wrapper 的 running／failed 记录均关联正确。失败时历史返回尚未生成，相关治理字段保持 null，不能写成已完成零行历史。

Sol 最终 focused 为 2 passed／3 deselected（2.98 秒），fresh full 为 5 passed（3.24 秒）。Luna 独立 focused 为 2 passed／3 deselected（2.84 秒），fresh full 为 5 passed（3.00 秒）；两组仅有已有 pytest 技术缓存警告，测试和四份直接产品文件哈希前后相同。完整命令及 guard 日志哈希见 `luna-accepted-proof.json`。Guard 日志的 11／14 条均为 owned-temp 授权事件，不是唯一用例数或 native 连接数。定向 Ruff、编译、编码检查通过；父代理也直接检查了未跟踪源码的 UTF-8、BOM、尾空格及结尾。

网页 6 Pro 第一轮结果复核返回 ACCEPT，仅接受上述冻结的五项合成执行边界证明，没有接受真实补数或全局上线，见 `pro-gap-repair-review-1.json`。父代理检查了最终源码和独立回执。至此没有产品代码修改、真实供应商请求、活动库检查、数据更新、服务中断或全局启用；宏观 writer 的具体协调缺口继续单独处理。

## 第二项修复的影响与方案起点

09:27 的独立快照见 `pre-macro-baseline.json`：正常健康仍为 200、全局选择仍关闭，活动库 stat 和 current pointer 不变。`choice_macro.py` 此时 SHA-256 为 `3f09021d4d4909585ca2c416b389562d907519b3c1c432778f6f2aea7f957b65`。已通过的股票分支测试继续冻结，不把它改作宏观测试框架。

父代理准确核对了三个生产符号：`_refresh_choice_macro_snapshot`、`refresh_public_cross_asset_headlines` 和 `refresh_tushare_ncd_shibor_proxy`。正确 GitNexus 索引与 HEAD 相同；先按名查询的两处歧义已用 function UID 消除。三份查询均返回 LOW／零 caller，但当前源码实际存在 workflow closure、actor 注册、lazy service 调用和盘前 driver 调用，因此图谱不能作为零影响证明。受影响流程是 Choice 宏观更新、公共跨资产／CSI300 和 NCD／Shibor 回退。直接调用处未预先持有同一路径锁，snapshot 后的 gate 计算位于原写锁之外。证据见 `macro-writer-impact-plan.json`。

已提交 Pro 的最小方案是在三处既有写块前补接现成的库路径级锁，再取得原专用锁；连接保持在两把锁内关闭，网络取数保持锁外。不新增锁框架或配置，不改 SQL、数据公式、事务、治理回执和既有超时语义。计划先用隔离库及进程 barrier 保存修前绕锁失败，再实施最小补丁和独立复验。该方案不自动清除其他 writer 的覆盖未知，也不授权真实 active inspector；当前等待 PLAN_READY。

Pro 随后返回 PLAN_READY，允许第二个有界执行项，产品只动 `choice_macro.py`，证明放在新 `tests/test_choice_macro_writer_admission.py`。要求先保存真实进程竞争红证据，再补三处锁；另验事务失败回滚后其他进程可重新取锁，以及第二把锁超时时不开库、不泄漏第一把锁。父代理已明确：supplier 完成事件不能单独证明到达锁边界，必须透明观察真实 path-acquire-attempt、entered 和 native-open 事件，不能用任意等待代替顺序证明。

前置死锁核对进一步确认，`register_actor_once` 只注册或更新 Dramatiq actor，没有取得路径锁；源文件中对 `CHOICE_MACRO_LOCK` 和其精确 key 的定向检索只命中该模块的三个写块与日志，不存在另一个已知反向持有点。块内 nested helper 仍由实施者在编辑前定向核对。父代理已在内存保存整份修改前源码用于 before-relative 比较，避免拿相对于 HEAD 的全部脏改动冒充本轮补丁。实际实现交 Sol，最终由 Luna 独立测试、父代理验收，结果将提交 REVIEW ROUND 2。

首个真实红证据已获得：`macro-admission-red-a` 在未改产品上为 1 failed（13.24 秒）。父代理直接读取了 `test_csi300_writer_waits_at_pa0/child-events.jsonl`，确认供应商替身完成后，writer 取得专用锁并尝试打开 owned 临时数据库，在父进程仍持有路径锁和只读连接时收到真实 `IOException`；事件中没有 path-acquire-attempt。这不是导入或 fixture 错误，也没有触碰活动库。

Sol 随后实施一处导入及三处多 context 锁获取，产品 SHA 为 `e6973fa4dedd05d8241f4a845a3de0f0a33549447e1b7e0bf067764a5b1a05af`。父代理把修改后文件按这四处预期修改反向归一，逐字符比较整份修改前内容，确认其余已有源码完全保留。首个竞争用例已转绿，完整失败释放和回归证明仍在实施，暂不计作第二轮验收完成。期间 Sol 因模型容量中断一次，已使用同一模型和代理接续，未更换生产方案或重跑真实数据。

Sol 随后的新文件定向为 5 passed（7.73 秒），四文件联合为 71 passed（46.48 秒）。父代理读完中间 SHA `832a52f6511741863c10a65d8aac55268f5af54cff1e27351131dca35be7b708` 后仍退回测试证明：跨进程用例在启动或事件断言失败、通信超时时没有完整收束所创建子进程；供应商替身之外缺少具名 HTTP 禁入计数；另外两个 writer 的取数先于锁获取及 NCD 确切值检查也未完整落到断言。它们是原 PLAN_READY 的证明和隔离要求，不是新增业务范围。该版本不交 Luna 作最终验收；产品补丁保持冻结，只补强测试，原运行记录保留。

## 第二项修复的最终候选

Sol 最终测试 SHA-256 为 `badd4ca96cd9c0412ce4ece34cd0311ef49909d20015ac34ca20c211fbcadb00`。父代理已阅读全部 919 行，核对三个实际 producer 的真实获取、打开、关闭和释放路径；供应商完成事件先于路径锁尝试，另外两入口核对 typed 输出。事务失败后比较四张表完整行集，并由另一进程真实重取路径锁；第二把锁超时的用例保持原锁实现，仅缩短测试等待，确认没有数据库打开，随后另一进程也能重新取锁。

测试中的 CSI300 子进程由创建它的 `Popen` 对象收束；嵌套 `finally` 保证先关闭 reader、释放已取得的锁，再有限等待该子进程，超时才对同一对象 terminate／kill 并等待退出。没有按历史 PID 或进程名清理。正常运行验证退出码为零；超时清理分支的存在来自源码审查，不冒充本轮动态故障注入。两个独立重取锁探针使用有界 `subprocess.run`，各自记录业务阶段零 HTTP／零数据库打开。所有子进程在应用导入前安装已有数据库保护和 Requests 禁入哨兵；后置自检与业务调用计数分开，外库自检在 native opener 之前被截断。

Sol 最终命令如下，两个临时根均为新建；重复运行不相加成新用例。

```text
.venv/Scripts/python.exe -m pytest -p _pytest_duckdb_guard -q tests/test_choice_macro_writer_admission.py --basetemp=.codex-tmp/pretrade-gap-repair-20260916/macro-admission-safety-h
5 passed in 8.85s

.venv/Scripts/python.exe -m pytest -p _pytest_duckdb_guard -q tests/test_choice_macro_writer_admission.py tests/test_choice_macro_csi300_scope.py tests/test_choice_macro_delivery.py tests/test_stock_refresh_isolated_execution.py --basetemp=.codex-tmp/pretrade-gap-repair-20260916/macro-admission-joint-i
71 passed in 45.38s
```

两文件定向 Ruff、`py_compile`、`git diff --check` 均通过；编码审计扫描 4534 份文件，新增和总 U+FFFD 均为零。早期 `macro-admission-producers-c`／`-d` 因 Choice fake 参数名和连接代理上下文协议不完整失败，`-e` 修正后为 3 passed（4.99 秒）；这些是夹具问题，不能混同于 `macro-admission-red-a` 的真实数据库占用红证据。

父代理的整份生产文件 before-relative 对照见 `root-macro-product-diff-proof.json`，仍只包含一处导入及三处锁块。当前已交 Luna 用独立 fresh roots 复跑，尚待网页 REVIEW ROUND 2，不将上述候选提前标为全局或真实运行验收通过。

## 独立复验及运行快照

Luna 的两条命令均退出零，无运行中 session。独立 focused 为 5 passed（7.79 秒），独立四文件联合为 71 passed（44.26 秒），每条只有已有 `PytestCacheWarning`：技术缓存目录已存在。回执为 `luna-macro-accepted-proof.json`；父代理重新计算其中八份源码和八份原始事件／保护日志哈希，全部相同。回执中一处后置自检域名说明已由父代理改为源码实际使用的 `guard-self-check.invalid`，测试源码和运行结果未变。

```text
.venv/Scripts/python.exe -m pytest -p _pytest_duckdb_guard -q tests/test_choice_macro_writer_admission.py --basetemp=.codex-tmp/pretrade-gap-repair-20260916/macro-admission-luna-focused-j
.venv/Scripts/python.exe -m pytest -p _pytest_duckdb_guard -q --basetemp=.codex-tmp/pretrade-gap-repair-20260916/macro-admission-luna-joint-k tests/test_choice_macro_writer_admission.py tests/test_choice_macro_csi300_scope.py tests/test_choice_macro_delivery.py tests/test_stock_refresh_isolated_execution.py
```

Focused 的父／写子进程分别有 15／1 条 guard 授权记录；联合分别有 170／1 条，全部限定在各自新临时根，没有拒绝。这是授权检查数量，不是 native 连接数或新增用例数量。父代理和 Luna 均读取了 CSI300 原始顺序及结果，确认业务阶段 HTTP／非目标库计数为零、后置自检分别为一，两个失败释放探针真实返回 acquired。正常退出有动态证据，超时收束分支仍只作静态审查披露。

10:19 的父代理只读快照见 `root-macro-final-runtime.json`：普通 API 健康、前端根页面及正常发布发现均为 200，全局 enabled 仍为 false；活动库仅检查 stat，其大小和修改时间未变；完整 current pointer 的大小、修改时间、哈希及身份均未变。26 份保留源码按本轮起点比较全部相同，其中 Livermore service 的旧漂移按本轮起点实际值保留，未沿用更早版本的验收。新增股票测试和宏观补丁分别匹配已冻结版本。没有业务数据库内容读取、真实供应商调用、更新重提、正式切换或服务操作。

上述冻结结果已提交网页 REVIEW ROUND 2；仅请求接受三处宏观 writer 的 admission 修复与隔离证明，活动库 inspector、安全读取当前精确日期覆盖和原全局在线门槛仍单列未完成。

## 最终结论和接续边界

网页 6 Pro 第二轮返回 ACCEPT，父代理结合完整源码审查、before-relative 对照和 Luna 独立结果，接受上述三处宏观写入口补丁及隔离证明。回执见 `pro-macro-writer-review-2.json`。本次最多三轮结果复核已使用两轮：第一轮只接受股票补齐分支测试，第二轮接受这项宏观生产补丁；没有第三轮，也没有全局上线 ACCEPT。

真正修复的是三个宏观 producer 未接入已有物理库路径锁的问题。普通 API reader 并未因这四处修改就参与协调，仍不能对活动库做未经证实安全的检查，更不能从旧封存数据推断当前缺失并重跑任务。原有 900 秒获取超时仍可能失败，本补丁没有新增 defer、排队公平性或永不失败保证。Pro 只复核脱敏证据，没有访问本机、修改代码或代替父代理验收。

当前停止点是安全读取边界仍未证明，而不是再次等待用户授予同一项本机权限。下一项应沿已有 inspector 与两项实际计划任务入口，补齐精确路径、单次原生打开、连接先于协调释放和有界收束的证据，同时确认这些实际 writer 都遵守同一准入；不能只看到 Ready／空闲就打开活动库，也不能把本轮人工持锁的测试 holder 当成生产读取边界。该门槛通过后，才可依据 `2026-09-15` 当前源表、独立 limit 数值及血缘证据确定必要子步，不盲目重跑旧日更整链或成功财务／bootstrap。

真实盘前 qualification、必要更新在服务保持在线时成功，以及首页、余额、债券、风险、损益的 5／10 并发冷／热请求、更新前中后状态和独立业务对账仍未验收。本轮没有修改公式、权限、调度、网络或全局开关，没有服务重启、提交、清理及真实业务执行。所有既有未提交改动、原失败日志、成功财务和 pointer 均保留；不要把这次局部修复报告成“可以正式上线”。

## 后续节省上下文的有界排查与暂停点

用户随后要求继续拆分子代理并控制 token 成本。本轮仅新建一个不继承长历史的 Luna high 只读代理，负责实际计划任务写入点定位；父代理检查 inspector 和直接依赖，没有启动 Sol 实施、重新运行已验收测试或发送新的网页 Pro 审查。原两轮 ACCEPT 的范围不变，第三轮结果复核尚未使用。

两项实际任务仍已启用。本轮查询时 `MOSS-DailyDataRefresh` 为 Ready，最近结果为 2；`MOSS-DataUpdateQueue` 为 Ready，最近结果为 0。这里只记录任务元数据，没有从结果码推断本轮故障原因，也没有把 Ready 当作检查期间的数据库保留权。外层任务锁不等于库路径锁，但长任务未持有整链库锁本身不是缺陷，不能把供应商请求包进长时间互斥区。

沿确定在用入口查到以下数据库打开边界。行号对应本轮源码，未改动这些文件。

| 写入函数 | 同路径锁情况 | 定位 |
|---|---|---|
| `ingest_stock_limit_prices` | 缺失；只有专用锁 | `backend/app/tasks/stock_limit_price_ingest.py:260-262` |
| `run_commodity_daily_ingest` | 缺失；只有专用锁 | `backend/app/tasks/commodity_daily_ingest.py:804-805` |
| `materialize_livermore_candidate_history` | 缺失；先打开写连接，后取专用锁 | `backend/app/tasks/livermore_candidate_history_materialize.py:401,635` |
| 复权因子、盘前持仓物化 | 已有 | 对应 task 的写连接前已取得 canonical path lock |

gate supplement 和 Tushare 新闻的最终写边界仍为 UNKNOWN，不能因本轮未展开就判为缺陷或已覆盖。禁止据此宣称全部计划任务已经协调。涨跌停价函数还在 `stock_limit_price_ingest.py:143-145` 做不带协调的只读预检；只给它的写连接补锁并不能证明所有读取安全。

父代理对 `ingest_stock_limit_prices` 的准确符号执行 upstream 分析，正确索引与 HEAD 相符，结果为 HIGH、13 个影响节点。直接节点包括每日任务 `refresh_stock_limit_prices_for_trade_date`、历史回填脚本和 10 个测试，另有间接每日入口。测试节点较多不等于可以忽略风险：真实每日刷新与回填共用该写入函数，其调用和锁序需要在实施前明确。已向用户提示 HIGH，并按 `pro-codex-loop` 和 `moss-agent-loops` 的停止规则暂停产品修改，待确认这一批高影响入口修复的边界。

inspector 仍未编辑。它通过现有 `read_only_connection` 默认最多尝试三次 native open，已有 `retries=1` 可用，不必改共享仓库层。其 GitNexus 结果虽然为 LOW／零 caller，实际 driver 有多处直接调用，不能把图谱零调用当作无影响。后续设计还须保持 selected／required-online 读取语义，不能为打开活动库清除上下文，不能在封存 generation 内创建技术锁目录。

建议后续只让 Sol 实施经 Pro 方案复核的明确写入边界补丁，由 Luna 用隔离数据库做定向复验，父代理检查实际连接与释放顺序。数值规则、SQL、供应商取数、权限、调度及全局开关不在这批修改内；不能在尚有 UNKNOWN 写入口时运行活动库 inspector。当前只有文档新增，无产品改动、真实数据读取、供应商请求、业务更新、服务操作或重复财务执行，也没有新增测试通过结论。

用户随后明确回复“是，修复完更新呗”，批准上述高影响修复，并要求修复验证后执行必要更新。因此不再等待同一范围授权；真实执行仍须先核实当前覆盖、日期和已有回执。后续精确追踪确认新闻 writer 已有路径锁，gate supplement 的实际 writer 尚缺该锁；这是同一在用盘前链中的直接依赖，已向用户说明纳入最小补接方案。商品 writer 还在打开连接期间调用供应商，不能直接把新增路径锁包在原整段外面。

本轮首个生产修改前的检查仍为正常前后端 200、发布发现 enabled=false，活动库 stat 与完整 pointer 哈希匹配上一快照。真实治理流的最新财务记录中没有活跃请求，成功的 `data_update_b0d6c34ba01b47b2b5873c230bd84b08` 继续保留，不重提。四个 writer 及 inspector 的修改前完整源码已保存在父代理会话基线中，用于区分本轮补丁与既有脏改动。商品、候选历史和 gate 的准确 GitNexus 查询均为 LOW／零 caller，但本轮已定位真实每日／盘前调用，所以仍披露索引调用信息不完整。

## 已实现的写入与检查边界

同一网页 6 Pro 已返回本批 PLAN_READY，未重置剩余一次结果复核预算。父代理先推进涨跌停价纵向路径，再按实际调用扩展到商品、候选、gate 及 inspector；候选 driver 后续直接调用的 outcome maturity 也发现同一缺口，因此只对这一个必要依赖补锁。最多三名子代理同时工作，实施使用 Sol，最后联合复验交 Luna max，父代理负责差异、运行边界和最终判断。

涨跌停价的严格只读预检、写入、dry-run 及空响应日期检查均使用同物理路径的既有锁。取数不持库句柄或路径锁，写入仍执行原有必需股票域复核。商品保留整轮商品专锁，仅在迁移和逐商品提交阶段短持路径锁及连接；供应商取数在路径锁和连接之外，仍保留逐商品提交、后续失败、空结果和 soft deadline 语义。没有新增锁基础设施、改变 SQL 或扩大数据日期。

候选历史的准确顺序是先取得路径锁，再打开写连接和计算；原候选专锁仍只保护最终替换段，不是两把锁都在首次连接之前。连接关闭后才释放路径锁。父代理另发现原 rollback 抛错会跳过 close，已用两处 nested try/finally 补齐，测试覆盖两个清理分支。Outcome maturity 与 gate 则在原专锁之前取得路径锁，原事务与业务规则不变。修改前完整源码位于 `writer-baseline/`，父代理使用 before-relative、忽略纯缩进的差异核实内容，没有把相对 HEAD 的历史脏改动当成本轮修改。

Inspector 先按既有读取上下文解析并固定路径。活动物理库读取在五秒准入锁内仅尝试一次 native open；已选封存库不创建 `.locks`，required-online 无选择时在开库前失败。原检查 SQL 和返回形状不变，仍不能替代独立数值涨跌停价、完整血缘和实际生产资格验收。

最窄测试分别保存了限价真实跨进程绕锁红证据、商品持连接取数红证据、候选和 maturity 开库顺序红证据、gate 开库契约红证据及 inspector 准入红证据。后几项是顺序断言失败，不混称原生数据库争用。Root 又退回商品用线程替身锁证明整轮串行的中间版本；最终改为两个 owned 子进程透明观察真实锁，第二个停在商品准入，首个取数阶段无路径锁或库句柄。限价和商品的准入失败均改用真实锁超时，限价回滚夹具补入已存在的目标日数据，避免只比较未受影响控制日。

实际日更单跳核对还确认 CFFEX、Tushare 新闻、复权因子和持仓 writer 已有同路径锁。日更 macro chain 的具名脚本主要输出模型 CSV／JSON／报告；定向发现的 DuckDB 访问为只读，未见其直接打开活动 DuckDB 写连接。这不是任意历史辅助脚本或全仓 writer 完整性证明。商品历史日期归一化等未在本次实际日更调用链中的辅助入口没有顺手修改。

## 加载修复前的运行检查

11:34 的实际配置元数据预检使用正常 `dev-env.ps1`，治理模式为 jsonl、Redis 为本机 `/11`；活动数据更新、待恢复 page intent、待处理 adjustment handoff 均为零，Redis 只有 heartbeat 和五条死信，没有 runnable／delay／ACK 项。死信未删除或重新派发。旧缓存流里遗留的历史 queued/running 标签不直接等同于当前可恢复工作；预检按 worker recovery 的实际协议过滤。诊断脚本在任何应用导入前禁止 DuckDB connect，本次未开活动库。

当前 worker 的启动时间仍为昨日，不能把磁盘补丁当作已在该进程内生效。正常前端也已由其他工作切换到 `frontend-remaining-20260916/accepted-build-final`，父代理保留其 selection，不回退旧构建。正式 API 的全局快照读取仍关闭，因此修复本地测试通过不等于正常 API 已与活动库隔离。此处记录的是加载和必要更新的前置检查，不是更新成功回执。

## 本地修复最终验收与第三轮关闭

Luna max 使用全新 owned 临时根，在一次联合调用中通过 96 项选定测试，session `79719`、exit 0、耗时 119.49 秒。Ruff 同样通过。原始命令、20 项源码／测试／guard／conftest 的前后哈希、真实子进程证据及原始日志索引保存在 `.codex-tmp/pretrade-gap-repair-20260916/luna-writer-final-proof.json`。195 条 guard 授权检查全部 allow，仅涉及本次 owned 临时库和内存；没有活动库或越界访问。父代理另行复核源码及日志哈希，未见不一致，没有重复计算此前 71 项或其他旧验收。

同一可见 6 Pro 会话第三轮返回 ACCEPT，仅接受冻结的六份生产文件准入／清理修复和本次合成验证。它明确区分 inspector 五秒锁准入与整段查询时限，也没有替本地执行 worker 重载、真实覆盖检查、数据恢复或发布。本周期三次结果复核到此结束，不追加第四轮。

用户“修复完更新”的真实执行授权独立于网页 verdict。接续的运维执行需实际加载修复、按当前覆盖选择必要日期和既有子任务，并先处理普通 API 仍读取活动库的暴露；不能把本地修复 ACCEPT、健康状态或 prepared 脚本当成更新已完成。成功财务及 bootstrap 仍禁止重放。此时两个具名运维脚本仅通过语法检查，尚未执行，后续以实际运行回执为准。

## 实际后台加载与当前数据检查（12:01 收口）

在用户已有运行授权下，11:54 执行一次具名 worker 重载，未重启 API 或前端。旧 worker 20084 和 keepalive 49600 已退出；新 worker 的 venv redirector 11024 与实际 Python 23548、单个 keepalive 30624 均经创建时间、父子关系、ExecutablePath 和命令核实。日志显示加载 38 个模块、四线程运行，stderr 为空；12:00 的 keepalive heartbeat 和 12:01 的正常 7888／5888 健康均正常，API 仍为原 32908。派发回执 `worker-reload-receipt.json` 与事后实际核验 `runtime-post-inspection.json` 分开保存，WMI 返回成功本身不算 readiness。

11:51 的新 stat 已发现活动库 mtime 为今日 10:51:50，与早期记录不同，故不再沿用昨晚状态推测缺口。11:55 使用真实 canonical lock、唯一只读连接及 owned-child 30 秒总时限执行现有 inspector，exit 0；库内检查耗时约 0.413 秒。`live-coverage-20260915.json` 证明 9 月 15 日七项基础检查均 ready，missing 为空。股票四类输入与 factor 各 5,219 行，复权所需 5,205 代码全部覆盖，CSI300 三条序列、gate、position、candidate 均存在。

独立数值涨跌停检查覆盖目标日全部 5,219 代码，无缺码、重复或空 lineage，原 DQ 规则通过；200 行比率样本无越界，不将样本比率核对表述为全量比率重算。必需来源表在目标日可用的 lineage 字段没有空值。这仍是覆盖和字段检查，不是独立金融对账或完整生产资格。

真实治理流进一步显示原失败之后已有成功股票更新 `choice_stock_refresh:2026-09-15:f55995a15335`，于昨晚 20:47:51 完成，明确 history_start_date 为 9 月 15 日且 Tushare gap repair 已启用。因此本轮没有再次执行行情、因子、复权、限价或整条失败日更。当天数据缺失的原假设已被当前覆盖与已有成功终态否定。

11:58 又以独立 owned 子进程、45 秒总时限、同路径锁和唯一只读连接，调用真实 signal confluence closure 检查，不运行 producer。结果见 `live-pretrade-closure-20260915.json`：日期正确、quality/vendor 均 ok、fallback none、macro authority ready、lineage complete，但返回 `signal_confluence_replay_not_ready`。成熟度 partial，20 个完成日期、2 个 blocking pending 日期、92 个 unsupported 日期、4 个 proxy-only 日期，matched entry 为 0，必要持有期统计不可用；另有真实风险门禁 block。这些是现有计算输出，不是允许本轮任意历史补算或放宽风险门槛的依据。临时诊断首次使用错误锁参数名，在开库前失败；仅修正为现有 `timeout_seconds` 参数后完成一次真实检查，生产补丁未改变。

Luna 的运维复核没有发现本次已执行结果受损的证据，但指出脚本不能泛化为自动 drain：准入前元数据不等于任意在途任务证明，Stop-Process 也不是优雅 drain。另需更正前文“元数据预检没有开活动库”的范围：Python 预检正文确实禁止 connect，但外层 `dev-env.ps1` 的 `print-env` 会调用 `_duckdb_has_seed_data` 只读探测活动库，并有 runtime-clean 初始化能力。该外层路径不属于本次六文件修复，不能宣称整段启动环境加载零开库或已完成全局 writer/reader 协调。

12:01 收尾时，20 项冻结源码／测试哈希均匹配，现有前端 selection 保留，活动库 stat 与 11:51 相同，完整 pointer 哈希仍为 `dd0c1c6b4222ddc37b71b8ebbf56f5370384345c57313439f8dd2e7ed1b1cdf0`，无维护标记。本轮实际交付是验收修复加载、真实当前覆盖和未满足资格原因的确认，没有派发新的业务更新或发布。正常 API 的 global immutable 开关仍 false；切换、必要 writer 重叠下五域验证、性能及独立业务对账仍未完成。代码复核预算已关闭，按循环技能收口，不临时新增生产补丁或绕过现有发布条件。
