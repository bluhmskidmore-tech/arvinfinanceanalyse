import { useQuery } from "@tanstack/react-query";

import type { DateString } from "../../data-structures/BondModel";
import { useBondWorkspace } from "../context/BondContext";
import type { BondApiService } from "../services/api";

export interface UseMarketDataOptions {
  api?: BondApiService;
  asOfDate?: DateString;
  bondId?: string | null;
  enabled?: boolean;
}

export function useMarketData(options: UseMarketDataOptions = {}) {
  const workspace = useBondWorkspace();
  const api = options.api ?? workspace.api;
  const bondId = options.bondId ?? workspace.selectedBondId;

  const yieldCurveQuery = useQuery({
    queryKey: ["bond-foundation", "market", "yield-curve", options.asOfDate],
    queryFn: () => api.getYieldCurve({ asOfDate: options.asOfDate }),
    enabled: options.enabled !== false,
  });

  const marketIndicesQuery = useQuery({
    queryKey: ["bond-foundation", "market", "indices", options.asOfDate],
    queryFn: () => api.getMarketIndices({ asOfDate: options.asOfDate }),
    enabled: options.enabled !== false,
  });

  const priceHistoryQuery = useQuery({
    queryKey: ["bond-foundation", "market", "price-history", bondId, options.asOfDate],
    queryFn: () => api.getBondPriceHistory(bondId as string),
    enabled: Boolean(bondId) && options.enabled !== false,
  });

  const yieldHistoryQuery = useQuery({
    queryKey: ["bond-foundation", "market", "yield-history", bondId, options.asOfDate],
    queryFn: () => api.getBondYieldHistory(bondId as string),
    enabled: Boolean(bondId) && options.enabled !== false,
  });

  return {
    yieldCurve: yieldCurveQuery.data,
    marketIndices: marketIndicesQuery.data?.indices ?? [],
    priceHistory: priceHistoryQuery.data ?? [],
    yieldHistory: yieldHistoryQuery.data ?? [],
    yieldCurveQuery,
    marketIndicesQuery,
    priceHistoryQuery,
    yieldHistoryQuery,
  };
}
