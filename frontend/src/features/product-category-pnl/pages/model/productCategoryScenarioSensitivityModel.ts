import type { ProductCategoryCandidateMetricStatus } from "./productCategoryPnlModelInternals";
import type {
  ProductCategoryPnlRow,
  ProductCategoryPnlPayload,
} from "../../../../api/contracts";
import {
  rawYiNumberInternal as rawYiNumber,
  productCategoryDeltaToneInternal as productCategoryDeltaTone,
  productCategoryYiNumberLabelInternal as productCategoryYiNumberLabel,
  formatSignedProductCategoryYiInternal as formatSignedProductCategoryYi,
  leafProductCategoryRowsInternal as leafProductCategoryRows,
  decimalNumberInternal as decimalNumber,
  PRODUCT_CATEGORY_CANDIDATE_METRIC_STATUS,
} from "./productCategoryPnlModelInternals";
import { EM_DASH } from "../../../../utils/format";
import { formatProductCategoryValue } from "./productCategoryPnlDisplayModel";

export type ProductCategoryScenarioSensitivityRow = {
  rate: string;
  ratePct: number;
  rateLabel: string;
  assetDelta: number | null;
  assetNetIncomeLabel: string;
  assetDeltaLabel: string;
  liabilityDelta: number | null;
  liabilityNetIncomeLabel: string;
  liabilityDeltaLabel: string;
  grandNetIncome: number | null;
  grandDelta: number | null;
  grandNetIncomeLabel: string;
  grandDeltaLabel: string;
  topMoverCategoryLabel: string;
  topMoverDelta: number | null;
  topMoverDeltaLabel: string;
  tone: "positive" | "negative" | "neutral";
};

export type ProductCategoryScenarioInsightCard = {
  key: "best_case" | "worst_case" | "range" | "ftp_slope";
  label: string;
  valueLabel: string;
  detailLabel: string;
  tone: "positive" | "negative" | "neutral";
};

export type ProductCategoryScenarioRiskRow = {
  categoryLabel: string;
  worstRateLabel: string;
  worstDelta: number | null;
  worstDeltaLabel: string;
  occurrenceLabel: string;
  tone: "positive" | "negative" | "neutral";
};

export type ProductCategoryScenarioPathPoint = {
  rateLabel: string;
  grandNetIncomeLabel: string;
  grandDeltaLabel: string;
  positionPct: number;
  positionClassName: string;
  tone: "positive" | "negative" | "neutral";
};

export type ProductCategoryScenarioActionItem = {
  title: string;
  valueLabel: string;
  detailLabel: string;
  tone: "positive" | "negative" | "neutral";
};

export type ProductCategoryScenarioHeatRow = {
  categoryLabel: string;
  exposureLabel: string;
  widthPct: number;
  widthClassName: string;
  tone: "positive" | "negative" | "neutral";
};

export type ProductCategoryScenarioComparisonCell = {
  rate: string;
  ratePct: number;
  rateLabel: string;
  netIncome: number | null;
  netIncomeLabel: string;
  delta: number | null;
  deltaLabel: string;
  tone: "positive" | "negative" | "neutral";
};

export type ProductCategoryScenarioComparisonRow = {
  categoryId: string;
  categoryLabel: string;
  sideLabel: string;
  baselineNetIncome: number | null;
  baselineNetIncomeLabel: string;
  cells: ProductCategoryScenarioComparisonCell[];
  bestRateLabel: string;
  bestDelta: number | null;
  bestDeltaLabel: string;
  worstRateLabel: string;
  worstDelta: number | null;
  worstDeltaLabel: string;
  range: number | null;
  rangeLabel: string;
  maxAbsDelta: number;
  tone: "positive" | "negative" | "neutral";
};

export type ProductCategoryScenarioActionClosureRow = {
  priorityLabel: string;
  categoryId: string;
  categoryLabel: string;
  sideLabel: string;
  triggerRateLabel: string;
  exposure: number;
  exposureLabel: string;
  scenarioNetIncomeLabel: string;
  recommendationLabel: string;
  evidenceItems: string[];
  memoLabel: string;
  tone: "positive" | "negative" | "neutral";
};

export type ProductCategoryScenarioBreakeven = {
  label: string;
  valueLabel: string;
  detailLabel: string;
  tone: "positive" | "negative" | "neutral" | "warning";
};

export type ProductCategoryScenarioSideOffset = {
  rateLabel: string;
  totalDeltaLabel: string;
  assetDeltaLabel: string;
  liabilityDeltaLabel: string;
  offsetLabel: string;
  conclusionLabel: string;
  assetWidthClassName: string;
  liabilityWidthClassName: string;
  tone: "positive" | "negative" | "neutral";
};

export type ProductCategoryScenarioReviewRow = {
  priorityLabel: string;
  categoryId: string;
  categoryLabel: string;
  sideLabel: string;
  triggerRateLabel: string;
  delta: number;
  deltaLabel: string;
  actionLabel: string;
  tone: "positive" | "negative" | "neutral";
};

export type ProductCategoryScenarioPressureSummary = {
  breakeven: ProductCategoryScenarioBreakeven;
  sideOffset: ProductCategoryScenarioSideOffset;
  reviewRows: ProductCategoryScenarioReviewRow[];
};

export type ProductCategoryScenarioSensitivitySurface = {
  metricStatus: ProductCategoryCandidateMetricStatus;
  baselineGrandTotalLabel: string | null;
  rows: ProductCategoryScenarioSensitivityRow[];
  insightCards: ProductCategoryScenarioInsightCard[];
  riskRows: ProductCategoryScenarioRiskRow[];
  pathPoints: ProductCategoryScenarioPathPoint[];
  actionItems: ProductCategoryScenarioActionItem[];
  heatRows: ProductCategoryScenarioHeatRow[];
  comparisonRows: ProductCategoryScenarioComparisonRow[];
  actionClosureRows: ProductCategoryScenarioActionClosureRow[];
  pressureSummary: ProductCategoryScenarioPressureSummary;
  analysisCopy: string | null;
  emptyCopy: string | null;
};

export function productCategoryRowDeltaYi(
  baselineRowsById: Map<string, ProductCategoryPnlRow>,
  scenarioRow: ProductCategoryPnlRow,
): number | null {
  const baselineRow = baselineRowsById.get(scenarioRow.category_id);
  if (!baselineRow) {
    return null;
  }
  const baselineValue = rawYiNumber(baselineRow.business_net_income);
  const scenarioValue = rawYiNumber(scenarioRow.business_net_income);
  if (baselineValue === null || scenarioValue === null) {
    return null;
  }
  return scenarioValue - baselineValue;
}

function productCategoryScenarioAnalysisCopy(
  worst: ProductCategoryScenarioSensitivityRow | undefined,
  best: ProductCategoryScenarioSensitivityRow | undefined,
): string | null {
  if (
    !worst ||
    !best ||
    worst.grandDelta === null ||
    best.grandDelta === null
  ) {
    return null;
  }
  if (worst.grandDelta < 0) {
    return `FTP 上行时全表净营收承压，最差情景较基线 ${worst.grandDeltaLabel} 亿元。`;
  }
  if (best.grandDelta > 0) {
    return `四档 FTP 情景均未低于基线，最佳情景较基线 ${best.grandDeltaLabel} 亿元。`;
  }
  return "四档 FTP 情景围绕基线窄幅波动，建议结合产品行变动继续复核。";
}

type ProductCategoryComparableScenarioRow =
  ProductCategoryScenarioSensitivityRow & {
    grandNetIncome: number;
    grandDelta: number;
  };

const EMPTY_PRODUCT_CATEGORY_SCENARIO_PRESSURE_SUMMARY: ProductCategoryScenarioPressureSummary =
  {
    breakeven: {
      label: "临界 FTP",
      valueLabel: EM_DASH,
      detailLabel: "待加载可比较情景后估算；此处仅做线性插值辅助判断。",
      tone: "neutral",
    },
    sideOffset: {
      rateLabel: EM_DASH,
      totalDeltaLabel: EM_DASH,
      assetDeltaLabel: EM_DASH,
      liabilityDeltaLabel: EM_DASH,
      offsetLabel: EM_DASH,
      conclusionLabel: "待加载情景矩阵后拆分资产端与负债端冲抵关系。",
      assetWidthClassName: "is-width-0",
      liabilityWidthClassName: "is-width-0",
      tone: "neutral",
    },
    reviewRows: [],
  };

function hasComparableScenarioGrandTotal(
  row: ProductCategoryScenarioSensitivityRow,
): row is ProductCategoryComparableScenarioRow {
  return row.grandNetIncome !== null && row.grandDelta !== null;
}

function productCategoryBucketPct(value: number): 0 | 25 | 50 | 75 | 100 {
  if (value <= 12.5) {
    return 0;
  }
  if (value <= 37.5) {
    return 25;
  }
  if (value <= 62.5) {
    return 50;
  }
  if (value <= 87.5) {
    return 75;
  }
  return 100;
}

function selectProductCategoryScenarioInsightCards(
  rows: ProductCategoryScenarioSensitivityRow[],
): ProductCategoryScenarioInsightCard[] {
  const comparableRows = rows.filter(hasComparableScenarioGrandTotal);
  if (comparableRows.length === 0) {
    return [];
  }
  const sortedByGrand = [...comparableRows].sort(
    (left, right) => right.grandNetIncome - left.grandNetIncome,
  );
  const best = sortedByGrand[0];
  const worst = sortedByGrand[sortedByGrand.length - 1];
  const cards: ProductCategoryScenarioInsightCard[] = [
    {
      key: "best_case",
      label: "最佳情景",
      valueLabel: `${best.rateLabel} / ${best.grandNetIncomeLabel}`,
      detailLabel: `较基线 ${best.grandDeltaLabel} 亿元`,
      tone: productCategoryDeltaTone(best.grandDelta),
    },
    {
      key: "worst_case",
      label: "最差情景",
      valueLabel: `${worst.rateLabel} / ${worst.grandNetIncomeLabel}`,
      detailLabel: `较基线 ${worst.grandDeltaLabel} 亿元`,
      tone: productCategoryDeltaTone(worst.grandDelta),
    },
  ];
  const range = Number((best.grandNetIncome - worst.grandNetIncome).toFixed(2));
  cards.push({
    key: "range",
    label: "情景区间",
    valueLabel: productCategoryYiNumberLabel(range),
    detailLabel: `${best.grandNetIncomeLabel} - ${worst.grandNetIncomeLabel} 亿元`,
    tone: "neutral",
  });
  const rateSpanBp = (worst.ratePct - best.ratePct) * 100;
  const slope =
    rateSpanBp === 0
      ? null
      : Number(
          ((worst.grandNetIncome - best.grandNetIncome) / rateSpanBp).toFixed(
            2,
          ),
        );
  cards.push({
    key: "ftp_slope",
    label: "FTP 斜率",
    valueLabel: productCategoryYiNumberLabel(slope),
    detailLabel: "每 1 bp 约影响净营收",
    tone: productCategoryDeltaTone(slope),
  });
  return cards;
}

function selectProductCategoryScenarioRiskRows(
  rows: ProductCategoryScenarioSensitivityRow[],
): ProductCategoryScenarioRiskRow[] {
  const byCategory = new Map<
    string,
    {
      categoryLabel: string;
      count: number;
      worstRateLabel: string;
      worstDelta: number | null;
    }
  >();
  for (const row of rows) {
    if (row.topMoverCategoryLabel === EM_DASH || row.topMoverDelta === null) {
      continue;
    }
    const current = byCategory.get(row.topMoverCategoryLabel);
    if (!current) {
      byCategory.set(row.topMoverCategoryLabel, {
        categoryLabel: row.topMoverCategoryLabel,
        count: 1,
        worstRateLabel: row.rateLabel,
        worstDelta: row.topMoverDelta,
      });
      continue;
    }
    current.count += 1;
    if (
      current.worstDelta === null ||
      Math.abs(row.topMoverDelta) > Math.abs(current.worstDelta)
    ) {
      current.worstRateLabel = row.rateLabel;
      current.worstDelta = row.topMoverDelta;
    }
  }
  return [...byCategory.values()]
    .sort((left, right) => {
      if (right.count !== left.count) {
        return right.count - left.count;
      }
      return Math.abs(right.worstDelta ?? 0) - Math.abs(left.worstDelta ?? 0);
    })
    .slice(0, 3)
    .map((row) => ({
      categoryLabel: row.categoryLabel,
      worstRateLabel: row.worstRateLabel,
      worstDelta: row.worstDelta,
      worstDeltaLabel: formatSignedProductCategoryYi(row.worstDelta),
      occurrenceLabel: `${row.count} 个情景触发最大变动`,
      tone: productCategoryDeltaTone(row.worstDelta),
    }));
}

function selectProductCategoryScenarioPathPoints(
  rows: ProductCategoryScenarioSensitivityRow[],
): ProductCategoryScenarioPathPoint[] {
  const comparableRows = rows.filter(hasComparableScenarioGrandTotal);
  if (comparableRows.length === 0) {
    return [];
  }
  const minRate = Math.min(...comparableRows.map((row) => row.ratePct));
  const maxRate = Math.max(...comparableRows.map((row) => row.ratePct));
  const span = maxRate - minRate;
  return comparableRows.map((row) => ({
    rateLabel: row.rateLabel,
    grandNetIncomeLabel: row.grandNetIncomeLabel,
    grandDeltaLabel: row.grandDeltaLabel,
    positionPct:
      span === 0 ? 50 : Math.round(((row.ratePct - minRate) / span) * 100),
    positionClassName: `is-position-${productCategoryBucketPct(
      span === 0 ? 50 : Math.round(((row.ratePct - minRate) / span) * 100),
    )}`,
    tone: row.tone,
  }));
}

function selectProductCategoryScenarioActionItems(input: {
  best?: ProductCategoryComparableScenarioRow;
  worst?: ProductCategoryComparableScenarioRow;
  riskRows: ProductCategoryScenarioRiskRow[];
}): ProductCategoryScenarioActionItem[] {
  const items: ProductCategoryScenarioActionItem[] = [];
  if (
    input.worst?.grandDelta !== null &&
    input.worst?.grandDelta !== undefined
  ) {
    const absoluteDelta = Math.abs(input.worst.grandDelta).toFixed(2);
    items.push({
      title:
        input.worst.grandDelta < 0 ? "锁定下行情景敞口" : "确认上行情景弹性",
      valueLabel: input.worst.grandDeltaLabel,
      detailLabel: `${input.worst.rateLabel} 情景较基线${input.worst.grandDelta < 0 ? "少" : "多"} ${absoluteDelta} 亿元`,
      tone: productCategoryDeltaTone(input.worst.grandDelta),
    });
  }
  const topRisk = input.riskRows[0];
  if (topRisk) {
    items.push({
      title: `优先复核 ${topRisk.categoryLabel}`,
      valueLabel: topRisk.worstDeltaLabel,
      detailLabel: `最大产品行变动出现在 ${topRisk.worstRateLabel}`,
      tone: topRisk.tone,
    });
  }
  if (
    input.best &&
    input.worst &&
    input.best.grandNetIncome !== input.worst.grandNetIncome
  ) {
    const range = Number(
      (input.best.grandNetIncome - input.worst.grandNetIncome).toFixed(2),
    );
    items.push({
      title: "设置情景监控阈值",
      valueLabel: productCategoryYiNumberLabel(range),
      detailLabel: "覆盖最佳到最差情景净营收区间",
      tone: "neutral",
    });
  }
  return items.slice(0, 3);
}

function selectProductCategoryScenarioHeatRows(input: {
  baselineRowsById: Map<string, ProductCategoryPnlRow>;
  scenarios: ProductCategoryPnlPayload[];
}): ProductCategoryScenarioHeatRow[] {
  const exposures = new Map<
    string,
    { categoryLabel: string; exposure: number }
  >();
  for (const scenario of input.scenarios) {
    for (const row of leafProductCategoryRows(scenario.rows)) {
      const delta = productCategoryRowDeltaYi(input.baselineRowsById, row);
      if (delta === null || delta === 0) {
        continue;
      }
      const current = exposures.get(row.category_id);
      if (!current || Math.abs(delta) > Math.abs(current.exposure)) {
        exposures.set(row.category_id, {
          categoryLabel: row.category_name || row.category_id,
          exposure: delta,
        });
      }
    }
  }
  const sorted = [...exposures.values()]
    .sort((left, right) => Math.abs(right.exposure) - Math.abs(left.exposure))
    .slice(0, 4);
  const maxAbs = Math.max(...sorted.map((row) => Math.abs(row.exposure)), 0);
  return sorted.map((row) => ({
    categoryLabel: row.categoryLabel,
    exposureLabel: formatSignedProductCategoryYi(row.exposure),
    widthPct:
      maxAbs === 0 ? 0 : Math.round((Math.abs(row.exposure) / maxAbs) * 100),
    widthClassName: `is-width-${productCategoryBucketPct(
      maxAbs === 0 ? 0 : Math.round((Math.abs(row.exposure) / maxAbs) * 100),
    )}`,
    tone: productCategoryDeltaTone(row.exposure),
  }));
}

function selectProductCategoryScenarioComparisonRows(input: {
  baselineRowsById: Map<string, ProductCategoryPnlRow>;
  scenarios: ProductCategoryPnlPayload[];
}): ProductCategoryScenarioComparisonRow[] {
  const scenarioRowsByCategory = new Map<
    string,
    {
      baselineRow: ProductCategoryPnlRow;
      scenarioRows: Array<{ rate: string; row: ProductCategoryPnlRow }>;
    }
  >();
  for (const scenario of input.scenarios) {
    const scenarioRate = scenario.scenario_rate_pct;
    if (scenarioRate === null || scenarioRate === undefined) {
      continue;
    }
    for (const scenarioRow of leafProductCategoryRows(scenario.rows)) {
      const baselineRow = input.baselineRowsById.get(scenarioRow.category_id);
      if (!baselineRow) {
        continue;
      }
      const current = scenarioRowsByCategory.get(scenarioRow.category_id);
      if (current) {
        current.scenarioRows.push({
          rate: String(scenarioRate),
          row: scenarioRow,
        });
      } else {
        scenarioRowsByCategory.set(scenarioRow.category_id, {
          baselineRow,
          scenarioRows: [{ rate: String(scenarioRate), row: scenarioRow }],
        });
      }
    }
  }
  const rows: Array<ProductCategoryScenarioComparisonRow | null> = [
    ...scenarioRowsByCategory.entries(),
  ].map(([categoryId, entry]) => {
    const baselineNetIncome = rawYiNumber(entry.baselineRow.business_net_income);
    const cells = entry.scenarioRows
      .map((scenarioEntry) => {
        const rate = scenarioEntry.rate;
        const ratePct = Number(rate);
        const netIncome = rawYiNumber(scenarioEntry.row.business_net_income);
        const delta = productCategoryRowDeltaYi(
          input.baselineRowsById,
          scenarioEntry.row,
        );
        return {
          rate: String(rate),
          ratePct,
          rateLabel: `${ratePct.toFixed(2)}%`,
          netIncome,
          netIncomeLabel: productCategoryYiNumberLabel(netIncome),
          delta,
          deltaLabel: formatSignedProductCategoryYi(delta),
          tone: productCategoryDeltaTone(delta),
        };
      })
      .filter(
        (cell): cell is ProductCategoryScenarioComparisonCell => cell !== null,
      )
      .sort((left, right) => left.ratePct - right.ratePct);
    const comparableCells = cells.filter(
      (
        cell,
      ): cell is ProductCategoryScenarioComparisonCell & {
        delta: number;
        netIncome: number;
      } => cell.delta !== null && cell.netIncome !== null,
    );
    if (comparableCells.length === 0) {
      return null;
    }
    const best = [...comparableCells].sort(
      (left, right) => right.delta - left.delta,
    )[0];
    const worst = [...comparableCells].sort(
      (left, right) => left.delta - right.delta,
    )[0];
    if (!best || !worst) {
      return null;
    }
    const minNetIncome = Math.min(
      ...comparableCells.map((cell) => cell.netIncome),
    );
    const maxNetIncome = Math.max(
      ...comparableCells.map((cell) => cell.netIncome),
    );
    const range = Number((maxNetIncome - minNetIncome).toFixed(2));
    const maxAbsDelta = Math.max(
      ...comparableCells.map((cell) => Math.abs(cell.delta)),
      0,
    );
    return {
      categoryId,
      categoryLabel: entry.baselineRow.category_name || categoryId,
      sideLabel: productCategoryScenarioSideLabel(entry.baselineRow.side),
      baselineNetIncome,
      baselineNetIncomeLabel: productCategoryYiNumberLabel(baselineNetIncome),
      cells,
      bestRateLabel: best.rateLabel,
      bestDelta: best.delta,
      bestDeltaLabel: formatSignedProductCategoryYi(best.delta),
      worstRateLabel: worst.rateLabel,
      worstDelta: worst.delta,
      worstDeltaLabel: formatSignedProductCategoryYi(worst.delta),
      range,
      rangeLabel: productCategoryYiNumberLabel(range),
      maxAbsDelta,
      tone: productCategoryDeltaTone(worst.delta),
    };
  });
  return rows
    .filter((row): row is ProductCategoryScenarioComparisonRow => row !== null)
    .sort((left, right) => right.maxAbsDelta - left.maxAbsDelta);
}

function productCategoryScenarioClosureRecommendation(
  row: ProductCategoryScenarioComparisonRow,
): string {
  if (row.sideLabel === "负债端") {
    return "复核负债成本、FTP 曲线与定价传导";
  }
  if (row.worstDelta !== null && row.worstDelta <= -0.5) {
    return "压降 FTP 敞口并复核规模、收益率输入";
  }
  return "复核 FTP 敞口、规模与收益率输入";
}

function selectProductCategoryScenarioActionClosureRows(
  comparisonRows: ProductCategoryScenarioComparisonRow[],
): ProductCategoryScenarioActionClosureRow[] {
  return comparisonRows
    .filter((row) => row.worstDelta !== null && row.worstDelta < 0)
    .sort(
      (left, right) =>
        Math.abs(right.worstDelta ?? 0) - Math.abs(left.worstDelta ?? 0),
    )
    .slice(0, 4)
    .map((row, index) => {
      const worstCell = row.cells.find(
        (cell) => cell.rateLabel === row.worstRateLabel,
      );
      const scenarioNetIncomeLabel = worstCell?.netIncomeLabel ?? EM_DASH;
      const recommendationLabel =
        productCategoryScenarioClosureRecommendation(row);
      return {
        priorityLabel: `动作 ${index + 1}`,
        categoryId: row.categoryId,
        categoryLabel: row.categoryLabel,
        sideLabel: row.sideLabel,
        triggerRateLabel: row.worstRateLabel,
        exposure: row.worstDelta ?? 0,
        exposureLabel: row.worstDeltaLabel,
        scenarioNetIncomeLabel,
        recommendationLabel,
        evidenceItems: [
          `正式基线净营收 ${row.baselineNetIncomeLabel} 亿元`,
          `${row.worstRateLabel} 情景净营收 ${scenarioNetIncomeLabel} 亿元`,
          `较基线 ${row.worstDeltaLabel} 亿元`,
        ],
        memoLabel: `${row.categoryLabel}在 ${row.worstRateLabel} 情景较基线 ${row.worstDeltaLabel} 亿元；${recommendationLabel}。`,
        tone: row.tone,
      };
    });
}

function productCategoryScenarioBaselineRelation(delta: number): string {
  if (delta > 0) {
    return `高于基线 ${formatSignedProductCategoryYi(delta)}`;
  }
  if (delta < 0) {
    return `低于基线 ${formatSignedProductCategoryYi(delta)}`;
  }
  return "与基线持平 0.00";
}

function selectProductCategoryScenarioBreakeven(
  comparableRows: ProductCategoryComparableScenarioRow[],
): ProductCategoryScenarioBreakeven {
  if (comparableRows.length === 0) {
    return EMPTY_PRODUCT_CATEGORY_SCENARIO_PRESSURE_SUMMARY.breakeven;
  }
  const sortedByRate = [...comparableRows].sort(
    (left, right) => left.ratePct - right.ratePct,
  );
  const exact = sortedByRate.find((row) => row.grandDelta === 0);
  if (exact) {
    return {
      label: "临界 FTP",
      valueLabel: `约 ${exact.ratePct.toFixed(2)}%`,
      detailLabel: `${exact.rateLabel} 情景与正式基线持平；此处仅做情景辅助判断。`,
      tone: "neutral",
    };
  }
  for (let index = 1; index < sortedByRate.length; index += 1) {
    const left = sortedByRate[index - 1];
    const right = sortedByRate[index];
    if (!left || !right || left.grandDelta * right.grandDelta > 0) {
      continue;
    }
    const deltaSpan = right.grandDelta - left.grandDelta;
    if (deltaSpan === 0) {
      continue;
    }
    const rate =
      left.ratePct +
      ((0 - left.grandDelta) / deltaSpan) * (right.ratePct - left.ratePct);
    return {
      label: "临界 FTP",
      valueLabel: `约 ${rate.toFixed(2)}%`,
      detailLabel: `线性插值：${left.rateLabel} ${productCategoryScenarioBaselineRelation(
        left.grandDelta,
      )}，${right.rateLabel} ${productCategoryScenarioBaselineRelation(right.grandDelta)}`,
      tone: "warning",
    };
  }
  const best = [...sortedByRate].sort(
    (left, right) => right.grandDelta - left.grandDelta,
  )[0];
  const worst = [...sortedByRate].sort(
    (left, right) => left.grandDelta - right.grandDelta,
  )[0];
  if (worst && worst.grandDelta > 0) {
    return {
      label: "临界 FTP",
      valueLabel: `高于 ${sortedByRate[sortedByRate.length - 1]?.rateLabel ?? EM_DASH}`,
      detailLabel: `已加载情景均高于基线，最低差额 ${worst.grandDeltaLabel}；未在当前区间触发临界点。`,
      tone: "positive",
    };
  }
  if (best && best.grandDelta < 0) {
    return {
      label: "临界 FTP",
      valueLabel: `低于 ${sortedByRate[0]?.rateLabel ?? EM_DASH}`,
      detailLabel: `已加载情景均低于基线，最高差额 ${best.grandDeltaLabel}；需复核情景输入或基线安全垫。`,
      tone: "negative",
    };
  }
  return EMPTY_PRODUCT_CATEGORY_SCENARIO_PRESSURE_SUMMARY.breakeven;
}

function selectProductCategoryScenarioSideOffset(
  worst: ProductCategoryComparableScenarioRow | undefined,
): ProductCategoryScenarioSideOffset {
  if (!worst || worst.assetDelta === null || worst.liabilityDelta === null) {
    return EMPTY_PRODUCT_CATEGORY_SCENARIO_PRESSURE_SUMMARY.sideOffset;
  }
  const totalAbs = Math.abs(worst.assetDelta) + Math.abs(worst.liabilityDelta);
  const assetWidth =
    totalAbs === 0
      ? 0
      : Math.round((Math.abs(worst.assetDelta) / totalAbs) * 100);
  const liabilityWidth =
    totalAbs === 0
      ? 0
      : Math.round((Math.abs(worst.liabilityDelta) / totalAbs) * 100);
  const hasOffset = worst.assetDelta * worst.liabilityDelta < 0;
  const offset = hasOffset
    ? Math.min(Math.abs(worst.assetDelta), Math.abs(worst.liabilityDelta))
    : 0;
  let conclusionLabel = "资产端与负债端变化较小，当前情景未形成显著冲抵。";
  if (hasOffset) {
    conclusionLabel = `资产端与负债端形成 ${productCategoryYiNumberLabel(
      offset,
    )} 亿元冲抵，净影响 ${worst.grandDeltaLabel}。`;
  } else if (worst.grandDelta < 0) {
    conclusionLabel = "资产端与负债端同向承压，未形成冲抵。";
  } else if (worst.grandDelta > 0) {
    conclusionLabel = "资产端与负债端同向改善，未形成冲抵。";
  }
  return {
    rateLabel: worst.rateLabel,
    totalDeltaLabel: worst.grandDeltaLabel,
    assetDeltaLabel: formatSignedProductCategoryYi(worst.assetDelta),
    liabilityDeltaLabel: formatSignedProductCategoryYi(worst.liabilityDelta),
    offsetLabel: productCategoryYiNumberLabel(offset),
    conclusionLabel,
    assetWidthClassName: `is-width-${productCategoryBucketPct(assetWidth)}`,
    liabilityWidthClassName: `is-width-${productCategoryBucketPct(liabilityWidth)}`,
    tone: productCategoryDeltaTone(worst.grandDelta),
  };
}

export function productCategoryScenarioSideLabel(side: string): string {
  if (side === "asset") {
    return "资产端";
  }
  if (side === "liability") {
    return "负债端";
  }
  return side || EM_DASH;
}

function productCategoryScenarioReviewAction(
  tone: "positive" | "negative" | "neutral",
): string {
  if (tone === "negative") {
    return "复核 FTP 敞口、规模与收益率输入";
  }
  if (tone === "positive") {
    return "确认情景收益改善来源可持续";
  }
  return "核对情景输入与产品行映射";
}

function selectProductCategoryScenarioReviewRows(input: {
  baselineRowsById: Map<string, ProductCategoryPnlRow>;
  scenarios: ProductCategoryPnlPayload[];
}): ProductCategoryScenarioReviewRow[] {
  const reviewByCategory = new Map<
    string,
    {
      categoryId: string;
      categoryLabel: string;
      sideLabel: string;
      triggerRateLabel: string;
      delta: number;
    }
  >();
  for (const scenario of input.scenarios) {
    const scenarioRate = decimalNumber(scenario.scenario_rate_pct);
    const triggerRateLabel =
      scenarioRate === null ? EM_DASH : `${scenarioRate.toFixed(2)}%`;
    for (const row of leafProductCategoryRows(scenario.rows)) {
      const delta = productCategoryRowDeltaYi(input.baselineRowsById, row);
      if (delta === null || delta === 0) {
        continue;
      }
      const existing = reviewByCategory.get(row.category_id);
      if (!existing || Math.abs(delta) > Math.abs(existing.delta)) {
        reviewByCategory.set(row.category_id, {
          categoryId: row.category_id,
          categoryLabel: row.category_name || row.category_id,
          sideLabel: productCategoryScenarioSideLabel(row.side),
          triggerRateLabel,
          delta,
        });
      }
    }
  }
  return [...reviewByCategory.values()]
    .sort((left, right) => Math.abs(right.delta) - Math.abs(left.delta))
    .slice(0, 3)
    .map((row, index) => {
      const tone = productCategoryDeltaTone(row.delta);
      return {
        priorityLabel: `复核 ${index + 1}`,
        categoryId: row.categoryId,
        categoryLabel: row.categoryLabel,
        sideLabel: row.sideLabel,
        triggerRateLabel: row.triggerRateLabel,
        delta: row.delta,
        deltaLabel: formatSignedProductCategoryYi(row.delta),
        actionLabel: productCategoryScenarioReviewAction(tone),
        tone,
      };
    });
}

function selectProductCategoryScenarioPressureSummary(input: {
  baselineRowsById: Map<string, ProductCategoryPnlRow>;
  comparableRows: ProductCategoryComparableScenarioRow[];
  scenarios: ProductCategoryPnlPayload[];
  worst?: ProductCategoryComparableScenarioRow;
}): ProductCategoryScenarioPressureSummary {
  return {
    breakeven: selectProductCategoryScenarioBreakeven(input.comparableRows),
    sideOffset: selectProductCategoryScenarioSideOffset(input.worst),
    reviewRows: selectProductCategoryScenarioReviewRows({
      baselineRowsById: input.baselineRowsById,
      scenarios: input.scenarios,
    }),
  };
}

export function selectProductCategoryScenarioSensitivitySurface(input: {
  baseline?: ProductCategoryPnlPayload | null;
  scenarios: ProductCategoryPnlPayload[];
}): ProductCategoryScenarioSensitivitySurface {
  if (!input.baseline || input.scenarios.length === 0) {
    return {
      metricStatus: PRODUCT_CATEGORY_CANDIDATE_METRIC_STATUS,
      baselineGrandTotalLabel: input.baseline
        ? formatProductCategoryValue(
            input.baseline.grand_total.business_net_income,
          )
        : null,
      rows: [],
      insightCards: [],
      riskRows: [],
      pathPoints: [],
      actionItems: [],
      heatRows: [],
      comparisonRows: [],
      actionClosureRows: [],
      pressureSummary: EMPTY_PRODUCT_CATEGORY_SCENARIO_PRESSURE_SUMMARY,
      analysisCopy: null,
      emptyCopy: "当前尚未返回可比较的 FTP 情景结果。",
    };
  }
  const baselineRowsById = new Map(
    input.baseline.rows.map((row) => [row.category_id, row]),
  );
  const baselineAssetTotal = rawYiNumber(
    input.baseline.asset_total.business_net_income,
  );
  const baselineLiabilityTotal = rawYiNumber(
    input.baseline.liability_total.business_net_income,
  );
  const baselineGrandTotal = rawYiNumber(
    input.baseline.grand_total.business_net_income,
  );
  const rows: ProductCategoryScenarioSensitivityRow[] = [];
  for (const scenario of input.scenarios) {
    const scenarioRate = scenario.scenario_rate_pct;
    if (scenarioRate === null || scenarioRate === undefined) {
      continue;
    }
    const ratePct = Number(scenarioRate);
    const assetValue = rawYiNumber(scenario.asset_total.business_net_income);
    const liabilityValue = rawYiNumber(
      scenario.liability_total.business_net_income,
    );
    const grandValue = rawYiNumber(scenario.grand_total.business_net_income);
    const assetDelta =
      assetValue === null || baselineAssetTotal === null
        ? null
        : assetValue - baselineAssetTotal;
    const liabilityDelta =
      liabilityValue === null || baselineLiabilityTotal === null
        ? null
        : liabilityValue - baselineLiabilityTotal;
    const grandDelta =
      grandValue === null || baselineGrandTotal === null
        ? null
        : grandValue - baselineGrandTotal;
    const topMover = leafProductCategoryRows(scenario.rows)
      .map((row) => ({
        row,
        delta: productCategoryRowDeltaYi(baselineRowsById, row),
      }))
      .filter(
        (item): item is { row: ProductCategoryPnlRow; delta: number } =>
          item.delta !== null,
      )
      .sort((left, right) => Math.abs(right.delta) - Math.abs(left.delta))[0];
    rows.push({
      rate: String(scenarioRate),
      ratePct,
      rateLabel: `${ratePct.toFixed(2)}%`,
      assetDelta,
      assetNetIncomeLabel: productCategoryYiNumberLabel(assetValue),
      assetDeltaLabel: formatSignedProductCategoryYi(assetDelta),
      liabilityDelta,
      liabilityNetIncomeLabel: productCategoryYiNumberLabel(liabilityValue),
      liabilityDeltaLabel: formatSignedProductCategoryYi(liabilityDelta),
      grandNetIncome: grandValue,
      grandDelta,
      grandNetIncomeLabel: productCategoryYiNumberLabel(grandValue),
      grandDeltaLabel: formatSignedProductCategoryYi(grandDelta),
      topMoverCategoryLabel:
        topMover?.row.category_name || topMover?.row.category_id || EM_DASH,
      topMoverDelta: topMover?.delta ?? null,
      topMoverDeltaLabel: formatSignedProductCategoryYi(
        topMover?.delta ?? null,
      ),
      tone: productCategoryDeltaTone(grandDelta),
    });
  }
  rows.sort((left, right) => Number(left.rate) - Number(right.rate));
  const comparableRows = rows.filter(hasComparableScenarioGrandTotal);
  const sortedByGrand = [...comparableRows].sort(
    (left, right) => right.grandNetIncome - left.grandNetIncome,
  );
  const best = sortedByGrand[0];
  const worst = sortedByGrand[sortedByGrand.length - 1];
  const riskRows = selectProductCategoryScenarioRiskRows(rows);
  const comparisonRows = selectProductCategoryScenarioComparisonRows({
    baselineRowsById,
    scenarios: input.scenarios,
  });
  return {
    metricStatus: PRODUCT_CATEGORY_CANDIDATE_METRIC_STATUS,
    baselineGrandTotalLabel: formatProductCategoryValue(
      input.baseline.grand_total.business_net_income,
    ),
    rows,
    insightCards: selectProductCategoryScenarioInsightCards(rows),
    riskRows,
    pathPoints: selectProductCategoryScenarioPathPoints(rows),
    actionItems: selectProductCategoryScenarioActionItems({
      best,
      worst,
      riskRows,
    }),
    heatRows: selectProductCategoryScenarioHeatRows({
      baselineRowsById,
      scenarios: input.scenarios,
    }),
    comparisonRows,
    actionClosureRows:
      selectProductCategoryScenarioActionClosureRows(comparisonRows),
    pressureSummary: selectProductCategoryScenarioPressureSummary({
      baselineRowsById,
      comparableRows,
      scenarios: input.scenarios,
      worst,
    }),
    analysisCopy: productCategoryScenarioAnalysisCopy(worst, best),
    emptyCopy: rows.length === 0 ? "当前尚未返回可比较的 FTP 情景结果。" : null,
  };
}
