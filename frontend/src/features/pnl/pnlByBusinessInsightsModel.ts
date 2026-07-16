import type { ApiEnvelope, PnlByBusinessInsightsPayload } from "../../api/contracts";

export type PnlByBusinessInsightsLeadershipStatus = "loading" | "ready" | "review";

export type PnlByBusinessInsightsLeadershipItem = {
  key: "concentration" | "negative_ftp" | "share_drift" | "scale_yield";
  label: string;
  value: string;
  detail: string;
  rowKey: string | null;
};

export type PnlByBusinessInsightsLeadershipModel = {
  status: PnlByBusinessInsightsLeadershipStatus;
  reason: string;
  qualityWarning: boolean;
  resolvedDate: string | null;
  traceId: string | null;
  items: PnlByBusinessInsightsLeadershipItem[];
};

type BuildArgs = {
  requestedDate: string;
  envelope: ApiEnvelope<PnlByBusinessInsightsPayload> | undefined;
  isLoading: boolean;
  isError: boolean;
};

function numberValue(value: string | null | undefined): number | null {
  if (value === null || value === undefined || value === "") {
    return null;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function pct(value: string | null | undefined, digits = 2): string {
  const parsed = numberValue(value);
  return parsed === null ? "—" : `${parsed.toFixed(digits)}%`;
}

function signedPp(value: string | null | undefined): string {
  const parsed = numberValue(value);
  if (parsed === null) {
    return "—";
  }
  return `${parsed > 0 ? "+" : ""}${parsed.toFixed(2)}pp`;
}

function reviewModel(reason: string, resolvedDate: string | null = null): PnlByBusinessInsightsLeadershipModel {
  return {
    status: "review",
    reason,
    qualityWarning: false,
    resolvedDate,
    traceId: null,
    items: [],
  };
}

export function hasApprovedPnlByBusinessInsightsEvidence(
  result: PnlByBusinessInsightsPayload,
): boolean {
  if (
    result.baseline_fallback_mode !== "none" ||
    !result.baseline_requested_report_date ||
    result.baseline_resolved_report_date !== result.baseline_requested_report_date
  ) {
    return false;
  }

  const evidence = result.component_evidence;
  if (
    !Array.isArray(evidence) ||
    evidence.length === 0 ||
    evidence.some((entry) => !entry || typeof entry !== "object")
  ) {
    return false;
  }

  const startMatch = /^(\d{4})-(0[1-9]|1[0-2])$/.exec(
    result.negative_ftp_persistence.window_start_month ?? "",
  );
  const endMatch = /^(\d{4})-(0[1-9]|1[0-2])$/.exec(
    result.negative_ftp_persistence.window_end_month ?? "",
  );
  if (!startMatch || !endMatch) {
    return false;
  }
  const startYear = Number(startMatch[1]);
  const endYear = Number(endMatch[1]);
  const startOrdinal = startYear * 12 + Number(startMatch[2]);
  const endOrdinal = endYear * 12 + Number(endMatch[2]);
  if (endOrdinal < startOrdinal || endYear - startYear > 1) {
    return false;
  }

  const expectedComponentDates = new Map<string, string>([
    ["current_ytd", result.as_of_date],
    ["baseline_ytd", result.baseline_requested_report_date],
  ]);
  for (let componentYear = startYear; componentYear <= endYear; componentYear += 1) {
    expectedComponentDates.set(
      `monthly_${componentYear}`,
      componentYear === endYear ? result.as_of_date : `${componentYear}-12-31`,
    );
  }
  const components = new Set(evidence.map((entry) => entry.component));
  if (
    evidence.length !== expectedComponentDates.size ||
    components.size !== evidence.length ||
    [...expectedComponentDates.keys()].some((component) => !components.has(component))
  ) {
    return false;
  }

  return evidence.every((entry) => {
    const expectedReportDate = expectedComponentDates.get(entry.component);
    return (
      expectedReportDate !== undefined &&
      entry.fallback_mode === "none" &&
      (entry.quality_flag === "ok" || entry.quality_flag === "warning") &&
      entry.vendor_status === "ok" &&
      entry.formal_source_admitted === true &&
      entry.admission_reason === null &&
      entry.requested_report_date === expectedReportDate &&
      entry.resolved_report_date === expectedReportDate
    );
  });
}

function buildLeadershipItems(result: PnlByBusinessInsightsPayload): PnlByBusinessInsightsLeadershipItem[] {
  const concentration = result.concentration;
  const eligibleNegativeFtpRows = result.negative_ftp_persistence.rows.filter(
    (row) => row.eligible && row.status === "eligible",
  );
  const negativeFtp = [...eligibleNegativeFtpRows]
    .filter((row) => row.warning_triggered)
    .sort(
      (left, right) =>
        (numberValue(right.negative_ftp_month_share_pct) ?? -1) -
          (numberValue(left.negative_ftp_month_share_pct) ?? -1) ||
        (right.negative_ftp_longest_streak_months ?? -1) -
          (left.negative_ftp_longest_streak_months ?? -1),
    )[0];
  const drift = result.share_drift.available && result.share_drift.baseline_available
    ? [...result.share_drift.rows]
        .filter((row) => numberValue(row.drift_pp) !== null)
        .sort(
          (left, right) =>
            Math.abs(numberValue(right.drift_pp) ?? 0) - Math.abs(numberValue(left.drift_pp) ?? 0),
        )[0]
    : undefined;
  const quadrantPriority = ["LARGE_LOW", "LARGE_HIGH", "SMALL_LOW", "SMALL_HIGH"] as const;
  const quadrant = result.scale_yield_quadrant.available
    ? [...result.scale_yield_quadrant.rows].sort((left, right) => {
        const priorityDelta =
          quadrantPriority.indexOf(left.quadrant_key) - quadrantPriority.indexOf(right.quadrant_key);
        if (priorityDelta !== 0) {
          return priorityDelta;
        }
        return (numberValue(right.scale_share_pct) ?? -1) - (numberValue(left.scale_share_pct) ?? -1);
      })[0]
    : undefined;

  const quadrantLabel: Record<string, string> = {
    LARGE_HIGH: "规模较大·收益较高",
    LARGE_LOW: "规模较大·收益较低",
    SMALL_HIGH: "规模较小·收益较高",
    SMALL_LOW: "规模较小·收益较低",
  };

  return [
    {
      key: "concentration",
      label: "结构集中度",
      value: `HHI ${pct(concentration.hhi_pct)} · Top${concentration.top_n} ${pct(concentration.top_n_share_pct)}`,
      detail: "YTD 日均余额、人民币等值、父级业务口径",
      rowKey: null,
    },
    {
      key: "negative_ftp",
      label: "持续负 FTP",
      value: negativeFtp
        ? `${negativeFtp.business_type} ${pct(negativeFtp.negative_ftp_month_share_pct)}`
        : eligibleNegativeFtpRows.length > 0
          ? "合格观察样本中未发现达到预警阈值的业务"
          : "观察期不足，暂不形成结论",
      detail: negativeFtp
        ? `近 ${result.negative_ftp_persistence.lookback_months} 个自然月，最长连续 ${negativeFtp.negative_ftp_longest_streak_months ?? "—"} 个月`
        : `至少 ${result.negative_ftp_persistence.minimum_observed_months} 个有效月且负值月份占比达到 ${pct(result.negative_ftp_persistence.warning_threshold_pct)}`,
      rowKey: negativeFtp?.row_key ?? null,
    },
    {
      key: "share_drift",
      label: "日均份额同比漂移",
      value: drift ? `${drift.business_type} ${signedPp(drift.drift_pp)}` : "同比同期间基准不可用",
      detail: drift
        ? `对比 ${result.share_drift.baseline_as_of_date ?? "—"}；新进/退出业务按 0 处理`
        : "当前口径不使用上一年末替代同期间基准",
      rowKey:
        drift?.lifecycle_status === "exited" || drift?.lifecycle_status === "unavailable"
          ? null
          : drift?.row_key ?? null,
    },
    {
      key: "scale_yield",
      label: "规模—FTP后收益",
      value: quadrant
        ? `${quadrant.business_type} · ${quadrantLabel[quadrant.quadrant_key]} · ${pct(quadrant.scale_share_pct)}`
        : "有效业务数不足，暂不分类",
      detail: quadrant
        ? `FTP后年化 ${pct(quadrant.ftp_net_annualized_yield_pct)}；按当期中位数作相对描述`
        : `至少需要 ${result.scale_yield_quadrant.minimum_eligible_rows} 个有效父级业务`,
      rowKey: quadrant?.row_key ?? null,
    },
  ];
}

export function buildPnlByBusinessInsightsLeadershipModel({
  requestedDate,
  envelope,
  isLoading,
  isError,
}: BuildArgs): PnlByBusinessInsightsLeadershipModel {
  if (isLoading) {
    return {
      status: "loading",
      reason: "结构分析加载中",
      qualityWarning: false,
      resolvedDate: null,
      traceId: null,
      items: [],
    };
  }
  if (isError) {
    return reviewModel("结构分析读取失败，主损益结果不受影响");
  }
  if (!envelope) {
    return reviewModel("结构分析结果尚未返回");
  }

  const { result_meta: meta, result } = envelope;
  const resolvedDate = meta.resolved_report_date ?? null;
  if (
    meta.basis !== "formal" ||
    !meta.formal_use_allowed ||
    meta.result_kind !== "pnl.by_business_insights"
  ) {
    return reviewModel("结构分析不是已批准的正式口径，暂不形成领导结论", resolvedDate);
  }
  if (result.result_version !== "v2") {
    return reviewModel("结构分析响应版本不受支持，需复核后使用", resolvedDate);
  }
  if (!hasApprovedPnlByBusinessInsightsEvidence(result)) {
    return reviewModel("结构分析基准或组件证据未通过门禁，需复核后使用", resolvedDate);
  }
  if (
    meta.fallback_mode !== "none" ||
    Boolean(meta.fallback_date) ||
    meta.requested_report_date !== requestedDate ||
    meta.resolved_report_date !== requestedDate ||
    result.as_of_date !== requestedDate
  ) {
    return reviewModel("结构分析截止日与当前页面不一致或发生降级，需复核后使用", resolvedDate);
  }
  if (
    (meta.quality_flag !== "ok" && meta.quality_flag !== "warning") ||
    meta.vendor_status !== "ok" ||
    meta.scenario_flag
  ) {
    return reviewModel("结构分析质量状态不可用于当前结论，需复核后使用", resolvedDate);
  }

  return {
    status: "ready",
    reason: meta.quality_flag === "warning" ? "正式口径已匹配；上游存在质量提示" : "正式口径已匹配",
    qualityWarning: meta.quality_flag === "warning",
    resolvedDate,
    traceId: meta.trace_id,
    items: buildLeadershipItems(result),
  };
}
