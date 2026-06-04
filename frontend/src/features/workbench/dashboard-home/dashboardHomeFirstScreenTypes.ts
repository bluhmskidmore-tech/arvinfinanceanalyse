export type HomeDeltaTone = "up" | "down" | "flat" | "muted" | "warn";

export type HomeDataStateKind =
  | "ready"
  | "partial"
  | "empty"
  | "loading"
  | "error"
  | "stale"
  | "backend-gap";

export type HomeHeaderStatus = {
  dataStatusKind: "ok" | "stale" | "error";
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

export type HomeDecisionRail = {
  conclusion: string;
  maxDragLabel: string;
  maxDragValue: string;
  maxContributionLabel: string;
  maxContributionValue: string;
  keyRisk: string;
  suggestions: readonly string[];
  pendingSummary: string;
  reportDate: string;
  dataUpdatedAt: string;
  dataSyncPrefix: string;
};

export type DashboardHomeFirstScreenView = {
  reportDate: string;
  useMockFallback: boolean;
  headerStatus: HomeHeaderStatus;
  decisionRail: HomeDecisionRail;
  terminalKpis: readonly HomeTerminalKpi[];
  keyRiskStrip: readonly HomeRiskTicker[];
};

export type DashboardHomeFirstScreenHydration = Pick<
  DashboardHomeFirstScreenView,
  "reportDate" | "headerStatus" | "decisionRail" | "terminalKpis" | "keyRiskStrip"
>;

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
