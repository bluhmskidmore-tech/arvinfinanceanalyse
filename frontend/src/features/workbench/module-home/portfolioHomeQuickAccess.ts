export type PortfolioQuickAccessTile = {
  key: string;
  icon: string;
  label: string;
  path: string;
  badge: string;
  description: string;
};

/** 首屏底部快捷入口：与组合工作台 live 子页对齐，不做前端补数。 */
export const PORTFOLIO_QUICK_ACCESS_TILES: PortfolioQuickAccessTile[] = [
  {
    key: "bond-dashboard",
    icon: "BD",
    label: "债券总览",
    path: "/bond-dashboard",
    badge: "核心读数",
    description: "headline KPI、风险指标与结构分布。",
  },
  {
    key: "positions",
    icon: "PO",
    label: "持仓透视",
    path: "/positions",
    badge: "逐券明细",
    description: "逐券持仓、估值与下钻证据。",
  },
  {
    key: "pnl-attribution",
    icon: "PA",
    label: "收益归因",
    path: "/pnl-attribution",
    badge: "归因瀑布",
    description: "规模/利率分解与主驱动摘要。",
  },
  {
    key: "bond-analysis",
    icon: "BA",
    label: "债券分析",
    path: "/bond-analysis",
    badge: "深度分析",
    description: "曲线、KRD 与策略标签读数。",
  },
  {
    key: "balance-analysis",
    icon: "BL",
    label: "资产负债",
    path: "/balance-analysis",
    badge: "规模错配",
    description: "资产/负债侧 overview 与 basis 分解。",
  },
  {
    key: "risk-tensor",
    icon: "RT",
    label: "风险张量",
    path: "/risk-tensor",
    badge: "风险闭合",
    description: "DV01、久期与风险张量日期闭合。",
  },
];
