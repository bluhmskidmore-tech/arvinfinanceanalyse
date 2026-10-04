import { useApiClient } from "../../../api/client";
import { useSearchParams } from "react-router-dom";
import { useState, useMemo, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";

function normalizeMovementCurrencyBasis(_value: string | null): "CNX" {
  return "CNX";
}

export function useBalanceMovementAnalysis() {
  const client = useApiClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const queryReportDate = searchParams.get("report_date")?.trim() || "";
  const rawQueryCurrencyBasis = searchParams.get("currency_basis")?.trim().toUpperCase() || "";
  const queryCurrencyBasis = normalizeMovementCurrencyBasis(rawQueryCurrencyBasis);
  const [selectedDate, setSelectedDate] = useState("");
  const [currencyBasis, setCurrencyBasis] = useState(queryCurrencyBasis);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [refreshMessage, setRefreshMessage] = useState<string | null>(null);

  const datesQuery = useQuery({
    queryKey: ["balance-movement-analysis", "dates", client.mode, currencyBasis],
    queryFn: ({ signal }) => client.getBalanceMovementDates(currencyBasis, { signal }),
    retry: false,
  });
  const reportDates = useMemo(
    () => datesQuery.data?.result.report_dates ?? [],
    [datesQuery.data?.result.report_dates],
  );
  const dateStatus = datesQuery.isError
    ? {
        tone: "error" as const,
        title: "报告日期加载失败",
        detail: "请确认后端 7888 服务与余额变动读模型可用。",
      }
    : !datesQuery.isLoading && reportDates.length === 0
      ? {
          tone: "empty" as const,
          title: "暂无已物化报告日期",
          detail: `${currencyBasis} 口径下没有可选日期；请先物化余额变动读模型。`,
        }
      : null;

  useEffect(() => {
    if (rawQueryCurrencyBasis && rawQueryCurrencyBasis !== "CNX") {
      const canonicalParams = new URLSearchParams(searchParams);
      canonicalParams.set("currency_basis", "CNX");
      setSearchParams(canonicalParams, { replace: true });
    }
  }, [rawQueryCurrencyBasis, searchParams, setSearchParams]);

  useEffect(() => {
    if (currencyBasis !== queryCurrencyBasis) {
      setCurrencyBasis(queryCurrencyBasis);
      setSelectedDate("");
    }
  }, [currencyBasis, queryCurrencyBasis]);

  useEffect(() => {
    if (!reportDates.length) {
      return;
    }
    if (queryReportDate && reportDates.includes(queryReportDate)) {
      if (selectedDate !== queryReportDate) {
        setSelectedDate(queryReportDate);
      }
      return;
    }
    if (!selectedDate || !reportDates.includes(selectedDate)) {
      setSelectedDate(reportDates[0] ?? "");
    }
  }, [queryReportDate, reportDates, selectedDate]);

  const detailQuery = useQuery({
    queryKey: ["balance-movement-analysis", "detail", client.mode, selectedDate, currencyBasis],
    queryFn: ({ signal }) =>
      client.getBalanceMovementAnalysis({
        reportDate: selectedDate,
        currencyBasis,
        signal,
      }),
    enabled: Boolean(selectedDate),
    retry: false,
  });

  function updateReportDateSelection(reportDate: string) {
    const nextParams = new URLSearchParams(searchParams);
    nextParams.set("report_date", reportDate);
    nextParams.set("currency_basis", "CNX");
    setSearchParams(nextParams, { replace: true });
    setSelectedDate(reportDate);
  }

  async function handleRefresh() {
    if (!selectedDate) {
      return;
    }
    const refreshReportDate =
      datesQuery.data?.result.freshness_status === "read_model_lagging"
        ? datesQuery.data.result.latest_upstream_control_report_date ?? selectedDate
        : selectedDate;
    const refreshTargetWasMaterialized =
      datesQuery.data?.result.report_dates.includes(refreshReportDate) ?? false;
    setIsRefreshing(true);
    setRefreshMessage(null);
    try {
      const payload = await client.refreshBalanceMovementAnalysis({
        reportDate: refreshReportDate,
        currencyBasis,
      });
      const upstreamRefreshCount =
        (payload.product_category_refreshed_dates?.length ?? 0) +
        (payload.formal_balance_refreshed_dates?.length ?? 0);
      const movementRefreshCount = payload.movement_refreshed_dates?.length ?? 0;
      const refreshDetail =
        upstreamRefreshCount > 0
          ? `，补刷新上游 ${upstreamRefreshCount} 月 / 读模型 ${movementRefreshCount} 月`
          : movementRefreshCount > 1
            ? `，读模型 ${movementRefreshCount} 月`
            : "";
      const rowCountText =
        typeof payload.row_count === "number" ? `${payload.row_count} 行` : "已排队";
      setRefreshMessage(`${payload.status}: ${rowCountText}${refreshDetail}`);
      const applyRefreshedDate = async () => {
        const refreshedDates = await datesQuery.refetch();
        if (!refreshedDates.data?.result.report_dates.includes(refreshReportDate)) {
          return false;
        }
        if (refreshReportDate === selectedDate) {
          await detailQuery.refetch();
        } else {
          updateReportDateSelection(refreshReportDate);
        }
        return true;
      };

      if (payload.status === "queued") {
        if (refreshTargetWasMaterialized) {
          setRefreshMessage(
            `queued: ${refreshReportDate} \u540e\u53f0\u5904\u7406\u4e2d\uff0c\u8bf7\u7a0d\u540e\u5237\u65b0`,
          );
          return;
        }
        const maxPollAttempts = 30;
        for (let attempt = 0; attempt < maxPollAttempts; attempt += 1) {
          if (await applyRefreshedDate()) {
            setRefreshMessage(`completed: ${refreshReportDate} \u5df2\u66f4\u65b0`);
            return;
          }
          if (attempt < maxPollAttempts - 1) {
            await new Promise<void>((resolve) => {
              window.setTimeout(resolve, 1_000);
            });
          }
        }
        setRefreshMessage(
          `queued: ${refreshReportDate} \u540e\u53f0\u5904\u7406\u4e2d\uff0c\u8bf7\u7a0d\u540e\u5237\u65b0`,
        );
        return;
      }
      await applyRefreshedDate();
    } finally {
      setIsRefreshing(false);
    }
  }

  return {
    datesQuery,
    detailQuery,
    reportDates,
    dateStatus,
    selectedDate,
    currencyBasis,
    isRefreshing,
    refreshMessage,
    updateReportDateSelection,
    handleRefresh,
  };
}
