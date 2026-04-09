import type {
  DashboardSnapshot,
  PlaceholderSnapshot,
} from "../api/contracts";

export const dashboardSnapshot: DashboardSnapshot = {
  title: "管理层驾驶舱",
  subtitle:
    "当前阶段仅交付可运行壳层与静态占位模块，后续页面将按薄前端方式逐步接入。",
  cards: [
    {
      id: "health",
      title: "今日窗口概况",
      value: "壳层已就绪",
      detail: "路由、主题、Query Provider 与 mock 契约已接通。",
    },
    {
      id: "routes",
      title: "工作台入口",
      value: "8 个",
      detail: "覆盖管理、分析、风险、团队、决策、债券、中台与市场观察入口。",
    },
    {
      id: "contract",
      title: "共享契约",
      value: "client.ts",
      detail: "前端只经由统一 API client 对接 health/result_meta 协议。",
    },
    {
      id: "boundary",
      title: "当前边界",
      value: "占位页面",
      detail: "不实现正式金融公式，不自行拼正式分析口径，不扩成厚业务页。",
    },
  ],
};

export const placeholderSnapshots: Record<string, PlaceholderSnapshot> = {
  dashboard: {
    title: "管理层驾驶舱",
    summary: "该工作台将在后续阶段接入真实薄页面。",
    highlights: [
      "保留统一壳层与导航节奏。",
      "保留 API 契约与 result_meta 包装。",
      "保留可替换的静态卡片结构。",
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
