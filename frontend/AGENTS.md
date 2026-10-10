# Frontend AGENTS.md

适用于 `frontend/`，沿用根 [AGENTS.md](../AGENTS.md)。本文件统一前端任务分级与验收；其它前端指南只补充设计或实现细节。

## Classify the change first

选择覆盖任务的最轻层级，仅在证据表明跨越边界时升级。

### Tier 1: visual-only

仅文案、间距、色彩、字体、响应式或呈现调整，不改变数据访问、业务含义、计算、筛选、日期、单位或显示值。检查目标组件及其样式/token；做相关静态检查和浏览器/组件验证，不新增业务逻辑测试，不查指标契约、血缘或数据目录。若暴露业务正确性问题，再升级。

### Tier 2: page-local business display

单页 adapter、formatter、selector/view model、筛选、指标呈现、日期、单位、fallback 或状态行为变化。只追踪受影响指标；现有契约、源码和测试足以确认口径时直接复用，定义或血缘不明确时再查 `moss-metric-contracts`、`moss-lineage-evidence`，来源列、可用性或报告日不明确时再查 `moss-data-catalog`。增补最小有效的相关行为测试，已有用例能证明修复时复用，不为工具清单追加检查。

### Tier 3: shared or cross-page business logic

共享 client、selector、formatter、跨页状态或其它多流程消费者发生变化。按根 GitNexus 规则分析影响，核对下游契约、日期、单位与 fallback，按已确认影响范围扩大验证；HIGH/CRITICAL 改动前告知用户。

## Navigation and architecture

从 `src/router/routes.tsx` 定位路由，再进入 `src/features/<domain>/`。正式金融计算留在后端；新建或实质修改端点实现放入 `src/api/` 对应领域 client，`src/api/client.ts` 只组合导出。新增或迁移的 mock 放在 `src/mocks/`，不向组合入口添加 payload 块。样例导入只允许测试、显式演示入口和受控模式选择器；尚未迁移的旧模块按 ESLint 中的明确例外逐域收敛，不扩大全目录豁免。生产构建必须移除样例依赖，真实请求失败不得转用样例。

## Affected metric verification

Tier 2/3 追踪受影响的 API 响应、adapter/transformer、store/state、selector/view model、组件及图表/表格。按实际风险核对单位换算（元/万元/亿元/%/bp）、精度与序列化、`null/0/undefined/NaN`、交易日/自然日/月末/YTD、`as_of_date` 与缓存/fallback 日期、mock/硬编码、前端重复计算，以及卡片/图/表筛选一致性。

Explicitly surface material no-data, stale-data, fallback-date, loading-failure, and unconfirmed-definition states. 工具不可用时按根规则说明本地替代证据与残余风险，不猜指标含义。

## UI and page models

修改外观前读 [DESIGN.md](../DESIGN.md)，仅在涉及指定路由或布局迁移时跟进其链接。页面首屏先回答一个主要业务问题。优先 token、页面原语、CSS modules 或页面局部样式；不复制布局 inline style，单次、局部、动态值可内联，不无故增加视觉复杂度或抬高债务基线。

新 view model 复用 `src/pageModel` 的 `LabeledValue`、`StateSurfaceItem`、`buildStateSurfaces`、`MetricTone` 和 `src/utils/format.ts`、`src/utils/tone.ts`，不新增重复的私有 formatter/tone；只有多个页面模型重复同一结构时才扩展共享原语。新页面缺值从 `src/pageModel` 或 `src/utils/format` 导入 `EM_DASH`，不新写 `"—"`、`"-"`、`"--"` 字面量。业务着色入口统一见 DESIGN §4.1。

## Evidence and validation

局部反馈的启动与命令统一见 [前端开发入口](README.md#运行局部检查)，按改动显式选择测试、lint 文件和必要的类型检查。同一批改动稳定后集中做一次收尾检查。复用当前依赖、源码和有效结果，不为常规验证复制候选源码或安装独立环境；页面 README 只补充模块边界和相关测试入口。

Tier 1 运行适用的文件级静态检查和相关视觉检查，不强制 typecheck 或业务测试。Tier 2 运行受影响文件的 lint 和相关行为测试；改变 TypeScript 结构、导入或类型，或无法由定向检查排除类型风险时，在现有环境运行一次 `npm run typecheck`。纯文案、样式以及类型结构未变且相关路径已验证的小修不重复类型检查。

Tier 3 按已确认的调用者扩大测试，执行 `npm run typecheck`；lint 只有受影响范围无法可靠选取，或规则、共享基础层要求时才全量运行。局部改动不强制 `npm run debt:audit`；仅在涉及债务规则/基线、仓库级规范、广泛共享基础层，或明确的 CI、正式发布验收要求时运行完整审计，其余按实际风险选相关子检查。全量测试也只由相关失败、共享风险或明确交付要求触发。既定 CI 和正式发布要求保留，但不自动套用于每次本地修复。

仅文档或注释改动检查文本、链接和编码，不跑前端构建或业务测试。构建用于验证打包风险或让本地入口加载改动，不是所有源码修改的默认收尾；本地生效及正式交接范围遵循根规则。

可见布局或交互变化做浏览器核对；版式以 1440×900 为基准，仅涉及响应式时补受影响断点。按 Tier 选相关组件/域测试，纯视觉不新增业务测试；共享样式影响 loading、空态、重试或空表时触发对应状态。主题 token/scope 变化运行相关主题测试，核对实际解析值和路由例外。

`debt:audit` 只证明脚本覆盖的债务未增长；Shape Lock 跳过 `var(...)` 及其 fallback，`style:audit` 告警也不等于设计验收通过。定向组件或浏览器检查补足实际圆角、主题和可见状态，报告范围沿用根验收规则。

审美合规改造按 DESIGN §10.1 使用 `node scripts/visual-compliance-audit.mjs` 采集页面指标与截图。默认覆盖方案中的 21 个路由；1440×900 检查全部门槛，1280×720 复查溢出、截断、左边线与控件。脚本参数以 `--help` 为准，阈值和已批准例外统一保存在 `scripts/visual-compliance.thresholds.json`；超标返回非零退出码。例外须有路由、原因和批准人，不以调高门槛替代修复。浏览器检查与 Vitest 串行执行，使用 mock 数据和任务专用输出目录，复用既有临时服务工具，不重启常驻服务。探针结果须结合相同视口的截图复核，不能替代业务检查或用户验收。
