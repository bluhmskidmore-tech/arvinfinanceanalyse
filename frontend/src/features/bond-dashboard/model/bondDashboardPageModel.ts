/**
 * 债券总览（/bond-dashboard）页面视图模型层：纯函数 + 类型，只做映射与展示格式化，
 * 不做任何正式金融计算；金额/利率格式一律复用 `../utils/format` 的既有函数。
 *
 * 迁移说明：`businessTypeMetricNumber` / `formatYiOrNoData` / `formatYearsOrNoData` /
 * `formatCreditRatioDetail` / `describeFirstScreenMetaFallback` / `buildDashboardConclusion`
 * 迁移自重构前的 `../pages/BondDashboardPage.tsx`（页面已切换到本模型，旧副本已删除）。
 * 除 `buildDashboardConclusion` 的结论句补单位（见函数内注释）外，其余保持逐字一致。
 */
import type {
  ApiEnvelope,
  BondDashboardBundlePayload,
  BondDashboardBundleSectionStatus,
  BondDashboardHeadlinePayload,
  Numeric,
  ResultMeta,
  RiskIndicatorsPayload,
} from "../../../api/contracts";
import { EM_DASH, numericRaw } from "../../../pageModel";
import { BOND_DASHBOARD_PAGE_BUNDLE_SECTIONS } from "../bondDashboardBundleModel";
import {
  formatDv01Wan,
  formatMomChange,
  formatRatePercent,
  formatYears,
  formatYi,
  type BondKpiMomKind,
} from "../utils/format";

// ---------------------------------------------------------------------------
// 原样迁移自 BondDashboardPage.tsx 的纯函数（行为、文案、判定顺序逐字一致）
// ---------------------------------------------------------------------------

/**
 * `Number("")` and `Number(null)` are both 0, so a blank cell would render as a real zero.
 * 2026-08-13 起后端对零覆盖的业务类型指标输出空串（缺失≠0，见
 * bond_dashboard_service._bond_dashboard_business_type_payload），本函数把空串归 null
 * 渲染 EM_DASH；显式 "0.00000000" 仍按真实零保留。
 */
export function businessTypeMetricNumber(value: unknown): number | null {
  if (value === null || value === undefined) return null;
  if (typeof value === "string" && value.trim() === "") return null;
  const raw = Number(value);
  return Number.isFinite(raw) ? raw : null;
}

export function formatYiOrNoData(value: Numeric | null | undefined): string {
  return numericRaw(value) === null ? EM_DASH : formatYi(value);
}

export function formatYearsOrNoData(value: Numeric | null | undefined): string {
  return numericRaw(value) === null ? EM_DASH : formatYears(value);
}

export function formatCreditRatioDetail(value: Numeric | null | undefined): string {
  return numericRaw(value) === null
    ? `当前信用占比 ${EM_DASH}`
    : `当前信用占比 ${formatRatePercent(value, 1)}%`;
}

/**
 * 首屏 stale/fallback 警示：quality_flag 非 ok、fallback_date 非空、
 * 或 resolved_report_date 与请求日不一致时，返回该信封的降级说明；否则返回 null。
 */
export function describeFirstScreenMetaFallback(
  label: string,
  meta: ResultMeta | undefined,
  pageRequestedReportDate: string | null,
): string | null {
  if (!meta) return null;
  const requestedDate = meta.requested_report_date?.trim() || pageRequestedReportDate?.trim() || "";
  const resolvedDate = meta.resolved_report_date?.trim() ?? "";
  const fallbackDate = meta.fallback_date?.trim() ?? "";
  const qualityDegraded = meta.quality_flag !== "ok";
  const dateFallback = Boolean(requestedDate && resolvedDate && resolvedDate !== requestedDate);
  if (!qualityDegraded && !fallbackDate && !dateFallback) return null;

  const parts: string[] = [];
  if (qualityDegraded) parts.push(`供数质量 ${meta.quality_flag}`);
  if (dateFallback) parts.push(`请求日 ${requestedDate} 回退至 ${resolvedDate}`);
  if (fallbackDate) parts.push(`回退日期 ${fallbackDate}`);
  const actualDate = resolvedDate || meta.as_of_date?.trim() || "";
  if (actualDate && !dateFallback) parts.push(`实际数据日期 ${actualDate}`);
  return `${label}：${parts.join("；")}`;
}

export function buildDashboardConclusion(
  headline: BondDashboardHeadlinePayload | undefined,
  risk: RiskIndicatorsPayload | undefined,
) {
  if (!headline || !risk) {
    return {
      title: "当前结论",
      body: "债券驾驶舱结论待载入，先确认报告日与正式读链路状态。",
      detail: "首屏结论会基于持仓规模、久期和信用占比同步更新。",
    };
  }

  const totalMarketValue = numericRaw(headline.kpis.total_market_value);
  const creditRatio = numericRaw(risk.credit_ratio);
  const creditTone =
    creditRatio === null
      ? `信用仓位 ${EM_DASH}`
      : creditRatio >= 0.5
        ? "信用仓位偏高"
        : creditRatio >= 0.3
          ? "信用仓位适中"
          : "利率债占比更高";
  const investmentState =
    totalMarketValue === null
      ? "不形成投放状态结论"
      : totalMarketValue > 0
        ? "处于已投放状态"
        : "尚未形成有效持仓";

  /*
   * 有意偏离逐字迁移（2026-08-13 视觉走查）：旧文案「组合规模约 3,423.05，久期约 4.29」
   * 缺单位，金额语义模糊；此处在数值可用时补「亿元 / 年」，缺值仍为裸 EM_DASH。
   */
  const scaleText = formatYiOrNoData(headline.kpis.total_market_value);
  const durationText = formatYearsOrNoData(headline.kpis.weighted_duration);
  return {
    title: "当前结论",
    body: `组合规模约 ${scaleText === EM_DASH ? scaleText : `${scaleText} 亿元`}，久期约 ${durationText === EM_DASH ? durationText : `${durationText} 年`}，${creditTone}。`,
    detail: `${formatCreditRatioDetail(risk.credit_ratio)}，总市值${investmentState}。`,
  };
}

export type BondDashboardConclusion = ReturnType<typeof buildDashboardConclusion>;

// ---------------------------------------------------------------------------
// KPI 横带模型（首页标准：单框 8 格横带替代原 7 张独立卡）
// ---------------------------------------------------------------------------

export type BondDashboardKpiCell = {
  key: string;
  label: string;
  /** 预格式化展示串；缺失为 EM_DASH。 */
  value: string;
  /** value 为 EM_DASH 时置 null（组件不渲染单位）。 */
  unit: string | null;
  /** 环比文本，来自 formatMomChange；bond_count 为整数差披露。 */
  mom: string | null;
  momTone: "up" | "down" | "flat" | "none";
  note?: string;
};

type BondDashboardNumericKpiKey =
  | "total_market_value"
  | "unrealized_pnl"
  | "weighted_ytm"
  | "weighted_duration"
  | "weighted_coupon"
  | "credit_spread_median"
  | "total_dv01";

/** 与 HeadlineKpis.tsx 的 KPI_DEFS 逐项一致（key/label/unit/format/momKind）。 */
const KPI_BAND_NUMERIC_DEFS: {
  key: BondDashboardNumericKpiKey;
  label: string;
  unit: string;
  format: (v: Numeric | null | undefined) => string;
  momKind: BondKpiMomKind;
}[] = [
  { key: "total_market_value", label: "债券持仓规模", unit: "亿", format: formatYi, momKind: "percent" },
  { key: "unrealized_pnl", label: "未实现损益", unit: "亿", format: formatYi, momKind: "amountYi" },
  { key: "weighted_ytm", label: "加权到期收益率", unit: "%", format: formatRatePercent, momKind: "rateBp" },
  { key: "weighted_duration", label: "加权久期", unit: "年", format: formatYears, momKind: "percent" },
  { key: "weighted_coupon", label: "加权票息率", unit: "%", format: formatRatePercent, momKind: "rateBp" },
  {
    key: "credit_spread_median",
    label: "信用债收益率中位数",
    unit: "%",
    format: formatRatePercent,
    momKind: "rateBp",
  },
  { key: "total_dv01", label: "DV01合计", unit: "万元/bp", format: formatDv01Wan, momKind: "percent" },
];

const BOND_COUNT_KPI = { key: "bond_count", label: "持仓只数", unit: "只" } as const;

/**
 * 环比 tone 推导与现网 HeadlineKpis 行为一致："+" 前缀=up、"-" 前缀=down、
 * 其余非空=flat、null=none。注意 amountYi 的 "+0.00 亿" 会判 up——保持现网行为。
 */
function momToneFromText(mom: string | null): BondDashboardKpiCell["momTone"] {
  if (mom === null) return "none";
  if (mom.startsWith("+")) return "up";
  if (mom.startsWith("-")) return "down";
  return "flat";
}

/** 持仓只数环比是计数差披露，不是金融计算：直接用整数差表达。 */
function formatBondCountDelta(delta: number): string {
  return `${delta > 0 ? "+" : ""}${delta} 只`;
}

export function buildBondDashboardKpiBand(input: {
  headline: BondDashboardHeadlinePayload | undefined;
  loading: boolean;
}): { cells: BondDashboardKpiCell[]; loading: boolean } {
  const { headline, loading } = input;

  if (!headline) {
    const placeholderLabels = [
      ...KPI_BAND_NUMERIC_DEFS.map(({ key, label }) => ({ key, label })),
      { key: BOND_COUNT_KPI.key, label: BOND_COUNT_KPI.label },
    ];
    return {
      cells: placeholderLabels.map(
        ({ key, label }): BondDashboardKpiCell => ({
          key,
          label,
          value: EM_DASH,
          unit: null,
          mom: null,
          momTone: "none",
        }),
      ),
      loading,
    };
  }

  const { kpis, prev_kpis: prevKpis, prev_report_date: prevReportDate } = headline;

  const cells = KPI_BAND_NUMERIC_DEFS.map((def): BondDashboardKpiCell => {
    const raw = kpis[def.key];
    const prevRaw = prevKpis?.[def.key];
    const value = def.format(raw);
    const mom = formatMomChange(def.momKind, raw, prevRaw);
    const cell: BondDashboardKpiCell = {
      key: def.key,
      label: def.label,
      value,
      unit: value === EM_DASH ? null : def.unit,
      mom,
      momTone: momToneFromText(mom),
    };
    if (def.key === "total_market_value" && prevReportDate) {
      cell.note = `环比基准 ${prevReportDate}`;
    }
    return cell;
  });

  const bondCountMom = prevKpis ? formatBondCountDelta(kpis.bond_count - prevKpis.bond_count) : null;
  cells.push({
    key: BOND_COUNT_KPI.key,
    label: BOND_COUNT_KPI.label,
    value: String(kpis.bond_count),
    unit: BOND_COUNT_KPI.unit,
    mom: bondCountMom,
    momTone: momToneFromText(bondCountMom),
  });

  return { cells, loading };
}

// ---------------------------------------------------------------------------
// 口径行模型
// ---------------------------------------------------------------------------

export function buildBondDashboardCaliberItems(input: {
  /** 空串表示未定。 */
  reportDate: string;
  /** headline.prev_report_date。 */
  prevReportDate: string | null;
  /** dates 信封顶层 data_source 字段。 */
  dataSource: string | undefined;
}): string[] {
  const items: string[] = [
    `报告日：${input.reportDate || EM_DASH}`,
    `环比基准：${input.prevReportDate || EM_DASH}`,
  ];
  if (input.dataSource === "bond_analytics_facts") {
    // 现有页面标题 Tooltip 的原文披露。
    items.push("数据来源：债券分析事实表（与余额分析页可能存在口径差异）");
  } else if (input.dataSource) {
    items.push(`数据来源：${input.dataSource}`);
  }
  return items;
}

// ---------------------------------------------------------------------------
// 首屏状态模型（收口页面现有四个 Alert 的判定与文案）
// ---------------------------------------------------------------------------

export type BondDashboardScreenNotice = {
  key: "dates-error" | "dates-empty" | "bundle-error" | "stale";
  kind: "error" | "info" | "warning";
  title: string;
  description: string;
};

export function buildBondDashboardScreenNotices(input: {
  datesError: boolean;
  datesEmpty: boolean;
  bundleError: boolean;
  fallbackNotices: string[];
}): BondDashboardScreenNotice[] {
  const notices: BondDashboardScreenNotice[] = [];
  if (input.datesError) {
    notices.push({
      key: "dates-error",
      kind: "error",
      title: "报告日加载失败",
      description: "当前无法获取债券驾驶舱可用报告日，请稍后重试。",
    });
  }
  if (input.datesEmpty) {
    notices.push({
      key: "dates-empty",
      kind: "info",
      title: "暂无可用报告日",
      description: "债券驾驶舱当前没有可读的正式报告日，因此首屏模块不展示业务结论。",
    });
  }
  if (input.bundleError) {
    notices.push({
      key: "bundle-error",
      kind: "error",
      title: "债券总览数据加载失败",
      description: "当前无法获取债券总览聚合数据，请稍后重试。",
    });
  }
  if (input.fallbackNotices.length > 0) {
    notices.push({
      key: "stale",
      kind: "warning",
      title: "首屏数据为回退/降级口径",
      description: `${input.fallbackNotices.join("。")}。下方 KPI 与结论基于上述回退数据，请以实际数据日期为准。`,
    });
  }
  return notices;
}

// ---------------------------------------------------------------------------
// bundle 分区状态披露模型
// ---------------------------------------------------------------------------

export type BondDashboardSectionStatusItem = {
  section: string;
  /** 中文名；未知 id 原样透出。 */
  label: string;
  status: "ok" | "error";
  message: string | null;
  durationMs: number | null;
};

const BOND_DASHBOARD_SECTION_LABELS = new Map<string, string>([
  ["headline-kpis", "首屏指标"],
  ["risk-indicators", "风险指标"],
  ["asset-structure", "资产结构(券种)"],
  ["asset-structure-rating", "资产结构(评级)"],
  ["asset-structure-portfolio-name", "资产结构(组合)"],
  ["asset-structure-tenor-bucket", "资产结构(期限)"],
  ["yield-distribution", "收益率分布"],
  ["portfolio-comparison", "组合对比"],
  ["spread-analysis", "利差分析"],
  ["maturity-structure", "期限结构"],
  ["industry-distribution", "行业分布"],
  ["business-type-metrics", "业务类型指标"],
]);

export function buildBondDashboardSectionStatusItems(
  bundle: ApiEnvelope<BondDashboardBundlePayload> | undefined,
): BondDashboardSectionStatusItem[] {
  if (!bundle) return [];
  const sectionStatuses: Partial<Record<string, BondDashboardBundleSectionStatus>> =
    bundle.result.section_statuses ?? {};
  const statusMap = new Map(Object.entries(sectionStatuses));
  const failedSections = new Set<string>(bundle.result.failed_sections ?? []);

  // 页面既定分区顺序优先；不在其中的分区（未知/超集 id）按出现顺序附在其后。
  const orderedSections: string[] = [...BOND_DASHBOARD_PAGE_BUNDLE_SECTIONS];
  for (const section of [...statusMap.keys(), ...failedSections]) {
    if (!orderedSections.includes(section)) orderedSections.push(section);
  }

  const items: BondDashboardSectionStatusItem[] = [];
  for (const section of orderedSections) {
    const status = statusMap.get(section);
    if (status) {
      items.push({
        section,
        label: BOND_DASHBOARD_SECTION_LABELS.get(section) ?? section,
        status: status.status,
        message: status.message,
        durationMs: status.duration_ms ?? null,
      });
    } else if (failedSections.has(section)) {
      items.push({
        section,
        label: BOND_DASHBOARD_SECTION_LABELS.get(section) ?? section,
        status: "error",
        message: null,
        durationMs: null,
      });
    }
  }
  return items;
}
