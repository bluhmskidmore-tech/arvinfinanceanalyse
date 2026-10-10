import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { type ApiClient } from "../../api/client";
import { apiQueryKeys } from "../../api/queryKeys";
import { type PnlByBusinessAnalysisDimension, type PnlByBusinessYtdItem } from "../../api/contracts";
import { type MainBreakdownDimension } from "./pnlByBusinessAnalysisOptions";
import { type PnlByBusinessViewMode } from "./pnlByBusinessPageModel";

const ANALYSIS_QUERY_STALE_MS = 5 * 60 * 1000;

/** 按既有阶段顺序读取月报、四类趋势和多维分析，业务总表就绪后才启用重查询。 */
export function usePnlByBusinessAnalysisQueries({
  client,
  selectedYear,
  selectedReportDate,
  viewMode,
  selectedBusinessRow,
  analysisDimension,
  mainBreakdownDimension,
  analysisBaseReady,
}: {
  client: ApiClient;
  selectedYear: number;
  selectedReportDate: string;
  viewMode: PnlByBusinessViewMode;
  selectedBusinessRow: PnlByBusinessYtdItem | undefined;
  analysisDimension: PnlByBusinessAnalysisDimension;
  mainBreakdownDimension: MainBreakdownDimension;
  analysisBaseReady: boolean;
}) {
  const [analysisLoadStage, setAnalysisLoadStage] = useState(0);
  useEffect(() => {
    setAnalysisLoadStage(0);
  }, [selectedReportDate, selectedBusinessRow?.row_key, viewMode]);
  useEffect(() => {
    if (!analysisBaseReady || analysisLoadStage !== 0) {
      return;
    }
    setAnalysisLoadStage(1);
  }, [analysisBaseReady, analysisLoadStage]);

  const monthlyBusinessQuery = useQuery({
    queryKey: ["pnl-by-business", "monthly-business", client.mode, selectedYear, selectedReportDate],
    enabled: Boolean(
      selectedReportDate &&
        selectedYear &&
        (viewMode === "monthly" || (viewMode === "ytd" && analysisBaseReady && analysisLoadStage >= 1)),
    ),
    queryFn: () => client.getPnlByBusinessMonthly(selectedYear, selectedReportDate),
    retry: false,
    staleTime: ANALYSIS_QUERY_STALE_MS,
  });

  const mainBreakdownQuery = useQuery({
    queryKey: apiQueryKeys.pnlByBusinessAnalysis(
      client.mode,
      selectedYear,
      selectedReportDate,
      mainBreakdownDimension,
      selectedBusinessRow?.row_key,
    ),
    enabled: analysisBaseReady,
    queryFn: () =>
      client.getPnlByBusinessAnalysis({
        year: selectedYear,
        asOfDate: selectedReportDate,
        businessKey: selectedBusinessRow!.row_key,
        dimension: mainBreakdownDimension,
      }),
    retry: false,
    staleTime: ANALYSIS_QUERY_STALE_MS,
  });
  const mainBreakdownRows = mainBreakdownQuery.data?.result.rows ?? [];

  const analysisQuery = useQuery({
    queryKey: apiQueryKeys.pnlByBusinessAnalysis(
      client.mode,
      selectedYear,
      selectedReportDate,
      analysisDimension,
      selectedBusinessRow?.row_key,
    ),
    enabled: Boolean(analysisBaseReady && analysisLoadStage >= 4),
    queryFn: () =>
      client.getPnlByBusinessAnalysis({
        year: selectedYear,
        asOfDate: selectedReportDate,
        businessKey: selectedBusinessRow!.row_key,
        dimension: analysisDimension,
      }),
    retry: false,
    staleTime: ANALYSIS_QUERY_STALE_MS,
  });
  const analysisRows = analysisQuery.data?.result.rows ?? [];

  const bondBucketQuery = useQuery({
    queryKey: apiQueryKeys.pnlByBusinessAnalysis(
      client.mode,
      selectedYear,
      selectedReportDate,
      "bond_bucket",
    ),
    enabled: Boolean(analysisBaseReady && analysisLoadStage >= 2),
    queryFn: () =>
      client.getPnlByBusinessAnalysis({
        year: selectedYear,
        asOfDate: selectedReportDate,
        dimension: "bond_bucket",
      }),
    retry: false,
    staleTime: ANALYSIS_QUERY_STALE_MS,
  });
  const bondBucketRows = bondBucketQuery.data?.result.rows ?? [];

  const bondBucketMonthlyQuery = useQuery({
    queryKey: apiQueryKeys.pnlByBusinessAnalysis(
      client.mode,
      selectedYear,
      selectedReportDate,
      "bond_bucket_monthly",
    ),
    enabled: Boolean(analysisBaseReady && analysisLoadStage >= 3),
    queryFn: () =>
      client.getPnlByBusinessAnalysis({
        year: selectedYear,
        asOfDate: selectedReportDate,
        dimension: "bond_bucket_monthly",
      }),
    retry: false,
    staleTime: ANALYSIS_QUERY_STALE_MS,
  });
  const bondBucketMonthlyRows = bondBucketMonthlyQuery.data?.result.rows ?? [];

  const instrumentAnalysisQuery = useQuery({
    queryKey: [
      ...apiQueryKeys.pnlByBusinessAnalysis(
        client.mode,
        selectedYear,
        selectedReportDate,
        "instrument",
        selectedBusinessRow?.row_key,
      ),
      "selected-business-drilldown",
    ],
    enabled: Boolean(analysisBaseReady),
    queryFn: () =>
      client.getPnlByBusinessAnalysis({
        year: selectedYear,
        asOfDate: selectedReportDate,
        businessKey: selectedBusinessRow!.row_key,
        dimension: "instrument",
      }),
    retry: false,
    staleTime: ANALYSIS_QUERY_STALE_MS,
  });
  const instrumentAnalysisRows = instrumentAnalysisQuery.data?.result.rows ?? [];
  useEffect(() => {
    if (analysisLoadStage === 1 && (monthlyBusinessQuery.isSuccess || monthlyBusinessQuery.isError)) {
      setAnalysisLoadStage(2);
    }
  }, [analysisLoadStage, monthlyBusinessQuery.isError, monthlyBusinessQuery.isSuccess]);

  useEffect(() => {
    if (analysisLoadStage === 2 && (bondBucketQuery.isSuccess || bondBucketQuery.isError)) {
      setAnalysisLoadStage(3);
    }
  }, [analysisLoadStage, bondBucketQuery.isError, bondBucketQuery.isSuccess]);

  useEffect(() => {
    if (analysisLoadStage === 3 && (bondBucketMonthlyQuery.isSuccess || bondBucketMonthlyQuery.isError)) {
      setAnalysisLoadStage(4);
    }
  }, [analysisLoadStage, bondBucketMonthlyQuery.isError, bondBucketMonthlyQuery.isSuccess]);

  useEffect(() => {
    if (analysisLoadStage === 4 && (analysisQuery.isSuccess || analysisQuery.isError)) {
      setAnalysisLoadStage(5);
    }
  }, [analysisLoadStage, analysisQuery.isError, analysisQuery.isSuccess]);

  return {
    analysisLoadStage,
    setAnalysisLoadStage,
    monthlyBusinessQuery,
    mainBreakdownQuery,
    mainBreakdownRows,
    analysisQuery,
    analysisRows,
    bondBucketQuery,
    bondBucketRows,
    bondBucketMonthlyQuery,
    bondBucketMonthlyRows,
    instrumentAnalysisQuery,
    instrumentAnalysisRows,
  };
}
