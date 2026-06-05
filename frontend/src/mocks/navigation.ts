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
  governanceStatus?: "temporary-exception";
  governanceBanner?: string;
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
    label: "经营驾驶舱",
    description: "先看今日判断、经营总览和跨页待办。",
    icon: "dashboard",
    defaultPath: "/",
  },
  {
    key: "portfolio",
    label: "组合工作台",
    description: "持仓、资产负债、损益与分析归因入口。",
    icon: "bond",
    defaultPath: "/balance-analysis",
  },
  {
    key: "market",
    label: "市场工作台",
    description: "承接市场观察、跨资产传导和新闻事件。",
    icon: "market",
    defaultPath: "/cross-asset",
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
    label: "报表与数据",
    description: "报表中心、数据中心与自助查询工具。",
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
  "balance-movement-analysis": "portfolio",
  "liability-analytics": "portfolio",
  "bond-dashboard": "portfolio",
  positions: "portfolio",
  "product-category-pnl": "portfolio",
  pnl: "portfolio",
  "pnl-bridge": "portfolio",
  "pnl-attribution": "portfolio",
  "pnl-by-business": "portfolio",
  "ledger-pnl": "portfolio",
  "bank-ledger-dashboard": "portfolio",
  "average-balance": "portfolio",
  "market-data": "market",
  "macro-toolkit": "market",
  "cross-asset": "market",
  "stock-analysis": "market",
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
  "/cross-asset-drivers": "/cross-asset",
  "/adb": "/average-balance",
  "/assets": "/bond-dashboard",
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
    label: "经营驾驶舱",
    path: "/",
    icon: "dashboard",
    description: "管理总览与壳层入口",
    readiness: "live",
    readinessLabel: "已开放",
    readinessNote: "已接真实只读链路，缺数时由后端返回受控回退值。",
  },
  {
    key: "operations-analysis",
    label: "经营分析",
    path: "/operations-analysis",
    icon: "analysis",
    description: "经营摘要与后续分析入口",
    readiness: "live",
    readinessLabel: "临时开放",
    governanceStatus: "temporary-exception",
    governanceBanner:
      "临时例外：该路由仅在第一阶段 PAGE-OPS-001 收口期间保持可见；如收口延期，下一轮 readiness 梳理需降级。",
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
    readinessLabel: "临时开放",
    governanceStatus: "temporary-exception",
    readinessNote: "已接治理后的债券分析驾驶舱，页面内按模块就绪度展示已落地与待晋升能力。",
  },
  {
    key: "cross-asset",
    label: "跨资产驱动",
    path: "/cross-asset",
    icon: "analysis",
    description: "宏观与资产价格向债券的传导估计",
    readiness: "live",
    readinessLabel: "临时开放",
    governanceStatus: "temporary-exception",
    readinessNote: "已接宏观-债市联动分析读链路；完整序列见市场数据页。",
  },
  {
    key: "team-performance",
    label: "团队绩效",
    path: "/team-performance",
    icon: "team",
    description: "团队贡献入口",
    readiness: "live",
    readinessLabel: "临时开放",
    governanceStatus: "temporary-exception",
    readinessNote: "已接统一接口客户端读链路。",
  },
  {
    key: "decision-items",
    label: "决策事项",
    path: "/decision-items",
    icon: "decision",
    description:
      "集中查看与处理资产负债分析决策事项：读接口拉取规则命中项，写接口回写确认/忽略与备注。",
    readiness: "live",
    readinessLabel: "临时开放",
    governanceStatus: "temporary-exception",
    readinessNote:
      "本页已接 balance-analysis 的 decision-items 与 decision-items/status 读写在统一 ApiClient 上，报告日由 dates 驱动，默认取可用日期中最新的一档。",
  },
  {
    key: "balance-analysis",
    label: "资产负债分析",
    path: "/balance-analysis",
    icon: "analysis",
    description: "债券与同业正式资产负债分析入口",
    readiness: "live",
    readinessLabel: "已开放",
    readinessNote: "已接正式事实读链路，是当前阶段主数据页之一。",
  },
  {
    key: "balance-movement-analysis",
    label: "余额变动分析",
    path: "/balance-movement-analysis",
    icon: "analysis",
    description: "AC / OCI / TPL 月末余额变动与总账控制数对账",
    readiness: "live",
    readinessLabel: "已开放",
    readinessNote: "已接会计资产变动正式读模型，CNX 141/142/143/1440101 为控制科目。",
  },
  {
    key: "liability-analytics",
    label: "负债结构分析",
    path: "/liability-analytics",
    icon: "analysis",
    description: "资金与负债：NIM 压力测试、对手方集中度与负债期限结构（V1 口径）",
    readiness: "live",
    readinessLabel: "已开放",
    readinessNote:
      "已接负债风险桶、收益率/NIM、对手方与月度序列读链路；月度概览与 Top10 柱序列与 V1 对齐。",
  },
  {
    key: "market-data",
    label: "市场数据",
    path: "/market-data",
    icon: "market",
    description: "市场观察入口",
    readiness: "live",
    readinessLabel: "已开放",
    readinessNote:
      "已接正式利率行情读链路，稳定序列走 formal 口径；分析口径模块（Livermore / 联动）独立标注。",
  },
  {
    key: "macro-toolkit",
    label: "宏观工具",
    path: "/macro-toolkit",
    icon: "analysis",
    description: "迁移后的宏观脚本工具入口，默认读取系统 Choice/Tushare 数据源。",
    readiness: "live",
    readinessLabel: "工具口径",
    readinessNote:
      "脚本注册表、分析结果与运行入口已接到后端宏观模块；页面明确标注非正式口径。",
  },
  {
    key: "stock-analysis",
    label: "股票分析",
    path: "/stock-analysis",
    icon: "market",
    description: "A股市场状态、行业强弱、候选股证据与风险观察。",
    readiness: "live",
    readinessLabel: "观察口径",
    governanceStatus: "temporary-exception",
    readinessNote:
      "复用 Livermore / Choice 股票只读分析链路，仅展示观察和复核证据，不生成交易指令。",
  },
  {
    key: "source-preview",
    label: "Source Preview",
    path: "/source-preview",
    icon: "market",
    description: "Source preview reserved route",
    readiness: "placeholder",
    readinessLabel: "Reserved",
    readinessNote:
      "Hidden reserved route. Source preview remains outside the current cutover boundary.",
    navigationVisibility: "hidden",
  },
  {
    key: "platform-config",
    label: "数据中心",
    path: "/platform-config",
    icon: "settings",
    description: "系统健康检查、数据源状态与中台配置。",
    readiness: "live",
    readinessLabel: "临时开放",
    governanceStatus: "temporary-exception",
    readinessNote: "展示系统健康检查与数据源状态。",
  },
  {
    key: "reports-center",
    label: "报表中心",
    path: "/reports",
    icon: "reports",
    description: "报表与导出清单（占位路由）。",
    readiness: "placeholder",
    readinessLabel: "保留",
    readinessNote: "保留导航入口；正式导出仍在各业务页，后续统一收录。",
  },
  {
    key: "bond-dashboard",
    label: "债券总览",
    path: "/bond-dashboard",
    icon: "bond",
    description: "承接 V1「/bonds」书签；债券组合 KPI、结构、风险一览。",
    readiness: "live",
    readinessLabel: "临时开放",
    governanceStatus: "temporary-exception",
    readinessNote: "已接 /api/bond-dashboard 聚合读链路。",
  },
  {
    key: "positions",
    label: "持仓透视",
    path: "/positions",
    icon: "bond",
    description: "债券与同业持仓明细、分布与客户下钻",
    readiness: "live",
    readinessLabel: "临时开放",
    governanceStatus: "temporary-exception",
    readinessNote: "已接 /api/positions 正式读链路（与 V1 对齐）；缺数时由后端返回空表与受控元数据。",
  },
  {
    key: "average-balance",
    label: "日均分析",
    path: "/average-balance",
    icon: "analysis",
    description: "同业与债券口径的日均分析视图；正式余额真源见「资产负债分析」。",
    readiness: "live",
    readinessLabel: "临时开放",
    governanceStatus: "temporary-exception",
    readinessNote: "可直接打开本路由；正式治理余额仍以资产负债分析页为准。",
  },
  {
    key: "ledger-pnl",
    label: "总账损益",
    path: "/ledger-pnl",
    icon: "analysis",
    description: "科目口径损益总览、账户聚合与明细透视。",
    readiness: "live",
    readinessLabel: "临时开放",
    governanceStatus: "temporary-exception",
    readinessNote: "直接消费后端总账损益读模型，不在前端补算科目口径汇总。",
  },
  {
    key: "bank-ledger-dashboard",
    label: "银行台账",
    path: "/bank-ledger-dashboard",
    icon: "analysis",
    description: "银行债券台账资产、发行负债与净敞口驾驶舱",
    readiness: "live",
    readinessLabel: "临时开放",
    governanceStatus: "temporary-exception",
    readinessNote:
      "接入 /api/ledger/* 新台账读链路，日期使用 as_of_date，金额 KPI 按亿元展示，明细保留原始元与 trace。",
  },
  {
    key: "risk-overview",
    label: "风险总览",
    path: "/risk-overview",
    icon: "risk",
    description: "风险总览与风险下钻入口",
    readiness: "placeholder",
    readinessLabel: "Reserved",
    readinessNote:
      "Reserved by the current boundary. Direct access stays on placeholder behavior until this surface is explicitly promoted.",
  },
  {
    key: "risk-tensor",
    label: "风险张量",
    path: "/risk-tensor",
    icon: "risk",
    description: "正式组合风险张量",
    readiness: "live",
    readinessLabel: "已开放",
    readinessNote: "已接正式风险张量读链路，并按后端日期接口选择可用报告日。",
  },
  {
    key: "concentration-monitor",
    label: "集中度监控",
    path: "/concentration-monitor",
    icon: "risk",
    description: "持仓集中度与限额预警",
    readiness: "live",
    readinessLabel: "临时开放",
    governanceStatus: "temporary-exception",
    readinessNote: "已接债券分析信用利差迁移集中度载荷与展示限额对照。",
  },
  {
    key: "cashflow-projection",
    label: "现金流预测",
    path: "/cashflow-projection",
    icon: "risk",
    description: "久期缺口分析、月度现金流投影与再投资风险",
    readiness: "live",
    readinessLabel: "临时开放",
    governanceStatus: "temporary-exception",
    readinessNote: "已接 /api/cashflow-projection 只读链路。",
  },
  {
    key: "kpi-performance",
    label: "绩效考核",
    path: "/kpi",
    icon: "kpi",
    description: "KPI 指标、批量导入、抓取计分与溯源",
    readiness: "live",
    readinessLabel: "临时开放",
    governanceStatus: "temporary-exception",
    readinessNote: "已接 /api/kpi 读写链路，与 V1 行为对齐。",
  },
  {
    key: "news-events",
    label: "新闻事件",
    path: "/news-events",
    icon: "decision",
    description: "Choice 新闻事件与回调异常入口",
    readiness: "live",
    readinessLabel: "临时开放",
    governanceStatus: "temporary-exception",
    readinessNote:
      "已接 Choice 新闻事件只读链路；页面为分析读面（非 formal metric 主链），与壳层「临时例外」横幅一致。",
  },
  {
    key: "product-category-pnl",
    label: "产品分析",
    path: "/product-category-pnl",
    icon: "analysis",
    description: "产品类别损益与场景分析入口",
    readiness: "live",
    readinessLabel: "临时开放",
    governanceStatus: "temporary-exception",
    readinessNote: "已接产品损益主分支，并为月度经营分析预留同屏并存分支。",
  },
  {
    key: "pnl",
    label: "收益分析",
    path: "/pnl",
    icon: "analysis",
    description: "收益总览、损益归因与期间收益（与 V1 /pnl 对齐）",
    readiness: "live",
    readinessLabel: "已开放",
    readinessNote: "收益指标与归因读链路已接；期间收益表为占位接口，正式明细表见 /pnl-formal-v1。",
  },
  {
    key: "pnl-bridge",
    label: "损益桥接",
    path: "/pnl-bridge",
    icon: "analysis",
    description: "正式口径损益桥接分解",
    readiness: "live",
    readinessLabel: "已开放",
    readinessNote: "已接正式损益桥接读链路，展示正式桥接分解与汇总图表。",
  },
  {
    key: "pnl-attribution",
    label: "收益归因",
    path: "/pnl-attribution",
    icon: "analysis",
    description: "规模/利率效应、TPL 市场相关性、损益构成、高级归因与 Campisi",
    readiness: "live",
    readinessLabel: "已开放",
    readinessNote: "已接 /api/pnl-attribution 读链路。",
  },
  {
    key: "cube-query",
    label: "自助查询",
    path: "/cube-query",
    icon: "analysis",
    description: "对事实表进行自由维度聚合、筛选、钻取",
    readiness: "live",
    readinessLabel: "已开放",
    readinessNote:
      "已接 /api/cube/query 与 /api/cube/dimensions/*；当前仅按已覆盖事实表与 result_meta 声明查询结果口径。",
  },
  {
    key: "pnl-by-business",
    label: "业务种类损益",
    path: "/pnl-by-business",
    icon: "analysis",
    description: "按 ZQTZ 业务种类1 追溯正式 FI 损益和规模。",
    readiness: "live",
    readinessLabel: "临时开放",
    governanceStatus: "temporary-exception",
    readinessNote: "读取 /api/pnl/by-business 与 /api/pnl/yearly-summary，不再跳转到总账损益。",
  },
  {
    key: "agent",
    label: "智能体工作台",
    path: "/agent",
    icon: "agent",
    description: "智能体分析工作台：面向证据问答、GitNexus 仓库图谱和后续页面助手。",
    readiness: "live",
    readinessLabel: "Hermes",
    readinessNote:
      "Hermes Agent is available through /api/agent/query when MOSS_AGENT_PROVIDER=hermes.",
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
