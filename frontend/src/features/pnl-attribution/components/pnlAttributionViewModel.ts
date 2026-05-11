import type {
  AdvancedAttributionSummary,
  Numeric,
  PnlCompositionPayload,
  TPLMarketCorrelationPayload,
  VolumeRateAttributionPayload,
} from "../../../api/contracts";

export type PnlAttributionTab = "volume-rate" | "tpl-market" | "composition" | "advanced";

const MISSING_DISPLAY = "—";

export function numericRaw(value: Numeric | null | undefined): number | null | undefined {
  if (value === null || value === undefined) {
    return undefined;
  }
  return value.raw ?? undefined;
}

export function formatYi(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return MISSING_DISPLAY;
  }
  const yi = value / 100_000_000;
  return `${yi >= 0 ? "+" : ""}${yi.toFixed(2)} 亿`;
}

export function formatYiNumeric(value: Numeric | null | undefined): string {
  const display = value?.display?.trim();
  if (display) {
    return display;
  }
  return formatYi(numericRaw(value));
}

export function formatMetaDateLabel(
  activeTab: PnlAttributionTab,
  options: {
    volumeRateData: VolumeRateAttributionPayload | null;
    tplMarketData: TPLMarketCorrelationPayload | null;
    compositionData: PnlCompositionPayload | null;
    advancedSummary: AdvancedAttributionSummary | null;
  },
) {
  if (activeTab === "volume-rate") {
    return {
      label: "当前期间",
      value: options.volumeRateData?.current_period ?? MISSING_DISPLAY,
    };
  }
  if (activeTab === "tpl-market") {
    const start = options.tplMarketData?.start_period;
    const end = options.tplMarketData?.end_period;
    return {
      label: "观察区间",
      value: start && end ? `${start} ~ ${end}` : MISSING_DISPLAY,
    };
  }
  if (activeTab === "composition") {
    return {
      label: "报告日期",
      value: options.compositionData?.report_date ?? options.compositionData?.report_period ?? MISSING_DISPLAY,
    };
  }
  return {
    label: "报告日期",
    value: options.advancedSummary?.report_date ?? MISSING_DISPLAY,
  };
}
