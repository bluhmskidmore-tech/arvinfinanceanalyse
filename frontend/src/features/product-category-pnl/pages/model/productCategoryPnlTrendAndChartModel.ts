import type {
  ProductCategoryPnlPayload,
  ProductCategoryPnlRow,
  ResultMeta,
} from "../../../../api/contracts";
import {
  buildSnapshotChartInternal,
  chronologicalProductCategorySnapshotsInternal,
  findProductCategoryReportDateForMonthInternal,
  findProductCategoryRowInternal,
  formatProductCategoryReportMonthLabelInternal,
  formatProductCategoryShortMonthLabelInternal,
  parseProductCategoryReportDateInternal,
  percentNumberInternal,
  productCategoryInterestEarningSpreadForBasisInternal,
  productCategoryInterestSpreadForBasisInternal,
  pushUniqueProductCategoryTrendPointInternal,
  type ProductCategoryInterestSpreadBasisLike,
  type ProductCategoryTrendReportPointLike,
  type ProductCategoryTrendSnapshotLike,
  yiNumberInternal,
} from "./productCategoryPnlModelInternals";

type SelectDetailRows = (
  baselineRows: ProductCategoryPnlRow[] | null | undefined,
  scenarioRows: ProductCategoryPnlRow[] | null | undefined,
) => ProductCategoryPnlRow[];

export function selectProductCategoryTrendReportDatesImpl(
  selectedDate: string,
  reportDates: string[] | undefined,
  limit = 8,
): string[] {
  return selectProductCategoryTrendReportPointsImpl(
    selectedDate,
    reportDates,
    "monthly",
    limit,
  ).map((point) => point.reportDate);
}

export function selectProductCategoryTrendReportPointsImpl(
  selectedDate: string,
  reportDates: string[] | undefined,
  monthlyView = "monthly",
  limit = 8,
): ProductCategoryTrendReportPointLike[] {
  if (!selectedDate) {
    return [];
  }
  const dates = Array.from(
    new Set([selectedDate, ...(reportDates ?? [])].filter(Boolean)),
  );
  const selected = parseProductCategoryReportDateInternal(selectedDate);
  if (!selected) {
    return dates.slice(0, limit).map((reportDate) => ({
      reportDate,
      view: monthlyView,
      label: formatProductCategoryReportMonthLabelInternal(reportDate),
    }));
  }

  const chronologicalPoints: ProductCategoryTrendReportPointLike[] = [];
  const previousYear = selected.year - 1;
  ([1, 2, 3] as const).forEach((quarter) => {
    const reportDate = findProductCategoryReportDateForMonthInternal(
      dates,
      previousYear,
      quarter * 3,
      selectedDate,
    );
    if (!reportDate) {
      return;
    }
    pushUniqueProductCategoryTrendPointInternal(chronologicalPoints, {
      reportDate,
      view: monthlyView,
      label: `${previousYear}\u5e74Q${quarter}`,
    });
  });

  ([11, 12] as const).forEach((month) => {
    const reportDate = findProductCategoryReportDateForMonthInternal(
      dates,
      previousYear,
      month,
      selectedDate,
    );
    if (!reportDate) {
      return;
    }
    pushUniqueProductCategoryTrendPointInternal(chronologicalPoints, {
      reportDate,
      view: monthlyView,
      label: formatProductCategoryReportMonthLabelInternal(reportDate),
    });
  });

  for (let month = 1; month <= selected.month; month += 1) {
    const reportDate = findProductCategoryReportDateForMonthInternal(
      dates,
      selected.year,
      month,
      selectedDate,
    );
    if (!reportDate) {
      continue;
    }
    pushUniqueProductCategoryTrendPointInternal(chronologicalPoints, {
      reportDate,
      view: monthlyView,
      label: formatProductCategoryReportMonthLabelInternal(reportDate),
    });
  }

  if (chronologicalPoints.length === 0) {
    return dates.slice(0, limit).map((reportDate) => ({
      reportDate,
      view: monthlyView,
      label: formatProductCategoryReportMonthLabelInternal(reportDate),
    }));
  }
  return chronologicalPoints.slice(-limit).reverse();
}

export function selectProductCategoryTwoYearInterestSpreadReportPointsImpl(
  selectedDate: string,
  reportDates: string[] | undefined,
  monthlyView = "monthly",
): ProductCategoryTrendReportPointLike[] {
  if (!selectedDate) {
    return [];
  }
  const dates = Array.from(
    new Set([selectedDate, ...(reportDates ?? [])].filter(Boolean)),
  );
  const selected = parseProductCategoryReportDateInternal(selectedDate);
  if (!selected) {
    return dates.slice(0, 6).map((reportDate) => ({
      reportDate,
      view: monthlyView,
      label: formatProductCategoryReportMonthLabelInternal(reportDate),
    }));
  }

  const chronologicalPoints: ProductCategoryTrendReportPointLike[] = [];
  const previousYear = selected.year - 1;
  for (let month = 1; month <= 12; month += 1) {
    const reportDate = findProductCategoryReportDateForMonthInternal(
      dates,
      previousYear,
      month,
      selectedDate,
    );
    if (!reportDate) {
      continue;
    }
    pushUniqueProductCategoryTrendPointInternal(chronologicalPoints, {
      reportDate,
      view: monthlyView,
      label: formatProductCategoryReportMonthLabelInternal(reportDate),
    });
  }

  for (let month = 1; month <= selected.month; month += 1) {
    const reportDate = findProductCategoryReportDateForMonthInternal(
      dates,
      selected.year,
      month,
      selectedDate,
    );
    if (!reportDate) {
      continue;
    }
    pushUniqueProductCategoryTrendPointInternal(chronologicalPoints, {
      reportDate,
      view: monthlyView,
      label: formatProductCategoryReportMonthLabelInternal(reportDate),
    });
  }
  return chronologicalPoints.reverse();
}

export function buildProductCategoryTrendSnapshotImpl(
  payload: ProductCategoryPnlPayload,
  label: string | undefined,
  meta: ResultMeta | undefined,
  selectDetailRows: SelectDetailRows,
): ProductCategoryTrendSnapshotLike {
  return {
    reportDate: payload.report_date,
    label,
    view: payload.view,
    meta,
    rows: selectDetailRows(payload.rows, undefined),
    assetTotal: payload.asset_total,
    liabilityTotal: payload.liability_total,
    grandTotal: payload.grand_total,
    interestSpread: payload.interest_spread ?? null,
    interestEarningSpread: payload.interest_earning_spread ?? null,
  };
}

export function selectProductCategoryTplScaleYieldChartImpl(
  snapshots: ProductCategoryTrendSnapshotLike[],
) {
  const chart = buildSnapshotChartInternal(snapshots, (snapshot) => {
    const row = findProductCategoryRowInternal(snapshot.rows, "bond_tpl");
    if (!row) {
      return null;
    }
    const cnyScale = yiNumberInternal(row.cny_scale);
    const foreignScale = yiNumberInternal(row.foreign_scale);
    const weightedYield = percentNumberInternal(row.weighted_yield);
    if (cnyScale === null || foreignScale === null || weightedYield === null) {
      return null;
    }
    return { cnyScale, foreignScale, weightedYield };
  });
  if (chart.labels.length === 0) {
    return null;
  }
  return {
    labels: chart.labels,
    cnyScale: chart.points.map((point) => point.cnyScale),
    foreignScale: chart.points.map((point) => point.foreignScale),
    weightedYield: chart.points.map((point) => point.weightedYield),
  };
}

export function selectProductCategoryCurrencyNetIncomeChartImpl(
  snapshots: ProductCategoryTrendSnapshotLike[],
) {
  const chart = buildSnapshotChartInternal(snapshots, (snapshot) => {
    const row = snapshot.grandTotal;
    if (!row) {
      return null;
    }
    const cnyNet = yiNumberInternal(row.cny_net);
    const foreignNet = yiNumberInternal(row.foreign_net);
    if (cnyNet === null || foreignNet === null) {
      return null;
    }
    return { cnyNet, foreignNet };
  });
  if (chart.labels.length === 0) {
    return null;
  }
  return {
    labels: chart.labels,
    cnyNet: chart.points.map((point) => point.cnyNet),
    foreignNet: chart.points.map((point) => point.foreignNet),
  };
}

export function selectProductCategoryInterestEarningIncomeScaleChartImpl(
  snapshots: ProductCategoryTrendSnapshotLike[],
) {
  const chart = buildSnapshotChartInternal(snapshots, (snapshot) => {
    const row = findProductCategoryRowInternal(
      snapshot.rows,
      "interest_earning_assets",
    );
    if (!row) {
      return null;
    }
    const scale = yiNumberInternal(row.cnx_scale);
    const income = yiNumberInternal(row.business_net_income);
    if (scale === null || income === null) {
      return null;
    }
    return { scale, income };
  });
  if (chart.labels.length === 0) {
    return null;
  }
  return {
    labels: chart.labels,
    scale: chart.points.map((point) => point.scale),
    income: chart.points.map((point) => point.income),
  };
}

export function selectProductCategoryInterestEarningAssetLiabilityScaleChartImpl(
  snapshots: ProductCategoryTrendSnapshotLike[],
) {
  const chart = buildSnapshotChartInternal(snapshots, (snapshot) => {
    const interestEarningAssets = findProductCategoryRowInternal(
      snapshot.rows,
      "interest_earning_assets",
    );
    const interestBearingLiabilities = snapshot.liabilityTotal;
    if (!interestEarningAssets || !interestBearingLiabilities) {
      return null;
    }
    const interestEarningAssetScale = yiNumberInternal(
      interestEarningAssets.cnx_scale,
    );
    const liabilityScale = yiNumberInternal(
      interestBearingLiabilities.cnx_scale,
    );
    if (interestEarningAssetScale === null || liabilityScale === null) {
      return null;
    }
    return {
      interestEarningAssetScale,
      interestBearingLiabilityScale: Math.abs(liabilityScale),
    };
  });
  if (chart.labels.length === 0) {
    return null;
  }
  return {
    labels: chart.labels,
    interestEarningAssetScale: chart.points.map(
      (point) => point.interestEarningAssetScale,
    ),
    interestBearingLiabilityScale: chart.points.map(
      (point) => point.interestBearingLiabilityScale,
    ),
  };
}

export function selectProductCategoryInterestSpreadChartImpl(
  snapshots: ProductCategoryTrendSnapshotLike[],
) {
  const chart = buildSnapshotChartInternal(snapshots, (snapshot) => {
    const assetYield = percentNumberInternal(
      snapshot.interestSpread?.all_currency_asset_yield_pct?.raw,
    );
    const liabilityYield = percentNumberInternal(
      snapshot.interestSpread?.all_currency_liability_yield_pct?.raw,
    );
    const spread = productCategoryInterestSpreadForBasisInternal(
      snapshot,
      "weighted",
    );
    if (assetYield === null || liabilityYield === null || spread === null) {
      return null;
    }
    return { assetYield, liabilityYield, spread };
  });
  if (chart.labels.length === 0) {
    return null;
  }
  return {
    labels: chart.labels,
    assetYield: chart.points.map((point) => point.assetYield),
    liabilityYield: chart.points.map((point) => point.liabilityYield),
    spread: chart.points.map((point) => point.spread),
  };
}

export function selectProductCategoryInterestEarningSpreadChartImpl(
  snapshots: ProductCategoryTrendSnapshotLike[],
) {
  const chart = buildSnapshotChartInternal(snapshots, (snapshot) => {
    const assetYield = percentNumberInternal(
      snapshot.interestEarningSpread?.all_currency_asset_yield_pct?.raw,
    );
    const liabilityYield = percentNumberInternal(
      snapshot.interestEarningSpread?.all_currency_liability_yield_pct?.raw,
    );
    const spread = productCategoryInterestEarningSpreadForBasisInternal(
      snapshot,
      "weighted",
    );
    if (assetYield === null || liabilityYield === null || spread === null) {
      return null;
    }
    return { assetYield, liabilityYield, spread };
  });
  if (chart.labels.length === 0) {
    return null;
  }
  return {
    labels: chart.labels,
    assetYield: chart.points.map((point) => point.assetYield),
    liabilityYield: chart.points.map((point) => point.liabilityYield),
    spread: chart.points.map((point) => point.spread),
  };
}

export function selectProductCategoryInterestSpreadYearComparisonChartImpl(
  snapshots: ProductCategoryTrendSnapshotLike[],
  basis: ProductCategoryInterestSpreadBasisLike = "weighted",
) {
  const yearMonthSpread = new Map<number, Map<number, number | null>>();
  let hasSpreadValue = false;
  chronologicalProductCategorySnapshotsInternal(snapshots).forEach(
    (snapshot) => {
      const parsed = parseProductCategoryReportDateInternal(
        snapshot.reportDate,
      );
      if (!parsed) {
        return;
      }
      const spread = productCategoryInterestSpreadForBasisInternal(
        snapshot,
        basis,
      );
      if (spread !== null) {
        hasSpreadValue = true;
      }
      const existing =
        yearMonthSpread.get(parsed.year) ?? new Map<number, number | null>();
      existing.set(parsed.month, spread);
      yearMonthSpread.set(parsed.year, existing);
    },
  );
  if (!hasSpreadValue || yearMonthSpread.size === 0) {
    return null;
  }

  const sortedMonths = Array.from({ length: 12 }, (_, index) => index + 1);
  const sortedYears = Array.from(yearMonthSpread.keys()).sort(
    (left, right) => left - right,
  );
  return {
    labels: sortedMonths.map((month) =>
      formatProductCategoryShortMonthLabelInternal(month),
    ),
    monthKeys: sortedMonths,
    comparisonStatus: buildProductCategoryYearComparisonStatusImpl(
      snapshots,
      (snapshot) =>
        productCategoryInterestSpreadForBasisInternal(snapshot, basis),
    ),
    series: sortedYears.map((year) => ({
      year: `${year}\u5e74`,
      spread: sortedMonths.map(
        (month) => yearMonthSpread.get(year)?.get(month) ?? null,
      ),
    })),
  };
}

export function selectProductCategoryInterestEarningSpreadYearComparisonChartImpl(
  snapshots: ProductCategoryTrendSnapshotLike[],
  basis: ProductCategoryInterestSpreadBasisLike = "weighted",
) {
  const yearMonthSpread = new Map<number, Map<number, number | null>>();
  let hasSpreadValue = false;
  chronologicalProductCategorySnapshotsInternal(snapshots).forEach(
    (snapshot) => {
      const parsed = parseProductCategoryReportDateInternal(
        snapshot.reportDate,
      );
      if (!parsed) {
        return;
      }
      const spread = productCategoryInterestEarningSpreadForBasisInternal(
        snapshot,
        basis,
      );
      if (spread !== null) {
        hasSpreadValue = true;
      }
      const existing =
        yearMonthSpread.get(parsed.year) ?? new Map<number, number | null>();
      existing.set(parsed.month, spread);
      yearMonthSpread.set(parsed.year, existing);
    },
  );
  if (!hasSpreadValue || yearMonthSpread.size === 0) {
    return null;
  }

  const sortedMonths = Array.from({ length: 12 }, (_, index) => index + 1);
  const sortedYears = Array.from(yearMonthSpread.keys()).sort(
    (left, right) => left - right,
  );
  return {
    labels: sortedMonths.map((month) =>
      formatProductCategoryShortMonthLabelInternal(month),
    ),
    monthKeys: sortedMonths,
    comparisonStatus: buildProductCategoryYearComparisonStatusImpl(
      snapshots,
      (snapshot) =>
        productCategoryInterestEarningSpreadForBasisInternal(snapshot, basis),
    ),
    series: sortedYears.map((year) => ({
      year: `${year}\u5e74`,
      spread: sortedMonths.map(
        (month) => yearMonthSpread.get(year)?.get(month) ?? null,
      ),
    })),
  };
}

export function selectProductCategoryIntermediateBusinessIncomeYearComparisonChartImpl(
  snapshots: ProductCategoryTrendSnapshotLike[],
) {
  const yearMonthIncome = new Map<number, Map<number, number | null>>();
  const months = new Set<number>();
  let hasIncomeValue = false;

  chronologicalProductCategorySnapshotsInternal(snapshots).forEach(
    (snapshot) => {
      const parsed = parseProductCategoryReportDateInternal(
        snapshot.reportDate,
      );
      if (!parsed) {
        return;
      }
      const row = findProductCategoryRowInternal(
        snapshot.rows,
        "intermediate_business_income",
      );
      const income = row ? yiNumberInternal(row.business_net_income) : null;
      if (income !== null) {
        hasIncomeValue = true;
      }
      const existing =
        yearMonthIncome.get(parsed.year) ?? new Map<number, number | null>();
      existing.set(parsed.month, income);
      yearMonthIncome.set(parsed.year, existing);
      months.add(parsed.month);
    },
  );

  if (!hasIncomeValue || yearMonthIncome.size === 0 || months.size === 0) {
    return null;
  }

  const sortedMonths = Array.from(months).sort((left, right) => left - right);
  const sortedYears = Array.from(yearMonthIncome.keys()).sort(
    (left, right) => left - right,
  );
  return {
    labels: sortedMonths.map((month) =>
      formatProductCategoryShortMonthLabelInternal(month),
    ),
    comparisonStatus: buildProductCategoryYearComparisonStatusImpl(
      snapshots,
      (snapshot) => {
        const row = findProductCategoryRowInternal(
          snapshot.rows,
          "intermediate_business_income",
        );
        return row ? yiNumberInternal(row.business_net_income) : null;
      },
    ),
    series: sortedYears.map((year) => ({
      year: `${year}\u5e74`,
      income: sortedMonths.map(
        (month) => yearMonthIncome.get(year)?.get(month) ?? null,
      ),
    })),
  };
}

function buildProductCategoryYearComparisonStatusImpl(
  snapshots: ProductCategoryTrendSnapshotLike[],
  selectValue: (snapshot: ProductCategoryTrendSnapshotLike) => number | null,
) {
  const pointsByYearMonth = new Map<
    string,
    {
      year: number;
      month: number;
      value: number | null;
      meta?: ResultMeta;
    }
  >();
  chronologicalProductCategorySnapshotsInternal(snapshots).forEach(
    (snapshot) => {
      const parsed = parseProductCategoryReportDateInternal(
        snapshot.reportDate,
      );
      if (!parsed) {
        return;
      }
      pointsByYearMonth.set(`${parsed.year}-${parsed.month}`, {
        ...parsed,
        value: selectValue(snapshot),
        meta: snapshot.meta,
      });
    },
  );

  const finitePoints = Array.from(pointsByYearMonth.values()).filter(
    (
      point,
    ): point is typeof point & {
      value: number;
    } => point.value !== null && Number.isFinite(point.value),
  );
  const yearsByMonth = new Map<number, Set<number>>();
  finitePoints.forEach((point) => {
    const years = yearsByMonth.get(point.month) ?? new Set<number>();
    years.add(point.year);
    yearsByMonth.set(point.month, years);
  });

  const qualityIssueMonthCount = finitePoints.filter(
    (point) =>
      point.meta !== undefined &&
      (point.meta.quality_flag !== "ok" ||
        point.meta.vendor_status !== "ok" ||
        point.meta.fallback_mode !== "none"),
  ).length;
  const hasUnknownQuality = finitePoints.some(
    (point) => point.meta === undefined,
  );

  return {
    comparableMonthCount: Array.from(yearsByMonth.values()).filter(
      (years) => years.size >= 2,
    ).length,
    qualityState:
      qualityIssueMonthCount > 0
        ? "degraded"
        : hasUnknownQuality
          ? "unknown"
          : "ok",
    qualityIssueMonthCount,
  };
}
