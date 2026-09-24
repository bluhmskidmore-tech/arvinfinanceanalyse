import type {
  DecimalLike,
  ProductCategoryPnlRow,
} from "../../../../api/contracts";
import { EM_DASH } from "../../../../utils/format";
import {
  formatProductCategoryReportMonthLabelInternal,
  interestSpreadMetricNumberInternal,
  parseProductCategoryReportDateInternal,
  productCategoryInterestSpreadForBasisInternal,
  type ProductCategoryInterestSpreadBasisLike,
  type ProductCategoryTrendSnapshotLike,
} from "./productCategoryPnlModelInternals";

type ProductCategoryInterestSpreadAttributionOptionLike = {
  basis: ProductCategoryInterestSpreadBasisLike;
  month: number;
};

type FormatRowDisplayValue = (
  row: ProductCategoryPnlRow,
  value: DecimalLike | null | undefined,
) => string;

type FormatYieldValue = (value: DecimalLike | null | undefined) => string;

type ProductCategoryInterestSpreadAttributionDetailPointLike = {
  reportLabel: string;
  amountLabel: string;
  cashLabel: string;
  yieldLabel: string;
};

export function buildProductCategoryInterestSpreadAttributionImpl(input: {
  snapshots: ProductCategoryTrendSnapshotLike[];
  options: ProductCategoryInterestSpreadAttributionOptionLike;
  currentYear: number;
  formatRowDisplayValue: FormatRowDisplayValue;
  formatYieldValue: FormatYieldValue;
}) {
  const current = findInterestSpreadAttributionSnapshot(
    input.snapshots,
    input.currentYear,
    input.options.month,
  );
  const prior = findInterestSpreadAttributionSnapshot(
    input.snapshots,
    input.currentYear - 1,
    input.options.month,
  );
  const currentMetrics = interestSpreadAttributionMetrics(
    current,
    input.options.basis,
  );
  const priorMetrics = interestSpreadAttributionMetrics(
    prior,
    input.options.basis,
  );
  const assetContributionBp = basisPointDelta(
    currentMetrics.assetYield,
    priorMetrics.assetYield,
  );
  const liabilityContributionBp = basisPointDelta(
    priorMetrics.liabilityYield,
    currentMetrics.liabilityYield,
  );
  const spreadDeltaBp = basisPointDelta(
    currentMetrics.spread,
    priorMetrics.spread,
  );
  const incompleteReasons = interestSpreadAttributionIncompleteReasons({
    current,
    prior,
    currentMetrics,
    priorMetrics,
    basis: input.options.basis,
  });

  return {
    selected: {
      basis: input.options.basis,
      month: input.options.month,
      currentYear: input.currentYear,
      priorYear: input.currentYear - 1,
      currentReportDate: current?.reportDate ?? null,
      priorReportDate: prior?.reportDate ?? null,
    },
    complete: incompleteReasons.length === 0,
    incompleteReasons,
    summary: {
      assetYieldCurrent: currentMetrics.assetYield,
      assetYieldPrior: priorMetrics.assetYield,
      liabilityYieldCurrent: currentMetrics.liabilityYield,
      liabilityYieldPrior: priorMetrics.liabilityYield,
      spreadCurrent: currentMetrics.spread,
      spreadPrior: priorMetrics.spread,
      assetContributionBp,
      liabilityContributionBp,
      spreadDeltaBp,
    },
    rows: {
      assetYield: {
        priorValue: priorMetrics.assetYield,
        currentValue: currentMetrics.assetYield,
        deltaBp: assetContributionBp,
        priorLabel: interestSpreadPercentLabel(priorMetrics.assetYield),
        currentLabel: interestSpreadPercentLabel(currentMetrics.assetYield),
        contributionLabel: signedBpLabelWithOneDecimal(assetContributionBp),
      },
      liabilityCost: {
        priorValue: priorMetrics.liabilityYield,
        currentValue: currentMetrics.liabilityYield,
        deltaBp: liabilityContributionBp,
        priorLabel: interestSpreadPercentLabel(priorMetrics.liabilityYield),
        currentLabel: interestSpreadPercentLabel(currentMetrics.liabilityYield),
        contributionLabel: signedBpLabelWithOneDecimal(liabilityContributionBp),
      },
      spread: {
        priorValue: priorMetrics.spread,
        currentValue: currentMetrics.spread,
        deltaBp: spreadDeltaBp,
        priorLabel: interestSpreadPercentLabel(priorMetrics.spread),
        currentLabel: interestSpreadPercentLabel(currentMetrics.spread),
        contributionLabel: signedBpLabelWithOneDecimal(spreadDeltaBp),
      },
    },
    details: {
      assetTotal: {
        prior: interestSpreadAttributionDetailPoint(
          prior,
          priorMetrics.assetRow,
          priorMetrics.assetYield,
          input.options.basis,
          input.formatRowDisplayValue,
          input.formatYieldValue,
        ),
        current: interestSpreadAttributionDetailPoint(
          current,
          currentMetrics.assetRow,
          currentMetrics.assetYield,
          input.options.basis,
          input.formatRowDisplayValue,
          input.formatYieldValue,
        ),
      },
      liabilityTotal: {
        prior: interestSpreadAttributionDetailPoint(
          prior,
          priorMetrics.liabilityRow,
          priorMetrics.liabilityYield,
          input.options.basis,
          input.formatRowDisplayValue,
          input.formatYieldValue,
        ),
        current: interestSpreadAttributionDetailPoint(
          current,
          currentMetrics.liabilityRow,
          currentMetrics.liabilityYield,
          input.options.basis,
          input.formatRowDisplayValue,
          input.formatYieldValue,
        ),
      },
    },
  };
}

function findInterestSpreadAttributionSnapshot(
  snapshots: ProductCategoryTrendSnapshotLike[],
  year: number,
  month: number,
): ProductCategoryTrendSnapshotLike | null {
  return (
    snapshots.find((snapshot) => {
      const parsed = parseProductCategoryReportDateInternal(
        snapshot.reportDate,
      );
      return parsed?.year === year && parsed.month === month;
    }) ?? null
  );
}

function interestSpreadAttributionMetrics(
  snapshot: ProductCategoryTrendSnapshotLike | null,
  basis: ProductCategoryInterestSpreadBasisLike,
): {
  assetYield: number | null;
  liabilityYield: number | null;
  spread: number | null;
  assetRow: ProductCategoryPnlRow | null;
  liabilityRow: ProductCategoryPnlRow | null;
} {
  if (!snapshot) {
    return {
      assetYield: null,
      liabilityYield: null,
      spread: null,
      assetRow: null,
      liabilityRow: null,
    };
  }
  const assetRow = snapshot.assetTotal ?? null;
  const liabilityRow = snapshot.liabilityTotal ?? null;
  if (!assetRow || !liabilityRow) {
    return {
      assetYield: null,
      liabilityYield: null,
      spread: null,
      assetRow,
      liabilityRow,
    };
  }
  const assetYield = interestSpreadMetricNumberInternal(
    basis === "cny"
      ? snapshot.interestSpread?.cny_asset_yield_pct
      : snapshot.interestSpread?.all_currency_asset_yield_pct,
  );
  const liabilityYield = interestSpreadMetricNumberInternal(
    basis === "cny"
      ? snapshot.interestSpread?.cny_liability_yield_pct
      : snapshot.interestSpread?.all_currency_liability_yield_pct,
  );
  return {
    assetYield,
    liabilityYield,
    spread: productCategoryInterestSpreadForBasisInternal(snapshot, basis),
    assetRow,
    liabilityRow,
  };
}

function basisPointDelta(
  current: number | null,
  prior: number | null,
): number | null {
  if (current === null || prior === null) {
    return null;
  }
  return Number(((current - prior) * 100).toFixed(1));
}

function interestSpreadPercentLabel(value: number | null): string {
  return value === null ? EM_DASH : `${value.toFixed(2)}%`;
}

function signedBpLabelWithOneDecimal(value: number | null): string {
  if (value === null || !Number.isFinite(value)) {
    return EM_DASH;
  }
  const sign = value > 0 ? "+" : value < 0 ? "-" : "";
  return `${sign}${Math.abs(value).toFixed(1)} bp`;
}

function interestSpreadAttributionIncompleteReasons(input: {
  current: ProductCategoryTrendSnapshotLike | null;
  prior: ProductCategoryTrendSnapshotLike | null;
  currentMetrics: {
    assetYield: number | null;
    liabilityYield: number | null;
    spread: number | null;
  };
  priorMetrics: {
    assetYield: number | null;
    liabilityYield: number | null;
    spread: number | null;
  };
  basis: ProductCategoryInterestSpreadBasisLike;
}): string[] {
  const prefix =
    input.basis === "cny" ? "\u4eba\u6c11\u5e01" : "\u5168\u53e3\u5f84";
  const reasons: string[] = [];
  if (!input.current) {
    reasons.push("\u7f3a\u5c11\u5f53\u524d\u6708\u6570\u636e");
  }
  if (!input.prior) {
    reasons.push("\u7f3a\u5c11\u4e0a\u5e74\u540c\u6708\u6570\u636e");
  }
  if (input.currentMetrics.assetYield === null) {
    reasons.push(`${prefix}当前月资产端收益率（含TPL）不可用`);
  }
  if (input.priorMetrics.assetYield === null) {
    reasons.push(`${prefix}上年同月资产端收益率（含TPL）不可用`);
  }
  if (input.currentMetrics.liabilityYield === null) {
    reasons.push(`${prefix}当前月负债端成本率不可用`);
  }
  if (input.priorMetrics.liabilityYield === null) {
    reasons.push(`${prefix}上年同月负债端成本率不可用`);
  }
  if (
    input.current &&
    input.prior &&
    input.currentMetrics.assetYield !== null &&
    input.priorMetrics.assetYield !== null &&
    input.currentMetrics.liabilityYield !== null &&
    input.priorMetrics.liabilityYield !== null &&
    (input.currentMetrics.spread === null || input.priorMetrics.spread === null)
  ) {
    reasons.push(`${prefix}资产负债利差（含TPL）未由后端返回`);
  }
  return reasons;
}

function interestSpreadAttributionDetailPoint(
  snapshot: ProductCategoryTrendSnapshotLike | null,
  row: ProductCategoryPnlRow | null,
  yieldValue: number | null,
  basis: ProductCategoryInterestSpreadBasisLike,
  formatRowDisplayValue: FormatRowDisplayValue,
  formatYieldValue: FormatYieldValue,
): ProductCategoryInterestSpreadAttributionDetailPointLike {
  const amountField = basis === "cny" ? "cny_scale" : "cnx_scale";
  const cashField = basis === "cny" ? "cny_cash" : "cnx_cash";
  return {
    reportLabel:
      snapshot?.label ??
      (snapshot
        ? formatProductCategoryReportMonthLabelInternal(snapshot.reportDate)
        : EM_DASH),
    amountLabel: row
      ? `${formatRowDisplayValue(row, row[amountField])}\u4ebf\u5143`
      : EM_DASH,
    cashLabel: row
      ? `${formatRowDisplayValue(row, row[cashField])}\u4ebf\u5143`
      : EM_DASH,
    yieldLabel:
      yieldValue === null ? EM_DASH : `${formatYieldValue(yieldValue)}%`,
  };
}
