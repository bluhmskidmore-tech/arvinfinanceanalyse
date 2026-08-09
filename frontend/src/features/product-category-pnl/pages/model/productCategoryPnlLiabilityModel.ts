import type {
  DecimalLike,
  ProductCategoryPnlRow,
} from "../../../../api/contracts";
import {
  chronologicalProductCategorySnapshotsInternal,
  type ProductCategoryReportDateParts,
  type ProductCategoryTrendSnapshotLike,
} from "./productCategoryPnlModelInternals";

type FormatDisplayValue = (
  row: ProductCategoryPnlRow,
  value: DecimalLike | null | undefined,
) => string;

type ProductCategoryLiabilityAmountField =
  "cnx_scale" | "cny_scale" | "foreign_scale";

type ProductCategoryLiabilityCopy = {
  missingAverageDailySuffix: string;
  missingRateSuffix: string;
  comparisonArrow: string;
  comparisonAmountPrefix: string;
  comparisonRatePrefix: string;
  comparisonJoiner: string;
  comparisonMissingCurrent: string;
  comparisonMissingPrior: string;
  liabilityTotalFallbackLabel: string;
  movementGroupAdjacent: string;
  movementGroupFallback: string;
  cnyCurrencyLabel: string;
  foreignCurrencyLabel: string;
  emptySurfaceCopy: string;
  emptyChartCopy: string;
};

export function buildProductCategoryLiabilitySideTrendSurfaceImpl(input: {
  snapshots: ProductCategoryTrendSnapshotLike[];
  metricStatus: unknown;
  displayOrderIndex: Map<string, number>;
  formatReportMonthLabel: (reportDate: string) => string;
  parseReportDate: (
    reportDate: string,
  ) => ProductCategoryReportDateParts | null;
  formatRowDisplayValue: FormatDisplayValue;
  formatForeignDisplayValue: FormatDisplayValue;
  percentNumber: (value: DecimalLike | null | undefined) => number | null;
  signedYiDeltaLabel: (value: number | null) => string;
  signedBpLabel: (value: number | null) => string;
  copy: ProductCategoryLiabilityCopy;
}) {
  const chart = selectProductCategoryLiabilitySideTrendChartImpl(input);
  const detailRows = selectProductCategoryLiabilityDetailTrendRowsImpl(input);
  const detailMatrix = selectProductCategoryLiabilityDetailMatrixImpl(input);
  const incompleteReasons = chart?.incompleteReasons ?? [];
  if (!chart && detailRows.length === 0 && detailMatrix.rows.length === 0) {
    return {
      metricStatus: input.metricStatus,
      chart: null,
      detailRows,
      detailMatrix,
      emptyCopy: input.copy.emptySurfaceCopy,
      incompleteReasons,
    };
  }
  return {
    metricStatus: input.metricStatus,
    chart,
    detailRows,
    detailMatrix,
    emptyCopy: chart ? null : input.copy.emptyChartCopy,
    incompleteReasons,
  };
}

export function selectProductCategoryLiabilitySideTrendChartImpl(input: {
  snapshots: ProductCategoryTrendSnapshotLike[];
  formatReportMonthLabel: (reportDate: string) => string;
  formatRowDisplayValue: FormatDisplayValue;
  formatForeignDisplayValue: FormatDisplayValue;
  percentNumber: (value: DecimalLike | null | undefined) => number | null;
  copy: ProductCategoryLiabilityCopy;
}) {
  const ordered = chronologicalProductCategorySnapshotsInternal(
    input.snapshots,
  );
  if (ordered.length === 0) {
    return null;
  }
  const labels: string[] = [];
  const totalAverageDaily: Array<number | null> = [];
  const totalRate: Array<number | null> = [];
  const incompleteReasons: string[] = [];

  ordered.forEach((snapshot) => {
    const label =
      snapshot.label ?? input.formatReportMonthLabel(snapshot.reportDate);
    const averageDaily = liabilityAmountDisplayNumber({
      row: snapshot.liabilityTotal ?? undefined,
      amountField: "cnx_scale",
      formatRowDisplayValue: input.formatRowDisplayValue,
      formatForeignDisplayValue: input.formatForeignDisplayValue,
    });
    const rate = input.percentNumber(snapshot.liabilityTotal?.weighted_yield);
    labels.push(label);
    totalAverageDaily.push(averageDaily);
    totalRate.push(rate);
    if (averageDaily === null) {
      incompleteReasons.push(`${label}${input.copy.missingAverageDailySuffix}`);
    }
    if (rate === null) {
      incompleteReasons.push(`${label}${input.copy.missingRateSuffix}`);
    }
  });

  return { labels, totalAverageDaily, totalRate, incompleteReasons };
}

export function selectProductCategoryLiabilityDetailMatrixImpl(input: {
  snapshots: ProductCategoryTrendSnapshotLike[];
  displayOrderIndex: Map<string, number>;
  formatReportMonthLabel: (reportDate: string) => string;
  parseReportDate: (
    reportDate: string,
  ) => ProductCategoryReportDateParts | null;
  formatRowDisplayValue: FormatDisplayValue;
  formatForeignDisplayValue: FormatDisplayValue;
  percentNumber: (value: DecimalLike | null | undefined) => number | null;
  signedYiDeltaLabel: (value: number | null) => string;
  signedBpLabel: (value: number | null) => string;
  copy: ProductCategoryLiabilityCopy;
}) {
  const ordered = chronologicalProductCategorySnapshotsInternal(
    input.snapshots,
  );
  const periods = ordered.map((snapshot) => ({
    key: `${snapshot.reportDate}:${snapshot.view ?? ""}`,
    label: snapshot.label ?? input.formatReportMonthLabel(snapshot.reportDate),
    reportDate: snapshot.reportDate,
  }));
  const rowsBySnapshot = ordered.map((snapshot) =>
    liabilityDetailRowsFromSnapshot(snapshot, input.displayOrderIndex),
  );
  const rowMaps = rowsBySnapshot.map(
    (rows) => new Map(rows.map((row) => [row.category_id, row])),
  );
  const rowRefs = new Map<
    string,
    { first: ProductCategoryPnlRow; latest: ProductCategoryPnlRow }
  >();

  rowsBySnapshot.forEach((rows) => {
    rows.forEach((row) => {
      const existing = rowRefs.get(row.category_id);
      rowRefs.set(row.category_id, {
        first: existing?.first ?? row,
        latest: row,
      });
    });
  });

  const categoryIds = Array.from(rowRefs.keys()).sort((left, right) => {
    const leftIndex =
      input.displayOrderIndex.get(left) ?? Number.MAX_SAFE_INTEGER;
    const rightIndex =
      input.displayOrderIndex.get(right) ?? Number.MAX_SAFE_INTEGER;
    if (leftIndex !== rightIndex) {
      return leftIndex - rightIndex;
    }
    return left.localeCompare(right);
  });
  const latestIndex = ordered.length - 1;
  const previousIndex = ordered.length - 2;
  const latestTotal = ordered[latestIndex]?.liabilityTotal ?? undefined;
  const firstTotal =
    ordered.find((snapshot) => snapshot.liabilityTotal)?.liabilityTotal ??
    undefined;
  const totalRow =
    latestTotal || firstTotal
      ? buildLiabilityDetailMatrixRow({
          categoryId: "liability_total",
          categoryLabel:
            latestTotal?.category_name ||
            firstTotal?.category_name ||
            input.copy.liabilityTotalFallbackLabel,
          isSummary: true,
          periods,
          latestIndex,
          previousIndex,
          rowAt: (index) => ordered[index]?.liabilityTotal ?? undefined,
          formatRowDisplayValue: input.formatRowDisplayValue,
          formatForeignDisplayValue: input.formatForeignDisplayValue,
          percentNumber: input.percentNumber,
          signedYiDeltaLabel: input.signedYiDeltaLabel,
          signedBpLabel: input.signedBpLabel,
        })
      : null;
  const detailRows = categoryIds.map((categoryId) => {
    const refs = rowRefs.get(categoryId);
    const latestRow = refs?.latest;
    const firstRow = refs?.first;
    return buildLiabilityDetailMatrixRow({
      categoryId,
      categoryLabel:
        latestRow?.category_name || firstRow?.category_name || categoryId,
      periods,
      latestIndex,
      previousIndex,
      rowAt: (index) => rowMaps[index]?.get(categoryId),
      formatRowDisplayValue: input.formatRowDisplayValue,
      formatForeignDisplayValue: input.formatForeignDisplayValue,
      percentNumber: input.percentNumber,
      signedYiDeltaLabel: input.signedYiDeltaLabel,
      signedBpLabel: input.signedBpLabel,
    });
  });
  const movementGroupLabel = adjacentProductCategoryMonths(
    ordered[previousIndex],
    ordered[latestIndex],
    input.parseReportDate,
  )
    ? input.copy.movementGroupAdjacent
    : input.copy.movementGroupFallback;
  const currencyDefs: Array<{
    currencyKey: "cny" | "foreign";
    currencyLabel: string;
    amountField: ProductCategoryLiabilityAmountField;
  }> = [
    {
      currencyKey: "cny",
      currencyLabel: input.copy.cnyCurrencyLabel,
      amountField: "cny_scale",
    },
    {
      currencyKey: "foreign",
      currencyLabel: input.copy.foreignCurrencyLabel,
      amountField: "foreign_scale",
    },
  ];
  const currencyMatrices: Array<{
    currencyKey: "cny" | "foreign";
    currencyLabel: string;
    movementGroupLabel: string;
    rows: Array<{
      categoryId: string;
      categoryLabel: string;
      isSummary?: boolean;
      cells: Array<{
        periodKey: string;
        amountLabel: string;
        rateLabel: string;
      }>;
      movement: {
        amountLabel: string;
        rateLabel: string;
      };
    }>;
  }> = currencyDefs.map((currency) => {
    const totalCurrencyRow =
      latestTotal || firstTotal
        ? buildLiabilityCurrencyMatrixRow({
            categoryId: "liability_total",
            categoryLabel:
              latestTotal?.category_name ||
              firstTotal?.category_name ||
              input.copy.liabilityTotalFallbackLabel,
            isSummary: true,
            amountField: currency.amountField,
            periods,
            latestIndex,
            previousIndex,
            rowAt: (index) => ordered[index]?.liabilityTotal ?? undefined,
            formatRowDisplayValue: input.formatRowDisplayValue,
            formatForeignDisplayValue: input.formatForeignDisplayValue,
            percentNumber: input.percentNumber,
            signedYiDeltaLabel: input.signedYiDeltaLabel,
            signedBpLabel: input.signedBpLabel,
          })
        : null;
    const currencyRows = categoryIds.map((categoryId) => {
      const refs = rowRefs.get(categoryId);
      const latestRow = refs?.latest;
      const firstRow = refs?.first;
      return buildLiabilityCurrencyMatrixRow({
        categoryId,
        categoryLabel:
          latestRow?.category_name || firstRow?.category_name || categoryId,
        amountField: currency.amountField,
        periods,
        latestIndex,
        previousIndex,
        rowAt: (index) => rowMaps[index]?.get(categoryId),
        formatRowDisplayValue: input.formatRowDisplayValue,
        formatForeignDisplayValue: input.formatForeignDisplayValue,
        percentNumber: input.percentNumber,
        signedYiDeltaLabel: input.signedYiDeltaLabel,
        signedBpLabel: input.signedBpLabel,
      });
    });
    return {
      currencyKey: currency.currencyKey,
      currencyLabel: currency.currencyLabel,
      movementGroupLabel,
      rows: totalCurrencyRow
        ? [totalCurrencyRow, ...currencyRows]
        : currencyRows,
    };
  });

  return {
    periods,
    movementGroupLabel,
    rows: totalRow ? [totalRow, ...detailRows] : detailRows,
    currencyMatrices,
  };
}

export function selectProductCategoryLiabilityDetailTrendRowsImpl(input: {
  snapshots: ProductCategoryTrendSnapshotLike[];
  displayOrderIndex: Map<string, number>;
  formatReportMonthLabel: (reportDate: string) => string;
  formatRowDisplayValue: FormatDisplayValue;
  formatForeignDisplayValue: FormatDisplayValue;
  percentNumber: (value: DecimalLike | null | undefined) => number | null;
  signedYiDeltaLabel: (value: number | null) => string;
  signedBpLabel: (value: number | null) => string;
  copy: ProductCategoryLiabilityCopy;
}) {
  const ordered = chronologicalProductCategorySnapshotsInternal(
    input.snapshots,
  );
  const latestSnapshot = ordered[ordered.length - 1];
  if (!latestSnapshot) {
    return [];
  }
  const latestLabel =
    latestSnapshot.label ??
    input.formatReportMonthLabel(latestSnapshot.reportDate);
  const latestIndex = ordered.length - 1;
  return liabilityDetailRowsFromSnapshot(
    latestSnapshot,
    input.displayOrderIndex,
  ).map((row) => {
    const latestAmount = liabilityAmountDisplayNumber({
      row,
      amountField: "cnx_scale",
      formatRowDisplayValue: input.formatRowDisplayValue,
      formatForeignDisplayValue: input.formatForeignDisplayValue,
    });
    const priorAmount =
      latestAmount !== null
        ? latestComparableLiabilityValue({
            snapshots: ordered,
            categoryId: row.category_id,
            metric: "cnx_scale",
            beforeIndex: latestIndex,
            displayOrderIndex: input.displayOrderIndex,
            formatReportMonthLabel: input.formatReportMonthLabel,
            formatRowDisplayValue: input.formatRowDisplayValue,
            formatForeignDisplayValue: input.formatForeignDisplayValue,
            percentNumber: input.percentNumber,
          })
        : null;
    const latestRate = input.percentNumber(row.weighted_yield);
    const priorRate =
      latestRate !== null
        ? latestComparableLiabilityValue({
            snapshots: ordered,
            categoryId: row.category_id,
            metric: "weighted_yield",
            beforeIndex: latestIndex,
            displayOrderIndex: input.displayOrderIndex,
            formatReportMonthLabel: input.formatReportMonthLabel,
            formatRowDisplayValue: input.formatRowDisplayValue,
            formatForeignDisplayValue: input.formatForeignDisplayValue,
            percentNumber: input.percentNumber,
          })
        : null;
    const amountDelta =
      latestAmount !== null && priorAmount
        ? Number((latestAmount - priorAmount.value).toFixed(2))
        : null;
    const rateDelta =
      latestRate !== null && priorRate
        ? Number(((latestRate - priorRate.value) * 100).toFixed(1))
        : null;
    return {
      categoryId: row.category_id,
      categoryLabel: row.category_name || row.category_id,
      latestAmountLabel: latestAmount !== null ? latestAmount.toFixed(2) : "-",
      amountDeltaLabel: input.signedYiDeltaLabel(amountDelta),
      latestRateLabel: latestRate !== null ? latestRate.toFixed(2) : "-",
      rateDeltaLabel: input.signedBpLabel(rateDelta),
      comparisonLabel: liabilityComparisonLabel({
        amountLatestLabel: latestAmount !== null ? latestLabel : null,
        amountPriorLabel: priorAmount?.label ?? null,
        rateLatestLabel: latestRate !== null ? latestLabel : null,
        ratePriorLabel: priorRate?.label ?? null,
        copy: input.copy,
      }),
    };
  });
}

function latestComparableLiabilityValue(input: {
  snapshots: ProductCategoryTrendSnapshotLike[];
  categoryId: string;
  metric: "cnx_scale" | "weighted_yield";
  beforeIndex?: number;
  displayOrderIndex: Map<string, number>;
  formatReportMonthLabel: (reportDate: string) => string;
  formatRowDisplayValue: FormatDisplayValue;
  formatForeignDisplayValue: FormatDisplayValue;
  percentNumber: (value: DecimalLike | null | undefined) => number | null;
}): { value: number; label: string; index: number } | null {
  const upperBound = input.beforeIndex ?? input.snapshots.length;
  for (let index = upperBound - 1; index >= 0; index -= 1) {
    const snapshot = input.snapshots[index];
    if (!snapshot) {
      continue;
    }
    const row = liabilityDetailRowsFromSnapshot(
      snapshot,
      input.displayOrderIndex,
    ).find((item) => item.category_id === input.categoryId);
    const value =
      input.metric === "cnx_scale"
        ? liabilityAmountDisplayNumber({
            row,
            amountField: "cnx_scale",
            formatRowDisplayValue: input.formatRowDisplayValue,
            formatForeignDisplayValue: input.formatForeignDisplayValue,
          })
        : input.percentNumber(row?.weighted_yield);
    if (value !== null) {
      return {
        value,
        label:
          snapshot.label ?? input.formatReportMonthLabel(snapshot.reportDate),
        index,
      };
    }
  }
  return null;
}

function liabilityComparisonLabel(input: {
  amountLatestLabel: string | null;
  amountPriorLabel: string | null;
  rateLatestLabel: string | null;
  ratePriorLabel: string | null;
  copy: ProductCategoryLiabilityCopy;
}): string {
  const amountLabel =
    input.amountLatestLabel && input.amountPriorLabel
      ? `${input.amountPriorLabel}${input.copy.comparisonArrow}${input.amountLatestLabel}`
      : null;
  const rateLabel =
    input.rateLatestLabel && input.ratePriorLabel
      ? `${input.ratePriorLabel}${input.copy.comparisonArrow}${input.rateLatestLabel}`
      : null;
  if (amountLabel && rateLabel && amountLabel !== rateLabel) {
    return `${input.copy.comparisonAmountPrefix}${amountLabel}${input.copy.comparisonJoiner}${input.copy.comparisonRatePrefix}${rateLabel}`;
  }
  if (!input.amountLatestLabel && !input.rateLatestLabel) {
    return input.copy.comparisonMissingCurrent;
  }
  return amountLabel ?? rateLabel ?? input.copy.comparisonMissingPrior;
}

function adjacentProductCategoryMonths(
  previous: ProductCategoryTrendSnapshotLike | undefined,
  latest: ProductCategoryTrendSnapshotLike | undefined,
  parseReportDate: (
    reportDate: string,
  ) => ProductCategoryReportDateParts | null,
): boolean {
  const previousDate = previous ? parseReportDate(previous.reportDate) : null;
  const latestDate = latest ? parseReportDate(latest.reportDate) : null;
  if (!previousDate || !latestDate) {
    return false;
  }
  return (
    latestDate.year * 12 +
      latestDate.month -
      (previousDate.year * 12 + previousDate.month) ===
    1
  );
}

function liabilityDetailRowsFromSnapshot(
  snapshot: ProductCategoryTrendSnapshotLike,
  displayOrderIndex: Map<string, number>,
): ProductCategoryPnlRow[] {
  return snapshot.rows
    .filter(
      (row) =>
        row.side === "liability" &&
        !row.is_total &&
        row.category_id !== "liability_total",
    )
    .sort((left, right) => {
      const leftIndex =
        displayOrderIndex.get(left.category_id) ?? Number.MAX_SAFE_INTEGER;
      const rightIndex =
        displayOrderIndex.get(right.category_id) ?? Number.MAX_SAFE_INTEGER;
      return leftIndex - rightIndex;
    });
}

function liabilityAmountDisplayNumber(input: {
  row: ProductCategoryPnlRow | undefined;
  amountField: ProductCategoryLiabilityAmountField;
  formatRowDisplayValue: FormatDisplayValue;
  formatForeignDisplayValue: FormatDisplayValue;
}): number | null {
  if (!input.row) {
    return null;
  }
  const label =
    input.amountField === "foreign_scale"
      ? input.formatForeignDisplayValue(input.row, input.row[input.amountField])
      : input.formatRowDisplayValue(input.row, input.row[input.amountField]);
  const parsed = Number(label);
  return Number.isFinite(parsed) ? parsed : null;
}

function liabilityDetailMetricLabels(input: {
  row: ProductCategoryPnlRow | undefined;
  amountField?: ProductCategoryLiabilityAmountField;
  formatRowDisplayValue: FormatDisplayValue;
  formatForeignDisplayValue: FormatDisplayValue;
  percentNumber: (value: DecimalLike | null | undefined) => number | null;
}) {
  const amountValue = liabilityAmountDisplayNumber({
    row: input.row,
    amountField: input.amountField ?? "cnx_scale",
    formatRowDisplayValue: input.formatRowDisplayValue,
    formatForeignDisplayValue: input.formatForeignDisplayValue,
  });
  const rateValue = input.percentNumber(input.row?.weighted_yield);
  return {
    amountLabel: amountValue !== null ? amountValue.toFixed(2) : "-",
    amountValue,
    rateLabel: rateValue !== null ? rateValue.toFixed(2) : "-",
    rateValue,
  };
}

function buildLiabilityDetailMatrixRow(input: {
  categoryId: string;
  categoryLabel: string;
  isSummary?: boolean;
  periods: Array<{ key: string }>;
  latestIndex: number;
  previousIndex: number;
  rowAt: (index: number) => ProductCategoryPnlRow | undefined;
  formatRowDisplayValue: FormatDisplayValue;
  formatForeignDisplayValue: FormatDisplayValue;
  percentNumber: (value: DecimalLike | null | undefined) => number | null;
  signedYiDeltaLabel: (value: number | null) => string;
  signedBpLabel: (value: number | null) => string;
}) {
  const latestMetrics = liabilityDetailMetricLabels({
    row: input.rowAt(input.latestIndex),
    formatRowDisplayValue: input.formatRowDisplayValue,
    formatForeignDisplayValue: input.formatForeignDisplayValue,
    percentNumber: input.percentNumber,
  });
  const previousMetrics = liabilityDetailMetricLabels({
    row: input.rowAt(input.previousIndex),
    formatRowDisplayValue: input.formatRowDisplayValue,
    formatForeignDisplayValue: input.formatForeignDisplayValue,
    percentNumber: input.percentNumber,
  });
  const amountDelta =
    latestMetrics.amountValue !== null && previousMetrics.amountValue !== null
      ? Number(
          (latestMetrics.amountValue - previousMetrics.amountValue).toFixed(2),
        )
      : null;
  const rateDelta =
    latestMetrics.rateValue !== null && previousMetrics.rateValue !== null
      ? Number(
          ((latestMetrics.rateValue - previousMetrics.rateValue) * 100).toFixed(
            1,
          ),
        )
      : null;

  return {
    categoryId: input.categoryId,
    categoryLabel: input.categoryLabel,
    isSummary: input.isSummary,
    cells: input.periods.map((period, index) => {
      const labels = liabilityDetailMetricLabels({
        row: input.rowAt(index),
        formatRowDisplayValue: input.formatRowDisplayValue,
        formatForeignDisplayValue: input.formatForeignDisplayValue,
        percentNumber: input.percentNumber,
      });
      return {
        periodKey: period.key,
        amountLabel: labels.amountLabel,
        rateLabel: labels.rateLabel,
      };
    }),
    movement: {
      amountLabel: input.signedYiDeltaLabel(amountDelta),
      rateLabel: input.signedBpLabel(rateDelta),
    },
  };
}

function buildLiabilityCurrencyMatrixRow(input: {
  categoryId: string;
  categoryLabel: string;
  isSummary?: boolean;
  amountField: ProductCategoryLiabilityAmountField;
  periods: Array<{ key: string }>;
  latestIndex: number;
  previousIndex: number;
  rowAt: (index: number) => ProductCategoryPnlRow | undefined;
  formatRowDisplayValue: FormatDisplayValue;
  formatForeignDisplayValue: FormatDisplayValue;
  percentNumber: (value: DecimalLike | null | undefined) => number | null;
  signedYiDeltaLabel: (value: number | null) => string;
  signedBpLabel: (value: number | null) => string;
}) {
  const latestMetrics = liabilityDetailMetricLabels({
    row: input.rowAt(input.latestIndex),
    amountField: input.amountField,
    formatRowDisplayValue: input.formatRowDisplayValue,
    formatForeignDisplayValue: input.formatForeignDisplayValue,
    percentNumber: input.percentNumber,
  });
  const previousMetrics = liabilityDetailMetricLabels({
    row: input.rowAt(input.previousIndex),
    amountField: input.amountField,
    formatRowDisplayValue: input.formatRowDisplayValue,
    formatForeignDisplayValue: input.formatForeignDisplayValue,
    percentNumber: input.percentNumber,
  });
  const amountDelta =
    latestMetrics.amountValue !== null && previousMetrics.amountValue !== null
      ? Number(
          (latestMetrics.amountValue - previousMetrics.amountValue).toFixed(2),
        )
      : null;
  const rateDelta =
    latestMetrics.rateValue !== null && previousMetrics.rateValue !== null
      ? Number(
          ((latestMetrics.rateValue - previousMetrics.rateValue) * 100).toFixed(
            1,
          ),
        )
      : null;

  return {
    categoryId: input.categoryId,
    categoryLabel: input.categoryLabel,
    isSummary: input.isSummary,
    cells: input.periods.map((period, index) => {
      const labels = liabilityDetailMetricLabels({
        row: input.rowAt(index),
        amountField: input.amountField,
        formatRowDisplayValue: input.formatRowDisplayValue,
        formatForeignDisplayValue: input.formatForeignDisplayValue,
        percentNumber: input.percentNumber,
      });
      return {
        periodKey: period.key,
        amountLabel: labels.amountLabel,
        rateLabel: labels.rateLabel,
      };
    }),
    movement: {
      amountLabel: input.signedYiDeltaLabel(amountDelta),
      rateLabel: input.signedBpLabel(rateDelta),
    },
  };
}
