# MOSS Fixed Income Platform — Frontend Implementation Spec

> **Source:** Deep Interview Session 2026-04-14
> **Mockups:** `.omx/mockups/*.png` (6 files)
> **Interview Spec:** `.omx/specs/deep-interview-frontend-display.md`

你现在是当前仓库里的前端主程 + 产品实现负责人。请基于 workspace 中已有的固定收益平台页面稿与规范文档，实现一套 6 页面、可运行、可扩展的固定收益前端平台。

# ====================

一、Source of truth

先在仓库里查找并读取以下文件；如果命名略有差异，寻找最接近的文件并说明映射关系。不要忽略这些文件。

页面稿（英文名）：

- dashboard_overview_hd.png
- business_analysis_hd.png
- bond_analysis_hd.png
- cross_asset_drivers_hd.png
- asset_liability_analysis_hd.png
- market_data_hd.png

规格文档：

- moss-fixed-income-platform-spec.md

如果 workspace 中还存在以下文件，也请读取并参考：

- ZQTZSHOW-20260301.xls
- TYWLSHOW-20260301.xls

重要原则：

1. 上述 PNG 是页面布局和信息层级的 source of truth。
2. 规格文档是产品和工程约束的 source of truth。
3. 如果图片与文档有轻微冲突，以"页面职责 + 统一设计系统 + 工程可维护性"为优先。
4. 不要自己发明另一套产品结构，不要做成新的"AI dashboard"。

# ====================

二、最终目标

在当前 repo 中实现一个"固定收益平台"前端，至少包含以下 6 个页面，并接入统一导航：

1. /dashboard                -> Dashboard Overview
2. /business-analysis        -> Business Analysis
3. /bond-analysis            -> Bond Analysis
4. /cross-asset-drivers      -> Cross Asset Drivers
5. /asset-liability-analysis -> Asset Liability Analysis
6. /market-data              -> Market Data

要求：

- 页面真实可运行，不是静态切图。
- 桌面端优先，适配 1366~1920 宽度。
- 中文 UI。
- 使用 mock 数据先跑通，但数据层必须可切换到真实 API。
- 路由、导航、布局、组件、状态、图表、表格都要落成代码。
- 页面之间要有统一视觉和统一交互规则。

# ====================

二.五、实施策略（关键约束）

**增量重构，不是推倒重来。**

当前仓库已有大量部分实现的页面：


| 目标页面                     | 现有文件                               | 策略              |
| ------------------------ | ---------------------------------- | --------------- |
| Dashboard                | `DashboardPage.tsx`                | 在现有基础上增强        |
| Business Analysis        | `OperationsAnalysisPage.tsx`       | 在现有基础上增强        |
| Bond Analysis            | `BondAnalyticsView` + 子组件          | 在现有基础上增强        |
| Cross Asset Drivers      | 跨资产页面                              | 在现有基础上增强        |
| Asset Liability Analysis | `BalanceAnalysisPage.tsx` (~2000行) | 在现有基础上增强（第一优先级） |
| Market Data              | `MarketDataPage.tsx`               | 在现有基础上增强        |


具体后端-前端差距：

- `BalanceAnalysisPage`: `/summary-by-basis` 和 `/advanced-attribution` 完全未接入；Detail 的 `summary[]` 未渲染；多个字段被忽略
- `DashboardPage`: 有 executive sections 但远未达 mockup 水平
- `BondAnalyticsView`: 有模块注册表但后端筛选参数未暴露
- `MarketDataPage`: 有明确占位文字"该板块图表待接入"
- 全局：`workbenchTheme` 定义了但未挂载到 `ConfigProvider`

**需新增的 API Client 方法（contracts.ts + client.ts）：**

- `getBalanceAnalysisSummaryByBasis(params)` → `GET /ui/balance-analysis/summary-by-basis`
- `getBalanceAnalysisAdvancedAttribution(params)` → `GET /ui/balance-analysis/advanced-attribution`

**需新增的类型：**

- `BalanceAnalysisBasisBreakdownPayload` / `BalanceAnalysisBasisBreakdownRow`
- `AdvancedAttributionBundlePayload`

**交互层次要求：层次 C**

- 顶部固定筛选器做高层维度选择（日期、持仓口径、币种、会计口径等）
- 表格区域内可做行展开、分组、小计等下钻操作（AG Grid Row Grouping / Pivot）

# ====================

三、工作方式（必须遵守）

先不要盲目开写。按下面顺序执行：

Step 1. 扫描仓库并输出 implementation plan
必须识别：

- 技术栈（React / Next / Vue / Vite / 其他）
- UI 组件体系
- 路由方式
- 状态管理方式
- 数据获取方式
- 图表库
- 表格库
- 主题 / tokens / layout shell
- 是否已有 side nav / app shell / card / table / chart wrapper

Step 2. 给出简洁但完整的实施计划
输出格式固定为：

- Repo findings
- Route plan
- File plan
- Component plan
- Data plan
- Validation plan
- Risks / assumptions

Step 3. 直接开始实现
除非遇到真正的 blocker，否则不要停下来等我确认。对普通工程决策自主处理，并在最终总结中说明。

Step 4. 验证
至少运行：

- lint
- typecheck
- build

如果 repo 中存在 Playwright / E2E / screenshot testing：

- 增加 6 个页面的最小 smoke coverage
- 或至少做可渲染检查

Step 5. 最终输出
固定格式：

- What changed
- Routes implemented
- Data wiring status
- Validation results
- Remaining risks
- Next recommended step

# ====================

四、绝对不能违反的设计约束

1. 必须复用当前项目已有设计系统

- 复用现有 tokens、颜色、阴影、圆角、栅格、布局容器、表格、按钮、图表封装
- 不要创造平行设计系统
- 不要引入大面积新风格

1. 风格要求

- 机构化、克制、浅色背景
- 信息密度高但可读
- 以 KPI 卡片、表格、状态标签、小趋势图、热力图为主
- 不要霓虹、毛玻璃、夸张渐变、发光、炫技 3D、过大的圆角卡片
- 不要"AI 概念图"风格

1. 页面职责必须清楚，不能互相重复

- Dashboard Overview：总览 + 分流 + 优先级，不做深度分析
- Business Analysis：收益质量、成本结构、期限缺口、经营动作
- Bond Analysis：债市内部判断（利率、曲线、信用、候选动作）
- Cross Asset Drivers：跨资产变量如何传导到债券，不是最终执行页
- Asset Liability Analysis：资产负债结构、缺口、滚续压力、风险指标
- Market Data：盘中数据终端页，信息密度最高

1. 文字要求

- 页面 copy 用中文
- 文件名、组件名、路由名用英文
- 不要堆一堆假大空文案
- 所有摘要都要简洁、业务化、可落地

1. 响应式策略

- desktop-first
- 重点保证 >= 1366px
- 小屏可以降级，但不要为了移动端破坏桌面信息密度
- 没有必要做完整 mobile app 风格

# ====================

五、统一站点结构

左侧主导航顺序固定为：

- 驾驶舱
- 经营分析
- 债券分析
- 跨资产驱动
- 团队绩效
- 决策事项
- 资产负债分析
- 市场数据
- 中台配置
- 报表中心

当前任务至少先把以下 6 个落地并可进入：

- 驾驶舱
- 经营分析
- 债券分析
- 跨资产驱动
- 资产负债分析
- 市场数据

其余导航项先保留占位或 disabled 状态即可，但不要做坏整体布局。

# ====================

六、页面职责与模块要求

---

1. Dashboard Overview /dashboard

---

定位：

- 首页总览 + 模块分流
- 不替代下面各专题页
- 先告诉用户"当前是什么状态、先看哪里"

必须包含：

1. 顶部 KPI 卡片
  - 市场资产
  - 市场负债
  - 资产负债差额
  - 静态利差
  - 1年内净缺口
  - 债券资产浮盈
  - 发行负债占比
  - 重大预警数量
2. 全局判断
  - 一段管理语言摘要
  - 说明资产端、负债端、短端缺口、长端配置的总体状态
3. 模块快照
  - 债券分析
  - 跨资产驱动
  - 资产负债分析
  - 市场数据
   每个模块用小卡片给出一句判断，点击可下钻
4. 预警中心
  - 短端缺口预警
  - 大额负债到期
  - 发行负债集中度
  - 异常资产跟踪
5. 结构与期限总览
  - 资产 / 负债结构条形图
  - 期限净缺口条
6. 今日待办
  - 来自各专题页的动作摘要
  - 例如滚续负债、关注 5Y、跟踪美债油价、复核异常资产
7. 关键日历
  - 近期负债到期、关键事件
8. 模块联动入口
  - 4 张较大的入口卡片，分别解释 4 个专题页"回答什么问题、输出什么结果"

说明：

- 首页重点是"总览 + 导航 + 优先级"
- 不要把各专题页内容全部塞进来

---

1. Business Analysis /business-analysis

---

定位：

- 面向管理层或经营层
- 回答"收益质量如何、成本结构是否健康、经营动作是什么"
- 不是交易员盘口页

必须包含：

1. 顶部 KPI
  - 市场资产
  - 市场负债
  - 静态资产收益率
  - 静态负债成本
  - 静态利差
  - 净经营贡献（静态年化）
  - 发行负债占比
  - 重大关注项
2. 本期经营结论
  - 用管理语言总结经营状态
  - 重点说收益来源、负债压力、缺口矛盾
3. 收益成本桥（瀑布图或等价表达）
  - 债券资产收益
  - 同业资产收益
  - 发行负债成本
  - 同业负债成本
  - 净经营贡献
4. 经营质量观察
  - 资产/负债比
  - 发行负债集中度
  - 短期负债占比
  - 1年内缺口/负债
  - 异常资产占比
   每项要有状态标签：正常 / 关注 / 预警
5. 资产 / 负债经营贡献
  - 资产大类、负债大类表格
  - 包括余额、占比、利率/收益、经营含义
6. 本期关注事项
  - 滚续负债
  - 优化结构
  - 提高收益质量
  - 处置异常
7. 近期经营日历
  - 负债到期与关注说明
8. 期限与集中度
  - 缺口条图
  - 集中度指标表
9. 管理输出
  - 经营判断
  - 核心矛盾
  - 当前优先级
  - 下钻方向

重要：

- 不要伪造预算完成率、资本占用、风险预算使用率等无法从当前 mock 明确得到的数值
- 如果 repo 已有真实经营 API，再接入；如果没有，就先留占位并标注 pending API
- 不允许硬编假数据装作真实结果

---

1. Bond Analysis /bond-analysis

---

定位：

- 债市内部分析页
- 只看债券市场本身
- 输出"债市候选动作"，不是最终管理指令

必须包含：

1. 顶部债市 KPI
  - 10Y 国债
  - 10Y 国开
  - 10Y-1Y 曲线斜率
  - 5Y/10Y 关键利差
  - AAA 3Y 利差
  - 1Y AAA 存单
  - DR007
  - 5Y IRS / 国债期货代表值
2. 市场判断
  - 一句话 / 一段话说明当前债市状态
3. 驱动拆解
  - 资金面
  - 政策预期
  - 供给
  - 海外扰动
   每一项有方向、强弱、解释
4. 收益率曲线
  - 国债 / 国开曲线
  - 当前形态
  - 简短解读
5. 信用利差
  - AAA / AA+ / AA 关键利差
  - 历史分位
  - 拥挤 / 中性 / 可配标签
6. 候选动作
  - 关注 5Y 国债
  - 暂不追 10Y
  - 信用仅做票息
  - 观察 1Y 存单
   注意：叫"候选动作"，不要叫"决策事项"
7. 观察名单
  - 关键券种 / 关键利差 / 关键评级段
8. 事件与供给日历
  - 国债 / 国开招标
  - 供给扰动
  - 宏观数据

---

1. Cross Asset Drivers /cross-asset-drivers

---

定位：

- 看跨资产变量如何传导到债券
- 输出"市场信号 / 候选动作"
- 不是内部执行页

必须包含：

1. 顶部 KPI
  - 10Y 国债
  - 10Y 美债
  - 中美国债利差
  - DR007
  - 沪深300
  - 原油
  - 铜 / 工业品
  - USD/CNY
2. 市场判断
  - 一句话说明主导因子和对债券的影响
3. 驱动拆解
  - 流动性
  - 海外约束
  - 增长预期
  - 通胀扰动
  - 风险偏好
4. 估值 / 分位热图
  - 10Y 国债
  - 5Y 国开-国债
  - AAA 3Y
  - 1Y AAA 存单
  - 中美国债利差
5. 跨资产走势（近20日统一基准）
  - 10Y 国债
  - 10Y 美债
  - A股
  - 原油
  - DR007
  - 铜
6. 市场候选动作
  - 关注 5Y 国债
  - 观察 1Y 存单
  - 暂不追长端
  - 信用仅做票息
7. 事件与供给日历
  - 国债招标
  - 同业存单到期
  - 美国非农 / CPI
  - 海外议息
8. 观察名单
  - 关键券种 / 关键跨资产信号

重要：

- 这一页不能和 Bond Analysis 重复
- Bond Analysis 看债市内部
- Cross Asset Drivers 看外部变量如何推债券定价

---

1. Asset Liability Analysis /asset-liability-analysis

---

定位：

- 金融市场条线口径的资产负债分析
- 重点是结构、缺口、成本、滚续、风险指标
- 不做会计报表翻版

必须包含：

1. 顶部 KPI
  - 市场资产
  - 市场负债
  - 静态资产收益率
  - 静态负债成本
  - 静态利差
  - 1年内净缺口
  - 债券资产浮盈
  - 异常预警
2. 摘要
  - 资产以债券为主
  - 负债以发行类为主
  - 短端缺口承压
  - 当前最关键经营问题
3. 收益成本分解（静态口径）
  - 债券资产收益
  - 同业资产收益
  - 发行负债成本
  - 同业负债成本
  - 静态利差 / 净经营贡献
4. 风险全景
  - 期限错配
  - 流动性压力
  - 负债滚续压力
  - 对手方集中度
  - 异常资产
5. 资产 / 负债 / 缺口贡献
  - 结构表或条形图
  - 支持"按资产大类 / 按负债大类 / 按期限桶"
6. 待关注事项
  - 短端缺口
  - 发行负债集中度
  - 高成本负债
  - 异常资产
7. 预警与事件
  - 缺口预警
  - 大额到期
  - 发行负债敏感
  - 异常资产跟踪
8. 期限结构
  - 资产 / 负债 / 净缺口按期限桶展示
  - 明确 7天、8-30天、31-90天、91天-1年、1-3年、3-5年、5年以上、无固定到期
9. 风险指标
  - 资产 / 负债比
  - 短期负债占比
  - 发行负债集中度
  - 异常资产占比
  - 浮盈覆盖率
  - 1年内缺口 / 负债
10. 关键日历
  - 未来到期负债清单
  - 级别：高 / 中 / 低
  - 说明：重点滚续 / 关注成本 / 常规观察

重要工程要求：

- 不要在浏览器端直接解析 xls 文件
- 把 Excel 转成 mock JSON 或预置 mock data
- 前端只消费标准化 view model，不消费原始台账字段

---

1. Market Data /market-data

---

定位：

- 盘中市场数据终端页
- 数据密度最高
- 偏交易台界面，但仍然维持当前浅色 MOSS 风格

必须包含：

1. 顶部 KPI
  - 10Y 国债
  - 10Y 国开
  - DR007
  - 1Y AAA 存单
  - AAA 3Y 利差
  - 5Y IRS
  - 10Y 美债
  - USD/CNY
2. 利率行情
  - 国债 / 国开关键期限表格
3. 收益率曲线
  - 国债 / 国开
  - 当前曲线对比
4. 信用利差
  - 中短票 / 城投债关键评级段
5. 资金市场
  - R001 / DR001 / DR007 / R007 / SHIBOR
6. 国债期货
  - T / TF / TS / TL 主力
7. 同业存单
  - 期限 x 评级 的利率矩阵
8. 债券成交明细（现券）
  - 时间、简称、期限、价格、收益率、方向
9. 信用债成交明细
  - 时间、简称、评级、价格、收益率
10. 资讯与日历
  - 债市快讯
  - 宏观与海外事件

重要：

- 这是 market terminal 风格页面
- 以高密度表格 + 曲线 + 明细为主
- 不要做成大块叙事页

# ====================

七、统一组件要求

尽量抽公共组件，不要 6 个页面各写一套：

必须抽出或复用以下通用组件（名称按当前 repo 风格适配）：

- AppShell / Sidebar / Header
- FilterBar
- KpiCard（支持小 sparkline）
- SectionCard
- StatusPill
- DenseTable
- CurveChart
- BarList / GapBar
- HeatmapTable
- AlertList
- CalendarList
- CandidateActionList
- SummaryBlock
- Empty / Error / Loading / Skeleton 状态组件

所有页面都要统一：

- 卡片 padding
- 标题层级
- 表格密度
- 状态标签颜色
- 数字格式化方式
- 更新时间显示位置

# ====================

八、数据层与 API 适配要求

必须设计"mock / api 双模式"，不要把 mock 写死在页面组件里。

要求：

1. 创建 feature-level 数据层
  建议结构（按当前 repo 约定调整）：
  - types/
  - services/
  - mocks/
  - adapters/
  - hooks/ or queries/
2. 用环境变量或配置切换数据源
  例如：
  - mock
  - api
3. 所有页面只消费 normalized view model
  不要在页面里直接做复杂字段变换
4. Excel 口径页面的初始 mock seed
  先使用下面这些值作为 seed data（用于 Dashboard / Business / Asset Liability 三页）：
  - marketAssetsYi: 3525.0
  - marketLiabilitiesYi: 1817.9
  - assetYieldPct: 2.07
  - liabilityCostPct: 1.77
  - staticSpreadBp: 29.5
  - oneYearGapYi: -373.0
  - bondFloatingGainYi: 68.48
  - issuedLiabilitySharePct: 66.3
  - ncdShareWithinIssuedPct: 81.8
5. 不要伪造真实后端能力
  - 如果没有 API，就保持 mock
  - 如果某指标（如预算完成率、资本占用、风险预算使用率）没有来源，就不要硬编
  - 可以在 UI 上显示 "Pending API" 或 feature flag disabled
6. 服务层建议至少预留这些 service 模块
  - overviewService
  - businessAnalysisService
  - bondAnalysisService
  - crossAssetService
  - assetLiabilityService
  - marketDataService
  - alertsService
  - calendarService

# ====================

九、工程实现约束

1. 路由

- 使用当前项目现有路由体系
- 不要额外创造第二套路由系统
- 6 个页面全部可访问

1. 代码组织

- 页面必须拆成可维护组件
- 不允许一个页面一个超大文件塞完所有 JSX/模板/逻辑
- 类型定义完整
- 数据映射与视图组件分开

1. 性能

- 用按路由拆包 / lazy load 降低 bundle 压力
- 重型图表和大表格尽量懒加载
- 不要为了 demo 引入一堆新的重型依赖

1. 状态

所有页面必须处理：

- loading
- empty
- error
- retry
- last updated
- mock mode / api mode 标识（如果合适）

1. Git / 工作区

- 如果当前 workspace 不是 git repo，不要主动初始化 git，直接报告
- 不要改动无关文件
- 不要做大规模无必要重构

# ====================

十、验证与验收标准

最低验收标准：

1. 6 个页面都能通过路由进入
2. 左侧导航高亮正确
3. 布局、层级、模块划分与 PNG 基本一致
4. 统一视觉风格成立
5. mock 数据完整可运行
6. 页面有 loading / empty / error 状态
7. lint 通过
8. typecheck 通过
9. build 通过
10. 如果有 E2E/Playwright，至少能打开 6 个页面并截图或断言关键标题存在

额外要求：

- 首页不要重复专题页
- Business Analysis 不要重复 Dashboard
- Cross Asset Drivers 不要重复 Bond Analysis
- Asset Liability Analysis 不要变成会计报表
- Market Data 保持高密度终端感

# ====================

十一、最终输出格式

最终回复固定用这个结构：

1. Repo findings
2. Implementation summary
3. Routes implemented
4. Major files changed / added
5. Data layer status (mock/api)
6. Validation results
7. Remaining risks
8. Recommended next step

# ====================

十二、禁止事项

禁止：

- 发明新的产品信息架构
- 使用夸张"AI dashboard"视觉
- 在 UI 中伪造无来源经营指标
- 在浏览器端直接解析 .xls 作为正式方案
- 把 6 个页面都写成一个巨大文件
- 为了赶时间跳过 lint/typecheck/build
- 大面积改动当前项目无关部分

现在开始：

1. 先扫描 repo 并给出 implementation plan
2. 然后直接实现
3. 最后按约定格式汇报结果