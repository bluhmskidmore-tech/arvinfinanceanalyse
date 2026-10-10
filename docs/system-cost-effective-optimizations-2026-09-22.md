# 高性价比优化实施与验收记录

本轮按用户“拆分子代理做”的要求实施五个方向。前四项已完成本地实现、定向检查及相应浏览器验证；第五项与另一活跃任务协同完成逐条类型基线和严格 CI 门禁。当前真实类型门禁仍然失败：相对可信历史基线，有 667 条新增或身份变化的诊断未获豁免。本文不构成部署、真实数据更新或业务对账结论。

接手 HEAD 为 `a97f0f3a268500ded23ba4233d55e1e0c96b70a3`，工作区已有大量未提交修改。余额客户端接入共享 transport、产品损益三个读取模型、发布防重放与利差缺失判断等已有成果均予以保留。本轮继续修复连接处，未修改正式金融公式、数据库结构或权限框架。

| 方向 | 本地结果 | 验证结果 |
| --- | --- | --- |
| 刷新、发布、年度复用的 PR 测试选择 | 已实现 | 映射 102 项；业务回归 130 项通过 |
| 余额变动读取边界 | 已实现 | 四文件 86 项通过 |
| 数据中心失败阶段处理 | 已实现 | 两文件 23 项通过 |
| 产品损益核心响应契约 | 已实现 | 四文件 117 项通过 |
| 逐条类型诊断与历史基线 | 已实现；当前源码被阻断 | 四文件自测 84 项通过；真实 gate 阻断 667 条未豁免诊断 |
| 两页面浏览器交互 | 已验证 | 10 项通过，服务响应全部为合成数据 |
| 前端静态检查 | 已验证 | typecheck 通过；lint 0 错误、1 警告 |
| 全仓债务检查 | 已验证 | 六段均通过，未提高基线 |

测试映射原来没有选中数据更新、系统发布和产品年度复用的关键回归。现按其实际实现依赖和测试自身精确选取，产品接口新增契约测试也接入同一机制。新增选择反例先出现 27 项失败，补充产品接口映射时另有 6 项失败，修复后完整映射测试通过。临时 Git 仓库中的故意失败 pytest 还验证了真实子进程错误能够使 gate 返回失败；没有只靠配置字符串判断门禁生效。证据在 `.codex-tmp/implement-gate-evidence.json`。

余额变动已有共享请求接入，但取消信号在组合入口丢失，明细失败又被首屏空态掩盖。本轮补齐 GET 信号传递和只读重试，保持 POST 刷新语义。独立复核再用 `result:null`、缺字段和错误字段类型证明外壳校验不足，现由领域客户端复用 `keyFields` 校验页面必需字段，并检查日期列表元素。合法空数组和可选字段省略保持兼容。重读失败保留缓存时，页面明确说明显示上次成功结果，状态区区分请求中、读取失败与已完成。新增提示提取为局部展示组件，页面行数保持原上限以内。

数据中心以前对所有失败提供日期重提快捷入口。现在依据既有 `failure_receipt`，识别财务发布、系统发布，以及主体已完成后的来源摘要失败，显示“财务计算已完成，发布待处理”，提供回执查看及处理说明。普通失败保留原操作，写权限按工作流继续判断。本页没有新增“只恢复发布”能力，也没有把显示待处理状态当作发布成功。前后文件指纹和测试结果在 `.codex-tmp/data-update-ui-result.json`。

产品损益保留已有日期、明细与历史响应模型，补齐归因、归因历史、刷新提交和刷新状态的命名响应模型。刷新回执复用既有 `CacheBuildRunRecord`，保留扩展字段、未设置字段的省略行为及显式 null。HTTP 和 OpenAPI 测试覆盖精度、日期、质量元数据、权限与错误状态，并证明删除关键字段会被契约检查发现；没有刷新 OpenAPI 基线来吸收破坏性变化。独立内存复核额外检查了真实服务编排生成的回执与 Decimal 边界。作者首轮 pytest 仅由 conftest 加载守卫，遗漏显式早期参数；父代理已用独立 Python 3.11 环境及显式守卫重跑全部 117 项并通过，未把两次执行累加成覆盖数量。

类型门禁由另一任务持有共享实现，本任务停止重叠编辑并做独立复核。新增 `tests/test_mypy_import_boundary.py` 曾证明根目录 `scripts/` 的合法诊断被错误拒绝，修复后 11 项通过。正式基线来自提交 `643496ad93ebc8d8fafd33389351ab4729b484f7` 的完整 backend 与根 scripts 副本，806 个 Python 文件逐字节核对，并使用历史源码专用 Python 3.11、mypy 1.20.1 环境重放，逐文件匹配旧基线 1,591 条、229 文件。配置、锁文件、源码和输出指纹记录在基线中；诊断身份结合语句和所属控制分支，防止删除一处旧错误抵消另一处新增错误。CI 不再忽略 gate 失败。

迁移过程曾遇到 backend-only 副本不完整及 editable 指向当前源码两种风险，早期回执已作废。两次相差的六条诊断实际来自历史 backfill 模块的导入静默设置，未证明读取当前文件。正式门禁的显式目标仍为 `backend/app`；mypy 默认可能静默处理环境包路径中非目标导入模块，因此不能声称覆盖全部脚本。六条诊断从未纳入豁免。可信重放证据为 `.codex-tmp/debt-remediation-20260922-task01a0c999/historical-complete-mypy-replay.json`，正式基线 SHA256 为 `8a54a3d538774e3f095814f7bb5ef07593fff8995b801bf5bb2d35a3f2068433`。本任务独立复核确认 1,591 条诊断身份唯一，历史候选与正式文件逐字节一致，971 份历史文件的指纹、回执、stdout 与 Git tree 证据相符。

当前工作区真实 gate 返回 exit 1，读取 2,043 条诊断，对照 1,591 条历史诊断，识别 667 条新增或变化诊断、215 条消失或变化的历史诊断。两组“变化”不能直接当作纯新增和已修复数量。运行没有改写基线，尚未豁免的问题继续阻断 CI；本轮产品损益路由和 schema 不在未豁免输出中。原始日志为同目录 `root-mypy-current-gate.log`，工具、基线、配置和锁文件指纹见 `final-gate-fingerprints.json`。最终 checker、旧债务、导入边界与 CI 内容四个测试文件合计 84 项通过，显式提前加载 DuckDB 守卫，命令与日志为 `root-mypy-ci-tests-command.json` 和 `root-mypy-ci-tests-final.log`；其中包含前述 11 项，不重复累加。CI 自测入口也已加入提前守卫参数，最终 workflow SHA256 为 `5aa6b88aecb668bbb59b08a18cdeae2ba6d102252562443457bb19f9901ce76c`。

本轮主要实现文件如下，列表只标明涉及路径，不把文件中全部既有修改归于本任务。

- `scripts/check_caliber_gate.py`、`tests/test_caliber_gate_mapping.py`
- `frontend/src/api/balanceMovementClient.ts`、`frontend/src/api/homeSupplementalClient.ts`
- `frontend/src/features/balance-movement-analysis/pages/BalanceMovementAnalysisPage.tsx`、`components/BalanceMovementReadStatus.tsx`
- `frontend/src/features/platform-config/DataUpdateCenter.tsx`、`dataUpdateCenterModel.ts`、`frontend/src/api/dataUpdatesClient.ts`
- `backend/app/api/routes/product_category_pnl.py`、`backend/app/schemas/product_category_pnl.py`
- `tests/test_product_category_api_contract.py`、`tests/test_product_category_pnl_flow.py`、`tests/test_mypy_import_boundary.py`
- `frontend/src/api/balanceMovementClient.test.ts`、`frontend/src/test/BalanceMovementRequestBoundary.test.tsx`、`BalanceMovementAnalysisPage.test.tsx`、`HomeStartupClient.test.ts`
- `frontend/src/features/platform-config/DataUpdateCenter.test.tsx`、`frontend/tests/playwright/runtime-reliability-closure.spec.mjs`
- `docs/data_update_center.md`

协同完成的类型门禁文件为 `scripts/check_mypy_baseline.py`、`scripts/mypy_baseline.json`、`tests/test_check_mypy_baseline.py` 和 `.github/workflows/ci.yml`。前四项验收后的源码指纹保存于 `.codex-tmp/roi-implementation-20260922/source-fingerprints.json`；父代理还逐项核对作者回执，相关实现文件一致，数据中心文档保留另一任务并行补充的恢复说明。

父代理关键验收命令如下。前端命令在 `frontend/` 执行，其余在仓库根执行。

```powershell
.\.tmp\mypy-current-311\Scripts\python.exe -m pytest -p _pytest_duckdb_guard tests/test_product_category_api_contract.py tests/test_product_category_metric_schema.py tests/test_product_category_pnl_flow.py tests/test_product_category_pnl_attribution.py -q
npm run typecheck
npm run lint
npm run debt:audit
```

真实类型门禁使用独立 Python 3.11 环境，命令为：

```powershell
.\.codex-tmp\debt-remediation-20260922-task01a0c999\qa-venv\Scripts\python.exe scripts/check_mypy_baseline.py
```

该命令的验收结果是按设计阻断未豁免诊断，并非类型检查全绿。仓库仍需后续按模块消化这些问题；本轮未扩大为全库类型清理。

最终独立复核还核对产品损益路由与 schema 的当前源码哈希和 mypy 缓存，两文件未被静默、诊断为空；在最终 checker 下重跑导入边界 11 项均通过。667 条只表示相对历史基线的新增或身份变化，不能等同于本轮新引入，也不能把它们统称为已经存在的问题。

浏览器使用现有受控源码启动入口，临时地址为 `http://127.0.0.1:5893`，API 代理指向关闭端口。Playwright 拦截所有 `/api`、`/ui` 和 `/health` 请求，拒绝写请求并记录其次数，不访问真实业务服务。10 项验证覆盖发布失败的可见回执和权限，以及日期、明细的四类坏响应与读取重试。最初两个 null 响应场景在浏览器失败，修复后通过。最终命令为：

```powershell
$env:MOSS_PLAYWRIGHT_STATE_BASE_URL='http://127.0.0.1:5893'
$env:MOSS_PLAYWRIGHT_OUTPUT_DIR='../.codex-tmp/roi-browser-20260922-final'
node node_modules/@playwright/test/cli.js test -c playwright.config.mjs tests/playwright/runtime-reliability-closure.spec.mjs --workers=1
```

临时服务已停止，端口探针返回 `ECONNREFUSED`。日常前端构建选择、后端服务和业务数据未由本任务变更。Lint 的一条警告位于既有 `PnlByBusinessPage.tsx:92`；Python 3.11 的契约复验另有一条 Starlette 测试客户端弃用警告。两者均未通过扩大忽略解决。

本会话未暴露指标、血缘和目录 MCP，采用当前页面契约、DTO、服务调用与合成测试作为替代。GitNexus 已刷新，但存在 scope extraction 警告且动态 JSX/HTTP 调用覆盖不全，影响分析结合当前源码调用处判断。未执行远端 CI、提交或部署，不能据本地检查宣称日常入口已经生效。
