import type { ProductCategoryCandidateMetricStatus } from "./productCategoryPnlModelInternals";
import type {
  ProductCategoryAttributionPayload,
  ProductCategoryPnlRow,
  ProductCategoryAttributionRow,
} from "../../../../api/contracts";
import {
  PRODUCT_CATEGORY_CANDIDATE_METRIC_STATUS,
  yiNumberInternal as yiNumber,
  rawYiNumberInternal as rawYiNumber,
  formatSignedProductCategoryYiInternal as formatSignedProductCategoryYi,
  productCategoryYiNumberLabelInternal as productCategoryYiNumberLabel,
  productCategoryDeltaToneInternal as productCategoryDeltaTone,
  parentProductCategoryIdsInternal as parentProductCategoryIds,
  percentNumberInternal as percentNumber,
  leafProductCategoryRowsInternal as leafProductCategoryRows,
} from "./productCategoryPnlModelInternals";
import { EM_DASH } from "../../../../utils/format";

export type ProductCategoryAttributionWaterfallKey =
  | "prior"
  | "day_effect"
  | "scale_effect"
  | "rate_effect"
  | "ftp_effect"
  | "direct_effect"
  | "unexplained_effect"
  | "closure_error"
  | "current";

export type ProductCategoryAttributionWaterfallRow = {
  key: ProductCategoryAttributionWaterfallKey;
  label: string;
  value: number | null;
  valueLabel: string;
  cumulative: number | null;
  cumulativeLabel: string;
  tone: "positive" | "negative" | "neutral";
};

export type ProductCategoryAttributionWaterfallSurface = {
  metricStatus: ProductCategoryCandidateMetricStatus;
  title: string;
  deltaLabel: string;
  rows: ProductCategoryAttributionWaterfallRow[];
  emptyCopy: string | null;
};

export type ProductCategoryRootCauseDriverKey =
  | "day_effect"
  | "scale_effect"
  | "rate_effect"
  | "ftp_effect"
  | "direct_effect"
  | "unexplained_effect"
  | "closure_error";

export type ProductCategoryRootCauseDriverRow = {
  key: ProductCategoryRootCauseDriverKey;
  label: string;
  value: number;
  valueLabel: string;
  relationLabel: "同向" | "抵消" | "中性";
  tone: "positive" | "negative" | "neutral";
};

export type ProductCategoryRootCauseSurface = {
  metricStatus: ProductCategoryCandidateMetricStatus;
  headline: {
    categoryId: string;
    categoryLabel: string;
    delta: number;
    deltaLabel: string;
    driverLabel: string;
    driverValueLabel: string;
    currentNetIncomeLabel: string;
    priorNetIncomeLabel: string;
    scaleLabel: string;
    yieldLabel: string;
    conclusionLabel: string;
    tone: "positive" | "negative" | "neutral";
  } | null;
  driverRows: ProductCategoryRootCauseDriverRow[];
  evidenceItems: string[];
  emptyCopy: string | null;
};

export type ProductCategoryDecisionFocusKey =
  | "top_contributor"
  | "top_pressure"
  | "largest_deterioration"
  | "largest_unexplained";

export type ProductCategoryDecisionFocusItem = {
  key: ProductCategoryDecisionFocusKey;
  categoryId: string;
  categoryLabel: string;
  reasonLabel: string;
  primaryLabel: string;
  secondaryLabel: string;
  tone: "positive" | "negative" | "neutral";
};

export type ProductCategoryDecisionFocusSurface = {
  metricStatus: ProductCategoryCandidateMetricStatus;
  items: ProductCategoryDecisionFocusItem[];
  emptyCopy: string | null;
};

const PRODUCT_CATEGORY_ATTRIBUTION_WATERFALL_STEPS = [
  ["day_effect", "天数因素"],
  ["scale_effect", "规模因素"],
  ["rate_effect", "利率因素"],
  ["ftp_effect", "FTP因素"],
  ["direct_effect", "直接因素"],
  ["unexplained_effect", "未解释"],
  ["closure_error", "闭合误差"],
] as const;

const PRODUCT_CATEGORY_ROOT_CAUSE_DRIVER_STEPS = [
  ["day_effect", "天数因素"],
  ["scale_effect", "规模因素"],
  ["rate_effect", "利率因素"],
  ["ftp_effect", "FTP因素"],
  ["direct_effect", "直接因素"],
  ["unexplained_effect", "未解释"],
  ["closure_error", "闭合误差"],
] as const satisfies ReadonlyArray<
  readonly [ProductCategoryRootCauseDriverKey, string]
>;

export function selectProductCategoryAttributionWaterfallSurface(
  attribution: ProductCategoryAttributionPayload | null | undefined,
): ProductCategoryAttributionWaterfallSurface {
  const headline = attribution?.totals?.grand_total;
  if (!headline || attribution?.state !== "complete") {
    return {
      metricStatus: PRODUCT_CATEGORY_CANDIDATE_METRIC_STATUS,
      title: "经营差异瀑布",
      deltaLabel: EM_DASH,
      rows: [],
      emptyCopy: "当前缺少可用的全表经营差异归因。",
    };
  }
  const prior = yiNumber(headline.prior?.business_net_income);
  const priorRaw = rawYiNumber(headline.prior?.business_net_income);
  const current = yiNumber(headline.current?.business_net_income);
  const currentRaw = rawYiNumber(headline.current?.business_net_income);
  const delta = yiNumber(headline.effects.delta_business_net_income);
  if (
    prior === null ||
    priorRaw === null ||
    current === null ||
    currentRaw === null
  ) {
    return {
      metricStatus: PRODUCT_CATEGORY_CANDIDATE_METRIC_STATUS,
      title: `${headline.category_name || "全表合计"}经营差异瀑布`,
      deltaLabel: formatSignedProductCategoryYi(delta),
      rows: [],
      emptyCopy: "当前归因缺少本期或对比期净营收。",
    };
  }
  let cumulative = priorRaw;
  const rows: ProductCategoryAttributionWaterfallRow[] = [
    {
      key: "prior",
      label: "对比期净营收",
      value: prior,
      valueLabel: productCategoryYiNumberLabel(prior),
      cumulative: priorRaw,
      cumulativeLabel: productCategoryYiNumberLabel(priorRaw),
      tone: productCategoryDeltaTone(prior),
    },
  ];
  for (const [key, label] of PRODUCT_CATEGORY_ATTRIBUTION_WATERFALL_STEPS) {
    const value = yiNumber(headline.effects[key]);
    const rawValue = rawYiNumber(headline.effects[key]);
    if (rawValue !== null) {
      cumulative += rawValue;
    }
    rows.push({
      key,
      label,
      value,
      valueLabel: formatSignedProductCategoryYi(value),
      cumulative: rawValue === null ? null : cumulative,
      cumulativeLabel:
        rawValue === null ? EM_DASH : productCategoryYiNumberLabel(cumulative),
      tone: productCategoryDeltaTone(value),
    });
  }
  rows.push({
    key: "current",
    label: "本期净营收",
    value: current,
    valueLabel: productCategoryYiNumberLabel(current),
    cumulative: currentRaw,
    cumulativeLabel: productCategoryYiNumberLabel(currentRaw),
    tone: productCategoryDeltaTone(delta),
  });
  return {
    metricStatus: PRODUCT_CATEGORY_CANDIDATE_METRIC_STATUS,
    title: `${headline.category_name || "全表合计"}经营差异瀑布`,
    deltaLabel: formatSignedProductCategoryYi(delta),
    rows,
    emptyCopy: null,
  };
}

export function selectProductCategoryRootCauseSurface(input: {
  rows: ProductCategoryPnlRow[];
  attribution?: ProductCategoryAttributionPayload | null;
}): ProductCategoryRootCauseSurface {
  if (!input.attribution || input.attribution.state !== "complete") {
    return {
      metricStatus: PRODUCT_CATEGORY_CANDIDATE_METRIC_STATUS,
      headline: null,
      driverRows: [],
      evidenceItems: [],
      emptyCopy: "当前缺少可用的产品级正式归因，暂不能拆解根因。",
    };
  }
  const parentIds = parentProductCategoryIds(input.rows);
  const attributionRows = input.attribution.rows.filter(
    (row) =>
      !row.category_id.endsWith("_total") &&
      row.category_id !== "grand_total" &&
      row.category_id !== "interest_earning_assets" &&
      !parentIds.has(row.category_id),
  );
  const headlineRow = attributionRows
    .map((row) => ({
      row,
      delta: yiNumber(row.effects.delta_business_net_income),
    }))
    .filter(
      (item): item is { row: ProductCategoryAttributionRow; delta: number } =>
        item.delta !== null && item.delta !== 0,
    )
    .sort((left, right) => Math.abs(right.delta) - Math.abs(left.delta))[0];
  if (!headlineRow) {
    return {
      metricStatus: PRODUCT_CATEGORY_CANDIDATE_METRIC_STATUS,
      headline: null,
      driverRows: [],
      evidenceItems: [],
      emptyCopy: "当前产品级归因没有可拆解的显著差异。",
    };
  }
  const displayRow = input.rows.find(
    (row) => row.category_id === headlineRow.row.category_id,
  );
  const currentNetIncome = yiNumber(
    headlineRow.row.current?.business_net_income ??
      displayRow?.business_net_income,
  );
  const priorNetIncome = yiNumber(headlineRow.row.prior?.business_net_income);
  const scale = yiNumber(
    headlineRow.row.current?.scale ?? displayRow?.cnx_scale,
  );
  const yieldPct = percentNumber(
    headlineRow.row.current?.yield_pct ?? displayRow?.weighted_yield,
  );
  const driverRows = PRODUCT_CATEGORY_ROOT_CAUSE_DRIVER_STEPS.map(
    ([key, label]) => {
      const value = yiNumber(headlineRow.row.effects[key]) ?? 0;
      const relationLabel: ProductCategoryRootCauseDriverRow["relationLabel"] =
        value === 0
          ? "中性"
          : Math.sign(value) === Math.sign(headlineRow.delta)
            ? "同向"
            : "抵消";
      return {
        key,
        label,
        value,
        valueLabel: formatSignedProductCategoryYi(value),
        relationLabel,
        tone: productCategoryDeltaTone(value),
      };
    },
  ).sort((left, right) => Math.abs(right.value) - Math.abs(left.value));
  const leadingDriver = driverRows[0] ?? null;
  const closureError = yiNumber(headlineRow.row.effects.closure_error);
  return {
    metricStatus: PRODUCT_CATEGORY_CANDIDATE_METRIC_STATUS,
    headline: {
      categoryId: headlineRow.row.category_id,
      categoryLabel:
        headlineRow.row.category_name || headlineRow.row.category_id,
      delta: headlineRow.delta,
      deltaLabel: formatSignedProductCategoryYi(headlineRow.delta),
      driverLabel: leadingDriver?.label ?? "未识别",
      driverValueLabel: leadingDriver?.valueLabel ?? EM_DASH,
      currentNetIncomeLabel: productCategoryYiNumberLabel(currentNetIncome),
      priorNetIncomeLabel: productCategoryYiNumberLabel(priorNetIncome),
      scaleLabel: productCategoryYiNumberLabel(scale),
      yieldLabel: yieldPct === null ? EM_DASH : `${yieldPct.toFixed(2)}%`,
      conclusionLabel: `${headlineRow.row.category_name || headlineRow.row.category_id} 变动 ${formatSignedProductCategoryYi(
        headlineRow.delta,
      )} 亿元，主导原因是 ${leadingDriver?.label ?? "未识别"} ${leadingDriver?.valueLabel ?? EM_DASH} 亿元。`,
      tone: productCategoryDeltaTone(headlineRow.delta),
    },
    driverRows,
    evidenceItems: [
      `本期净营收 ${productCategoryYiNumberLabel(currentNetIncome)} 亿元`,
      `对比期净营收 ${productCategoryYiNumberLabel(priorNetIncome)} 亿元`,
      `当前规模 ${productCategoryYiNumberLabel(scale)} 亿元`,
      `当前收益率 ${yieldPct === null ? EM_DASH : `${yieldPct.toFixed(2)}%`}`,
      `闭合误差 ${formatSignedProductCategoryYi(closureError)} 亿元`,
    ],
    emptyCopy: null,
  };
}

function focusItemFromRow(input: {
  key: ProductCategoryDecisionFocusKey;
  row: ProductCategoryPnlRow;
  value: number;
  reasonLabel: string;
  secondaryLabel: string;
}): ProductCategoryDecisionFocusItem {
  return {
    key: input.key,
    categoryId: input.row.category_id,
    categoryLabel: input.row.category_name || input.row.category_id,
    reasonLabel: input.reasonLabel,
    primaryLabel: productCategoryYiNumberLabel(input.value),
    secondaryLabel: input.secondaryLabel,
    tone: productCategoryDeltaTone(input.value),
  };
}

export function selectProductCategoryDecisionFocusSurface(input: {
  rows: ProductCategoryPnlRow[];
  grandTotal?: Pick<ProductCategoryPnlRow, "business_net_income"> | null;
  attribution?: ProductCategoryAttributionPayload | null;
}): ProductCategoryDecisionFocusSurface {
  const candidates = leafProductCategoryRows(input.rows)
    .map((row) => {
      const value = yiNumber(row.business_net_income);
      return value === null || value === 0 ? null : { row, value };
    })
    .filter(
      (item): item is { row: ProductCategoryPnlRow; value: number } =>
        item !== null,
    );
  const items: ProductCategoryDecisionFocusItem[] = [];
  const topContributor = candidates
    .filter((item) => item.value > 0)
    .sort((left, right) => right.value - left.value)[0];
  if (topContributor) {
    items.push(
      focusItemFromRow({
        key: "top_contributor",
        row: topContributor.row,
        value: topContributor.value,
        reasonLabel: "本期贡献最高",
        secondaryLabel: "优先确认利润可持续性",
      }),
    );
  }
  const topPressure = candidates
    .filter((item) => item.value < 0)
    .sort((left, right) => left.value - right.value)[0];
  if (topPressure) {
    items.push(
      focusItemFromRow({
        key: "top_pressure",
        row: topPressure.row,
        value: topPressure.value,
        reasonLabel: "本期压力最大",
        secondaryLabel: "优先定位收入承压来源",
      }),
    );
  }
  if (
    input.attribution?.compare === "mom" &&
    input.attribution.state === "complete"
  ) {
    const parentIds = parentProductCategoryIds(input.rows);
    const attributionRows = input.attribution.rows.filter(
      (row) =>
        !row.category_id.endsWith("_total") &&
        row.category_id !== "grand_total" &&
        row.category_id !== "interest_earning_assets" &&
        !parentIds.has(row.category_id),
    );
    const largestDeterioration = attributionRows
      .map((row) => ({
        row,
        value: yiNumber(row.effects.delta_business_net_income),
      }))
      .filter(
        (item): item is { row: ProductCategoryAttributionRow; value: number } =>
          item.value !== null && item.value < 0,
      )
      .sort((left, right) => left.value - right.value)[0];
    if (largestDeterioration) {
      items.push({
        key: "largest_deterioration",
        categoryId: largestDeterioration.row.category_id,
        categoryLabel:
          largestDeterioration.row.category_name ||
          largestDeterioration.row.category_id,
        reasonLabel: "环比恶化最大",
        primaryLabel: formatSignedProductCategoryYi(largestDeterioration.value),
        secondaryLabel: "优先查看规模/利率/FTP驱动",
        tone: "negative",
      });
    }
    const largestUnexplained = attributionRows
      .map((row) => ({ row, value: yiNumber(row.effects.unexplained_effect) }))
      .filter(
        (item): item is { row: ProductCategoryAttributionRow; value: number } =>
          item.value !== null && item.value !== 0,
      )
      .sort((left, right) => Math.abs(right.value) - Math.abs(left.value))[0];
    if (largestUnexplained) {
      items.push({
        key: "largest_unexplained",
        categoryId: largestUnexplained.row.category_id,
        categoryLabel:
          largestUnexplained.row.category_name ||
          largestUnexplained.row.category_id,
        reasonLabel: "未解释金额最大",
        primaryLabel: formatSignedProductCategoryYi(largestUnexplained.value),
        secondaryLabel: "需要复核归因残差",
        tone: productCategoryDeltaTone(largestUnexplained.value),
      });
    }
  }
  return {
    metricStatus: PRODUCT_CATEGORY_CANDIDATE_METRIC_STATUS,
    items,
    emptyCopy:
      items.length === 0 ? "当前没有可形成决策焦点的产品行或归因结果。" : null,
  };
}
