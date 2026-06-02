import { getPortfolioModuleDrilldowns } from "./portfolioModuleDrilldowns";
import { getMarketModuleDrilldowns } from "./marketModuleDrilldowns";

export type ModuleWorkbenchHomeKind =
  | "portfolio"
  | "market"
  | "risk"
  | "performance"
  | "governance";

export type ModuleHomeDrilldown = {
  key: string;
  label: string;
  path: string;
  description: string;
  statusLabel: string;
  icon?: string;
};

export type ModuleWorkbenchHomeConfig = {
  kind: ModuleWorkbenchHomeKind;
  title: string;
  shortTitle: string;
  question: string;
  summary: string;
  sourceScope: string;
  kpiKeys: string[];
  sourceKeys: string[];
  briefingTitles: string[];
  drilldowns: ModuleHomeDrilldown[];
  dataNotes: string[];
};

export const moduleWorkbenchHomeConfigs: Record<
  ModuleWorkbenchHomeKind,
  ModuleWorkbenchHomeConfig
> = {
  portfolio: {
    kind: "portfolio",
    title: "组合工作台",
    shortTitle: "组合",
    question: "规模、久期、结构与损益 — 首页读链路汇总",
    summary:
      "首页聚合资产负债、债券总览、风险/收益结构、Basis 分解与损益归因摘要；逐券明细与完整归因瀑布仍进入下钻页。",
    sourceScope: "资产负债 / 债券总览 / 持仓 / 损益归因",
    kpiKeys: ["balanceTotal", "assetMarket", "liabilityMarket", "bondMarket"],
    sourceKeys: ["balance", "bondDashboard", "positions", "pnlAttribution"],
    briefingTitles: ["规模与错配", "风险敏感度", "收益解释"],
    drilldowns: getPortfolioModuleDrilldowns(),
    dataNotes: [
      "不在首页补算正式金融指标；只展示既有接口返回的数值、日期和状态。",
      "组合首页缺数时保留缺数状态，引导进入对应下钻页面核验。",
    ],
  },
  market: {
    kind: "market",
    title: "市场工作台",
    shortTitle: "市场",
    question: "今天利率、跨资产和新闻事件是否改变组合阅读顺序？",
    summary:
      "首页聚合市场数据、跨资产、宏观工具、股票分析和新闻事件的可用状态与关键行情。",
    sourceScope: "Choice/Tushare 市场数据 / 跨资产 / 新闻事件",
    kpiKeys: ["macroSeries", "tenYearRate", "rateSeries", "catalogSeries"],
    sourceKeys: ["choiceLatest", "marketRates", "marketCatalog", "newsEvents"],
    briefingTitles: ["利率快照", "跨资产传导", "事件状态"],
    drilldowns: getMarketModuleDrilldowns(),
    dataNotes: [
      "市场首页只引用行情/事件接口的返回状态，不把观察口径提升为正式经营结论。",
      "旧书签 /market 继续跳转到 /market-data。",
    ],
  },
  risk: {
    kind: "risk",
    title: "风险工作台",
    shortTitle: "风险",
    question: "当前组合风险、集中度和流动性是否触发优先处置？",
    summary:
      "首页聚合风险张量、集中度和现金流预测的核心状态；明细仍在风险张量等页面展开。",
    sourceScope: "风险张量 / 集中度 / 现金流预测",
    kpiKeys: ["riskReportDates", "portfolioDv01", "modifiedDuration", "liquidityGap"],
    sourceKeys: ["riskDates", "riskTensor", "cashflow", "concentration"],
    briefingTitles: ["久期与 DV01", "信用与集中度", "现金流压力"],
    drilldowns: [
      {
        key: "risk-tensor",
        label: "风险张量",
        path: "/risk-tensor",
        description: "查看正式风险张量、KRD、CS01 与质量标记。",
        statusLabel: "正式链路",
      },
      {
        key: "concentration-monitor",
        label: "集中度监控",
        path: "/concentration-monitor",
        description: "查看发行人、行业、评级和限额相关集中度。",
        statusLabel: "已开放",
      },
      {
        key: "cashflow-projection",
        label: "现金流预测",
        path: "/cashflow-projection",
        description: "查看未来现金流、久期缺口和再投资风险。",
        statusLabel: "已开放",
      },
    ],
    dataNotes: [
      "风险首页不以前端估算替代监管口径 DV01 或现金流压力指标。",
      "风险报告日读取失败时，首页只显示失败状态，不使用前端补数。",
    ],
  },
  performance: {
    kind: "performance",
    title: "绩效工作台",
    shortTitle: "绩效",
    question: "本期 KPI、团队贡献和业务损益是否支持经营复盘？",
    summary:
      "首页聚合 KPI、团队绩效、业务损益和产品损益的摘要入口，不替代考核明细。",
    sourceScope: "KPI / 团队绩效 / 业务损益 / 产品损益",
    kpiKeys: ["ownerCount", "kpiScore", "kpiMetricCount", "businessPnl"],
    sourceKeys: ["kpiOwners", "kpiSummary", "pnlByBusiness", "teamPerformance"],
    briefingTitles: ["KPI 完成", "团队贡献", "损益复盘"],
    drilldowns: [
      {
        key: "kpi-performance",
        label: "绩效考核",
        path: "/kpi",
        description: "查看 KPI 指标、抓取、计分和溯源。",
        statusLabel: "已开放",
      },
      {
        key: "team-performance",
        label: "团队绩效",
        path: "/team-performance",
        description: "查看团队贡献、中心映射和经营指标解释。",
        statusLabel: "已开放",
      },
      {
        key: "pnl-by-business",
        label: "业务种类损益",
        path: "/pnl-by-business",
        description: "按业务种类查看正式 FI 损益和规模读链路。",
        statusLabel: "临时开放",
      },
      {
        key: "product-category-pnl",
        label: "产品分析",
        path: "/product-category-pnl",
        description: "查看产品类别损益与场景分析入口。",
        statusLabel: "临时开放",
      },
    ],
    dataNotes: [
      "绩效首页展示 KPI 与损益接口已经返回的汇总，不在首页重建考核公式。",
      "若 KPI owner 或业务损益为空，首页明确显示缺数状态。",
    ],
  },
  governance: {
    kind: "governance",
    title: "报表与数据",
    shortTitle: "数据",
    question: "当前数据健康、来源状态和报表能力是否可支撑交付？",
    summary:
      "首页聚合数据中心健康、数据源状态、自助查询和报表中心规划状态；未接入报表能力保持规划中。",
    sourceScope: "健康检查 / 数据源 / Cube 查询 / 报表规划",
    kpiKeys: ["healthLive", "healthSummary", "sourceCount", "cubeDimensions"],
    sourceKeys: ["health", "sourceFoundation", "cubeQuery", "reports"],
    briefingTitles: ["系统健康", "数据源状态", "报表规划"],
    drilldowns: [
      {
        key: "platform-config",
        label: "数据中心",
        path: "/platform-config",
        description: "查看系统健康检查、数据源状态和中台配置。",
        statusLabel: "已开放",
      },
      {
        key: "cube-query",
        label: "自助查询",
        path: "/cube-query",
        description: "对已覆盖事实表做维度聚合、筛选和下钻。",
        statusLabel: "正式链路",
      },
      {
        key: "reports-center",
        label: "报表中心规划",
        path: "/reports",
        description: "统一报表与导出清单仍在规划；不伪造报表数据。",
        statusLabel: "规划中",
      },
    ],
    dataNotes: [
      "没有后端正式接口的报表能力只显示为规划/待接入状态。",
      "数据健康和来源状态来自既有健康检查与 source foundation 读链路。",
    ],
  },
};
