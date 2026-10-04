import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import type { ApiClient } from "../../../api/clientContext";
import type { HomeOperatingRevenueCandidate } from "./dashboardHomeSnapshotAdapter";

/** QDB 总账候选口径的母公司营业收入；正式的「集团营业收入」来源未接入，两者不是同一口径。 */
const OPERATING_REVENUE_METRIC_ID = "income.operating.mother_bank";
const DISPLAY_FRACTION_DIGITS = 2;

/** `2026-07-31` -> `202607`；候选指标接口按自然月取数。 */
export function toCandidateReportMonth(
  reportDate: string | null | undefined,
): string | null {
  const match = /^(\d{4})-(\d{2})-\d{2}$/.exec(reportDate?.trim() ?? "");
  return match ? `${match[1]}${match[2]}` : null;
}

export function useHomeOperatingRevenueCandidate(
  dataClient: ApiClient,
  reportDate: string | null | undefined,
  options: { enabled: boolean },
): HomeOperatingRevenueCandidate | null {
  const reportMonth = toCandidateReportMonth(reportDate);
  // 该口径只在真实数据源下取；mock 模式保持「未接入」占位，避免样例值冒充候选值。
  const enabled =
    options.enabled && dataClient.mode === "real" && Boolean(reportMonth);

  const query = useQuery({
    queryKey: [
      "ledger-pnl",
      "candidate-financial-indicators",
      dataClient.mode,
      reportMonth ?? "pending-snapshot",
      OPERATING_REVENUE_METRIC_ID,
    ] as const,
    queryFn: () =>
      dataClient.getLedgerPnlCandidateFinancialIndicators(reportMonth ?? "", {
        includeLineage: false,
        metricId: OPERATING_REVENUE_METRIC_ID,
      }),
    retry: false,
    staleTime: 300_000,
    enabled,
  });

  return useMemo(() => {
    const result = query.data?.result;
    if (!enabled || query.isError || !result || result.report_month !== reportMonth || result.calculation_status === "error") {
      return null;
    }
    const metric = result.metrics.find(
      (item) => item.metric_id === OPERATING_REVENUE_METRIC_ID,
    );
    if (!metric || metric.status === "error" || metric.value == null || !metric.value.trim()) {
      return null;
    }
    const raw = Number(metric.value);
    if (!Number.isFinite(raw)) {
      return null;
    }
    return {
      display: `${raw.toFixed(DISPLAY_FRACTION_DIGITS)} 亿`,
      status: metric.status,
      reportMonth: result.report_month,
    };
  }, [enabled, query.data?.result, query.isError, reportMonth]);
}
