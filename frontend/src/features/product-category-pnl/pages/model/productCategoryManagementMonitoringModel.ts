import {
  parseProductCategoryReportDateInternal as parseProductCategoryReportDate,
  PRODUCT_CATEGORY_CANDIDATE_METRIC_STATUS,
  formatProductCategoryShortMonthLabelInternal as formatProductCategoryShortMonthLabel,
  findProductCategoryRowInternal as findProductCategoryRow,
  rawYiNumberInternal as rawYiNumber,
  decimalNumberInternal as decimalNumber,
  signedBpLabelInternal as signedBpLabel,
  signedYiDeltaLabelInternal as signedYiDeltaLabel,
} from "./productCategoryPnlModelInternals";
import { EM_DASH } from "../../../../utils/format";
import type { ProductCategoryTrendSnapshot } from "../productCategoryPnlPageModel";
import type {
  ProductCategoryAttributionPayload,
  ProductCategoryAttributionRow,
  DecimalLike,
} from "../../../../api/contracts";
import type { ProductCategoryCandidateMetricStatus } from "./productCategoryPnlModelInternals";

export type ProductCategoryManagementMonitoringSurface = {
  metricStatus: ProductCategoryCandidateMetricStatus;
  state: "ready" | "insufficient" | "scenario_blocked";
  periodLabel: string;
  currentMonthLabel: string;
  coverageLabel: string;
  emptyCopy: string | null;
  tpl: {
    currentPnlLabel: string;
    currentYieldLabel: string;
    currentScaleLabel: string;
    thresholds: Array<{
      key: "prior_month" | "year_average" | "q1_average";
      label: string;
      targetPnlLabel: string;
      requiredYieldLabel: string;
      liftBpLabel: string;
    }>;
  } | null;
  liability: {
    yearNetLabel: string;
    positivePoolLabel: string;
    negativePoolLabel: string;
    offsetRatioLabel: string;
    currentMonthDeltaLabel: string;
    leadingMovementLabel: string;
    leadingDriverLabel: string;
  } | null;
  derivatives: {
    yearTotalLabel: string;
    monthlyAverageLabel: string;
    volatilityLabel: string;
    topThreeConcentrationLabel: string;
    negativeMonthCountLabel: string;
  } | null;
  runRate: {
    q1MonthlyAverageLabel: string;
    recentPeriodLabel: string;
    recentMonthlyAverageLabel: string;
    yearMonthlyAverageLabel: string;
    recoveryLiftLabel: string;
    remainingMonths: number;
    remainingAtRecentPaceLabel: string;
    gapToYearPaceLabel: string;
  } | null;
  methodNotes: string[];
};

/** Candidate static pace, called only after January-to-report-month coverage is complete. */
export function buildProductCategoryManagementRunRate(monthlyNetIncome: number[]) {
  const month = monthlyNetIncome.length;
  const average = (values: number[]) =>
    values.reduce((total, value) => total + value, 0) / values.length;
  const recentStartMonth = Math.max(1, month - 2);
  const recentMonthlyAverage = average(monthlyNetIncome.slice(-3));
  const yearMonthlyAverage = average(monthlyNetIncome);
  const recoveryLift = recentMonthlyAverage <= 0
    ? null
    : (yearMonthlyAverage / recentMonthlyAverage - 1) * 100;
  const remainingMonths = 12 - month;
  const remainingAtRecentPace = recentMonthlyAverage * remainingMonths;
  return {
    recentStartMonth,
    recentMonthlyAverage,
    yearMonthlyAverage,
    recoveryLift,
    remainingMonths,
    remainingAtRecentPace,
  };
}
const PRODUCT_CATEGORY_MANAGEMENT_LIABILITY_IDS = [
  "interbank_deposits",
  "interbank_borrowings",
  "repo_liabilities",
  "interbank_cds",
  "credit_linked_notes",
] as const;

function emptyProductCategoryManagementMonitoringSurface(
  state: "insufficient" | "scenario_blocked",
  reportDate: string,
  emptyCopy: string,
  coverageLabel = "待补齐",
): ProductCategoryManagementMonitoringSurface {
  const selected = parseProductCategoryReportDate(reportDate);
  return {
    metricStatus: PRODUCT_CATEGORY_CANDIDATE_METRIC_STATUS,
    state,
    periodLabel: selected
      ? `${selected.year} 年 1—${selected.month} 月`
      : "未选择报告月份",
    currentMonthLabel: selected ? `${selected.month} 月` : EM_DASH,
    coverageLabel,
    emptyCopy,
    tpl: null,
    liability: null,
    derivatives: null,
    runRate: null,
    methodNotes: [],
  };
}

function formatProductCategoryManagementYi(value: number): string {
  return value.toFixed(2);
}

function formatProductCategoryManagementPercent(value: number | null): string {
  return value === null || !Number.isFinite(value)
    ? EM_DASH
    : `${value.toFixed(1)}%`;
}

/**
 * Candidate management view derived from year-to-date monthly formal payloads and the selected month's MoM attribution.
 * It does not replace governed totals, forecast results, or formal FTP scenario calculations.
 */
export function selectProductCategoryManagementMonitoringSurface(input: {
  reportDate: string;
  snapshots: ProductCategoryTrendSnapshot[];
  currentAttribution?: ProductCategoryAttributionPayload | null;
  scenarioDistinct?: boolean;
}): ProductCategoryManagementMonitoringSurface {
  if (input.scenarioDistinct) {
    return emptyProductCategoryManagementMonitoringSurface(
      "scenario_blocked",
      input.reportDate,
      "经营修复监控只使用正式基准口径；请将 FTP 场景恢复为正式基准后查看。",
      "正式基线停算",
    );
  }

  const selected = parseProductCategoryReportDate(input.reportDate);
  if (!selected) {
    return emptyProductCategoryManagementMonitoringSurface(
      "insufficient",
      input.reportDate,
      "请选择有效报告月份，监控使用当年年初至所选月的连续正式月度数据。",
      "需选择报告月份",
    );
  }

  const snapshotsByMonth = new Map<number, ProductCategoryTrendSnapshot>();
  input.snapshots.forEach((snapshot) => {
    const parsed = parseProductCategoryReportDate(snapshot.reportDate);
    if (
      parsed?.year === selected.year &&
      parsed.month >= 1 &&
      parsed.month <= selected.month &&
      snapshot.reportDate <= input.reportDate &&
      (!snapshot.view || snapshot.view === "monthly")
    ) {
      snapshotsByMonth.set(parsed.month, snapshot);
    }
  });
  const months = Array.from({ length: selected.month }, (_, index) => index + 1);
  const missingMonths = months.filter(
    (month) => !snapshotsByMonth.has(month),
  );
  if (missingMonths.length > 0) {
    return emptyProductCategoryManagementMonitoringSurface(
      "insufficient",
      input.reportDate,
      `需要 1—${selected.month} 月连续正式月度数据；当前缺少 ${missingMonths.map(formatProductCategoryShortMonthLabel).join("、")}。`,
      `已覆盖 ${selected.month - missingMonths.length}/${selected.month} 月`,
    );
  }
  const yearSnapshots = months.map((month) =>
    snapshotsByMonth.get(month)!,
  );
  const tplRows = yearSnapshots.map((snapshot) =>
    findProductCategoryRow(snapshot.rows, "bond_tpl"),
  );
  const derivativeRows = yearSnapshots.map((snapshot) =>
    findProductCategoryRow(snapshot.rows, "derivatives"),
  );
  const grandTotalValues = yearSnapshots.map((snapshot) =>
    rawYiNumber(snapshot.grandTotal?.business_net_income),
  );
  const liabilityTotalValues = yearSnapshots.map((snapshot) =>
    rawYiNumber(snapshot.liabilityTotal?.business_net_income),
  );
  const tplPnlValues = tplRows.map((row) =>
    rawYiNumber(row?.business_net_income),
  );
  const derivativePnlValues = derivativeRows.map((row) =>
    rawYiNumber(row?.business_net_income),
  );
  const currentAttribution =
    input.currentAttribution?.compare === "mom" &&
    input.currentAttribution.state === "complete" &&
    input.currentAttribution.report_date === input.reportDate
      ? input.currentAttribution
      : null;
  const tplAttributionRow = currentAttribution?.rows.find(
    (row) => row.category_id === "bond_tpl",
  );
  const currentTplPoint = tplAttributionRow?.current;
  const currentTplRow = tplRows[selected.month - 1];
  const requiredValues = [
    ...grandTotalValues,
    ...liabilityTotalValues,
    ...tplPnlValues,
    ...derivativePnlValues,
  ];
  const currentTplScale = rawYiNumber(currentTplPoint?.scale);
  const currentTplPnl = rawYiNumber(currentTplPoint?.business_net_income);
  const currentTplYield = decimalNumber(currentTplPoint?.yield_pct);
  const currentTplFtp = decimalNumber(currentTplRow?.baseline_ftp_rate_pct);
  const currentTplDays = currentTplPoint?.days ?? null;
  if (
    requiredValues.some((value) => value === null) ||
    currentTplScale === null ||
    currentTplScale <= 0 ||
    currentTplPnl === null ||
    currentTplYield === null ||
    currentTplFtp === null ||
    currentTplDays === null ||
    currentTplDays <= 0
  ) {
    return emptyProductCategoryManagementMonitoringSurface(
      "insufficient",
      input.reportDate,
      "连续月份已覆盖，但 TPL、衍生品、合计行或本期正式归因字段不完整，候选监控未生成。",
      `${selected.month}/${selected.month} 月 · 字段不完整`,
    );
  }

  const safeTplPnlValues = tplPnlValues as number[];
  const safeGrandTotalValues = grandTotalValues as number[];
  const safeLiabilityTotalValues = liabilityTotalValues as number[];
  const safeDerivativePnlValues = derivativePnlValues as number[];
  const sum = (values: number[]) =>
    values.reduce((total, value) => total + value, 0);
  const average = (values: number[]) => sum(values) / values.length;
  const yearTplAverage = average(safeTplPnlValues);
  const thresholdInputs = [
    ...(selected.month > 1 ? [{
      key: "prior_month" as const,
      label: `达到 ${selected.month - 1} 月净营收水平`,
      targetPnl: safeTplPnlValues[selected.month - 2]!,
    }] : []),
    {
      key: "year_average" as const,
      label: "达到年内月均净营收水平",
      targetPnl: yearTplAverage,
    },
    ...(selected.month >= 3 ? [{
      key: "q1_average" as const,
      label: "达到 Q1 月均净营收水平",
      targetPnl: average(safeTplPnlValues.slice(0, 3)),
    }] : []),
  ];
  const thresholds = thresholdInputs.map((threshold) => {
    const requiredYield =
      currentTplFtp +
      (threshold.targetPnl / currentTplScale) * (365 / currentTplDays) * 100;
    const liftBp = (requiredYield - currentTplYield) * 100;
    return {
      key: threshold.key,
      label: threshold.label,
      targetPnlLabel: formatProductCategoryManagementYi(threshold.targetPnl),
      requiredYieldLabel: `${requiredYield.toFixed(2)}%`,
      liftBpLabel: signedBpLabel(liftBp),
    };
  });

  const liabilityCategoryTotals = PRODUCT_CATEGORY_MANAGEMENT_LIABILITY_IDS.map(
    (categoryId) => {
      const monthlyValues = yearSnapshots.map((snapshot) =>
        rawYiNumber(
          findProductCategoryRow(snapshot.rows, categoryId)
            ?.business_net_income,
        ),
      );
      return monthlyValues.some((value) => value === null)
        ? null
        : sum(monthlyValues as number[]);
    },
  );
  if (liabilityCategoryTotals.some((value) => value === null)) {
    return emptyProductCategoryManagementMonitoringSurface(
      "insufficient",
      input.reportDate,
      `负债端 1—${selected.month} 月产品明细不完整，候选监控未生成。`,
      `${selected.month}/${selected.month} 月 · 负债明细不完整`,
    );
  }
  const safeLiabilityCategoryTotals = liabilityCategoryTotals as number[];
  const liabilityPositivePool = sum(
    safeLiabilityCategoryTotals.filter((value) => value > 0),
  );
  const liabilityNegativePool = sum(
    safeLiabilityCategoryTotals.filter((value) => value < 0),
  );
  const liabilityOffsetRatio =
    liabilityPositivePool > 0
      ? (Math.abs(liabilityNegativePool) / liabilityPositivePool) * 100
      : null;
  const liabilityCurrentMonthDelta =
    selected.month > 1
      ? safeLiabilityTotalValues[selected.month - 1]! -
        safeLiabilityTotalValues[selected.month - 2]!
      : rawYiNumber(currentAttribution?.totals?.liability_total.effects.delta_business_net_income);
  const liabilityAttributionRows = (currentAttribution?.rows ?? [])
    .filter((row) =>
      PRODUCT_CATEGORY_MANAGEMENT_LIABILITY_IDS.includes(
        row.category_id as (typeof PRODUCT_CATEGORY_MANAGEMENT_LIABILITY_IDS)[number],
      ),
    )
    .map((row) => ({
      row,
      delta: rawYiNumber(row.effects.delta_business_net_income),
    }))
    .filter(
      (item): item is { row: ProductCategoryAttributionRow; delta: number } =>
        item.delta !== null && item.delta < 0,
    )
    .sort((left, right) => left.delta - right.delta);
  const leadingLiabilityMovement = liabilityAttributionRows[0] ?? null;
  const liabilityDriverCandidates = leadingLiabilityMovement
    ? [
        ["天数", leadingLiabilityMovement.row.effects.day_effect],
        ["规模", leadingLiabilityMovement.row.effects.scale_effect],
        ["利率", leadingLiabilityMovement.row.effects.rate_effect],
        ["FTP", leadingLiabilityMovement.row.effects.ftp_effect],
        ["直接项", leadingLiabilityMovement.row.effects.direct_effect],
        ["未解释", leadingLiabilityMovement.row.effects.unexplained_effect],
      ].map(([label, value]) => ({
        label: String(label),
        value: rawYiNumber(value as DecimalLike) ?? 0,
      }))
    : [];
  const leadingLiabilityDriver = liabilityDriverCandidates.sort(
    (left, right) => Math.abs(right.value) - Math.abs(left.value),
  )[0];

  const derivativeYearTotal = sum(safeDerivativePnlValues);
  const derivativeMonthlyAverage = average(safeDerivativePnlValues);
  const derivativeVolatility = Math.sqrt(
    average(
      safeDerivativePnlValues.map(
        (value) => (value - derivativeMonthlyAverage) ** 2,
      ),
    ),
  );
  const derivativeTopThreeConcentration =
    selected.month >= 3 && derivativeYearTotal > 0
      ? (sum(
          safeDerivativePnlValues
            .slice()
            .sort((left, right) => right - left)
            .slice(0, 3),
        ) /
          derivativeYearTotal) *
        100
      : null;
  const derivativeNegativeMonthCount = safeDerivativePnlValues.filter(
    (value) => value < 0,
  ).length;

  const {
    recentStartMonth, recentMonthlyAverage, yearMonthlyAverage,
    recoveryLift, remainingMonths, remainingAtRecentPace,
  } = buildProductCategoryManagementRunRate(safeGrandTotalValues);

  return {
    metricStatus: PRODUCT_CATEGORY_CANDIDATE_METRIC_STATUS,
    state: "ready",
    periodLabel: `${selected.year} 年 1—${selected.month} 月`,
    currentMonthLabel: `${selected.month} 月`,
    coverageLabel: `${selected.month}/${selected.month} 月正式数据`,
    emptyCopy: null,
    tpl: {
      currentPnlLabel: formatProductCategoryManagementYi(currentTplPnl),
      currentYieldLabel: `${currentTplYield.toFixed(2)}%`,
      currentScaleLabel: formatProductCategoryManagementYi(currentTplScale),
      thresholds,
    },
    liability: {
      yearNetLabel: formatProductCategoryManagementYi(
        sum(safeLiabilityTotalValues),
      ),
      positivePoolLabel: formatProductCategoryManagementYi(
        liabilityPositivePool,
      ),
      negativePoolLabel: signedYiDeltaLabel(liabilityNegativePool),
      offsetRatioLabel:
        formatProductCategoryManagementPercent(liabilityOffsetRatio),
      currentMonthDeltaLabel: signedYiDeltaLabel(liabilityCurrentMonthDelta),
      leadingMovementLabel: leadingLiabilityMovement
        ? `${leadingLiabilityMovement.row.category_name || leadingLiabilityMovement.row.category_id} ${signedYiDeltaLabel(leadingLiabilityMovement.delta)}`
        : `${selected.month} 月无负向回落`,
      leadingDriverLabel: leadingLiabilityDriver
        ? `${leadingLiabilityDriver.label} ${signedYiDeltaLabel(leadingLiabilityDriver.value)}`
        : "无可用驱动",
    },
    derivatives: {
      yearTotalLabel: formatProductCategoryManagementYi(derivativeYearTotal),
      monthlyAverageLabel: formatProductCategoryManagementYi(
        derivativeMonthlyAverage,
      ),
      volatilityLabel: formatProductCategoryManagementYi(derivativeVolatility),
      topThreeConcentrationLabel: formatProductCategoryManagementPercent(
        derivativeTopThreeConcentration,
      ),
      negativeMonthCountLabel: `${derivativeNegativeMonthCount} 个月`,
    },
    runRate: {
      q1MonthlyAverageLabel:
        selected.month >= 3
          ? formatProductCategoryManagementYi(average(safeGrandTotalValues.slice(0, 3)))
          : EM_DASH,
      recentPeriodLabel: `${recentStartMonth}—${selected.month} 月`,
      recentMonthlyAverageLabel:
        formatProductCategoryManagementYi(recentMonthlyAverage),
      yearMonthlyAverageLabel:
        formatProductCategoryManagementYi(yearMonthlyAverage),
      recoveryLiftLabel: formatProductCategoryManagementPercent(recoveryLift),
      remainingMonths,
      remainingAtRecentPaceLabel: formatProductCategoryManagementYi(remainingAtRecentPace),
      gapToYearPaceLabel: signedYiDeltaLabel(
        remainingAtRecentPace - yearMonthlyAverage * remainingMonths,
      ),
    },
    methodNotes: [
      `TPL 阈值固定 ${selected.month} 月正式规模、正式 FTP 和归因天数，仅反推达到目标净营收所需收益率，不构成预测；一季度未结束时不展示 Q1 阈值，1 月不展示上月阈值。`,
      `负债改善质量按五类负债产品年内累计正、负净营收池归组；${selected.month} 月回落及驱动直接复用正式月环比归因。`,
      "衍生品稳定性仅以年内月度净营收波动、负值月份和 Top3 月份集中度作为代理；不足三个月时不展示集中度，不识别一次性或可重复收益。",
      `经营节奏使用当年最近 ${Math.min(3, selected.month)} 个月的正式合计净营收月均，静态延展至年末；差额按年内月均延展同样的剩余 ${remainingMonths} 个月比较。近期月均非正时不展示恢复百分比，不替代预算、计财目标或正式预测。`,
    ],
  };
}
