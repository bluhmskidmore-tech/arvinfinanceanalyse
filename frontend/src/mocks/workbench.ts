import type {
  AlertsPayload,
  ContributionPayload,
  OverviewPayload,
  PlaceholderSnapshot,
  PnlAttributionPayload,
  RiskOverviewPayload,
  SummaryPayload,
} from "../api/contracts";

export const overviewPayload: OverviewPayload = {
  title: "经营总览",
  metrics: [
    {
      id: "aum",
      label: "资产规模",
      value: "1,023.47 亿",
      delta: "+2.35%",
      tone: "positive",
      detail: "较上月保持温和扩张，当前页面仅展示受控摘要值。",
    },
    {
      id: "yield",
      label: "年内收益",
      value: "+12.63 亿",
      delta: "+8.72%",
      tone: "positive",
      detail: "收益口径后续由正式后端替换，前端只消费结果。",
    },
    {
      id: "goal",
      label: "目标完成率",
      value: "63.1%",
      delta: "目标 20.00 亿",
      tone: "neutral",
      detail: "保留目标追踪入口，不在浏览器端推导正式口径。",
    },
    {
      id: "risk",
      label: "风险预算使用率",
      value: "68.7%",
      delta: "+3.6pp",
      tone: "warning",
      detail: "展示受控风险摘要，为后续风险页预留数据入口。",
    },
  ],
};

export const summaryPayload: SummaryPayload = {
  title: "本周管理摘要",
  narrative:
    "本周组合收益延续修复，收益主要来自久期与票息贡献。风险端仍需关注信用集中度与流动性预留，当前页面不在前端拼接正式分析口径。",
  points: [
    {
      id: "income",
      label: "收益",
      tone: "positive",
      text: "利率下行仍是收益主驱动，票息贡献保持稳定。",
    },
    {
      id: "risk",
      label: "风险",
      tone: "warning",
      text: "信用集中度抬升，需继续压实预警边界。",
    },
    {
      id: "action",
      label: "建议",
      tone: "neutral",
      text: "保留流动性缓冲，避免在高波动窗口放大仓位。",
    },
  ],
};

export const pnlAttributionPayload: PnlAttributionPayload = {
  title: "收益归因",
  total: "12.63 亿",
  segments: [
    { id: "carry", label: "Carry", amount: 5.21, display_amount: "+5.21 亿", tone: "positive" },
    { id: "roll", label: "Roll-down", amount: 2.18, display_amount: "+2.18 亿", tone: "positive" },
    { id: "credit", label: "信用利差", amount: 1.42, display_amount: "+1.42 亿", tone: "positive" },
    { id: "trading", label: "交易损益", amount: -0.85, display_amount: "-0.85 亿", tone: "negative" },
    { id: "other", label: "其他", amount: 0.67, display_amount: "+0.67 亿", tone: "neutral" },
  ],
};

export const riskOverviewPayload: RiskOverviewPayload = {
  title: "风险全景",
  signals: [
    {
      id: "duration",
      label: "久期风险",
      value: "32.1%",
      status: "stable",
      detail: "久期暴露仍处于本周可接受区间。",
    },
    {
      id: "leverage",
      label: "杠杆风险",
      value: "54.3%",
      status: "watch",
      detail: "杠杆使用率上行，需结合资金窗口观察。",
    },
    {
      id: "credit",
      label: "信用集中度",
      value: "78.9%",
      status: "warning",
      detail: "集中度已逼近预警阈值。",
    },
    {
      id: "liquidity",
      label: "流动性风险",
      value: "41.2%",
      status: "stable",
      detail: "流动性缓冲仍具备调节空间。",
    },
  ],
};

export const contributionPayload: ContributionPayload = {
  title: "团队 / 账户 / 策略贡献",
  rows: [
    {
      id: "rates",
      name: "利率组",
      owner: "按团队",
      contribution: "+4.21 亿",
      completion: 65,
      status: "核心拉动",
    },
    {
      id: "credit",
      name: "信用组",
      owner: "按团队",
      contribution: "+2.18 亿",
      completion: 58,
      status: "稳定贡献",
    },
    {
      id: "trading",
      name: "交易组",
      owner: "按团队",
      contribution: "+0.32 亿",
      completion: 31,
      status: "波动偏大",
    },
  ],
};

export const alertsPayload: AlertsPayload = {
  title: "预警与事件",
  items: [
    {
      id: "a1",
      severity: "high",
      title: "久期敞口接近上限",
      occurred_at: "10:15",
      detail: "账户 B 久期 6.82，接近上限 7.00。",
    },
    {
      id: "a2",
      severity: "medium",
      title: "信用集中度预警",
      occurred_at: "09:48",
      detail: "城投敞口 23.5%，接近阈值 25%。",
    },
    {
      id: "a3",
      severity: "medium",
      title: "杠杆使用率上升",
      occurred_at: "09:30",
      detail: "当前 1.82x，较上周上升 0.06x。",
    },
  ],
};

export const placeholderSnapshots: Record<string, PlaceholderSnapshot> = {
  dashboard: {
    title: "管理层驾驶舱",
    summary: "当前主页面已经切换为可连接真实后端 endpoint 的执行舱。",
    highlights: [
      "概览与摘要采用独立 query。",
      "归因、风险、贡献和预警具备空态与错误态。",
      "其余工作台仍保持薄占位，避免越界到厚业务页面。",
    ],
  },
  "operations-analysis": {
    title: "经营分析",
    summary: "该工作台将在后续阶段接入真实薄页面。",
    highlights: ["经营摘要", "收益结构", "业务观察"],
  },
  "risk-overview": {
    title: "风险总览",
    summary: "该工作台将在后续阶段接入真实薄页面。",
    highlights: ["风险热区", "风险趋势", "治理提示"],
  },
  "team-performance": {
    title: "团队绩效",
    summary: "该工作台将在后续阶段接入真实薄页面。",
    highlights: ["团队贡献", "账户视角", "策略视角"],
  },
  "decision-matters": {
    title: "决策事项",
    summary: "该工作台将在后续阶段接入真实薄页面。",
    highlights: ["待决策队列", "事项状态", "办理建议"],
  },
  "bond-analysis": {
    title: "债券分析",
    summary: "该工作台将在后续阶段接入真实薄页面。",
    highlights: ["券种观察", "久期视角", "估值要点"],
  },
  "platform-config": {
    title: "中台配置",
    summary: "该工作台将在后续阶段接入真实薄页面。",
    highlights: ["口径治理", "权限配置", "契约维护"],
  },
  "market-data": {
    title: "市场数据",
    summary: "该工作台将在后续阶段接入真实薄页面。",
    highlights: ["利率曲线", "宏观日历", "市场快照"],
  },
};
