# Design tokens（MOSS-V3 实现入口）

本目录提供设计令牌和 Ant Design 主题映射。视觉政策、主题选择、圆角例外、业务色语义与动效要求以根目录 [DESIGN.md](../../../DESIGN.md) 为唯一权威；本文件只说明代码入口和使用方式。先复用已有 token，不在 feature 内另造色板。

## 核心文件

| 文件 | 作用 |
|------|------|
| `designSystem.ts` | `designTokens` 提供通用刻度，`nocturneTokens` 提供默认深色镜像，`ibTokens` / `dhApiTokens` 供相应兼容范围使用。 |
| `../styles/tokens.css` | CSS 变量、scope 色板和共享兼容映射。 |
| `themeScopes.ts` | `NOCTURNE_THEME_SCOPES` 与 `NocturneThemeScope`，和 CSS scope 清单同步。 |
| `tokens.ts` | `shellTokens` 历史浅色兼容别名，不是新深色页面的色板模板。 |
| `theme.ts` | `workbenchTheme` 使用 Nocturne，映射 `ConfigProvider` 的 token 和组件配置。 |
| `../utils/tone.ts` | `TONE_DH_CSS_VAR` 是深色 DOM 着色入口；`TONE_CSS_VAR` 保留 IB 浅色及既有兼容用途。 |
| `../components/charts/chartTheme.ts` | `nocturneChartTheme` 供深色图表复用，canvas 不读取 CSS 变量。 |

## 使用入口

深色 DOM 样式消费 `--dh-api-*`，不能读取 CSS 变量的消费方使用 `nocturneTokens`。盈亏、利率变动与风险方向的着色含义遵守 DESIGN §4.1，不通过选色反推业务含义。浅色 `designTokens.color.semantic` 不能直接用于深色页面。

通用间距、字号、行高、密度和动效仍由 `designTokens.space`、`fontSize`、`lineHeight`、`density`、`motion` 提供；存在某个刻度不代表每种页面都可使用。页面圆角、层级和动效按 DESIGN §5 / §8 选择，不将 `radius.sm/md/lg/xl` 自动当成面板层级，也不用阴影表达深色面板层次。

对比性数字复用 `designSystem.ts` 导出的 `tabularNumsStyle`。例如，主题目录内需要 JS 样式值的消费者可以这样取值；页面中的导入路径按其位置调整，重复布局仍放已有样式模块。

```ts
import { designTokens, nocturneTokens, tabularNumsStyle } from "./designSystem";

const numericStyle = { ...tabularNumsStyle, color: nocturneTokens.color.ink };
const panelRadius = nocturneTokens.radius;
const blockGap = designTokens.space[4];
```

表格密度以 `theme.ts` 的 `Table` 映射及 `designTokens.density` 为准，ag-grid 消费方复用相同刻度。新增 scope 的同步位置与检查要求见 DESIGN §10；不要复制页面级主题覆盖块。

## Ant Design 映射约定

- 根 `AppProviders` 只承载 API 与查询缓存上下文，不异步切换 Ant Design Provider，避免业务子树二次挂载。
- 首页和轻量工作台壳不挂载 Ant Design 主题，保持首屏启动链轻量。
- 非首页工作台路由通过懒加载的 `ThemedRouteBoundary` 一次性挂载 `ConfigProvider theme={workbenchTheme}`，业务页面首次显示时主题已就绪。
- **不要**在页面级再次包一层 `ConfigProvider` 改主色，除非该路由是隔离演示页，并且需要在文档中说明原因。
- Button / Input / Table / Card 的视觉以 `theme.ts` 为准；单独调某个按钮时先用 `type` / `danger` / `size`，再考虑 style。

## Style Governance Commands

检查范围按 [frontend/AGENTS.md](../../AGENTS.md) 和 DESIGN §10.1 选择，从 `frontend/` 运行相应命令。

- `npm run style:inventory` 提供迁移盘点，不是每次局部修改的必跑项。
- `npm run style:audit` 检查增量非 token 颜色及私有阴影，并提示内联样式、大圆角和数据状态面风险。
- `npm run debt:audit` 检查既有债务基线是否增长，不证明圆角变量解析值、路由例外和全部设计规则合规。

主题值或 scope 清单变化时运行相关 `theme.test.ts`；可见布局和状态按受影响范围做组件或浏览器核对。文档及仅注释改动使用轻量验证，不把本文件变成全量测试清单。
