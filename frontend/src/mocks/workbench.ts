import type {
  AlertsPayload,
  ContributionPayload,
  HomeSnapshotPayload,
  OverviewPayload,
  PlaceholderSnapshot,
  PnlAttributionPayload,
  RiskOverviewPayload,
  SummaryPayload,
  VerdictPayload,
} from "../api/contracts";

export const overviewPayload: OverviewPayload = {
  title: "经营总览（演示）",
  metrics: [
    {
      id: "aum",
      label: "示例指标一",
      value: { raw: null, unit: "yuan", display: "—", precision: 2, sign_aware: false },
      delta: { raw: null, unit: "pct", display: "—", precision: 2, sign_aware: true },
      tone: "neutral",
      detail: "静态演示字段，不代表任何业务口径。",
    },
    {
      id: "yield",
      label: "示例指标二",
      value: { raw: null, unit: "yuan", display: "—", precision: 2, sign_aware: false },
      delta: { raw: null, unit: "pct", display: "—", precision: 2, sign_aware: true },
      tone: "neutral",
      detail: "静态演示字段，不代表任何业务口径。",
    },
    {
      id: "goal",
      label: "示例指标三",
      value: { raw: null, unit: "yuan", display: "—", precision: 2, sign_aware: false },
      delta: { raw: null, unit: "pct", display: "—", precision: 2, sign_aware: true },
      tone: "neutral",
      detail: "静态演示字段，不代表任何业务口径。",
    },
    {
      id: "risk",
      label: "示例指标四",
      value: { raw: null, unit: "yuan", display: "—", precision: 2, sign_aware: false },
      delta: { raw: null, unit: "pct", display: "—", precision: 2, sign_aware: true },
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
  title: "经营贡献拆解（演示）",
  total: { raw: null, unit: "yuan", display: "—", precision: 2, sign_aware: true },
  segments: [
    {
      id: "a",
      label: "分段 A",
      amount: { raw: null, unit: "yuan", display: "—", precision: 2, sign_aware: true },
      tone: "neutral",
    },
    {
      id: "b",
      label: "分段 B",
      amount: { raw: null, unit: "yuan", display: "—", precision: 2, sign_aware: true },
      tone: "neutral",
    },
    {
      id: "c",
      label: "分段 C",
      amount: { raw: null, unit: "yuan", display: "—", precision: 2, sign_aware: true },
      tone: "neutral",
    },
  ],
};

export const mockVerdictPayload: VerdictPayload = {
  conclusion: "演示：首屏定调结论占位，用于展示 Pyramid 叙事结构。",
  tone: "neutral",
  reasons: [
    {
      label: "示例指标一",
      value: "—",
      detail: "静态演示字段，不代表任何业务口径。",
      tone: "neutral",
    },
  ],
  suggestions: [
    { text: "进入对应专题页继续下钻原因链条", link: null },
    { text: "关注信用利差与久期暴露", link: "/bond-analysis" },
  ],
};

export const riskOverviewPayload: RiskOverviewPayload = {
  title: "风险全景（演示）",
  signals: [
    {
      id: "duration",
      label: "示例信号一",
      value: { raw: null, unit: "ratio", display: "—", precision: 2, sign_aware: false },
      status: "stable",
      detail: "演示占位，不代表监控结果。",
    },
    {
      id: "leverage",
      label: "示例信号二",
      value: { raw: null, unit: "ratio", display: "—", precision: 2, sign_aware: false },
      status: "watch",
      detail: "演示占位，不代表监控结果。",
    },
    {
      id: "credit",
      label: "示例信号三",
      value: { raw: null, unit: "ratio", display: "—", precision: 2, sign_aware: false },
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
      contribution: { raw: null, unit: "yuan", display: "—", precision: 2, sign_aware: true },
      completion: 0,
      status: "占位",
    },
    {
      id: "credit",
      name: "示例行二",
      owner: "演示",
      contribution: { raw: null, unit: "yuan", display: "—", precision: 2, sign_aware: true },
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
      "独立查询与载入、空数据、错误、重试状态。",
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
    summary: "风险总览路由已保留，但当前风险张量与债券分析下钻物化结果尚未进入可用状态。",
    highlights: ["正式风险张量表未落地", "债券分析下钻结果未就绪", "当前阶段只保留入口与状态说明"],
  },
  "liability-analytics": {
    title: "负债结构分析",
    summary: "负债结构分析当前只保留兼容入口，不宣称已进入全仓第二阶段的正式主链消费面。",
    highlights: ["仍属兼容模块", "不把分析口径结果冒充正式切换", "待后续阶段定义后再晋升"],
  },
  "risk-tensor": {
    title: "风险张量",
    summary: "风险张量页依赖的正式风险张量表尚未物化，当前不展示失败查询结果，只保留阶段说明。",
    highlights: ["依赖表未落地", "不在前端补算风险指标", "完成物化后再切回真实页面"],
  },
  "team-performance": {
    title: "团队绩效",
    summary: "团队绩效仍是壳层占位模块，当前只保留入口和规划说明。",
    highlights: ["无真实读链路", "无正式指标计算", "后续按治理面能力补齐"],
  },
  "decision-matters": {
    title: "决策事项",
    summary: placeholderSummary,
    highlights: ["规划要点一", "规划要点二", "规划要点三"],
  },
  "bond-analysis": {
    title: "债券分析",
    summary: "债券分析驾驶舱仍未到可展示阶段，当前不直接暴露未完成的债券分析页面。",
    highlights: ["债券分析物化表未就绪", "入口保留但不触发失败接口", "待治理读模型稳定后恢复"],
  },
  "product-category-pnl": {
    title: "产品损益",
    summary: "产品损益页面路由已搭好，但当前读模型还没有可消费报告日，因此先落回占位说明。",
    highlights: ["报告日列表为空", "不展示空表和错误态", "等读模型物化后恢复"],
  },
  pnl: {
    title: "损益明细",
    summary: "损益明细依赖的正式损益事实表尚未物化，当前页面不再发失败请求。",
    highlights: ["正式固收损益事实表未落地", "非标损益桥接事实表未落地", "完成物化后恢复真实工作台"],
  },
  "pnl-bridge": {
    title: "损益桥接",
    summary: "损益桥接仍处于预留阶段，当前只保留模块说明，避免把未完成页面当成可用功能。",
    highlights: ["桥接结果未稳定", "不暴露失败接口", "后续以正式读模型为准切回"],
  },
  "platform-config": {
    title: "中台配置",
    summary: "中台配置当前仍为占位入口，暂不展示未完成的治理页细节。",
    highlights: ["仅保留入口", "不展示假数据", "待治理面成熟后恢复真实页面"],
  },
  "market-data": {
    title: "市场数据",
    summary: placeholderSummary,
    highlights: ["规划要点一", "规划要点二", "规划要点三"],
  },
  "cube-query": {
    title: "多维查询",
    summary: "Cube query 入口保留，但当前不把自由聚合查询页宣称为 repo-wide Phase 2 已晋升消费面。",
    highlights: ["保留后续扩展入口", "当前以边界说明替代 live 宣称", "避免把实验/保留面误写成正式主链"],
  },
};

export const mockHomeSnapshot: HomeSnapshotPayload = {
  report_date: "2026-04-18",
  mode: "strict",
  source_surface: "executive_analytical",
  overview: overviewPayload,
  attribution: pnlAttributionPayload,
  domains_missing: [],
  domains_effective_date: {
    balance: "2026-04-18",
    pnl: "2026-04-18",
    liability: "2026-04-18",
    bond: "2026-04-18",
  },
  verdict: mockVerdictPayload,
};
