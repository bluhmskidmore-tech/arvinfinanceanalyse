# Design System — MOSS V3

> 本文件是全站版式、配色、字体、密度与动效的**唯一权威**。改动任何界面外观前先读本文；数值以 `frontend/src/theme/designSystem.ts` 与 `frontend/src/styles/tokens.css` 为单一来源。QA 与代码审查中，明显违背本文的实现应被标出。

---

## 1. Product Context

- **What this is:** 面向机构固收与组合管理的业务工作台（经营日报、债券分析、风险、绩效、治理与报表），强调可读数字、可追踪口径与页面级闭环。
- **Who it's for:** 投资/交易、风控、经营与管理层——需要在统一界面里"先看结论、再下钻证据"的用户。
- **Project type:** 内部业务 Web 应用（重数据仪表与表格，**非营销站**）。营销页设计法则（Hero 规则、Bento、图片策略等）不适用；本文吸收的是通用审美纪律：一致性锁、降噪、状态语义化、文案自审。
- **North star:** 冷静、可审计。数字与单位一眼可辨；异常、缺口、兜底显式呈现，**不用装饰掩盖缺失数据**。

---

## 2. 主题体系（深色为默认）

项目现存两套视觉语言，但产品默认且最终收敛方向是**全系统深色机构终端**。**一页一主题，页内禁止混用或中途翻转**（Page Theme Lock）；IB 浅色仅用于尚未迁移的存量页面或经产品明确书面批准的例外，不再作为新页面或重做页面的默认方案。

### 2.1 IB 浅色工作台（受控例外 / 存量迁移）

纸感浅底 + 白卡 + 深藏青强调 + 深色侧栏。该体系保留用于兼容尚未完成迁移的页面；任何新增使用都必须记录路由、原因、批准人和退出条件。

| Token | 值 | 用途 |
|---|---|---|
| `--ib-paper` | `#f4f3f0` | 应用底 |
| `--ib-surface` / `--ib-surface-muted` | `#ffffff` / `#f7f6f3` | 卡片 / 次级面 |
| `--ib-hairline` | `#e2e0da` | 细分隔线 |
| `--ib-ink` / `--ib-ink-secondary` / `--ib-ink-muted` | `#16191d` / `#5c6370` / `#8a8f98` | 正文 / 次文 / 弱文 |
| `--ib-accent` (+hover/surface) | `#14366b` | 主强调、链接、主按钮 |
| `--ib-up` / `--ib-down` / `--ib-warn` | `#1f7a4d` / `#b42318` / `#b54708` | 语义色 |
| `--ib-rail-*` | `#10161f` 系 + 金条 `#c9a85c` | 左侧导航深栏 |
| `--ib-radius` | `2px` | 全局锐角卡片 |
| `--ib-serif` | Georgia / Noto Serif SC 栈 | 仅标题/刊头 |

### 2.2 深色机构终端（Decision Desk，全站默认）

用于全系统业务页面，包括经营日报、组合、债券、股票、市场数据、宏观、损益与治理工作流。近黑藏青底 + 分层面板 + **去饱和**冷强调。

> `/product-category-pnl` 已由产品确认锁定为深色完成版；不得用旧 IB 浅色实现或历史快照覆盖。现存浅色页面属于迁移债务，不构成后续设计权威。

| Token | 值 | 用途 |
|---|---|---|
| `--dh-api-bg` | `#070a12` | 页面底（非纯黑） |
| `--dh-api-panel` / `-2` / `-3` | `#0c1421` / `#101a2a` / `#132033` | 三层面板递进 |
| `--dh-api-line` / `-soft` | `rgba(103,119,142,.34/.22)` | 边线两级 |
| `--dh-api-ink` / `soft` / `muted` | `#e8eef7` / `#a9b6c7` / `#8593a8` | 文字三级 |
| `--dh-api-blue` | `#72a7dc` | 强调/链接（去饱和） |
| `--dh-api-green` / `amber` / `red` | `#66b98b` / `#c9a565` / `#d47a72` | 语义色（去饱和） |

**规则：**
- 深色页语义色必须用以上去饱和色阶，禁止把浅色主题的高饱和 `#ef4444`/`#2d8a5e` 直接搬进深色页。
- 面板层级靠 `panel → panel-2 → panel-3` 背景递进 + 细边线表达，**不靠阴影**（深色底上阴影无效且脏）。
- 页面主题由页面根容器一次性声明（token 重映射），子组件禁止各自覆盖主题变量。

### 2.3 选择规则

- 新页面、重做页面和恢复页面默认使用深色机构终端主题，并在页面根容器一次性声明 `theme-dh-api` 或其统一后继主题标记。
- IB 浅色只允许作为明确记录的临时兼容或产品例外；不得因旧文档、旧截图或旧提交把已确认的深色页面回退为浅色。
- `/product-category-pnl`、经营日报首页、组合首页、债券分析和股票分析均为已锁定深色路由。
- 同一路由树下的详情页/下钻页跟随其入口页主题，避免跳转时明暗闪切。

### 2.4 存量浅色迁移边界

| 项 | 约定 |
|---|---|
| **状态** | 仍为浅色的页面可以在迁移完成前继续运行，但不得作为新功能的视觉模板 |
| **改动规则** | 业务修复可保持现状；视觉重做、页面恢复或新增主要区块时应整页收敛到深色，不制造新的明暗拼接 |
| **Token** | 深色实现统一使用 `--dh-api-*` 或其后继全局 token；禁止扩张自制 `--command-*`、裸 navy hex 或第三套主题 |
| **例外记录** | 必须写明路由、批准人、批准日期、原因和退出条件；没有记录即按深色默认处理 |
| **验收口径** | 页面根主题标记、1440×900 截图和定向回归必须共同证明未发生浅色回退 |

---

## 3. Typography

- **UI/正文：** 本地系统栈 `PingFang SC / Microsoft YaHei UI / Noto Sans SC / Segoe UI`（`fontFamily.sans`）。**不引入外链展示字体**——内网可用性优先。
- **数字/KPI/表格：** 等宽栈（`fontFamily.tabular`）+ `font-variant-numeric: tabular-nums`。**所有对比性数字必须 tabular**，保证列对齐与变动可扫。
- **衬线（`--ib-serif`）：** 仅限 IB 浅色主题的页面刊头/大标题。深色终端页不用衬线。
- **Scale（px）：** 页标题 18–20；卡片标题 14–16；正文 13–14；辅助 11–12；KPI 主值 20–24。**数据行最小 12px**——便读性优先于塞满一屏。
- **多行标签对齐：** 同一横带内的 KPI/卡片标签统一 2 行 clamp（`-webkit-line-clamp: 2` + 固定 `min-height`），完整文案入 `title`。禁止因标签换行不一致导致同排数值错位。
- **大写宽字距徽标（GOV / FORMAL / ANALYTICAL / READY 等）：** 属既定终端语言，仅用于**状态/口径徽标**。禁止把它扩散为普通区块标题装饰；每个模块头最多一个。

---

## 4. Color

- **单一数值源：** `designSystem.ts`（`designTokens` + `ibTokens`）与 `tokens.css`。新色先入 token，禁止散落硬编码 hex。
- **浅色例外主题锚点：** 主色 `primary[600]` `#1850a1`（偏蓝少青）；链接/次强调 `info[500]` `#3b82f6`。仅供已登记的浅色例外或迁移中页面使用；新组件默认使用 2.2 的深色终端 token。
- **语义色统一：** `semantic.profit/up = #2d8a5e`、`loss/down = #ef4444`（浅色）；深色页用 2.2 的去饱和对应色。同一页面同一语义只允许一种色值。
- **Color Consistency Lock：** 页面级强调色一旦确定，全页统一。不允许第 7 个区块突然出现主题外的新强调色。
- **禁用：** AI 紫/霓虹渐变、纯黑 `#000` 大底、高饱和撞色、无语义的彩色装饰。
- **域内调色板（`cockpit` / `warm` / `institutional`）：** 可继续使用，但仅限视觉层（visual-only），不承载业务语义；新页面优先从 IB / dh-api 两套主色系取色，确有需要再引用域内调色板，并保持与所在页面主题的明暗与饱和度协调。

---

## 5. Spacing & Layout

- **Base unit:** 4px（`designTokens.space`）。页内垂直节奏用 8/12/16/24 组合；同一栅格行内卡片 padding 与 gap 必须一致。
- **Density:** compact 为主。深色终端页更紧（面板 padding 12–15px，行高 1.25–1.35）。
- **栅格：** 主内容 + 右栏布局用 `minmax(0, 1fr) + 固定右栏（320px 级）`；三列区大桌面 8-8-8，窄屏先折 12+12 再单栏，**禁止**压缩字号保列数。
- **不等高网格必须 `align-items: start`：** 多列卡片/新闻组内容量天然不等时，禁止默认 stretch 把空卡拉出大段空白（"空白比内容多"是版式事故）。左右双栏若追求齐底，用 `align-self: stretch` 让**卡片背景**补齐，而非留裸空白断层。
- **空态收缩：** 0 条数据的分组收缩到消息框自身高度（min-height ≤ 120px 级），居中一句话说明 + 原因，不占满等高格。
- **圆角一致性（Shape Lock）：** IB 主题全局 `2px` 锐角；深色终端页 `6px`。一页一套圆角制度，禁止混用大圆角"玩具感"卡片。
- **卡片使用纪律：** 仅当层级需要时才用卡片容器；同级信息优先用 `border-top` / `divide` / 留白分组。禁止"格子套格子"。

---

## 6. 状态与数据可信呈现

这是本系统区别于普通仪表盘的核心：**状态即内容**。

- **五态齐备：** 每个数据区块必须可感知 loading / 空 / 错 / stale / partial。无数据时禁止用演示数冒充正式口径。
- **占位防重排：** 懒加载区块的 Suspense 占位必须带与相邻面板一致的背板（背景+边线）和接近真实高度的 `min-height`，禁止 1px 占位导致内容到达时页面跳动。
- **缺值占位符：** 表格/指标缺值统一 `—`（金融惯例）。**同一缺失原因整列缺失时**，明细行用安静的 `—`，原因说明只在区块头部/汇总处出现一次——禁止把"缺 XXX"文案在每行重复。
- **状态圆点必须承载语义：** 圆点颜色 = 数据状态（通过/部分/缺口/延迟）。禁止纯装饰圆点。
- **状态信息去重：** 同一事实（如"数据已更新 04:40"）全页最多出现两处（工具条 + 底栏）。卡片内不再重复全局报告日；来源/口径细节（如 `home.snapshot`、basis 代码）收进 `title`/tooltip，不占正文版面。
- **溯源标识分层：** 端点路径、trace 类技术信息属于"证据层"，只出现在证据链/API 目录等专门模块，不散落到业务结论区。

---

## 7. 文案（Copy Register）

- **一页一语域：** 面向用户的文案统一**简体中文业务语言**。禁止中英混排的技术微标签（如 `coverage map · expanded landed domains`、`date-gated`、`domains landed`）——这类内容要么中文化，要么收进 tooltip，要么删除。
- **例外：** 既定大写状态徽标（GOV/FORMAL/READY 等）、接口路径、代码标识可保留英文，因为它们是"证据引用"而非叙述文案。
- **`·` 分隔符配额：** 单行元信息最多 1 个 `·`。超出时改分行、竖线分栏或删字段。
- **禁止微元句：** 区块标题旁不加"解释这个组件如何实现"的装饰性小字。标题 + 状态徽标已足够。
- **em-dash 禁令：** 叙述文案中不用 `—` 作修辞停顿（表格缺值占位 `—` 除外，见第 6 节）。
- **发布前自审：** 通读所有可见字符串，清除语法不通、指代不明、AI 味修辞的句子。宁要平实，不要"聪明但错"。

---

## 8. Motion

- **Approach:** minimal-functional。仅状态切换、折叠、Tab、路由过渡、hover/active 反馈。
- **无限循环装饰动效默认禁止**（扫光、网格漂移一类），**唯一豁免：经营日报首页 hero 的环境呼吸光**（`dhAmbientCanvasBreathe`，约 6.4s 缓慢透明度呼吸，无数据语义，业主 2026-07-19 拍板保留）。豁免仅限该处，不得扩散到其他页面或组件；`prefers-reduced-motion` 下必须完全静态或隐藏。
- **时长/曲线：** 用 `designTokens.motion`（fast 150ms hover / base 200ms 展开 / easeOut）。
- **必须尊重 `prefers-reduced-motion`：** 所有非 hover 动效在 reduce 下退化为静态。
- **滚动监听：** 禁止裸 `window.addEventListener("scroll")` 驱动动画；用 IntersectionObserver 或 idle-callback 门控（现有分级加载门控即此模式）。

---

## 9. Page Locks（区块顺序锁）

以下页面的信息区块顺序未经产品确认**不得调整**。

### 9.1 债券分析 / 组合工作台首页

1) 宏观市场条 → 2) 本日判断（结论文本+轻装饰）→ 3) 组合 KPI 横带 → 4) 三列：曲线与波动 | 四象策略 | 收益归因 → 5) 三列：结构/风险/今日焦点 → 6) 双列：事件日历 | 重点券表

### 9.2 经营日报首页（深色终端，2026-07 现状）

- **首屏：** 工具条（报告日/搜索/状态胶囊 ≤3 个/刷新）→ 早间决策一览（判断 hero + 来源核验）→ KPI 横带（规模/损益/久期/YTM，4 卡等高对齐）
- **下半屏（懒加载，带骨架占位）：** 宏观/日历上下文（左前瞻+过往、右政策资金面，双栏齐底）→ 市场/日历上下文 → 债券信息新闻（三组，空组收缩）→ 快捷下钻 → 重点券 + 风险暴露/增减仓 → 收益趋势 → 结构看板 → 券商研报 → 证据链路
- **右栏（320px）：** 待复核 → 待办事项 → 数据质量（含来源台账，一卡合并）
- **首屏问题：** "今日组合的可执行判断是什么、数据是否可信"，两问都必须在首屏可答。

---

## 10. Relationship to Code

- **数值单一来源：** `frontend/src/theme/designSystem.ts`（scale、语义色、motion）+ `frontend/src/styles/tokens.css`（CSS 变量）。域内扩展 token 需与本文语义一致。
- **正式金融指标：** 前端只消费后端/adapter 输出，不自行推导（与 `AGENTS.md`/`CLAUDE.md` 一致）。
- **全站版式契约（opt-in）：** 未在第 9 节锁定顺序的页面，以 [`docs/frontend-layout-contract.md`](docs/frontend-layout-contract.md) 为默认骨架。
- **验收工具：** 改动版式后跑 `npm run test`（相关域）、`npm run debt:audit`、浏览器 1440×900 基准截图对比；不等高网格、状态去重、文案语域属于审查必查项。

---

## 11. Anti-Patterns（一票否决清单）

1. 页内主题翻转（浅色页中插深色区块，反之亦然）；存量浅色页必须按整页边界迁移
2. 等高 stretch 造成的空卡大留白；左右栏裸空白断层
3. 同一状态文案在页面 3 处以上重复；每行重复同一缺失原因
4. 无限循环装饰动效（§8 已豁免的首页 hero 呼吸光除外）；不尊重 reduced-motion
5. 中英混排技术微标签出现在业务叙述位
6. 单行 2 个以上 `·`；区块标题旁的装饰性微元句
7. 高饱和语义色直接用于深色终端页
8. 无语义装饰圆点；AI 紫渐变；纯黑大底
9. KPI 标签换行导致同排数值错位
10. 1px 懒加载占位造成内容到达时重排
11. 用随机演示数据冒充正式口径

---

## 12. Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-04-27 | 引入根目录 DESIGN.md，债券分析页以完稿为权威 ±5% | 统一协作与实现验收 |
| 2026-04-27 | 延续系统字体栈，不强制外联展示字体 | 内网可用性，减少加载变量 |
| 2026-05-29 | 经营驾驶舱首页改为分层卡片+更大留白 | 解决格子套格子拥挤感 |
| 2026-06-12 | 引入 IB 浅色 restyle（ibTokens：纸底/深栏/衬线刊头/2px 锐角） | 机构感统一视觉语言 |
| 2026-07-07 | 全文重写：正式承认「IB 浅色 + 深色终端」双主题体系并各自定 token 权威；新增状态呈现、文案语域、防重排、反模式清单 | 旧文档只覆盖浅色体系，与首页深色终端现状脱节；沉淀本轮首页整改（KPI 对齐、状态去重、动效移除、空态收缩、中文化）为可审查标准 |
| 2026-07-07 | `cockpit`/`warm`/`institutional` 域内调色板继续保留使用，定位为 visual-only；新页面优先 IB / dh-api 取色 | 存量页面依赖广，强制冻结成本高；以"优先级引导"代替"禁令" |
| 2026-07-19 | 经营日报首页 hero 呼吸光（`dhAmbientCanvasBreathe`）由"违规待删"改为**正式豁免保留** | 业主明确表态喜欢该动效；限定单点豁免 + reduced-motion 静态化，避免禁令被整体架空 |
| 2026-07-19 | `/market-data` 首屏 command sheet **保留深色岛**（§2.4）；主体仍 IB 浅色；深色岛收口到 `--dh-api-*` | 业主拍板保留交易终端扫读锚点；用书面单点豁免代替"整页改浅/整页改深"；禁止自制第三套深色 palette 扩散 |
| 2026-07-19 | 现金流页久期缺口色：正缺口**禁止**映射 `--ib-up`；默认中性次级墨色（`--ib-ink-secondary`），结构偏离需强调时用 `--ib-warn`；负缺口可用 `--ib-down` 仅标方向 | ALM 正缺口≠经营利好；避免绿=好误导；业主采纳评估推荐 |
| 2026-07-19 | 余额分析风险/告警红由页内亮红（如 `#c5162e`）**收束到 `--ib-down`** | 浅色页语义色统一走 IB；业主采纳评估推荐 |
| 2026-07-19 | 宏观工具箱从 §2.2 深色名单移除，保持 IB 浅色 | 工具表单型非驾驶舱；与全局统一方案 D1-b 一致 |
| 2026-08-09 | 全系统视觉默认与最终收敛方向改为深色机构终端；IB 浅色降级为受控例外 / 存量迁移状态；`/product-category-pnl` 锁定深色完成版 | 业主最新确认“全系都应该是深色系”；防止旧设计文档或历史浅色快照再次覆盖已验收页面。此前与本条冲突的浅色默认、宏观浅色和市场数据深色岛决定均视为历史记录，不再作为当前实现权威 |
| 2026-08-11 | 视觉 token 审计基线 `tokens.css` 105→106、`designSystem.ts` 203→205：承认 8-09 深色收敛新增的 `--ib-accent-hover` 深色重映射 token，并把 `theme.ts` 链接 hover/active 裸 hex 收敛为 `dhApiTokens.color.blueHover/blueActive`（theme.ts 归零）；经营日报延迟区块 14 处 8/5/4px 圆角按 Shape Lock 归一为 `var(--dh-api-radius)` / 2px | 8-09 “restore dark route foundation / confirmed option two” 两笔提交未跑视觉审计即落库；新 token 属业主拍板的深色收敛产物，且 §10 规定数值单一来源就在 tokens.css/designSystem.ts，故基线在这两个 token 权威文件上抬升；散落页面里的 hex 与偏格圆角按 §4/§5 收敛而非放宽基线 |
| 2026-08-12 | 经营日报首页数据功能五件套（归因徽标 / Top5 集中度 / 超额方向色 / 各期限 DV01 条 / 待复核事项预览）的**二轮评审修复**：DV01 条全量展示后端固定 9 桶（此前 slice(0,8) 静默丢 30Y 长端），条宽计算入 view builder、无数值桶不画最小条；KRD 与事项预览的 loading/error/stale 以行内状态行露出（§6 五态，empty 仍收缩）、事项读取失败时不再落入「暂无治理待办」空文案；风险概览用 Top5 集中度**替换**与首屏 KPI 带完全重复的 DV01 格（§6 去重，保持 5 格避免窄面板数值截断）；事项预览来源标注「余额分析台账 · 截至日期」只在首行出现、次行显示行级事由（§6 去重）；徽标与 KRD 数值 11→12px（§3 数据行底线）；900-1024 断点隐藏归因徽标行保住「进入专题页」链接（92px 预算内被 overflow 裁切）；`data-tone="flat"` 补 muted 样式 | 十人评审后业主要求「再次 review」；五名专项评审（业务口径/React/架构/设计合规/视觉走查）发现 30Y 丢桶属业务正确性缺陷、静默吞态违反 §6、DV01 格重复违反 §6 去重；同轮完成 KRD 客户端注册进 homeSupplementalClient（首页轻量 chunk 架构）与余额日期查询 key 补 mode 维度 |
| 2026-08-12 | 经营日报首页 Nocturne 换肤的**配套排版与微交互**（同日实施，补记范围）：支撑带三面板等高对齐（40px 头线 / 28px 次行线 / 底边齐平、内部行均分）、英文眉标删除、覆盖计数收纳为行内徽标、长政策说明收进行级 title；KPI sparkline（无真实 history 不画线，禁用常数兜底序列）、KPI 变动色按数值符号取向（warning 保留琥珀）、组合透视分布微条（行底 2px）、国债收益率期限小图（按 1/3/5/10 年真实比例定位）、收益趋势标题走势线；懒加载区块一次性入场显现、KPI 数字滚动（900ms，测试与 reduced-motion 直显终值）、刷新旋转指示与 toast；持仓抽屉 portal 补 `data-moss-theme-scope` 防主题逃逸；十人评审后修复：导航壳背景 `!important` 压制、900-1024 断点隐藏 KPI 走势线、分布行 11px/数值 12px、工具栏控件 10→11px、负零变动归中性 | 业主要求 review+优化后落地；「仅换肤」原记录范围失真，按审计要求补记；假走势线违反 §6「禁止演示数冒充」故一并修正 |
| 2026-08-11 | 经营日报首页采纳 **Nocturne 换肤（仅换肤，不动版式）**：页面与所属工作台外壳切换为 Nocturne 色板（底 `#161826`、卡面 `#232532`、描边 `#3f424d`、唯一强调蓝紫 `#9184d9`、低饱和绿 `#5abd99` / 红 `#d97b6c`（自 `#de8577` 加深一档与琥珀拉开） / 琥珀 `#d5b26e`），`--dh-api-radius` 页面级重映射为 8px；**涨跌色统一为绿涨红跌**（`up/ok`=绿、`down/bad`=红，KPI 变动/收益率曲线/资金利率行翻转，持仓变动矩阵原本即绿增红减不变）；色板唯一定义入 `tokens.css` 的 `[data-moss-theme-scope="dashboard-home"]` 块（含 shell grid `:has()` 作用域），页面模块 CSS 全部走 `--nct-*`/`--dh-api-*` 引用；tokens.css hex 基线 106→122 | 业主 2026-08-11 确认设计交接包「三个布局方向设计评审」（Nocturne 三方向）为首页视觉参考并选定 1a 方向色彩语言，同时明确**首屏排版布局保持现状不重构**；换肤同步消除同页两套涨跌色冲突（原 KPI `up→红/down→绿` 与持仓矩阵 `增→绿/减→红` 同屏相悖，违反 §4 Color Consistency Lock）；蓝紫 accent `#9184d9` 为业主单点批准的低饱和蓝紫，不解除 §4 对高饱和 AI 紫（audit FORBIDDEN 列表）的禁令，其他页面不得自行引用；8px 圆角属 Nocturne 圆角制度、页内统一，符合 §5 一页一套圆角 |
| 2026-08-12 | 总账损益 `/ledger-pnl` 按业主指示照首页 Nocturne 标准实现：`tokens.css` 与 `workbenchDeferredChrome.css` 均以选择器别名扩展到 `[data-moss-theme-scope="ledger-pnl"]`（**无新增色值**，铬件块与 macro-toolkit 共用）；页根声明 scope + `theme-dh-api`，两个 antd 抽屉补同一 scope 防主题逃逸，深色 owner 仍由 `ThemedRouteBoundary` 独占（页根重复声明 `data-moss-theme="dark"` 会让 `live-route-dark-theme` 判定出两个 owner）；7 个样式文件约 371 处 `--ib-*` 直接改走 `--dh-api-*`（`--ib-*` 在路由边界即被算成钢蓝字面值再继承，Nocturne scope 翻不动），77 处 `var(--ib-radius, 2px)`、2 处 `--ib-radius, 6px`、3 处 `--moss-radius-sm`、8 处 pill `999px` 归一为 `var(--dh-api-radius)`（8px），24px 数字圆标改 `50%`，候选面板装饰性 3px 顶条删除、满饱和强调块换软底+强调描边；页标题 32→20px、副文 15→12px、模式徽标去大写宽字距，工具条改 32px 控件并把口径说明移出 label（原先塞在 label 内把两个下拉基线顶歪）；9 个章节统一编号分区头（CSS counter + 眉标 + 发丝线 + 五态状态位）并补 `scroll-margin-top`；KPI 由五张独立卡改单框五格等高横带（发丝竖分割、等宽数值、标签 2 行 clamp、1280/720 断点），表体 12px / 表头 11px / 发丝底边 / 数值右对齐走等宽栈；**功能审计结论从页底移到首屏 01「当日结论」**并入章节导航；后端枚举中文化（`ready · candidate` → `可用 · 候选口径`，未登记枚举原样透出）；补展示 `/api/ledger-pnl/data` 已返回但页面未用的 `summary.total_pnl`/`count`（按 `data_status` 收敛，避免把后端补零当真零） | 业主 2026-08-12 指示「按首页标准实现」，路径沿用同日 macro-toolkit 已验收的 scope 别名方案；首屏结论上移落实 §9「首屏一问」与 `frontend/AGENTS.md`「主结论首屏可见」；KPI 卡上 `MTR-LPN-001 / pending_confirmation=true` 经业主同意**保留可见**仅做视觉降权（`LedgerPnlPage.test.tsx` 断言其为治理必显项），未收进 tooltip；同轮修掉两处既有缺陷——`LedgerPnlSectionNav.css` 的 `--dh-api-ink-muted` 变量名不存在导致徽标色声明整条失效、章节锚点缺 `scroll-margin-top` 致跳转被粘顶导航压住。验收：视觉 token 审计 passed（无基线增长，off-radius 179/225），`live-route-dark-theme` 的 `ledger-pnl` 通过，`LedgerPnl` 301 测试通过 |
| 2026-08-12 | 宏观工具 `/macro-toolkit`、`/macro-observation`（同组件）按业主指示照首页 Nocturne 语言重构：`tokens.css` Nocturne scope 以选择器别名扩展到 `[data-moss-theme-scope="macro-toolkit"]`（无新增色值），页面 CSS 收敛旧 dh-api 钢蓝 rgba 软色与浅色遗产（白色半透明底、浅色 palette-step、白内阴影）到 var/color-mix 链，圆角随 `--dh-api-radius`（8px），分区头对齐首页编号语言（CSS counter 01/02…+ 眉标 + 发丝线），KPI/表格按首页密度纪律收口，antd Tag/主按钮/开关强调色翻至 Nocturne 语义链，装饰性彩色左条删除、状态语义条统一 2px 并保持绿涨红跌语义 | 业主 2026-08-09 确认全系统深色收敛方向、2026-08-12 指示宏观工具照首页重塑；2026-07-19「宏观工具箱保持 IB 浅色」决定按 2026-08-09 条目降级为历史记录 |
| 2026-08-12 | 组合工作台 `/portfolio` 按业主指示跟进首页 Nocturne 换肤（**仅换视觉层**，不动布局几何/DOM 结构/styles.* 类名/testid）：`tokens.css` Nocturne scope 以选择器别名扩展到 `[data-moss-theme-scope="portfolio-home"]`（无新增色值）；因该路由深色 owner 为 `ThemedRouteBoundary`，钢蓝基准块以 `.workbench-shell-grid:has(.themed-route-boundary.theme-dh-api)`（0-3-0）在外壳上定义 `--dh-api-*`，同块追加同权后置的 `.workbench-shell-grid.workbench-shell-grid:has(...)` 提权别名行外壳才翻得动；页内 V3 皮肤块删除全部 `--dh-api-*` 钢蓝字面量与页底 radial 渐变（数值唯一来源回归 tokens.css scope），约 160 处 rgba/rgb 字面量按语义家族收敛为 `--dh-api-*` 的 var/color-mix 链（文件 rgba/rgb 归零），13 处硬编码 6px 圆角归一 `var(--dh-api-radius)`（8px）；卡片制度由「微蓝渐变 + 蓝光边 + 内阴影」降级为首页平卡语言（`--dh-api-line` 描边 + panel 平底 + 无阴影，hover 描边 accent 34% mix），嵌套深底面板走 panel-2/panel-3 mix；ECharts 走新增 `nocturneTokens` 常量组（`designSystem.ts`，数值源=tokens.css Nocturne scope，仅供 canvas 类消费），结构条形图与归因瀑布切换取色；激活 ant-tabs 文字被 antd cssinjs（0-4-0、注入靠后）压住，页内以重复类 0-5-0 收敛至 accent；`designSystem.ts` hex 基线 205→221（nocturneTokens 16 个 hex 镜像，因并行任务在途仅手工上抬本文件条目，未全量重写基线） | 业主 2026-08-12 指示组合页跟进 Nocturne；换肤前后 Playwright 几何审计同态对比 8 横带 + 11 代表卡 rect/cols/gap/padding 全等、docH 不变、无横向溢出，布局零变化有据；页根不重复声明 `data-moss-theme="dark"`（避免 `live-route-dark-theme` 双 owner），沿用 ledger-pnl 同款 scope 别名路径 |
| 2026-08-12 | 市场总览 `/market-overview` 按业主指示照首页 Nocturne 排版标准**重做**：`tokens.css` Nocturne scope 以选择器别名扩展到 `[data-moss-theme-scope="market-overview"]`（无新增色值）；移除 `dhLightPage` 浅色残留，工具栏/组内子导航/章节导航对齐首页 dhTopbar 语言，01-04 编号分区头统一（CSS counter + 眉标 + 发丝线），行情带由独立卡改首页同款 KPI 单框横带（发丝竖分割、等宽数值）；ECharts 色板改运行时注入（`readCssVar` 读取 scope 内 `--nct-*` 计算值，jsdom 无布局环境回退静态值），tone 业务语义保留（利率上行=警戒琥珀而非涨绿，与 §4 语义色纪律一致）；外壳钢蓝烘焙以页内三写类名 + `!important` 直引 `--nct-*` 压制（网格底/rail/rail-mark/主列 main/导航 hover 与 active 高亮） | 业主 2026-08-12 指示「按照首页的排版布局来做」；验收：定向 Vitest 209 项、Playwright smoke 与 `live-route-dark-theme`、typecheck 通过，视觉 token 审计无基线增长；提交 2b219aca |
| 2026-08-12 | Nocturne 路由外壳统一收口：实测发现 `workbenchShell.css` 的 §Dark terminal 块以 `.workbench-shell-grid:has(.themed-route-boundary.theme-dh-api)`（0-3-0）+ `!important` 把钢蓝渐变**烘焙**在外壳网格/rail/主列上，且 `tokens.css` 钢蓝基准块以同选择器在外壳上定义 `--dh-api-*`，导致 scope 别名（0-2-0）对外壳**静默失效**——除已逐页压制的 dashboard-home / portfolio-home / market-overview 外，其余 8 条已接入 Nocturne 的路由（`/macro-toolkit`、`/macro-observation`、`/ledger-pnl`、`/average-balance`、`/positions`、`/bond-dashboard`、`/liability-analytics`、`/bank-ledger-dashboard`，Playwright computed-style 探测确认 grid/rail/main/终端条全部仍为钢蓝）外壳一直是钢蓝近黑（与 Nocturne rail 肉眼难辨）。修复取**统一收口**而非逐页复制 market-overview 压制块：① `tokens.css` 三个 Nocturne 别名块的外壳选择器统一双写类名升权至 0-3-0（portfolio-home 先例推广到全部 scope），变量翻转即自动修复主列纸面、终端条与非 cockpit 路由的 rail hover/active（cockpit 壳 `/`、`/portfolio` 的激活态另有 0-4-0 `!important` 金蓝烘焙，两页已按各自页内制度验收，不在本次范围）；② `workbenchShell.css` 末尾新增「Nocturne 外壳统一收口」终层压制变量触不到的烘焙渐变（网格 radial 提亮层、rail 98% 不透明钢蓝渐变、institutional-console 金蓝装饰），终端条钢青装饰层按启动性能守卫压在 `workbenchDeferredChrome.css` 末尾分册；值全部引用 `--nct-*`、特异性与 `!important` 对齐烘焙规则并后置、不依赖动态 import 注入顺序。其中 rail-mark 一条对非 cockpit 路由是把 `transparent` 基线改为 Nocturne 实面的**视觉决定**（对齐 market-overview 验收观感），cockpit 壳（dashboard-home / portfolio-home）的 rail-mark 保持透明制度不入列表；页内既有压制块 portfolio-home / market-overview 特异性更高且取值等价保留不动，dashboard-home 页内块（0-3-0 无 `!important`）由终层接管、取值同为 Nocturne 色板。**新增 Nocturne scope 时共四处**：tokens.css 主色板/paper 别名块与终层三条选择器列表各加一行；若该路由渲染终端条（`showShellTerminalBar`），tokens.css 终端条块与 `workbenchDeferredChrome.css` 分册再各加一行（`theme.test.ts` 有列表 parity 断言护栏）。已知残留：page-v2 面板烘焙（`.moss-page-v2-*`）不在本次范围，`/positions` 首屏结论块仍为钢蓝渐变，待后续收口 | 逐页复制压制块会让 10 个 scope × 4 条规则漂移且新路由必然重蹈覆辙，统一层一处收口；非 Nocturne 深色路由（`/risk-overview`、`/risk-tensor` 对照实测）钢蓝外壳保持原样；验收：13 路由探测对照全数翻转/保持、修复路由 1440×900 截图无明暗拼接、`WorkbenchShell`/`liveRoute` Vitest 91 项、`live-route-dark-theme` 全量、lint/typecheck 通过、视觉 token 审计无基线增长；三模型（Opus/GPT/Grok）交叉审查后按共识修正 rail-mark 列表、维护指引与本条措辞 |
| 2026-08-13 | Nocturne 外壳收口**两项已知残留修复**（承接上条）：① page-v2 面板烘焙——`workbenchShell.css` §83-94 以 0-4-0 `!important` 把钢蓝渐变 `linear-gradient(rgba(16,26,42,.98), rgba(12,20,33,.98))` 与结论左边线 `rgba(114,167,220,.72)` 烘焙在 `.moss-page-v2-surface / -evidence-panel / -decision-hero__conclusion` 上（`/positions` 首屏结论块实测确认）；收口终层追加两条压制：背景压平 `var(--nct-surface)`、结论左边线 `var(--nct-accent)`，烘焙里的 `border-color: var(--dh-api-line)` 与 `box-shadow: none` 经变量翻转已是 Nocturne 值（实测 border 为 `--nct-ring`）不重复声明；scope 列表与 grid/rail 同构全量 10 条（未渲染 page-v2 类的路由 `:has()` 命中但零效果，保 parity 可断言），`:is()` 合并三类目标维持 0-4-0 同权后置。② cockpit 壳 rail hover/active 金蓝烘焙（§cockpit 0-4-0 `!important`）——**实测定性分化**：`/portfolio` 激活项仍金蓝（金蓝渐变 + 金描边 + `inset 3px 0 0 rgba(201,165,101,.84)`）、hover 仍钢蓝 `rgba(114,167,220,.08)`；`/`（dashboard-home）已被页内 0-5-0 `!important` 块（dashboardHomeOptionTwo）接管为蓝紫、`/market-overview`（`isModuleHomePage` 亦走 `--cockpit` 变体壳）由页内 0-6-0 块等值接管，均无视觉缺陷；终层以同权 0-4-0 后置补压**三个 cockpit scope 全列兜底**（防止将来按「终层唯一权威」清理页内块时金蓝烘焙静默回归），实际生效目标是无页内块的 `/portfolio`。取值：hover accent 9%/22% 与 active accent 14% + `inset 2px 0 0 var(--nct-accent)` 对齐 tokens.css `--moss-shell-rail-active-bg` / `--moss-shadow-institutional-active` 语义，active 边线 30% mix 沿用 market-overview 验收块先例。`theme.test.ts` parity 断言同步：page-v2 背景与结论左边线两列表 = palette 全量、cockpit hover/active 两列表 = 三个 cockpit scope；`nocturneScopeSet` 增加可选选择器过滤（rail-mark 与 page-v2 背景压制 body 声明相同，按选择器区分），三模型（Opus/GPT/Grok）交叉审查全 PASS 后按建议补 market-overview 兜底行与结论列表选择器过滤 | 上条 45e00032 收口时明确记录的两项已知残留；延续「统一终层、值全引 `--nct-*` 不新增色值、特异性与 `!important` 对齐烘焙并后置」制度，不动 tokens.css 与页内既有压制块。验收：Playwright computed-style 修前/修后对比——`/positions` 结论块由钢蓝渐变+钢蓝左边线翻为 `#232532` 平底 + `#9184d9` 左边线，`/` 激活态修前后完全不变（accent 13% + inset 2px），`/portfolio` 激活/hover 翻为 accent 链，非 Nocturne 深色对照 `/pnl-by-business` 的 page-v2 钢蓝烘焙保持原样；`/positions` 1440×900 截图无明暗拼接；theme+WorkbenchShell 定向 Vitest 102 项、typecheck 通过；debt:audit 本次触碰文件零增长（`theme.test.ts` hex 15>基线14 为 HEAD 既有欠账，本次 diff 无 hex） |
| 2026-08-13 | 股票分析 `/stock-analysis` 按业主指示照首页 Nocturne 色系换肤（**仅换色，不动版式**）：`tokens.css` 主色板/paper 别名块以选择器别名扩展到 `[data-moss-theme-scope="stock-analysis"]`（无新增色值；不渲染终端条故终端条块不加），收口终层 grid/rail/rail-mark/page-v2 背景/结论边线五条列表各加一行，cockpit hover/active 兜底列表扩为四 scope（该页 `isStockAnalysisMinimalShell` 走 `--cockpit` 变体壳，金蓝烘焙实测命中）；**scope 声明三处**——`MarketWorkbenchFrame` 新增可选 `themeScope` 透传（frame 顶栏/子导航不在页根子树，scope 须落在 frame 根；market-data 不传零影响）、页根 `<section>` 同元素补声明（页根自带 `theme-dh-api` 类，同元素钢蓝基准块会挡掉从 frame 继承的翻转值，靠 tokens.css 源序覆盖，ledger-pnl 同款）、复核助手抽屉 body 与个股抽屉 antd panel 各补 scope 防 portal 主题逃逸；`StockAnalysisPage.css` 68 处 rgba 字面量按语义家族收敛为 `--dh-api-*` 的 var/color-mix 链（文件 rgba 归零：钢蓝/亮蓝/浅色主色 `rgba(24,80,161)` 收敛到 accent，tailwind 红琥珀与暗语义实底收敛到 red/amber/green mix，白色系收敛到 ink mix，白色 72% 实底列表项改 `--sa-dh-card-soft`），共享骨架 `dhCard:hover` 钢蓝字面量以页内升权覆盖为 accent 34% mix（对齐首页 hover 制度）；`stockAnalysisTokens.ts` 内联 `#93bfff` / 白 18% 改 var/color-mix 链；ECharts 取色（`stockChartPalette` 与个股抽屉 K 线）由 `dhApiTokens` 钢蓝常量切到 `nocturneTokens` 常量组（canvas 无法消费 CSS 变量，组合工作台先例）；`theme.test.ts` cockpit 两断言扩为四 scope，`StockAnalysisChartModel` / `StockDetailDrawer` 色值断言同步切源 | 业主 2026-08-13 指示「/stock-analysis 色系风格与首页一致」，沿用 scope 别名 + 终层收口既定路径（决议 2026-08-12「新增 scope 共四处」维护指引）；验收：浏览器 computed-style 探测外壳网格 `#161826`、rail `#131522`、frame 顶栏与卡面 `#232532`、页根 `--dh-api-bg #161826` / radius 8px、rail 激活项 accent 14% + `inset 2px 0 0 #9184d9`、个股抽屉 panel `#161826`，首屏/中部/抽屉截图与首页对照同色系无明暗拼接；theme parity 37 项、StockDetailDrawer/WorkbenchShell/PageChrome 等定向 Vitest、eslint、typecheck 通过，视觉 token 审计本次触碰文件零增长；`StockAnalysisPage.test.tsx` 4 例失败经 diff 归因为并行会话对 `marketDataClient.ts` 的在途重构（choice_stock 刷新链路），与本次换肤无关 |
| 2026-08-13 | 利率风险总览 `/risk-overview` 按业主指示照首页 Nocturne 排版标准重做：`tokens.css` scope 别名扩展到 `[data-moss-theme-scope="risk-overview"]`（无新增色值；终端条两处不加——`isModuleHomePage` 不渲染终端条），收口终层五条列表与 cockpit hover/active 补 risk-overview 行（该页亦走 `--cockpit` 变体壳；2026-08-12 收口条目中「`/risk-overview` 钢蓝外壳保持原样」的对照定位自本条起失效）；页根挂载的 `dhApiBackedHome`（dashboardHomeShell）以钢蓝字面量重写 `--dh-api-line/line-soft/*-soft` 6 个变量压掉 scope 别名，页内以 `.roV6Scope` 三写（0-3-0）变量压制块拉回 `--nct-*` 链；共享壳 `dhRefreshBtn`/`dhRailCard`/下钻行的钢蓝 rgba 硬编码不走变量、变量压制翻不动，以 TSX 本地皮肤类 + 三写前缀高特异性覆盖（平卡 + accent hover，撤钢蓝光带织纹与金→钢蓝渐变圆点）；工具栏收敛首页 dhTopbar 语言（`risk-overview-toolbar`），01-04 节题统一编号件，8 卡 KPI 改单框横带（等高分格 / 发丝竖缝 / 等宽数字 / 标签 2 行 clamp），999px 胶囊与偏格圆角归一 `var(--dh-api-radius)`（语义圆点除外），表体 12px / 表头 11px；1280 断点不降 KPI 字号（§3 主值下限 20px，本页格宽足够，首页同断点降号先例不复用）；「Drill-down」英文眉标删除、「血缘 · LINEAGE」中文化、03 节题 meta `·` 超配额改斜杠（§7）；缺值占位字面量归一 EM_DASH（riskHomeAdapter 的 `"-"` 与页面 `"—"`）；英文 disclosure 原文零改动、容器由截断改完整可见；风险警戒琥珀/红语义保留，未译作涨跌语义 | 业主 2026-08-13 指示按 market-overview 同套方案重做；三模型（Opus/GPT/Grok）交叉审查：GPT 运行态实测抓到共享壳钢蓝残留（刷新钮 `rgba(13,23,40)`、卡 hover `rgba(114,167,220)`）与 1280 断点 KPI 实测 18.56px 违反 §3 下限，Opus 抓到 riskHomeAdapter 漏列提交集与本条目缺失，均已修复并复测（按钮/卡默认与 hover 全部翻 Nocturne 链、1280 实测 20px）。验收：theme/WorkbenchShell/RiskOverview/riskHome/ModuleWorkbenchHome 297 项 Vitest（含新增 scope 声明与工具栏断言）、`risk-overview-desktop-layout` 10/10（几何锁无需改）、`live-route-dark-theme`、typecheck 通过；debt:audit 本任务文件无基线增长；scope 共享行随并行任务提交 98f190d0 先行入库，本条对应页面实现提交 |
