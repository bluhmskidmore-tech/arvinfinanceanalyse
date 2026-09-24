import type {
  DecimalLike,
  ProductCategoryInterestSpreadPayload,
  ProductCategoryLiabilityCostDecomposition,
  ProductCategoryMetricValue,
} from "../../../../api/contracts";
import { EM_DASH, formatBp } from "../../../../utils/format";
import {
  decimalNumberInternal,
  formatProductCategoryReportMonthLabelInternal,
  yiNumberInternal,
} from "./productCategoryPnlModelInternals";

/**
 * 展示换算常数：后端返回的利差字段单位已是百分数（0.78 表示 0.78%），
 * ×100 只把展示单位换成 BP，不构成前端重算金融指标。
 */
const BASIS_POINTS_PER_PERCENT = 100;

type SpreadMetricLike = ProductCategoryMetricValue | null | undefined;

/**
 * 读数只消费 payload 的利差段与负债成本拆解段，其余字段与本读数无关。
 * `ProductCategoryPnlPayload` 结构上满足该形状，无需改动 B1 的契约文件。
 */
export type ProductCategorySpreadReadoutPayloadLike = {
  interest_spread?: ProductCategoryInterestSpreadPayload | null;
  interest_earning_spread?: ProductCategoryInterestSpreadPayload | null;
  liability_cost_decomposition?: ProductCategoryLiabilityCostDecomposition | null;
};

export type ProductCategorySpreadReadoutMetric = {
  key: string;
  label: string;
  value: string;
  note: string;
  available: boolean;
};

export type ProductCategorySpreadReadoutState =
  | "ready"
  | "partial"
  | "unavailable";

export type ProductCategorySpreadReadoutLiability = {
  state: ProductCategorySpreadReadoutState;
  title: string;
  description: string;
  reason: string | null;
  metrics: ProductCategorySpreadReadoutMetric[];
};

export type ProductCategorySpreadReadoutSurface = {
  state: ProductCategorySpreadReadoutState;
  /** 单月 / 累计的显式口径标注，随视图切换。 */
  viewLabel: string;
  caliberNote: string;
  reason: string | null;
  metrics: ProductCategorySpreadReadoutMetric[];
  liability: ProductCategorySpreadReadoutLiability;
};

function spreadMetricNumber(metric: SpreadMetricLike): number | null {
  return decimalNumberInternal(metric?.raw ?? null);
}

function percentLabel(metric: SpreadMetricLike): string {
  const raw = spreadMetricNumber(metric);
  if (raw === null) {
    return EM_DASH;
  }
  const display = typeof metric?.display === "string" ? metric.display.trim() : "";
  return display.length > 0 ? display : `${raw.toFixed(2)}%`;
}

/** 百分数字段的 BP 展示换算（×100），不改变后端口径。 */
function bpLabelFromPercent(metric: SpreadMetricLike): string {
  const raw = spreadMetricNumber(metric);
  if (raw === null) {
    return EM_DASH;
  }
  return formatBp(raw * BASIS_POINTS_PER_PERCENT, false);
}

/** 后端已按 `unit="bp"` 返回的字段，直接按 BP 展示。 */
function bpLabel(metric: SpreadMetricLike): string {
  const raw = spreadMetricNumber(metric);
  if (raw === null) {
    return EM_DASH;
  }
  const display = typeof metric?.display === "string" ? metric.display.trim() : "";
  return display.length > 0 ? display : formatBp(raw, false);
}

function liabilityScaleLabel(value: DecimalLike | null | undefined): string {
  const yi = yiNumberInternal(value ?? null);
  if (yi === null) {
    return EM_DASH;
  }
  // 负债侧金额沿用负号，规模按绝对值展示，与正式表负债行一致。
  return `${Math.abs(yi).toFixed(2)} 亿元`;
}

function metric(input: {
  key: string;
  label: string;
  value: string;
  note: string;
}): ProductCategorySpreadReadoutMetric {
  return { ...input, available: input.value !== EM_DASH };
}

function clnImpactCopy(metricValue: SpreadMetricLike): {
  title: string;
  description: string;
  metricLabel: string;
  metricNote: string;
} {
  const raw = spreadMetricNumber(metricValue);
  if (raw === null || raw === 0) {
    return {
      title: "负债端 CLN 影响",
      description:
        raw === 0
          ? "信用联结票据对负债端成本率无净影响，后端直出"
          : "信用联结票据对负债端成本率的影响，后端直出",
      metricLabel: "CLN 影响（bp）",
      metricNote:
        raw === 0
          ? "信用联结票据对负债成本率无净影响"
          : "信用联结票据对负债成本率的影响",
    };
  }
  if (raw < 0) {
    return {
      title: "负债端 CLN 降本",
      description: "信用联结票据降低负债端成本率，后端直出",
      metricLabel: "CLN 降本（bp）",
      metricNote: "信用联结票据对负债成本率的降低",
    };
  }
  return {
    title: "负债端 CLN 拖累",
    description: "信用联结票据抬升负债端成本率，后端直出",
    metricLabel: "CLN 拖累（bp）",
    metricNote: "信用联结票据对负债成本率的抬升",
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

/**
 * 从 payload 运行时读取 `liability_cost_decomposition`。
 * 后端字段可能尚未部署，缺失或形状异常时返回 `null` 并由调用方降级。
 */
export function readProductCategoryLiabilityCostDecomposition(
  payload: unknown,
): ProductCategoryLiabilityCostDecomposition | null {
  if (!isRecord(payload)) {
    return null;
  }
  const decomposition = payload.liability_cost_decomposition;
  return isRecord(decomposition)
    ? (decomposition as ProductCategoryLiabilityCostDecomposition)
    : null;
}

function spreadReadoutViewLabel(
  selectedView: string,
  reportDate: string,
): { viewLabel: string; caliberNote: string } {
  const monthLabel = reportDate
    ? formatProductCategoryReportMonthLabelInternal(reportDate)
    : "待选报告月";
  if (selectedView === "monthly") {
    return {
      viewLabel: `单月口径 · ${monthLabel}`,
      caliberNote: `当前为单月（${monthLabel}）口径，切换「汇总视图」查看年初至今累计口径。`,
    };
  }
  return {
    viewLabel: `累计口径 · 截至 ${monthLabel}`,
    caliberNote: `当前为年初至今累计口径（截至 ${monthLabel}），切换「月度视图」查看单月口径。`,
  };
}

function buildLiabilitySurface(
  decomposition: ProductCategoryLiabilityCostDecomposition | null,
): ProductCategorySpreadReadoutLiability {
  if (!decomposition) {
    return {
      state: "unavailable",
      title: "负债端 CLN 影响",
      description: "信用联结票据对负债端成本率的影响，后端直出",
      reason: "后端未返回负债成本拆解字段，CLN 影响暂不可用。",
      metrics: [],
    };
  }
  const impactCopy = clnImpactCopy(decomposition.cln_drag_bp);
  const clnScale = liabilityScaleLabel(decomposition.cln_scale);
  const metrics = [
    metric({
      key: "liability_yield_pct",
      label: "负债端成本率",
      value: percentLabel(decomposition.liability_yield_pct),
      note: "负债合计加权成本率",
    }),
    metric({
      key: "liability_yield_ex_cln_pct",
      label: "剔除CLN后成本率",
      value: percentLabel(decomposition.liability_yield_ex_cln_pct),
      note: "负债合计剔除信用联结票据",
    }),
    metric({
      key: "cln_drag_bp",
      label: impactCopy.metricLabel,
      value: bpLabel(decomposition.cln_drag_bp),
      note: impactCopy.metricNote,
    }),
    metric({
      key: "cln_yield_pct",
      label: "CLN 自身成本率",
      value: percentLabel(decomposition.cln_yield_pct),
      note: `规模 ${clnScale}`,
    }),
  ];
  const availableCount =
    metrics.filter((item) => item.available).length +
    (clnScale === EM_DASH ? 0 : 1);
  const expectedFieldCount = metrics.length + 1;
  if (availableCount === 0) {
    return {
      state: "unavailable",
      title: impactCopy.title,
      description: impactCopy.description,
      reason: "后端返回的负债成本拆解全部为空，CLN 影响暂不可用。",
      metrics,
    };
  }
  const state =
    availableCount === expectedFieldCount
      ? ("ready" as const)
      : ("partial" as const);
  return {
    state,
    title: impactCopy.title,
    description: impactCopy.description,
    reason:
      state === "partial"
        ? "后端返回的负债成本拆解不完整，缺失项以—展示。"
        : null,
    metrics,
  };
}

/**
 * 主屏利差读数：两个口径的收益率/成本率/利差一律从后端 payload 的
 * `interest_earning_spread`（生息资产口径）与 `interest_spread`（含TPL 资产端口径）直取，
 * 前端只做百分数→BP 的展示换算，不重算任何金融指标。
 */
export function selectProductCategorySpreadReadoutSurface(input: {
  payload?: ProductCategorySpreadReadoutPayloadLike | null;
  reportDate: string;
  selectedView: string;
}): ProductCategorySpreadReadoutSurface {
  const interestEarning: ProductCategoryInterestSpreadPayload | null =
    input.payload?.interest_earning_spread ?? null;
  const interestSpread: ProductCategoryInterestSpreadPayload | null =
    input.payload?.interest_spread ?? null;
  const { viewLabel, caliberNote } = spreadReadoutViewLabel(
    input.selectedView,
    input.reportDate,
  );
  const metrics = [
    metric({
      key: "interest_earning_asset_yield",
      label: "生息资产收益率",
      value: percentLabel(interestEarning?.all_currency_asset_yield_pct),
      note: "生息资产口径 · 本外币合计",
    }),
    metric({
      key: "liability_yield",
      label: "负债端成本率",
      value: percentLabel(interestEarning?.all_currency_liability_yield_pct),
      note: "计息负债合计 · 本外币合计",
    }),
    metric({
      key: "interest_earning_spread",
      label: "生息资产利差（bp）",
      value: bpLabelFromPercent(interestEarning?.all_currency_spread_pct),
      note: "生息资产收益率与负债端成本率之差（后端计算）",
    }),
    metric({
      key: "asset_yield_with_tpl",
      label: "资产端收益率（含TPL）",
      value: percentLabel(interestSpread?.all_currency_asset_yield_pct),
      note: "资产端合计含交易性金融资产",
    }),
    metric({
      key: "interest_spread_with_tpl",
      label: "资产负债利差（含TPL）（bp）",
      value: bpLabelFromPercent(interestSpread?.all_currency_spread_pct),
      note: "含TPL 资产端与负债端之差（后端计算）",
    }),
  ];
  const availableCount = metrics.filter((item) => item.available).length;
  const state: ProductCategorySpreadReadoutState =
    availableCount === metrics.length
      ? "ready"
      : availableCount > 0
        ? "partial"
        : "unavailable";
  return {
    state,
    viewLabel,
    caliberNote,
    reason:
      state === "ready"
        ? null
        : state === "partial"
          ? "后端返回的利差指标不完整，缺失项以—展示。"
          : "后端未返回利差指标，主屏利差读数暂不可用。",
    metrics,
    liability: buildLiabilitySurface(
      readProductCategoryLiabilityCostDecomposition(input.payload),
    ),
  };
}
