export type HomeDeltaTone = "up" | "down" | "flat" | "muted" | "warn";

export type HomeDataStateKind =
  | "ready"
  | "partial"
  | "empty"
  | "loading"
  | "error"
  | "stale"
  | "backend-gap";

/**
 * 报告日期口径模式。
 * - exact: 请求日与实际数据日一致，只显示一个报告日
 * - fallback: 请求日无数据，回退到最近可用快照（请求日 ≠ 实际数据日）
 * - stale: 新报告日获取失败，沿用上一版本数据
 * - loading: 主快照读取中
 * - error: 首页主快照读取失败（包括权限或请求失败）
 * - mock: 样例数据（无真实后端）
 * - empty: 暂无任何数据日
 */
export type HomeReportDateMode =
  | "exact"
  | "fallback"
  | "stale"
  | "loading"
  | "error"
  | "mock"
  | "empty";

/**
 * 首页报告日期上下文 —— 把"请求日 / 实际数据日 / 回退原因 / 数据截至日"
 * 四类语义统一收口，避免顶部与正文显示不同日期却无解释。
 *
 * 语义定义对齐 docs/page_contracts.md 与 api/contracts.ts::ResultMeta：
 * - requestedDate: 用户在日期控件中选择的日期（空表示 latest，由后端选最新严格交集）
 * - actualDataDate: 本次 KPI 与结论真正对应的日期（仅取 snapshot.result.report_date）
 * - divergenceReason: 请求日 ≠ 实际数据日时的原因说明
 * - dataAsOfDate: 各核心域有效日期（snapshot.result.domains_effective_date）
 * - generatedAt: 快照生成时间；与来源数据有效日期分开，不互相回填
 * - mode: 日期口径模式，用于驱动显式状态展示
 */
export type HomeReportDateContext = {
  requestedDate: string;
  actualDataDate: string;
  divergenceReason: string | null;
  dataAsOfDate: string;
  generatedAt?: string;
  mode: HomeReportDateMode;
};

export type HomeGovernanceStatusKind =
  | "ok"
  | "partial"
  | "fallback"
  | "stale"
  | "loading"
  | "error";

export type HomeHeaderStatus = {
  dataStatusKind: HomeGovernanceStatusKind;
  snapshotFailureKind?: "permission" | "requestFailed" | null;
  formalUseAllowed?: boolean | null;
  governanceFeedAvailable?: boolean;
  dataUpdatedAt: string;
  marketStatus: string;
  valuationLabel: string;
  valuationTone: "ok" | "warn";
  riskReviewCount: number;
  showRiskReview: boolean;
  dataSyncPrefix: string;
};

export type HomeTerminalKpi = {
  id: string;
  label: string;
  value: string;
  unit?: string;
  delta: string;
  deltaTone: HomeDeltaTone;
  sparkline: readonly number[];
  state: HomeDataStateKind;
};

export type HomeRiskTicker = {
  id: string;
  label: string;
  value: string;
  delta: string;
  deltaTone: HomeDeltaTone;
};

export type HomeProductCategoryHeadlineMetric = {
  id: string;
  label: string;
  value: string;
  detail: string;
};

export type HomeProductCategoryHeadline = {
  state: HomeDataStateKind;
  metrics: readonly HomeProductCategoryHeadlineMetric[];
};

export type HomeMissingDomain = {
  id: string;
  label: string;
};

export type HomeDecisionSuggestion = {
  id: string;
  text: string;
  to?: string;
};

export type HomeDecisionActionPriority = "high" | "medium" | "low";

export type HomeDecisionAction = {
  id: string;
  title: string;
  priority: HomeDecisionActionPriority;
  sourceLabel: string;
  reason: string;
  to?: string;
  statusKind: HomeDataStateKind;
};

export type HomeDecisionRail = {
  conclusion: string;
  maxDragLabel: string;
  maxDragValue: string;
  maxContributionLabel: string;
  maxContributionValue: string;
  /** 语义布尔：组件据此判断是否渲染徽标，避免与占位符文本做字面量比较。 */
  hasDrag: boolean;
  hasContribution: boolean;
  keyRisk: string;
  suggestions: readonly HomeDecisionSuggestion[];
  actions: readonly HomeDecisionAction[];
  pendingSummary: string;
  reportDate: string;
  dataUpdatedAt: string;
  dataSyncPrefix: string;
};

export type DashboardHomeFirstScreenView = {
  reportDate: string;
  useMockFallback: boolean;
  reportDateContext: HomeReportDateContext;
  headerStatus: HomeHeaderStatus;
  decisionRail: HomeDecisionRail;
  productCategoryHeadline: HomeProductCategoryHeadline;
  missingDomains: readonly HomeMissingDomain[];
  terminalKpis: readonly HomeTerminalKpi[];
  keyRiskStrip: readonly HomeRiskTicker[];
};

export type DashboardHomeFirstScreenHydration = Pick<
  DashboardHomeFirstScreenView,
  "reportDate" | "headerStatus" | "decisionRail" | "terminalKpis" | "keyRiskStrip"
> & {
  supplementalState?: HomeSupplementalApiState;
};

export type HomeSupplementalApiState = {
  kind: HomeDataStateKind;
  label: string;
};

export function resolveDeltaClass(
  tone: HomeDeltaTone,
  styles: Record<string, string>,
): string {
  if (tone === "up" || tone === "warn") {
    return styles.dhUpRed ?? "";
  }
  if (tone === "down") {
    return styles.dhDownGreen ?? "";
  }
  return styles.dhMuted ?? "";
}
