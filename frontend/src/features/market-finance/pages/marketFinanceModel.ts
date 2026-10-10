import type { ChoiceMacroLatestPoint } from "../../../api/contracts";

export type MarketFinanceRepresentativeSeries = {
  key: "cn-gov-10y" | "dr007" | "usdcny" | "credit-aaa";
  label: string;
  ids: readonly string[];
};

export const MARKET_FINANCE_REPRESENTATIVE_SERIES: readonly MarketFinanceRepresentativeSeries[] = [
  {
    key: "cn-gov-10y",
    label: "10年国债",
    ids: ["CA.CN_GOV_10Y", "E1000180", "EMM00166466"],
  },
  {
    key: "dr007",
    label: "DR007",
    ids: ["CA.DR007", "M002", "EMM00167613"],
  },
  {
    key: "usdcny",
    label: "人民币汇率",
    ids: ["CA.USDCNY", "EMM00058124"],
  },
  {
    key: "credit-aaa",
    label: "信用利差 中短票AAA",
    ids: ["CN_CREDIT_AAA_1Y", "S0059650", "EMM00166655"],
  },
];

export type SelectedMarketFinanceSeries = MarketFinanceRepresentativeSeries & {
  point: ChoiceMacroLatestPoint | null;
};

export function pickRepresentativeSeries(
  points: readonly ChoiceMacroLatestPoint[],
  whitelist: readonly MarketFinanceRepresentativeSeries[] =
    MARKET_FINANCE_REPRESENTATIVE_SERIES,
): SelectedMarketFinanceSeries[] {
  const candidates = points.filter(
    (point) => (point.refresh_tier ?? "stable") !== "isolated",
  );

  return whitelist.map((representative) => {
    const point = representative.ids
      .map((id) => candidates.find((candidate) => candidate.series_id === id))
      .find((candidate): candidate is ChoiceMacroLatestPoint => Boolean(candidate));

    return { ...representative, point: point ?? null };
  });
}
