# 经营日报首页维护入口

本文件维护首页模块、数据边界和相关测试入口。通用开发流程按根目录与前端 `AGENTS.md`，启动和局部命令统一在 [前端开发入口](../../../../README.md)。日期记录保留在文末，供具体问题追溯。

本目录服务 `/` 与 `/dashboard`。首页首先展示主快照对应的经营判断、核心指标和数据可信状态，再加载补充分析。每次改动先确定一个具体展示或交互目标，沿下表找到所属文件；金融指标定义仍以既有页面契约和后端结果为准。

## 从哪里改

| 改动内容 | 首先检查 |
| --- | --- |
| 主快照、请求日期与实际日期 | `../pages/useDashboardSnapshotBoundary.ts` |
| 首屏数值、单位、状态映射 | `dashboardHomeSnapshotAdapter.ts`、`useDashboardHomeFirstScreenViewModel.ts` |
| 补充风险提示与更新时间映射 | `dashboardHomeFirstScreenView.ts` 中的 `mapToHomeFirstScreenHydration` |
| 补充请求与辅助来源状态 | `useDashboardHomeSupplementalHydration.ts` |
| 补充内容挂载与首屏回传 | `DeferredTerminalHomeContent.tsx` |
| 当前报告日校验、首屏合并 | `DashboardHomePage.tsx` |
| 首屏布局 | `DashboardHomeOptionTwoOverview.tsx` 及对应样式模块 |
| 页面外框与顶栏布局 | `dashboardHomeOptionTwo.module.css` |
| 顶栏日期、搜索与状态控件 | `sections/DashboardHomeToolbar.tsx`、`dashboardHomeShell.module.css` |
| 下半屏内容 | `DeferredTerminalHomeBody.tsx`、`DashboardHomeOptionTwoLayout.tsx` |

## 数据更新边界

`useDashboardHomeFirstScreenViewModel` 负责主快照首屏结果。补充 hook 返回 `firstScreenHydration`、`supplementalState` 和 `updatedAt`，其中只有 `firstScreenHydration` 会回传首页，并且只包含 `reportDate` 与 `keyRiskStrip`。四张核心指标、决策区与首屏状态栏不属于补充更新范围。

补充 hook 通过窄入口 `mapToHomeFirstScreenHydration` 取得风险提示和更新时间，不组装 overview、损益归因或完整首屏模型。完整首屏 mapper 也复用这一入口，使补充数据的同日筛选、缺值显示和快照时间来源保持一致。新增补充字段时先核对实际消费者，再决定是否扩展该入口。

`supplementalState` 和 `updatedAt` 直接交给下半屏，继续展示辅助来源状态与原有更新时间。它们变化时应更新下半屏，不应触发首屏回传。风险提示的文案、数值或其他字段变化时需要回传，因此去重比较使用完整 `keyRiskStrip`。

`DashboardHomePage` 只接收与当前主快照报告日相同的补充结果，切换报告日时清理旧补充状态。保留现有请求门控和查询键；修改加载时序时，必须验证旧日期的迟到响应不会进入当前页面。真实模式的空值、失败和过期状态继续由原有模型表达。

主快照请求失败时，只允许保留相同请求日期、客户端和完整性选项下的旧版本。切换到不可用日期后，首屏数值显示缺口并说明原因，不从其他日期的缓存补回资产规模；同一日期刷新失败仍保留该日读数并标明刷新失败。

手动选择报告日时，请求该日的部分可用快照：已有资产按当天数据展示，缺失的损益组件留空并披露缺口。未选日期时仍由后端选择最新完整报告日。缺失数据域不填写其他日期作为实际生效日；全部核心数据域缺失时仍返回不可用。

## 样式归属

当前首页的外框、顶栏排布和响应式尺寸由 `dashboardHomeOptionTwo.module.css` 维护。`dashboardHomeShell.module.css` 继续提供控件基础样式，包括日期输入点击层、搜索焦点反馈和移动端触控尺寸；其中旧顶栏外框规则只匹配同时带旧根类和首页标识的页面。修改当前布局时在对应基础块或断点内调整，不再通过页面额外导入 shell 样式控制覆盖顺序。

首页根布局与子组件所需的兼容变量集中在主样式开头的 `.page`，Nocturne 映射直接消费 `tokens.css` 的 `dashboard-home` scope。不要恢复文件尾部的历史根样式或重复声明整套主题映射。电脑端保持“今日需处理、产品分类摘要、组合变化”的顺序，组合变化中归因在左、四项指标在右。

`tests/playwright/dashboard-home-style-ownership.spec.mjs` 会在六种屏幕宽度下，把实际 shell 样式表分别放到最前和最后，比较布局、控件和搜索聚焦状态。这个检查使用 Vite 开发服务；与现有布局及滚动加载检查一起运行，可验证样式归属变化没有改变页面行为。

## 最小验证路径

日常启动和局部验证命令统一见 [前端开发入口](../../../../README.md#运行局部检查)。首页快照、报告日、首屏映射与补充加载需要组合验证时，可选择现有 `-HomeFeedback` 的 7 文件集合；下半屏、新闻或持仓抽屉只选择各自相关用例。完整页面验收使用原入口，不把局部反馈当作整页通过。

补充回传或日期行为变化，先从 `frontend/` 运行以下现有测试。测试分别覆盖回传边界与下半屏披露、完整页面日期和指标保护，以及真实模式的样例数据隔离。

```sh
npm run test -- src/test/DeferredTerminalHomeContent.test.tsx src/test/DashboardHomePage.test.tsx src/features/workbench/dashboard-home/useDashboardHomeMockFallbackGuard.test.tsx
```

`DashboardHomePage.test.tsx` 的请求先后断言使用 `runNextIdle` 逐波释放已注册的空闲任务；最终内容断言使用 `settleHomeIdleWork` 等待正文挂载和短定时任务完成。证明请求仍未发起时使用 `settleHomeTimersWithoutIdle`，处理已排队的定时任务与查询通知，但不打开空闲门控。不要复制生产毫秒数编写等待函数；性能预算断言仍使用原始墙钟。

首屏风险展示或补充回传映射变化时，选择 `dashboardHomeFirstScreenView.test.ts` 和 `useDashboardHomeFirstScreenViewModel.test.tsx`；新闻请求波次变化时，选择 `useDashboardHomeViewModel.test.tsx`。下半屏分布或状态映射的局部修复优先选择 `dashboardHomeBodyView.test.ts`、`DashboardHomeOptionTwoLayout.test.tsx`，不因属于首页就连带执行全部首屏、加载和契约检查。跨越上述边界时再补对应页面组合用例。

验证范围按 [前端规则](../../../../AGENTS.md#evidence-and-validation) 选择；涉及滚动加载时使用 `tests/playwright/dashboard-home-deferred-reveal.spec.mjs`，运行环境见 `playwright.config.mjs`。

样式归属变化时，在已启动的 mock Vite 服务上运行以下检查，并按 `playwright.config.mjs` 设置对应服务地址。

```sh
npx playwright test -c playwright.config.mjs tests/playwright/dashboard-home-style-ownership.spec.mjs tests/playwright/dashboard-home-layout.spec.mjs tests/playwright/dashboard-home-deferred-reveal.spec.mjs
```

2026-10-04 在显式 mock 临时 Vite 服务上，Linux / Node 22.23.3 的六项原有布局用例全部通过，命令正常退出 0（16.9 秒），测试与断言保持不变。最终 360×800、390×844 的首个核心 KPI 主值底部分别为 794.28125px、771.78125px；手机截图已复核，768 平板及 1280、1440、1920 桌面也通过原用例。临时服务已停止，实际日常入口的生效状态由统一集成另行核对。

改前 Windows 两个手机尺寸的首个 KPI 主值底部均为 1066.78125px。修正仅涉及 720px 以下的信息排布和间距；Linux 360 后续暴露了归因提示换行，多占 21px，将归因卡左右内边距从 8px 调为 4px 后恢复首屏可读。首次 Linux 桌面失败来自隔离目录漏复制宏观日历 JSON，已按源文件字节补齐，未修改产品区域或等待断言。

Windows 前轮六项用例虽逐项通过，但浏览器退出仍被会话内 `DictManager_DictSaveLocker` 命名锁阻塞，主动终止后的命令退出码为 1；新浏览器加载了搜狗输入法模块，持锁旧进程的归属尚未确认。这个 Windows 执行环境问题仍未解决，Linux 的通过结果不能替代 Windows CLI 或 CI 全绿声明。

视觉改动先读根目录 `DESIGN.md`，只追踪对应组件和样式；业务展示改动核对受影响指标；加载时序改动核对首次进入、慢请求、失败与切日。复用已有测试场景，新增用例应证明尚未覆盖的行为。一个任务由一个代理主责整合，生产代码与测试可以分工，但同一文件应只有一个写入者。

电脑端布局检查已覆盖 1280×900、1440×900、1920×900，断言当前区块顺序、指标字号与数值对齐、完整显示、顶栏控件不重叠、搜索聚焦，以及首屏与下半屏共用边界。仅验收电脑端时可选 `dashboard-home-layout.spec.mjs -g "aligns desktop"`；这不代表手机端检查通过。2026-09-28 本轮实际执行了浏览器逐项检查和 83 项定向 Vitest，未执行 Playwright CLI；首页主样式整理前后，首屏布局与主题变量使用实测值比较。随后将新闻与研究的 96 条内部规则归回 dashboardHomeOptionTwoDeferred.module.css，首页主样式只管理该区域的外框和标题；两份样式合计删除 143 条重复或被完全覆盖的声明，保留仍参与层叠的规则。本次追加的 64 项定向 Vitest、文件级 ESLint 和 CSS 语法检查通过；5896 源码预览中核对了 1280、1440、1920 电脑宽度和历史数据展开状态。浏览器比较覆盖实际加载内容，不代表所有主题与加载状态的视觉穷举。日常 5888 入口未发布，手机端未验收，亦不表示全站技术债清零。

## 历史交接记录

## 2026-09-30 响应字段契约收口

首页原有 13 个无细字段响应声明已收口：三个首页接口复用 `executive_dashboard.py` 中的完整 payload，七个债券接口使用 `home_bond_read_contracts.py` 保留原有 Q8 字符串格式，三个支持区接口使用 `home_support_read_contracts.py` 复用利率、日历类型并显式声明新闻事件字段。改动集中于这五个路由文件和三份模型文件，没有改金融计算或读取服务。

契约守卫现在要求 20 条首页接口有命名响应结构，并对新增契约核对实际消费字段。根结构为空、`result` 仍为自由字典、消费字段退化为无约束类型时，即使新旧摘要相同也会失败。交接工具还要求 `coverage_gaps` 明确为空，防止复用以前带 13 处缺口的通过回执。2026-09-30 本次交接的契约摘要为 `cc4b564cfe70eab9ded136514e7f06fb1c470a3427cdcefa0d7f8c42c218e317`，绑定当次 25 个契约源码文件，见 [handoff-typed-current-process.json](../../../../../.codex-tmp/home-delivery-20260929/acceptance-20260930/handoff-typed-current-process.json)。后续版本的当前契约身份由同一交接工具生成并核对。

本轮 309 个定向用例通过，其中首页组 95 项、债券组 86 项、支持区组 37 项，交接工具 60 项、契约守卫 31 项；新增支持区用例分两次执行，共 24 个独立用例。未选中的测试不计入通过。命令、选择器和结果保存在本次证据目录的 `typed-contract-validation.json`，全部受影响 Python 文件 Ruff 和仓库编码检查通过。前端消费路径独立复核没有发现阻断，债券新旧模型的 21 个字段集合一致。

激活前，真实 5888 首页的 13 条路径、15 次响应在本机经过新 DTO 校验与路由相同的序列化流程，字段增删、类型和数值变化均为零；响应只在本机内存和本地 Python 标准输入流转，技术回执为 `live-response-models.json`。旧运行 OpenAPI 的 13 条差异实测被拦截，保存在 `backend-contract-before-activation.json`。

沿现有 `dev-api.ps1 -SkipStartupStorageMigrations` 入口重载后端后，严格八层验收通过。收尾检测到运行进程再次被重载，随后对当时的 7888 进程重新从 5888 验证，20 条契约与当前源码一致、覆盖缺口为零；22 次请求均完成并返回 200，五个区块和研究页签均覆盖，持续加载与页面错误为零。最终回执为 `handoff-typed-current-process.json`。前端登记仍指向已有 2026-09-30 候选，合法空态和未接入披露保留，手机端仍未纳入。这些检查不替代业务金额对账；尚未提交 Git。

## 2026-09-30 固定整页验收入口

用户要求完整电脑端首页验收、正式发布或版本交接时，统一使用 `scripts/release_handoff_receipt.py --page dashboard-home`。该模式执行真实浏览器全页检查，并从同一个前端地址读取后端 OpenAPI，再把两项结果纳入交接回执。只运行原六层检查，或只看到健康接口返回 200，不能据此宣布首页整页验收通过。普通源码修复和本地运行更新不自动触发此流程；相关行为验证通过即可报告该修复生效，其它模块的质量问题继续披露，不能据此宣称整页通过。

浏览器检查逐段滚动首页内部容器，覆盖持仓、风险、市场、支撑信息和证据五个区块，并切换研究页签。它要求所有必需数据请求完成，拦截接口错误、传输失败、页面异常、漏加载模块和持续加载占位；余额分析有可用报告日时另要求待办请求。合法空态和“未接入”提示保留。HTML 与入口脚本哈希必须匹配同次 HTTP 检查和登记候选，旧回执、启动失败与检查超时均不能通过。

以下命令用于本次实际运行的 2026-09-30 候选；后续切换版本时应替换为该版本的源码清单、测试回执和构建关联，不能沿用旧版本输入。`--source-root` 指向受测候选源码，`--repo-root` 指向运行登记所在仓库。`--output` 必填，执行后会保留整页、契约和交接回执及检查进程的 stderr 日志。

```powershell
.\.venv\Scripts\python.exe scripts/release_handoff_receipt.py `
  --page dashboard-home `
  --repo-root F:/MOSS-V3 `
  --source-root F:/MOSS-V3/.codex-tmp/update-stability-20260930/candidate `
  --source-manifest F:/MOSS-V3/.codex-tmp/update-stability-20260930/candidate/source-manifest.json `
  --test-receipt F:/MOSS-V3/.codex-tmp/home-delivery-20260929/acceptance-20260930/home-test-current.json `
  --build-receipt F:/MOSS-V3/.codex-tmp/home-delivery-20260929/acceptance-20260930/build-binding-current.json `
  --selection F:/MOSS-V3/tmp-governance/runtime-clean/control/frontend.json `
  --base-url http://127.0.0.1:5888/ `
  --output F:/MOSS-V3/.codex-tmp/home-delivery-20260929/acceptance-20260930/handoff-typed-current-process.json
```

契约检查比较首页实际使用的 20 个 GET 接口成功响应结构，包括四效应的 `principal_evidence` 字段，并记录当前契约源码哈希及检查期间的稳定性。初次落地时其中 13 个接口仍使用无字段约束或通用字典响应，当时回执披露了这些覆盖缺口；本日后续收口结果见上节。该检查不证明运行后端全部实现与源码一致，也不替代业务金额对账。

本次保留已有 2026-09-30 运行包，仅重载前端服务使 `/openapi.json` 只读代理配置生效。最新代码在真实 5888 入口观察到五个区块、22 次请求，全部返回 200 且完成，持续加载和页面异常均为零，八层交接均通过；结果见本次证据目录的 `handoff-current.json`。手机端仍未纳入。

验收工具自身的回归检查已执行：根目录 `.\.venv\Scripts\python.exe -m pytest tests/test_release_handoff_receipt.py tests/test_verify_home_runtime_contract.py -q` 共 84 项通过；前端 `npm run test:home-runtime-acceptance` 的 12 个独立 Chromium 场景及 `npm run test -- src/test/StartupPerformanceGuards.test.ts` 的 30 项性能护栏通过。文件级 Ruff、ESLint、四个脚本的 JavaScript 语法检查、`tsconfig.node.json` 类型检查及仓库编码检查通过。未运行全站测试或重新构建应用。

## 2026-09-29 日常入口切换

后续全页检查复现了四效应接口 500 和研究报告代理 502。四效应的运行 OpenAPI 缺少 `principal_evidence`，而当前源码与现有测试已包含该字段；运行后端早于契约修复启动。执行 `.\.venv\Scripts\python.exe -m pytest tests/test_campisi_attribution_service.py tests/test_campisi_four_effects_detail_summary.py -q`，94 项通过后，沿原受控启动入口重启后端，保持跳过存储迁移，确认运行契约已包含该字段。本轮未另改业务代码或前端运行包。5888 真实首页两次全页滚动检查各触发 22 次请求，均返回 200，加载失败、持续加载占位和页面异常均为零；原有“未接入”数据源提示仍保留。研究报告连接重置在这两次复验中未再出现，不代表已证明代理故障永不复发。技术证据为候选目录的 `loading-current.json`、`loading-after-backend-reload.json` 与 `loading-reload-confirmation.json`。

用户随后授权切换，已通过既有运行控制器将 5888 登记并启动为 `home-delivery-20260929/source/frontend/dist`。`handoff-deployed.json` 的源码、测试、构建关联、候选完整性、运行登记与 HTTP 指纹六层均通过。真实浏览器在 1440×900 核对了 5888 首页：主快照与读取版本接口返回 200，报告日状态为 exact，四张核心指标卡已渲染，没有未捕获页面异常；未记录业务金额，也不将该检查提升为金额对账。证据为 [deployment-live-result.json](../../../../../.codex-tmp/home-delivery-20260929/deployment-live-result.json)。

旧运行包 `frontend-release-20260928-home-date/dist` 保留，原登记保存在候选目录的 `deployment-previous-selection.json`。当前候选目录已经承载日常运行构建，不得作为临时产物清理。以下“未部署”描述保留前一阶段交付时点含义；当时归档包未因部署而重写。

## 2026-09-29 电脑端交付验证

本批候选源码、构建和证据保存在 [home-delivery-20260929](../../../../../.codex-tmp/home-delivery-20260929/)，归档入口为该目录的 `home-delivery.zip`。范围为电脑端首页，手机端未纳入；未提交 Git，也未部署到日常 5888 入口。交付包显式包含根 `conftest.py`、`_pytest_duckdb_guard.py` 和测试所需源码，避免只复制已跟踪文件漏掉隔离守卫。它是当前工作树的独立候选，不等于一个已提交版本。

从候选源码按 `backend/uv.lock` 安装 Python 3.11 开发环境后，`uv sync --check --frozen --project backend --extra dev --python 3.11` 确认无需变更，首页快照、缓存、接口、服务与血缘的六个测试文件共 152 项通过。首次检查有 151 项通过、1 项失败，原因是血缘测试仍断言旧 `routeElement`；修正为当前 `systemReadRouteElement(<DashboardHomePage />, false)` 后，单项和锁定环境复验均通过。没有修改业务读取逻辑。`backend-home-locked.receipt.json`、对应日志和 XML 保留完整命令与结果。

首页快速检查的七个文件 116 项、补充九个文件 79 项通过，两批没有重复文件。前端 app/node 类型检查、首页相关 ESLint、候选源码范围的六段债务检查、real 构建与两个 bundle 守卫通过。前端复用本机依赖，已核对已安装锁记录中的版本与 `package-lock.json` 一致；本批未重新执行 `npm ci`，不能称为全新前端依赖安装验证。

Playwright 实际执行了 1280×900、1440×900、1920×900 布局与桌面延迟加载，共四项通过。密集文本裁切检查因 mock 持仓/政策行不足而跳过，未计为通过。另对 real 生产候选包注入合成响应，验证三个电脑宽度的首屏、同日刷新失败保留读数并提示过期、无数据日期清空旧值、迟到响应不覆盖新日期，浏览器无未捕获异常。截图与 `candidate-browser-results.json` 对应这些合成场景，不代表真实业务金额对账或密集正文裁切验收。

`frontend-source-manifest.json`、`build-binding.json`、`build-manifest.json` 和 `frontend-test-receipt.json` 将受测前端文件与 309 个构建文件关联。5992 候选入口的 HTML、入口脚本哈希匹配候选；5888 日常入口不匹配，运行登记也未切换，因此交接工具的总状态仍为 failed，不能将其改写为发布通过。查看 `handoff-candidate-final.log` 与 `handoff-daily.log` 时应分别读取源码、测试、构建、登记和 HTTP 层。测试服务在结项时停止，候选文件保留。
