export type WorkbenchReadiness = "live" | "placeholder" | "gated";

export type WorkbenchGroupKey =
  | "overview"
  | "portfolio"
  | "market"
  | "risk"
  | "performance"
  | "governance";

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

export type WorkbenchNavigationGroup = {
  key: WorkbenchGroupKey;
  label: string;
  description: string;
  icon: string;
  defaultPath: string;
  sections: WorkbenchSection[];
};

const workbenchGroupDefinitions: Array<Omit<WorkbenchNavigationGroup, "sections">> = [
  {
    key: "overview",
    label: "总览工作台",
    description: "先看总览、经营判断和跨页待办。",
    icon: "dashboard",
    defaultPath: "/",
  },
  {
    key: "portfolio",
    label: "组合工作台",
    description: "围绕持仓、资产负债、损益和专题分析展开。",
    icon: "bond",
    defaultPath: "/balance-analysis",
  },
  {
    key: "market",
    label: "市场工作台",
    description: "承接市场观察、跨资产传导和新闻事件。",
    icon: "market",
    defaultPath: "/market-data",
  },
  {
    key: "risk",
    label: "风险工作台",
    description: "聚焦风险张量、集中度和流动性压力。",
    icon: "risk",
    defaultPath: "/risk-tensor",
  },
  {
    key: "performance",
    label: "绩效工作台",
    description: "查看团队绩效与 KPI 归因结果。",
    icon: "kpi",
    defaultPath: "/kpi",
  },
  {
    key: "governance",
    label: "治理工作台",
    description: "放置配置、报表和自由查询工具。",
    icon: "settings",
    defaultPath: "/platform-config",
  },
];

const workbenchSectionGroups: Record<string, WorkbenchGroupKey> = {
  dashboard: "overview",
  "operations-analysis": "overview",
  "decision-items": "overview",
  "bond-analysis": "portfolio",
  "balance-analysis": "portfolio",
  "liability-analytics": "portfolio",
  "bond-dashboard": "portfolio",
  positions: "portfolio",
  "product-category-pnl": "portfolio",
  pnl: "portfolio",
  "pnl-bridge": "portfolio",
  "pnl-attribution": "portfolio",
  "ledger-pnl": "portfolio",
  "average-balance": "portfolio",
  "market-data": "market",
  "cross-asset": "market",
  "news-events": "market",
  "risk-overview": "risk",
  "risk-tensor": "risk",
  "concentration-monitor": "risk",
  "cashflow-projection": "risk",
  "kpi-performance": "performance",
  "team-performance": "performance",
  "platform-config": "governance",
  "reports-center": "governance",
  "cube-query": "governance",
  agent: "governance",
};

/**
 * V1 书签/外部链接常用路径 → V3 工作台规范路径。
 * 与 `router/routes.tsx` 中 `<Navigate replace />` 保持一致。
 */
export const workbenchPathAliases: Record<string, string> = {
  "/macro-analysis": "/market-data",
  "/market": "/market-data",
  "/adb": "/average-balance",
  "/assets": "/bond-dashboard",
  "/pnl-by-business": "/ledger-pnl",
  "/liabilities": "/liability-analytics",
  "/bonds": "/bond-dashboard",
  "/bond-analytics-advanced": "/bond-analysis",
};

export function resolveWorkbenchPathAlias(pathname: string): string {
  return workbenchPathAliases[pathname] ?? pathname;
}

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
    readinessNote:
      "已接 source preview、macro、news、formal FX 状态，以及资产负债 overview 速览与跳转。",
  },
  {
    key: "bond-analysis",
    label: "债券分析",
    path: "/bond-analysis",
    icon: "bond",
    description: "债券工作台入口",
    readiness: "live",
    readinessLabel: "Live",
    readinessNote: "已接 governed bond analytics cockpit，页面内按模块 readiness 展示已落地与待晋升能力。",
  },
  {
    key: "cross-asset",
    label: "跨资产驱动",
    path: "/cross-asset",
    icon: "analysis",
    description: "宏观与资产价格向债券的传导估计",
    readiness: "live",
    readinessLabel: "Live",
    readinessNote: "已接 macro-bond-linkage 分析读链路；完整序列见市场数据页。",
  },
  {
    key: "team-performance",
    label: "团队绩效",
    path: "/team-performance",
    icon: "team",
    description: "团队贡献入口",
    readiness: "live",
    readinessLabel: "Live",
    readinessNote: "已接统一 ApiClient 读链路。",
  },
  {
    key: "decision-items",
    label: "决策事项",
    path: "/decision-items",
    icon: "decision",
    description: "跨页决策与待办聚合（占位路由）。",
    readiness: "placeholder",
    readinessLabel: "Reserved",
    readinessNote: "保留导航入口；能力仍在各业务页，后续再收敛到此路由。",
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
    key: "liability-analytics",
    label: "负债结构分析",
    path: "/liability-analytics",
    icon: "analysis",
    description: "NIM 压力测试、对手方集中度与负债期限结构（V1 口径）",
    readiness: "placeholder",
    readinessLabel: "Compat",
    readinessNote:
      "当前仅保留 compatibility 模块入口；正式 Phase 2 主链未纳入 liability_analytics_compat 消费面。",
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
    key: "platform-config",
    label: "中台配置",
    path: "/platform-config",
    icon: "settings",
    description: "配置与治理入口",
    readiness: "live",
    readinessLabel: "Live",
    readinessNote: "展示系统健康检查与数据源状态。",
  },
  {
    key: "reports-center",
    label: "报表中心",
    path: "/reports",
    icon: "reports",
    description: "报表与导出清单（占位路由）。",
    readiness: "placeholder",
    readinessLabel: "Reserved",
    readinessNote: "保留导航入口；正式导出仍在各业务页，后续统一收录。",
  },
  {
    key: "bond-dashboard",
    label: "债券总览",
    path: "/bond-dashboard",
    icon: "bond",
    description: "承接 V1「/bonds」书签；债券组合 KPI、结构、风险一览。",
    readiness: "live",
    readinessLabel: "Live",
    readinessNote: "已接 /api/bond-dashboard 聚合读链路。",
  },
  {
    key: "positions",
    label: "持仓透视",
    path: "/positions",
    icon: "bond",
    description: "债券与同业持仓明细、分布与客户下钻",
    readiness: "live",
    readinessLabel: "Live",
    readinessNote: "已接 /api/positions 正式读链路（与 V1 对齐）；缺数时由后端返回空表与受控元数据。",
  },
  {
    key: "average-balance",
    label: "ADB Analytical",
    path: "/average-balance",
    icon: "analysis",
    description: "同业与债券口径的 ADB analytical 视图；正式余额真源见「资产负债分析」。",
    readiness: "live",
    readinessLabel: "Live",
    readinessNote: "可直接打开本路由；正式 governed 余额仍以资产负债分析页为准。",
  },
  {
    key: "ledger-pnl",
    label: "Ledger PnL",
    path: "/ledger-pnl",
    icon: "analysis",
    description: "科目口径损益总览、账户聚合与明细透视。",
    readiness: "live",
    readinessLabel: "Live",
    readinessNote: "直接消费后端 ledger-pnl read model，不在前端补算科目口径汇总。",
  },
  {
    key: "risk-overview",
    label: "风险总览",
    path: "/risk-overview",
    icon: "risk",
    description: "风险总览与风险下钻入口",
    readiness: "placeholder",
    readinessLabel: "Placeholder",
    readinessNote:
      "executive risk overview 仍在当前 cutover 之外；请优先使用风险张量与已落地的 bond analytics 读面。",
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
    key: "concentration-monitor",
    label: "集中度监控",
    path: "/concentration-monitor",
    icon: "risk",
    description: "持仓集中度与限额预警",
    readiness: "live",
    readinessLabel: "Live",
    readinessNote: "已接 bond analytics credit-spread-migration 集中度载荷与展示限额对照。",
  },
  {
    key: "cashflow-projection",
    label: "现金流预测",
    path: "/cashflow-projection",
    icon: "risk",
    description: "久期缺口分析、月度现金流投影与再投资风险",
    readiness: "live",
    readinessLabel: "Live",
    readinessNote: "已接 /api/cashflow-projection 只读链路。",
  },
  {
    key: "kpi-performance",
    label: "绩效考核",
    path: "/kpi",
    icon: "kpi",
    description: "KPI 指标、批量导入、抓取计分与溯源",
    readiness: "live",
    readinessLabel: "Live",
    readinessNote: "已接 /api/kpi 读写链路，与 V1 行为对齐。",
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
    key: "pnl-attribution",
    label: "损益归因",
    path: "/pnl-attribution",
    icon: "analysis",
    description: "规模/利率效应、TPL 市场相关性、损益构成、高级归因与 Campisi",
    readiness: "live",
    readinessLabel: "Live",
    readinessNote: "已接 /api/pnl-attribution 读链路。",
  },
  {
    key: "cube-query",
    label: "多维查询",
    path: "/cube-query",
    icon: "analysis",
    description: "对事实表进行自由维度聚合、筛选、钻取",
    readiness: "placeholder",
    readinessLabel: "暂缓",
    readinessNote: "入口保留；自由聚合查询尚未作为 Phase 2 主消费面晋升。",
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

export function pathMatchesWorkbenchSection(sectionPath: string, pathname: string) {
  if (sectionPath === "/") {
    return pathname === "/" || pathname === "/dashboard";
  }
  return sectionPath === pathname;
}

export function findWorkbenchSectionByPath(
  pathname: string,
  sections: WorkbenchSection[] = visibleWorkbenchNavigation,
) {
  const resolved = resolveWorkbenchPathAlias(pathname);
  return (
    sections.find((section) => pathMatchesWorkbenchSection(section.path, resolved)) ??
    sections[0]
  );
}

export function resolveWorkbenchGroupKey(section: WorkbenchSection): WorkbenchGroupKey {
  return workbenchSectionGroups[section.key] ?? "overview";
}

export const visibleWorkbenchNavigation = workbenchNavigation.filter(
  (section) => section.navigationVisibility !== "hidden",
);

export const primaryWorkbenchNavigation = visibleWorkbenchNavigation.filter(
  (section) => section.readiness === "live",
);

export const secondaryWorkbenchNavigation = visibleWorkbenchNavigation.filter(
  (section) => section.readiness !== "live",
);

export const primaryWorkbenchNavigationGroups: WorkbenchNavigationGroup[] =
  workbenchGroupDefinitions
    .map((group) => ({
      ...group,
      sections: primaryWorkbenchNavigation.filter(
        (section) => resolveWorkbenchGroupKey(section) === group.key,
      ),
    }))
    .filter((group) => group.sections.length > 0);

export function findWorkbenchGroupByPath(pathname: string) {
  const currentSection = findWorkbenchSectionByPath(pathname);
  return (
    primaryWorkbenchNavigationGroups.find(
      (group) => resolveWorkbenchGroupKey(currentSection) === group.key,
    ) ?? primaryWorkbenchNavigationGroups[0]
  );
}
