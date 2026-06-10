export type MarketQuickAccessTile = {
  key: string;
  icon: string;
  label: string;
  path: string;
  badge: string;
  description: string;
};

export const MARKET_QUICK_ACCESS_TILES: MarketQuickAccessTile[] = [
  {
    key: "market-data",
    icon: "MD",
    label: "市场数据",
    path: "/market-data",
    badge: "已开放",
    description: "正式利率序列、曲线与流动性快照。",
  },
  {
    key: "cross-asset",
    icon: "XA",
    label: "跨资产驱动",
    path: "/cross-asset",
    badge: "观察口径",
    description: "宏观、汇率与权益向债市的传导解释。",
  },
  {
    key: "macro-toolkit",
    icon: "MT",
    label: "宏观工具",
    path: "/macro-toolkit",
    badge: "工具口径",
    description: "脚本注册表、信号卡片与能力模块。",
  },
  {
    key: "news-events",
    icon: "NE",
    label: "新闻事件",
    path: "/news-events",
    badge: "已开放",
    description: "Choice 新闻事件与回调异常摘要。",
  },
  {
    key: "stock-analysis",
    icon: "EQ",
    label: "股票分析",
    path: "/stock-analysis",
    badge: "观察口径",
    description: "A 股市场状态、行业强弱与风险观察。",
  },
  {
    key: "macro-observation",
    icon: "MO",
    label: "宏观观察",
    path: "/macro-observation",
    badge: "观察口径",
    description: "只读宏观信号、风险状态与策略证据。",
  },
];
