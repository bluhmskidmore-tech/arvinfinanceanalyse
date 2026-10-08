import { useApiClient } from "../../../api/client";
import { useSearchParams } from "react-router-dom";
import { useState, useMemo, useEffect, useRef } from "react";
import { requestUnlessAborted, sleepUnlessAborted } from "../../../app/jobs/polling";
import type { BalanceMovementBucket } from "../../../api/contracts";
import { balanceMovementBuckets } from "../lib/balanceMovementBusinessModel";
import { useQuery } from "@tanstack/react-query";

export type BalanceMovementReadState = "confirmed" | "refreshing" | "cached_after_error";
type RefreshFailureSource = "refresh" | "dates" | "detail";

function normalizeMovementCurrencyBasis(_value: string | null): "CNX" {
  return "CNX";
}

export function useBalanceMovementAnalysis() {
  const client = useApiClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const queryReportDate = searchParams.get("report_date")?.trim() || "";
  const rawQueryCurrencyBasis = searchParams.get("currency_basis")?.trim().toUpperCase() || "";
  const queryCurrencyBasis = normalizeMovementCurrencyBasis(rawQueryCurrencyBasis);
  const currencyBasis = queryCurrencyBasis;
  const requestedReportDate = searchParams.get("requested_report_date")?.trim() || queryReportDate;
  const queryBucket = searchParams.get("basis_bucket");
  const selectedBucket: BalanceMovementBucket | "all" = balanceMovementBuckets.find((bucket) => bucket === queryBucket) ?? "all";
  const isEvidenceOpen = searchParams.get("evidence") === "1" && selectedBucket !== "all";
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [refreshMessage, setRefreshMessage] = useState<string | null>(null);
  const [refreshFailure, setRefreshFailure] = useState<{ source: RefreshFailureSource; message: string } | null>(null);

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

  const selectedDate = reportDates.includes(queryReportDate) ? queryReportDate : reportDates[0] ?? "";
  const selectionIdentity = `${client.mode}|${currencyBasis}|${selectedDate}|${requestedReportDate || selectedDate}|${selectedBucket}|${isEvidenceOpen}`;
  const latestSelectionRef = useRef(selectionIdentity);
  latestSelectionRef.current = selectionIdentity;
  const refreshControllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    setIsRefreshing(false);
    setRefreshMessage(null);
    return () => refreshControllerRef.current?.abort();
  }, [selectionIdentity]);

  useEffect(() => {
    // Bucket and evidence navigation do not establish a new read snapshot.
    setRefreshFailure(null);
  }, [client.mode, currencyBasis, selectedDate]);

  useEffect(() => {
    if (!selectedDate) return;
    const canonicalParams = new URLSearchParams(searchParams);
    if (queryReportDate && queryReportDate !== selectedDate) {
      canonicalParams.set("requested_report_date", queryReportDate);
    }
    canonicalParams.set("report_date", selectedDate);
    canonicalParams.set("currency_basis", "CNX");
    if (canonicalParams.toString() !== searchParams.toString()) {
      setSearchParams(canonicalParams, { replace: true });
    }
  }, [queryReportDate, searchParams, selectedDate, setSearchParams]);

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

  const refreshError = refreshFailure && (
    refreshFailure.source === "refresh" ||
    (refreshFailure.source === "dates" && datesQuery.isError) ||
    (refreshFailure.source === "detail" && detailQuery.isError)
  ) ? refreshFailure.message : null;
  const readStatus: BalanceMovementReadState = datesQuery.isError || detailQuery.isError || refreshError
    ? "cached_after_error"
    : datesQuery.isFetching || detailQuery.isFetching || isRefreshing
      ? "refreshing"
      : "confirmed";
  const actualReportDate = detailQuery.data?.result_meta.resolved_report_date ||
    detailQuery.data?.result.report_date || selectedDate;

  function updateReportDateSelection(reportDate: string) {
    const nextParams = new URLSearchParams(searchParams);
    nextParams.set("report_date", reportDate);
    nextParams.set("currency_basis", "CNX");
    nextParams.delete("requested_report_date");
    setSearchParams(nextParams);
  }

  function updateBucketSelection(bucket: BalanceMovementBucket | "all") {
    const nextParams = new URLSearchParams(searchParams);
    nextParams.set("basis_bucket", bucket);
    nextParams.delete("evidence");
    setSearchParams(nextParams);
  }

  function updateEvidenceSelection(open: boolean) {
    const nextParams = new URLSearchParams(searchParams);
    if (open && selectedBucket !== "all") nextParams.set("evidence", "1");
    else nextParams.delete("evidence");
    setSearchParams(nextParams);
  }

  async function handleRefresh() {
    if (!selectedDate) {
      return;
    }
    refreshControllerRef.current?.abort();
    const controller = new AbortController();
    refreshControllerRef.current = controller;
    const { signal } = controller;
    const canCommit = () => !signal.aborted && latestSelectionRef.current === selectionIdentity;
    const refreshReportDate =
      datesQuery.data?.result.freshness_status === "read_model_lagging"
        ? datesQuery.data.result.latest_upstream_control_report_date ?? selectedDate
        : selectedDate;
    const refreshTargetWasMaterialized =
      datesQuery.data?.result.report_dates.includes(refreshReportDate) ?? false;
    setIsRefreshing(true);
    setRefreshMessage(null);
    setRefreshFailure(null);
    let failureSource: RefreshFailureSource = "refresh";
    try {
      const payload = await requestUnlessAborted(() => client.refreshBalanceMovementAnalysis({
        reportDate: refreshReportDate,
        currencyBasis,
      }), signal);
      if (!canCommit()) return;
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
      setRefreshMessage(`运行状态 ${payload.status}: ${rowCountText}${refreshDetail}；读取与发布状态另行核对。`);
      const applyRefreshedDate = async () => {
        if (!canCommit()) return false;
        failureSource = "dates";
        const refreshedDates = await requestUnlessAborted(() => datesQuery.refetch(), signal);
        if (!canCommit()) return false;
        if (refreshedDates.isError) throw refreshedDates.error;
        if (!refreshedDates.data?.result.report_dates.includes(refreshReportDate)) {
          return false;
        }
        if (refreshReportDate === selectedDate) {
          failureSource = "detail";
          const refreshedDetail = await requestUnlessAborted(() => detailQuery.refetch(), signal);
          if (!canCommit()) return false;
          if (refreshedDetail.isError) throw refreshedDetail.error;
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
          if (!canCommit()) return;
          if (await applyRefreshedDate()) {
            if (canCommit()) setRefreshMessage(`报告日 ${refreshReportDate} 已可读取；运行终态与发布状态仍需分别确认。`);
            return;
          }
          if (attempt < maxPollAttempts - 1) {
            await sleepUnlessAborted(1_000, signal);
          }
        }
        if (!canCommit()) return;
        setRefreshMessage(
          `queued: ${refreshReportDate} \u540e\u53f0\u5904\u7406\u4e2d\uff0c\u8bf7\u7a0d\u540e\u5237\u65b0`,
        );
        return;
      }
      await applyRefreshedDate();
    } catch (error) {
      if (!canCommit()) return;
      const message = `刷新或后续读取失败：${error instanceof Error ? error.message : "请重试"}；未确认发布状态。`;
      setRefreshFailure({ source: failureSource, message });
      setRefreshMessage(message);
    } finally {
      if (canCommit()) setIsRefreshing(false);
    }
  }

  return {
    datesQuery,
    detailQuery,
    reportDates,
    dateStatus,
    selectedDate,
    requestedReportDate,
    actualReportDate,
    readStatus,
    selectedBucket,
    isEvidenceOpen,
    updateBucketSelection,
    updateEvidenceSelection,
    currencyBasis,
    isRefreshing,
    refreshMessage: refreshFailure ? refreshError : refreshMessage,
    refreshError,
    updateReportDateSelection,
    handleRefresh,
  };
}
