# 全局统一美观度优化方案（提案 · 执行中）

> 状态：**执行中**（2026-07-19 起按本方案 Phase 0→1→2→3→4 推进；会话内曾用 4a/4b/4c/4d 称呼浅色长尾批次，对应本方案 **Phase 3**，不是 Phase 4）。
> 基准权威：`DESIGN.md`（双主题体系）+ `frontend/src/theme/designSystem.ts` + `frontend/src/styles/tokens.css`。
> 审计依据：2026-07-19 四路只读审计（token 层 / 页面主题 / 共享组件 / 字体动效）；运行时红线：`scripts/audit_visual_tokens.mjs`（只降不升）。

### 进度快照（相对本方案）

| Phase | 状态 | 备注 |
|---|---|---|
| **0 地基** | ✅ 完成 | 0.1–0.6 已落地；呼吸光业主豁免保留 |
| **1 深色并轨** | ✅ 主路径完成 | 1.1–1.6 主路径已落地；壳内非主路径阴影长尾可并入 Phase 4 / 截图复核批 |
| **2 共享原语** | ✅ 主路径完成 | **2.2–2.5** ✅；**2.1** 业务消费点已迁完（含经营分析三卡→`EvidencePanel`）；仅 `cashflow-projection` WIP 冻结保留旧 `DataSection`，旧组件本体+契约测试作兼容边界 |
| **3 浅色长尾** | 🔄 接近完成 | **3.1–3.2 ✅**；**3.3** KPI 两行 clamp ✅；Stock/Market + 三 module-home（module/market/risk）9–10.5px ✅；CrossAsset / EquityKpi / DeepResearch / 壳层活页已收口；长尾：MacroToolkit(~81)、ledger-pnl、balanceWorkbench、`dashboardCockpit` 等；rem 字面量另批 |
| **4 死代码** | ⏳ 未开始 | |

视觉水位（2026-07-20 3.3 收尾核对）：hex **1467** / offRadius **218** / `"--"` **13** / forbidden **1** / TSX style props **1056**/1541（相对开局约 3800+ hex 已下降；typecheck、debt:audit 通过；`style:audit` workspace-vs-HEAD 现被无关 WIP `bondAnalyticsCockpitTokens.ts` 1 处 private shadow 挡住，非本批 3.3 文件）。

---

## 0. 一句话结论

系统的视觉问题**不是"不够好看"，而是"同一套设计语言被实现了四遍"**。
DESIGN.md 的方向（冷静、可审计、双主题）不需要推翻；需要的是先把 token 层收敛成单一来源，再把分裂的页面与原语逐层并轨，最后才谈得上"美观度升级"。

---

## 1. 现状诊断（审计事实摘要）

### 1.1 地基：token 双源矛盾，深色族没有"户口"

| 问题 | 证据 |
|---|---|
| TS 与 CSS 同名不同值 | `radius.sm`：TS=6（designSystem.ts:247）vs CSS=2px（tokens.css:145）；`shadow` 四档 TS 各异、CSS 全压平；`railSectionLabel` 三处两值 |
| `--dh-api-*` 深色终端 token 无权威定义点 | 仅活在 `dashboardHomeShell.module.css:3494-3531` 的 module 作用域里，且已被复制 3 次并开始漂移（`--dh-api-muted` 两处不一致） |
| 同名 `.dhPage` 两个 CSS module 两种主题 | 深色：dashboardHomeShell.module.css:1；浅色：dashboardHome.module.css:34——页面 import 错模块即整页明暗翻转，这是全站主题体系的实际枢纽，也是最大事故结构 |
| 死样式层 | dashboardCockpit.css（3139 行全局引入）约 79% 类疑似死亡、引用未定义变量、158 个 `!important`；`--moss-color-warm-*` 桥接变量生产零引用 |
| 字体名漂移 | "IBM Plex Mono"（132 处消费）、"Inter"、"Plus Jakarta Sans"、"Alibaba PuHuiTi" 均未本地托管，静默 fallback |

### 1.2 页面：四套深色 palette 并存

| palette | accent | 使用页 | 合规性 |
|---|---|---|---|
| dh-api 钦定（去饱和） | `#72a7dc` | 经营日报、风险总览（2 页） | ✅ |
| portfolio/market/bond 系 | `#7dd3fc` 亮天蓝 | 组合、市场、债券分析（3 页，逐行复制） | ❌ 非 dh-api |
| stock-analysis 系 | `#1d4ed8` 高饱和 | 股票分析 | ❌ 命中 §11.7 一票否决 |
| macro-toolkit | 深色壳类 + 浅色 token 覆盖 | 宏观工具箱 | ❌ DESIGN 说是深色页，实际渲染浅色 |

另有两处 Page Theme Lock 硬伤：`/market-data` 浅色页首屏内嵌深色 command sheet（MarketDataPage.css:13220）；`/bond-dashboard`、`/cube-query`、`/platform-config`、`/concentration-monitor` 仍是 antd 毛坯 + inline style，未接入 token 体系。

### 1.3 原语：同一语义三套实现

- 区块卡片 ×3：DataSection / AsyncSection（20px 圆角）/ SectionCard（8px），合计 48 个消费点，全部浅色限定
- KPI ×3：KpiCard（13 个内联 style 对象、硬编码白底）/ page-v2 KpiBand / 各页自造
- section-lead ×2、skeleton ×3（其中 Skeletons.tsx 引用了不存在的 Tailwind 类，边框静默丢失）
- 圆角离散取值 10 种（2/6/8/10/12/14/16/18/20/24px），DESIGN 只允许 2 种（浅色 2px / 深色 6px）；`displayTokens.ts:75` 把 20px 写进了 token 层，等于把反模式合法化
- **正确方向已存在**：`page/PagePrimitives.tsx` 的 page-v2 契约族（class 驱动、有测试、18 个消费点）应成为唯一标准

### 1.4 字体与动效

- 深色页衬线越界：经营日报刊头、风险页 hero、股票分析 4 处（§3：深色页不用衬线）
- KPI 主值未走 tabular 等宽栈（shell:1866 `.dhHeroKpiValue` 仅裸 sans）
- 字阶越界：深色页 hero 数字 40–56px（§3 上限 24px）；538 处 10px 字体（§3 下限 11px）
- **AI 紫实锤**：dashboardHomeShell.module.css:2679 `rgba(139,92,246)`（§4 明令禁用）
- `dhAmbientCanvasBreathe 6.4s infinite` 呼吸动效回加（§8：已移除、不得回加）
- reduced-motion 缺口：agent / cross-asset / stock-analysis 三域共 6 个无限动画无退化

### 1.5 量级

硬编码 hex 约 3,800+ 处（StockAnalysisPage.css 单文件 564）；inline style 1,100+ 处；`!important` 5,090 处（StockAnalysisPage.css 占 2,303）；6 个样式文件各超 6,000 行。`npm run debt:audit` 当前全部通过（基线即现状，只能降不能升）。

---

## 2. 目标态设计方向（美观度判断）

在 DESIGN.md「冷静、可审计」北极星之下，补四条可执行的审美纪律，作为本轮统一的"目标感"：

1. **一页一个签名强调色，其余全部中性阶梯。**
   强调色只出现在交互态（hover/选中/激活）、主 CTA、关键状态上；次要表面用灰阶递进表达层级。当前深色页 sky 蓝、宝蓝、灰蓝并存，等于每页各喊各的口号。
2. **两种字体声部，分工明确。**
   叙述文字走比例体；一切可对比数字（KPI、表格、金额、百分比）走 tabular 等宽声部，纵向对齐可扫。KPI 主值是全站"被读得最多的字"，当前反而最不受纪律约束。
3. **层级靠发丝线、留白与字重字阶，不靠阴影、渐变、圆角。**
   扁平色场 + 1px hairline 分区；深色页 panel→panel-2→panel-3 背景递进；阴影全 token 化并压到最轻一档。字阶建立层级（尺寸/字重/字距），不用颜色数量建立层级。
4. **状态即装饰。**
   状态圆点、徽标、语义色承载数据状态，是唯一被允许的"彩色"。任何无语义的彩色装饰（光斑、呼吸、渐变带）视为噪音移除。

---

## 3. 分阶段方案

> 每阶段独立可交付、可回滚；严格按照 AGENTS.md 分层：Phase 0–1 属 Tier 1（视觉收敛为主），Phase 2 跨 Tier 1/2，Phase 3 逐页 Tier 1。全程遵守 §9 Page Locks，不动区块顺序，不动任何业务口径。

### Phase 0 · 地基：token 单一来源（先行，无视觉变化目标）

| 项 | 内容 |
|---|---|
| 0.1 | ✅ 消 TS↔CSS 双源矛盾：`radius.sm`→2、shadow 四档压平、`--ib-rail-section-label`→`#6b7480`、`--moss-font-serif` 对齐 `ibTokens` |
| 0.2 | ✅ `--dh-api-*` 已在 tokens.css + designSystem.ts（先期完成） |
| 0.3 | ✅ AI 紫已清除。~~删除呼吸动效~~ → **业主拍板保留**（DESIGN.md §8 豁免 + 首页已恢复） |
| 0.4 | ✅ 字体名清扫：生产 CSS/TS 未托管字体名统一到 `--moss-font-*` / 系统栈（design-lab / docs 样稿不在范围） |
| 0.5 | ✅ reduced-motion：agent/stock 已有；本轮补 cross-asset `ca-pulse` / `ca-spin` |
| 0.6 | ✅ 浅色 module `.dhPage` → `.dhLightPage`；壳层深色 `.dhPage` 保留 |

**验证**：`debt:audit` 基线不升；1440×900 全页截图 diff 应为零或接近零；目标域测试。
**风险**：低。唯一视觉差异来自 0.3/0.4（移除紫色带与呼吸光、字体 fallback 链变化），需截图确认可接受。

### Phase 1 · 深色终端并轨：一页一主题，一套 dh-api

| 项 | 内容 | 状态 |
|---|---|---|
| 1.1 | 组合 / 市场 / 债券分析三页从 `#7dd3fc` 系切换到 dh-api 去饱和色阶（删除逐行复制的 palette 块） | 大体完成；债券页主色、语义色与蓝色透明阶已改由 `--dh-api-*` 派生，局部历史中性色仍待后续审计 |
| 1.2 | 股票分析页自建 `--sa-dh-*` 高饱和色板 → dh-api；移除 600px 装饰光斑 | ✅ 色板已桥接 dh-api；根节点 `::before/::after` 600px 装饰光斑已删 |
| 1.3 | 宏观工具箱主题拍板后归一（见 §4 决策点 D1） | ✅ 已锁浅色；`DESIGN.md` §2.2 已剔除宏观 |
| 1.4 | `/market-data` 首屏深色孤岛（见 §4 D2） | ✅ 拍板 c：岛保留；`--command-*` → `--dh-api-*` |
| 1.5 | 深色页衬线退出；深色圆角统一 6px；深色阴影按 §2.2 退出 | ✅ 主路径：shell/stock `--ib-serif→sans`；stock 去 600px 装饰光斑；刊头/ledger/queue-title 改 sans；债券/壳圆角阴影最小包已做。余量：壳内非主路径 box-shadow 长尾另批截图清理 |
| 1.6 | 深色页 KPI 主值接 tabular 栈，字阶收回 20–24px 区间 | ✅ 主路径：shell hero KPI / decision h3、risk/portfolio/bond metric、stock empty-signal 与刊头超大字已收回 ≤24（刊头 20）；余量逐页截图复核 |

**验证**：七页深色页截图对比（改动页需人工确认视觉差异符合预期）；`debt:audit` 基线应**下降**（palette 复制块删除）。
**风险**：中。1.1/1.2 是肉眼可见的色相变化（亮蓝 → 灰蓝），需产品确认；不改变任何数据。

### Phase 2 · 共享原语收口：一套卡片、一套 KPI、一套圆角

| 项 | 内容 | 状态 |
|---|---|---|
| 2.1 | 确立 page-v2 契约族（PagePrimitives）为唯一标准；DataSection / AsyncSection / SectionCard 标记弃用并迁移 48 个消费点（可分页面批次） | ✅ 主路径：`PageDataSection` / `PageAsyncSection` 桥保留 testid、文案与状态优先级；pnl-attribution、executive、Balance、FormalPnl、OperationsAnalysis 等安全消费点已迁。仅 `cashflow-projection` 因既有 WIP 冻结，旧组件本体/契约测试保留作兼容边界 |
| 2.2 | KpiCard 重建：token 驱动、主题感知（浅/深皆可用）、消灭 13 个内联 style 对象 | ✅ 布局/色阶迁入 `KpiCard.css`（`data-tone`）；sparkline stroke 仍读 displayTokens |
| 2.3 | 圆角锁落地：token 层删除 20px 档（displayTokens.radius.section），浅色全站 2px、深色 6px；154 处浅色大圆角批量收敛 | ✅ token+共享原语已锁；页面级 20px 长尾另批 |
| 2.4 | 修复 Skeletons.tsx 失效 Tailwind 类；skeleton 三份实现合一 | ✅ `SkeletonBars` 共享原语；AsyncSection/DataSection/Skeletons/DeferredSkeleton 已迁 |
| 2.5 | 组件层 20 处硬编码 hex 全部改引用 token | ✅ `components/**` 17 hex→0（CSS 9 + AccountingBasis 图 8）；图表色走 ibTokens/designTokens |

**验证**：每个迁移批次跑该域组件测试 + 页面截图；`debt:audit` 的 inline-style 基线应显著下降。
**风险**：中。迁移消费点时会触碰多页面文件，严格分批、每批可独立回滚；业务逻辑零改动。

### Phase 3 · 浅色长尾与毛坯页

| 项 | 内容 | 状态 |
|---|---|---|
| 3.1 | 4 个 antd 毛坯页（bond-dashboard / cube-query / platform-config / concentration-monitor）接入 IB token + page-v2 原语，消灭 inline style | ✅ 四页完成：PageHeader/EvidencePanel/PageStateSurface + 页面 module.css；bond-dashboard 19→4（余 ECharts 高度等功能性），concentration 19→0，cube/platform 旧 CSS 删除换 module.css；存量测试零弱化全绿 |
| 3.2 | 硬编码 hex 分区清扫（优先级：StockAnalysisPage.css 564 → MarketDataPage.css 476 → BalanceMovementAnalysisPage.css 289 → TeamPerformancePage.css 195） | ✅ 四个优先 CSS 均清零；Stock/Market 的历史页内 palette 已桥接 `--dh-api-*` / `--ib-*` |
| 3.3 | 538 处 10px 字体收敛到 §3 刻度（≥11px），KPI 标签两行 clamp 规则补齐 | 🔄 主路径已落地：① `KpiCard` 标签 `-webkit-line-clamp: 2` + native `title`（`KpiCard.css` / `KpiCard.tsx` + 契约测试）；② Stock/MarketData 与三 module-home CSS（`moduleWorkbenchHome` / `marketHome` / `riskOverview`）9–10.5px 已清零。仍待：MacroToolkit(~81)、ledger-pnl 簇、balanceWorkbench、BondAnalyticsInstitutionalCockpit、`dashboardCockpit` 死层等 |

**验证**：逐页截图 diff + 该页测试。
**本批验证（2026-07-20 · Stock/Market + bridge）**：定向测试 233/233；typecheck、build:fast、debt:audit 通过；两页 1440×900 截图复核无横向溢出。
**3.3 收尾核对（2026-07-20）**：`KpiCard` + `module-home` 定向 vitest **76/76**；`npm run typecheck` 通过；`debt:audit` + visual token audit 通过（hex 1467/2348）；`style:audit` 对 **本批 CSS/KpiCard** 无 workspace 门禁项——工作区整体 FAIL 来自无关未提交文件 `bondAnalyticsCockpitTokens.ts` 1 处 private shadow。人工截图（market/risk/module home）仍建议补一眼。
**风险**：低；字阶与标签截断为纯视觉，业务数据与指标路径未改。长尾清扫仍可能挤布局，需按页截图。

### Phase 4 · 死代码与级联战争清理（收尾）

- dashboardCockpit.css 死类摘除（191 类仅 40 活）、未定义变量引用清理
- `!important` 战争区（shell vs cockpit 互相压制）随死代码清理自然消解；StockAnalysisPage.css 的 2,303 个 `!important` 在 1.2/3.2 专项中同步收敛
- warm / cockpit 死调色板按 DESIGN §12 既定"visual-only"定位做引用清理
- 收尾时**下调 debt:audit 全部基线**，把本轮成果固化为新红线

---

## 4. 需要你拍板的决策点

| # | 决策 | 选项 | 我的建议 |
|---|---|---|---|
| D1 | 宏观工具箱归属 | a) 按 DESIGN §2.2 转深色终端；b) 承认浅色现状并修订 DESIGN | **b**——该页是工具表单型而非驾驶舱，浅色更合适；修订 DESIGN 比强转深色代价小 |
| D2 | market-data 首屏深色孤岛 | a) 整页转深色；b) command sheet 改浅色；c) **保留深色岛 + DESIGN 豁免** | **c（已拍板 2026-07-19）**——见 `DESIGN.md` §2.4；主体仍 IB；岛内收敛 `--dh-api-*`，不强制改浅色 |
| D6 | 现金流久期正缺口色 | a) `--ib-up`；b) `--ib-warn`；c) 中性墨色 | **c 为主、b 可强调（已拍板）**——正缺口禁绿；见 Decisions Log |
| D7 | 余额分析风险红 | a) 保留页内亮红；b) 收束 `--ib-down` | **b（已拍板）** |
| D3 | 深色页刊头衬线（经营日报大标题） | a) 保留（产品确认豁免 §3）；b) 改 sans | **b**——但需产品看一眼截图再定，它是首页最显眼的单点 |
| D4 | 组合/市场/债券/股票页 accent 色相变化 | 亮蓝系 → dh-api 灰蓝 `#72a7dc` | 执行，但先出 1 页样张（建议风险总览同源的经营日报做基准，组合页做首个迁移样张）确认 |
| D5 | 阶段排序 | 建议按 Phase 0→1→2→3→4；也可把 Phase 2.3 圆角锁提前到 Phase 1 后（视觉收益最快） | 圆角锁提前：它对"统一感"的肉眼收益最大、机械性最强 |

---

## 5. 明确不做什么（Scope Discipline）

- 不推翻 DESIGN.md 双主题体系，不引入第三套主题
- 不动 §9 Page Locks 的区块顺序，不动任何业务口径、adapter、metric 路径
- 不引入外链字体、新框架、新构建依赖
- 不做后端、数据库、状态架构改动
- 不做"一次性全仓替换"式大重构——每阶段独立 PR、独立可回滚

## 6. 全程验证纪律

- 每阶段：`npm run debt:audit`（基线只降不升）+ 相关域 lint/typecheck/test + 1440×900 截图基准对比
- Phase 0 要求"截图零差异"（除 0.3/0.4 已声明项）；Phase 1 起每页改动出前后对比样张
- 任何涉及业务指标展示的意外牵连，立即停下来按 Tier 2 流程走 metric-contract 证据链
