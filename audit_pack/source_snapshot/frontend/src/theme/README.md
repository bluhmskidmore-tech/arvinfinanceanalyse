# Design tokens（MOSS-V3 前端基线）

本目录定义工作台壳层与业务页共用的**设计令牌**与 **Ant Design 主题映射**。后续子代理在单页交付时，应优先复用这里，而不是在 feature 内再发明一套色值/间距。

## 核心文件

| 文件 | 作用 |
|------|------|
| `designSystem.ts` | 正式 scale：色阶 9 级、间距、字号、圆角、阴影、密度、动效、金融语义色。 |
| `tokens.ts` | `shellTokens`：历史兼容别名，供 `WorkbenchShell`、旧页面等 import。新代码可直用 `designSystem.ts`。 |
| `theme.ts` | `workbenchTheme`：`ConfigProvider` 的 `token` + `components` 覆盖。 |

## 颜色：何时用哪一级

- **主色 `color.primary.*`**：品牌/主操作、关键链接、强调边框。首屏结论区 eyebrow、与主品牌一致的点缀。
- **功能色 `success` / `warning` / `danger` / `info`**：AntD Tag、Alert、`KpiCard` 的语义状态。不要用功能色充当大面积背景（用对应的 `neutral` / 浅软底）。
- **中性灰 `neutral.*`**：正文、次级说明、分割线、卡片边框。大屏表格表头默认用 `neutral[600]` 弱化。
- **金融语义 `semantic`**：**仅用于数值正负与涨跌含义**——`profit`/`loss`、`up`/`down`。不要用语义色替换功能色 Alert（二者语汇不同）。
- **领域特例**：债券驾驶舱等模块可有局部 token 文件（如 `bondAnalyticsCockpitTokens`）；与全局冲突时，以本基线为准做收敛。

## 间距与卡片

- 使用 `designTokens.space[1]`…`[10]`（4px base）。页面块级间距优先 **16（`space[4]`）或 24（`space[6]`）**。
- 卡片：`designTokens.card.padding` / `gap` 与 AntD Card 已在 `theme.ts` 对齐；不要将随机 `margin: 14` 散落到页面。

## 字号与数字

- 正文 **13**，副文 **12**，页标题级差见 `designTokens.fontSize`。
- **tabular-nums**：表格金额列、KPI 网格、并排对比数值。标签句中文句子不必强制 monospace。
- 如需强对齐金额列，可在容器上设 `fontVariantNumeric: "tabular-nums"`（见 `tabularNumsStyle`）。

## 表格密度

- **紧凑 28 / 标准 36 / 舒适 44**（行高语义）。当前 AntD Table 默认值按「标准」在 `theme.ts` 配置了 `cellPaddingBlock`/`cellFontSize`。
- ag-grid 若单独使用：在列定义层跟同一套数值，不要在页面写死像素。

## 圆角与阴影

- **sm/md/lg/xl**：控件与卡片层级递增。工作台大面板可用 `tokens.shadowPanel`（较重 lift）。
- **shadow.card / popover / modal**：分别用于卡片漂浮、下拉/气泡、对话框。别把 modal 阴影用在每张卡片上。

## 动效

- `motion.duration*` 与 `ease*` 供过渡、抽屉、轻量 hover。本期不强制全站动画；新增交互时再从 token 取用。

## Ant Design 映射约定

- 全局通过 `AppProviders` → `ConfigProvider theme={workbenchTheme}`。
- **不要**在页面级再次包一层 `ConfigProvider` 改主色，除非该路由是隔离演示页。
- Button / Input / Table / Card 的视觉以 `theme.ts` 为准；单独调某个按钮时先用 `type`/`danger`/`size`，再考虑 style。

## 不要做

- 不把 mock 十六进制散落在 TSX（除领域模块内已过审的常量）。
- 不把 **i18n / 暗色主题** 与本文件混谈——当前规范外；若立项再扩展 token。
- 不在此文件堆业务名词；业务口径写在 feature 内的 adapter/注释。
