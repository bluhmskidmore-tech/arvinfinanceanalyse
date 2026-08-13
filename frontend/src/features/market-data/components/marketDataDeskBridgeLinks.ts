import { EM_DASH } from "../../../utils/format";

export type MarketDataWorkbenchLink = {
  testId: string;
  label: string;
  to: string;
};

export const MARKET_DATA_WORKBENCH_LINKS: MarketDataWorkbenchLink[] = [
  {
    testId: "market-data-bridge-link-overview",
    label: "市场工作台 →",
    to: "/market-overview",
  },
  {
    testId: "market-data-bridge-link-cross-asset",
    label: "跨资产 →",
    to: "/cross-asset",
  },
  {
    testId: "market-data-bridge-link-macro-toolkit",
    label: "宏观工具 →",
    to: "/macro-toolkit",
  },
];

export function marketDataPageHref(path: string, watchDate?: string): string {
  if (!watchDate || watchDate === EM_DASH) {
    return path;
  }
  return `${path}?date=${encodeURIComponent(watchDate)}`;
}
