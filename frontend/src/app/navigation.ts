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
    label: "经营日报",
    description: "先看主快照读数、数据边界和跨页待办。",
    icon: "dashboard",
    defaultPath: "/",
  },
  {
    key: "portfolio",
    label: "组合工作台",
    description: "持仓、资产负债、损益与分析归因入口。",
    icon: "bond",
    defaultPath: "/portfolio",
  },
  {
    key: "market",
    label: "市场工作台",
    description: "承接市场观察、跨资产传导和新闻事件。",
    icon: "market",
    defaultPath: "/market-overview",
  },
  {
    key: "risk",
    label: "风险工作台",
    description: "聚焦风险张量、集中度和流动性压力。",
    icon: "risk",
    defaultPath: "/risk-overview",
  },
  {
    key: "performance",
    label: "绩效工作台",
    description: "查看团队绩效与 KPI 归因结果。",
    icon: "kpi",
    defaultPath: "/performance",
  },
  {
    key: "governance",
    label: "报表与数据",
    description: "报表中心、数据中心与自助查询工具。",
    icon: "settings",
    defaultPath: "/reports",
  },
];

const workbenchSectionGroups: Record<string, WorkbenchGroupKey> = {
  dashboard: "overview",
  "operations-analysis": "overview",
  "market-finance": "overview",
  "decision-items": "overview",
  "portfolio-home": "portfolio",
  "bond-analysis": "portfolio",
  "bond-trading-desk": "portfolio",
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
  "pnl-by-business-insights": "portfolio",
  "ledger-pnl": "portfolio",
  "bank-ledger-dashboard": "portfolio",
  "average-balance": "portfolio",
  "market-overview": "market",
  "market-data": "market",
  "macro-observation": "market",
  "macro-toolkit": "market",
  "cross-asset": "market",
  "stock-analysis": "market",
  "news-events": "market",
  "risk-overview": "risk",
  "risk-tensor": "risk",
  "concentration-monitor": "risk",
  "cashflow-projection": "risk",
  "performance-home": "performance",
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
    label: "经营日报",
    path: "/",
    icon: "dashboard",
    description: "主快照读数与数据边界入口",
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
    key: "market-finance",
    label: "金市与计财",
    path: "/market-finance",
    icon: "analysis",
    description: "金市投研与计划财务协同台：分列市场、FTP、经营与资产负债既有证据。",
    readiness: "live",
    readinessLabel: "临时开放",
    governanceStatus: "temporary-exception",
    readinessNote:
      "复用市场利率、产品分类损益与资产负债 overview 既有只读链路；不补算跨域传导、OCI 与资本口径，缺证据统一显示待复核。",
  },
  {
    key: "portfolio-home",
    label: "组合工作台",
    path: "/portfolio",
    icon: "bond",
    description: "组合一级首页：聚合资产负债、债券总览、持仓和归因入口。",
    readiness: "live",
    readinessLabel: "已开放",
    readinessNote: "一级首页只做摘要与下钻，不替代子页面正式业务逻辑。",
  },
  {
    key: "bond-analysis",
    label: "债券分析",
    path: "/bond-analysis",
    icon: "bond",
    description: "债券工作台入口",
    readiness: "live",
    readinessLabel: "已开放",
    readinessNote: "已接债券分析交易台首屏、组合读面、风险监控和下钻复核入口。",
  },
  {
    key: "bond-trading-desk",
    label: "单券交易分析台",
    path: "/bond-trading-desk",
    icon: "bond",
    description: "单券只读拼装读面，由重仓券/持仓深钻进入。",
    readiness: "live",
    readinessLabel: "深钻路由",
    readinessNote:
      "只拼装 top-holdings / positions / 利差列表；盘口、约束与相似券等待后端契约，导航默认隐藏。",
    navigationVisibility: "hidden",
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
    key: "market-overview",
    label: "市场工作台",
    path: "/market-overview",
    icon: "market",
    description: "市场一级首页：聚合行情、跨资产、宏观工具、股票和新闻事件入口。",
    readiness: "live",
    readinessLabel: "已开放",
    readinessNote: "一级首页展示市场数据状态和关键行情，旧 /market 书签仍跳转到 /market-data。",
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
    key: "macro-observation",
    label: "宏观观察",
    path: "/macro-observation",
    icon: "analysis",
    description: "只读宏观分析入口，展示核心信号、风险状态和策略供数证据。",
    readiness: "live",
    readinessLabel: "观察口径",
    readinessNote:
      "复用宏观分析读链路，只展示 analytical evidence；刷新、脚本注册表和运行结果留在宏观工具页。",
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
    label: "报表与数据",
    path: "/reports",
    icon: "reports",
    description: "报表与数据一级首页：聚合数据健康、来源状态、自助查询与报表规划。",
    readiness: "live",
    readinessLabel: "已开放",
    readinessNote: "报表能力未接入正式后端接口时明确显示规划中，不伪造报表数据。",
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
      "Candidate imported position_snapshot read model; import-time rv_ledger_classification_v2 materializes UNCLASSIFIED; legacy batches fail closed and invalid_materialization also fails closed. Currency buckets remain independent with past-only fallback. Historical backfill completed for live batches 1-8 and golden sample captured-awaiting-approval; formal use, owner approval, authorized real-page UAT, and UNKNOWN remediation remain pending; same source hash cannot be replayed.",
  },
  {
    key: "risk-overview",
    label: "风险工作台",
    path: "/risk-overview",
    icon: "risk",
    description: "风险一级首页：聚合风险张量、集中度和现金流预测状态。",
    readiness: "live",
    readinessLabel: "已开放",
    readinessNote: "一级首页只做风险摘要与下钻，不在前端补算正式风险指标。",
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
    key: "performance-home",
    label: "绩效工作台",
    path: "/performance",
    icon: "kpi",
    description: "绩效一级首页：聚合 KPI、团队绩效、业务与产品损益入口。",
    readiness: "live",
    readinessLabel: "已开放",
    readinessNote: "一级首页展示绩效读链路状态，不重建 KPI 计分公式。",
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
    label: "正式损益",
    path: "/pnl",
    icon: "analysis",
    description: "正式损益汇总、固收明细与非标桥接明细",
    readiness: "live",
    readinessLabel: "已开放",
    readinessNote: "已接正式损益日期、overview 与明细读链路；页面展示后端结果和 result_meta，不在前端重算。",
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
    key: "pnl-by-business-insights",
    label: "业务结构与FTP后收益分析",
    path: "/pnl-by-business-insights",
    icon: "analysis",
    description: "业务种类集中度、负FTP持续性、份额漂移与规模—FTP后收益正式结构分析。",
    readiness: "live",
    readinessLabel: "已开放",
    readinessNote: "读取 /api/pnl/by-business-insights；正式指标仅按已批准定义展示，未追溯 FI 趋势保持为独立诊断。",
  },
  {
    key: "agent",
    label: "MOSS Chat",
    path: "/agent",
    icon: "agent",
    description: "像聊天一样提问，需要时再展开证据、运行细节和页面上下文。",
    readiness: "gated",
    readinessLabel: "受控试用",
    readinessNote:
      "仅在开发态显式开启前端开关时开放；默认与生产环境保持关闭，后端权限和开关继续 fail closed。",
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
  return sections.find((section) => pathMatchesWorkbenchSection(section.path, resolved)) ?? null;
}

export function resolveWorkbenchGroupKey(section: WorkbenchSection): WorkbenchGroupKey {
  return workbenchSectionGroups[section.key] ?? "overview";
}

type AgentFrontendEnvironment = Pick<ImportMetaEnv, "DEV" | "VITE_MOSS_AGENT_FRONTEND_ENABLED">;

export function isAgentFrontendEnabled(
  environment: AgentFrontendEnvironment = import.meta.env,
) {
  return (
    environment.DEV === true &&
    environment.VITE_MOSS_AGENT_FRONTEND_ENABLED === "true"
  );
}

export function getVisibleWorkbenchNavigation(
  environment: AgentFrontendEnvironment = import.meta.env,
) {
  return workbenchNavigation.filter(
    (section) =>
      section.navigationVisibility !== "hidden" ||
      (section.key === "agent" && isAgentFrontendEnabled(environment)),
  );
}

export const visibleWorkbenchNavigation = getVisibleWorkbenchNavigation();

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
  if (!currentSection) {
    return null;
  }

  return (
    primaryWorkbenchNavigationGroups.find(
      (group) => resolveWorkbenchGroupKey(currentSection) === group.key,
    ) ?? primaryWorkbenchNavigationGroups[0]
  );
}
