import type {
  BalanceCurrencyBasis,
  BalanceAnalysisDecisionItemStatusRow,
  BalanceAnalysisDecisionItemsPayload,
  BalanceAnalysisDecisionStatus,
  BalancePositionScope,
  BalanceAnalysisSeverity,
  BalanceAnalysisCurrentUserPayload,
  ResultMeta,
} from "../../../api/contracts";

const SEVERITY_RANK: Record<BalanceAnalysisSeverity, number> = {
  high: 0,
  medium: 1,
  low: 2,
};

function isNonEmptyString(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

function isValidSeverity(value: unknown): value is BalanceAnalysisSeverity {
  return value === "low" || value === "medium" || value === "high";
}

function isValidDecisionStatus(value: unknown): value is BalanceAnalysisDecisionStatus {
  return value === "pending" || value === "confirmed" || value === "dismissed";
}

function severitySortRank(value: unknown): number {
  if (isValidSeverity(value)) {
    return SEVERITY_RANK[value];
  }
  return 3;
}

function compareRows(
  a: BalanceAnalysisDecisionItemStatusRow,
  b: BalanceAnalysisDecisionItemStatusRow,
): number {
  const aPending = a.latest_status?.status === "pending" ? 0 : 1;
  const bPending = b.latest_status?.status === "pending" ? 0 : 1;
  if (aPending !== bPending) {
    return aPending - bPending;
  }
  const sev = severitySortRank(a.severity) - severitySortRank(b.severity);
  if (sev !== 0) {
    return sev;
  }
  const titleCmp = (a.title ?? "").localeCompare(b.title ?? "", undefined, { sensitivity: "base" });
  if (titleCmp !== 0) {
    return titleCmp;
  }
  return (a.decision_key ?? "").localeCompare(b.decision_key ?? "", undefined, { sensitivity: "base" });
}

function rowFieldWarnings(row: BalanceAnalysisDecisionItemStatusRow, index: number): string[] {
  const prefix = isNonEmptyString(row.decision_key)
    ? `decision_key=${row.decision_key}`
    : `row[${index}]`;
  const warnings: string[] = [];
  if (!isNonEmptyString(row.decision_key)) {
    warnings.push(`${prefix}: missing or empty decision_key`);
  }
  if (!isNonEmptyString(row.title)) {
    warnings.push(`${prefix}: missing or empty title`);
  }
  if (!isNonEmptyString(row.action_label)) {
    warnings.push(`${prefix}: missing or empty action_label`);
  }
  if (!isValidSeverity(row.severity)) {
    warnings.push(`${prefix}: missing or invalid severity`);
  }
  if (!isNonEmptyString(row.reason)) {
    warnings.push(`${prefix}: missing or empty reason`);
  }
  if (!isNonEmptyString(row.source_section)) {
    warnings.push(`${prefix}: missing or empty source_section`);
  }
  if (!isNonEmptyString(row.rule_id)) {
    warnings.push(`${prefix}: missing or empty rule_id`);
  }
  if (!isNonEmptyString(row.rule_version)) {
    warnings.push(`${prefix}: missing or empty rule_version`);
  }
  if (!row.latest_status || !isValidDecisionStatus(row.latest_status.status)) {
    warnings.push(`${prefix}: missing or invalid latest_status.status`);
  }
  return warnings;
}

function metaWarnings(meta: ResultMeta | undefined): string[] {
  if (!meta) {
    return [];
  }
  const out: string[] = [];
  if (!meta.formal_use_allowed) {
    out.push("result_meta: formal_use_allowed is false; analytical context only.");
  }
  if (meta.quality_flag === "stale" || meta.vendor_status === "vendor_stale") {
    out.push("result_meta: data may be stale; confirm dates before acting.");
  }
  if (meta.quality_flag === "error") {
    out.push("result_meta: quality_flag is error.");
  }
  if (meta.fallback_mode !== "none") {
    out.push("result_meta: fallback_mode is active; reduced confidence.");
  }
  return out;
}

export type DecisionItemsStatusCounts = Record<BalanceAnalysisDecisionStatus, number>;

export type DecisionItemsSeverityCounts = Record<BalanceAnalysisSeverity, number>;

/** UI-facing aggregate for balance-analysis decision items (single build entry point). */
export type DecisionItemsPageViewModel = {
  reportDate: string;
  positionScope: BalancePositionScope;
  currencyBasis: BalanceCurrencyBasis;
  rows: BalanceAnalysisDecisionItemStatusRow[];
  summary: string;
  statusCounts: DecisionItemsStatusCounts;
  severityCounts: DecisionItemsSeverityCounts;
  pendingRows: BalanceAnalysisDecisionItemStatusRow[];
  attentionRows: BalanceAnalysisDecisionItemStatusRow[];
  contractWarnings: string[];
};

const EMPTY_STATUS_COUNTS: DecisionItemsStatusCounts = {
  pending: 0,
  confirmed: 0,
  dismissed: 0,
};

const EMPTY_SEVERITY_COUNTS: DecisionItemsSeverityCounts = {
  low: 0,
  medium: 0,
  high: 0,
};

export function buildDecisionItemsPageViewModel(input: {
  payload?: Partial<BalanceAnalysisDecisionItemsPayload> | null;
  result_meta?: ResultMeta;
  currentUser?: BalanceAnalysisCurrentUserPayload | null;
  loading?: boolean;
  error?: boolean;
}): DecisionItemsPageViewModel {
  void input.currentUser;

  const contractWarnings = [...metaWarnings(input.result_meta)];

  if (input.loading) {
    return {
      reportDate: input.payload?.report_date ?? "",
      positionScope: input.payload?.position_scope ?? "all",
      currencyBasis: input.payload?.currency_basis ?? "native",
      rows: [],
      summary: "Loading decision items…",
      statusCounts: { ...EMPTY_STATUS_COUNTS },
      severityCounts: { ...EMPTY_SEVERITY_COUNTS },
      pendingRows: [],
      attentionRows: [],
      contractWarnings,
    };
  }

  if (input.error) {
    return {
      reportDate: input.payload?.report_date ?? "",
      positionScope: input.payload?.position_scope ?? "all",
      currencyBasis: input.payload?.currency_basis ?? "native",
      rows: [],
      summary: "Unable to load decision items.",
      statusCounts: { ...EMPTY_STATUS_COUNTS },
      severityCounts: { ...EMPTY_SEVERITY_COUNTS },
      pendingRows: [],
      attentionRows: [],
      contractWarnings,
    };
  }

  const rawRows = Array.isArray(input.payload?.rows) ? input.payload.rows.slice() : [];

  rawRows.forEach((row, index) => {
    contractWarnings.push(...rowFieldWarnings(row, index));
  });

  const rows = rawRows.slice().sort(compareRows);

  const statusCounts: DecisionItemsStatusCounts = { ...EMPTY_STATUS_COUNTS };
  const severityCounts: DecisionItemsSeverityCounts = { ...EMPTY_SEVERITY_COUNTS };

  for (const row of rawRows) {
    if (row.latest_status && isValidDecisionStatus(row.latest_status.status)) {
      statusCounts[row.latest_status.status] += 1;
    }
    if (isValidSeverity(row.severity)) {
      severityCounts[row.severity] += 1;
    }
  }

  const pendingRows = rows.filter((row) => row.latest_status?.status === "pending");

  const attentionRows = rows.filter((row) => {
    const pending = row.latest_status?.status === "pending";
    const sevHigh = row.severity === "high";
    const sevMed = row.severity === "medium";
    return pending || sevHigh || sevMed;
  });

  let summary: string;
  if (rows.length === 0) {
    summary = "No decision items for this report.";
  } else {
    summary = `${rows.length} item(s) · pending ${statusCounts.pending} · high severity ${severityCounts.high}`;
  }

  return {
    reportDate: input.payload?.report_date ?? "",
    positionScope: input.payload?.position_scope ?? "all",
    currencyBasis: input.payload?.currency_basis ?? "native",
    rows,
    summary,
    statusCounts,
    severityCounts,
    pendingRows,
    attentionRows,
    contractWarnings,
  };
}
