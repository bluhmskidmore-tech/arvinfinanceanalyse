# 盘前更新运行安全接续（2026-09-15）

本次已补上选定测试链路在打开数据库前的保护，Luna 独立验证的前置 16 项及原十文件 151 项均通过，网页 Pro 在本轮第一次最终复核返回 ACCEPT，局部测试安全周期已关闭。真实数据源业务访问、历史写入归因和正式在线更新仍未完成，测试结果不代表盘前决策已经可用。

本次承接用户对“继续下一步”的明确同意，先处理测试接触活动库的防护缺口，并只读核定数据源绑定与活动库占用。它是新的最多三轮网页 Pro 复核周期，不是已结束盘前周期的第四轮，也不重开已通过的业务资格实现。

## 起点与范围

前一周期的最终结果见 `docs/system-online-pretrade-closure-2026-09-15.md`：连续合成集成与代码获得接受，正常启用及原全局在线更新验收仍未通过。收尾发现活动库 size/mtime 变化，而完整读取 pointer 不变；实际写入者没有对应证据，归因为 UNKNOWN。不能反推测试有罪，也不能凭 151 项断言通过证明没有默认路径泄漏。（相关执行证据仅保存在本地，公开版本不附原文。）

本轮只读检查首先确认 `tests/conftest.py` 没有 before-open 数据库防护，只有启动跳过、临时目录和缓存清理。根 `conftest.py` 不存在。直接发布调用还会使用 `financial_result_publication.py` 内的 SQL `ATTACH` 打开源库或候选库，所以单拦截 `duckdb.connect` 不足以授权重新运行包含真实发布链的联合测试。

首改应限制在测试入口及最小防护 helper、定向回归。防护必须在收集／导入阶段生效，拒绝正式库和未明确归属的路径，并在 native opener 前留下不含业务内容的技术拒绝证据。允许内存和当前测试自有临时库；不得通过自动改写默认路径、放行整个 `.codex-tmp` 或扩大白名单来掩盖 fixture 泄漏。ATTACH、别名和子进程的覆盖需要明确，不能宣称为通用文件系统沙箱。

## 执行约束与验收

按 goal-based 方式执行，触发为用户本轮同意；最多三轮执行复核，同时最多三个子代理。主要实现仍用 GPT-5.6 Sol，独立验证用 Luna max，父代理负责方案、整合、运行边界及最终结论。第一条证明命令为仓库 `.venv` 下运行新增的数据库防护测试，通过后才允许执行已确认受保护的原十文件组。网页 Pro 只接收脱敏技术摘要，其建议不替代本地验证或用户授权。

不提交、不推送、不清理原脏改动。未授权本轮改变正常服务、调度、权限、凭据、网络或全局读取设置；不打开真实 DuckDB 试锁，不重跑日更、成功财务请求或成功 bootstrap。源 IP 只能依据已有有效本机绑定及原供应商约束确定，不能猜测。缺少有效绑定或实际锁主证据时，必须单独列为阻点，不能以测试保护完成代替上线完成。

局部完成要求是定向拒绝／允许回归与受保护的相关测试通过、Pro 返回 ACCEPT，并准确列出未覆盖边界。原全局完成条件继续继承交接文件：必要更新期间服务保持在线，五域固定代表流程持续稳定一致读取，日期／来源覆盖和延迟按原标准验收。各执行时点与最终处置分节保留，后续结果不改写历史记录。

## 首轮计划与新运行证据

原网页会话可见模式为 6 Pro，本轮明确标识为新用户批准的任务。Pro 的 PLAN_READY 要求先完成 sentinel-backed connect 防护及双测试根的收集期证明，随后补真实 ATTACH 与受测子进程入口，最后才执行原十文件联合组。新增根级薄安装器复用同一 helper，不迁移现有 fixtures。Root 已说明此举具有测试套件级影响；新脏符号不能因 GitNexus 没有调用者而按低风险处理。当前 HEAD 与索引 lastCommit 均为 `3ca0bbc438644214878bd789c4322a722c9d6393`。

当前 pytest 插件元数据包括 anyio、hypothesispytest、xdist、schemathesis、typeguard；没有 PYTEST_PLUGINS 或 PYTHONPATH 注入证据。这里只用 importlib 元数据查询，未导入插件或应用。根 conftest 并不早于全部第三方插件，运行回执需要披露前置插件边界；必要时同 helper 以显式 `-p` 加载，不能用关闭全部插件后的结果替代原组行为。

Luna 的只读记录见 `.codex-tmp/system-runtime-safety-20260915/runtime-preflight.json`。旧来源 IP 当前不属于本机；既有 host wrapper 已动态选择物理默认网关接口，再把同一个地址传给后续步骤。当前有符合现存选择规则的本机候选，但没有证据需要修改为另一个固定地址，也不能仅凭此断言供应商业务访问恢复。当次日志只证明旧地址确实传入且随后失效，无法证明其在任务开始时就不存在。系统 DNS 当前能解析，独立直连 resolver 的一次请求被拒绝；这不是 HTTPS 连接成功证明。

常用 handle 工具未安装，openfiles 查询权限不足，venv 无 psutil，因此原工具路径未识别当前持有者。父代理查阅微软官方 [RmGetList](https://learn.microsoft.com/en-us/windows/win32/api/restartmanager/nf-restartmanager-rmgetlist) 及关联文档后安排一次有界的内置资源查询。只创建临时 Restart Manager 会话、登记精确目标、读取使用者清单并结束该会话，不调用 shutdown/restart，不打开 DuckDB 引擎或变更正常服务。该查询即便得到当前清单，也不能回溯证明历史写入者或写访问权限。

该脚本在普通沙箱的 StartSession 返回 29，尚未登记目标，记录为不可见而非零占用。父代理读取完整脚本后，通过工具审批执行同一个精确资源查询；`2026-09-15T13:35:16.981234Z` 的 Start／Register／GetList／End 均返回 0，当前使用者清单为空。回执单独保存为 `restart-manager-approved-query.json`，原沙箱失败回执保留。文件元数据仍为 3,669,766,144 字节、mtime `12:59:30.519376Z`。查询没有打开数据库引擎，也不证明短时读取永远不存在；历史写入者仍为 UNKNOWN。

诊断脚本后来仅修正退出码语义，要求 GetList 和 EndSession 都成功，不再仅凭资源登记成功就返回 0。三项 fake OS 用例覆盖 GetList 失败、结束失败、全成功；没有为这项修正重查真实文件。最终脚本 SHA 为 `1e964b761dcfd132f0153ae99c9cf9ee7cf55521db52ae895b0ee32f9512642f`，已执行查询回执仍保留执行当时的旧 SHA，不伪装为新版本已做真实查询。

## 首改证明

Sol 已完成根入口、共享测试 helper 与七项 connect 防护回归，首条证明命令得到 `7 passed in 2.90s`；四文件 Ruff 与 diff check 通过。该结果只证明最初 connect 边界。父代理／Luna 静态复核要求继续补齐同一计划内的 caught-denial 整体失败、持久化技术审计、后端测试根独立调用时的自有临时目录登记及双根正负证明，完成后才冻结独立复验。

根级 helper 被既有 `/_*.py` 忽略规则覆盖，父代理因此仅增加 `!/_pytest_duckdb_guard.py` 精确例外，避免交付遗漏；没有 `git add`、提交或更改其他忽略规则。新增入口是测试安全代码，不把它当可随意删除的临时探针。

补齐后 Sol 为 `10 passed in 6.17s`，Luna 独立为 `10 passed in 5.40s`，四份源文件前后 SHA 一致、Ruff 通过。`guard-independent-audit.json` 记录该修订。父代理逐条核对原始 trace 后发现 PID 5176 实为 explicit-plugin 收集拒绝子进程，并非 caught-denial 子进程，已要求更正审计而不改原始 trace。首次保留的九条记录只是 partial trace，其中含 fake-recorder 记录，不能当全部真实连接次数；caught-denial 此时仅有测试内断言证明，原始子回执未保留。后续修订据此要求每个子进程结束立即将回执归入父测试证据。

## ATTACH 与子进程直接切片

第二切片仍不改产品文件，只在测试 helper 中于 collection_finish／runtest_setup 幂等保护 `financial_result_publication` 的两个实际私有构建入口。由 source-path ATTACH 的分支先检查 source 与 candidate；借用连接的分支先确认连接确实由本进程 guard 创建，再检查 candidate。身份登记使用 WeakKeyDictionary，不使用会因对象回收而复用的裸 id，也不以强引用改变连接生命周期。路径校验复用同一策略，发生在原生 execute 前；没有通过 PRAGMA 打开后补查，也没有通用 SQL parser 或连接代理。

选定组唯一子进程在 `tests/test_system_read_publication.py` 内。它先导入同一 helper、登记父测试传入的精确临时 case 根，才导入 DuckDB 并操作合成 fact 表；finally 保证成功或失败都保留连接回执，发生意外拒绝则失败。原发布业务断言保留，只增加安全上下文与回执断言。当前十文件的 publisher 模块在收集期已导入，public function alias 内部仍通过模块全局查找受保护的私有入口；任意 test-body 首次导入、reload、直接 `_duckdb`、提前捕获的其他原生 opener 及未改造子进程不在本项覆盖内。

Sol 的新定向组为 `15 passed in 6.16s`，实际发布复制及 child 用例为 `1 passed in 2.32s`。原始父子记录分别保留在 `attach-guard-slice-proof` 与 `child-slice-proof` 专用目录，后续不会复用这些 basetemp。回归还确认已有 receipt 被 pytest 临时目录重置删除后，会由内存完整重建，不漏掉此前收集阶段记录。helper 暂冻结为 `396893ec8eee1283e4bdfb91220eb078314120739235309d93b45c9c6599d4b3`，新增 guard test 为 `9b47abea44fdcd24bcc7111ef5b6f6d6e25c9d31865ba4795b825a42acf24571`，现有 publication test 为 `d62d41e87e8b588597732717ebe3fd2ce911ab12a7bd7fa08b0dca1fb2fc0318`。

父代理条件授权 Luna：先独立验证上述定向边界及冻结哈希，全部通过后，才以显式 `-p _pytest_duckdb_guard` 前置插件运行原十文件联合组。任何前置失败、哈希漂移或不明意外拒绝均停止，不以扩大允许目录或修改业务断言换取通过。实际完成结果见下一节，不与先前未加保护的 151 项混用。

## 最终受保护回归与原始证据

Luna 的最后独立前置调用为 15 项 guard 回归加实际 publication child 用例，`16 passed in 6.94s`，退出码 0；五份 Python 文件 Ruff 全部通过。随后同一最终源码的原十文件组在一个新进程中一次运行，结果为 `151 passed in 74.70s (0:01:14)`，退出码 0。此处的 16 和 151 有用例重叠，不相加为独立覆盖总数，也不代替前端或真实业务验收。

父代理接手收尾后逐条读取、计算 SHA 并核对两份原始 JSONL，而不是将复制文件累计为事件。主进程回执记录 871 次授权检查，包含 845 次自有临时路径和 26 次内存；子进程独立回执为一次自有临时路径检查。两者均没有拒绝记录，没有任何获准的非内存目标越出本次精确 basetemp。主进程访问类型为 297 次读写／默认、472 次只读、51 次源库 ATTACH 和 51 次候选库 ATTACH。这些是进入 native 操作前的授权检查次数，不是独立连接数，也不保证每次 native 调用最终成功。借用连接分支由定向正负测试证明，不能写成它也被这 151 项的 trace 实际覆盖。

原始文件保留在 `.codex-tmp/system-runtime-safety-20260915/guard-final-151-basetemp-luna-1789481220490/`，不能复用或清理该 basetemp。主回执 `pytest-duckdb-guard-attempts.jsonl` 的 SHA 为 `35d7b21148ff6f1dc491b6dbe7451e1041677e904f593f18cb496809773c0e0a`；子回执 `test_full_database_publication0/pytest-duckdb-guard-attempts.jsonl` 的 SHA 为 `9ebe9825439ec4e5117f4dcc4d54748ccc9c93439d7b4068cf36b757ea455cbf`。

最后前置组的复制汇总 `guard-final-connection-trace-exact.jsonl` 有 37 行，其中包括原件及副本的重复和 fake-recorder 记录，不是 37 次真实 native 操作。首次十项的 partial trace、PID 归类更正和未保留的 caught-denial 原始子回执仍按前节披露；后来的完整受保护联合组不能倒推补齐那份旧证据。

父代理的独立汇总为 `.codex-tmp/system-runtime-safety-20260915/guard-final-root-audit.json`，不是没有完成的 Luna 最终审计文件。`2026-09-15T14:15:10.223Z` 根核查确认 20 份此前已接受产品源码哈希全部匹配，五份 Python 防护源码仍对应 Sol 冻结版本，完整 pointer 的 SHA 保持 `dd0c1c6b4222ddc37b71b8ebbf56f5370384345c57313439f8dd2e7ed1b1cdf0`，活动库 size/mtime 仍为 3,669,766,144 字节及 `12:59:30.519Z`。这不是 Luna 对所有文件的另一份前后报告，也不扩大为全程无副作用证明。

以下是已执行命令的归一化记录，不是要求重跑。后续执行不得复用已保存证据的 basetemp，否则 pytest 可能清空原始回执。

```text
.venv/Scripts/python.exe -m pytest -p _pytest_duckdb_guard -q --basetemp=.codex-tmp/system-runtime-safety-20260915/guard-final-151-basetemp-luna-1789481220490 tests/test_pretrade_qualification_contract.py tests/test_pretrade_checklist.py tests/test_livermore_daily_pretrade_refresh.py tests/test_livermore_pretrade_check_export.py tests/test_system_read_publication.py tests/test_system_read_market_publication.py tests/test_system_read_market_publication_integration.py tests/test_system_online_read_boundary.py tests/test_pretrade_producer_full_integration.py tests/test_pretrade_sealed_api_integration.py
.venv/Scripts/python.exe -m ruff check conftest.py _pytest_duckdb_guard.py tests/conftest.py tests/test_test_database_guard.py tests/test_system_read_publication.py
.venv/Scripts/python.exe -m py_compile conftest.py _pytest_duckdb_guard.py tests/conftest.py tests/test_test_database_guard.py tests/test_system_read_publication.py
node scripts/audit_encoding_integrity.mjs
```

Ruff 与 py_compile 在父代理收尾时再次退出 0。先前最终编码检查扫描 4526 个文件，新增 U+FFFD 为 0；定向 diff check 通过。源码改动仅为根 `conftest.py`、`_pytest_duckdb_guard.py`、`tests/conftest.py`、`tests/test_test_database_guard.py`、现有 publication test 的 child 安全上下文和 `.gitignore` 精确例外。没有修改本轮之外的产品实现、财务公式、正常调度或全局开关。

## 最终复核与接续边界

北京时间 22:42，父代理向原网页可见 6 Pro 提交本轮第一次最终复核包。Pro 随后返回 ACCEPT，接受检查过的 pytest 路径保护、定向边界证明和独立受保护的原十文件回归，没有要求追加执行轮次；它明确不接受全仓库隔离或正式运行安全认证。只发送了脱敏技术摘要、最小代码摘录、验证命令和证据边界，没有发送原始银行数据、金额、私有 IP、凭据或真实来源版本字符串。复核结论源自所提交材料，Pro 未直接读取本地文件或运行测试；旧盘前第三轮的 ACCEPT 未被替代为本轮 verdict。摘要回执为 `.codex-tmp/system-runtime-safety-20260915/pro-final-review.json`。

`2026-09-15T14:46:45.888Z` 最终只读观察确认正常 API `/health` 和前端根路径均为 200，六份本轮源码／配置哈希、20 份此前冻结产品哈希仍匹配，活动库 size/mtime 及完整 pointer SHA 未变。只读取源码、JSON、文件元数据和既有健康入口，没有为了查锁而打开数据库。该独立时点记录见 `.codex-tmp/system-runtime-safety-20260915/runtime-final-readonly-snapshot.json`；较早的查询和审计没有被覆盖。

测试保护只覆盖本次检查的连接入口、两个发布 ATTACH 入口和受测 Python 子进程。任意其他 SQL ATTACH、直接 `_duckdb`、安装前捕获的原生 opener、测试函数内首次导入或 reload publisher、未改造子进程、主动替换 guard 和文件系统竞态都不属于通用保护承诺。根 conftest 不早于每个第三方插件；本次 151 项明确使用 `-p` 前置同一个 helper。

运行侧目前能确认的是：已有动态来源 IP 选择规则存在有效本机候选，系统 DNS 可以解析，获批的精确资源查询在该时点没有列出使用者。尚不能确认供应商业务链路可用，不能回溯识别 20:59 的写入者，也不能把查无当前使用者等同于获得写访问权。下一步应先按现有入口核验真实盘前依赖和业务访问，并在操作前重新取得当前进程／任务证据；没有必要新来源变化时不发起财务更新。

正式启用、真实盘前资格、全服务在线时必要更新成功、原五域固定流程 5／10 并发及 P95、独立业务对账仍未通过。既有健康服务、完整 pointer、成功 bootstrap 和成功财务请求全部保留。本轮没有财务重跑、bootstrap、日更重提、手工 drain、停止／重启正常服务、网络或权限修改，也没有提交或推送代码。
