import { getMarketModuleDrilldowns } from "../module-home/marketModuleDrilldowns";
import type { MarketWorkbenchPageKey } from "./types";

const MARKET_WORKBENCH_NAV_KEYS = new Set<MarketWorkbenchPageKey>([
  "cross-asset",
  "market-overview",
  "market-data",
  "macro-observation",
  "macro-toolkit",
  "stock-analysis",
  "news-events",
]);

const MARKET_WORKBENCH_NAV_INITIALS: Record<MarketWorkbenchPageKey, string> = {
  "cross-asset": "XA",
  "market-overview": "HO",
  "market-data": "MD",
  "macro-observation": "MO",
  "macro-toolkit": "MT",
  "stock-analysis": "EQ",
  "news-events": "NE",
};

export type MarketWorkbenchNavItem = {
  key: MarketWorkbenchPageKey;
  label: string;
  path: string;
  description: string;
  statusLabel: string;
  iconLabel: string;
};

export function getMarketWorkbenchNav(): MarketWorkbenchNavItem[] {
  return getMarketModuleDrilldowns()
    .filter((item) => MARKET_WORKBENCH_NAV_KEYS.has(item.key as MarketWorkbenchPageKey))
    .map((item) => {
      const key = item.key as MarketWorkbenchPageKey;
      return {
        key,
        label: item.label,
        path: item.path,
        description: item.description,
        statusLabel: item.statusLabel,
        iconLabel: MARKET_WORKBENCH_NAV_INITIALS[key],
      };
    });
}
