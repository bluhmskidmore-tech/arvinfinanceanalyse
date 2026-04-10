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
  title: "经营总览（演示）",
  metrics: [
    {
      id: "aum",
      label: "示例指标一",
      value: "—",
      delta: "—",
      tone: "neutral",
      detail: "静态演示字段，不代表任何业务口径。",
    },
    {
      id: "yield",
      label: "示例指标二",
      value: "—",
      delta: "—",
      tone: "neutral",
      detail: "静态演示字段，不代表任何业务口径。",
    },
    {
      id: "goal",
      label: "示例指标三",
      value: "—",
      delta: "—",
      tone: "neutral",
      detail: "静态演示字段，不代表任何业务口径。",
    },
    {
      id: "risk",
      label: "示例指标四",
      value: "—",
      delta: "—",
      tone: "neutral",
      detail: "静态演示字段，不代表任何业务口径。",
    },
  ],
};

export const summaryPayload: SummaryPayload = {
  title: "管理摘要（演示）",
  narrative:
    "以下为前端壳层占位文案，用于展示排版与异步状态，请勿当作分析结论或正式口径。",
  points: [
    {
      id: "income",
      label: "要点一",
      tone: "neutral",
      text: "演示：后续替换为后端返回的摘要条目。",
    },
    {
      id: "risk",
      label: "要点二",
      tone: "neutral",
      text: "演示：后续替换为后端返回的摘要条目。",
    },
    {
      id: "action",
      label: "要点三",
      tone: "neutral",
      text: "演示：后续替换为后端返回的摘要条目。",
    },
  ],
};

export const pnlAttributionPayload: PnlAttributionPayload = {
  title: "收益归因（演示）",
  total: "—",
  segments: [
    { id: "a", label: "分段 A", amount: 0, display_amount: "—", tone: "neutral" },
    { id: "b", label: "分段 B", amount: 0, display_amount: "—", tone: "neutral" },
    { id: "c", label: "分段 C", amount: 0, display_amount: "—", tone: "neutral" },
  ],
};

export const riskOverviewPayload: RiskOverviewPayload = {
  title: "风险全景（演示）",
  signals: [
    {
      id: "duration",
      label: "示例信号一",
      value: "—",
      status: "stable",
      detail: "演示占位，不代表监控结果。",
    },
    {
      id: "leverage",
      label: "示例信号二",
      value: "—",
      status: "watch",
      detail: "演示占位，不代表监控结果。",
    },
    {
      id: "credit",
      label: "示例信号三",
      value: "—",
      status: "warning",
      detail: "演示占位，不代表监控结果。",
    },
  ],
};

export const contributionPayload: ContributionPayload = {
  title: "贡献列表（演示）",
  rows: [
    {
      id: "rates",
      name: "示例行一",
      owner: "演示",
      contribution: "—",
      completion: 0,
      status: "占位",
    },
    {
      id: "credit",
      name: "示例行二",
      owner: "演示",
      contribution: "—",
      completion: 0,
      status: "占位",
    },
  ],
};

export const alertsPayload: AlertsPayload = {
  title: "预警与事件（演示）",
  items: [
    {
      id: "a1",
      severity: "low",
      title: "示例事件一",
      occurred_at: "—",
      detail: "演示占位，非真实告警。",
    },
    {
      id: "a2",
      severity: "low",
      title: "示例事件二",
      occurred_at: "—",
      detail: "演示占位，非真实告警。",
    },
  ],
};

const placeholderSummary =
  "此工作台为壳层占位：路由与布局已就绪，业务页面与契约字段后续接入。";

export const placeholderSnapshots: Record<string, PlaceholderSnapshot> = {
  dashboard: {
    title: "管理层驾驶舱",
    summary:
      "首页演示：可切换数据源适配器并消费后端契约；展示层只渲染返回结果，不推导业务口径。",
    highlights: [
      "独立查询与 loading / empty / error / 重试。",
      "懒加载分区降低首屏体积。",
      "其余菜单项保持薄占位页面。",
    ],
  },
  "operations-analysis": {
    title: "经营分析",
    summary: placeholderSummary,
    highlights: ["规划要点一", "规划要点二", "规划要点三"],
  },
  "risk-overview": {
    title: "风险总览",
    summary: placeholderSummary,
    highlights: ["规划要点一", "规划要点二", "规划要点三"],
  },
  "team-performance": {
    title: "团队绩效",
    summary: placeholderSummary,
    highlights: ["规划要点一", "规划要点二", "规划要点三"],
  },
  "decision-matters": {
    title: "决策事项",
    summary: placeholderSummary,
    highlights: ["规划要点一", "规划要点二", "规划要点三"],
  },
  "bond-analysis": {
    title: "债券分析",
    summary: placeholderSummary,
    highlights: ["规划要点一", "规划要点二", "规划要点三"],
  },
  "platform-config": {
    title: "中台配置",
    summary: placeholderSummary,
    highlights: ["规划要点一", "规划要点二", "规划要点三"],
  },
  "market-data": {
    title: "市场数据",
    summary: placeholderSummary,
    highlights: ["规划要点一", "规划要点二", "规划要点三"],
  },
};
