# 全局在线更新新周期：实现与上线验证

用户在上一周期暂停后明确同意继续补齐缺口、完成候选验证，并在门槛满足后按已有授权上线。本周期为新的 goal-based 执行复核，最多三轮，同时最多三名活跃子代理；Sol 主要实现，Luna max 独立验证，父代理负责整合、网页 Pro 和运行验收。原始未提交改动、旧成功财务请求和正式运行配置均保留。

## 首个修复范围

首批文件限定为 `backend/app/tasks/system_read_publication.py`、`backend/app/tasks/source_preview_refresh.py`、`backend/app/repositories/source_preview_repo.py`、`tests/test_system_read_publication.py` 和必要的既有来源版本 composer。首先修资格检查漏掉合法空批次的状态，不改 producer、导入行为、金融公式、schema 或权限。

2026-09-15T05:45:55Z 重新只读核对，活动数据库仍为 3,668,979,712 字节，mtime 仍为 `2026-09-15T00:02:48.034Z`，完整读取 pointer 不存在。没有重复执行旧预检来代替修复。GitNexus 索引 HEAD 匹配，但新发布器的三个函数未在索引中，upstream 查询均返回 UNKNOWN；不能据此称为零影响。直接调用补充证据表明，预览 predicate 由 `_manifest_matches_current_facts` 使用，后者用于 bootstrap 选择和正常发布事实校验，因此正反向回归同时约束初始化和正常发布。

本轮第一个证明命令为 `.venv/Scripts/python.exe -m pytest -q tests/test_system_read_publication.py`，先加入经过真实 bootstrap 资格入口的失败回归，覆盖合法 None/空批次、相同哈希终态、来源选择变化、归档边界、显式批次兼容及非写入保证。只有实际通过资格的状态才能进入唯一性判断；单个未核验候选也不能被当作合格。

## 后续验收门槛

空批次修复之后，按直接调用与写入回执核对独立 writer 的影响面并接入最小发布触发。不能用“已披露陈旧”代替全局刷新完成，也不能让单域金融变更形成未闭合的完整快照。候选服务必须从合格完整版本启动，固定首页、余额、债券、风险、损益，不得删除失败领域。验证浏览器、同源数值、日期/来源及 5/10 并发多轮冷暖读取后，再判断正式切换。

正式切换与真实在线数据更新分别验收。没有合法新来源变化时，修复、初始化与候选验证可以继续，但不得重跑 `data_update_b0d6c34ba01b47b2b5873c230bd84b08` 或制造数据变化；真实必要在线更新继续单独标 PENDING。停止条件是本轮门槛完成且 Pro ACCEPT，或同一阻塞两次有证据、三轮预算用尽、必要业务含义/权限无法确定。已明确的本机运维授权不重复询问；新范围或不可恢复操作另行处理。

网页已恢复原会话，可见模式为 6 Pro，并返回 PLAN_READY。批准先做两文件资格修复和真实 bootstrap 入口回归；其后再沿实际启用的 launcher、schedule 与 task 完成边界核对 writer。仅完成写入但依赖不闭合时不得复制发布，也不得禁用正常 writer 来制造覆盖通过。候选与运行切换是第三阶段，真实必要在线财务更新仍须单独证明。只传脱敏技术摘要，没有业务金额、原始数据、凭据或文件上传。MCP 契约/血缘工具当前不可调用，以原契约、producer 和仓储为本地证据，不提升排除域为正式口径。

新周期运行核对发现 7888/5888 均无监听，Node 请求明确返回 ECONNREFUSED。这是本轮任何服务操作前的状态，与上午记录不同；运行控制器仍无维护标记。已交 Luna 独立只读核对当前 worker/keeper/计划任务、最短日志与既有恢复入口，尚未恢复或启用新机制。

## 第一轮实际结果

两文件资格修复已完成。先加入经过真实 bootstrap 入口的反例，得到 `1 failed, 23 deselected`；修复后完整目标测试为 `30 passed`。Luna 对相同冻结哈希独立复跑，完整 30 项、新增 preview 7 项、合成发布/无重放 2 项均通过，定向 Ruff 和编码检查通过。空批次现在复用 producer 的 None 选择语义；只有事实判定严格为 True 的终态进入唯一性判断，单个未知候选也不会误放行。既有等价终态政策未改变，全部真实记录仍留在冻结历史中。

2026-09-15T06:13:14Z 只执行一次新的真实只读资格检查，结果为 `qualified`。七个领域均完成实际事实核验，source-preview 两个空批次终态均能匹配原选择规则得到的六个来源族。先前失败原因已经修正；本次不是重新导入或伪造批次。活动数据库大小和 mtime 未变，完整读取 pointer 仍不存在，未执行 COPY、CAS 或财务重算。回执为 `.codex-tmp/system-online-update-20260915/resume-bootstrap-preflight.json`，早先失败回执保留为 `pre-resume-bootstrap-preflight.json`。

本轮冻结的 `system_read_publication.py` SHA-256 为 `0fda840b735c56ea7157b4fddf9b4082e8324879c8b3cb66b14983c114630699`，`test_system_read_publication.py` 为 `181709392f2bfa8047839826d885728af24fec8230727c588731558b6e2936c7`。新增 preview 集成测试对其他六域使用有界隔离，因此不单独宣称七域合成业务对账；七域现存事实资格来自上述真实只读检查。第一轮修复证据和具体后续 writer 方案已交原网页 6 Pro 会话复核，尚未收到本轮 verdict。

第一轮网页复核随后返回 `ACCEPT`，范围限定为上述冻结两文件资格修复。Pro 同意进入第二轮，要求余额混合日期仍须证明保留域依赖没有改变，测试共享依赖改变时在 CAS 前拒绝；市场 aggregate 必须在 child 执行前落真实 run identity，逐步保存实际回执，不能事后编造总报告。发布专用恢复必须绑定同一 aggregate 并绕过七步业务执行。全局启用与完成未被接受。

第二轮已分给两名 Sol：一名负责共享发布器与 balance_daily 完成挂点，另一名负责实际市场 aggregate 和必要 child receipt。Luna 正在独立核对旧 worker 启动会触发的 pending recovery，父代理负责现有运行恢复、整合和 Pro。最多三名子代理，不变更财务公式、权限、schema 或调度基础框架。最终引用的文件哈希将以第二轮完成后的冻结为准，第一轮哈希仅证明当轮已审版本。

第二轮的真实 producer 语义反例又证明，balance_daily 导入新余额来源后会改变 source-manifest 的逐族最新选择，旧 source-preview 终态因而不再匹配。保留旧 preview 时拒绝发布是正确保护，但不能把这种正常新文件路径称为更新已闭合。父代理据此批准必要的一跳扩展：既有 `_refresh_source_preview_cache` 增加默认关闭的 `from_existing_manifests` 模式，余额日期验证成功后只用现存合格归档构建 preview，保存真实新终态；不再次 ingest、不运行 PnL、不改 parser 或正式使用边界。它属于余额依赖完成步骤，不能在 publication-only 恢复内执行。实现和测试仍在进行，尚未据此通过启用门槛。

父代理并行审查市场适配器时发现资格核验与共享 writer lock 之间的并发窗口。市场来源指纹必须由同一个 writer-lock 内连接核验，并在 COPY 前后再次比较，不能只在锁外读一次后由发布器接纳新的当前事实。两名 Sol 正在接入这一有界 validator，并增加窗口内变化拒绝与真实共享 publisher 集成回归。新闻 coverage 需使用真实收到时间范围；纯文件宏观日报的非正式降级不得被混当作活动数据库写入失败。

## 运行恢复与真实 writer 拓扑

独立只读诊断确认旧 API、前端、worker、keepalive 和私有 PostgreSQL 已退出，日志没有足够证据解释突然退出原因；机器未重启，Redis 仍运行，维护标记不存在。在已有运维恢复授权下，仅用既有私有 PostgreSQL start helpers 恢复原 datadir，未执行 init、迁移、grants 或 KPI bootstrap。API 通过既有运行控制器启动且跳过存储迁移，前端用原 accepted build 恢复。7888/5888 都返回 200，活动 DuckDB stat 未变，全局新开关仍为 false。没有启动财务 drain，worker/keepalive 等恢复前 pending 检查完成后再恢复。这是恢复旧服务，不是新机制切换。

Luna 的准确任务检查确认 `MOSS-DataUpdateQueue` 和 `MOSS-DailyDataRefresh` 均 enabled/Ready；后者实际 action 为 `scripts/scheduling/run_daily_data_refresh_host.ps1`，最近结果为 2。Choice、MacroFreshness、MacroDaily 三个 legacy timer 原本均 disabled，未作任何启停修改。当前 writer 实施聚焦已启用 aggregate 及数据中心 balance_daily，legacy skip 保留拒绝未核验外部完成回执的门槛。完整脱敏检查见 `.codex-tmp/system-online-update-20260915/resume-qualifier-independent-audit.json`。

进一步只读核对 2026-09-14 的准确 aggregate 日志与 Choice 原子回执，Choice 失败原因为活动 DuckDB 被另一进程占用（日志第 30 行记录 ALERT FAILED）；同一轮 news 在第 382 行失败，原因是 RemoteDisconnected 网络断连，不归为数据库锁问题。本轮未重跑该链。它们分别是共享读写根因的另一个真实影响实例和独立网络依赖风险。

候选准备仍未启动服务或发布：用既有运行控制器重新验证 build-v2 manifest 和全部 306 文件，验证通过且没有改正式 selection。只新增任务临时 bootstrap 与候选前端脚本并做语法检查，等待第二轮 gates。2026-09-15T06:27:58Z Node 系统探针观察到物理内存 33,812,221,952 字节、可用内存 7,477,256,192 字节、F 盘可用 15,622,889,472 字节。CIM 沙箱查询被拒绝且产生的零值不能作资源证据。发布仍需通过现有容量与 bounded_v1 资源保护；没有自动 generation 清理，磁盘增长风险继续保留，不清理用户文件或旧证据腾空间。

worker 恢复前，首份 Redis 检查误读默认 `/0`，被父代理拒绝作为 gate，原回执已标 `invalid_environment`。父代理和 Luna 随后分别验证正常 dev-env 最终是 `127.0.0.1:6379/11`，治理和 DuckDB 都在正式工作目录。准确检查显示 page prepare pending、adjustment handoff pending、Redis queue/DQ/ACK/in-flight 均为零，仅有三条非 pending 的死信，不执行或删除它们。准确回执为 `resume-recovery-pending-readonly-audit-corrected.json`。

据此恢复原 worker 和单实例 keepalive。worker stdout 确认加载 38 个任务模块、4 线程运行；keepalive 在 14:33:11、14:34:13 连续报告 PostgreSQL/API/frontend 均正常，进程检查可用，stderr 为空。新开关仍 false，活动 DuckDB 大小与 mtime 未变，没有 full pointer。首次 helper 调用因缺少既有 `$root` 调用上下文在启动前失败，补齐原约定后启动成功，未产生重复进程；没有执行财务 drain。完整独立运行恢复验收另交 Luna 核实。

独立恢复回执 `runtime-restored-independent-audit.json` 随后通过：API 健康、原 accepted 前端身份、私有 PostgreSQL、worker heartbeat、单实例 keepalive 均正常，Redis `/11` 没有活动队列，数据中心活动请求为零。两个 Python PID 的父子关系经父代理 CIM 核实为同一个虚拟环境 redirector 与基础 Python worker，不是两个独立 worker。候选启动准备改用既有 dev-up/keepalive 的隐藏 WMI 模式，避免依附临时执行进程；前端启动脚本也复用 `verify_build` 校验全部文件，仍不修改正式 selection。

15:10 按相同授权及新 CIM 精确身份，仅替换本轮恢复的 keepalive PID 40084，使用既有隐藏 WMI 启动方式，未重启 API、前端或 worker。新独立 launcher 返回成功，15:10:47 heartbeat 确认 PostgreSQL/API/frontend 正常，stderr 为空，7888/5888 均仍为 200。日志为 `resume-keepalive-detached.stdout.log` / `.stderr.log`。没有维护窗口、更新 dispatch 或数据库写入。

## 第二轮冻结与复验进展

Balance/shared lane 已冻结：共享 publisher 41 项、数据中心 58 项、读取边界 22 项、通用金融发布器 25 项全部通过；source-preview 完整 56 项通过，最终新增定向 3 项通过。Ruff 与编码检查通过。除新余额来源补齐预览外，另加入历史余额日期反例，预览使用真实 `report_dates` 最大覆盖日，不再强加余额请求日期。此处是实施者结果，Luna 正在以相同哈希和逐测试文件独立解释器复验，尚未作真实初始化发布。

市场 lane 在父代理收口审阅中继续修正两个实际边界：日志加嵌套 JSON 不能误选最内层对象；缺失 news 写入计数不能等同于零写入。父代理还要求核验 pretrade 后运行 macro freshness 的直接依赖，以及失败 aggregate 的真实终态。此 lane 尚未进入第二轮 Pro 最终复核，不据最早的 25 项测试结果启用全局开关。

候选静态独立检查确认 build-v2 全部 306 文件身份一致、两个服务仅用 7889/5889、ASGI 观察器不改响应体、bootstrap 不 dispatch 财务。它也发现临时入口的锁外 precheck 并发窗口，已最小修正：bootstrap 在既有短 operation lock 内核对并原子占用本次 attempt 回执，长 COPY 仍由 publisher writer lock 管理；候选 launcher 在锁内检查进程、端口和日志并独占预留日志，核对 cache profile/attempt label。限定 Ruff E9/F821 和 PowerShell parse 通过，Luna 复验中。没有执行候选入口。固定五域只读验收工具本轮重跑为 13 passed。

Luna 随后独立复跑上述五组测试，共 149 passed（41/58/22/25/3），五个实现文件 SHA 均与冻结值匹配。回执为 `resume-balance-shared-independent-audit.json`，测试使用临时归档样本和数据库，不是重跑真实财务。初传标签 `repo` 指 `system_read_publication_repo.py` 文件哈希，曾被误解为仓库快照摘要；已在同一回执中纠正，git HEAD 单独保留。两份候选脚本的锁内 guard 复验也通过，见 `candidate-static-independent-evidence-corrected.json`；bootstrap 的四条 E402 为先插入本地根路径再导入的明确限定例外，未声称默认全量 Ruff 通过。

市场调度依赖经另一名 Sol 独立只读核对确认：pretrade 按目标日核验 `fact_choice_macro_daily`，其回执没有可连接到后续 freshness 的宏观内容版本。因此七步结束后的指纹只能证明最终 cut 稳定，不能证明先前产物使用最终宏观事实。父代理批准必要的最小顺序修正，freshness 在 pretrade 前完成，pretrade 同时依赖 limit 与本轮 freshness，并保留 freshness 独立运行的能力。未改计算公式。市场适配器与完整共享发布器的穿透测试另交 Sol，用临时七步回执和数据库实际执行 COPY/seal/CAS，不以两端各自单测替代连通性验证。

市场独立复验随后完成，适配器 19 项、实际 adapter 到共享 COPY/seal/CAS 集成 2 项、PowerShell 调度 13 项均通过，三份冻结实现文件前后 SHA 一致，回执为 `resume-market-independent-audit.json`。加上余额/shared 149 项，本轮两组独立验证合计 183 passed。没有真实供应商或财务重跑。

第二轮网页 Pro 返回 `REVISE`。余额/shared 没有新增阻断项；剩余缺口是已有 Choice 周末无写跳过时，新闻和宏观仍独立写入，但 aggregate 无法发布。不能将失败关闭本身称为全局刷新闭合。第三轮限定查明既有消费契约是否允许保留准确旧 Choice/pretrade 日期和依赖；只有有依据的沿用才可实现，缺证据、部分写入或不兼容旧依赖变化必须继续拒绝，不新增交易日历或猜测上个交易日。

Pro 同时明确允许进行隔离 bootstrap 和候选验证，不必等第三轮市场修复结束；正常配置与正式前端 selection 仍须保持不变。父代理据此开始唯一一次合格现存状态 bootstrap，入口内部重新核验资格、容量和来源 cut，只复制、封存并发布现存合格事实，不 dispatch 旧财务请求。第三轮预算保留给修复和实际候选证据，正式启用仍未获通过。

## 隔离初始化与第三轮阻断

2026-09-15T07:43:23Z 至 07:45:29Z，唯一一次 `resume_publish_bootstrap.py` 成功完成现存状态 COPY、seal 和 CAS。新 generation 为 `system-read-2026-08-31-75f2365545e061d2f2c2`，manifest SHA-256 为 `977656b42ae3f48813cf7400d58b25dbbc7a5452323b808da8eac78266941f65`。活动库 stat 未变，未 dispatch 或重算财务。快照为 2,019,307,520 字节；发布阶段峰值进程内存为 5,315,911,680 字节，未超过 bounded_v1 限制。完整回执为 `resume-bootstrap-publication.json`。这证明现存合格事实可以初始化，不证明真实在线财务更新。

15:46 通过既有隐藏 WMI 模式启动 7889/5889 隔离候选，正式 7888/5888 与配置不变；前端启动核验冻结 build-v2 全部 306 文件。首个 cold-5 API 为 PID 18332，启动于 15:46:26，三项预热关闭；只检查 health 后交 Luna 发起固定负载，不用暖请求冒充冷启动。

两名 Sol 对第三轮阻断分别给出直接证据，未修改冻结实现。`scripts/choice_stock_daily_refresh.py:398` 的周末回执没有旧有效日期、terminal 或 readiness；`scripts/run_livermore_daily_pretrade_refresh.py:544` 按同一 target_date 读取 Choice、factor 与三条 CSI300 宏观序列，闭市分支只报告 target_date_not_open；旧 pretrade 回执没有其宏观输入内容身份。`scripts/scheduling/daily_data_refresh.ps1:399` 将依赖跳过向下传播，但宏观和新闻仍独立运行。技术层保存旧表未变不能证明它与新宏观兼容。

依据循环技能的同一必要业务契约阻断停止条件，暂停第三轮市场扩展和正式切换，不再泛扫或猜测。最小待决契约是：旧 pretrade 的精确日期、terminal 和实际三条 CSI300 输入必须能够恢复，且宏观刷新后对应输入身份完全未变，才可能允许保留；任一变化或证据缺失继续拒绝。隔离候选验证属于 Pro 已允许的独立工作，继续完成，不据此消除正式启用 NO-GO。

## 候选首测与必要读取修复

原冻结候选四组读取完成，共 540 次 GET（含更新状态），全部 HTTP/契约通过、单一 generation，每域业务哈希稳定；720 项同源 tieout 通过。cold-5/cold-10 分别来自全新 PID 18332/24004 且关闭三项预热；warm 来自另一新 PID 21340，三项预热真实完成后才计时。没有真实 writer overlap。原始回执 `resume-candidate-cold-5.json`、`resume-candidate-cold-10.json`、`resume-candidate-warm-5.json`、`resume-candidate-warm-10.json` 保留不覆盖。

| 固定接口 | 冷 5 P95 ms | 冷 10 P95 ms | 热 5 P95 ms | 热 10 P95 ms |
| --- | ---: | ---: | ---: | ---: |
| 首页 | 2171.757 | 3650.492 | 1813.382 | 4128.054 |
| 余额 | 1758.272 | 3501.966 | 2208.675 | 3386.919 |
| 债券 | 4423.820 | 9344.998 | 4527.190 | 9809.534 |
| 风险 | 3413.430 | 7100.210 | 1817.135 | 7299.796 |
| 损益 | 2634.650 | 3832.281 | 2643.778 | 3140.174 |
| 更新状态 | 3443.461 | 6319.599 | 4039.512 | 6404.747 |

该结果未达到一秒交互目标。定向代码核对发现，每次请求在命中已有 validation cache 之前，仍完整读取、SHA 校验并 JSON 解析约 44 MB 的 system manifest，另解析 PnL manifest；同一请求内已有 ContextVar 复用，不能归咎于未证实的重复嵌套调用。父代理批准第三轮独立的最小性能修复：仍逐请求读取并核验实际 SHA，只将已核验内容的缓存查询移至 JSON 解析前，命中时继续验证 generation、expiry 和 reader API/schema；失效标记和数据库 miss 核验不减弱。不会采用仅信任文件 mtime/大小、跳过 manifest 内容哈希的方案。

此函数同时被系统读取、普通损益读取和发布器调用，实际影响按 HIGH 处理；GitNexus 对未跟踪符号返回 UNKNOWN，不能视为零影响。Sol 负责该 resolver 与定向测试，正式服务和业务公式不变。测试等原四组负载全部结束后执行；修复后将用独立标记和新进程复验，不将原进程结果归给新源码。

修前计数反例实际失败，第二次 resolve 累计 read/hash/parse 为 `(2, 2, 2)`；修复后为 `(2, 2, 1)`。实现者关键 4 项、完整金融发布 28 项、系统发布 41 项、读取边界 22 项和仓储接入 8 项通过，Ruff 与编码检查通过；同尺寸恢复 mtime 的 manifest 篡改依然被实际内容哈希拒绝。实现 SHA 为 `ae21ee8d32bdc0450d4e93f4272d2e4ec31a6770bb2fd916ce71bb8a800910ba`，测试 SHA 为 `b4ed2ed01812e0e044e7b34a217456920132edf103261f9c9a4aec00182d8f02`，独立复验另行记录。GitNexus change detection 因 spawnSync git EPERM 不可用，未声称通过，也没有提交代码。

Luna 对上述冻结文件独立复跑金融发布 28、读取边界 22、仓储接入 8，共 58 passed，前后 SHA 相同。回执为 `resume-manifest-parse-independent-audit.json`；这是修订后测试，不与旧 183 项简单相加为不同用例总数。

另一次三文件只读核对发现，`frozen_system_governance_rows` 每次递归解冻整条历史，`GovernanceRepository.read_by_cache_keys` 和 latest 路径也先全量解冻再筛选；债券 `get_benchmark_excess_many` 会读取两条完整治理流。这是有证据的额外对象复制，不是已完成计时定位。下一步应记录该函数的行数、调用次数和耗时，再判断是否仅对命中行解冻；本轮没有新建治理索引或扩大通用缓存框架，也没有将这一推断外推为风险/更新状态的全部根因。

## 修复后候选实测与浏览器结果

修复后四组仍为 540 次 GET、零 HTTP/契约/锁错误，720 项同源 tieout 全部通过。Luna 对八份报告逐一比较，六类读取接口的原版/修复后业务哈希完全一致；八组合计 1080 次 GET、1440 项 tieout。它证明被比较读面的结果一致，不是独立会计对账，也没有真实 writer overlap。

| 固定接口 | 冷 5 P95 ms | 冷 10 P95 ms | 热 5 P95 ms | 热 10 P95 ms |
| --- | ---: | ---: | ---: | ---: |
| 首页 | 978.259 | 979.936 | 548.798 | 610.887 |
| 余额 | 859.746 | 955.078 | 465.312 | 1621.685 |
| 债券 | 3537.669 | 6273.034 | 3282.328 | 6179.041 |
| 风险 | 2575.147 | 4101.898 | 1971.133 | 5141.052 |
| 损益 | 417.595 | 562.741 | 384.179 | 456.199 |
| 更新状态 | 3094.031 | 4588.811 | 3288.545 | 4328.914 |

首页、损益四组均达到一秒目标，余额热 10 未达标，债券、风险、更新状态仍偏慢。风险热 5 较原版略慢，因此不称每组都改善。原始修后回执以 `resume-candidate-postfix-` 开头，原版报告未覆盖；准确进程及启动/预热/停止时间见 `candidate-process-evidence.json`。

父代理在真实候选浏览器逐页检查首页、余额、债券、风险、损益洞察，固定报告日为 2026-08-31。首页资产与余额资产卡、三页 DV01、风险总市值和只数，以及损益 Top3/HHI/日均余额，均对照同 generation API 并核对亿元、万元/bp、百分比等实际显示单位。损益页面仍明确显示原已接受的 `financial-20260831-66e1166f10ebf174`。余额的质量复核、债券候选口径、风险缺到期日等警告、损益旧来源限制均保持可见；没有将预警包装为全部正式正确。此处只核查代表性显示路径，不等于全页全部指标审计。部分工作台壳层初始短暂出现带“演示”标记的行情，加载后替换为已落地真实行情，未据此宣称所有辅助模块无既有界面问题。

首页最后一次受控只读刷新前，记录 `candidate-requests-warm.jsonl` 为 650 行，时间 08:16:21.069Z，随后仅点击“刷新首页数据”，没有父代理额外 API 请求。第 651—672 行共 22 个请求：先由未 pin 的 `/api/system-read-publication` 握手，再有 21 个 pin 同一完整 generation 的读取；全部 200 且 body completed。没有将一次同版本刷新写成实际业务更新后的版本切换。

候选启动已核验全部 306 个产物文件。08:14:56Z 又从实际 HTTP 读取 index 和 main JS，其 SHA 分别为 `848ab0629df111f786b3f393ca2e92a0f8b2ffd5355f7b63809ce92d96cc66bd`、`f37c36584b66d1b9d477bd477d19213f718e4112953345534075f370ed6abd71`，与 accepted-build-v2 相同。没有重新构建或修改正式 selection。

第三轮脱敏实现、全部实测、浏览器证据与明确 NO-GO 已提交同一可见 6 Pro 会话，等待最终 verdict。只发技术文本，未发送业务金额、原始来源、凭据或文件。08:19:44Z 在重新核对进程树和端口归属后，仅结束候选 API PID 12740 与候选前端 PID 7308；08:19:48Z 两个候选端口已关闭，正式 7888/5888 仍为 200。未删除任何文件，快照和日志保留，活动库仍为 3,668,979,712 字节且 mtime 不变。

Luna 的最终只读回执 `resume-candidate-final-readonly-audit.json` 已完成：最终 resolver 下真实 market/shared 集成仍为 2 passed；八报告的 1080 请求、1440 tieout、零失败、原后哈希一致、306 文件与实际 HTTP 产物身份、全局默认关闭，以及第 651—672 行刷新窗口均独立核对。最终冻结 resolver SHA 未变。

16:21 收尾只读检查确认原 API 39976/52800、前端 39372、私有 PostgreSQL 13276、keepalive 39568 仍在；16:21:11 keepalive 心跳为 PostgreSQL/API/frontend 全部正常。第一次按 `dev-worker.py` 筛选遗漏了 worker，其实际入口为 `backend.app.tasks.dev_worker_runner --threads 4`；随后按真实入口核对，原 15964/20084 父子进程仍在，没有重启或重复拉起 worker。

## 本周期关闭与下一项待决

第三轮 Pro 返回 `ACCEPT`，明确只接受冻结的 manifest JSON 解析复用修复，以及单个完整 generation 下已实际完成的初始化、候选读取和代表性页面验证。正式启用、全域性能和真实在线更新目标仍为 NO-GO；不是全局交付 ACCEPT。本周期三轮已关闭，不能据这个局部 verdict 自动启动第四轮。Pro 收到的摘要中候选关闭尚待执行，其回复期间父代理已按上述准确 PID 完成收尾，实际回执优先于摘要时点。

用户待决的是周末产品行为：新闻、宏观已经独立更新，而旧盘前决策不能证明与新数据兼容时，是否允许发布独立信息并明确停用不合格旧决策，还是保留整套旧版本直到依赖齐备。已发送非阻塞问题，尚未收到选择，不按预选项视为批准。选择后才能建立可测试的发布契约；不能仅增加一个 skip-success 分支。下一轮性能工作先计时归因冻结治理流的读取，再做有证据的最小修复。真正必要的在线财务更新仍需合法新来源变化；禁止重复成功的 2026-08-31 请求。

接续时应先读取本文件和三份独立回执：`resume-manifest-parse-independent-audit.json`、`resume-candidate-final-readonly-audit.json`、`candidate-process-evidence.json`。完整 pointer 已存在，bootstrap 成功回执已存在，不能再执行初始 bootstrap 脚本。保留 2 GB 级别合格快照、原日志和已有未提交修改，不自动清理 generation。候选 7889/5889 已关闭，正式配置仍 false；如将来获准启用，应另行核对实际服务、最新来源、所有 gates 与已接受产物，不使用本文件的历史 PID 直接操作。

本轮关键证明命令（pytest 不加载 dev-env，真实更新命令不在此列）：

```text
.venv/Scripts/python.exe -m pytest -q tests/test_financial_result_publication.py                 # 28 passed
.venv/Scripts/python.exe -m pytest -q tests/test_system_online_read_boundary.py                 # 22 passed
.venv/Scripts/python.exe -m pytest -q tests/test_system_online_read_repositories.py             # 8 passed
.venv/Scripts/python.exe -m pytest -q tests/test_system_read_market_publication_integration.py  # 2 passed
node .codex-tmp/system-online-update-20260915/candidate_artifact_http_check.mjs                  # index/main JS match；当前候选已关闭
```

八组只读负载均使用 `scripts/verify_system_online_reads.py`，固定 `--report-date 2026-08-31 --rounds 3 --require-generation --include-update-status --business-tieout`，`--clients` 分别为 5/10；原版与 postfix 使用独立输出文件和实际独立冷/热进程。全部样本保留，没有删去失败模块或只取快请求。

## 后续盘前周期索引

上文“周末行为待用户选择”为该周期结束时点。用户随后已同意新闻／宏观独立更新，并要求实际解决盘前决策；另一个三轮周期的实现、反例和最终证据已记录于 `docs/system-online-pretrade-closure-2026-09-15.md`。网页 Pro 已接受该盘前实现与连续合成 producer、封存和实际 API 验证，最终后端联合组 151 项通过。新周期也已关闭，不能与本文件旧三轮合并或无限追加。（相关执行证据仅保存在本地，公开版本不附原文。）

正常启用、真实数据盘前资格、必要真实财务更新时五域并发，以及本文件已披露的性能缺口仍未通过。18:45 自行运行的正常日更失败和晚间活动库文件变化已有最新只读记录，接续以最新盘前文档为准，禁止依据本文件较早“stat 未变”推断现在仍未变，也不得重跑已成功 bootstrap 或财务请求。

## 运行安全后续索引（2026-09-15 22:46）

后续测试保护和只读预检已记录于 `docs/system-runtime-safety-2026-09-15.md`。选定测试的 connect、实际 publication ATTACH 和受测子进程均已增加打开前保护；独立前置 16 项与随后原十文件 151 项通过，最终 Pro 第一次复核 ACCEPT，只关闭该局部周期。原先未加保护的历史 151 项不因这次通过而自动获得全程隔离证明。

最新只读证据确认既有动态接口选择存在当前有效候选，不能据此认定供应商业务访问成功；获批资源查询的当时使用者清单为空，不能追溯历史写入者。22:46 正常健康入口 200，完整 pointer 和活动库元数据保持该新周期记录的状态，未启动新业务更新或正常切换。原五域固定端点、负载和未达标项全部继承，不因测试安全 ACCEPT 降低验收标准。

## 真实访问后续索引（2026-09-16 08:24）

最新 `docs/pretrade-live-recovery-2026-09-15.md` 已记录独立诊断实现、36 项独立证明和唯一一次真实 daily_basic 身份访问成功，以及另三项现有主源股票历史任务的显式日期／临时存储证明。两次 Pro 复核均 ACCEPT，但各自限定于上述不同分支；它们不是端到端盘前恢复。现有任务参数已够用于这段测试，没有新增生产恢复框架。

正常入口仍保留原运行方式，08:15 全局选择接口明确返回 enabled=false，08:24 正常健康均为 200、活动库元数据与完整 pointer 未变。没有财务、bootstrap、整链日更重放或服务切换。原五域负载、性能和独立业务一致性缺口继续继承；补数前必须核对旧运行已落地内容及必要缺口，不能由任务失败反推整段均未写入。
