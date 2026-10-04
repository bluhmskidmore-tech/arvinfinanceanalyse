# 宏观下游读取与线程上下文接续（2026-09-16）

用户在获知整体尚未完成后回复“可以，开启吧”。本轮按继续完成剩余修复执行，不将这句话解释为绕过已失败门槛直接打开全局开关。前一周期三次复核已经关闭，全部旧结论保留；本次明确接续最多三轮结果复核、同时最多三个子代理，由 Sol 实施、Luna max 独立验证、父代理最终审查。

## 已证实根因与首改范围

上次真实 normal-app 回执 `macro-fixed-runtime-proof.json` 的 SHA-256 为 `1f0fdf61837696e78696fa77e5aceda5d7391c5a877b537b2b5c216a02b1cc9f`。180 次 GET、240 项同源核对通过，但九次活动库只读尝试被拒绝，整体验证失败。这九次不来自已修复并独立验证的 system_sources／shadow 入口。本轮不重新执行其 8／32 项测试，也不重新执行旧环境、启动、财务或 bootstrap 切片。

两次失败来自 `cffex_member_rank_repo.table_stats`，一次来自 `dual_frequency_equity_repo.load_dual_frequency_equity_history`；这两个入口未解析选定快照，直接检查和打开传入的活动路径。另外六次来自已接有效路径 helper 的三个 context loader，实际调用方 `macro_toolkit_read_service.build_macro_toolkit_full_analysis_blocks` 使用 ThreadPoolExecutor，却没有传递 ContextVar 中的快照选择和 required-online 状态。修复应在两个 repository 的文件检查前解析有效路径，并在每次线程池提交时分别复制上下文；不要重复包装已经接入 helper 的下游 loader。

| 首改生产文件 | 修改前 SHA-256 |
| --- | --- |
| backend/app/repositories/cffex_member_rank_repo.py | 28da064f6a39929fd81e09c1d65cf65e71e504aeca0c23f224bddb8ba9e6ec98 |
| backend/app/repositories/dual_frequency_equity_repo.py | 87c624b073a0f0c5603e33024404f7c80ed8d66977ae1417d83a33a48f56abfa |
| backend/app/services/macro_toolkit_read_service.py | 37362103f5eb96418e752f4d92afb7c1862aca728fd1e64462e2a3d05950b7e0 |

GitNexus 使用 `moss-v3-main-current-20260809`，当前 HEAD 与索引 lastCommit 均为 `3ca0bbc438644214878bd789c4322a722c9d6393`。table_stats 和 full-analysis-blocks 的图谱风险为 LOW，但漏掉已证实的动态调用；dual-frequency 风险 MEDIUM，14 个上游、12 个直接调用，其中生产调用为 macro ETF history loader，其他主要是现有 repository 测试。父代理用实际错误栈补足图谱，不把零图谱调用者当作无影响。

本轮未接入指标、血缘、catalog MCP，以命名的本地源码、既有契约测试及真实运行回执替代。只改变读取路径和上下文，不改金融公式、SQL、金额单位、日期、空值和降级语义，不把宏观分析表面提升为正式金融口径。API／前端起点均为 200，全局发现 enabled=false。

## 实施与验收约定

Luna 的两次定向只读搜索找到可复用模式：executive_service 已在每次 submit 使用 `copy_context().run`，不共享同一个 Context。直接历史回归为 `tests/test_dual_frequency_equity_repo.py`；宏观线程池已有两项 route-wrapper 并发／本地连接测试，位于 `tests/test_macro_toolkit_scripts.py`。此次未找到 table_stats 直接测试，不能虚构已有覆盖。

先对 `tests/test_macro_remaining_read_boundaries.py` 做真实失败先行证明，使用临时数据库、现有 DuckDB guard、子进程导入前网络哨兵和独立持有 active RW 的真实进程。使用真正的 repository 查询与真正的三线程执行器；并发 barrier 应能识别错误地共享一个 Context 的实现，并覆盖 required-online 没有 selection、快照失效、快照切换、无选择／显式 active scope、参数与结果顺序以及异常清理。每次 pytest 使用新的不存在的 basetemp，冻结后 Luna 只独立执行所需新测试一次。

随后父代理用 `macro-context-runtime` 新证据前缀重复正常应用与原五域／更新状态检查。保持真实三类预热、端点、并发数和拒绝活动库开库的观察器不变；保留旧失败文件，不改正式开关、前端选择或业务数据。局部测试、真实读取边界、性能、真实必要更新期间并发以及独立业务一致性分别判断，不合并为“全局完成”。相同阻塞重复两次或三轮复核用完即停止扩围并报告。

具体方案已提交原网页可见的 6 Pro。当前仅记录已提交，等待 PLAN_READY 后才授权子代理落地生产改动。历史留存、成功更新不重跑、未提交改动不清理、无提交推送等约束保持有效。

网页 Pro 随后返回 PLAN_READY，明确首改没有阻塞问题。它认可三个边界的最小修复，补强要求是：在提交线程为每个任务单独复制上下文；三个 worker 使用有超时的 barrier 证明真实并发；两个重叠请求各自固定不同快照；worker 内也要证明缺少 required selection／快照失效时禁止回退；失败必须解除测试 barrier 并收回自有进程。父代理已核对建议与本地约束相容，随后授权 Sol 仅修改三份生产文件和一份新测试，不扩展到已有 helper 的下游 loader。

## 首红、首绿与真实运行结果

首个有效红测使用新测试文件与 `.codex-tmp/macro-remaining-red-a2`：实际 table_stats 在快照 scope 中返回 active 的一行，而非 snapshot 的两行，退出 1。更早 a1 是 fixture 表名错误，不算读取根因证据。三个最小修复落地后，同一文件在 `.codex-tmp/macro-remaining-green-a1` 首绿，1 passed in 1.89s；随后继续补齐约定的边界测试。

生产冻结 SHA-256：cffex 为 `83dd07bd318d4ff09bd11360bd93631673662f70229ff3189cd791d01b9d0cf6`，dual 为 `89686b2dff338530455eb4d09d1ef0eaa95be0c2f2fc10084a7b445c100c5899`，read service 为 `5e01e59bcc7a0c4bc088b6daec25f65b47c86b9c398f07ad516ea11d1a9bbd35`。父代理另在内存中撤去 cffex 本轮新增 import 与 Path 行，哈希精确回到本轮起点，确认文件中既有 writer 改动没有被改写；该内存校验没有写文件。独立 Sol 生产增量 review APPROVE，未发现新问题，测试审查另记。

16:10:43 至 16:11:38，父代理对冻结的三个生产文件完成一次真实 normal-app 复验，`macro-context-runtime-proof.json` 的 SHA-256 为 `2a6dd1539fe2decd87f8c5a51238cc4029f1b8ddbe96f5cbc938a744392878b7`，整体退出 0。home／income／market 预热全部为 true，观察到 232 次开库，无活动库或其他非封存开库拒绝，Requests provider 调用为零。5／10 客户端各两轮的 180 次 GET 与 240 项同源核对全部通过，HTTP、envelope 和每域同代次业务指纹均一致。临时服务及进程退出，正式身份和冻结源码前后不变。

5 并发回执 SHA-256 为 `962a23ff52bfd68477e885a6fce7e9f83d670858d56868cfea0ac600594f8690`，10 并发为 `c994ede891014c99a79addb68751437849e535592afb06b3e39c5056001fb795`。所有文件仍在 `.codex-tmp/system-read-activation-20260916/`，新前缀不覆盖旧失败。该结果通过本次实际读取隔离门槛，仍不证明实际业务 writer 重叠、完整浏览器交互或独立会计审计。

| 域 | 5 并发 P95（毫秒） | 10 并发 P95（毫秒） |
| --- | ---: | ---: |
| 首页 | 1230.933 | 651.738 |
| 余额 | 619.669 | 1027.612 |
| 债券 | 3018.041 | 6475.045 |
| 风险 | 2310.460 | 4537.040 |
| 损益 | 1545.904 | 500.515 |
| 更新状态 | 4056.144 | 6040.415 |

多项读取仍高于一秒目标；这是有开发负载的两轮小样本，不能作受控性能比较。没有删除慢接口或放宽门槛。正式全局开关未打开，尚未执行新的业务更新。父代理已读取 `docs/data_update_center.md`，后续仅核对实际来源、明确日期及已有请求，再判断是否存在必要更新，不为构造 writer 证据重跑成功业务。

## 冻结测试与独立审查

新增测试最终 SHA-256 为 `f1ea65d6206e044be488b3926758fd5b8131afba5d71418f8ba185079f08bf95`。下列命令均退出 0，每次使用独立且运行前不存在的 basetemp，没有复跑已验收的财务、bootstrap、环境或旧宏观切片。

```powershell
.venv/Scripts/python.exe -m pytest -p _pytest_duckdb_guard -q tests/test_macro_remaining_read_boundaries.py --basetemp=.codex-tmp/macro-remaining-freeze-a1
# Sol: 8 passed in 5.48s
.venv/Scripts/python.exe -m pytest -p _pytest_duckdb_guard -q tests/test_dual_frequency_equity_repo.py --basetemp=.codex-tmp/macro-remaining-dual-regression-a1
# Sol: 11 passed in 3.01s
.venv/Scripts/python.exe -m pytest -p _pytest_duckdb_guard -q tests/test_macro_toolkit_scripts.py::test_macro_toolkit_full_analysis_blocks_run_heavy_sections_concurrently tests/test_macro_toolkit_scripts.py::test_macro_toolkit_full_analysis_uses_three_worker_local_connections --basetemp=.codex-tmp/macro-remaining-service-regression-a1
# Sol: 2 passed in 3.97s
.venv/Scripts/python.exe -m pytest -p _pytest_duckdb_guard -q tests/test_macro_remaining_read_boundaries.py --basetemp=.codex-tmp/macro-remaining-luna-independent-a1
# Luna 独立执行一次: 8 passed in 5.11s
```

独立 Luna 回执 `macro-remaining-independent-proof.json` 的 SHA-256 为 `5db7881eaae5b6a40820b4cc7de08c59dc6abe170b9ded41718d9523d5435e97`。真实 RW holder 完整记录打开和关闭；三个 reader callback 使用三个不同 worker，实际 repository 查询只打开 snapshot，活动库打开和网络调用均为零。30 次父进程临时库访问全部符合 guard 规则，四个冻结文件前后哈希一致。

Sol 对冻结生产增量和完整新测试的最终 review 为 APPROVE，未发现新增问题；Luna 将本轮修复及已测 normal-app 读取隔离判为 CLEAR，将性能与运营证据判为 WATCH，全局上线判为 BLOCK。父代理审阅了完整新测试、实际回执和哈希；有超时的 barrier 能在超时后破坏屏障并退出，当前测试并没有显式调用 `Barrier.abort()`，不将这项实现描述为已存在。

真实运行 helper 当前 SHA-256 为 `99f3bfd721695e009da363c0b3b777e9ade3ba60721e33a16173a6a0a5196c96`。父代理补核全部 232 次 native open：均为 accepted、read_only，且不是内存库；活动库 stat（纳秒按原始十进制字符串比较）、publication pointer、前端选择及回执登记的源码身份仍完全一致。正式 API `/health` 与前端根页均为 200，正式 discovery 仍为 `enabled=false, generation=null, coverage_dates={}`。

## 是否需要新增财务更新

按纯环境解析得到的实际入口为 `F:/MOSS-V3/data_input`，治理目录为 `F:/MOSS-V3/data/governance`。只检查输入文件元数据及请求回执，不打开活动 DuckDB，不修改或提交更新。输入根目录 1215 个文件和五个财务子目录的直接文件，均没有晚于成功财务请求回执的修改时间；这些文件中观察到的最新修改时间为 2026-09-10。未扫描 processed 派生目录，也未进行所有输入文件内容哈希认证，因此结论只限于“未发现新增输入变化”，不是内容绝对未变证明。

`data_update_run.jsonl` 的 46 条事件按 run_id 去重后为五个历史请求，最新状态中没有 queued／running／waiting 请求。2026-08-31 的最终 core_financial 请求 `data_update_b0d6c34ba01b47b2b5873c230bd84b08` 已于 2026-09-15T00:02:48.326792+00:00 完成；此前失败事件不能误读为仍在运行。没有证据支持为了本次验收重新提交同日财务更新。本轮也没有核验新的市场更新资格，更没有重跑已成功股票更新、历史回放或 bootstrap。

新周期结果复核第 1 轮已向同一网页 Pro 提交冻结增量、准确命令、独立回执和真实读取复验，明确请求仅评审本轮读取修复，不请求把局部 ACCEPT 当作上线授权。

## 最终结论与接续边界

网页 Pro 思考 2 分 21 秒后返回 ACCEPT，覆盖冻结的三个读取边界、隔离测试和临时正常应用的实际读取结果；未发现需要修订的本轮代码或关键测试断言。它认可有限 barrier 超时和完整进程退出证据，未要求为缺少显式 abort 重写测试。实际应用运行早于独立测试审查收尾，父代理已如实披露；匹配的冻结哈希和随后完成的独立验证可支持此次运行，不应仅为调整叙述顺序重新运行。当前周期仅使用 1／3 次结果复核，旧周期保持关闭。

父代理最终 review 同意本轮读取缺口已闭合：两个直接 repository reader 在文件检查前解析快照路径，每个线程池任务分别继承提交线程的读取选择，原九次活动库尝试在相同预热和端点验证中降至零。这不是所有可能 API、SQL ATTACH 或网络库的覆盖证明。Sol 实施测试共 21 项，Luna 独立复测其中新增 8 项，不能合计为 29 个不同测试或把全部回归都说成独立复测。最后 targeted diff-check 退出 0，编码审计扫描 4553 文件，未新增 U+FFFD。

正式开关仍未打开，服务保持在线。本轮没有重启正式 API／worker，没有创建业务更新、修改前端选择、推送提交或清理任何已有改动；历史 PIT 留存决定不变。下一步应先围绕本次债券、风险和更新状态的已测耗时做有界性能定位，并核实其他域在受控样本下的目标；只有发现真实必要更新及其可靠来源／日期／请求后，才通过现有后台链路完成服务在线时的写入与五域读取重叠验收，并补齐独立业务核对和代表性浏览器交互。不得为了获得 writer 证据重放成功财务更新，也不得把同源算式闭合当作独立会计审计。全局上线结论继续为未完成，不能用本轮 ACCEPT 覆盖这些剩余验收项。
