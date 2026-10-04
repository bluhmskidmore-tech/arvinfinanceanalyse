import type {
  ProductCategoryAttributionRow,
  DecimalLike,
  ProductCategoryPnlPayload,
  ProductCategoryAttributionPayload,
  ProductCategoryPnlRow,
} from "../../../../api/contracts";
import {
  formatSignedProductCategoryYiInternal as formatSignedProductCategoryYi,
  rawYiNumberInternal as rawYiNumber,
  productCategoryYiNumberLabelInternal as productCategoryYiNumberLabel,
  findProductCategoryRowInternal as findProductCategoryRow,
  decimalNumberInternal as decimalNumber,
  yiNumberInternal as yiNumber,
  productCategoryDeltaToneInternal as productCategoryDeltaTone,
} from "./productCategoryPnlModelInternals";
import { EM_DASH } from "../../../../utils/format";
import { selectProductCategoryClosureErrorSignal } from "./productCategoryPnlDisplayModel";
import {
  productCategoryRowDeltaYi,
  productCategoryScenarioSideLabel,
} from "./productCategoryScenarioSensitivityModel";

type ScenarioExplanationHelpers = {
  yiNumber: (value: DecimalLike | null | undefined) => number | null;
  rawYiNumber: (value: DecimalLike | null | undefined) => number | null;
  formatSignedProductCategoryYi: (value: number | null) => string;
  productCategoryDeltaTone: (
    value: number | null,
  ) => ProductCategoryScenarioExplanationDriverRow["tone"];
};

const PRODUCT_CATEGORY_SCENARIO_EXPLANATION_DRIVERS = [
  ["ftp_effect", "FTP因素"],
  ["scale_effect", "规模因素"],
  ["rate_effect", "利率因素"],
  ["day_effect", "天数因素"],
  ["direct_effect", "直接因素"],
  ["unexplained_effect", "未解释"],
] as const;

function scenarioExplanationDriverRows(
  attributionRow: ProductCategoryAttributionRow | undefined,
  helpers: ScenarioExplanationHelpers,
): ProductCategoryScenarioExplanationDriverRow[] {
  if (!attributionRow) {
    return [];
  }
  return PRODUCT_CATEGORY_SCENARIO_EXPLANATION_DRIVERS.map(([key, label]) => {
    const raw = attributionRow.effects[key];
    const value = typeof raw === "string" && raw.trim() === "" ? null : helpers.yiNumber(raw);
    return {
      key,
      label,
      value,
      valueLabel: helpers.formatSignedProductCategoryYi(value),
      tone: helpers.productCategoryDeltaTone(value),
    };
  }).sort(
    (left, right) => Math.abs(right.value ?? 0) - Math.abs(left.value ?? 0),
  );
}

function dominantScenarioExplanationDriver(
  rows: ProductCategoryScenarioExplanationDriverRow[],
): ProductCategoryScenarioExplanationDriverRow | undefined {
  return rows.find((row) => row.value !== null && row.value !== 0);
}

function scenarioExplanationAttributionTotal(
  row: ProductCategoryAttributionRow | undefined,
  helpers: ScenarioExplanationHelpers,
): number | null {
  const delta = row?.effects.delta_business_net_income;
  return typeof delta === "string" && delta.trim() === "" ? null : helpers.rawYiNumber(delta);
}

export function selectProductCategoryScenarioAttributionImpl(input: {
  attributionRow: ProductCategoryAttributionRow | undefined;
  helpers: ScenarioExplanationHelpers;
}) {
  const { attributionRow, helpers } = input;
  const driverRows = scenarioExplanationDriverRows(attributionRow, helpers);
  const dominantDriver = dominantScenarioExplanationDriver(driverRows);
  const attributionTotal = scenarioExplanationAttributionTotal(attributionRow, helpers);
  const attributionDriversComplete =
    attributionRow?.state === "complete" &&
    driverRows.length === PRODUCT_CATEGORY_SCENARIO_EXPLANATION_DRIVERS.length &&
    driverRows.every((row) => row.value !== null);
  const rawClosureError = attributionRow?.effects.closure_error;
  const closureError =
    typeof rawClosureError === "string" && rawClosureError.trim() === ""
      ? null
      : rawClosureError;
  return { driverRows, dominantDriver, attributionTotal, attributionDriversComplete, closureError };
}

export function scenarioExplanationReviewActions(input: {
  bridgeTone: ProductCategoryScenarioExplanation["bridgeTone"];
  dominantDriver?: ProductCategoryScenarioExplanationDriverRow;
  triggerRateLabel: string;
  attributionReady: boolean;
  hasClosureGap: boolean;
}): string[] {
  const actions =
    !input.attributionReady
      ? [
          "先补齐正式归因变动、六项驱动与闭合误差，再核对情景压力。",
          "核对正式归因期间口径：确认正式归因的 current/prior 日期、月度/同比口径与情景基线不同。",
        ]
      : input.hasClosureGap
        ? [
            "先复核正式归因闭合误差及六项驱动的输入来源。",
            "核对正式归因期间口径：确认正式归因的 current/prior 日期、月度/同比口径与情景基线不同。",
          ]
        : input.bridgeTone === "warning"
          ? [
              `先复核情景 FTP 假设：确认 ${input.triggerRateLabel} 情景是否只改变 FTP，不混入正式期间变动。`,
              "核对正式归因期间口径：确认正式归因的 current/prior 日期、月度/同比口径与情景基线不同。",
            ]
          : [
              "先确认情景压力与正式归因合计接近，再复核主导驱动和输入来源。",
              "核对正式归因期间口径：确认 current/prior 日期、月度/同比口径与情景基线不同。",
            ];
  if (input.dominantDriver) {
    const driverActionByKey: Record<
      ProductCategoryScenarioExplanationDriverRow["key"],
      string
    > = {
      ftp_effect: "复核 FTP 输入、基准利率和资产负债侧映射。",
      scale_effect: "复核规模口径、日均余额和产品分类映射。",
      rate_effect: "复核收益率/成本率输入、计息天数和基准利率变动。",
      day_effect: "复核归因期间计息天数和报告日期。",
      direct_effect: "复核直接收入、支出与产品分类映射。",
      unexplained_effect:
        "复核残差来源，检查缺失字段、四舍五入和未覆盖业务项。",
    };
    actions.push(
      `重点追踪 ${input.dominantDriver.label}：${driverActionByKey[input.dominantDriver.key]}`,
    );
  }
  return actions.slice(0, 3);
}
export type ProductCategoryScenarioExplanationDriverRow = {
  key: keyof Pick<
    ProductCategoryAttributionRow["effects"],
    | "ftp_effect"
    | "scale_effect"
    | "rate_effect"
    | "day_effect"
    | "direct_effect"
    | "unexplained_effect"
  >;
  label: string;
  value: number | null;
  valueLabel: string;
  tone: "positive" | "negative" | "neutral";
};

export type ProductCategoryScenarioExplanation = {
  categoryId: string;
  categoryLabel: string;
  sideLabel: string;
  triggerRateLabel: string;
  scenarioDeltaLabel: string;
  baselineNetIncomeLabel: string;
  scenarioNetIncomeLabel: string;
  summaryLabel: string;
  bridgeLabel: string;
  bridgeConclusionLabel: string;
  bridgeTone: "positive" | "negative" | "neutral" | "warning";
  reviewActionItems: string[];
  driverRows: ProductCategoryScenarioExplanationDriverRow[];
  emptyCopy: string | null;
};

function scenarioExplanationBridge(input: {
  scenarioDelta: number | null | undefined;
  attributionTotal: number | null;
  closureError: DecimalLike | null | undefined;
  attributionDriversComplete: boolean;
}): Pick<
  ProductCategoryScenarioExplanation,
  "bridgeLabel" | "bridgeConclusionLabel" | "bridgeTone"
> {
  const scenarioDeltaLabel = formatSignedProductCategoryYi(
    input.scenarioDelta ?? null,
  );
  const attributionTotalLabel = formatSignedProductCategoryYi(
    input.attributionTotal,
  );
  if (
    input.scenarioDelta === null ||
    input.scenarioDelta === undefined ||
    input.attributionTotal === null
  ) {
    return {
      bridgeLabel: `口径桥：情景压力 ${scenarioDeltaLabel} 亿元；正式归因合计 ${attributionTotalLabel} 亿元；差异 ${EM_DASH}。`,
      bridgeConclusionLabel:
        "当前缺少可比较的情景压力或正式净收入变动，暂不能做口径差异判断。",
      bridgeTone: "neutral",
    };
  }
  const bridgeGap = Number(
    (input.scenarioDelta - input.attributionTotal).toFixed(2),
  );
  const bridgeGapAbs = Math.abs(bridgeGap);
  const closureError = rawYiNumber(input.closureError);
  const closureSignal = selectProductCategoryClosureErrorSignal(input.closureError);
  const bridgeTone =
    bridgeGapAbs > 0.01 || closureSignal.hasMaterialGap ? "warning" : "neutral";
  const bridgeConclusionLabel = closureSignal.hasMaterialGap
    ? `正式归因闭合误差 ${formatSignedProductCategoryYi(closureError)} 亿元，需先复核六项驱动和输入来源，再判断与情景压力的口径差异。`
    : closureError === null
      ? "正式归因闭合误差缺失，暂不能确认归因闭合；情景压力与正式变动需分开复核。"
      : !input.attributionDriversComplete
        ? "正式归因驱动不完整，暂不能确认完整归因；情景压力与正式变动需分开复核。"
        : bridgeTone === "neutral"
          ? "情景压力与正式归因合计接近，可优先复核主导驱动和输入来源。"
          : `情景压力与正式归因差异 ${productCategoryYiNumberLabel(bridgeGapAbs)} 亿元，需分开复核情景 FTP 假设和正式归因期间口径。`;
  return {
    bridgeLabel: `口径桥：情景压力 ${scenarioDeltaLabel} 亿元；正式归因合计 ${attributionTotalLabel} 亿元；差异 ${formatSignedProductCategoryYi(bridgeGap)} 亿元。`,
    bridgeConclusionLabel,
    bridgeTone,
  };
}

export function selectProductCategoryScenarioExplanation(input: {
  categoryId: string | null | undefined;
  baseline?: ProductCategoryPnlPayload | null;
  scenarios: ProductCategoryPnlPayload[];
  attribution?: ProductCategoryAttributionPayload | null;
}): ProductCategoryScenarioExplanation | null {
  if (!input.categoryId || !input.baseline) {
    return null;
  }
  const baselineRow = findProductCategoryRow(
    input.baseline.rows,
    input.categoryId,
  );
  if (!baselineRow) {
    return {
      categoryId: input.categoryId,
      categoryLabel: input.categoryId,
      sideLabel: EM_DASH,
      triggerRateLabel: EM_DASH,
      scenarioDeltaLabel: EM_DASH,
      baselineNetIncomeLabel: EM_DASH,
      scenarioNetIncomeLabel: EM_DASH,
      summaryLabel: "当前正式基线未返回该产品行，无法形成行级情景解释。",
      bridgeLabel: `口径桥：情景压力 ${EM_DASH} 亿元；正式归因合计 ${EM_DASH} 亿元；差异 ${EM_DASH}。`,
      bridgeConclusionLabel:
        "当前缺少可比较的情景压力或正式归因驱动，暂不能做口径差异判断。",
      bridgeTone: "neutral",
      reviewActionItems: ["补齐正式基线和情景矩阵后，再生成行级复核动作。"],
      driverRows: [],
      emptyCopy: "当前正式基线未返回该产品行，无法形成行级情景解释。",
    };
  }
  const baselineNetIncome = rawYiNumber(baselineRow.business_net_income);
  const scenarioMoves = input.scenarios
    .map((scenario) => {
      if (scenario.report_date !== input.baseline?.report_date || scenario.view !== input.baseline?.view) {
        return null;
      }
      const scenarioRow = findProductCategoryRow(
        scenario.rows,
        input.categoryId as string,
      );
      if (!scenarioRow) {
        return null;
      }
      const delta = productCategoryRowDeltaYi(
        new Map([[baselineRow.category_id, baselineRow]]),
        scenarioRow,
      );
      const scenarioNetIncome = rawYiNumber(scenarioRow.business_net_income);
      const scenarioRate = decimalNumber(scenario.scenario_rate_pct);
      if (
        delta === null ||
        scenarioNetIncome === null ||
        scenarioRate === null
      ) {
        return null;
      }
      return {
        row: scenarioRow,
        delta,
        scenarioNetIncome,
        rateLabel: `${scenarioRate.toFixed(2)}%`,
      };
    })
    .filter(
      (
        move,
      ): move is {
        row: ProductCategoryPnlRow;
        delta: number;
        scenarioNetIncome: number;
        rateLabel: string;
      } => move !== null,
    )
    .sort((left, right) => Math.abs(right.delta) - Math.abs(left.delta));
  const topMove = scenarioMoves[0];
  const comparableAttribution =
    input.attribution?.state === "complete" && input.baseline.view === "monthly" &&
    input.attribution.current_report_date === input.baseline.report_date
      ? input.attribution
      : null;
  const attributionRow = comparableAttribution?.rows.find(
    (row) => row.category_id === input.categoryId,
  );
  const { driverRows, dominantDriver, attributionTotal, attributionDriversComplete, closureError } =
    selectProductCategoryScenarioAttributionImpl({
      attributionRow,
      helpers: { yiNumber, rawYiNumber, formatSignedProductCategoryYi, productCategoryDeltaTone },
    });
  const scenarioDeltaLabel = formatSignedProductCategoryYi(
    topMove?.delta ?? null,
  );
  const triggerRateLabel = topMove?.rateLabel ?? EM_DASH;
  const baselineNetIncomeLabel =
    productCategoryYiNumberLabel(baselineNetIncome);
  const scenarioNetIncomeLabel = productCategoryYiNumberLabel(
    topMove?.scenarioNetIncome ?? null,
  );
  const bridge = scenarioExplanationBridge({
    scenarioDelta: topMove?.delta,
    attributionTotal,
    closureError,
    attributionDriversComplete,
  });
  const reviewActionItems = scenarioExplanationReviewActions({
    bridgeTone: bridge.bridgeTone,
    dominantDriver,
    triggerRateLabel,
    attributionReady:
      attributionTotal !== null &&
      attributionDriversComplete &&
      decimalNumber(closureError) !== null &&
      topMove !== undefined,
    hasClosureGap: selectProductCategoryClosureErrorSignal(closureError).hasMaterialGap,
  });
  const driverCopy = dominantDriver
    ? `正式归因显示主导因素为 ${dominantDriver.label} ${dominantDriver.valueLabel} 亿元。`
    : "当前正式归因未返回可排序的驱动项。";
  const summaryLabel = `${baselineRow.category_name || baselineRow.category_id}在 ${triggerRateLabel} 情景较正式基线 ${scenarioDeltaLabel} 亿元；${driverCopy}`;
  return {
    categoryId: baselineRow.category_id,
    categoryLabel: baselineRow.category_name || baselineRow.category_id,
    sideLabel: productCategoryScenarioSideLabel(baselineRow.side),
    triggerRateLabel,
    scenarioDeltaLabel,
    baselineNetIncomeLabel,
    scenarioNetIncomeLabel,
    summaryLabel,
    ...bridge,
    reviewActionItems,
    driverRows,
    emptyCopy: topMove ? null : "当前情景矩阵未返回该产品行的可比较结果。",
  };
}
