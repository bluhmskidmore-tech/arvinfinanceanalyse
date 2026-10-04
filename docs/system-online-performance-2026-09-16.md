# 全局在线读取性能接续（2026-09-16）

最终结论：四个服务的本轮修复、31 项独立测试及受控正常应用读取隔离通过；五个业务域在本次 5／10 并发测量中均低于一秒。更新状态 10 并发及单客户端债券仍有超限，真实在线必要更新、浏览器流程和独立业务核对未验收，全局尚未完成，正式开关保持 false。Pro 第 2／3 次均 ACCEPT 本轮有界修复及证据，未接受上线；当前三轮周期已关闭，不自动扩改或重置。

用户要求继续拆分子代理，按难度选模型，由父代理最终验收。本轮接续 `system-read-context-closure-2026-09-16.md` 已通过的三边界修复，不重复其 21 项实施测试和 8 项独立复验。Sol 负责复杂代码和性能判断，Luna max 负责有界证据分析、更新资格核对和冻结后的独立验证，同时最多三个子代理。开始时沿用网页 Pro 已接受第 1／3 次的周期，仅剩两次结果复核；执行过程如下。

正式全局读取开关未打开，原服务、前端选择及未提交改动保留。不得重复成功的 8 月 31 日财务更新、9 月 15 日股票更新或 bootstrap。历史 PIT 缺口继续保留，不改风险和资格门槛。性能、真实业务更新期间的读写重叠、独立业务核对和浏览器流程分别验收。

## 测量依据

原验证脚本 `scripts/verify_system_online_reads.py` 的退出状态检查 HTTP、envelope、锁、代次、日期及同源一致性，不会因为 P95 大于一秒而退出失败。一秒目标必须另外判断，不能将 exit 0 写成性能通过。此前每域仅 10／20 个样本，P95 近似最大值；首轮也不等于冷启动证据。

父代理从既有受保护正常应用验证脚本派生只读性能 helper：`.codex-tmp/system-read-performance-20260916/profile_sealed_reads.py`，SHA-256 为 `e23905fa4e36240e2640e2cabac4d003b7a507a03924d160734df4ec5350164f`。仅为真实 resolver、manifest 读取和 native connect 计时，不替换返回值、校验或金融计算；仍拒绝活动库及非封存文件开库，禁止 Requests provider 调用，使用临时 7889，不切换正式服务。

首次 `performance-baseline` 因新增的预热等待诊断上限 45 秒到期而退出 1，未进入负载阶段，回执保留。第二次仅将该诊断等待期限改为 120 秒，使用独立前缀 `performance-baseline-ready`；实际首次后台预热耗时 60.749 秒并正常完成后才开始负载。这是诊断准备上限修正，不是删掉预热或放宽业务／一秒性能门槛。

```powershell
. .\scripts\dev-env.ps1
$env:MOSS_READ_PERF_PROBE_LABEL = 'performance-baseline-ready'
& .\.venv\Scripts\python.exe .codex-tmp/system-read-performance-20260916/profile_sealed_reads.py
```

第二次命令退出 0，回执 `performance-baseline-ready-proof.json` 的 SHA-256 为 `ba9723be02e765b4e37c6b6216c191230de58a6c0c026c80dd160d9234cea7d1`。三个真实预热保持开启；单客户端两轮，5／10 客户端各五轮，共 462 GET，检查无失败。382 次 native open 无拒绝，provider 尝试为零，临时服务退出，登记的正式身份和源码前后未变。5／10 并发每域样本分别为 25／50；样本更多，但仍是开发机上的有界比较，不是生产容量认证。

| 域 | 单客户端 P95 毫秒（2 样本） | 5 并发 P95 毫秒 | 10 并发 P95 毫秒 |
| --- | ---: | ---: | ---: |
| 首页 | 186.413 | 1585.003 | 619.866 |
| 余额 | 460.113 | 178.423 | 2707.322 |
| 债券 | 876.315 | 3138.281 | 6386.117 |
| 风险 | 415.337 | 415.276 | 4455.616 |
| 损益 | 85.761 | 1873.645 | 844.646 |
| 更新状态 | 3291.034 | 3858.122 | 4791.494 |

## 根因与首改范围

债券服务的明细缓存键包含报告日、筛选条件和活动库路径／mtime，却没有选定快照身份；仓储在缓存之后才解析快照，因此不同代次共享活动库 stat 时可能复用旧明细。`get_portfolio_headlines` 即使明细缓存命中，仍重复多轮 Python 聚合、模型转换和正式血缘构建。先用 A／B 代次隔离和调用计数证明，再在该明细边界修正身份，并仅为已验证完整封存 scope 下的头条响应复用既有 runtime cache；非封存旧行为、日期失效、trace 独立及返回值防污染必须保留。金融公式、SQL、DTO、单位、日期及空值不改。

更新状态的主要单请求耗时已有直接证据：`data_update_service.scheduled_updates` 每次调用 `data_health_service._run_schtasks_query`，固定命令枚举本机所有任务。实际命令是 `schtasks`，不是 PowerShell。本机只读测量全量枚举耗时 2536 毫秒，逐个查询页面固定的五个任务共 412 毫秒，每个约 80—85 毫秒。通配名称查询返回 1，不采用。拟给既有 helper 添加可选单任务参数，默认全量行为不变；数据中心只查五个固定任务，任一查询失败后仅回退一次原全量路径，维持 missing 与权限／环境错误的既有语义。状态不缓存，require_scheduler 继续实时校验，不修改计划任务及其执行入口。

44,099,312 字节的全局 manifest 确实在每个请求缓存查找前重读并计算摘要；受控测量中主事件线程 resolver 中位数约 32 毫秒、P95 619 毫秒，竞争时最高 2.2 秒，但不能据此认定它是所有慢请求的唯一根因。本轮先不修改共享 publication 校验、ContextVar scope、中间件或风险 SQL。

| 首改文件 | 修改前 SHA-256 |
| --- | --- |
| backend/app/services/bond_analytics_service.py | 5b8e591fde272cd154222cd6736bb24f725fb4e20f64ed000b00b4cd89b3f0aa |
| backend/app/services/data_health_service.py | d8ba1e63cf609d2b6fb03da5d4b9bd6d425ef39a855b3c4988d8a376251f42f1 |
| backend/app/services/data_update_service.py | 622e8a570fc825d013e615d3faecbeac641ae9db756939f21dfee9dc21a964b8 |

GitNexus HEAD 与 index 都是 `3ca0bbc438644214878bd789c4322a722c9d6393`。一次债券 impact 出现 WAL／锁异常；后续查询恢复，但漏掉实际调用，故以源码直接调用补足，不把 0 当作无影响。债券头条直接消费者为 route 和 dashboard section，明细缓存有三个同服务调用。scheduled_updates 为 LOW（四个上游），query helper 为 LOW（六个上游），同时涉及只读状态和写前检查，测试必须覆盖两者。共享 system_read_scope 为 HIGH，本轮不触及。指标、血缘和 catalog MCP 未暴露，使用本地契约、命名源码、原测试和实际回执作为替代，不扩张金融口径。

同一可见 6 Pro 返回 PLAN_READY，没有首改阻塞。先证明并修正明细缓存的 A／B 污染，再缓存已验证封存 scope 的头条结果；缓存命中前的读取选择和失效边界不能消失，日期 invalidation 必须覆盖新缓存及相关在途工作。调度查询失败或响应无法匹配固定任务时，须丢弃部分结果并只回退一次原全量查询。

按用户“按难度选模型”的最新要求，Sol high 实施较复杂的债券服务与 `tests/test_bond_sealed_headlines_cache.py`；Luna max 实施两个服务中的小范围任务查询调整与 `tests/test_data_update_schedule_query_scope.py`。分开新测试文件，避免并行编辑冲突。另一 Luna max 独立审查诊断证据；随后在冻结版本上独立测试，父代理作最终 review。计划将结果复核第 2 次用于冻结补丁与测试，第 3 次用于同一 462-GET 协议的真实运行结果；不重置预算。

## 真实更新资格

Luna 在 16:41 只读核对：`MOSS-DailyDataRefresh` 状态 Ready，下次执行为 2026-09-16 18:45（UTC+8），上次结果 2；结果码不被当作业务结果。9 月 15 日股票更新先失败后已有成功回执，9 月 16 日聚合日志及股票更新记录当时尚不存在。匿名页面 market 操作权限 false，没有伪造身份或启动任务。

本轮核查没有证明 9 月 16 日来源已到齐，不能仅凭日期提前提交更新。下一次真实机会为既有 18:45 调度；仍须到时核对来源、聚合与各子任务回执、实际结果日期和读取稳定性。不会拿昨天失败 aggregate 覆盖其后成功股票任务，也不会为了 writer-overlap 证明重放成功财务数据。

## 独立复核与实现进展

Luna 只读核对 baseline 回执，确认 462 GET、616 项同源核对全部通过，382 次真实 native open 全部为封存库只读（system 304 次、PnL 78 次），没有活动库或 Requests provider 调用。首次失败诊断未产生负载样本，不能并入成功测量。阶段计时含启动及 discovery，不能直接归因具体接口；同一进程按 1、5、10 客户端顺序逐步热化，修复后必须保持顺序与样本数一致。

Sol 已完成债券服务及新测试：先用 3 项失败证明同 stat 的 A／B 快照串读和暖命中绕过校验，再修正实际读路径，随后证明头条重复重算并使用既有 runtime singleflight 缓存。新增 13 项测试、5 项精确回归、1 项空结果接口契约通过；尚待独立复验和统一性能比较，不据此宣称上线。

Scheduler 初版 11 项新测试和 1 项既有测试通过，但执行命令漏了要求的 `-p _pytest_duckdb_guard`；仓库 conftest 会加载 guard，这不等于显式早期注入。初版也没有改前失败证据，两点如实保留，后续冻结版另作显式 guard 独立验证。独立 Sol review 发现串行五次查询各有 15 秒上限，再加一次全量回退可使异常等待扩大至约 90 秒。已退回实施者限制整组定向查询共享预算，并用假时钟验证；不通过真实等待或运行任务来试错。

17:10 父代理只读核对活动库大小、纳秒 mtime、全局 pointer 和 baseline 中的生产源码身份一致。前端 control 文件则已在本轮负载之后由外部工作更新为 `.codex-tmp/home-inflation-20260916/accepted-build-final`；没有回退或改写它。后续证明只覆盖各自测量区间，不把本轮之外的前端变动写成身份始终未变。性能 helper 未列入本轮三个服务文件，父代理将在修复后测量前后单独核对其冻结 SHA。

Scheduler 超时修正已收口：原 15 秒上限改为整组定向查询共用的单调时钟预算，传入每次剩余时间；失败仍至多一次原全量回退，因此最坏约 30 秒，不能写成总等待仍为 15 秒。新增预算测试在实现前为 2 failed／12 passed，修正后 14 passed，两次均显式使用早期 guard；测试无 DuckDB 尝试，未生成 attempt 回执，不虚构回执或独立计数。Sol 只读复审 APPROVE，另有 Luna 冻结复验。

债券缓存的 Luna 独立复验为 13 passed，冻结 SHA 前后未变。这组测试使用临时占位文件及 mock 仓储，证明缓存／选路语义而非真实 SQL；实际封存库读取由后续正常应用测量补充。Sol 对真实消费者复核另发现一项 P1：`bond_dashboard_service.get_bond_dashboard_bundle` 原生 `ThreadPoolExecutor.map` 不传播读取 ContextVar，实际页面的 `portfolio-headlines` section 会在 worker 中退回活动库。父代理核实源码后接受该问题；这是本轮服务的直接上游消费者，不扩展为全库线程重构。GitNexus 对该 symbol 返回 LOW／0，但漏掉已知 route，仍用源码补足，不据 0 宣称无影响。Sol 获授权仅新增 `bond_dashboard_service.py` 的逐提交上下文传播和独立 `test_bond_bundle_read_context.py` 回归；原债券缓存文件冻结。

## 冻结代码与精确验证

| 文件 | SHA-256 |
| --- | --- |
| backend/app/services/bond_analytics_service.py | bd904b53e0476bf31ff6a6204d96962dda19d71adb4c76875cf0c1178ed625db |
| backend/app/services/bond_dashboard_service.py | 8daefbba4d924c9b185c18dd2d4738dcda1946db5f7919d06462b048f9f5c9aa |
| backend/app/services/data_health_service.py | 01c646c6e5c535edf7f4fa4c9da81ce76ba9c6960536afafea34f6c7e3f27f36 |
| backend/app/services/data_update_service.py | 2c13d3f5ccc3e9ae1da0b699a91b88c38d926cc21b779df882302b530af7975c |
| tests/test_bond_sealed_headlines_cache.py | f2152c403ea2f04691f2351f469be395894d427d0009a1be8545f74aa0cd6ae1 |
| tests/test_bond_bundle_read_context.py | bdb671259a7a674c5a87d4966edea5c7898fb321735d90535d10fb82c5cc607a |
| tests/test_data_update_schedule_query_scope.py | 3033e4e0a919587d542bfa68e0b517596ec0b3cd4fbaafcb675b1edb9b5ac15d |

父代理还冻结了未改动依赖 `runtime_cache.py`（`f56182d7bfd37e2b3fbb2a592ed9fe2aa0bf2ae008533b8f8b6fa9d34fef5a7d`）、`duckdb_read_context.py`（`b69125cc07d21e9aa17db7689c8a1ff458632cb77a5a2cbcb43f84eaa4ca20db`）及原性能 helper，用于后续测量区间归属检查。

以下独立命令各只执行一次，运行前确认临时目录不存在；前两条分别为 13 passed／14 passed，哈希前后不变：

```powershell
.\.venv\Scripts\python.exe -m pytest -p _pytest_duckdb_guard -q tests/test_bond_sealed_headlines_cache.py --basetemp=.codex-tmp/bond-sealed-independent-root-20260916-a1
.\.venv\Scripts\python.exe -m pytest -p _pytest_duckdb_guard -q tests/test_data_update_schedule_query_scope.py --basetemp=.codex-tmp/scheduler-independent-root-20260916-a1
```

Bundle 实施先以真实仓储 SQL 读出临时活动库的合成值，证明红测；再作 7 行上下文传播改动，新增 4 项测试和 3 项既有 bundle 回归均通过。红测 guard 有 4 条记录，绿测有 19 条：主封存测试只读 snapshot 2 次、active 0 次；双代次测试只读 A／B 各 2 次、active 0 次；缺失／删除测试无 active 回退。fixture 播种和单独 legacy 测试允许打开其自有临时 active 文件，不属于生产活动库，也不混入封存读取计数。两个 future 测试未使用 barrier，故不额外宣称确定的交叠时序，更不是生产 writer-overlap。冻结后的独立 bundle 验证另记。

独立 bundle 命令为 `.\.venv\Scripts\python.exe -m pytest -p _pytest_duckdb_guard -q tests/test_bond_bundle_read_context.py --basetemp=.codex-tmp/bond-bundle-independent-root-20260916-a1`，只运行一次，4 passed in 5.16s，两个 SHA 前后相同。父代理逐条检查真实 guard 回执，共 19 条，均为 test／owned_temp／allow：9 条 fixture 写入、8 条封存 scope 只读 snapshot、2 条明确 legacy 只读临时 active。没有 denied 或生产库路径。至此新增独立用例共 31 项，不将实施者重复运行计为新增覆盖。Sol 对 scheduler 和 bundle 两项修正均最终 APPROVE，父代理完成源码与回执核对；已提交同一 Pro 周期第 2 次结果复核，等待裁决。

父代理在本地独立复验、代码 review 和十个冻结文件 SHA 检查均通过后，启动 `performance-fixed-ready` 真实应用复验。启动时网页第 2 次复核仍在进行；如实区分时间顺序，不描述成先有网页 ACCEPT。复验 helper 本体未改，只传入新输出前缀。一次前置 Node 哈希命令因 PowerShell 引号失败而退出，未启动任何 runtime；改用有效参数后哈希全部一致，随后只启动一次性能验证。

## 修复后真实运行结果

网页 Pro 第 2 次结果为 ACCEPT，仅接受冻结实现与相应测试，不授权上线。父代理运行下列命令一次，退出 0；回执 `performance-fixed-ready-proof.json` 的 SHA 为 `7f5ee9adde69dbcb507dc167e0d4beeec7faa8f1ee5b22f2f9dd64bac6fc18b0`。

```powershell
. .\scripts\dev-env.ps1
$env:MOSS_READ_PERF_PROBE_LABEL = 'performance-fixed-ready'
& .\.venv\Scripts\python.exe .codex-tmp/system-read-performance-20260916/profile_sealed_reads.py
```

仍为实际 normal app，三个预热全部开启；首次后台预热成功耗时 48.753 秒，完成后才开始同一组 462 GET。所有 HTTP／envelope／日期／代次检查通过，616 项同源核对通过。父代理跨基线与修复后逐组比较六类业务指纹，全部相同，包括更新状态。382 次 native 打开均为允许的封存库只读，无 active／denied 和 Requests provider 尝试。临时服务结束，helper 登记的身份保持不变；另行登记的四个服务、三个新测试、两个未改依赖及 helper 的十个 SHA 前后相同，补充回执为 `performance-fixed-extra-identities.json`。

| 域 | 单客户端修复后 P95 毫秒 | 5 并发修复后 P95 毫秒 | 10 并发修复后 P95 毫秒 |
| --- | ---: | ---: | ---: |
| 首页 | 229.432 | 406.966 | 660.364 |
| 余额 | 520.004 | 214.098 | 392.986 |
| 债券 | 1165.151 | 217.392 | 458.759 |
| 风险 | 597.103 | 188.150 | 538.298 |
| 损益 | 107.658 | 401.770 | 520.674 |
| 更新状态 | 614.560 | 626.351 | 1042.851 |

本次 5／10 并发的五个业务域均低于一秒，但更新状态 10 并发为 1042.851 毫秒，未通过；单客户端债券两样本为 1165.151 毫秒，也不隐去。因此六接口全组性能验收仍未通过，不靠四舍五入、重跑求绿或删掉接口改变结论。单客户端两样本不是冷启动认证，各组样本及开发机条件也不足以保证生产容量。六接口不含 bond-dashboard bundle，后者本轮有真实临时库的服务／回归测试，未声称完成正常应用 bundle 流量或浏览器交互。

17:28 附近正式 API `/health` 返回 200；本轮没有重启、启用全局开关、提交数据请求或执行计划任务。真实必要更新的在线读写交叠、浏览器流程和独立业务来源核对仍缺。父代理已向 Pro 提交最后第 3 次结果复核，明确全局未完成，并保留 18:45 原有任务机会而不重跑已成功工作。

Luna 最后只读审计确认两组各 462 GET／616 项核对、全部业务 hash 一致及上述两个延迟未通过项；未重跑。父代理 17:34 再次请求正式 `/api/system-read-publication`，HTTP 200、`enabled=false`、`generation=null`；实际监听 7888 的 PID 为 57728，前端 5888 为 23780，临时 7889 已无监听。本轮未操作正式进程，后续运维须重新查询 PID，不沿用早先记录。

网页第 3 次最终返回 ACCEPT，明确只接受冻结补丁、读取隔离／同源一致性及如实保留的部分性能结果；全局仍 NOT READY，未授权上线。依 `pro-codex-loop` 的三轮上限，本周期收口。下一轮应从两个已测超限、实际必要更新资格及在线读写重叠、代表性浏览器和独立业务核对这些具体缺口开始；不能将 18:45 排程本身当作成功，也不能重放旧财务、股票或 bootstrap。44 MB manifest 校验不因体积大就自动成为下一次改动目标，不新增共享基础设施重构。
