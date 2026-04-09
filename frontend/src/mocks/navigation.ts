export type WorkbenchSection = {
  key: string;
  label: string;
  path: string;
  icon: string;
  description: string;
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
    key: "decision-matters",
    label: "决策事项",
    path: "/decision-matters",
    icon: "decision",
    description: "待决策事项入口",
  },
  {
    key: "bond-analysis",
    label: "债券分析",
    path: "/bond-analysis",
    icon: "bond",
    description: "债券工作台入口",
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
];
