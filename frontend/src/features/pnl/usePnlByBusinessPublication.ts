import { useEffect, useMemo, useRef } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type ApiClient } from "../../api/client";
import { buildPnlByBusinessInsightsLeadershipModel } from "./pnlByBusinessInsightsModel";
import { usesPnlByBusinessReadinessProtocol, resolveApprovedPnlByBusinessInsightsEnvelope } from "./pnlByBusinessPublicationModel";
import { type PnlByBusinessViewMode } from "./pnlByBusinessPageModel";

export function usePnlByBusinessPrecompute({
  client,
  selectedYear,
  selectedReportDate,
  viewMode,
}: {
  client: ApiClient;
  selectedYear: number;
  selectedReportDate: string;
  viewMode: PnlByBusinessViewMode;
}) {
  const queryClient = useQueryClient();
  const precomputeTrackedRunIdRef = useRef<string | null>(null);
  const precomputeStatusQueryKey = [
    "pnl-by-business",
    "precompute-status",
    client.mode,
    selectedYear,
    selectedReportDate,
  ] as const;
  const precomputeStatusQuery = useQuery({
    queryKey: precomputeStatusQueryKey,
    enabled: Boolean(selectedReportDate && selectedYear && viewMode !== "formal"),
    queryFn: () => client.getPnlByBusinessPrecomputeStatus(selectedYear, selectedReportDate),
    retry: false,
    refetchInterval: (query) => {
      const taskStatus = query.state.data?.status;
      return taskStatus === "queued" || taskStatus === "running" ? 5_000 : false;
    },
  });
  const rebuildPrecomputeMutation = useMutation({
    mutationFn: (selection: { year: number; reportDate: string }) =>
      client.rebuildPnlByBusinessPrecompute(selection.year, selection.reportDate),
    onSuccess: async (queuedStatus, selection) => {
      const submittedStatusQueryKey = [
        "pnl-by-business",
        "precompute-status",
        client.mode,
        selection.year,
        selection.reportDate,
      ] as const;
      queryClient.setQueryData(submittedStatusQueryKey, queuedStatus);
      await queryClient.refetchQueries({
        queryKey: submittedStatusQueryKey,
        exact: true,
        type: "all",
      });
    },
  });

  useEffect(() => {
    const taskStatus = precomputeStatusQuery.data?.status;
    const runId = precomputeStatusQuery.data?.run_id ?? null;
    if ((taskStatus === "queued" || taskStatus === "running") && runId) {
      precomputeTrackedRunIdRef.current = runId;
      return;
    }
    if (
      taskStatus === "completed" &&
      precomputeStatusQuery.data?.is_current &&
      runId &&
      precomputeTrackedRunIdRef.current === runId
    ) {
      precomputeTrackedRunIdRef.current = null;
      void queryClient.invalidateQueries({ queryKey: ["pnl-by-business"] });
    }
  }, [precomputeStatusQuery.data, queryClient]);

  return { precomputeStatusQuery, rebuildPrecomputeMutation };
}

export function usePnlByBusinessPublishedInsights({
  client,
  selectedYear,
  selectedReportDate,
  viewMode,
  precomputeStatusQuery,
}: {
  client: ApiClient;
  selectedYear: number;
  selectedReportDate: string;
  viewMode: PnlByBusinessViewMode;
  precomputeStatusQuery: ReturnType<typeof usePnlByBusinessPrecompute>["precomputeStatusQuery"];
}) {
  const precomputeStatus = precomputeStatusQuery.data;
  const usesReadinessProtocol =
    precomputeStatusQuery.isSuccess && usesPnlByBusinessReadinessProtocol(precomputeStatus);
  const publishedInsightsGeneration =
    usesReadinessProtocol &&
    precomputeStatus?.readiness === "ready" &&
    precomputeStatus.generation
      ? precomputeStatus.generation
      : null;
  const legacyInsightsReadAllowed =
    precomputeStatusQuery.isSuccess &&
    precomputeStatus !== undefined &&
    !usesPnlByBusinessReadinessProtocol(precomputeStatus);
  const publishedInsightsReadAllowed =
    usesReadinessProtocol && publishedInsightsGeneration !== null;
  const businessInsightsQuery = useQuery({
    queryKey: [
      "pnl-by-business",
      "insights",
      client.mode,
      selectedYear,
      selectedReportDate,
      publishedInsightsGeneration ?? "legacy",
    ],
    enabled: Boolean(
      selectedReportDate &&
      selectedYear &&
      viewMode === "ytd" &&
      (legacyInsightsReadAllowed || publishedInsightsReadAllowed),
    ),
    queryFn: ({ signal }) =>
      client.getPnlByBusinessInsights(
        selectedYear,
        selectedReportDate,
        publishedInsightsGeneration
          ? { signal, generation: publishedInsightsGeneration }
          : { signal },
      ),
    retry: false,
  });
  const approvedBusinessInsightsEnvelope = useMemo(() =>
    resolveApprovedPnlByBusinessInsightsEnvelope({
      envelope: businessInsightsQuery.data,
      insightsQuerySucceeded: businessInsightsQuery.isSuccess,
      legacyReadAllowed: legacyInsightsReadAllowed,
      precomputeStatusQuerySucceeded: precomputeStatusQuery.isSuccess,
      publishedGeneration: publishedInsightsGeneration,
      publishedReadAllowed: publishedInsightsReadAllowed,
      selectedReportDate,
      usesReadinessProtocol,
    }), [
    businessInsightsQuery.data,
    businessInsightsQuery.isSuccess,
    legacyInsightsReadAllowed,
    precomputeStatusQuery.isSuccess,
    publishedInsightsGeneration,
    publishedInsightsReadAllowed,
    selectedReportDate,
    usesReadinessProtocol,
  ]);
  const businessInsightsBoundaryLoading =
    viewMode === "ytd" &&
    (precomputeStatusQuery.isLoading ||
      (publishedInsightsReadAllowed || legacyInsightsReadAllowed) && businessInsightsQuery.isLoading);
  const businessInsightsBoundaryError =
    viewMode === "ytd" &&
    (precomputeStatusQuery.isError ||
      (precomputeStatusQuery.isSuccess &&
        usesReadinessProtocol &&
        (!publishedInsightsReadAllowed || precomputeStatus?.readiness !== "ready")) ||
      businessInsightsQuery.isError ||
      (businessInsightsQuery.isSuccess && approvedBusinessInsightsEnvelope === undefined));
  const businessInsightsLeadershipModel = useMemo(
    () =>
      buildPnlByBusinessInsightsLeadershipModel({
        requestedDate: selectedReportDate,
        envelope: approvedBusinessInsightsEnvelope,
        isLoading: businessInsightsBoundaryLoading,
        isError: businessInsightsBoundaryError,
      }),
    [
      approvedBusinessInsightsEnvelope,
      businessInsightsBoundaryError,
      businessInsightsBoundaryLoading,
      selectedReportDate,
    ],
  );

  return { approvedBusinessInsightsEnvelope, businessInsightsLeadershipModel };
}
