import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { useApiClient } from "../../api/clientContext";
import { EM_DASH } from "../../utils/format";
import { errorStatusCode } from "./riskTensorPresentation";

export function useRiskTensorQueries() {
  const client = useApiClient();

  const [searchParams, setSearchParams] = useSearchParams();

  const explicitReportDate = searchParams.get("report_date")?.trim() || "";

  const datesQuery = useQuery({
    queryKey: ["risk-tensor", "dates", client.mode],
    queryFn: () => client.getRiskTensorDates(),
    retry: false,
  });

  const blockedReportDates = datesQuery.data?.result.blocked_report_dates ?? [];

  const selectedBlockedReportDate = explicitReportDate
    ? blockedReportDates.find((entry) => entry.report_date === explicitReportDate)
    : undefined;

  const latestBlockedReportDate = [...blockedReportDates].sort((a, b) => b.report_date.localeCompare(a.report_date))[0];

  const highlightedBlockedReportDate = selectedBlockedReportDate ?? latestBlockedReportDate;

  const latestAvailableReportDate = datesQuery.data?.result.report_dates[0] ?? "";

  const reportDate = useMemo(() => {
    if (explicitReportDate) {
      return explicitReportDate;
    }
    return datesQuery.data?.result.report_dates[0] ?? "";
  }, [datesQuery.data?.result.report_dates, explicitReportDate]);

  const reportDateOptions = useMemo(() => {
    const dates = datesQuery.data?.result.report_dates ?? [];
    if (!reportDate || dates.includes(reportDate)) {
      return dates;
    }
    return [reportDate, ...dates];
  }, [datesQuery.data?.result.report_dates, reportDate]);

  const datesBlockingError = datesQuery.isError;

  const datesEmpty =
    !explicitReportDate &&
    !datesQuery.isLoading &&
    !datesBlockingError &&
    (datesQuery.data?.result.report_dates.length ?? 0) === 0;

  const tensorBlockedByReportDate = Boolean(selectedBlockedReportDate);

  const tensorQueryEnabled = Boolean(reportDate) && datesQuery.isSuccess && !tensorBlockedByReportDate;

  const tensorQuery = useQuery({
    queryKey: ["risk-tensor", reportDate],
    queryFn: () => client.getRiskTensor(reportDate),
    enabled: tensorQueryEnabled,
    retry: false,
  });

  const scenarioStressQuery = useQuery({
    queryKey: ["risk-tensor", "scenario-stress", reportDate],
    queryFn: () => client.getRiskScenarioStress(reportDate),
    enabled: tensorQueryEnabled && tensorQuery.isSuccess,
    retry: false,
  });

  const envelope = datesBlockingError || tensorBlockedByReportDate ? undefined : tensorQuery.data;

  const result = envelope?.result;

  const isEmpty =
    !tensorQuery.isLoading &&
    !tensorQuery.isError &&
    result !== undefined &&
    result.bond_count === 0;

  const tensorErrorStatusCode = errorStatusCode(tensorQuery.error);

  const datesErrorStatusCode = errorStatusCode(datesQuery.error);

  const tensorErrorReportDate = reportDate || explicitReportDate || "未选择";

  const datesErrorReportDate = explicitReportDate || "未选择";

  const datesGovernanceMeta = datesQuery.data?.result_meta;

  const datesEmptyTraceId = datesGovernanceMeta?.trace_id ?? EM_DASH;

  const handleUseLatestAvailableReportDate = () => {
    if (!latestAvailableReportDate) {
      return;
    }
    setSearchParams((previous) => {
      const next = new URLSearchParams(previous);
      next.set("report_date", latestAvailableReportDate);
      return next;
    });
  };

  return {
    setSearchParams,
    explicitReportDate,
    datesQuery,
    blockedReportDates,
    selectedBlockedReportDate,
    highlightedBlockedReportDate,
    latestAvailableReportDate,
    reportDate,
    reportDateOptions,
    datesBlockingError,
    datesEmpty,
    tensorBlockedByReportDate,
    tensorQueryEnabled,
    tensorQuery,
    scenarioStressQuery,
    envelope,
    result,
    isEmpty,
    tensorErrorStatusCode,
    datesErrorStatusCode,
    tensorErrorReportDate,
    datesErrorReportDate,
    datesGovernanceMeta,
    datesEmptyTraceId,
    handleUseLatestAvailableReportDate,
  };
}
