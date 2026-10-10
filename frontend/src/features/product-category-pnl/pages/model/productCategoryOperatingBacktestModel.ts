import type {
  ProductCategoryOperatingActionKind,
  ProductCategoryOperatingBacktestActionRow,
  ProductCategoryOperatingBacktestMissActionRow,
  ProductCategoryOperatingBacktestCalibrationRow,
  ProductCategoryOperatingBacktestExample,
} from "./productCategoryOperatingBacktestOutcomeModel";
import type { ProductCategoryCandidateMetricStatus } from "./productCategoryPnlModelInternals";
import type { ProductCategoryOperatingActionQueueRow } from "./productCategoryOperatingAnalysisModel";
import type {
  ProductCategoryAttributionPayload,
  ProductCategoryPnlRow,
  ProductCategoryPnlPayload,
} from "../../../../api/contracts";
import {
  parentProductCategoryIdsInternal as parentProductCategoryIds,
  parseProductCategoryReportDateInternal as parseProductCategoryReportDate,
  rawYiNumberInternal as rawYiNumber,
  decimalNumberInternal as decimalNumber,
  signedYiDeltaLabelInternal as signedYiDeltaLabel,
  PRODUCT_CATEGORY_CANDIDATE_METRIC_STATUS,
} from "./productCategoryPnlModelInternals";
import {
  buildProductCategoryOperatingMovementRows,
  selectProductCategoryOperatingActionQueue,
} from "./productCategoryOperatingAnalysisModel";
import { EM_DASH } from "../../../../utils/format";
import {
  buildProductCategoryOperatingBacktestExample,
  summarizeProductCategoryOperatingBacktestOutcomes,
} from "./productCategoryOperatingBacktestOutcomeModel";

export type ProductCategoryOperatingBacktestLatestReviewRow = {
  priorityLabel: string;
  categoryId: string;
  categoryLabel: string;
  actionKind: ProductCategoryOperatingActionKind;
  actionLabel: string;
  reviewLabel: string;
  riskRankLabel: string;
  riskReasonLabel: string;
  reasonLabel: string;
  impactLabel: string;
  watchReportDateLabel: string;
  releaseConditionLabel: string;
  observationLabel: string;
  gapLabel: string;
  evidenceLabel: string;
  currentEvidenceItems: string[];
  checkItems: string[];
  tone: "positive" | "negative" | "neutral";
};

export type ProductCategoryOperatingBacktestSurface = {
  metricStatus: ProductCategoryCandidateMetricStatus;
  summary: {
    evaluatedMonthCount: number;
    signalCount: number;
    latestPendingCount: number;
    coverageLabel: string;
    attributionCoverageLabel: string;
    attributionCoverageDetailLabel: string;
    backtestGateLabel: string;
    backtestGateDetailLabel: string;
    backtestGateTone: "positive" | "negative" | "neutral";
    sampleRepairLabel: string;
    sampleRepairDetailLabel: string;
    sampleRepairDateLabel: string;
    sampleRepairReviewLabel: string;
    reviewWorkloadLabel: string;
    reviewWorkloadDetailLabel: string;
    dispositionLabel: string;
    dispositionDetailLabel: string;
    evidenceLabel: string;
  };
  coverageRows: Array<{
    reportDate: string;
    nextReportDate: string | null;
    statusLabel: string;
    detailLabel: string;
    signalCount: number;
    tone: "positive" | "negative" | "neutral";
  }>;
  actionRows: ProductCategoryOperatingBacktestActionRow[];
  missReasonRows: ProductCategoryOperatingBacktestMissActionRow[];
  calibrationRows: ProductCategoryOperatingBacktestCalibrationRow[];
  latestReviewRows: ProductCategoryOperatingBacktestLatestReviewRow[];
  examples: ProductCategoryOperatingBacktestExample[];
  emptyCopy: string | null;
};

function productCategoryBacktestCurrentUnexplainedAbs(
  action: ProductCategoryOperatingActionQueueRow,
): number | null {
  if (action.actionKind !== "review_attribution") {
    return null;
  }
  const parsed = Number(action.primaryMetricLabel);
  return Number.isFinite(parsed) ? Math.abs(parsed) : null;
}

function productCategoryBacktestNextUnexplainedAbs(
  attribution: ProductCategoryAttributionPayload | null | undefined,
  rows: ProductCategoryPnlRow[],
  categoryId: string,
): number | null {
  if (
    !attribution ||
    attribution.compare !== "mom" ||
    attribution.state !== "complete"
  ) {
    return null;
  }
  const parentCategoryIds = parentProductCategoryIds(rows);
  const movement = buildProductCategoryOperatingMovementRows(
    attribution,
    parentCategoryIds,
  ).find((row) => row.categoryId === categoryId);
  if (!movement) {
    return 0;
  }
  return movement.leadingDriverKey === "unexplained_effect"
    ? Math.abs(movement.leadingDriverValue)
    : 0;
}

function productCategoryBacktestLatestReviewRows(input: {
  latestActionRows: ProductCategoryOperatingActionQueueRow[];
  actionRows: ProductCategoryOperatingBacktestActionRow[];
  calibrationRows: ProductCategoryOperatingBacktestCalibrationRow[];
  latestReportDate: string | null;
  backtestGateTone: "positive" | "negative" | "neutral";
}): ProductCategoryOperatingBacktestLatestReviewRow[] {
  const actionRowsByAction = new Map(
    input.actionRows.map((row) => [row.actionKind, row]),
  );
  const watchReportDate = input.latestReportDate
    ? productCategoryNextMonthEndDate(input.latestReportDate)
    : null;
  const reviewLabel =
    input.backtestGateTone === "negative" ? "补样本后复核" : "复核后执行";
  const riskRankForCalibration = (
    calibration: ProductCategoryOperatingBacktestCalibrationRow,
  ) => {
    if (calibration.confidenceLabel === "高置信") {
      return "P1 高置信复核";
    }
    if (calibration.confidenceLabel === "中置信") {
      return "P2 中样本复核";
    }
    return "P3 低样本复核";
  };
  const checkItemsForAction = (
    actionKind: ProductCategoryOperatingActionKind,
  ): string[] => {
    if (actionKind === "reprice_or_improve") {
      return [
        "确认最新收益率改善证据",
        "复核规模扩张是否稀释收益率",
        "核对净营收是否同步改善",
      ];
    }
    if (actionKind === "shrink_or_limit") {
      return [
        "确认压降后净营收改善",
        "复核规模回落是否落实",
        "核对收益率是否继续承压",
      ];
    }
    if (actionKind === "selective_growth") {
      return [
        "确认扩张后仍为正贡献",
        "复核新增规模质量",
        "核对收益率是否被摊薄",
      ];
    }
    return ["确认未解释差异下降", "复核归因残差来源", "核对正式归因闭合误差"];
  };
  const releaseConditionForAction = (
    actionKind: ProductCategoryOperatingActionKind,
  ): string => {
    if (actionKind === "reprice_or_improve") {
      return "放行条件：收益率转正改善且净营收不恶化";
    }
    if (actionKind === "shrink_or_limit") {
      return "放行条件：净营收改善且规模不反弹";
    }
    if (actionKind === "selective_growth") {
      return "放行条件：规模扩张且净营收为正";
    }
    return "放行条件：未解释差异下降且闭合误差可接受";
  };
  const observationForAction = (
    actionKind: ProductCategoryOperatingActionKind,
  ): string => {
    if (actionKind === "reprice_or_improve") {
      return "观察口径：下一期收益率改善且净营收不恶化";
    }
    if (actionKind === "shrink_or_limit") {
      return "观察口径：下一期净营收改善且规模不反弹";
    }
    if (actionKind === "selective_growth") {
      return "观察口径：下一期规模扩张且净营收为正";
    }
    return "观察口径：下一期未解释差异下降且闭合误差可接受";
  };
  const gapForAction = (
    row: ProductCategoryOperatingActionQueueRow,
  ): string => {
    if (row.actionKind === "reprice_or_improve") {
      const yieldEvidence =
        row.evidenceItems.find((item) => item.startsWith("收益率 ")) ??
        "收益率 -";
      return `判定缺口：当前${yieldEvidence}，需下一期收益率转正改善`;
    }
    if (row.actionKind === "shrink_or_limit") {
      const netIncomeEvidence =
        row.evidenceItems.find((item) => item.startsWith("净营收 ")) ??
        "净营收 -";
      return `判定缺口：当前${netIncomeEvidence}，需下一期净营收改善`;
    }
    if (row.actionKind === "selective_growth") {
      const scaleEvidence =
        row.evidenceItems.find((item) => item.startsWith("规模 ")) ?? "规模 -";
      return `判定缺口：当前${scaleEvidence}，需下一期规模扩张且净营收为正`;
    }
    return "判定缺口：需下一期正式归因确认未解释差异下降";
  };
  const tightenRowsByAction = new Map(
    input.calibrationRows
      .filter((row) => row.recommendationLabel === "收紧触发条件")
      .map((row) => [row.actionKind, row]),
  );
  return input.latestActionRows.flatMap((row) => {
    const calibration = tightenRowsByAction.get(row.actionKind);
    if (!calibration) {
      return [];
    }
    const actionRow = actionRowsByAction.get(row.actionKind);
    return [
      {
        priorityLabel: row.priorityLabel,
        categoryId: row.categoryId,
        categoryLabel: row.categoryLabel,
        actionKind: row.actionKind,
        actionLabel: row.actionLabel,
        reviewLabel,
        riskRankLabel: riskRankForCalibration(calibration),
        riskReasonLabel: `${calibration.confidenceLabel}；${calibration.reasonLabel.replace(/^命中率 [^，]+，/, "")}`,
        reasonLabel: `历史回测建议${calibration.recommendationLabel}：${calibration.reasonLabel}`,
        impactLabel: actionRow
          ? `历史均值：净营收 ${actionRow.averageNetIncomeDeltaLabel} 亿元、收益率 ${actionRow.averageYieldDeltaBpLabel}、规模 ${actionRow.averageScaleDeltaLabel} 亿元`
          : `历史均值：${EM_DASH}`,
        watchReportDateLabel: `观察月份：${watchReportDate ?? EM_DASH}`,
        releaseConditionLabel: releaseConditionForAction(row.actionKind),
        observationLabel: observationForAction(row.actionKind),
        gapLabel: gapForAction(row),
        evidenceLabel: `${row.triggerLabel}；${calibration.confidenceLabel}，${calibration.evidenceLabel}`,
        currentEvidenceItems: row.evidenceItems,
        checkItems: checkItemsForAction(row.actionKind),
        tone: "negative" as const,
      },
    ];
  });
}

function productCategoryBacktestReviewWorkload(
  latestReviewRows: ProductCategoryOperatingBacktestLatestReviewRow[],
): {
  reviewWorkloadLabel: string;
  reviewWorkloadDetailLabel: string;
} {
  const p1Count = latestReviewRows.filter((row) =>
    row.riskRankLabel.startsWith("P1"),
  ).length;
  const p2Count = latestReviewRows.filter((row) =>
    row.riskRankLabel.startsWith("P2"),
  ).length;
  const p3Count = latestReviewRows.filter((row) =>
    row.riskRankLabel.startsWith("P3"),
  ).length;
  const headline =
    p1Count > 0
      ? `P1 ${p1Count}`
      : p2Count > 0
        ? `P2 ${p2Count}`
        : p3Count > 0
          ? `P3 ${p3Count}`
          : "0";
  return {
    reviewWorkloadLabel: headline,
    reviewWorkloadDetailLabel: `复核 ${latestReviewRows.length} 条；P1 ${p1Count} 条，P2 ${p2Count} 条，P3 ${p3Count} 条`,
  };
}

function productCategoryBacktestRuleDisposition(
  calibrationRows: ProductCategoryOperatingBacktestCalibrationRow[],
): {
  dispositionLabel: string;
  dispositionDetailLabel: string;
} {
  const tightenCount = calibrationRows.filter(
    (row) => row.recommendationLabel === "收紧触发条件",
  ).length;
  const observeCount = calibrationRows.filter(
    (row) => row.recommendationLabel === "继续观察",
  ).length;
  const keepCount = calibrationRows.filter(
    (row) => row.recommendationLabel === "保留规则",
  ).length;
  const headline =
    tightenCount > 0
      ? `收紧 ${tightenCount}`
      : observeCount > 0
        ? `观察 ${observeCount}`
        : `保留 ${keepCount}`;
  return {
    dispositionLabel: headline,
    dispositionDetailLabel: `规则处置：收紧 ${tightenCount} 条，观察 ${observeCount} 条，保留 ${keepCount} 条`,
  };
}

const PRODUCT_CATEGORY_BACKTEST_REQUIRED_MONTH_COUNT = 3;
const PRODUCT_CATEGORY_BACKTEST_REQUIRED_SIGNAL_COUNT = 6;

function productCategoryBacktestGate(input: {
  evaluatedMonthCount: number;
  signalCount: number;
}): {
  backtestGateLabel: string;
  backtestGateDetailLabel: string;
  backtestGateTone: "positive" | "negative" | "neutral";
} {
  const enoughHistory =
    input.evaluatedMonthCount >= PRODUCT_CATEGORY_BACKTEST_REQUIRED_MONTH_COUNT;
  const enoughSignals =
    input.signalCount >= PRODUCT_CATEGORY_BACKTEST_REQUIRED_SIGNAL_COUNT;
  if (enoughHistory && enoughSignals) {
    return {
      backtestGateLabel: "可用于复核",
      backtestGateDetailLabel: `连续回测 ${input.evaluatedMonthCount}/${PRODUCT_CATEGORY_BACKTEST_REQUIRED_MONTH_COUNT} 个月；可评价信号 ${input.signalCount} 条，达到规则复核阈值`,
      backtestGateTone: "positive",
    };
  }
  return {
    backtestGateLabel: "样本不足",
    backtestGateDetailLabel: `连续回测 ${input.evaluatedMonthCount}/${PRODUCT_CATEGORY_BACKTEST_REQUIRED_MONTH_COUNT} 个月；可评价信号 ${input.signalCount} 条，未达到规则放行阈值`,
    backtestGateTone: "negative",
  };
}

function productCategoryBacktestSampleRepair(input: {
  evaluatedMonthCount: number;
  signalCount: number;
  latestReportDate: string | null;
}): {
  sampleRepairLabel: string;
  sampleRepairDetailLabel: string;
  sampleRepairDateLabel: string;
  sampleRepairReviewLabel: string;
} {
  const missingMonthCount = Math.max(
    0,
    PRODUCT_CATEGORY_BACKTEST_REQUIRED_MONTH_COUNT - input.evaluatedMonthCount,
  );
  const missingSignalCount = Math.max(
    0,
    PRODUCT_CATEGORY_BACKTEST_REQUIRED_SIGNAL_COUNT - input.signalCount,
  );
  const repairDates: string[] = [];
  let cursor = input.latestReportDate;
  for (let index = 0; index < missingMonthCount; index += 1) {
    const nextDate = cursor ? productCategoryNextMonthEndDate(cursor) : null;
    if (!nextDate) {
      break;
    }
    repairDates.push(nextDate);
    cursor = nextDate;
  }
  return {
    sampleRepairLabel:
      missingMonthCount > 0
        ? `补 ${missingMonthCount} 个月`
        : missingSignalCount > 0
          ? `补 ${missingSignalCount} 条信号`
          : "样本已满足",
    sampleRepairDetailLabel: `闸口需 ${PRODUCT_CATEGORY_BACKTEST_REQUIRED_MONTH_COUNT} 个月/${PRODUCT_CATEGORY_BACKTEST_REQUIRED_SIGNAL_COUNT} 条信号；当前 ${input.evaluatedMonthCount} 个月/${input.signalCount} 条信号`,
    sampleRepairDateLabel:
      repairDates.length > 0
        ? `需补月份：${repairDates.join("、")}`
        : "需补月份：-",
    sampleRepairReviewLabel:
      repairDates.length > 0
        ? `最早复核：${repairDates[repairDates.length - 1]} 后`
        : missingSignalCount > 0
          ? "最早复核：待补齐信号后"
          : "最早复核：当前可复核",
  };
}

function productCategoryNextMonthEndDate(reportDate: string): string | null {
  const parsed = parseProductCategoryReportDate(reportDate);
  if (!parsed) {
    return null;
  }
  const nextMonth = parsed.month === 12 ? 1 : parsed.month + 1;
  const nextYear = parsed.month === 12 ? parsed.year + 1 : parsed.year;
  const lastDay = new Date(nextYear, nextMonth, 0).getDate();
  return `${nextYear}-${String(nextMonth).padStart(2, "0")}-${String(lastDay).padStart(2, "0")}`;
}

function productCategoryReportDatesAreConsecutiveMonths(
  current: string,
  next: string,
): boolean {
  return productCategoryNextMonthEndDate(current) === next;
}

function productCategoryBacktestEmptyCopy(
  coverageRows: ProductCategoryOperatingBacktestSurface["coverageRows"],
): string {
  const skippedRow = coverageRows.find(
    (row) => row.statusLabel === "跳过：非连续月份",
  );
  if (skippedRow?.nextReportDate) {
    const expectedNextReportDate = productCategoryNextMonthEndDate(
      skippedRow.reportDate,
    );
    return `需要至少两个连续月度正式 payload 才能回测行动信号；${skippedRow.reportDate} 后缺少 ${expectedNextReportDate ?? EM_DASH}，实际下一期为 ${skippedRow.nextReportDate}。`;
  }
  return "需要至少两个连续月度正式 payload 才能回测行动信号。";
}

function productCategoryAttributionCoverage(input: {
  payloads: ProductCategoryPnlPayload[];
  attributionsByReportDate?: Map<
    string,
    ProductCategoryAttributionPayload | null
  >;
}): {
  attributionCoverageLabel: string;
  attributionCoverageDetailLabel: string;
} {
  const reportDates = Array.from(
    new Set(input.payloads.map((payload) => payload.report_date)),
  ).sort();
  if (reportDates.length === 0) {
    return {
      attributionCoverageLabel: "0/0",
      attributionCoverageDetailLabel: "暂无月度归因样本",
    };
  }
  const coveredDates = reportDates.filter((reportDate) =>
    input.attributionsByReportDate?.get(reportDate),
  );
  const missingDates = reportDates.filter(
    (reportDate) => !input.attributionsByReportDate?.get(reportDate),
  );
  const missingSuffix =
    missingDates.length > 0
      ? `；缺少 ${missingDates.slice(0, 3).join("、")}`
      : "；归因样本完整";
  return {
    attributionCoverageLabel: `${coveredDates.length}/${reportDates.length}`,
    attributionCoverageDetailLabel: `归因覆盖 ${coveredDates.length}/${reportDates.length}${missingSuffix}`,
  };
}

export function selectProductCategoryOperatingActionBacktestSurface(input: {
  payloads: ProductCategoryPnlPayload[];
  attributionsByReportDate?: Map<
    string,
    ProductCategoryAttributionPayload | null
  >;
}): ProductCategoryOperatingBacktestSurface {
  const payloads = input.payloads
    .filter(
      (payload) =>
        payload.view === "monthly" && payload.scenario_rate_pct === null,
    )
    .slice()
    .sort((left, right) => left.report_date.localeCompare(right.report_date));
  const attributionCoverage = productCategoryAttributionCoverage({
    payloads,
    attributionsByReportDate: input.attributionsByReportDate,
  });
  const latestPayload = payloads[payloads.length - 1];
  const latestActionRows = latestPayload
    ? selectProductCategoryOperatingActionQueue({
        rows: latestPayload.rows,
        attribution: input.attributionsByReportDate?.get(
          latestPayload.report_date,
        ),
        parentCategoryIds: parentProductCategoryIds(latestPayload.rows),
      }).rows
    : [];
  const latestPendingCount = latestActionRows.length;
  const samples: ProductCategoryOperatingBacktestExample[] = [];
  const coverageRows: ProductCategoryOperatingBacktestSurface["coverageRows"] =
    [];

  for (let index = 0; index < payloads.length - 1; index += 1) {
    const current = payloads[index];
    const next = payloads[index + 1];
    if (!current || !next) {
      continue;
    }
    const currentActions = selectProductCategoryOperatingActionQueue({
      rows: current.rows,
      attribution: input.attributionsByReportDate?.get(current.report_date),
      parentCategoryIds: parentProductCategoryIds(current.rows),
    }).rows;
    if (
      !productCategoryReportDatesAreConsecutiveMonths(
        current.report_date,
        next.report_date,
      )
    ) {
      coverageRows.push({
        reportDate: current.report_date,
        nextReportDate: next.report_date,
        statusLabel: "跳过：非连续月份",
        detailLabel: `期望下一月末 ${productCategoryNextMonthEndDate(current.report_date) ?? EM_DASH}，实际 ${next.report_date}`,
        signalCount: currentActions.length,
        tone: "negative",
      });
      continue;
    }
    const currentRowsById = new Map(
      current.rows.map((row) => [row.category_id, row]),
    );
    const nextRowsById = new Map(
      next.rows.map((row) => [row.category_id, row]),
    );
    for (const action of currentActions) {
      const currentRow = currentRowsById.get(action.categoryId);
      const nextRow = nextRowsById.get(action.categoryId);
      if (!currentRow || !nextRow) {
        continue;
      }
      // Keep raw amounts/rates through the outcome rules; round only labels.
      const currentNetIncome = rawYiNumber(currentRow.business_net_income);
      const nextNetIncome = rawYiNumber(nextRow.business_net_income);
      const netIncomeDelta =
        currentNetIncome === null || nextNetIncome === null
          ? null
          : nextNetIncome - currentNetIncome;
      const currentYield = decimalNumber(currentRow.weighted_yield);
      const nextYield = decimalNumber(nextRow.weighted_yield);
      const yieldDeltaBp =
        currentYield === null || nextYield === null
          ? null
          : (nextYield - currentYield) * 100;
      const currentScale = rawYiNumber(currentRow.cnx_scale);
      const nextScale = rawYiNumber(nextRow.cnx_scale);
      const scaleDelta =
        currentScale === null || nextScale === null
          ? null
          : nextScale - currentScale;
      const currentUnexplainedAbs =
        productCategoryBacktestCurrentUnexplainedAbs(action);
      const nextUnexplainedAbs = productCategoryBacktestNextUnexplainedAbs(
        input.attributionsByReportDate?.get(next.report_date),
        next.rows,
        action.categoryId,
      );
      samples.push(
        buildProductCategoryOperatingBacktestExample(
          {
            reportDate: current.report_date,
            nextReportDate: next.report_date,
            categoryId: action.categoryId,
            categoryLabel: action.categoryLabel,
            priorityLabel: action.priorityLabel,
            actionKind: action.actionKind,
            actionLabel: action.actionLabel,
            netIncomeDelta,
            nextNetIncome,
            yieldDeltaBp,
            scaleDelta,
            currentUnexplainedAbs,
            nextUnexplainedAbs,
          },
          signedYiDeltaLabel,
        ),
      );
    }
    coverageRows.push({
      reportDate: current.report_date,
      nextReportDate: next.report_date,
      statusLabel: "已回测",
      detailLabel: "使用下一期 monthly 正式 payload 验证",
      signalCount: currentActions.length,
      tone: "positive",
    });
  }
  if (latestPayload) {
    coverageRows.push({
      reportDate: latestPayload.report_date,
      nextReportDate: null,
      statusLabel: "最新月待观察",
      detailLabel: `等待下一期 ${productCategoryNextMonthEndDate(latestPayload.report_date) ?? EM_DASH} payload 验证`,
      signalCount: latestPendingCount,
      tone: "neutral",
    });
  }

  const evaluatedDates = Array.from(
    new Set(samples.map((sample) => sample.reportDate)),
  ).sort();
  const { actionRows, missReasonRows, calibrationRows } =
    summarizeProductCategoryOperatingBacktestOutcomes({
      samples,
      formatYiDelta: signedYiDeltaLabel,
    });
  const backtestGate = productCategoryBacktestGate({
    evaluatedMonthCount: evaluatedDates.length,
    signalCount: samples.length,
  });
  const sampleRepair = productCategoryBacktestSampleRepair({
    evaluatedMonthCount: evaluatedDates.length,
    signalCount: samples.length,
    latestReportDate: latestPayload?.report_date ?? null,
  });
  const latestReviewRows = productCategoryBacktestLatestReviewRows({
    latestActionRows,
    actionRows,
    calibrationRows,
    latestReportDate: latestPayload?.report_date ?? null,
    backtestGateTone: backtestGate.backtestGateTone,
  });
  const reviewWorkload =
    productCategoryBacktestReviewWorkload(latestReviewRows);
  const ruleDisposition =
    productCategoryBacktestRuleDisposition(calibrationRows);

  return {
    metricStatus: PRODUCT_CATEGORY_CANDIDATE_METRIC_STATUS,
    summary: {
      evaluatedMonthCount: evaluatedDates.length,
      signalCount: samples.length,
      latestPendingCount,
      coverageLabel:
        evaluatedDates.length > 0
          ? `${evaluatedDates[0]} 至 ${evaluatedDates[evaluatedDates.length - 1]}`
          : EM_DASH,
      attributionCoverageLabel: attributionCoverage.attributionCoverageLabel,
      attributionCoverageDetailLabel:
        attributionCoverage.attributionCoverageDetailLabel,
      backtestGateLabel: backtestGate.backtestGateLabel,
      backtestGateDetailLabel: backtestGate.backtestGateDetailLabel,
      backtestGateTone: backtestGate.backtestGateTone,
      sampleRepairLabel: sampleRepair.sampleRepairLabel,
      sampleRepairDetailLabel: sampleRepair.sampleRepairDetailLabel,
      sampleRepairDateLabel: sampleRepair.sampleRepairDateLabel,
      sampleRepairReviewLabel: sampleRepair.sampleRepairReviewLabel,
      reviewWorkloadLabel: reviewWorkload.reviewWorkloadLabel,
      reviewWorkloadDetailLabel: reviewWorkload.reviewWorkloadDetailLabel,
      dispositionLabel: ruleDisposition.dispositionLabel,
      dispositionDetailLabel: ruleDisposition.dispositionDetailLabel,
      evidenceLabel: "信号来自动作队列；结果使用下一期 monthly 正式口径验证。",
    },
    coverageRows,
    actionRows,
    missReasonRows,
    calibrationRows,
    latestReviewRows,
    examples: samples
      .slice()
      .sort(
        (left, right) =>
          Math.abs(right.netIncomeDelta ?? 0) -
          Math.abs(left.netIncomeDelta ?? 0),
      )
      .slice(0, 6),
    emptyCopy:
      samples.length === 0
        ? productCategoryBacktestEmptyCopy(coverageRows)
        : null,
  };
}
