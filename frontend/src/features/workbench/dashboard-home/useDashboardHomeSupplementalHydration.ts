import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { apiQueryKeys } from "../../../api/queryKeys";
import type { ResultMeta } from "../../../api/contracts";
import { mapToHomeFirstScreenHydration } from "./dashboardHomeFirstScreenView";
import type {
  DashboardHomeFirstScreenHydration,
  HomeSupplementalApiState,
} from "./dashboardHomeFirstScreenTypes";
import type { DashboardHomeSnapshotBoundary } from "./useDashboardHomeFirstScreenViewModel";
import { useMockHomeFirstScreenView } from "./useMockHomeFirstScreenView";

export type DashboardHomeSupplementalHydrationResult = {
  firstScreenHydration: DashboardHomeFirstScreenHydration;
  supplementalState: HomeSupplementalApiState;
  updatedAt: string;
};

function supplementalRiskSource(input: {
  label: string;
  reportDate: string;
  payloadDate: string | undefined;
  meta: ResultMeta | undefined;
  isError: boolean;
  isSuccess: boolean;
}): { displayAllowed: boolean; state: HomeSupplementalApiState } {
  const { label, meta } = input;
  const payloadDate = input.payloadDate?.trim();
  if (!payloadDate) {
    return {
      displayAllowed: false,
      state: input.isError
        ? { kind: "error", label: `${label}读取失败` }
        : input.isSuccess
          ? { kind: "partial", label: `${label}未返回风险摘要或实际数据日` }
          : { kind: "loading", label: `${label}读取中` },
    };
  }
  if (!meta) {
    return { displayAllowed: false, state: { kind: "partial", label: `${label}未返回质量信息，未展示` } };
  }

  // The payload and every supplied effective-date field must agree with the
  // snapshot. A requested report date or a fresh response time cannot replace them.
  const effectiveDates = Array.from(new Set([
    payloadDate, meta.resolved_report_date, meta.as_of_date, meta.fallback_date,
  ].flatMap((date) => date?.trim() ? [date.trim()] : [])));
  const dateLabel = `数据日 ${effectiveDates.join("、")}`;
  const fallback = meta.fallback_mode !== "none";
  if (effectiveDates.some((date) => date !== input.reportDate)) {
    return {
      displayAllowed: false,
      state: {
        kind: "partial",
        label: `${label}${fallback ? "使用回退数据，" : ""}${dateLabel} 与首页报告日 ${input.reportDate} 不一致，未展示`,
      },
    };
  }
  if (meta.quality_flag === "error" || meta.quality_flag === "missing" || meta.vendor_status === "vendor_unavailable") {
    return { displayAllowed: false, state: { kind: "error", label: `${label}数据不可用（${dateLabel}），未展示` } };
  }

  const stale = meta.quality_flag === "stale" || meta.vendor_status === "vendor_stale";
  const reasons = [
    input.isError ? "读取失败，保留旧值" : "",
    fallback ? "使用回退数据" : "",
    stale ? "数据偏旧" : "",
    meta.quality_flag !== "ok" && !stale ? "数据需复核" : "",
  ].filter(Boolean);
  return {
    displayAllowed: true,
    state: reasons.length > 0
      ? {
          kind: stale || fallback || input.isError ? "stale" : "partial",
          label: `${label}${reasons.join("，")}（${dateLabel}）`,
        }
      : { kind: "ready", label: `${label}已就绪` },
  };
}

export function useDashboardHomeSupplementalHydration(
  snapshotBoundary: DashboardHomeSnapshotBoundary,
  options: { enabled: boolean } = { enabled: true },
): DashboardHomeSupplementalHydrationResult {
  const {
    dataClient,
    snapshotQuery,
    snapshotResult,
    snapshotMeta,
    supplementalReportDate,
  } = snapshotBoundary;

  // real 模式不允许任何 mock UI 可达路径：useMockFallback 只看数据源模式，
  // 不再挂接 isLiveDataFallback 之类的运行时回退信号。
  const useMockFallback = dataClient.mode !== "real";
  const mockFirstScreenView = useMockHomeFirstScreenView(useMockFallback);
  const snapshotReportDate = snapshotResult?.report_date?.trim() || "";
  const hasSupplementalReportDate = Boolean(supplementalReportDate);
  const supplementalQueriesEnabled =
    !useMockFallback && options.enabled && hasSupplementalReportDate;

  // Reuse the same home-summary query as the body view model. TanStack
  // Query deduplicates the shared key, so first-screen hydration consumes the
  // embedded headline instead of issuing a second headline-kpis request.
  const bondHomeSummaryQuery = useQuery({
    queryKey: apiQueryKeys.bondDashboardHomeSummary(dataClient.mode, supplementalReportDate),
    queryFn: () => dataClient.getBondDashboardHomeSummary(supplementalReportDate ?? ""),
    retry: false,
    staleTime: 60_000,
    enabled: supplementalQueriesEnabled,
  });

  const portfolioHeadlinesQuery = useQuery({
    queryKey: apiQueryKeys.bondAnalyticsPortfolioHeadlines(dataClient.mode, supplementalReportDate),
    queryFn: () => dataClient.getBondAnalyticsPortfolioHeadlines(supplementalReportDate ?? ""),
    retry: false,
    staleTime: 60_000,
    enabled: supplementalQueriesEnabled,
  });
  const headlineSource = useMemo(() => supplementalRiskSource({
    label: "债券摘要",
    reportDate: snapshotReportDate,
    payloadDate: bondHomeSummaryQuery.data?.result.headline?.report_date,
    meta: bondHomeSummaryQuery.data?.result_meta,
    isError: bondHomeSummaryQuery.isError,
    isSuccess: bondHomeSummaryQuery.isSuccess,
  }), [bondHomeSummaryQuery.data, bondHomeSummaryQuery.isError, bondHomeSummaryQuery.isSuccess, snapshotReportDate]);
  const portfolioSource = useMemo(() => supplementalRiskSource({
    label: "组合风险摘要",
    reportDate: snapshotReportDate,
    payloadDate: portfolioHeadlinesQuery.data?.result.report_date,
    meta: portfolioHeadlinesQuery.data?.result_meta,
    isError: portfolioHeadlinesQuery.isError,
    isSuccess: portfolioHeadlinesQuery.isSuccess,
  }), [portfolioHeadlinesQuery.data, portfolioHeadlinesQuery.isError, portfolioHeadlinesQuery.isSuccess, snapshotReportDate]);
  const supplementalState = useMemo<HomeSupplementalApiState>(
    () => {
      if (!hasSupplementalReportDate) return { kind: "backend-gap", label: "等待主快照报告日" };
      if (useMockFallback) return { kind: "backend-gap", label: "样例模式未请求" };
      if (!supplementalQueriesEnabled) return { kind: "loading", label: "等待补充查询" };
      if (bondHomeSummaryQuery.isError && portfolioHeadlinesQuery.isError &&
        !bondHomeSummaryQuery.data && !portfolioHeadlinesQuery.data) {
        return { kind: "error", label: "补充查询失败" };
      }
      const states = [headlineSource.state, portfolioSource.state];
      const issues = states.filter((state) => state.kind !== "ready" && state.kind !== "loading");
      if (issues.length > 0) {
        return {
          kind: states.every((state) => state.kind === "error")
            ? "error"
            : issues.some((state) => state.kind === "partial" || state.kind === "error") ? "partial" : "stale",
          label: issues.map((state) => state.label).join("；"),
        };
      }
      return states.every((state) => state.kind === "ready")
        ? { kind: "ready", label: "补充查询已完成" }
        : { kind: "loading", label: "补充查询读取中" };
    },
    [
      bondHomeSummaryQuery.data,
      bondHomeSummaryQuery.isError,
      headlineSource,
      hasSupplementalReportDate,
      portfolioHeadlinesQuery.data,
      portfolioHeadlinesQuery.isError,
      portfolioSource,
      supplementalQueriesEnabled,
      useMockFallback,
    ],
  );

  const snapshotUnavailable =
    dataClient.mode === "real" && snapshotQuery.isError && !snapshotResult;
  const snapshotLoading =
    dataClient.mode === "real" && snapshotQuery.isFetching && !snapshotResult;

  const hydration = useMemo(
    () => mapToHomeFirstScreenHydration({
      reportDate: snapshotReportDate,
      bondHeadline: headlineSource.displayAllowed ? bondHomeSummaryQuery.data?.result.headline ?? null : null,
      portfolio: portfolioSource.displayAllowed ? portfolioHeadlinesQuery.data?.result ?? null : null,
      bondHeadlineState: headlineSource.state,
      portfolioState: portfolioSource.state,
      snapshotMeta,
      snapshotUnavailable,
      snapshotLoading,
    }),
    [
      bondHomeSummaryQuery.data?.result.headline,
      headlineSource,
      snapshotReportDate,
      portfolioHeadlinesQuery.data?.result,
      portfolioSource,
      snapshotMeta,
      snapshotLoading,
      snapshotUnavailable,
    ],
  );

  return useMemo(
    () => useMockFallback && mockFirstScreenView
      ? {
          firstScreenHydration: {
            reportDate: mockFirstScreenView.reportDate,
            keyRiskStrip: mockFirstScreenView.keyRiskStrip,
          },
          supplementalState,
          updatedAt: mockFirstScreenView.headerStatus.dataUpdatedAt,
        }
      : { ...hydration, supplementalState },
    [hydration, mockFirstScreenView, supplementalState, useMockFallback],
  );
}
