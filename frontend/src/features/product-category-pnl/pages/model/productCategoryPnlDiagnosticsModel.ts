import type { ProductCategoryCandidateMetricStatus } from "./productCategoryPnlModelInternals";
import type {
  DecimalLike,
  ProductCategoryPnlRow,
  ProductCategoryInterestSpreadPayload,
} from "../../../../api/contracts";
import {
  formatProductCategoryValue,
  formatProductCategoryYieldValue,
  formatProductCategoryRowDisplayValue,
} from "./productCategoryPnlDisplayModel";
import { EM_DASH } from "../../../../utils/format";
import {
  decimalNumberInternal as decimalNumber,
  productCategorySideLabelInternal as productCategorySideLabel,
  toneNameForValueInternal as toneNameForValue,
  formatProductCategoryReportMonthLabelInternal as formatProductCategoryReportMonthLabel,
  bpLabelInternal as bpLabel,
  signedBpLabelInternal as signedBpLabel,
  PRODUCT_CATEGORY_CANDIDATE_METRIC_STATUS,
  interestSpreadMetricNumberInternal as interestSpreadMetricNumber,
} from "./productCategoryPnlModelInternals";
import type { ProductCategoryTrendSnapshot } from "../productCategoryPnlPageModel";

export type ProductCategoryDiagnosticsMatrixRow = {
  categoryId: string;
  categoryLabel: string;
  sideLabel: string;
  scaleLabel: string;
  scaleMissing: boolean;
  businessNetIncomeLabel: string;
  businessNetIncomeTone: "neutral" | "positive" | "negative";
  yieldLabel: string;
  yieldMissing: boolean;
  cnyNetLabel: string;
  cnyNetTone: "neutral" | "positive" | "negative";
  foreignNetLabel: string;
  foreignNetTone: "neutral" | "positive" | "negative";
  driverHint: string;
};

export type ProductCategoryNegativeContributionRow = {
  categoryId: string;
  categoryLabel: string;
  sideLabel: string;
  lossLabel: string;
  scaleLabel: string;
  scaleMissing: boolean;
  yieldLabel: string;
  yieldMissing: boolean;
  driverHint: string;
};

type ProductCategorySpreadMovementAttributionBase = {
  currentLabel: string;
  priorLabel: string;
  currentAssetYieldLabel: string;
  currentLiabilityYieldLabel: string;
  currentSpreadLabel: string;
  priorSpreadLabel: string;
  assetYieldDeltaLabel: string;
  liabilityYieldDeltaLabel: string;
  spreadDeltaLabel: string;
  driverHint: string;
};

export type ProductCategorySpreadMovementAttribution =
  | ({
      state: "ready";
    } & ProductCategorySpreadMovementAttributionBase)
  | ({
      state: "incomplete";
      reason: string;
    } & ProductCategorySpreadMovementAttributionBase);

export type ProductCategoryDiagnosticsSurface = {
  metricStatus: ProductCategoryCandidateMetricStatus;
  headlineTotalLabel: string | null;
  matrixRows: ProductCategoryDiagnosticsMatrixRow[];
  matrixEmptyCopy: string | null;
  negativeWatchlistRows: ProductCategoryNegativeContributionRow[];
  negativeWatchlistEmptyCopy: string | null;
  spreadAttribution: ProductCategorySpreadMovementAttribution;
};

function formatProductCategoryDiagnosticMoneyLabel(
  value: DecimalLike | null | undefined,
): string {
  const display = formatProductCategoryValue(value);
  return display === EM_DASH ? "\u7f3a\u5931" : `${display} \u4ebf\u5143`;
}

function formatProductCategoryDiagnosticYieldLabel(
  value: DecimalLike | null | undefined,
): { label: string; missing: boolean } {
  const display = formatProductCategoryYieldValue(value);
  if (display === EM_DASH) {
    return { label: "\u6536\u76ca\u7387\u7f3a\u5931", missing: true };
  }
  return { label: `${display}%`, missing: false };
}

function dominantNetHint(label: string, value: number | null): string | null {
  if (value === null || value === 0) {
    return null;
  }
  return value > 0
    ? `${label}\u51c0\u6536\u5165\u4e3b\u5bfc`
    : `${label}\u51c0\u6536\u5165\u627f\u538b`;
}

function buildProductCategoryDriverHint(row: ProductCategoryPnlRow): string {
  const hints: string[] = [];
  const cnyNet = decimalNumber(row.cny_net);
  const foreignNet = decimalNumber(row.foreign_net);
  const cnyCash = decimalNumber(row.cny_cash);
  const foreignCash = decimalNumber(row.foreign_cash);
  const cnyFtp = decimalNumber(row.cny_ftp);
  const foreignFtp = decimalNumber(row.foreign_ftp);

  if (cnyNet === null && foreignNet === null) {
    hints.push("\u51c0\u6536\u5165\u62c6\u5206\u7f3a\u5931");
  } else {
    const dominantCurrency =
      Math.abs(cnyNet ?? 0) >= Math.abs(foreignNet ?? 0)
        ? dominantNetHint("\u4eba\u6c11\u5e01", cnyNet)
        : dominantNetHint("\u5916\u5e01", foreignNet);
    if (dominantCurrency) {
      hints.push(dominantCurrency);
    }
  }

  const currencyPressureHints: string[] = [];
  if (cnyNet !== null && cnyNet < 0) {
    currencyPressureHints.push(
      "\u4eba\u6c11\u5e01\u51c0\u6536\u5165\u4e3a\u8d1f",
    );
  } else if (
    cnyCash !== null &&
    cnyFtp !== null &&
    Math.abs(cnyFtp) > Math.abs(cnyCash) &&
    Math.abs(cnyFtp) > 0
  ) {
    currencyPressureHints.push("\u4eba\u6c11\u5e01FTP\u9ad8\u4e8e\u73b0\u91d1");
  }

  if (foreignNet !== null && foreignNet < 0) {
    currencyPressureHints.push("\u5916\u5e01\u51c0\u6536\u5165\u4e3a\u8d1f");
  } else if (
    foreignCash !== null &&
    foreignFtp !== null &&
    Math.abs(foreignFtp) > Math.abs(foreignCash) &&
    Math.abs(foreignFtp) > 0
  ) {
    currencyPressureHints.push("\u5916\u5e01FTP\u9ad8\u4e8e\u73b0\u91d1");
  }

  if (currencyPressureHints.length > 0) {
    hints.push(currencyPressureHints.join("\uff0c"));
  }

  if (hints.length === 0) {
    return "\u73b0\u91d1\u3001FTP\u3001\u51c0\u6536\u5165\u62c6\u5206\u5e73\u7a33";
  }
  return hints.slice(0, 2).join("\uff1b");
}

function buildProductCategoryDiagnosticsMatrixRow(
  row: ProductCategoryPnlRow,
): ProductCategoryDiagnosticsMatrixRow {
  const scaleDisplay = formatProductCategoryRowDisplayValue(row, row.cnx_scale);
  const yieldDisplay = formatProductCategoryDiagnosticYieldLabel(
    row.weighted_yield,
  );
  return {
    categoryId: row.category_id,
    categoryLabel: row.category_name,
    sideLabel: productCategorySideLabel(row.side),
    scaleLabel:
      scaleDisplay === EM_DASH
        ? "\u89c4\u6a21\u7f3a\u5931"
        : `${scaleDisplay} \u4ebf\u5143`,
    scaleMissing: scaleDisplay === EM_DASH,
    businessNetIncomeLabel: formatProductCategoryDiagnosticMoneyLabel(
      row.business_net_income,
    ),
    businessNetIncomeTone: toneNameForValue(row.business_net_income),
    yieldLabel: yieldDisplay.label,
    yieldMissing: yieldDisplay.missing,
    cnyNetLabel: formatProductCategoryDiagnosticMoneyLabel(row.cny_net),
    cnyNetTone: toneNameForValue(row.cny_net),
    foreignNetLabel: formatProductCategoryDiagnosticMoneyLabel(
      row.foreign_net,
    ),
    foreignNetTone: toneNameForValue(row.foreign_net),
    driverHint: buildProductCategoryDriverHint(row),
  };
}

function buildSpreadMovementDriverHint(
  assetYieldDelta: number | null,
  liabilityYieldDelta: number | null,
  spreadDelta: number | null,
): string {
  if (
    assetYieldDelta === null ||
    liabilityYieldDelta === null ||
    spreadDelta === null
  ) {
    return "\u7f3a\u5c11\u5b8c\u6574\u6536\u76ca\u7387\u5bf9\u6bd4";
  }
  if (spreadDelta === 0) {
    return "\u8d44\u4ea7\u4e0e\u8d1f\u503a\u6536\u76ca\u7387\u53d8\u52a8\u57fa\u672c\u5bf9\u51b2\uff0c\u5229\u5dee\u6301\u5e73";
  }

  const assetAbs = Math.abs(assetYieldDelta);
  const liabilityAbs = Math.abs(liabilityYieldDelta);
  if (spreadDelta > 0) {
    if (assetAbs >= liabilityAbs) {
      return assetYieldDelta >= 0
        ? "\u8d44\u4ea7\u6536\u76ca\u7387\u4e0a\u884c\u4e3b\u5bfc\u5229\u5dee\u8d70\u9614"
        : "\u8d44\u4ea7\u6536\u76ca\u7387\u56de\u843d\u8f83\u7f13\uff0c\u5229\u5dee\u4ecd\u8d70\u9614";
    }
    return liabilityYieldDelta <= 0
      ? "\u8d1f\u503a\u6536\u76ca\u7387\u4e0b\u884c\u4e3b\u5bfc\u5229\u5dee\u8d70\u9614"
      : "\u8d1f\u503a\u6536\u76ca\u7387\u4e0a\u884c\u8f83\u7f13\uff0c\u5229\u5dee\u4ecd\u8d70\u9614";
  }

  if (assetAbs >= liabilityAbs) {
    return assetYieldDelta <= 0
      ? "\u8d44\u4ea7\u6536\u76ca\u7387\u4e0b\u884c\u4e3b\u5bfc\u5229\u5dee\u6536\u7a84"
      : "\u8d44\u4ea7\u6536\u76ca\u7387\u4e0a\u884c\u4e0d\u8db3\uff0c\u5229\u5dee\u6536\u7a84";
  }
  return liabilityYieldDelta >= 0
    ? "\u8d1f\u503a\u6536\u76ca\u7387\u4e0a\u884c\u4e3b\u5bfc\u5229\u5dee\u6536\u7a84"
    : "\u8d1f\u503a\u6536\u76ca\u7387\u4e0b\u884c\u4e0d\u8db3\uff0c\u5229\u5dee\u6536\u7a84";
}

function buildProductCategorySpreadMovementAttribution(input: {
  trendSnapshots?: ProductCategoryTrendSnapshot[];
  assetTotal?: ProductCategoryPnlRow | null;
  liabilityTotal?: ProductCategoryPnlRow | null;
  interestSpread?: ProductCategoryInterestSpreadPayload | null;
}): ProductCategorySpreadMovementAttribution {
  const currentSnapshot =
    input.trendSnapshots?.[0] ??
    (input.assetTotal || input.liabilityTotal
      ? {
          reportDate:
            input.assetTotal?.report_date ??
            input.liabilityTotal?.report_date ??
            "",
          rows: [],
          assetTotal: input.assetTotal,
          liabilityTotal: input.liabilityTotal,
          interestSpread: input.interestSpread ?? null,
        }
      : null);
  const priorSnapshot = input.trendSnapshots?.slice(1)[0] ?? null;

  const currentLabel =
    currentSnapshot?.label ??
    formatProductCategoryReportMonthLabel(currentSnapshot?.reportDate ?? "");
  const priorLabel =
    priorSnapshot?.label ??
    formatProductCategoryReportMonthLabel(priorSnapshot?.reportDate ?? "");
  const currentAssetYield = interestSpreadMetricNumber(
    currentSnapshot?.interestSpread?.all_currency_asset_yield_pct,
  );
  const currentLiabilityYield = interestSpreadMetricNumber(
    currentSnapshot?.interestSpread?.all_currency_liability_yield_pct,
  );
  const currentSpread = interestSpreadMetricNumber(
    currentSnapshot?.interestSpread?.all_currency_spread_pct,
  );
  const priorAssetYield = interestSpreadMetricNumber(
    priorSnapshot?.interestSpread?.all_currency_asset_yield_pct,
  );
  const priorLiabilityYield = interestSpreadMetricNumber(
    priorSnapshot?.interestSpread?.all_currency_liability_yield_pct,
  );
  const priorSpread = interestSpreadMetricNumber(
    priorSnapshot?.interestSpread?.all_currency_spread_pct,
  );
  const assetYieldDelta =
    currentAssetYield === null || priorAssetYield === null
      ? null
      : (currentAssetYield - priorAssetYield) * 100;
  const liabilityYieldDelta =
    currentLiabilityYield === null || priorLiabilityYield === null
      ? null
      : (currentLiabilityYield - priorLiabilityYield) * 100;
  const spreadDelta =
    currentSpread === null || priorSpread === null
      ? null
      : (currentSpread - priorSpread) * 100;

  const base: ProductCategorySpreadMovementAttributionBase = {
    currentLabel: currentLabel || "\u5f53\u524d\u671f",
    priorLabel: priorLabel || "\u4e0a\u671f",
    currentAssetYieldLabel:
      currentAssetYield === null
        ? "\u7f3a\u5931"
        : `${currentAssetYield.toFixed(2)}%`,
    currentLiabilityYieldLabel:
      currentLiabilityYield === null
        ? "\u7f3a\u5931"
        : `${currentLiabilityYield.toFixed(2)}%`,
    currentSpreadLabel: bpLabel(
      currentSpread === null ? null : currentSpread * 100,
    ),
    priorSpreadLabel: bpLabel(priorSpread === null ? null : priorSpread * 100),
    assetYieldDeltaLabel: signedBpLabel(assetYieldDelta),
    liabilityYieldDeltaLabel: signedBpLabel(liabilityYieldDelta),
    spreadDeltaLabel: signedBpLabel(spreadDelta),
    driverHint: buildSpreadMovementDriverHint(
      assetYieldDelta,
      liabilityYieldDelta,
      spreadDelta,
    ),
  };

  if (!currentSnapshot) {
    return {
      state: "incomplete",
      reason:
        "\u5f53\u524d\u5feb\u7167\u7f3a\u5931\uff0c\u65e0\u6cd5\u6784\u5efa\u5229\u5dee\u5f52\u56e0\u3002",
      ...base,
    };
  }
  if (currentAssetYield === null || currentLiabilityYield === null) {
    return {
      state: "incomplete",
      reason: "后端未返回资产端或负债端收益率字段，无法展示利差归因。",
      ...base,
    };
  }
  if (currentSpread === null) {
    return {
      state: "incomplete",
      reason: "后端未返回利差指标，无法展示当期利差。",
      ...base,
    };
  }
  if (!priorSnapshot || [priorAssetYield, priorLiabilityYield, priorSpread].includes(null)) {
    return {
      state: "incomplete",
      reason:
        "\u7f3a\u5c11\u53ef\u6bd4\u4e0a\u671f\u8d8b\u52bf\u5feb\u7167\uff0c\u65e0\u6cd5\u5b8c\u6210\u5229\u5dee\u53d8\u52a8\u5f52\u56e0\u3002",
      ...base,
    };
  }

  return {
    state: "ready",
    ...base,
  };
}

export function buildProductCategoryDiagnosticsSurface(input: {
  rows: ProductCategoryPnlRow[];
  trendSnapshots?: ProductCategoryTrendSnapshot[];
  assetTotal?: ProductCategoryPnlRow | null;
  liabilityTotal?: ProductCategoryPnlRow | null;
  grandTotal?: ProductCategoryPnlRow | null;
  interestSpread?: ProductCategoryInterestSpreadPayload | null;
}): ProductCategoryDiagnosticsSurface {
  const productRows = input.rows.filter(
    (row) => !row.is_total && row.category_id !== "grand_total",
  );
  const matrixRows = productRows.map(buildProductCategoryDiagnosticsMatrixRow);
  const negativeWatchlistRows = productRows
    .filter((row) => {
      const businessNetIncome = decimalNumber(row.business_net_income);
      return businessNetIncome !== null && businessNetIncome < 0;
    })
    .sort(
      (left, right) =>
        Number(left.business_net_income) - Number(right.business_net_income),
    )
    .map((row) => {
      const scaleDisplay = formatProductCategoryRowDisplayValue(
        row,
        row.cnx_scale,
      );
      const yieldDisplay = formatProductCategoryDiagnosticYieldLabel(
        row.weighted_yield,
      );
      return {
        categoryId: row.category_id,
        categoryLabel: row.category_name,
        sideLabel: productCategorySideLabel(row.side),
        lossLabel: formatProductCategoryDiagnosticMoneyLabel(
          row.business_net_income,
        ),
        scaleLabel:
          scaleDisplay === EM_DASH
            ? "\u89c4\u6a21\u7f3a\u5931"
            : `${scaleDisplay} \u4ebf\u5143`,
        scaleMissing: scaleDisplay === EM_DASH,
        yieldLabel: yieldDisplay.label,
        yieldMissing: yieldDisplay.missing,
        driverHint: buildProductCategoryDriverHint(row),
      };
    });

  return {
    metricStatus: PRODUCT_CATEGORY_CANDIDATE_METRIC_STATUS,
    headlineTotalLabel: input.grandTotal
      ? `${formatProductCategoryValue(input.grandTotal.business_net_income)} \u4ebf\u5143`
      : null,
    matrixRows,
    matrixEmptyCopy:
      matrixRows.length === 0
        ? "\u5f53\u524d payload \u672a\u8fd4\u56de\u53ef\u8bca\u65ad\u7684\u4ea7\u54c1\u884c\u3002"
        : null,
    negativeWatchlistRows,
    negativeWatchlistEmptyCopy:
      matrixRows.length === 0
        ? "\u5f53\u524d payload \u672a\u8fd4\u56de\u53ef\u8bca\u65ad\u7684\u4ea7\u54c1\u884c\u3002"
        : negativeWatchlistRows.length === 0
          ? "\u5f53\u524d\u6240\u9009\u53e3\u5f84\u4e0b\u6682\u65e0 business_net_income \u4e3a\u8d1f\u7684\u4ea7\u54c1\u884c\u3002"
          : null,
    spreadAttribution: buildProductCategorySpreadMovementAttribution({
      trendSnapshots: input.trendSnapshots,
      assetTotal: input.assetTotal,
      liabilityTotal: input.liabilityTotal,
      interestSpread: input.interestSpread ?? null,
    }),
  };
}
