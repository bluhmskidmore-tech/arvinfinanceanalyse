/**
 * Nocturne 色板已登记的页面 scope（`data-moss-theme-scope` 取值）。
 *
 * 与 `src/styles/tokens.css` 主色板块（`--nct-bg: #161826`）的 scope 列表
 * 同构全量；theme.test.ts 断言两者一致，防止本清单与 CSS 漂移。
 * `PageV2Shell` / `MarketWorkbenchFrame` 的 `themeScope` prop 收窄为该
 * 字面量联合，杜绝拼写错误产生静默死 scope（CSS 选择器永不命中）。
 * 新页面接入 Nocturne 时：tokens.css 各收口块加行 + 本清单登记同步进行。
 */
export const NOCTURNE_THEME_SCOPES = [
  "agent",
  "average-balance",
  "balance-analysis",
  "balance-movement-analysis",
  "bank-ledger-dashboard",
  "bond-analysis",
  "bond-dashboard",
  "bond-trading-desk",
  "cashflow-projection",
  "concentration-monitor",
  "cross-asset",
  "cube-query",
  "dashboard-home",
  "decision-items",
  "kpi",
  "ledger-pnl",
  "liability-analytics",
  "macro-toolkit",
  "market-data",
  "market-finance",
  "market-overview",
  "module-workbench-home",
  "news-events",
  "operations-analysis",
  "platform-config",
  "pnl",
  "pnl-attribution",
  "pnl-bridge",
  "pnl-by-business",
  "pnl-by-business-insights",
  "portfolio-home",
  "positions",
  "product-category-pnl",
  "risk-overview",
  "risk-tensor",
  "stock-analysis",
  "team-performance",
] as const;

export type NocturneThemeScope = (typeof NOCTURNE_THEME_SCOPES)[number];
