# 产品损益刷新流程收敛记录

2026-09-11，本批完成产品损益页面刷新职责分离，修复部分历史查询漏刷、同一归因查询重复刷新，以及刷新后诊断和回测面板自动收起的问题。范围为 `/product-category-pnl` 的刷新按钮与新增、编辑、撤销、恢复调整后的数据同步。金融公式、接口合同、数据库结构和后台任务执行方式保持原样。

原页面在 `runRefreshWorkflow` 内逐项调用查询的 `refetch`，需要同步维护查询定义和刷新清单。负债累计矩阵、情景下的正式回测历史、管理监测补充历史已经有查询入口，但没有完整进入该清单。月环比归因则可能通过两个观察者重复刷新。原生 `details` 在正式基线重新加载期间被卸载，重新挂载时未绑定已有的展开状态，导致面板收起。

现在由 `useProductCategoryRefresh` 管理任务提交、轮询、忙碌状态、错误和回执，继续使用既有 `runPollingTask`，通过 TanStack Query 的 mutation 状态统一刷新按钮与调整后的刷新。任务成功后，按 `product-category-pnl` 命名空间和当前数据模式取消旧读取、将缓存标为过期，并只重新请求已启用的查询。关闭或未挂载的查询保留过期标记，等待用户再次使用。同步范围按任务完成时的查询观察者确定，因此切换日期或情景不会依赖旧事件闭包中的查询清单。

任务失败不触发这次查询失效，也不会自动重提任务。任务成功但某个读取失败时，仍由已有页面错误和重试区域展示读取失败。诊断和回测 `details` 的 `open` 属性绑定已有状态，刷新后继续保留用户查看位置。

影响评估为中等。直接入口为主页面刷新和三组调整处理函数，涵盖创建/编辑、撤销、恢复。当前页所有相关日期和情景缓存都会失效，但只加载已启用的查询。其他数据模式、`operations-entry`、`product-category-audit`、月度经营分析等缓存不在本次同步范围；跨页面依赖仍需后续单独梳理。GitNexus 返回零上游调用，但当前路由与调整入口存在直接引用，因此影响判断采用当前代码核对结果，未采信其低风险评级。

本批变更文件如下。主页面原有的其他未提交修改已保留，改前副本记录在本地 `.codex-tmp/product-category-refresh-lifecycle-20260911/`。

- `frontend/src/features/product-category-pnl/pages/ProductCategoryPnlPage.tsx`
- `frontend/src/features/product-category-pnl/pages/useProductCategoryRefresh.ts`
- `frontend/src/features/product-category-pnl/pages/useProductCategoryRefresh.test.tsx`
- `frontend/src/test/ProductCategoryPnlBacktestFormalHistory.test.tsx`
- `frontend/tests/playwright/product-category-pnl-desktop-states.spec.mjs`

相关 Vitest 共 7 个文件、182 个用例通过。新增 6 个用例使用实际 QueryClient 验证查询去重、模式隔离、关闭面板按需加载、轮询期间切换日期和情景、旧响应丢弃、失败重试，以及任务错误与读取错误的区分。原有主页面用例继续覆盖刷新冲突、终态失败、手工调整及读取失败后的显示。

历史回测的两个断言在改前页面也失败，原因是把所有历史读取视为回测独占，忽略了管理监测已使用同一正式历史查询。本批改为检查回测没有新增重复或不适用的请求，保留正式/情景金额和结果状态断言。对照复跑通过临时 Vitest 转换插件读取改前页面完成，没有回退工作区文件。

从 `frontend/` 执行的相关回归命令：

```text
npm run test -- src/test/ProductCategoryPnlPage.test.tsx src/test/ProductCategoryPnlBacktestFormalHistory.test.tsx src/test/ProductCategoryPnlFormalScenarioContract.test.tsx src/test/ProductCategoryPnlPublicationMode.test.tsx src/test/ProductCategoryAdjustmentAuditPage.test.tsx src/test/PollingTask.test.ts src/features/product-category-pnl/pages/useProductCategoryRefresh.test.tsx
npm run lint
npm run typecheck
```

Playwright 新增 1 个浏览器流程通过，使用合成读取响应和任务回执，未执行真实财务刷新。验证了关闭面板时只更新当前管理监测所需历史，打开负债累计视图后刷新会再次读取累计历史，诊断与回测面板均保留展开状态，且没有未捕获页面异常。执行命令如下，环境变量仅作用于测试进程：

```powershell
$env:MOSS_PLAYWRIGHT_USE_WEB_SERVER='1'
$env:MOSS_PLAYWRIGHT_PORT='5908'
$env:MOSS_PLAYWRIGHT_STATE_PORT='5909'
$env:MOSS_PLAYWRIGHT_OUTPUT_DIR='../.codex-tmp/product-category-refresh-lifecycle-20260911/playwright'
npx playwright test -c playwright.config.mjs product-category-pnl-desktop-states.spec.mjs -g "refresh synchronizes" --workers=1
```

`npm run debt:audit` 执行了全部 6 项检查，其中 5 项通过；主债务检查仍因本批未修改的 `backend/app/services/pnl_service.py` 为 3753 行、超过 3748 行基线而失败。本次产品损益页面符合其行数基线，未提高任何债务阈值。全量 lint、类型检查和编码完整性检查通过。

本批没有性能基准提速结论，也不代表整个系统完成架构改造。页面模型的跨功能依赖、后端读取与任务职责分离、计算热点优化和按来源日期局部重算仍属于后续批次。此次变更没有持久化数据迁移，可通过撤回本批代码恢复原行为，无须数据库回滚。
