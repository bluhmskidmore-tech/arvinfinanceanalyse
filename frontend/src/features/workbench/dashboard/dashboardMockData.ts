/** 经营驾驶舱首页：API 缺字段时的集中 mock（禁止散落在 JSX）。 */

export const DASHBOARD_COCKPIT_IMPROVEMENT_NOTES = [
  "信息分层重构：核心KPI前置，宏观脉搏强化，减少噪音干扰。",
  "宏观-债市-组合联动：宏观指标与组合表现联动展示，支持快速判断市场驱动因素。",
  "风险预警前置：风险雷达和预警列表前置，关键风险早发现。",
  "指标口径统一：统一关键指标展示口径和取数逻辑。",
  "钻取路径清晰：支持从指标到明细的快速穿透分析。",
] as const;

export const DASHBOARD_COCKPIT_HEADER_STATUS = {
  dataUpdatedAt: "09:15",
  marketStatus: "市场已收盘",
  notificationCount: 12,
} as const;

export const DASHBOARD_COCKPIT_REPORT_DATE = "2026-04-30";

export type DashboardCockpitNavItem = {
  id: string;
  label: string;
  path: string;
};

export type DashboardCockpitNavGroup = {
  id: string;
  label: string;
  items: readonly DashboardCockpitNavItem[];
};

export const DASHBOARD_COCKPIT_NAV_GROUPS: readonly DashboardCockpitNavGroup[] = [
  {
    id: "overview",
    label: "",
    items: [{ id: "dashboard", label: "经营驾驶舱", path: "/" }],
  },
  {
    id: "portfolio",
    label: "组合与监控",
    items: [
      { id: "workbench", label: "组合工作台", path: "/balance-analysis" },
      { id: "market", label: "市场工作台", path: "/cross-asset" },
      { id: "risk", label: "风险工作台", path: "/risk-tensor" },
      { id: "performance", label: "绩效工作台", path: "/kpi" },
      { id: "liability", label: "资金与负债", path: "/liability-analytics" },
    ],
  },
  {
    id: "analytics",
    label: "分析与归因",
    items: [
      { id: "pnl-attribution", label: "收益归因", path: "/pnl-attribution" },
      { id: "duration", label: "久期与利率", path: "/bond-analysis" },
      { id: "credit", label: "信用与利差", path: "/bond-analysis" },
      { id: "product-pnl", label: "产品分析", path: "/product-category-pnl" },
    ],
  },
  {
    id: "reports",
    label: "报表与数据",
    items: [
      { id: "reports", label: "报表中心", path: "/reports" },
      { id: "data-center", label: "数据中心", path: "/platform-config" },
      { id: "cube", label: "自助查询", path: "/cube-query" },
      { id: "dictionary", label: "数据字典", path: "/platform-config" },
    ],
  },
  {
    id: "system",
    label: "系统管理",
    items: [
      { id: "alerts", label: "预警管理", path: "/decision-items" },
      { id: "permissions", label: "权限管理", path: "/platform-config" },
      { id: "settings", label: "系统设置", path: "/platform-config" },
    ],
  },
];

export type DashboardExposureRowMock = {
  id: string;
  account: string;
  type: string;
  assetScale: string;
  weight: string;
  duration: string;
  dv01: string;
  dailyPnl: string;
  tone: "positive" | "negative" | "neutral" | "warning";
};

export const DASHBOARD_EXPOSURE_ROWS_MOCK: readonly DashboardExposureRowMock[] = [
  {
    id: "exp-1",
    account: "组合A期",
    type: "组合",
    assetScale: "3,438.23",
    weight: "92.71%",
    duration: "4.14",
    dv01: "10,615.59",
    dailyPnl: "-4.97",
    tone: "negative",
  },
  {
    id: "exp-2",
    account: "信用策略账户",
    type: "策略",
    assetScale: "1,005.70",
    weight: "27.12%",
    duration: "2.40",
    dv01: "2,357.21",
    dailyPnl: "+10.07",
    tone: "positive",
  },
  {
    id: "exp-3",
    account: "利率策略账户",
    type: "策略",
    assetScale: "1,344.90",
    weight: "36.23%",
    duration: "5.63",
    dv01: "7,366.72",
    dailyPnl: "+62.99",
    tone: "positive",
  },
  {
    id: "exp-4",
    account: "货币与同业",
    type: "现金管理",
    assetScale: "1,087.63",
    weight: "29.31%",
    duration: "0.83",
    dv01: "1,916.67",
    dailyPnl: "--",
    tone: "neutral",
  },
  {
    id: "exp-5",
    account: "风险总计",
    type: "--",
    assetScale: "3,708.10",
    weight: "100.00%",
    duration: "4.14",
    dv01: "10,615.59",
    dailyPnl: "-4.97",
    tone: "negative",
  },
];

export const DASHBOARD_PORTFOLIO_STATS_MOCK = [
  { id: "books", label: "组合数", value: "38 个" },
  { id: "positions", label: "持仓债券", value: "1,256 只" },
  { id: "coupon", label: "平均票面利率", value: "2.85%" },
  { id: "rating", label: "主导评级（Top1）", value: "AAA" },
] as const;

export const DASHBOARD_ASSET_BARS_MOCK = [
  { id: "rate", label: "利率债", pct: 36.3, value: "1,345.62 亿", color: "#1D4E89" },
  { id: "credit", label: "信用债", pct: 42.9, value: "1,587.83 亿", color: "#16835F" },
  { id: "cd", label: "同业存单", pct: 14.4, value: "534.21 亿", color: "#C77700" },
  { id: "other", label: "其他", pct: 6.4, value: "240.44 亿", color: "#6B7280" },
] as const;

export const DASHBOARD_INTERBANK_MOCK = {
  assets: "219.91 亿",
  liabilities: "679.07 亿",
  netPosition: "-459.16 亿",
} as const;

export const DASHBOARD_ATTRIBUTION_TABS_MOCK = [
  {
    id: "day",
    label: "日度",
    pnl: "-368.09 万",
    change: "-223.30 万",
    yield: "-0.10bp",
    changeTone: "down",
  },
  {
    id: "week",
    label: "周度",
    pnl: "-1,286.42 万",
    change: "-412.18 万",
    yield: "-0.35bp",
    changeTone: "down",
  },
  {
    id: "month",
    label: "月度",
    pnl: "+6,428.31 万",
    change: "+1,032.45 万",
    yield: "+1.73bp",
    changeTone: "up",
  },
  {
    id: "ytd",
    label: "YTD",
    pnl: "+29.71 亿",
    change: "+1.82 亿",
    yield: "+0.81%",
    changeTone: "up",
  },
] as const;

export const DASHBOARD_ATTRIBUTION_WATERFALL_MOCK = [
  { id: "rate-change", label: "利率变动", value: "-512.34", status: "demo" as const, tone: "negative" as const },
  { id: "credit-spread", label: "信用利差", value: "+286.21", status: "demo" as const, tone: "positive" as const },
  { id: "coupon", label: "票息收入", value: "+198.67", status: "demo" as const, tone: "positive" as const },
  { id: "trading", label: "交易盈亏", value: "-223.46", status: "demo" as const, tone: "negative" as const },
  { id: "fees", label: "其他费用", value: "-116.14", status: "demo" as const, tone: "negative" as const },
  { id: "total", label: "综合贡献", value: "-368.09", status: "demo" as const, tone: "negative" as const },
] as const;

export const DASHBOARD_ATTRIBUTION_NOTE_MOCK = [
  "利率上行导致组合估值回落，对损益形成主要拖累。",
  "信用利差收窄贡献正收益，主要来自中高等级信用债估值修复。",
  "当日新增买入利率债 32.45 亿，卖出信用债 18.30 亿，久期小幅上升。",
] as const;

export const DASHBOARD_RISK_ALERT_COUNTS_MOCK = [
  { id: "high", label: "高风险预警", count: 2, tone: "warn" },
  { id: "medium", label: "中风险预警", count: 6, tone: "flat" },
  { id: "low", label: "低风险预警", count: 3, tone: "down" },
] as const;

export const DASHBOARD_RISK_TODOS_MOCK = [
  { id: "duration-limit", title: "组合久期超限处理", priority: "高", status: "需处理", path: "/decision-items" },
  { id: "put-confirm", title: "回售行权确认（5笔）", priority: "中", status: "待确认", path: "/decision-items" },
  { id: "credit-valuation", title: "信用债估值调整复核", priority: "中", status: "待复核", path: "/decision-items" },
  { id: "monthly-report", title: "月度持仓规模上报", priority: "低", status: "待上报", path: "/reports" },
] as const;

export const DASHBOARD_WATCHLIST_MOCK = [
  { id: "fast-duration-fall", label: "久期回落较快组合", count: "2", note: "组合", path: "/bond-analysis" },
  { id: "credit-spread-widen", label: "信用利差走阔品种", count: "3", note: "品种", path: "/bond-analysis" },
  { id: "weak-liquidity", label: "流动性偏弱债券", count: "4", note: "债券", path: "/positions" },
  { id: "high-turnover", label: "高换手率债券", count: "2", note: "债券", path: "/ledger-pnl" },
  { id: "large-net-buy", label: "大额净买入主体", count: "1", note: "主体", path: "/positions" },
] as const;

export type DashboardBalanceMetricMock = {
  id: string;
  label: string;
  value: string;
  delta: string;
  tone: "positive" | "negative" | "neutral" | "warning";
};

export const DASHBOARD_BALANCE_METRICS_MOCK: readonly DashboardBalanceMetricMock[] = [
  { id: "assets", label: "总资产规模", value: "3,708.10 亿", delta: "较昨日 +22.30 亿", tone: "warning" },
  { id: "ytd-pnl", label: "年度损益", value: "+29.71 亿", delta: "YTD收益率 0.81%", tone: "positive" },
  { id: "nim", label: "净息差", value: "1.76%", delta: "+0.02bp", tone: "positive" },
  { id: "capital", label: "资本占用", value: "456.32 亿", delta: "+3.21 亿", tone: "warning" },
  { id: "leverage", label: "杠杆率", value: "102.35%", delta: "稳定", tone: "neutral" },
  { id: "liquidity", label: "流动性覆盖率", value: "182.67%", delta: "安全垫充足", tone: "positive" },
  { id: "core-tier1", label: "核心一级资本充足率", value: "11.32%", delta: "监管线以上", tone: "positive" },
  { id: "rwa", label: "风险加权资产", value: "1,892.45 亿", delta: "较昨日 +8.12 亿", tone: "warning" },
];

export type DashboardQuickDrilldownMock = {
  id: string;
  label: string;
  description: string;
  path: string;
};

export const DASHBOARD_QUICK_DRILLDOWN_MOCK: readonly DashboardQuickDrilldownMock[] = [
  { id: "positions", label: "持仓明细", description: "债券与客户下钻", path: "/positions" },
  { id: "attribution", label: "收益归因分析", description: "规模/利率/交易拆解", path: "/pnl-attribution" },
  { id: "duration", label: "久期分布", description: "久期与利率暴露", path: "/bond-analysis" },
  { id: "credit", label: "信用敞口分析", description: "评级/主体/利差", path: "/bond-analysis" },
  { id: "industry", label: "行业分布", description: "行业集中度", path: "/positions" },
  { id: "trades", label: "交易流水", description: "买卖与换手", path: "/ledger-pnl" },
  { id: "reports", label: "报表中心", description: "导出与订阅", path: "/reports" },
  { id: "cube", label: "自助查询", description: "多维聚合", path: "/cube-query" },
];

export const DASHBOARD_RISK_RADAR_MOCK = {
  dimensions: ["利率风险", "信用风险", "流动性风险", "集中度风险", "杠杆风险"],
  values: [72, 58, 65, 81, 48],
} as const;

/** 8 张宏观市场脉搏：API 失败或空序列时的首屏兜底（标注演示）。 */
export const DASHBOARD_MARKET_PULSE_MOCK = [
  { id: "cgb10y", label: "10年国债", value: "1.76%", delta: "+0.02bp", deltaTone: "up" as const, sparkline: [1.72, 1.73, 1.74, 1.73, 1.75, 1.76, 1.75, 1.76, 1.77, 1.76, 1.75, 1.76], statusLabel: "演示" },
  { id: "dr007", label: "DR007", value: "1.29%", delta: "-1bp", deltaTone: "down" as const, sparkline: [1.36, 1.34, 1.32, 1.31, 1.3, 1.3, 1.29, 1.28, 1.29, 1.29, 1.28, 1.29], statusLabel: "演示" },
  { id: "slope", label: "1Y-10Y利差", value: "-26.2bp", delta: "+3bp", deltaTone: "up" as const, sparkline: [-30, -29, -28, -28, -27, -26, -27, -26, -25, -26, -26, -26.2], statusLabel: "演示" },
  { id: "us10y", label: "美债10Y", value: "4.35%", delta: "-2.1bp", deltaTone: "down" as const, sparkline: [4.42, 4.4, 4.39, 4.38, 4.37, 4.36, 4.36, 4.35, 4.34, 4.35, 4.34, 4.35], statusLabel: "演示" },
  { id: "usdcny", label: "人民币汇率", value: "7.2431", delta: "+0.0021", deltaTone: "up" as const, sparkline: [7.236, 7.238, 7.239, 7.24, 7.241, 7.242, 7.241, 7.242, 7.243, 7.244, 7.243, 7.2431], statusLabel: "演示" },
  { id: "brent", label: "原油 Brent", value: "118.26", delta: "-0.58", deltaTone: "down" as const, sparkline: [119.8, 119.4, 119.1, 118.9, 118.5, 118.4, 118.7, 118.2, 118.1, 118.4, 118.3, 118.26], statusLabel: "演示" },
  { id: "csi300", label: "A股指数 沪深300", value: "3,762.75", delta: "+0.82%", deltaTone: "up" as const, sparkline: [3718, 3724, 3730, 3732, 3740, 3745, 3750, 3753, 3758, 3762, 3760, 3762.75], statusLabel: "演示" },
  { id: "credit-spread", label: "信用利差 中短票AAA", value: "69.8bp", delta: "-0.6bp", deltaTone: "down" as const, sparkline: [72, 71.4, 71, 70.8, 70.5, 70.2, 70, 69.8, 69.7, 69.9, 69.8, 69.8], statusLabel: "演示" },
] as const;

export const DASHBOARD_PRODUCT_PNL_SERIES_MOCK = {
  months: ["1月", "2月", "3月", "4月", "5月", "6月", "7月", "8月", "9月", "10月", "11月", "12月"],
  series: [
    { id: "rate", name: "利率债", values: [-0.5, 0.2, 0.7, 0.4, 0.3, 0.8, 0.5] },
    { id: "credit", name: "信用债", values: [0.1, 0.25, 0.2, 0.18, 0.22, 0.16, -0.2] },
    { id: "interbank", name: "同业存单", values: [-0.1, -0.05, -0.1, -0.08, -0.1, -0.06, -0.28] },
    { id: "other", name: "其他", values: [-0.3, -0.2, -0.22, -0.18, -0.16, -0.24, -0.6] },
    { id: "total", name: "合计", values: [-0.8, 0.2, 0.5, 0.32, 0.26, 0.66, -1.08] },
  ],
} as const;
