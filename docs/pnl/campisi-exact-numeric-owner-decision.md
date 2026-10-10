# Campisi 精确数值与正式口径负责人决策包

## 1. 结论

Campisi 当前不能通过一次前端格式化改动完成精确数值迁移。正式 PnL Bridge 在核心计算阶段仍保留 `Decimal`，但历史序列化链路会先把它压成二进制浮点；Campisi 随后只读取兼容字段 `raw`，并在行、汇总和页面适配中继续使用 `float`/`number`。因此，前端即使引入高精度库，也只能精确展示一个已经发生误差的近似值。

本轮先完成两项边界清楚的改动。PnL Bridge 在不改变现有 `raw`、`display`、排序和闭合状态的前提下，额外携带来自生产端 `Decimal` 的 `raw_text`；Campisi formal bridge 的应计利息可用性改为同时检查期初和期末，只修正质量披露，不改变金额、残差、排序或正式闭合。两项都不宣称 Campisi 已完成精确迁移，也不授权修改正式归因口径。

## 2. 改动前后与系统内置能力

改动前，PnL Bridge 的金额从 `Decimal` 进入 `promote_flat_payload` 后默认转成 `float`，响应只有兼容数值与展示文本。Campisi 的 `_numeric_raw` 只取 `raw`，前端四效应、六效应、期限桶和首页摘要继续按 JavaScript `number` 处理。超过 `2^53` 或带长小数尾数时，误差会在页面格式化之前产生。

改动后，PnL Bridge 行与汇总的 `Numeric` 信封新增精确 `raw_text`，原有 `raw` 和 `display` 保持兼容。Campisi 暂时仍读取 `raw`，所以这条 wire 不会改变选择效应、残差、闭合状态、主驱动排序或用户看到的正式金额。四个 Campisi 组件和首页适配器已经进入 exact-numeric 受控路径；其中四效应、增强归因、期限桶和首页适配器的五处 literal `/1e8` 分别登记为四项 pending。Decision Grade 目前只是受控路径，不存在可“移除”的 pending 条目；AST 守卫也不扫描所有普通 `number` 运算。

这不是另建一套计算引擎。MOSS 原有规则/缓存版本、血缘和 Golden 机制；`Numeric.raw_text`、受控路径 registry、AST 守卫和 Manifest numeric-policy digest 是本次 WP5 建立或扩展的数值治理基础。当前 `release_eligible=false` 属于全局 exact-numeric registry，并且 policy digest 只接入非生产 WP7 rehearsal，不是 Campisi 专属生产门禁。后续 Campisi 应沿用同一条生产端 Decimal、契约端 `raw_text`、展示端精确文本的路径。

## 3. 已确认事实

以下事实来自当前工作树的本地代码、契约测试、Golden 失败证据和 GitNexus 影响分析。指标契约、血缘目录和指标目录 MCP 在本轮不可用，因此没有把本地推断包装成外部权威口径。

- `backend/app/services/explicit_numeric.py:49-104` 历史默认会将 `Decimal` 转为 `float`；本轮增加的 `preserve_decimal` 是显式、默认关闭的兼容开关。这里只能证明使用 `promote_flat_payload` 的其他调用方不被全局切换；直接把 Decimal 交给 `Numeric`/`numeric_from_raw` 的其他 schema 原本就可能生成 `raw_text`。
- `backend/app/services/pnl_bridge_service.py:247-265` 只对 PnL Bridge 行与汇总的 promotion 路径启用无损传输。
- `backend/app/schemas/pnl_bridge.py:35-54` 现在能在直接接收 `Decimal` 时生成 `raw_text`，兼容数值字段仍保留。
- 当前 `Numeric.display` 仍从兼容 `float raw` 生成，不是可直接宣称精确的文本通道；例如 `Decimal('2.675')` 的兼容 display 可能受二进制浮点和现有舍入模式影响。Stage 1 保持它不变是兼容要求，正式精确展示必须另行冻结舍入模式。
- `backend/app/services/campisi_attribution_service.py:632-635` 的 `_numeric_raw` 仍只读取 `raw`；formal row、asset class、bucket、totals 和 closure summary 还在不同位置转回或读取 `float/raw`，半迁移可能让金额与状态使用不同精度基底。
- model fallback 的持仓和曲线仍会转 `float`，曲线插值还存在百分数八位中间舍入；它们都在完整 Decimal 验收范围内。
- `backend/app/schemas/campisi_attribution_read.py:150-293` 只覆盖 four/enhanced/maturity 的 plain-number DTO。`/campisi/decision-grade` 当前没有 `response_model`，直接返回 dict，缺失的响应契约本身就是迁移前置项。
- `frontend/src/features/pnl-attribution/components/CampisiAttributionPanel.tsx`、`CampisiEnhancedPanel.tsx`、`CampisiMaturityBucketPanel.tsx` 和 `frontend/src/features/workbench/dashboard-home/adapters/buildHomeMarketContextModel.ts` 的 literal 亿元缩放已登记 pending；`CampisiDecisionGradePanel.tsx` 属于受控路径，但不是现有 pending 条目。
- Campisi 仍使用静态 v1 身份，没有进入正式 module registry，meta 也没有完整中继上游 PnL Bridge 的 source/rule/cache lineage。additive `raw_text` 本身不要求提升公式版本；Campisi 开始消费精确值时才必须提升其 rule/cache、补 lineage 并重审 Golden。

以 `Decimal('9007199254740993.00005')` 为例，先转 `float` 会得到 `9007199254740994.0`，误差为 `0.99995` 元。`raw_text` 可以防止这一类误差进入新消费链，但只有 Campisi 的计算、DTO 和直接展示全部完成版本化迁移后，才能称为端到端精确。

## 4. 需要负责人决定的正式口径

这些事项会改变正式结果、质量状态、排序或管理层解释，不得由代码维护者代替业务负责人决定。

| 待决事项 | 适用分支 | 当前证据 | 需要冻结的决定 |
| --- | --- | --- | --- |
| 期间总体 | formal bridge；decision-grade 消费窗口 | 单月 PnL 可能被标成任意请求期间并仍显示闭合 | PnL 人群、期初期末与请求窗口的一致性；含头/含尾、自然日/交易日、365 年化、同日窗口和 `start > end`；错配时阻断还是降级 |
| 新增与退出持仓 | model fallback | 进场/退场持仓变化可能进入 PnL/selection | lifecycle 的计算归属、是否剔除、是否单列及披露方式 |
| 曲线单位与非正值 | model fallback | 只有当整条正值曲线的最大值低于 0.5 个百分点时，启发式才会整体放大 100 倍；零或负值会被过滤 | 输入单位契约、零/负利率合法性、曲线中间舍入和异常处理方式 |
| 到期收益率 | model fallback | Campisi 可能拒绝合法负 YTM 并回退票息；Bond Analytics 已把负 YTM 归为 observed | Campisi 是否继承权威负 YTM 分类、版本化切换、回退条件与质量标记 |
| 付息频率 | model fallback | 权威频率未完整传递时使用 1/2 次启发式 | 权威字段、缺失时的阻断或 fallback 规则 |
| 缺失值 | model fallback | coupon/face/MV 可能无质量披露地折零；YTM 也可能折零，但已有 missing warning | `missing`、真实零和不可用的区分，以及各字段对金额、质量状态和回退的影响 |
| 选择/残差 | formal bridge 与 model fallback | 现有 baseline 已规定：bridge selection 扣七项且未拆二阶项留在 selection；model selection 是曲线分解残差 | 确认或变更现有 baseline，并冻结 selection、residual noise 与二阶项的正式名称和归属 |
| 闭合、舍入与安静阈值 | formal bridge、model、decision-grade、前端 | 行级/汇总级容差、1 分或 1 元阈值、页面静默阈值和 display 舍入不是同一口径 | Decimal 舍入模式与舍入点、绝对/相对容差、状态判断精度基底、比例阈值及展示规则 |
| 排序和主驱动 | 聚合层与 Dashboard Home | 资产排名与首页最大贡献/拖累依赖浮点金额 | 使用未舍入 Decimal 还是展示值排序，以及并列规则 |

负责人字段目前均为 `PENDING`。在正式 owner、决定日期、适用规则版本和批准证据写入治理载体之前，这张表只能作为决策输入，不能作为批准记录。

## 5. 分阶段执行方案

第一阶段已经完成安全通道。PnL Bridge 为 Decimal 来源附加 `raw_text`，旧字段和 Campisi 行为不变；相关契约测试锁定兼容性和精确文本。

第二阶段只修复已有核心语义的安全中继。当前已把 formal bridge 的应计利息可用性从“只看期初”修正为“期初、期末都存在”，反例证明只改变 availability/diagnostic，不改变金额、selection、排序和 formal closure。期间错配、进出场、缺值和曲线单位的 warning/quality 状态会影响页面解释，必须先完成下一阶段的 owner 决定；在此之前最多新增不参与 status/quality 的观察字段，不能统一标成 SAFE 披露。

这项中继仍有三个已知披露缺口。formal bridge 复用的应计利息诊断文案描述了 model 路径的净价/票息 fallback，与正式桥金额来源并不完全一致；PnL Attribution 会展示 availability，但 Dashboard Home 不消费该质量提示；顶层 `result_meta.quality_flag` 也不会因这项 availability 单独升级。修正文案、首页传播或顶层质量状态都会改变用户解释或消费契约，应分别评审，不能夹带在本次布尔判定修复中。

第三阶段由 PnL、固收模型、财务口径和前端产品责任人共同冻结上表中的决定。批准材料必须同时给出规则版本、缓存版本、适用起始日期、历史重算范围、Golden 差异解释、回滚条件和审批摘要。

第四阶段进行版本化生产端迁移。Campisi bridge 与 model 两条路径应从 row 到 asset class、maturity bucket、total、summary 和 closure 全部保持同一 Decimal 精度基底；closure 状态不得一边读取 `raw_text`、另一边继续读取近似 `raw`。model 曲线的 float 转换、插值中间舍入也必须纳入迁移。four/enhanced/maturity DTO 改为受治理的 `Numeric` 信封，decision-grade 先补严格 response model；旧 `raw` 仅作兼容，正式计算读取原始 Decimal 或来源一致的 `raw_text`。这一阶段才提升 Campisi rule/cache、注册 module identity、补齐 PnL Bridge 上游 lineage 并重审 Golden，不能把行为变化隐藏在现有 v1 身份下。

第五阶段迁移前端直接展示。当前后端 `display` 仍由兼容 float 生成，不能作为精确来源；在后端具备 Decimal-derived display 前，金额、占比、表格和 tooltip 应使用 `raw_text` 的受控 Decimal formatter，并采用 owner 冻结的舍入模式。图表坐标可以在最后边界转成 `number`，但不能反向参与正式闭合、排序或主驱动判断。四效应、增强归因、期限桶和首页摘要的现有 pending 要逐项清零；Decision Grade 需要先补响应契约和精度用例，而不是移除一个不存在的 pending 条目。

第六阶段形成发布证据。需要新增 Campisi 专用 JSON Golden、超过 `2^53` 和长小数尾数的浏览器证据、期间/生命周期/负收益率/缺失值样本、行级与汇总闭合测试，并由 owner 审阅差异后重新捕获。Golden、版本、血缘、registry 和审批证据全部闭合，才能把 Campisi 纳入未来正式发布门；当前全局 rehearsal policy 仍不等于 Campisi 专属生产门禁。

## 6. 验收标准

Campisi 精确数值工作只有同时满足以下条件才算完成：生产端从 row 到各级聚合、bucket、total、summary、closure 和排序保持同一 Decimal 精度基底；所有非 null、Decimal-backed 的正式金额和比例 DTO 都提供来源一致的 `raw_text`，null 仍按契约省略；页面直接展示不再通过二进制浮点重建文本；图表数值边界不参与正式判断；期间、生命周期、曲线单位及中间舍入、YTM、付息频率、缺失值、选择/残差和容差均有 owner 决定；Campisi rule/cache、module identity 与上游 lineage 已治理；专用 Golden、契约、浏览器和降级测试全部通过；相关受控路径和 pending 在审批证据约束下闭合。

目前只满足了第一阶段、应计利息两端可用性的安全中继及 registry 登记。现状应表述为“PnL Bridge 无损数值通道已建立，Campisi 已修正一项质量披露，正式迁移待负责人决策”，不得写成“Campisi 已完成精确数值改造”或“归因口径已获批准”。

## 7. 当前验证与已知门禁

本轮定向测试已经证明 PnL Bridge 的兼容 `raw/display` 不变，Decimal 来源新增精确 `raw_text`；应计利息期末缺失时 Campisi availability 正确降级，而 totals、selection 和 formal closure 不变。现有 Campisi 公式/组件测试可以防止已知行为回归，但不能替代上表中的正式口径决定，也没有覆盖全部高精度边界。

在本决策包形成的早期验证阶段，PnL Bridge 两个历史 Golden 曾在比较新增字段前因运行时 PnL rule v4 与样本 v3 不一致而失败。2026-09-05 工作树验收已对样本版本、`raw_text` 及差异解释完成技术重捕获和复核；这不替代本包所列正式口径的负责人决定，相关 owner 状态仍为 `PENDING`。后续重捕获同样必须审阅规则版本和精确字段差异，不能把刷新 Golden 当作业务批准。
