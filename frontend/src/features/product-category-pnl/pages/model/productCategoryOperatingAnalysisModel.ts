import type {
  ProductCategoryAttributionRow,
  ProductCategoryPnlRow,
  ProductCategoryAttributionPayload,
} from "../../../../api/contracts";
import type { ProductCategoryOperatingActionKind } from "./productCategoryOperatingBacktestOutcomeModel";
import type { ProductCategoryCandidateMetricStatus } from "./productCategoryPnlModelInternals";
import {
  leafProductCategoryRowsInternal as leafProductCategoryRows,
  yiNumberInternal as yiNumber,
  productCategorySideLabelInternal as productCategorySideLabel,
  productCategoryPercentLabelInternal as productCategoryPercentLabel,
  formatSignedProductCategoryYiInternal as formatSignedProductCategoryYi,
  percentNumberInternal as percentNumber,
  medianProductCategoryNumberInternal as medianProductCategoryNumber,
  parentProductCategoryIdsInternal as parentProductCategoryIds,
  PRODUCT_CATEGORY_CANDIDATE_METRIC_STATUS,
} from "./productCategoryPnlModelInternals";
import { formatProductCategoryValue } from "./productCategoryPnlDisplayModel";
import { EM_DASH } from "../../../../utils/format";

export type ProductCategoryOperatingContributionRow = {
  categoryId: string;
  categoryLabel: string;
  sideLabel: string;
  netIncome: number;
  netIncomeLabel: string;
  contributionPct: number | null;
  contributionLabel: string;
  tone: "positive" | "negative";
};

export type ProductCategoryOperatingMovementRow = {
  categoryId: string;
  categoryLabel: string;
  delta: number;
  deltaLabel: string;
  leadingDriverKey: keyof Pick<
    ProductCategoryAttributionRow["effects"],
    | "day_effect"
    | "scale_effect"
    | "rate_effect"
    | "ftp_effect"
    | "direct_effect"
    | "unexplained_effect"
  >;
  leadingDriverLabel: string;
  leadingDriverValue: number;
  leadingDriverValueLabel: string;
  closureErrorLabel: string;
};

export type ProductCategoryOperatingQuadrant =
  | "core_profit_pool"
  | "scale_efficiency_watch"
  | "selective_growth"
  | "shrink_or_reprice";

export type ProductCategoryOperatingQuadrantRow = {
  categoryId: string;
  categoryLabel: string;
  scale: number;
  scaleLabel: string;
  yieldPct: number;
  yieldLabel: string;
  netIncome: number | null;
  netIncomeLabel: string;
  quadrant: ProductCategoryOperatingQuadrant;
  quadrantLabel: string;
};

export type ProductCategoryOperatingActionQueueRow = {
  priorityLabel: string;
  categoryId: string;
  categoryLabel: string;
  actionKind: ProductCategoryOperatingActionKind;
  actionLabel: string;
  triggerLabel: string;
  primaryMetricLabel: string;
  evidenceItems: string[];
  tone: "positive" | "negative" | "neutral";
};

export type ProductCategoryOperatingAnalysisSurface = {
  metricStatus: ProductCategoryCandidateMetricStatus;
  contribution: {
    grandTotalLabel: string | null;
    profitRows: ProductCategoryOperatingContributionRow[];
    pressureRows: ProductCategoryOperatingContributionRow[];
    emptyCopy: string | null;
  };
  movement: {
    rows: ProductCategoryOperatingMovementRow[];
    emptyCopy: string | null;
  };
  quadrant: {
    scaleBenchmark: number | null;
    yieldBenchmark: number | null;
    scaleBenchmarkLabel: string;
    yieldBenchmarkLabel: string;
    rows: ProductCategoryOperatingQuadrantRow[];
    emptyCopy: string | null;
  };
  actionQueue: {
    rows: ProductCategoryOperatingActionQueueRow[];
    emptyCopy: string | null;
  };
};

const PRODUCT_CATEGORY_OPERATING_DRIVER_LABELS = {
  scale_effect: "规模因素",
  rate_effect: "利率因素",
  day_effect: "天数因素",
  ftp_effect: "FTP因素",
  direct_effect: "直接因素",
  unexplained_effect: "未解释",
} as const;

const PRODUCT_CATEGORY_OPERATING_DRIVER_KEYS = Object.keys(
  PRODUCT_CATEGORY_OPERATING_DRIVER_LABELS,
) as Array<keyof typeof PRODUCT_CATEGORY_OPERATING_DRIVER_LABELS>;

function productCategoryQuadrantLabel(
  quadrant: ProductCategoryOperatingQuadrant,
): string {
  if (quadrant === "core_profit_pool") {
    return "核心利润池";
  }
  if (quadrant === "scale_efficiency_watch") {
    return "高规模低收益";
  }
  if (quadrant === "selective_growth") {
    return "低规模高收益";
  }
  return "低规模低收益";
}

function productCategoryQuadrantForPoint(input: {
  scale: number;
  yieldPct: number;
  scaleBenchmark: number;
  yieldBenchmark: number;
}): ProductCategoryOperatingQuadrant {
  const highScale = input.scale >= input.scaleBenchmark;
  const highYield = input.yieldPct > input.yieldBenchmark;
  if (highScale && highYield) {
    return "core_profit_pool";
  }
  if (highScale) {
    return "scale_efficiency_watch";
  }
  if (highYield) {
    return "selective_growth";
  }
  return "shrink_or_reprice";
}

function selectProductCategoryOperatingContribution(input: {
  rows: ProductCategoryPnlRow[];
  grandTotal?: Pick<ProductCategoryPnlRow, "business_net_income"> | null;
}): ProductCategoryOperatingAnalysisSurface["contribution"] {
  const candidates = leafProductCategoryRows(input.rows)
    .map((row) => {
      const value = yiNumber(row.business_net_income);
      if (value === null || value === 0) {
        return null;
      }
      const grandTotal = yiNumber(input.grandTotal?.business_net_income);
      const denominator =
        grandTotal !== null && grandTotal !== 0 ? Math.abs(grandTotal) : null;
      const contributionPct = denominator
        ? Number(((value / denominator) * 100).toFixed(1))
        : null;
      return {
        categoryId: row.category_id,
        categoryLabel: row.category_name || row.category_id,
        sideLabel: productCategorySideLabel(row.side),
        netIncome: value,
        netIncomeLabel: value.toFixed(2),
        contributionPct,
        contributionLabel: productCategoryPercentLabel(contributionPct),
        tone: value > 0 ? ("positive" as const) : ("negative" as const),
      };
    })
    .filter(
      (row): row is ProductCategoryOperatingContributionRow => row !== null,
    );
  const profitRows = candidates
    .filter((row) => row.netIncome > 0)
    .sort((left, right) => right.netIncome - left.netIncome)
    .slice(0, 5);
  const pressureRows = candidates
    .filter((row) => row.netIncome < 0)
    .sort((left, right) => left.netIncome - right.netIncome)
    .slice(0, 5);
  return {
    grandTotalLabel: input.grandTotal
      ? formatProductCategoryValue(input.grandTotal.business_net_income)
      : null,
    profitRows,
    pressureRows,
    emptyCopy:
      profitRows.length === 0 && pressureRows.length === 0
        ? "当前正式表没有可排序的产品贡献。"
        : null,
  };
}

export function buildProductCategoryOperatingMovementRows(
  attribution: ProductCategoryAttributionPayload | null | undefined,
  parentCategoryIds: Set<string>,
): ProductCategoryOperatingMovementRow[] {
  if (
    !attribution ||
    attribution.compare !== "mom" ||
    attribution.state !== "complete"
  ) {
    return [];
  }
  const rows: ProductCategoryOperatingMovementRow[] = [];
  for (const row of attribution.rows) {
    if (
      row.category_id.endsWith("_total") ||
      row.category_id === "grand_total" ||
      row.category_id === "interest_earning_assets" ||
      parentCategoryIds.has(row.category_id)
    ) {
      continue;
    }
    const delta = yiNumber(row.effects.delta_business_net_income);
    if (delta === null || delta === 0) {
      continue;
    }
    const leadingDriverKey = PRODUCT_CATEGORY_OPERATING_DRIVER_KEYS.reduce(
      (best, key) => {
        const bestValue = Math.abs(yiNumber(row.effects[best]) ?? 0);
        const currentValue = Math.abs(yiNumber(row.effects[key]) ?? 0);
        return currentValue > bestValue ? key : best;
      },
      PRODUCT_CATEGORY_OPERATING_DRIVER_KEYS[0],
    );
    const leadingDriverValue = yiNumber(row.effects[leadingDriverKey]) ?? 0;
    rows.push({
      categoryId: row.category_id,
      categoryLabel: row.category_name || row.category_id,
      delta,
      deltaLabel: formatSignedProductCategoryYi(delta),
      leadingDriverKey,
      leadingDriverLabel:
        PRODUCT_CATEGORY_OPERATING_DRIVER_LABELS[leadingDriverKey],
      leadingDriverValue,
      leadingDriverValueLabel:
        formatSignedProductCategoryYi(leadingDriverValue),
      closureErrorLabel: formatSignedProductCategoryYi(
        yiNumber(row.effects.closure_error),
      ),
    });
  }
  rows.sort((left, right) => Math.abs(right.delta) - Math.abs(left.delta));
  return rows;
}

function selectProductCategoryOperatingMovement(
  attribution: ProductCategoryAttributionPayload | null | undefined,
  parentCategoryIds: Set<string>,
): ProductCategoryOperatingAnalysisSurface["movement"] {
  if (
    !attribution ||
    attribution.compare !== "mom" ||
    attribution.state !== "complete"
  ) {
    return {
      rows: [],
      emptyCopy: "当前缺少可用的月度经营差异归因。",
    };
  }
  const rows = buildProductCategoryOperatingMovementRows(
    attribution,
    parentCategoryIds,
  );
  const topRows = rows.slice(0, 5);
  return {
    rows: topRows,
    emptyCopy: topRows.length === 0 ? "当前归因结果没有显著变动项。" : null,
  };
}

function selectProductCategoryOperatingQuadrant(
  rows: ProductCategoryPnlRow[],
  options: { limit?: number | null } = {},
): ProductCategoryOperatingAnalysisSurface["quadrant"] {
  const candidates = leafProductCategoryRows(rows)
    .map((row) => {
      const scale = yiNumber(row.cnx_scale);
      const yieldPct = percentNumber(row.weighted_yield);
      const netIncome = yiNumber(row.business_net_income);
      if (scale === null || yieldPct === null || scale <= 0) {
        return null;
      }
      return {
        row,
        scale,
        yieldPct,
        netIncome,
        netIncomeLabel: netIncome !== null ? netIncome.toFixed(2) : EM_DASH,
      };
    })
    .filter(
      (
        row,
      ): row is {
        row: ProductCategoryPnlRow;
        scale: number;
        yieldPct: number;
        netIncome: number | null;
        netIncomeLabel: string;
      } => row !== null,
    );
  const scaleBenchmark = medianProductCategoryNumber(
    candidates.map((item) => item.scale),
  );
  const yieldBenchmark = medianProductCategoryNumber(
    candidates.map((item) => item.yieldPct),
  );
  if (scaleBenchmark === null || yieldBenchmark === null) {
    return {
      scaleBenchmark: null,
      yieldBenchmark: null,
      scaleBenchmarkLabel: EM_DASH,
      yieldBenchmarkLabel: EM_DASH,
      rows: [],
      emptyCopy: "当前缺少可用于规模/收益率象限的规模或收益率。",
    };
  }
  const quadrantRows = candidates
    .map((item) => {
      const quadrant = productCategoryQuadrantForPoint({
        scale: item.scale,
        yieldPct: item.yieldPct,
        scaleBenchmark,
        yieldBenchmark,
      });
      return {
        categoryId: item.row.category_id,
        categoryLabel: item.row.category_name || item.row.category_id,
        scale: item.scale,
        scaleLabel: item.scale.toFixed(2),
        yieldPct: item.yieldPct,
        yieldLabel: item.yieldPct.toFixed(2),
        netIncome: item.netIncome,
        netIncomeLabel: item.netIncomeLabel,
        quadrant,
        quadrantLabel: productCategoryQuadrantLabel(quadrant),
      };
    })
    .sort((left, right) => right.scale - left.scale);
  const displayRows =
    options.limit === null
      ? quadrantRows
      : quadrantRows.slice(0, options.limit ?? 12);
  return {
    scaleBenchmark,
    yieldBenchmark,
    scaleBenchmarkLabel: scaleBenchmark.toFixed(2),
    yieldBenchmarkLabel: yieldBenchmark.toFixed(2),
    rows: displayRows,
    emptyCopy:
      displayRows.length === 0
        ? "当前缺少可用于规模/收益率象限的产品行。"
        : null,
  };
}

function productCategoryOperatingActionRow(input: {
  categoryId: string;
  categoryLabel: string;
  actionKind: ProductCategoryOperatingActionKind;
  actionLabel: string;
  triggerLabel: string;
  primaryMetricLabel: string;
  evidenceItems: string[];
  tone: "positive" | "negative" | "neutral";
}): Omit<ProductCategoryOperatingActionQueueRow, "priorityLabel"> {
  return input;
}

export function selectProductCategoryOperatingActionQueue(input: {
  rows: ProductCategoryPnlRow[];
  attribution?: ProductCategoryAttributionPayload | null;
  parentCategoryIds: Set<string>;
}): ProductCategoryOperatingAnalysisSurface["actionQueue"] {
  const leafRows = leafProductCategoryRows(input.rows);
  const actionRows: Array<
    Omit<ProductCategoryOperatingActionQueueRow, "priorityLabel">
  > = [];
  const seenCategoryIds = new Set<string>();
  const movementRows = buildProductCategoryOperatingMovementRows(
    input.attribution,
    input.parentCategoryIds,
  );
  const quadrant = selectProductCategoryOperatingQuadrant(input.rows, {
    limit: null,
  });
  const quadrantByCategoryId = new Map(
    quadrant.rows.map((row) => [row.categoryId, row]),
  );
  const appendActionRow = (
    row: Omit<ProductCategoryOperatingActionQueueRow, "priorityLabel">,
  ) => {
    if (seenCategoryIds.has(row.categoryId)) {
      return;
    }
    seenCategoryIds.add(row.categoryId);
    actionRows.push(row);
  };

  const lowYieldLoss = leafRows
    .map((row) => {
      const netIncome = yiNumber(row.business_net_income);
      const scale = yiNumber(row.cnx_scale);
      const yieldPct = percentNumber(row.weighted_yield);
      const movement = movementRows.find(
        (item) => item.categoryId === row.category_id,
      );
      const quadrantRow = quadrantByCategoryId.get(row.category_id);
      const hasLowYield =
        quadrantRow?.quadrant === "scale_efficiency_watch" ||
        quadrantRow?.quadrant === "shrink_or_reprice";
      if (
        netIncome === null ||
        netIncome >= 0 ||
        yieldPct === null ||
        scale === null ||
        !hasLowYield
      ) {
        return null;
      }
      return { row, netIncome, scale, yieldPct, movement };
    })
    .filter((row): row is NonNullable<typeof row> => row !== null)
    .sort((left, right) => left.netIncome - right.netIncome)[0];

  if (lowYieldLoss) {
    appendActionRow(
      productCategoryOperatingActionRow({
        categoryId: lowYieldLoss.row.category_id,
        categoryLabel:
          lowYieldLoss.row.category_name || lowYieldLoss.row.category_id,
        actionKind: "shrink_or_limit",
        actionLabel: "压降或限额复核",
        triggerLabel: "负贡献叠加收益偏低",
        primaryMetricLabel: lowYieldLoss.netIncome.toFixed(2),
        evidenceItems: [
          `净营收 ${lowYieldLoss.netIncome.toFixed(2)} 亿元`,
          `规模 ${lowYieldLoss.scale.toFixed(2)} 亿元`,
          `收益率 ${lowYieldLoss.yieldPct.toFixed(2)}%`,
          `变动 ${lowYieldLoss.movement?.deltaLabel ?? EM_DASH} 亿元`,
        ],
        tone: "negative",
      }),
    );
  }

  const unexplainedReview = movementRows
    .filter(
      (row) =>
        row.leadingDriverKey === "unexplained_effect" &&
        Math.abs(row.leadingDriverValue) > 0,
    )
    .sort(
      (left, right) =>
        Math.abs(right.leadingDriverValue) - Math.abs(left.leadingDriverValue),
    )[0];

  if (unexplainedReview) {
    appendActionRow(
      productCategoryOperatingActionRow({
        categoryId: unexplainedReview.categoryId,
        categoryLabel: unexplainedReview.categoryLabel,
        actionKind: "review_attribution",
        actionLabel: "归因复核",
        triggerLabel: "未解释差异偏高",
        primaryMetricLabel: unexplainedReview.leadingDriverValueLabel,
        evidenceItems: [
          `未解释 ${unexplainedReview.leadingDriverValueLabel} 亿元`,
          `变动 ${unexplainedReview.deltaLabel} 亿元`,
        ],
        tone: "neutral",
      }),
    );
  }

  const reprice = quadrant.rows.find(
    (row) =>
      row.quadrant === "scale_efficiency_watch" &&
      !seenCategoryIds.has(row.categoryId),
  );
  if (reprice) {
    appendActionRow(
      productCategoryOperatingActionRow({
        categoryId: reprice.categoryId,
        categoryLabel: reprice.categoryLabel,
        actionKind: "reprice_or_improve",
        actionLabel: "重定价/提效",
        triggerLabel: "高规模低收益",
        primaryMetricLabel: `${reprice.yieldLabel}%`,
        evidenceItems: [
          `规模 ${reprice.scaleLabel} 亿元`,
          `收益率 ${reprice.yieldLabel}%`,
          `净营收 ${reprice.netIncomeLabel} 亿元`,
        ],
        tone: "negative",
      }),
    );
  }

  const selectiveGrowth = quadrant.rows.find(
    (row) =>
      row.quadrant === "selective_growth" &&
      row.netIncome !== null &&
      row.netIncome > 0 &&
      !seenCategoryIds.has(row.categoryId),
  );
  if (selectiveGrowth) {
    appendActionRow(
      productCategoryOperatingActionRow({
        categoryId: selectiveGrowth.categoryId,
        categoryLabel: selectiveGrowth.categoryLabel,
        actionKind: "selective_growth",
        actionLabel: "选择性扩张",
        triggerLabel: "低规模高收益",
        primaryMetricLabel: `${selectiveGrowth.yieldLabel}%`,
        evidenceItems: [
          `规模 ${selectiveGrowth.scaleLabel} 亿元`,
          `收益率 ${selectiveGrowth.yieldLabel}%`,
          `净营收 ${selectiveGrowth.netIncomeLabel} 亿元`,
        ],
        tone: "positive",
      }),
    );
  }

  const rows = actionRows.map((row, index) => ({
    priorityLabel: `P${index + 1}`,
    ...row,
  }));
  return {
    rows,
    emptyCopy:
      rows.length === 0 ? "当前没有需要进入经营动作队列的产品分类。" : null,
  };
}

export function selectProductCategoryOperatingAnalysisSurface(input: {
  rows: ProductCategoryPnlRow[];
  grandTotal?: Pick<ProductCategoryPnlRow, "business_net_income"> | null;
  attribution?: ProductCategoryAttributionPayload | null;
}): ProductCategoryOperatingAnalysisSurface {
  const parentCategoryIds = parentProductCategoryIds(input.rows);
  return {
    metricStatus: PRODUCT_CATEGORY_CANDIDATE_METRIC_STATUS,
    contribution: selectProductCategoryOperatingContribution({
      rows: input.rows,
      grandTotal: input.grandTotal,
    }),
    movement: selectProductCategoryOperatingMovement(
      input.attribution,
      parentCategoryIds,
    ),
    quadrant: selectProductCategoryOperatingQuadrant(input.rows),
    actionQueue: selectProductCategoryOperatingActionQueue({
      rows: input.rows,
      attribution: input.attribution,
      parentCategoryIds,
    }),
  };
}
