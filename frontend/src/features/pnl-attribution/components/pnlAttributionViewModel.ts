import type {
  AdvancedAttributionSummary,
  Numeric,
  PnlCompositionPayload,
  ProductCategoryAttributionPayload,
  ProductCategoryPnlPayload,
  ProductCategoryPnlRow,
  TPLMarketCorrelationPayload,
  VolumeRateAttributionPayload,
} from "../../../api/contracts";
import { EM_DASH, formatYi as formatYiShared } from "../../../utils/format";

export type PnlAttributionTab = "product-category" | "volume-rate" | "tpl-market" | "composition" | "advanced";
export type MissingReportDateSource = "none" | "formal-attribution" | "product-category" | "both";
export type VolumeRateBridgeStatus = "closed" | "residual" | "missing" | "no-prior";

export type DualReportDateResolution = {
  formalReportDate: string | null;
  productCategoryReportDate: string | null;
  hasFormalDate: boolean;
  hasProductCategoryDate: boolean;
  datesAligned: boolean;
  missingSource: MissingReportDateSource;
  formalDates: string[];
  productCategoryDates: string[];
};

export type VolumeRateBridgeSummary = {
  currentPnl: number | undefined;
  previousPnl: number | undefined;
  pnlChange: number | undefined;
  volumeEffect: number | undefined;
  rateEffect: number | undefined;
  interactionEffect: number | undefined;
  explainedEffect: number | undefined;
  unexplainedEffect: number | undefined;
  coveragePct: number | undefined;
  status: VolumeRateBridgeStatus;
  statusLabel: string;
  /** 闭合/覆盖率的口径披露文案；消费组件（损益变动桥状态区）应在判定文案旁原样渲染。 */
  closureDisclosure: string;
};

const MISSING_DISPLAY = EM_DASH;
/**
 * 量价归因“闭合 / 覆盖率”判定容差（元）。
 * 口径来源＝前端展示启发式，不是后端契约：workbench 量价归因契约只输出
 * `total_recon_error`，没有闭合判定或容差字段，本常量仅用于展示层状态归类。
 * 判定口径下沉后端属跨栈决策（BF5 报告项），在此之前不得把该判定当作正式指标。
 */
export const VOLUME_RATE_CLOSURE_TOLERANCE_YUAN = 10_000;
/** UI 判定文案/tooltip 必须携带的口径披露；随容差常量联动，禁止各消费方另写一份。 */
export const VOLUME_RATE_CLOSURE_DISCLOSURE = `闭合判定为前端口径（容差 ${
  VOLUME_RATE_CLOSURE_TOLERANCE_YUAN / 10_000
} 万元，非后端契约）`;

const PRODUCT_CATEGORY_TPL_ROW_ID = "bond_tpl";

export type PnlAttributionErrorSummary = {
  /** 面向用户的中文结论句（不含接口路径等英文技术原文）。 */
  message: string;
  /** 原始错误文本（含接口路径），属证据层，只进 title 悬浮提示（§6）。 */
  detail: string;
};

/**
 * 把客户端抛出的 `Request failed: <path> (<status>)` 收敛为中文结论句；
 * 其他文案（后端 detail 多为中文）原样透出，不做二次加工。
 */
export function summarizePnlAttributionError(
  raw: string | null | undefined,
): PnlAttributionErrorSummary | null {
  const text = raw?.trim();
  if (!text) {
    return null;
  }
  const requestFailure = /^Request failed: (\S+) \((\d{3})\)$/.exec(text);
  if (requestFailure) {
    return {
      message: `后端接口请求失败（HTTP ${requestFailure[2]}），当前视图数据未能读取；请重试或先检查后端服务。`,
      detail: text,
    };
  }
  return { message: text, detail: text };
}

/**
 * 结果元信息条「生成时间」展示格式：`YYYY-MM-DD HH:mm`，微秒级 ISO 原值收 title。
 * 仅做字符串截取，不做时区换算（原值带 Z/偏移语义，换算属口径变更）。
 * 非 ISO 形态的字符串原样透出，缺失返回 EM_DASH。
 */
export function formatGeneratedAtDisplay(value: unknown): {
  text: string;
  title: string;
} {
  if (typeof value !== "string" || !value.trim()) {
    return { text: EM_DASH, title: "" };
  }
  const raw = value.trim();
  const isoMatch = /^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})/.exec(raw);
  if (!isoMatch) {
    return { text: raw, title: raw };
  }
  return { text: `${isoMatch[1]} ${isoMatch[2]}`, title: raw };
}

export type AttributionBridgeTone =
  | "total-prev"
  | "total-current"
  | "positive"
  | "negative"
  | "neutral";

export type AttributionBridgeBar = {
  category: string;
  /** 透明垫柱：柱体下沿（累计起点与终点的较小值，可为负）。 */
  base: number;
  /** 柱体跨度（恒 ≥ 0），与垫柱同栈叠放后覆盖 [base, base+size]。 */
  size: number;
  /** 原始带符号数值（顶部标签与 tooltip 用）。 */
  value: number;
  tone: AttributionBridgeTone;
};

export type AttributionBridge = {
  bars: AttributionBridgeBar[];
  /** 柱间累计水平连线（虚线）：from/to 为类目索引，level 为连线所在累计值。 */
  connectors: Array<{ from: number; to: number; level: number }>;
};

/**
 * 标准归因桥（瀑布）定位：上期总值起步 → 各效应从累计位起画 → 当期总值收尾。
 * 任一输入缺失返回 null：缺失不得补 0 参与累计定位，调用方回退独立柱形态。
 * 交叉效应方向语义弱（二阶联动项），tone 恒为 neutral；规模/利率按符号取绿/红。
 */
export function buildAttributionBridge(values: {
  previous: number | null;
  volume: number | null;
  rate: number | null;
  interaction: number | null;
  current: number | null;
}): AttributionBridge | null {
  const { previous, volume, rate, interaction, current } = values;
  if (
    previous === null ||
    volume === null ||
    rate === null ||
    interaction === null ||
    current === null
  ) {
    return null;
  }
  const bars: AttributionBridgeBar[] = [];
  const connectors: AttributionBridge["connectors"] = [];
  const pushSpan = (
    category: string,
    start: number,
    end: number,
    value: number,
    tone: AttributionBridgeTone,
  ) => {
    bars.push({
      category,
      base: Math.min(start, end),
      size: Math.abs(end - start),
      value,
      tone,
    });
  };
  pushSpan("上期损益", 0, previous, previous, "total-prev");
  let cumulative = previous;
  const effects: Array<[string, number, AttributionBridgeTone]> = [
    ["规模效应", volume, volume >= 0 ? "positive" : "negative"],
    ["利率效应", rate, rate >= 0 ? "positive" : "negative"],
    ["交叉效应", interaction, "neutral"],
  ];
  for (const [category, value, tone] of effects) {
    const start = cumulative;
    connectors.push({ from: bars.length - 1, to: bars.length, level: start });
    pushSpan(category, start, start + value, value, tone);
    cumulative = start + value;
  }
  // 末段连线落在效应累计位；若存在未解释差额，它与当期柱顶的落差即残差的可视化。
  connectors.push({ from: bars.length - 1, to: bars.length, level: cumulative });
  pushSpan("当期损益", 0, current, current, "total-current");
  return { bars, connectors };
}

export function findProductCategoryReportDateForPeriod(
  reportDates: readonly string[],
  period: string,
): string | null {
  const periodPrefix = `${period}-`;
  return reportDates.find((date) => date.startsWith(periodPrefix)) ?? null;
}

export function selectProductCategoryTplRow(
  payload: ProductCategoryPnlPayload,
): ProductCategoryPnlRow | null {
  return (
    payload.rows.find((row) => row.category_id === PRODUCT_CATEGORY_TPL_ROW_ID) ??
    null
  );
}

export function numericRaw(value: Numeric | null | undefined): number | undefined {
  if (value === null || value === undefined) {
    return undefined;
  }
  return value.raw ?? undefined;
}

/** 域内统一的带符号亿元入口：委托共享 formatYi（signed 恒真），输出与既往逐字一致。 */
export function formatYi(value: number | null | undefined): string {
  return formatYiShared(value, true);
}

export function formatYiNumeric(value: Numeric | null | undefined): string {
  const display = value?.display?.trim();
  if (display) {
    return display;
  }
  return formatYi(numericRaw(value));
}

export function buildVolumeRateBridgeSummary(data: VolumeRateAttributionPayload | null): VolumeRateBridgeSummary | null {
  if (!data) {
    return null;
  }

  const currentPnl = numericRaw(data.total_current_pnl);
  const previousPnl = numericRaw(data.total_previous_pnl);
  const pnlChange = numericRaw(data.total_pnl_change);
  const volumeEffect = numericRaw(data.total_volume_effect);
  const rateEffect = numericRaw(data.total_rate_effect);
  const interactionEffect = numericRaw(data.total_interaction_effect);
  const unexplainedEffect = numericRaw(data.total_recon_error);
  const canCalculateClosure =
    data.has_previous_data &&
    pnlChange !== undefined &&
    volumeEffect !== undefined &&
    rateEffect !== undefined &&
    interactionEffect !== undefined &&
    unexplainedEffect !== undefined;
  const explainedEffect = canCalculateClosure ? volumeEffect + rateEffect + interactionEffect : undefined;
  const coveragePct =
    canCalculateClosure && explainedEffect !== undefined && pnlChange !== undefined
      ? Math.abs(pnlChange) <= VOLUME_RATE_CLOSURE_TOLERANCE_YUAN
        ? Math.abs(explainedEffect) <= VOLUME_RATE_CLOSURE_TOLERANCE_YUAN
          ? 100
          : undefined
        : (Math.abs(explainedEffect) / Math.abs(pnlChange)) * 100
      : undefined;
  const hasMaterialResidual =
    unexplainedEffect !== undefined && Math.abs(unexplainedEffect) > VOLUME_RATE_CLOSURE_TOLERANCE_YUAN;
  const status: VolumeRateBridgeStatus = !data.has_previous_data
    ? "no-prior"
    : !canCalculateClosure
      ? "missing"
      : hasMaterialResidual
        ? "residual"
        : "closed";
  const statusLabel =
    status === "closed"
      ? "归因闭合"
      : status === "residual"
        ? "存在未解释差额"
        : status === "no-prior"
          ? "无上期对比"
          : "归因字段不完整";

  return {
    currentPnl,
    previousPnl,
    pnlChange,
    volumeEffect,
    rateEffect,
    interactionEffect,
    explainedEffect,
    unexplainedEffect,
    coveragePct,
    status,
    statusLabel,
    closureDisclosure: VOLUME_RATE_CLOSURE_DISCLOSURE,
  };
}

export function formatMetaDateLabel(
  activeTab: PnlAttributionTab,
  options: {
    volumeRateData: VolumeRateAttributionPayload | null;
    tplMarketData: TPLMarketCorrelationPayload | null;
    compositionData: PnlCompositionPayload | null;
    advancedSummary: AdvancedAttributionSummary | null;
    productCategoryAttributionData?: ProductCategoryAttributionPayload | null;
    productCategoryMonthlyData?: ProductCategoryPnlPayload | null;
    productCategoryYtdData?: ProductCategoryPnlPayload | null;
  },
) {
  if (activeTab === "volume-rate") {
    return {
      label: "当前期间",
      value: options.volumeRateData?.current_period ?? MISSING_DISPLAY,
    };
  }
  if (activeTab === "tpl-market") {
    const start = options.tplMarketData?.start_period;
    const end = options.tplMarketData?.end_period;
    return {
      label: "观察区间",
      value: start && end ? `${start} ~ ${end}` : MISSING_DISPLAY,
    };
  }
  if (activeTab === "composition") {
    return {
      label: "报告日期",
      value: options.compositionData?.report_date ?? options.compositionData?.report_period ?? MISSING_DISPLAY,
    };
  }
  if (activeTab === "product-category") {
    return {
      label: "报告日期",
      value:
        options.productCategoryAttributionData?.current_report_date ??
        options.productCategoryMonthlyData?.report_date ??
        options.productCategoryYtdData?.report_date ??
        MISSING_DISPLAY,
    };
  }
  return {
    label: "报告日期",
    value: options.advancedSummary?.report_date ?? MISSING_DISPLAY,
  };
}

function normalizeReportDates(dates: readonly string[] | null | undefined): string[] {
  return Array.from(new Set((dates ?? []).map((date) => String(date).trim()).filter(Boolean))).sort((a, b) =>
    b.localeCompare(a),
  );
}

export function resolveDualReportDates(options: {
  businessDates: readonly string[] | null | undefined;
  productCategoryDates: readonly string[] | null | undefined;
  preferredReportDate?: string | null;
}): DualReportDateResolution {
  const formalDates = normalizeReportDates(options.businessDates);
  const productCategoryDates = normalizeReportDates(options.productCategoryDates);
  const formalSet = new Set(formalDates);
  const productCategorySet = new Set(productCategoryDates);
  const preferred = options.preferredReportDate?.trim();
  const formalReportDate =
    preferred && formalSet.has(preferred) ? preferred : formalDates[0] ?? null;
  const productCategoryReportDate =
    preferred && productCategorySet.has(preferred)
      ? preferred
      : productCategoryDates[0] ?? null;
  const missingSource: MissingReportDateSource =
    formalDates.length === 0 && productCategoryDates.length === 0
      ? "both"
      : formalDates.length === 0
        ? "formal-attribution"
        : productCategoryDates.length === 0
          ? "product-category"
          : "none";
  return {
    formalReportDate,
    productCategoryReportDate,
    hasFormalDate: formalReportDate !== null,
    hasProductCategoryDate: productCategoryReportDate !== null,
    datesAligned:
      formalReportDate !== null &&
      productCategoryReportDate !== null &&
      formalReportDate === productCategoryReportDate,
    missingSource,
    formalDates,
    productCategoryDates,
  };
}
