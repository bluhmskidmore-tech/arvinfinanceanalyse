import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import type { LivermoreStrategyPayload } from "../../../api/contracts";
import { useApiClient } from "../../../api/clientContext";
import { useDeferredSectionSeen } from "../../../hooks/useDeferredSectionSeen";
import {
  buildSectorHeavyweightPreview,
  type StockSectorHeavyweightPreviewRow,
  type StockSectorHeavyweightPreviewSummary,
} from "../lib/stockAnalysisPageModel";
import { stockAnalysisReadQueryOptions } from "../lib/stockAnalysisQueryOptions";
import {
  buildHeavyweightTrendIndex,
  type StockHeavyweightTrendIndex,
} from "../lib/stockHeavyweightTrendView";

const TREND_WINDOW_DAYS = 20;
const TREND_STOCKS_PER_SECTOR = 3;

export type StockHeavyweightSection = {
  preview: StockSectorHeavyweightPreviewSummary | null;
  rows: StockSectorHeavyweightPreviewRow[];
  trends: StockHeavyweightTrendIndex;
  sectionRef: (node: HTMLElement | null) => void;
};

/**
 * Data for the 权重股摘要 card: the workbench-derived sector leaders plus their
 * 20-session close trends.
 *
 * The trend request is gated on the card scrolling into view (and on the deep
 * research zone being open) so the first screen never pays for ~24 extra close
 * series it may not display.
 */
export function useStockHeavyweightSection({
  strategyPayload,
  deepResearchOpen,
}: {
  strategyPayload: LivermoreStrategyPayload | null;
  deepResearchOpen: boolean;
}): StockHeavyweightSection {
  const client = useApiClient();
  const asOfDate = strategyPayload?.as_of_date ?? null;
  const section = useDeferredSectionSeen<HTMLElement>(Boolean(asOfDate));

  const preview = useMemo(
    () => (strategyPayload ? buildSectorHeavyweightPreview(strategyPayload) : null),
    [strategyPayload],
  );
  const rows = useMemo(
    () => preview?.rows.filter((row) => row.stocks.length > 0) ?? [],
    [preview],
  );

  const sectorLimit = preview?.sectorLimit ?? 8;
  const trendQuery = useQuery({
    queryKey: ["stock-analysis", "heavyweight-trends", asOfDate ?? "__none", sectorLimit],
    queryFn: () =>
      client.getStockHeavyweightTrends({
        ...(asOfDate ? { asOfDate } : {}),
        windowDays: TREND_WINDOW_DAYS,
        sectorLimit,
        stocksPerSector: TREND_STOCKS_PER_SECTOR,
      }),
    enabled: Boolean(asOfDate) && deepResearchOpen && section.seen,
    ...stockAnalysisReadQueryOptions,
  });

  const trends = useMemo(
    () => buildHeavyweightTrendIndex(trendQuery.data?.result),
    [trendQuery.data?.result],
  );

  return { preview, rows, trends, sectionRef: section.ref };
}
