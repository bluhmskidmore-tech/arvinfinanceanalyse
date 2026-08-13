/*
 * WorkbenchShell 外壳铬件渲染分支的 section-key 清单（与 workbenchShellTicker
 * 同款先例：Shell 的非组件常量放同级模块，避免组件文件混导出破坏 Fast
 * refresh）。导出给 theme.test.ts 从渲染分支推导 Nocturne CSS 收口列表的
 * 期望值：新增或调整渲染分支时只改这里，parity 断言随之联动。组合关系与
 * WorkbenchShell 内的布尔分支一一对应（纯提炼，行为零变化）。
 */

/** isDashboardCockpitShell：经营日报 / 组合首页走 cockpit 驾驶舱壳。 */
export const DASHBOARD_COCKPIT_SECTION_KEYS: readonly string[] = [
  "dashboard",
  "portfolio-home",
];

/** isModuleHomePage：模块一级首页（performance/reports 由单页组件承载）。 */
export const MODULE_HOME_SECTION_KEYS: readonly string[] = [
  "portfolio-home",
  "market-overview",
  "risk-overview",
  "performance-home",
  "reports-center",
];

/**
 * 宏观工具 / 宏观观察（同一页面组件）：页面自带页头是唯一标题带，
 * 外壳终端条（大标题 + 报告日 chip + 市场 ticker + 工具链接）整块抑制，
 * 报表中心 / 中台配置仍可从左栏「支持入口」进入；组内子导航保持渲染。
 */
export const MACRO_TOOLKIT_SECTION_KEYS: readonly string[] = [
  "macro-toolkit",
  "macro-observation",
];

/** useCockpitShellFrame 为真的 section（workbench-shell-grid--cockpit 壳变体）。 */
export const COCKPIT_SHELL_SECTION_KEYS: readonly string[] = [
  ...new Set([
    ...DASHBOARD_COCKPIT_SECTION_KEYS,
    "bond-analysis",
    "stock-analysis",
    "balance-analysis",
    "balance-movement-analysis",
    "product-category-pnl",
    ...MODULE_HOME_SECTION_KEYS,
  ]),
];

/** showShellTerminalBar 为假（外壳终端条整块抑制）的 section。 */
export const TERMINAL_BAR_EXCLUDED_SECTION_KEYS: readonly string[] = [
  ...new Set([
    ...DASHBOARD_COCKPIT_SECTION_KEYS,
    "bond-analysis",
    "stock-analysis",
    "balance-analysis",
    ...MACRO_TOOLKIT_SECTION_KEYS,
    "balance-movement-analysis",
    ...MODULE_HOME_SECTION_KEYS,
  ]),
];

/** 组内子导航被抑制的 section（对比终端条排除表：去掉宏观工具组、加 market-data 终端主布局）。 */
export const SECTION_SUBNAV_EXCLUDED_SECTION_KEYS: readonly string[] = [
  ...new Set([
    ...DASHBOARD_COCKPIT_SECTION_KEYS,
    "bond-analysis",
    "stock-analysis",
    "balance-analysis",
    "balance-movement-analysis",
    "market-data",
    ...MODULE_HOME_SECTION_KEYS,
  ]),
];
