import type {
  AdvancedAttributionSummary,
  Numeric,
  PnlCompositionPayload,
  ProductCategoryAttributionPayload,
  ProductCategoryPnlPayload,
  TPLMarketCorrelationPayload,
  VolumeRateAttributionPayload,
} from "../../../api/contracts";

export type PnlAttributionTab = "volume-rate" | "tpl-market" | "composition" | "product-category" | "advanced";
export type MissingCommonDateSource = "none" | "business" | "product-category" | "both";
export type VolumeRateBridgeStatus = "closed" | "residual" | "missing" | "no-prior";

export type CommonReportDateResolution = {
  reportDate: string | null;
  hasCommonDate: boolean;
  missingSource: MissingCommonDateSource;
  commonDates: string[];
  businessDates: string[];
  productCategoryDates: string[];
};

export type VolumeRateBridgeSummary = {
  currentPnl: number | undefined;
  previousPnl: number | undefined;
  pnlChange: number | undefined;
  volumeEffect: number | undefined;
  rateEffect: number | undefined;
  interactionEffect: number | undefined;
  explainedEffect: number | undefined;
  unexplainedEffect: number | undefined;
  coveragePct: number | undefined;
  status: VolumeRateBridgeStatus;
  statusLabel: string;
};

const MISSING_DISPLAY = "—";
const VOLUME_RATE_CLOSURE_TOLERANCE_YUAN = 10_000;

export function numericRaw(value: Numeric | null | undefined): number | undefined {
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

export function buildVolumeRateBridgeSummary(data: VolumeRateAttributionPayload | null): VolumeRateBridgeSummary | null {
  if (!data) {
    return null;
  }

  const currentPnl = numericRaw(data.total_current_pnl);
  const previousPnl = numericRaw(data.total_previous_pnl);
  const pnlChange = numericRaw(data.total_pnl_change);
  const volumeEffect = numericRaw(data.total_volume_effect);
  const rateEffect = numericRaw(data.total_rate_effect);
  const interactionEffect = numericRaw(data.total_interaction_effect);
  const canCalculateClosure =
    data.has_previous_data &&
    pnlChange !== undefined &&
    volumeEffect !== undefined &&
    rateEffect !== undefined &&
    interactionEffect !== undefined;
  const explainedEffect = canCalculateClosure ? volumeEffect + rateEffect + interactionEffect : undefined;
  const unexplainedEffect =
    canCalculateClosure && explainedEffect !== undefined ? pnlChange - explainedEffect : undefined;
  const coveragePct =
    canCalculateClosure && explainedEffect !== undefined && pnlChange !== undefined
      ? Math.abs(pnlChange) <= VOLUME_RATE_CLOSURE_TOLERANCE_YUAN
        ? Math.abs(explainedEffect) <= VOLUME_RATE_CLOSURE_TOLERANCE_YUAN
          ? 100
          : undefined
        : (Math.abs(explainedEffect) / Math.abs(pnlChange)) * 100
      : undefined;
  const hasMaterialResidual =
    unexplainedEffect !== undefined && Math.abs(unexplainedEffect) > VOLUME_RATE_CLOSURE_TOLERANCE_YUAN;
  const status: VolumeRateBridgeStatus = !data.has_previous_data
    ? "no-prior"
    : !canCalculateClosure
      ? "missing"
      : hasMaterialResidual
        ? "residual"
        : "closed";
  const statusLabel =
    status === "closed"
      ? "归因闭合"
      : status === "residual"
        ? "存在未解释差额"
        : status === "no-prior"
          ? "无上期对比"
          : "归因字段不完整";

  return {
    currentPnl,
    previousPnl,
    pnlChange,
    volumeEffect,
    rateEffect,
    interactionEffect,
    explainedEffect,
    unexplainedEffect,
    coveragePct,
    status,
    statusLabel,
  };
}

export function formatMetaDateLabel(
  activeTab: PnlAttributionTab,
  options: {
    volumeRateData: VolumeRateAttributionPayload | null;
    tplMarketData: TPLMarketCorrelationPayload | null;
    compositionData: PnlCompositionPayload | null;
    advancedSummary: AdvancedAttributionSummary | null;
    productCategoryAttributionData?: ProductCategoryAttributionPayload | null;
    productCategoryMonthlyData?: ProductCategoryPnlPayload | null;
    productCategoryYtdData?: ProductCategoryPnlPayload | null;
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
  if (activeTab === "product-category") {
    return {
      label: "报告日期",
      value:
        options.productCategoryAttributionData?.current_report_date ??
        options.productCategoryMonthlyData?.report_date ??
        options.productCategoryYtdData?.report_date ??
        MISSING_DISPLAY,
    };
  }
  return {
    label: "报告日期",
    value: options.advancedSummary?.report_date ?? MISSING_DISPLAY,
  };
}

function normalizeReportDates(dates: readonly string[] | null | undefined): string[] {
  return Array.from(new Set((dates ?? []).map((date) => String(date).trim()).filter(Boolean))).sort((a, b) =>
    b.localeCompare(a),
  );
}

export function resolveCommonReportDate(options: {
  businessDates: readonly string[] | null | undefined;
  productCategoryDates: readonly string[] | null | undefined;
  preferredReportDate?: string | null;
}): CommonReportDateResolution {
  const businessDates = normalizeReportDates(options.businessDates);
  const productCategoryDates = normalizeReportDates(options.productCategoryDates);
  const businessSet = new Set(businessDates);
  const productCategorySet = new Set(productCategoryDates);
  const commonDates = businessDates.filter((date) => productCategorySet.has(date));
  const preferred = options.preferredReportDate?.trim();
  const reportDate =
    preferred && businessSet.has(preferred) && productCategorySet.has(preferred) ? preferred : commonDates[0] ?? null;
  const missingSource: MissingCommonDateSource =
    businessDates.length === 0 && productCategoryDates.length === 0
      ? "both"
      : businessDates.length === 0
        ? "business"
        : productCategoryDates.length === 0
          ? "product-category"
          : "none";
  return {
    reportDate,
    hasCommonDate: reportDate !== null,
    missingSource,
    commonDates,
    businessDates,
    productCategoryDates,
  };
}
