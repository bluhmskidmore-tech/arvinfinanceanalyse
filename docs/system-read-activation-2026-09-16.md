# 普通 API 封存读取接续与盘前资格核查（2026-09-16）

用户在上一轮修复加载、真实覆盖检查之后要求“继续处理”。本轮先解决环境路径会因活动库占用而切换的问题，再对当前源码、现有前端和现存完整 publication 做普通 API 切换预检。盘前回放资格另作有界只读定位，不混入首个代码修改。原全局目标仍是必要真实更新期间五域读取稳定且一致，不以本文件或局部测试代替该验收。

## 本轮边界与起点

本轮为新的 goal-based 执行周期，最多三次网页 Pro 结果复核、同时最多三个子代理；此前已关闭的三轮及六文件 96 项验收不重跑。Sol 实施，Luna max 独立复验，父代理负责实际运行、集成和最终判断。相同阻塞出现两次、关键业务意义不明或预算耗尽时收口并留下准确缺口，不重置循环。用户已经给出的本机运行切换和必要更新授权继续有效，不由网页建议代替授权。

13:34 附近只读快照显示正常 API／前端均 200，完整读取发现接口仍 enabled=false，现有前端 selection 为 `frontend-remaining-20260916/accepted-build-final`。活动库 stat 为 3,669,766,144 字节、mtime `2026-09-16T02:51:50.410Z`；只读其文件元数据，没有复制或哈希活动库。完整 pointer 哈希仍为 `dd0c1c6b4222ddc37b71b8ebbf56f5370384345c57313439f8dd2e7ed1b1cdf0`，无维护标记。

上一轮已经用真实只读检查证明 9 月 15 日基础资料及数值限价覆盖齐全，并识别已有成功股票终态 `choice_stock_refresh:2026-09-15:f55995a15335`。当天行情、因子、复权、限价和旧失败 aggregate 均不重放；成功财务与 bootstrap 同样禁止重放。现有盘前 closure 的 replay partial、风险 block 是待核实业务状态，不能通过修改阈值、掩盖不可用或重新盖章消除。

## 首个已证实根因与最小方案

`scripts/dev-env.ps1` 调用 `dev_postgres_cluster.py print-env`。当前 `command_print_env` 先运行 `_prepare_runtime_clean_paths`，它有初始化和复制能力；随后 `_resolve_storage_root_for_env` 把 `_duckdb_has_seed_data` 的开库错误当作 False。正在被 writer 占用的正确 repo 库可能因此被误认为无资料，连同治理、归档及输入目录一起切到 runtime-clean。路径配置不应由瞬时数据库健康决定。

首改范围只包含 `scripts/dev_postgres_cluster.py` 的这两个函数及对应定向测试。拟让 print-env 仅生成环境映射，不执行准备／复制；repo 路径存在时保持其归属，健康由既有启动检查另行拒绝，不能因零字节、损坏、占用或权限错误悄悄改用另一库。repo 缺失时保留有证据的既有 runtime 默认，异常文件类型须明确失败。显式 command_up 的准备、迁移、grants 和 bootstrap 不修改，本补丁不认证它们可在 writer 并发期间运行。

GitNexus 正确项目与 HEAD 均为 `3ca0bbc438644214878bd789c4322a722c9d6393`。`command_print_env` upstream 为 LOW、一名直接 caller main；resolver 为 LOW、三层 upstream，直接 caller 为 build_env_mapping。图谱没有反映 PowerShell caller，实际影响包括 API、worker 和开发运维入口，已经向用户披露。指标／血缘／目录 MCP 不可调用，使用具名代码、页面契约、回执和只读检查替代，不推断新的业务口径。

首个证明应在测试自有目录以真实子进程持有 RW 连接，复现旧环境选择错误或非法开库／复制，并验证修后 idle 与 held-writer 的 repo 数据及 sidecar 路径一致、配置查询零 connect 和零 mkdir／copy。随后运行定向边界用例及 `tests/test_dev_postgres_cluster.py`，使用显式仓库 Python、`-p _pytest_duckdb_guard`、全新 basetemp；独立复验前冻结源码。普通 API 激活前另需当前完整版本资格、五域和盘前 unavailable 合约、当前前端兼容性及恢复方式的实际检查。

不修改 core_finance、指标公式、成熟度／风险门槛、权限、调度、队列或当前前端 selection。不提交、不清理现有改动和证据。

## 网页方案复核与盘前实际分类

本轮原网页会话的可见模式为 6 Pro，已返回 PLAN_READY，认可先把环境解析与数据库健康分离。方案要求真实临时库 writer 占用下完整环境映射不变，并用独立断言证明 print-env 不连接、复制或初始化；明确不把该局部修复外推为 command_up、启动迁移或正式在线更新已安全。此处仅为方案回执，尚无本轮结果 ACCEPT。

父代理以受监督子进程调用现有 `livermore_candidate_history_backtest_window_summary`，目标为 2026-09-15、既有窗口为 2026-03-19 至 2026-09-15。子进程总时限 45 秒，先取 canonical path lock、等待上限 5 秒，只允许一次明确目标的 native read-only 连接并传入 `_conn`，拒绝 HTTP；未运行 producer 或业务更新。第一次读取成功但工具输出被截断，不能当作完整明细证据；第二次约 9 秒退出 0，将完整技术明细以排他创建方式保存在 `.codex-tmp/system-read-activation-20260916/live-replay-reasons.json`。两次均是只读检查，不是更新重试。

真实分类为 completed 20 日、pending 8 日、unsupported 92 日、proxy-only 4 日。pending 中 6 日属于自然尾部：8 月 24 日、9 月 8、9、10、14、15 日；非尾部阻塞是 7 月 21 日和 8 月 18 日，分别有 6 行和 1 行前向柱缺口。92 日均为 `missing_required_source_table`，覆盖 3 月 19 日至 9 月 3 日之间的部分交易日，提示涉及行情、交易状态、股票池、行业归属、行业强度、限价标识和连续涨停来源覆盖；该分类本身还不能区分原始事实缺失与覆盖记录缺失，不据此批量补跑历史。

proxy-only 的具体日期为 4 月 13 日、5 月 20 日、7 月 8 日和 7 月 10 日，不是等待自然成熟能解决的缺口。执行可用统计只有 `factor_screen`、`fresh_trend_watchlist`、`hybrid_fusion`、`mean_reversion`、`uptrend_momentum`，没有资格判定所要求的 `stock_candidate` 键，因此不能将 matched_entry_count=0 简化解释成已核实无交易。现有风险 block 与回放数据资格是两道独立门槛，均未修改。

现存完整 publication 的 bundle 为旧版，没有 `pretrade_availability`。仓储明确将其解释为 `legacy_system_read_bundle_has_no_pretrade_qualification`，不得因活动库当天资料齐全而替该封存版本补造 ready。正式启用仍须遵守已有候选验证和业务资格门槛；本轮不会仅凭环境解析修复自动开启全局开关。

进一步沿原 coverage loader 追踪发现，资格取 `choice_stock_request_audit` 合格记录与各事实表已落地字段的交集。父代理随后对上述 92 个具体缺口日期执行一次同等保护的真实只读核查，约 5.5 秒退出 0，证据为 `.codex-tmp/system-read-activation-20260916/replay-missing-authority.json`。92 日都存在事实覆盖缺口，没有任何一天仅缺审计记录；其中 90 日还含“事实已落地但对应审计未齐”的条目，5 日含“审计已齐但事实未落地”的条目。这是条目级交集问题，不能把几类日期数量相加，也不能手写审计记录补资格。

对该已保存回执按字段汇总后，92 日的事实缺口精确收敛为同样三项：`limit_up_quality:point_in_time_limit_streaks`、`sector_membership:sw2021_industry_membership`、`stock_universe:a_share_universe_sector_001004`，每项各缺 92 日。四类 daily observation 字段在 coverage 所用规则下已经落地。因此不能把这 92 日描述为整天没有行情，也不能据此重抓整窗日线、复权或限价。后续恢复必须证明来源在所选历史时点成立，不能把当前股票池／行业成分标成历史数据。

同一次读取按原 loader 统计整个请求窗口，`stock_candidate` 候选行 32、执行行 28、entry_executable 行 27；这批是尚未按决策日期资格及 point-in-time 收益掩码筛选的原始窗口计数，不是 matched_entry_count，也不证明两个期限统计已齐。生产 materializer 明确支持该 signal_kind，不能把别的策略种类当作其别名挪入硬门槛。现有证据已排除“所有 stock_candidate 执行行根本不存在”的解释，具体哪些行被日期资格排除尚未逐行审计。

## 实际环境及封存版本预检

Sol 完成生产修复后，父代理通过修复后的真实 `scripts/dev-env.ps1` 加载环境，再运行受监督的 `inspect_sealed_read_preflight.py`。只在该检查子进程内启用完整读取，以现有 `system_read_scope` 及封存验证器解析当前 pointer；没有修改服务配置。2026-09-16 13:52 的检查退出 0，原始回执为 `.codex-tmp/system-read-activation-20260916/sealed-read-preflight.json`，SHA-256 为 `0243fb1a0826da9e845f86c3f979e32c278e3f62d8b0ed2f96208a4da55c6d39`。

实际数据路径为 repo 的 `data/moss.duckdb`，治理、归档和输入分别为 `data/governance`、`data/archive`、`data_input`。同一子进程在应用模块导入前安装连接限制，只允许两处既有 immutable generation 目录的只读打开；实际共两次 native open，分别是完整快照和其已绑定的损益快照，活动库打开为零。现有完整 generation、损益 generation、manifest 和 12 张表的 8 月 31 日覆盖均通过既有验证。盘前状态仍明确为 unavailable，原因是旧 bundle 没有资格凭证。

该检查前后活动库 stat、完整 pointer 哈希、当前前端 selection 哈希和已修环境脚本哈希均未变化。selection 哈希为 `0a58745ebeb014ce3e68f7ab9a8c3f82a8eda079d40862d4abea5d0fe505b56e`。这些是实际路径与现存封存资格的预检证据，不是正常 API 已切换、当前前端与新读面交互通过、实际 writer 并发或更新完成证明。

普通 `dev-api.ps1` 仍会调用 `dev-postgres-up.ps1`，随后 `Assert-DevBootstrapStorageReady` 仍直接只读探测活动库；前者保留准备／迁移，后者没有 canonical admission。本轮没有运行这条启动链，也未认证它可在写任务并发期间安全执行。纯环境修复不会自动消除这个独立启动门槛。

## 环境修复独立验收

Sol 只修改 `scripts/dev_postgres_cluster.py` 的两个函数并导入 stat，`command_print_env` 直接返回原 build_env_mapping；resolver 只检查文件系统元数据，保留合法别名，拒绝坏路径及元数据错误。生产文件 SHA-256 为 `866bf3ebd41b20748d4888007164885fedd2539cd43f55c850ececbeea330dea`。原测试替换了“复制遇到 PermissionError 后容忍继续”的旧预期，改为 prepare、copy、mkdir、connect 零调用硬断言；显式初始化测试保留。

旧实现红测为 8 failed、2 passed，退出 1，其中真实独立 RW holder 已直接复现 repo 数据及 sidecar 整组误切 runtime；哨兵测试失败另记为纯度失败，不混称开库锁错误。首次 Luna 的 36 项通过后，父代理发现其回执只证明父进程受 guard 保护，要求 Sol 补子进程保护，而不是接受边界缺口。最终测试在被测模块导入前安装现有 guard 和 HTTP 哨兵，真实执行原 CLI；查询的 guard 回执存于被测 repo 外，holder 有真实 ready barrier 和精确进程回收。

最终 Luna 在全新 basetemp 仅运行一次以下联合命令，结果 36 passed in 5.66s、退出 0：

```powershell
.venv/Scripts/python.exe -m pytest -p _pytest_duckdb_guard -q tests/test_dev_postgres_print_env_purity.py tests/test_dev_postgres_cluster.py --basetemp=.codex-tmp/system-read-activation-20260916/luna-env-a2
```

父进程 guard 18 条、holder 子进程 1 条授权记录均为 owned_temp/allow；这些不是连接数。空闲、writer-held、失败 CLI 三个查询子进程的 before/after 数据库尝试均为 0，HTTP 调用为 0。真实 holder 在本测试库上有一条 RW 允许记录，测试后已退出。测试创建和修改的是自有临时库，不是正式库。

三个文件测试前后哈希一致：原测试为 `8320884dca69c2ab633f037609c1d92d1c9374b9e2e8c0354d0c89fafafc7197`，新增测试为 `b464cf9b53d94785783fa247e62e34582c3003387b0befcfcd9bd22d27383265`。Ruff 与 tracked diff 检查通过；未跟踪新增测试的 no-index 检查为退出 1、无诊断，代表与 NUL 内容不同，不是空白错误。Sol 的格式、编译和编码审计通过。中间独立回执保持原样；最终回执为 `.codex-tmp/system-read-activation-20260916/luna-env-final-proof.json`，SHA-256 为 `87bff7338b0c2f29e09e589800b2293cbf3e84982bbe9a2a7af58899ff9decf5`。

本轮第一次结果复核已提交原网页 6 Pro，明确限定环境修复及实际封存预检，不申请全局上线完成。另提交正常 API 启动入口的最小后续提案供复核，目前尚未修改该入口。其开关必须为 `system_read_publication_enabled`，不能误用已开启的仅损益 `financial_publication_enabled`。

网页第一次结果复核随后返回 ACCEPT，仅接受上述冻结环境修复和子进程封存预检。Pro 认可下一步只修 `dev-api.ps1` 的条件启动分支：复用 get_settings 的全系统开关，严格拒绝设置解析错误／空或畸形输出；完整快照模式绕开 shell 初始化和活动库 probe，由真实 lifespan 校验封存版本，强制 migration skip 不得泄漏到后续关闭模式。发布关闭时保留既有行为。它不批准正式启用，也不证明全局在线完成。本轮仍最多三次结果复核，当前已用一次。

父代理在第一次结果提交后发现新增测试还硬编码了本轮临时目录名，合法默认 pytest／CI 路径会被错误拒绝。Sol 随后只移除此测试目录依赖，保留 tmp_path、正式路径拒绝和 child guard，并在不含日期段的全新 `.codex-tmp/env-purity-portable-a1` 通过 15 项，4.98 秒；生产文件与原测试未变。新增测试最新 SHA-256 为 `74f0160fb0aee6530f38a6e106afb8b41597e0135cb465f29225310e8eb46a27`。这项最终 harness 修订不冒用第一次 ACCEPT 对旧 test hash 的覆盖，独立复验和下一次结果包需明确纳入。

14:19 另以真实 dev-env 和受监督只读子进程调用既有 `assert_postgres_schema_current`，退出 0。已部署与代码要求的 Alembic head 均为 `c2e94f6a8b10`，read_only=true，未调用初始化／迁移，也没有 DuckDB 打开。回执为 `.codex-tmp/system-read-activation-20260916/postgres-readiness.json`。它证明本次运行的 PostgreSQL 结构前提，不是未来服务始终可用或 API 切换已完成的保证。

## 历史补齐入口的已证实限制

Luna 对 `choice_stock_materialize.py`、`choice_stock_refresh.py` 和 `choice_stock_daily_refresh.py` 作定向只读核查，未调用供应商或运行更新。显式 as_of_date 确实进入请求及落地日期标签，但没有证明三类缺项的历史成分有效期或当时真实性；不能断言这些接口必然返回伪历史，也不能把请求带日期当作真实 PIT 来源证明。现有 Tushare gap-repair 仅针对 CSD 日频缺口，没有补这三类历史时点证据的能力证明。

现有 run-once 入口仍执行完整请求计划、历史与因子刷新，没有 required_items／field_key／missing-only 参数，也没有证明可仅填三项并保留四类已落地日行情。恢复这条业务路径需要权威的历史来源契约或可追溯原始快照，以及范围明确的恢复入口；当前停止历史写入，不批量重放 92 日，不手填审计或放松资格门槛。这是业务来源证据和恢复能力的具体障碍，不影响独立修复启动入口。

## 最终环境测试与当前前端兼容性

Luna 在独立全新且不含日期段的 `.codex-tmp/env-purity-luna-portable-a1` 对最终 portable harness 只运行一次，15 passed in 6.77s，退出 0。父进程 guard 3 条和真实 holder 子进程 1 条均为 owned_temp/allow；实际 print-env 空闲、占用及失败子进程均零连接尝试、零 HTTP，holder 已退出。生产脚本、原测试与 portable 新测试的前后哈希均未变。

随后在 frontend 目录仅执行 `npm run test -- src/test/SystemReadGenerationBoundary.test.tsx src/test/transport.test.ts`，两文件 40 项通过、退出 0，耗时 2.18 秒。当前六个关键源码文件均匹配所选构建的 source manifest，selection 未变；前后端都将 current-user 保持在 live 读取路径。测试使用 stub fetch，证明握手、请求版本、交互隔离和失败关闭契约，不证明真实后端身份与权限决策，也不是实际浏览器或正式启用验收。原始回执为 `.codex-tmp/system-read-activation-20260916/runtime-client-and-portability-proof.json`。

## 正常 API 启动入口修复

Sol 已在 `scripts/dev-api.ps1` 落地条件分支，生产文件 SHA-256 为 `e910d1ca57deb66a94aeab39bef06a61b1795cc1ba83934883687d540747f3d7`。它通过同一 Python、cwd、环境调用真实 get_settings，仅接受单行 0／1；解析失败、空或畸形输出在初始化前终止。完整读取开启时跳过 shell 的 up 与活动库 Assert，临时强制已有 migration skip，并在 finally 恢复强制值。关闭或仅 PnL publication 开启时保留原路径，显式 Skip 参数保留原语义。worker、共享 Assert、调度、settings 和 main 均未修改。

修前自有 fake-runtime 红测 9 failed，修后首次新文件 14 passed，另一个直接维护保护测试通过。真实 lifespan 与真实 storage dispatcher／publication resolver 已在自有封存 fixture 上运行，完整 pointer 接受，缺失、损坏、不兼容和 invalidated pointer 拒绝，活动库打开和网络尝试为零。父代理审查指出：首次 PS 测试用固定探针输出，不能单独证明真实设置解析；lifespan 首次关闭预热且没有调用事件，不能声称实际预热通过或已由事件证明失败先于预热。后续仅补这两项测试证据，不改冻结生产脚本；中间测试哈希与回执单独保留。

用户随后明确表示“没事历史的留着吧”。本轮不再要求补齐历史 PIT；保留已有历史和缺口，继续按真实资格显示资料不足，不把这一选择解释为允许删除资料、手写回执或降低门槛。

## 实际完整读取启动检查发现的剩余直连

父代理在 14:40 至 14:41 通过全新受监督子进程运行正常 `backend.app.main:app`，只在临时本地端口 7889 启用完整封存读取，保留实际首页、收入及市场预热。未改正式配置、前端 selection 或 pointer，未运行业务 writer。子进程总时限 240 秒，在应用导入前限制 native DuckDB 只读打开现有 immutable generation，拒绝活动库及 provider Requests 调用；此观察器不冒充所有 SQL ATTACH 或网络库的完整审计。

正常 lifespan 完成后，既有 `verify_system_online_reads.py` 分别以 5、10 个并发客户端运行两轮，覆盖首页、余额、债券、风险、损益和更新状态。两次命令均退出 0，共 180 次 GET，零 HTTP／envelope／版本／业务核对错误，各域版本内业务指纹保持一致。未制造或执行更新，不能把 phase 标签当作 writer overlap；同源核对不是独立会计审计。

尽管请求通过，整次运行检查退出 1：真实后台市场预热仍尝试直接只读打开活动 DuckDB 6 次，被观察器拒绝。另有 274 次允许的 immutable native 只读打开，provider Requests 尝试为零；这些是本观察器的 native 调用记录。原始证据为 `actual-sealed-runtime-proof.json`、`actual-runtime-5-clients.json` 和 `actual-runtime-10-clients.json`，均位于本轮 `.codex-tmp/system-read-activation-20260916/`。自有 API 线程已停止，子进程已结束；活动库 stat、完整 pointer、前端 selection 和冻结生产文件哈希前后未变。

错误栈明确指向 `system_sources.py` 的 alias identity direct connect 和 `equity_shadow_portfolio.py` 的影子组合 direct connect。定向源码核查另见同文件 full macro frame 使用同样路径；宏观 cache key 取活动路径及其 stat，因此也需使读取与缓存身份都遵循现有有效快照选择。不能通过关预热、吞异常或只看 180 次 GET 来宣布通过。

GitNexus 对 `resolve_system_duckdb_path` 的影响为 HIGH、30 个 upstream，直接 caller 包括本文件两处、WindPy 两处和 crowding 读取；对 alias identity loader 为 HIGH、17 个 upstream，影子组合为 LOW，运行栈补足了图谱漏掉的实际 API caller。已向用户说明宏观分析、策略摘要和后台取数影响，并请求批准仅修读取选择及版本缓存边界；该共享入口尚未修改。

本次 5 并发 P95（毫秒）为：首页 468.502、余额 428.446、债券 3134.321、风险 1252.589、损益 1519.331、更新状态 3788.908；10 并发为 721.747、2737.934、5788.146、5834.029、717.762、5159.061。多项未达一秒目标，保留全部端点和失败门槛，不删慢项，也不外推本次两轮小样本为完整性能验收。

## 启动补强最终独立证明及第二次结果提交

Sol 仅加强新增测试：将真实 settings.py 原样复制到测试自有 runtime，由其真实 _REPO_ROOT 定位自有 config/.env 和 .env；PowerShell 传入的 -c 表达式原样转交、严格断言并执行，区分完整发布开启与仅 PnL 开启。真实 lifespan、storage dispatcher、两迁移入口和 publication resolver 未被替换，只将更深层迁移 subprocess／DuckDB registry 设为调用即失败，并记录 warmup 调用顺序。完整 pointer 的 home warmup 带对应 generation，四种失败均在 warmup 前停止。warmup spy 不代表实际缓存计算通过；上一节真实缓存计算已经提供独立失败证据。

最终新增测试 SHA-256 为 `61a3b7b1ce827a5f36bfe53d3ae4cb33aa68bc10c246731056d528cf982b79e1`，生产启动脚本未变。Sol 最终增量 7 passed in 28.75s，随后 Luna 只对三个变更节点运行一次独立增量：

```powershell
.venv/Scripts/python.exe -m pytest -p _pytest_duckdb_guard -q tests/test_dev_api_immutable_startup.py::test_dev_api_executes_exact_settings_probe_against_owned_env_files tests/test_dev_api_immutable_startup.py::test_actual_lifespan_accepts_complete_publication_without_active_storage_access tests/test_dev_api_immutable_startup.py::test_actual_lifespan_rejects_unusable_publication_without_active_fallback --basetemp=.codex-tmp/startup-luna-final-a1
```

结果 7 passed in 28.11s、退出 0，前后冻结哈希一致；设置解析两子项零开库／HTTP，真实 lifespan 有效场景只有两次临时 generation/PnL 只读打开，活动库为零；四个坏 pointer 的 warmup 为零，底层迁移副作用哨兵为零。精简回执 `startup-final-incremental-proof.json` 的 SHA-256 为 `59a20822247d6e0d51d0318158a31ad66d71369c640e6bdd7c33ebe48a700c4c`。旧 14 项回执仍保留原哈希，未冒充最终文件的全量复验。

第二次结果复核已提交原网页 Pro，包含冻结启动修复、最终独立测试，以及明确标为失败的真实预热／五域检查。另请 Pro 评估仅在宏观共用 path resolver 与影子组合读取入口复用现有 resolve_effective_read_path 的方案，保留 SQL、计算、异常分类及 close 语义，不新建框架。此处记录提交事实，尚不代表收到第二次 ACCEPT 或用户已批准 HIGH 后续修改。

网页第二轮随后返回 ACCEPT，仅接受冻结启动／环境切片；明确真实应用检查仍失败，性能和正式激活仍未通过。Pro 认可上述宏观两文件最小方案，但以用户明确批准 HIGH 范围为前提，不把网页意见作为授权。本轮已用两次结果复核，保留最后一次给获批宏观修复及真实复验，不另开循环或重置预算。

下一切片的 FIRST_FILES 为 `system_sources.py`、`equity_shadow_portfolio.py`、只读参考 `duckdb_read_context.py`、拟新增 `tests/test_macro_immutable_read_selection.py`。首改应在共同路径边界调用现有有效路径解析，早于 exists／stat／cache／connect，且位于会吞掉普通数据错误的处理块之外。以唯一 immutable 物理路径及其 stat 作为缓存身份已足够，无需另造代次缓存层。私有 identity loader 仅在证据证明共同 resolver 之外仍有调用绕过时增加本地解析，不扩展无关模块。

首个隔离证明须由真实子进程持有临时 active RW，实际 alias、full macro frame 和 shadow reader 读取另一个封存 fixture；已填充缓存后切换两份快照，保持 active 路径及 stat 不变，确认值和缓存身份随选择改变。缺失必需 selection 或快照失效时须先失败，不能返回已有缓存／空可用结果或活动数据；无 selection 与显式 active_read_scope 的原读取行为及退出后的上下文恢复应保留，异常也必须关闭连接。随后仅运行直接 pushdown／shadow 回归、Luna 独立冻结复验和一次新证据前缀的真实预热／五域检查。保留本次失败原始回执，不覆盖旧日志。

14:54 结束前只读状态核对：正式 API 和前端均 200，完整读取发现 enabled=false，临时 7889 无 listener；活动库大小及 mtime、pointer、前端 selection、冻结启动／环境文件哈希未变。待改宏观文件基线分别为 `c7d2efdea6b4ae2d58745b05fbdfe35fc93e6b14a0f48095dbfd32732e1631d6` 和 `01647c9dc264e3e868a748a907506d30744519e54bc7b3b457713a62eed4bd82`，尚无本轮修改。当前停止在 HIGH 共享读取范围待用户确认，不执行正式切换或业务更新；历史不补的用户选择保持有效。所有未提交改动和证据保留，无提交／推送／清理。

## 用户批准后的宏观读取修复（2026-09-16 下午接续）

用户随后明确同意拆分子代理实施并由父代理最终 review，当前 HIGH 两文件范围已获批准，不再重复索要同一授权。Sol 负责两个宏观读取入口及一个新隔离测试文件，Luna max 负责冻结后的独立验证，父代理保留最终源码审查和实际预热／五域复验责任，同时不超过三个运行中的子代理。历史资料继续保留原状，不执行财务、股票或 bootstrap 重跑，不改正式开关和前端选择。

首个 core-first 测试已实际复现 resolver 在快照 scope 中仍返回 active：修前 1 failed，修后相同测试 1 passed。随后补充真实跨进程持库、切换快照的缓存身份、失效选择拒绝回退和异常关闭等边界；首绿本身不作为这一切片的最终验收。旧实际运行回执全部保留，下一次复验使用 `macro-fixed-runtime` 新前缀，保留同一正常应用、真实预热、端点、并发数和拒绝活动库打开的检查，仅补充被拒绝打开的无数据栈帧与明确失败文字。

生产两文件已冻结。`system_sources.py` SHA-256 为 `2b22a7b710eca83c60a4349ab69f21e68fa5c674d6b6b9ac179d1f60665e19cc`，`equity_shadow_portfolio.py` 为 `b102a9d1269474e5af7ef761be3a31f12bd8b37677021d6030098d7764a0f308`。两者只引入现有有效路径解析；SQL、计算、缓存结构、数据错误分类及连接关闭语义未改。最终新测试 SHA-256 为 `e1a684256385f99611c6f0eb8da39d0b99f6d0f3f21170c27ca9e10507fe7316`。Sol 最终新文件 8 项、既有 pushdown 22 项、shadow 7 项及 silent-degradation 定向 3 项均通过。三文件 Ruff lint、测试格式、内存编译、diff 和编码审计通过；两个生产文件的整文件格式检查仍有既存格式债，未作无关机械格式化。独立 Sol 只读代码及测试 review 未发现新增问题，给出补丁级 APPROVE；Luna 独立执行另记。

### 修后真实运行仍未通过，不扩大本轮实现

15:22:39 至 15:23:34，父代理通过实际 `dev-env.ps1` 启动自有 7889 正常应用，执行一次新前缀复验。脚本 SHA-256 为 `0e3fb122a5e16ca9621c2f4508fff9dbab11df8e096d418412b722e0965f6d29`，正常 home／income／market 预热均为 true。5／10 并发、各两轮，180 GET 的状态、envelope、版本及 240 项同源核对均通过，各域同代次业务指纹只有一个，但整体验证仍退出 1。

原两个已修入口不再出现在被拒绝打开的栈中。继续执行后暴露九次下游活动库只读尝试，全部被 observer 拒绝；249 次封存只读打开获准，Requests provider 尝试为零。新的具体原因分为两类：`cffex_member_rank_repo.table_stats` 的 82／86 行、`dual_frequency_equity_repo.load_dual_frequency_equity_history` 的 61／67 行仍直接使用活动路径，共三次；另外六次来自三个股票／宏观 context loader。后者已经调用 `resolve_effective_read_path`，不能再把它们误诊为缺少 helper。直接调用方 `macro_toolkit_read_service.build_macro_toolkit_full_analysis_blocks` 的 386–398 行把三个任务直接提交给 ThreadPoolExecutor，没有传递调用线程的 ContextVar 读取选择及 required-online 状态。这与实际线程栈吻合，是下一步应处理的上下文边界。本轮只读核对了这些精确栈及入口，没有修改新增范围。

新回执 `macro-fixed-runtime-proof.json` SHA-256 为 `1f0fdf61837696e78696fa77e5aceda5d7391c5a877b537b2b5c216a02b1cc9f`；5 并发回执 SHA-256 为 `34fd58c9f9e946bcb173aacfd83108ed10220bb730ca0f92bd8c1fd81aa68b40`，10 并发为 `3c9172efbd041d53fac96cde527a046d0188af44b045cd38c2153d2d1d8de1a4`。新旧失败日志互不覆盖。自有 server thread 已停止、进程退出，活动库 stat、正式 pointer、前端 selection、正常应用／启动文件及本轮两个生产文件的前后身份完全相同。观察器仅认证其记录的 native connect／Requests 范围，不外推为所有 SQL ATTACH 或网络库审计；没有真实 writer 重叠。

| 域 | 5 并发 P95（毫秒） | 10 并发 P95（毫秒） |
| --- | ---: | ---: |
| 首页 | 588.500 | 665.753 |
| 余额 | 490.707 | 701.885 |
| 债券 | 3175.136 | 6408.379 |
| 风险 | 2011.187 | 4751.150 |
| 损益 | 1740.474 | 1192.760 |
| 更新状态 | 3861.543 | 5700.847 |

上述仍是两轮小样本，且本机同时存在开发工作负载，不能据此断言较上一轮变快或变慢，更不能算性能通过。原全局零活动库读取门槛已连续两次失败，按 pro-codex-loop 的停止条件不再扩改或重跑；完成当前冻结补丁独立验证与第三轮结果复核后收口。正式全局开关、必要在线业务更新、五域性能及独立业务对账均仍未验收。下一步应按已证实调用栈限定为两个 repository 的有效路径选择和一个线程池提交边界，不继续盲扫或在已接 helper 的三个 loader 重复加包装。

Sol 已执行的最终定向命令如下，所有 basetemp 在执行前不存在，没有重跑旧环境／启动／财务更新套件：

```powershell
.venv/Scripts/python.exe -m pytest -p _pytest_duckdb_guard -q tests/test_macro_immutable_read_selection.py --basetemp=.codex-tmp/macro-immutable-freeze-a1
.venv/Scripts/python.exe -m pytest -p _pytest_duckdb_guard -q tests/test_macro_system_sources_pushdown.py --basetemp=.codex-tmp/macro-immutable-pushdown-a1
.venv/Scripts/python.exe -m pytest -p _pytest_duckdb_guard -q tests/test_macro_toolkit_shadow_portfolio_report.py --basetemp=.codex-tmp/macro-immutable-shadow-a1
.venv/Scripts/python.exe -m pytest -p _pytest_duckdb_guard -q 'tests/test_macro_silent_degradation_visibility.py::test_missing_system_tables_warn_and_return_empty_frame' 'tests/test_macro_silent_degradation_visibility.py::test_missing_system_tables_warn_only_once_per_table' 'tests/test_macro_silent_degradation_visibility.py::test_missing_duckdb_file_warns_once_across_alias_lookups' --basetemp=.codex-tmp/macro-immutable-silent-a1
```

实际应用复验命令为 `. .\scripts\dev-env.ps1` 后执行 `& .\.venv\Scripts\python.exe .codex-tmp/system-read-activation-20260916/exercise_existing_sealed_runtime.py`，完整子命令与新证据文件均在 `macro-fixed-runtime-proof.json`，其退出 1 与各 GET verifier 的退出 0 必须分别保留。

### 冻结补丁独立验收与最终复核提交

Luna max 只运行一次冻结后的新测试文件：`.venv/Scripts/python.exe -m pytest -p _pytest_duckdb_guard -q tests/test_macro_immutable_read_selection.py --basetemp=.codex-tmp/macro-luna-independent-a1`，退出 0，8 passed in 14.21s。三份冻结文件前后哈希一致；真实 holder 的 ready／closed 各一次，reader 子进程四次只读开库均为自有 snapshot，活动库为零、HTTP 为零；父 guard 的 35 条授权事件和 holder／reader 共用子回执的五条事件均为自有临时路径。授权事件不是额外的原生连接计数。独立回执 `macro-independent-proof.json` SHA-256 为 `b4f5cba6bcc7dabaaa4af892c92c38d1a42e130328f280850f60797d01b39c2e`，父代理已重新读取并核对。

独立 Sol 代码与测试审查结论为 APPROVE，Luna 架构结论为补丁 CLEAR、整体 BLOCK。父代理同意保留两个最小修复及其测试，同时拒绝全局上线。精确剩余阻塞是 `macro_toolkit_read_service.py` 的线程上下文传递、`cffex_member_rank_repo.py` 和 `dual_frequency_equity_repo.py` 的直接读取路径，而非本次补丁新引入的计算或缓存缺陷。

第三轮材料已发往原网页可见的 6 Pro，会话与三轮预算均沿用，不另起周期；仅传递脱敏技术差异、测试命令及失败摘要，没有业务行、金额、凭据或原始运行日志。当前仅记录已提交，最终网页意见随后补记。15:30 前后只读收尾确认：正式 API／前端均 200，完整读取开关 false，自有 7889 已关闭，活动库 stat 和回执记录的所有正式身份仍相同；无提交、推送、服务重启、配置切换或成功业务重跑。

第三轮网页 Pro 随后明确返回 ACCEPT，只接受冻结的两个读取入口及隔离证明，未发现该补丁的可行动缺陷；同时明确 whole-runtime FAILED、全局上线 BLOCKED。网页核对的是提交的技术证据，并未访问或测试本地代码。原会话为 `https://chatgpt.com/c/6aa791c9-c0b0-83e9-88eb-2ea4002aa3ee`，本次回复显示思考 1m 59s。该意见与父代理最终判断一致：保留已验证补丁，不把新增下游失败当作此补丁引入的回归，也不把 180 GET／240 同源核对盖过九次活动库尝试。

当前三轮结果复核全部用完，此接续周期关闭，不自动重置或发起新的实施。下一次接续直接从上述三个有证据的边界做必要影响分析和最小修复；它们通过后仍需正常预热零活动库读取、真实必要更新期间服务在线、五域稳定与独立业务一致性证据。历史缺口、性能不足、未进行正式切换等事实均保留。全部已有未提交修改和新旧证据继续留在工作区。
