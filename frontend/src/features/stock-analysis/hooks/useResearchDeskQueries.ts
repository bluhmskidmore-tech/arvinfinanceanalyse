import { useQuery } from "@tanstack/react-query";

import type { ApiClient } from "../../../api/client";
import { normalizeIsoCalendarDate } from "../lib/stockAnalysisDate";
import { stockAnalysisReadQueryOptions } from "../lib/stockAnalysisQueryOptions";

function receivedToForAsOfDate(asOfDate: string): string {
  return `${asOfDate.slice(0, 10)}T23:59:59Z`;
}

/**
 * 研究台按选中标的读取的三个接口：个股详情、K 线分析、Choice 新闻。
 *
 * 新闻的 as_of 以策略 as_of 为主，缺失时回退到详情接口真实返回的 as_of_date，
 * 所以该派生值只能在这里算并回传给页面的研究台模型。
 */
export function useResearchDeskQueries({
  client,
  selectedCandidate,
  asOfDate,
  analyticsAsOf,
}: {
  client: ApiClient;
  selectedCandidate: { stockCode: string } | null;
  asOfDate: string | undefined;
  analyticsAsOf: string | null;
}) {
  const detailQuery = useQuery({
    queryKey: [
      "stock-analysis",
      "livermore-stock-detail",
      selectedCandidate?.stockCode ?? "__none",
      asOfDate ?? null,
      60,
    ] as const,
    queryFn: () =>
      client.getLivermoreStockDetail({
        stockCode: selectedCandidate?.stockCode ?? "",
        asOfDate,
        lookback: 60,
      }),
    enabled: selectedCandidate != null,
    ...stockAnalysisReadQueryOptions,
  });
  const klineQuery = useQuery({
    queryKey: [
      "stock-analysis",
      "kline-analysis",
      selectedCandidate?.stockCode ?? "__none",
      asOfDate ?? null,
      60,
    ] as const,
    queryFn: () =>
      client.getStockKlineAnalysis({
        stockCode: selectedCandidate?.stockCode ?? "",
        asOfDate,
        lookback: 60,
      }),
    enabled: selectedCandidate != null,
    ...stockAnalysisReadQueryOptions,
  });
  const resolvedDetailAsOfDate = normalizeIsoCalendarDate(detailQuery.data?.result?.as_of_date);
  const newsAsOfDate = analyticsAsOf ?? resolvedDetailAsOfDate ?? null;
  const newsQuery = useQuery({
    queryKey: [
      "stock-analysis",
      "choice-news-latest",
      selectedCandidate?.stockCode ?? "__none",
      newsAsOfDate,
      10,
    ] as const,
    queryFn: () =>
      client.getChoiceNewsEvents({
        limit: 10,
        offset: 0,
        stockCode: selectedCandidate?.stockCode ?? undefined,
        receivedTo: receivedToForAsOfDate(newsAsOfDate ?? ""),
      }),
    enabled: selectedCandidate != null && newsAsOfDate != null,
    ...stockAnalysisReadQueryOptions,
  });

  return {
    detailQuery,
    klineQuery,
    newsQuery,
    newsAsOfDate,
  };
}
