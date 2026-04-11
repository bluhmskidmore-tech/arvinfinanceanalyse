export type WorkbenchSection = {
  key: string;
  label: string;
  path: string;
  icon: string;
  description: string;
  navigationVisibility?: "primary" | "hidden";
};

export const workbenchNavigation: WorkbenchSection[] = [
  {
    key: "dashboard",
    label: "驾驶舱",
    path: "/",
    icon: "dashboard",
    description: "管理总览与壳层入口",
  },
  {
    key: "operations-analysis",
    label: "经营分析",
    path: "/operations-analysis",
    icon: "analysis",
    description: "经营摘要与后续分析入口",
  },
  {
    key: "risk-overview",
    label: "风险总览",
    path: "/risk-overview",
    icon: "risk",
    description: "风险工作台占位",
  },
  {
    key: "team-performance",
    label: "团队绩效",
    path: "/team-performance",
    icon: "team",
    description: "团队贡献入口",
  },
  {
    key: "news-events",
    label: "新闻事件",
    path: "/news-events",
    icon: "decision",
    description: "Choice 新闻事件与回调异常入口",
  },
  {
    key: "bond-analysis",
    label: "债券分析",
    path: "/bond-analysis",
    icon: "bond",
    description: "债券工作台入口",
  },
  {
    key: "balance-analysis",
    label: "资产负债分析",
    path: "/balance-analysis",
    icon: "analysis",
    description: "债券与同业正式资产负债分析入口",
  },
  {
    key: "product-category-pnl",
    label: "产品损益",
    path: "/product-category-pnl",
    icon: "analysis",
    description: "产品类别损益与场景分析入口",
  },
  {
    key: "platform-config",
    label: "中台配置",
    path: "/platform-config",
    icon: "settings",
    description: "配置与治理入口",
  },
  {
    key: "market-data",
    label: "市场数据",
    path: "/market-data",
    icon: "market",
    description: "市场观察入口",
  },
  {
    key: "agent",
    label: "Agent Workbench",
    path: "/agent",
    icon: "agent",
    description: "Hidden analytical workbench route for agent-facing news and evidence surfaces.",
    navigationVisibility: "hidden",
  },
];

export const primaryWorkbenchNavigation = workbenchNavigation.filter(
  (section) => section.navigationVisibility !== "hidden",
);
