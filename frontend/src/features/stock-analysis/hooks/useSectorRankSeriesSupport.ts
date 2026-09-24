import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import type { ApiClient } from "../../../api/client";
import { buildSectorSeriesTrendOption } from "../lib/stockAnalysisChartModel";
import { buildSectorRowsFromSectorSeries } from "../lib/stockAnalysisPageModel";
import {
  buildSectorSeriesTrendLines,
  latestSectorSeriesTableRows,
  localizeSectorSeriesUnsupportedNotes,
} from "../lib/stockAnalysisSectorSeriesModel";
import { stockAnalysisReadQueryOptions } from "../lib/stockAnalysisQueryOptions";
import type { SectorSeriesWindow } from "./useSectorPanelState";

export function useSectorRankSeriesSupport({
  client,
  analyticsAsOf,
  sectorSeriesWindow,
  sectorSeriesExpanded,
  shouldLoadFallback,
}: {
  client: ApiClient;
  analyticsAsOf: string | null;
  sectorSeriesWindow: SectorSeriesWindow;
  sectorSeriesExpanded: boolean;
  shouldLoadFallback: boolean;
}) {
  const sectorRankSeriesQuery = useQuery({
    queryKey: ["stock-analysis", "livermore-sector-rank-series", analyticsAsOf ?? "__none", sectorSeriesWindow] as const,
    queryFn: () =>
      client.getLivermoreSectorRankSeries({
        asOfDate: analyticsAsOf ?? undefined,
        windowDays: sectorSeriesWindow,
        topK: 10,
      }),
    enabled: Boolean((sectorSeriesExpanded || shouldLoadFallback) && analyticsAsOf),
    ...stockAnalysisReadQueryOptions,
  });

  const sectorSeriesTableRows = useMemo(() => {
    const envelope = sectorRankSeriesQuery.data?.result;
    const series = envelope?.series;
    if (!series || envelope?.state !== "ok") {
      return [];
    }
    return latestSectorSeriesTableRows(series);
  }, [sectorRankSeriesQuery.data?.result]);

  const sectorSeriesFallbackRows = useMemo(
    () => buildSectorRowsFromSectorSeries(sectorSeriesTableRows),
    [sectorSeriesTableRows],
  );

  const sectorSeriesTrendLines = useMemo(() => {
    const envelope = sectorRankSeriesQuery.data?.result;
    const series = envelope?.series;
    if (!series || envelope?.state !== "ok") {
      return [];
    }
    return buildSectorSeriesTrendLines(series, 5);
  }, [sectorRankSeriesQuery.data?.result]);

  const sectorSeriesTrendChartOption = useMemo(
    () => buildSectorSeriesTrendOption(sectorSeriesTrendLines),
    [sectorSeriesTrendLines],
  );

  const sectorSeriesUnsupportedNotes = useMemo(
    () => localizeSectorSeriesUnsupportedNotes(sectorRankSeriesQuery.data?.result?.unsupported_notes),
    [sectorRankSeriesQuery.data?.result?.unsupported_notes],
  );

  return {
    sectorRankSeriesQuery,
    sectorSeriesFallbackRows,
    sectorSeriesTableRows,
    sectorSeriesTrendChartOption,
    sectorSeriesTrendLines,
    sectorSeriesUnsupportedNotes,
  };
}
