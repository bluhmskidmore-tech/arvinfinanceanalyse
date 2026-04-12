export type WorkbenchReadiness = "live" | "placeholder" | "gated";

export type WorkbenchSection = {
  key: string;
  label: string;
  path: string;
  icon: string;
  description: string;
  readiness: WorkbenchReadiness;
  readinessLabel: string;
  readinessNote: string;
  navigationVisibility?: "primary" | "hidden";
};

export const workbenchNavigation: WorkbenchSection[] = [
  {
    key: "dashboard",
    label: "驾驶舱",
    path: "/",
    icon: "dashboard",
    description: "管理总览与壳层入口",
    readiness: "live",
    readinessLabel: "Live",
    readinessNote: "已接真实只读链路，缺数时由后端返回受控回退值。",
  },
  {
    key: "operations-analysis",
    label: "经营分析",
    path: "/operations-analysis",
    icon: "analysis",
    description: "经营摘要与后续分析入口",
    readiness: "live",
    readinessLabel: "Live",
    readinessNote: "已接 source preview、macro、news 与 formal FX 状态读链路。",
  },
  {
    key: "risk-overview",
    label: "风险总览",
    path: "/risk-overview",
    icon: "risk",
    description: "风险总览与风险下钻入口",
    readiness: "live",
    readinessLabel: "Live",
    readinessNote: "已接正式 risk tensor 主链，并串接 bond analytics 下钻只读结果。",
  },
  {
    key: "risk-tensor",
    label: "风险张量",
    path: "/risk-tensor",
    icon: "risk",
    description: "正式组合风险张量",
    readiness: "live",
    readinessLabel: "Live",
    readinessNote: "已接正式 risk tensor 读链路，并按后端 dates 接口选择可用报告日。",
  },
  {
    key: "team-performance",
    label: "团队绩效",
    path: "/team-performance",
    icon: "team",
    description: "团队贡献入口",
    readiness: "placeholder",
    readinessLabel: "Placeholder",
    readinessNote: "当前仍为壳层占位，只展示模块说明，不展示真实数据。",
  },
  {
    key: "news-events",
    label: "新闻事件",
    path: "/news-events",
    icon: "decision",
    description: "Choice 新闻事件与回调异常入口",
    readiness: "live",
    readinessLabel: "Live",
    readinessNote: "已接真实 Choice news 只读链路。",
  },
  {
    key: "bond-analysis",
    label: "债券分析",
    path: "/bond-analysis",
    icon: "bond",
    description: "债券工作台入口",
    readiness: "gated",
    readinessLabel: "Not Ready",
    readinessNote: "债券分析物化表尚未就绪，当前页面属于预留入口。",
  },
  {
    key: "balance-analysis",
    label: "资产负债分析",
    path: "/balance-analysis",
    icon: "analysis",
    description: "债券与同业正式资产负债分析入口",
    readiness: "live",
    readinessLabel: "Live",
    readinessNote: "已接 formal fact 读链路，是当前阶段主数据页之一。",
  },
  {
    key: "product-category-pnl",
    label: "产品损益",
    path: "/product-category-pnl",
    icon: "analysis",
    description: "产品类别损益与场景分析入口",
    readiness: "live",
    readinessLabel: "Live",
    readinessNote: "已接产品损益主分支，并为月度经营分析预留同屏并存分支。",
  },
  {
    key: "pnl",
    label: "损益明细",
    path: "/pnl",
    icon: "analysis",
    description: "正式损益明细入口",
    readiness: "live",
    readinessLabel: "Live",
    readinessNote: "已接 formal pnl 事实表读链路，报告日由后端 dates 接口驱动。",
  },
  {
    key: "pnl-bridge",
    label: "损益桥接",
    path: "/pnl-bridge",
    icon: "analysis",
    description: "正式口径损益桥接分解",
    readiness: "live",
    readinessLabel: "Live",
    readinessNote: "已接 formal pnl bridge 读链路，展示正式桥接分解与汇总图表。",
  },
  {
    key: "platform-config",
    label: "中台配置",
    path: "/platform-config",
    icon: "settings",
    description: "配置与治理入口",
    readiness: "placeholder",
    readinessLabel: "Placeholder",
    readinessNote: "当前仍为壳层占位，用于保留入口与后续治理面。",
  },
  {
    key: "market-data",
    label: "市场数据",
    path: "/market-data",
    icon: "market",
    description: "市场观察入口",
    readiness: "live",
    readinessLabel: "Live",
    readinessNote: "已接宏观、FX analytical 与 formal FX 状态读链路。",
  },
  {
    key: "agent",
    label: "Agent Workbench",
    path: "/agent",
    icon: "agent",
    description: "Hidden analytical workbench route for agent-facing news and evidence surfaces.",
    readiness: "gated",
    readinessLabel: "Disabled Stub",
    readinessNote: "受 Phase 1 限制，仅保留隐藏路由与 disabled stub。",
    navigationVisibility: "hidden",
  },
];

export const primaryWorkbenchNavigation = workbenchNavigation.filter(
  (section) =>
    section.navigationVisibility !== "hidden" && section.readiness === "live",
);

export const secondaryWorkbenchNavigation = workbenchNavigation.filter(
  (section) =>
    section.navigationVisibility !== "hidden" && section.readiness !== "live",
);
