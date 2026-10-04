# 真实盘前恢复接续（2026-09-15）

用户同意继续核验供应商真实访问及盘前依赖，并要求继续拆分子代理、由父代理最终验收。本轮从真实运行失败开始，不重开上一轮已经接受的测试保护，也不以新增诊断代替盘前产出恢复。

## 本轮范围与起点

采用新的 goal-based 周期，最多三轮执行复核、同时最多三个子代理。Sol 分别核对供应商入口和盘前依赖，Luna max 独立核对运行状态及定向证明，父代理负责 Pro 方案复核、真实操作判断、整合与最终验收。开工文件哈希见 `.codex-tmp/pretrade-live-recovery-20260915/start-source-manifest.json`；此前接受的 20 份产品源码及六份测试保护／配置文件均匹配。

`2026-09-15` 的既有市场 aggregate 是 `business_failed`。Choice、宏观 freshness、新闻失败，复权和涨跌停因上游未经验证被跳过，盘前步骤也未执行。独立宏观 chain 虽退出 0，但业务回执为 degraded，不等于合格业务成功。盘前没有执行，不能据此断言它在本日实际计算后发生了成熟度失败。详细技术状态和精确来源见 `dependency-start.json`；其中没有原始来源路径的 9 月 14 日旧探针线索仅保留为未核实历史说法，不作为当前 blocker 或资格证据。

已有 `PublicationOnly` 只恢复 `business_completed`／`publication_failed`，不能恢复本次 `business_failed`。正常市场入口会执行七个业务子步，没有按失败子步自动续跑能力。本轮不新增通用恢复框架，也不拿重跑整链试连。成功的 8 月 31 日财务请求和成功 bootstrap 继续禁止重放；尚未发现需要新财务更新的来源变化。

页面合同 `GAP-STOCK-ANALYSIS-PAGE` 的主问题是能否继续复核候选。`GET /ui/market-data/stock-analysis/workbench` 是首屏队列权威，日期、缺失、回退与资格不能在前端改写。该页维持 `observational_only`、`basis=analytical`、`formal_use_allowed=false`，不因数据恢复而变成交易批准。本轮血缘／指标／数据目录 MCP 方法不可调用，使用本地页面合同、实际代码和具名 JSON 回执替代；未核实的业务字段保持 UNKNOWN。

## 当前运行与访问证据

Luna 的 `runtime-start.json` 记录正常 API／前端健康 200、活动库 size/mtime 和完整 pointer 身份未变。普通沙箱的 CIM 及既有 ResolveOnly 读取被拒绝，一次 schtasks 回退也不可用；这属于工具可见性限制，不能写成任务异常或当前无网卡。

父代理完整读取既有 `run_daily_data_refresh_host.ps1`，确认 ResolveOnly 在加载 dev-env 和调用业务链之前退出，随后按工具审批执行精确只读查询。当前存在符合既有物理网卡／默认网关规则的已分配来源地址；两项正常任务均 Ready、enabled，市场任务保留该次失败，队列最近执行为 0。原权限失败记录保留，新结果另记 `approved-readonly-runtime.json`。没有启动任务、换固定 IP、改网络或打开活动 DuckDB。

供应商路径核查确认现有 Choice CLI 的 `--dry-run` 会读取活动库及治理记录，不能作为零数据库网络探针。完整 worker 在物化前写 running 治理记录，更不能用于试连。已有 `_DefaultTushareStockClient.trade_cal`／`daily_basic` 直接使用官方 HTTPS 根 API、现存 token resolver、`(10,30)` 超时，不自行写库或治理；外围 materialization retry 不应进入单次诊断。Tushare 日历可访问与失败端点 daily_basic 的权限是不同证据，也不能外推到 EmQuant。

## 最小首改及验证门槛

原可见 6 Pro 会话已返回本轮 PLAN_READY，选定独立 `scripts/check_stock_supplier_access.py` 及对应测试，不改正常 Choice CLI 的读写分支。Sol 负责这两个新文件；另一个 Sol 独立只读核查复用客户端的重定向、重试、凭据目的地和来源绑定；Luna max 在源码冻结后复验，父代理保留真实访问和最终验收职责。必须显式给定规范目标日和当前已分配 IPv4，不能回退到自动日期或不绑定连接；每次只检查一个明确端点，没有自动重试、备用数据源或自动 ETL。

本轮真实检查选择原失败端点 `daily_basic`，只给定 `2026-09-15`、一个公开测试代码和 `ts_code,trade_date` 身份字段。不会先做日历请求，再自动增加第二次请求。独立入口可以显式选择单日 SSE 日历，但日历结果不能替代 daily_basic 权限证据。输出限制为 state、date、count、elapsed、error_class；尚未收到有效响应时 count 为 null，不能把连接失败写成零行。

首个代码证明使用 fake HTTP 和禁止数据库／治理／物化调用的哨兵，验证输入检查、确切调用次数、HTTPS／超时、来源绑定恢复、返回日期和行数，以及不泄露凭据或原始错误的技术输出。定向 pytest 必须显式加载已接受的 `_pytest_duckdb_guard`，使用本轮全新临时根，不复用旧证据目录。Sol 首改与证明完成后由 Luna 独立复验，父代理核对最终源码，才安排一次限定真实访问。

真实读取仍须在执行前核定日期、参数、现存凭据用途、当前绑定、活跃任务及输出脱敏方式。日历空结果、日期不符、权限／配额、DNS／TLS／超时分别记录，不能写为盘前就绪。实际 requests 路径没有传输层字节硬上限，响应后行数限制不等价于响应字节限制；不得据此宣称通用有界网络客户端。

正式启用、真实盘前资格、全服务在线的必要更新、原五域 5／10 并发与延迟、独立业务一致性仍是待验收条件。本轮不改公式、成熟度、策略或资格门禁，不停正常服务，不改权限、凭据、网络、调度或全局 SDK，不提交、不推送、不清理脏工作区。

## 9 月 16 日接续核验

用户再次要求继续。北京时间 07:41 的只读检查显示，26 份已接受源码仍全部匹配，正常 API／前端健康均为 200，活动库元数据与完整 pointer 哈希保持上述起点值。仍使用原失败请求的 `2026-09-15`，不因跨日自动执行新日更新。实际证据见 `continuation-readonly-20260916.json`。

独立传输审查发现，正常共享 Tushare 客户端未禁用重定向，307／308 可保留含 token 的 POST body；该共享风险尚未修复。本次诊断只在独立进程的临时上下文中强制 `allow_redirects=False`、`verify=True`，拒绝重复 POST 和 3xx，退出时恢复原函数，没有修改共享客户端。Requests 的本机默认 transport retry 为零；这不代表 DNS／TCP 只尝试一个地址，也不是传输字节硬上限。

普通沙箱的 HTTP(S)／ALL proxy 指向回环禁网端口，因此不能将该环境中的失败解释为供应商不可用。父代理获批执行的环境只读检查确认这三项代理与自定义 CA 均未配置，没有改动任何网络设置。随后完成源码冻结及 Luna 独立验收，真实调用结果见下节。

## 单次真实端点验收

新增诊断与测试已经实现。产品脚本 SHA-256 为 `bd14f211214baaf34235225e43ee6108cf1eca456a0461df2fb71ddbe005f28f`，最终测试 SHA-256 为 `39cb7499f5ddbf4b623ae7df9f2edb7dee6925d06e373685e27bd87b6011bb2c`。根验收与 Luna 均发现首版测试缺少具名治理／缓存／任务副作用哨兵，因此仅补强测试：全新受保护子进程在真实 helper 导入前安装双 DuckDB 连接哨兵，导入后拦截具名业务入口，再实际执行 fake-HTTP daily_basic。连接与业务入口计数为零，请求为一次。这证明受测路径，不是通用 native-I/O 沙箱。

Sol 补强后 36 项通过，Luna 在另一全新临时根独立复跑仍为 36 项通过，用时 7.39 秒；前后两文件 SHA 相同。Ruff、编译和编码完整性通过。旧版 36 项、中间失败和最终 36 项没有相加成不同用例总数；入口尚不存在时的 import errors 也不作为业务红测。精确命令及工具输出见 `single-live-diagnostic-root-audit.json`。

父代理在真实调用前重新运行既有 ResolveOnly，当前已分配来源地址确已不同于前夜，两项正常任务均为 Ready。使用新地址，固定公开 fixture `000001.SZ`、日期 `2026-09-15` 和身份字段，执行了唯一一次 daily_basic 读取。真实输出为 `state=matched`、`count=1`、`elapsed=3507`、`error_class=null`，进程退出 0。没有先查日历，没有重试或派发业务更新；07:52 的调用后核对显示，活动库元数据、完整 pointer 哈希未变，7888／5888 健康均为 200。

由此只接受当前网络环境下该端点、该日期、该代码的身份访问，不外推到 Choice 全量、复权、涨跌停、宏观或盘前候选资格。下一步须先核定补数入口：当前已跨至 9 月 16 日，既有 scheduler 在发布启用时拒绝历史 AsOfDate，因为无日期的宏观 freshness writer 会混入当前数据；旧 business_failed aggregate 也不满足 PublicationOnly。不能绕过该保护或仅因单端点成功就重跑七子步。

根与 Sol 对既有 scheduler／market-publication 控制器的定向检查进一步确认，factor、limit、news 等命令绑定活动库，其他子步使用默认 settings；这两个入口没有统一隔离库参数或失败子步恢复命令。正常全局选择目前仍关闭，disabled publication 分支并不是隔离写入机制，不能凭它证明在线补数安全。旧回执保留为 business_failed，不追加或篡改其中已存在的子步。该结论限定于已经检查的入口，不宣称穷尽整个仓库的全部机制。

07:56 已向同一可见 6 Pro 会话提交本轮第一次结果复核，随后返回 ACCEPT，范围仅为冻结诊断、36 项独立证明和一次真实端点访问。正式启用、真实盘前恢复及原全局验收未获接受。复核仅含脱敏技术文本，没有源文件上传、凭据、私有地址或原始业务数据；具体验收边界见 `pro-diagnostic-review-1.json`。

Pro 指出的最小下一步比新增隔离框架更窄：先检查首个失败股票 producer 的直接 callable。CLI 没有统一库参数，不能推断其下层函数也不能指定库。父代理依用户“继续”要求将这一受限执行边界证明交 Sol，初始仅允许新增一个测试文件，真实业务代码先只读；用模拟供应商和临时存储证明目标日与全部写目的地可绑定，Luna 再独立复验。若某个早期默认访问无法显式限定，先报告确切位置，不据此派发真实 producer，不改历史日期保护或旧失败回执。

## 现有股票任务的隔离执行证明

直接 callable `backend/app/tasks/choice_stock_refresh.py::run_choice_stock_refresh` 已能显式接收 `duckdb_path`、`catalog_path`、`governance_path`、`archive_root`、`as_of_date` 和 `history_start_date`，并传入现有 `_run_choice_stock_refresh_job`。因此本步没有新增生产入口或恢复框架，只增加 `tests/test_stock_refresh_isolated_execution.py`。其最终 SHA-256 为 `0bac4be1fc8e794f74eafdec4ac88757e21d5c2dd0aefe0f68e8c5cab98fafd1`；上述两个产品文件未修改。

正例只替换 Choice 客户端，实际执行既有 producer、materializer、事实表和运行／完成治理回执，将四类目的地限定为测试自身拥有的临时目录。报告日与历史起日均为 `2026-09-15`，所有带日期的 sector、CSS、CSD 调用均核对该日。实际临时库生成一条 materialize run、七条请求审计和四类历史事实行，治理记录为同一运行的 running、completed。Tushare、因子、缓存、overlay、Livermore、额外 manifest 等具名下游的调用计数为零；这些下游没有执行，不能写成完整 Choice 或盘前恢复成功。

测试插件在应用导入前加载；新增测试局部哨兵进一步覆盖受测的 Python 写入、目录创建、替换／移动及双 DuckDB 打开入口。正例独立断言拒绝计数为零，避免应用捕获异常后隐藏越界企图。两个反例分别证明外部治理路径和非精确数据库目标在底层打开前被拒绝。哨兵只存在于测试中，不是生产任务已有的通用运行隔离；本步实际打开了临时 DuckDB，不是零数据库调用。

Sol 最终三项通过，Luna max 在另一全新临时根独立复验仍为三项通过；源码哈希未变，定向 Ruff 与编译通过。Luna 唯一警告为 `PytestCacheWarning`，技术缓存目录 `.codex-tmp/pytest-cache/v/cache` 已存在，来源是 pytest cacheprovider；没有清理缓存或修改权限。精确命令如下，完整证明见 `.codex-tmp/pretrade-live-recovery-20260915/stock-history-isolated-proof.json`。

```text
.venv/Scripts/python.exe -m pytest -p _pytest_duckdb_guard -q tests/test_stock_refresh_isolated_execution.py --basetemp=.codex-tmp/pretrade-live-recovery-20260915/stock-history-isolated-sol-final3-20260916g
# 3 passed in 2.26s，exit 0
.venv/Scripts/python.exe -m pytest -p _pytest_duckdb_guard -q --basetemp=F:/MOSS-V3/.codex-tmp/pretrade-live-recovery-20260915/stock-history-isolated-luna-independent-20260916 tests/test_stock_refresh_isolated_execution.py
# 3 passed in 2.09s，exit 0
```

这份证明只覆盖主源 Choice 的合成历史子段，没有进入 Tushare gap-repair 或旧 daily_basic 失败分支，也未核定旧运行已经落地哪些真实历史行。它不能作为重跑真实历史或启动完整日更的依据。若继续真实恢复，须先用既有只读接口／回执核对明确日期的实际缺口，再检查目标供应商分支的全部输出目的地及运行回执；没有证据时保持 PENDING，不能盲目补数。

父代理 08:24 的只读收尾确认原 26 份保护源码、三份新文件及两份被调用产品源码均未漂移，7888／5888 健康均为 200，活动库元数据与完整 pointer 哈希保持本轮起点。08:15 正常 `GET /api/system-read-publication` 为 HTTP 200、`enabled=false`。完整记录见 `final-root-state-20260916.json`；这些是时点观察，不替代真实更新期间的在线证明。

网页 6 Pro 第二轮返回 ACCEPT，没有要求修改，范围仅为这份冻结三用例执行边界证明。复核明确指出：真实 daily_basic 身份请求和模拟 Choice 主源历史是不同分支，不能拼成端到端恢复结论；负例证明的是测试哨兵，不是未修改生产 callable 自带路径禁入保护。完整接受边界见 `pro-isolated-history-review-2.json`，Pro 仅看脱敏技术摘要，未读取仓库或亲自执行测试。

本轮由 Sol 实现一份独立诊断脚本及两份测试，Luna max 分别独立通过 36 项诊断测试和 3 项历史子段测试，父代理检查最终源码／技术回执并执行唯一一次真实端点访问。没有重跑成功财务或 bootstrap，没有服务停止、调度变化、全局开关修改、旧失败回执变造、提交或清理。当前仍不能向用户交付“盘前已经恢复”或“系统全局完成”；下一项只读工作是查明已落地事实和必要缺口，不能以缺乏证据为由直接再写一遍。

## 复核后的旧运行写入边界补证

父代理随后让 Sol 只读寻找既有状态入口。`GET /ui/macro/toolkit/choice-stock/refresh-status` 要求正常读取权限及运行归属校验，并非纯 JSON 回执接口：它还会打开当前 selected DuckDB 构造 overview。它既不能还原旧运行的部分提交，也不符合本轮不新增活动库连接的限制，因此没有调用，更没有伪造身份绕过归属检查。

旧 aggregate 内嵌 Choice 回执与具名外部 JSON 的规范序列化哈希一致；该哈希不是原文件字节哈希，父代理已分别计算，未将格式差异误判为篡改。回执确认报告日、历史起日均为 `2026-09-15`，实际 `tushare_gap_repair=true`，与本轮三项主源测试的分支不同。仅凭 failed、null 行数和缺少 source/vendor version，不能判断异常发生在业务提交前还是后。

进一步证据来自旧交接已明确引用的 `.codex-tmp/system-online-pretrade-20260915/daily-refresh-readonly-diagnostic.json`，不是扩大扫描日志目录。其指定的 `scripts/scheduling/logs/20260915.log` 第 74—109 行保存了实际异常栈：history 的 `materialize_choice_stock_inputs:362` 调用 `_sector_strength_rows:1549`，进入 `_daily_basic_by_key:1686` 后发生 DNS ConnectionError。主事实事务到源码第 624 行才开始，第 699 行提交；该异常在第 559—571 行处理后重新抛出。worker 在 history 返回后才会开始 factor。因此证据现已缩窄为：这一具名调用在自己的历史业务表事务前失败，没有提交该次历史事实，也没有到达其 factor 步骤。

同一日志第 114—116 行还表明，失败审计在 `_persist_failed_materialization:2498` 打开数据库时被占用拒绝，不能算成功落库。治理和 JSON 失败回执则确实存在，所以结论不是“本次零写入”。这项补证也不证明当前数据库没有别的任务写入同日数据，更不能解释后续活动库 mtime 变化。父代理已将 Sol 最初仅凭 JSON 得出的过强判断退回，直到获得上述实际栈才接受这个限定结论。

技术来源、运行身份、行号和哈希见 `old-run-write-boundary-root-audit.json`。该补证发生在第二轮 Pro 接受之后，属于根只读验收，不冒充 Pro 已接受真实恢复。下一步应对准已证实的 Tushare gap-repair 分支验证隔离输出，并通过既有获准读取／快照边界核定当前目标日覆盖，之后才决定必要补数。当前盘前和全局验收仍为 PENDING；本轮没有派发第三轮真实更新。

最终编码完整性检查扫描 4,532 个文件，新增 U+FFFD 为零。三份新源码与四份文档另经 Node 直接检查 UTF-8、BOM、尾空格和文件结尾；不能用不覆盖 untracked 文件的 `git diff --check` 替代这一证明。检查期间的编码／格式输出另存 `final-format-audit.json`，定向测试命令与警告保留在前述两份测试证明中，原脏工作区继续保留。
