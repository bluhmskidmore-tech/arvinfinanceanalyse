/**
 * /positions 页面视图模型层：纯函数 + 类型，不引入 React/antd。
 *
 * - 只做映射与展示格式化；金额/利率沿用后端 Decimal string 经
 *   `formatAmountYi` / `formatRatePercent` 格式化，不做任何正式金融计算。
 * - `formatCoverageSummary` … `topRatingItem` 等迁移函数与
 *   `components/PositionsView.tsx` 中现存实现逐字一致（文案与判定顺序被
 *   PositionsView 系列 Vitest 精确锁定）；角色 5 重写视图时删除旧实现并
 *   改从本模块 import。
 * - 缺失值一律 `EM_DASH`；`"0"` 是真实零，必须保留为 `0.00 亿元` / `0.00%`。
 */
import type {
  CounterpartyStatsResponse,
  InterbankCounterpartySplitResponse,
  RateCoverage,
  RatingStatsResponse,
  ResultMeta,
} from "../../../api/contracts";
import { EM_DASH, type LabeledValue } from "../../../pageModel";
import { formatAmountYi, formatRatePercent } from "../utils/format";

/** 页面主 Tab：债券持仓 / 同业持仓。 */
export type PositionsTabKey = "bonds" | "interbank";

// ---------------------------------------------------------------------------
// 展示格式化（迁移自 PositionsView.tsx，行为逐字一致）
// ---------------------------------------------------------------------------

export function formatCoverageSummary(coverage: RateCoverage | null | undefined): string {
  if (!coverage) {
    return EM_DASH;
  }
  const missing =
    coverage.missing_count > 0
      ? `，缺 ${coverage.missing_count} 笔 / ${formatAmountYi(coverage.missing_amount)}`
      : "";
  return `${coverage.coverage_ratio}%${missing}`;
}

export function rateCoveragePolicyLabel(policy: string | null | undefined): string {
  if (policy === "exclude_missing_rate_from_denominator") {
    return "缺失利率剔除分母";
  }
  return policy || EM_DASH;
}

export function compactVersion(value: string | null | undefined): string {
  if (!value) {
    return EM_DASH;
  }
  return value.length > 18 ? `${value.slice(0, 15)}…` : value;
}

export function metaSummary(meta: ResultMeta | null | undefined): string {
  if (!meta) {
    return EM_DASH;
  }
  return `${meta.quality_flag} / ${compactVersion(meta.source_version)} / ${compactVersion(meta.rule_version)}`;
}

// ---------------------------------------------------------------------------
// 主列表信封归一化与首屏状态（迁移自 PositionsView.tsx，行为逐字一致）
// ---------------------------------------------------------------------------

export type PositionsFirstScreenStatus = {
  type: "error" | "warning" | "info";
  message: string;
  description: string;
};

export type PositionsPrimaryListTableState = "loading" | "error" | "blocked" | "empty" | "ready";

export type PositionsPrimaryListMeta = Pick<
  ResultMeta,
  | "quality_flag"
  | "vendor_status"
  | "fallback_mode"
  | "requested_report_date"
  | "resolved_report_date"
  | "as_of_date"
  | "fallback_date"
>;

export type PositionsPrimaryListResult<T> = {
  items: T[];
  total: number;
  page: number;
  page_size: number;
};

export type PositionsPrimaryListEnvelope<T> = {
  result_meta: PositionsPrimaryListMeta;
  result: PositionsPrimaryListResult<T>;
};

export const POSITIONS_QUALITY_FLAGS: readonly ResultMeta["quality_flag"][] = [
  "ok",
  "warning",
  "error",
  "stale",
  "missing",
];
export const POSITIONS_VENDOR_STATUSES: readonly ResultMeta["vendor_status"][] = [
  "ok",
  "vendor_stale",
  "vendor_unavailable",
];
export const POSITIONS_FALLBACK_MODES: readonly ResultMeta["fallback_mode"][] = [
  "none",
  "latest_snapshot",
];

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

export function isAllowedStatus<T extends string>(
  value: unknown,
  allowed: readonly T[],
): value is T {
  return typeof value === "string" && (allowed as readonly string[]).includes(value);
}

export function isOptionalDate(value: unknown): value is string | null | undefined {
  return value === undefined || value === null || typeof value === "string";
}

/** 主列表信封 fail-closed 归一化：缺字段/非法状态/非法分页一律返回 null。 */
export function normalizePositionsPrimaryListEnvelope<T>(
  value: unknown,
): PositionsPrimaryListEnvelope<T> | null {
  if (!isRecord(value) || !isRecord(value.result_meta) || !isRecord(value.result)) {
    return null;
  }

  const meta = value.result_meta;
  const result = value.result;
  const qualityFlag = meta.quality_flag;
  const vendorStatus = meta.vendor_status;
  const fallbackMode = meta.fallback_mode;
  if (
    !isAllowedStatus(qualityFlag, POSITIONS_QUALITY_FLAGS) ||
    !isAllowedStatus(vendorStatus, POSITIONS_VENDOR_STATUSES) ||
    !isAllowedStatus(fallbackMode, POSITIONS_FALLBACK_MODES) ||
    !isOptionalDate(meta.requested_report_date) ||
    !isOptionalDate(meta.resolved_report_date) ||
    !isOptionalDate(meta.as_of_date) ||
    !isOptionalDate(meta.fallback_date)
  ) {
    return null;
  }

  const { items, total, page, page_size: pageSize } = result;
  if (
    !Array.isArray(items) ||
    typeof total !== "number" ||
    !Number.isFinite(total) ||
    !Number.isInteger(total) ||
    total < 0 ||
    typeof page !== "number" ||
    !Number.isInteger(page) ||
    page < 1 ||
    typeof pageSize !== "number" ||
    !Number.isInteger(pageSize) ||
    pageSize < 1
  ) {
    return null;
  }

  return {
    result_meta: {
      quality_flag: qualityFlag,
      vendor_status: vendorStatus,
      fallback_mode: fallbackMode,
      requested_report_date: meta.requested_report_date,
      resolved_report_date: meta.resolved_report_date,
      as_of_date: meta.as_of_date,
      fallback_date: meta.fallback_date,
    },
    result: {
      items: items as T[],
      total,
      page,
      page_size: pageSize,
    },
  };
}

export function buildPositionsPrimaryListTableState({
  reportDate,
  datesLoading,
  datesError,
  listLoading,
  listSuccess,
  listError,
  envelope,
}: {
  reportDate: string;
  datesLoading: boolean;
  datesError: boolean;
  listLoading: boolean;
  listSuccess: boolean;
  listError: boolean;
  envelope: PositionsPrimaryListEnvelope<unknown> | null;
}): PositionsPrimaryListTableState {
  if (!reportDate) {
    if (datesLoading) {
      return "loading";
    }
    return datesError ? "error" : "blocked";
  }

  if (listError) {
    return "error";
  }
  if (listLoading || !listSuccess) {
    return "loading";
  }

  if (!envelope) {
    return "error";
  }
  if (envelope.result.total === 0 && envelope.result.items.length === 0) {
    return "empty";
  }
  if (envelope.result.items.length === 0) {
    return "blocked";
  }
  return "ready";
}

export function buildPositionsFirstScreenStatus({
  tab,
  datesError,
  datesEmpty,
  listError,
  listTableState,
  meta,
}: {
  tab: PositionsTabKey;
  datesError: boolean;
  datesEmpty: boolean;
  listError: boolean;
  listTableState: PositionsPrimaryListTableState;
  meta: PositionsPrimaryListMeta | undefined;
}): PositionsFirstScreenStatus | null {
  const listLabel = tab === "bonds" ? "债券持仓" : "同业持仓";

  if (datesError) {
    return {
      type: "error",
      message: "可用报告日加载失败",
      description: "当前无法确定持仓报告日，请稍后重试。",
    };
  }

  if (listError) {
    return {
      type: "error",
      message: `${listLabel}加载失败`,
      description: "持仓请求未成功，请稍后重试。",
    };
  }

  if (listTableState === "error") {
    return {
      type: "error",
      message: `${listLabel}响应不完整`,
      description: "当前返回内容缺少必要的数据或状态信息，请稍后重试。",
    };
  }

  if (meta?.quality_flag === "error" || meta?.vendor_status === "vendor_unavailable") {
    return {
      type: "error",
      message: `${listLabel}数据当前不可用`,
      description: "当前返回结果未达到可用状态，请稍后重试。",
    };
  }

  if (datesEmpty) {
    return {
      type: "info",
      message: "暂无可用报告日",
      description: "当前无法查询持仓数据。",
    };
  }

  if (listTableState === "empty") {
    return {
      type: "info",
      message: `当前报告日暂无${listLabel}数据`,
      description: "可调整报告日或筛选条件后重试。",
    };
  }

  const stale = meta?.quality_flag === "stale" || meta?.vendor_status === "vendor_stale";
  if (meta?.fallback_mode === "latest_snapshot") {
    const dateDetails = [
      meta.requested_report_date ? `请求日期 ${meta.requested_report_date}` : null,
      meta.resolved_report_date ? `解析日期 ${meta.resolved_report_date}` : null,
      meta.as_of_date ? `有效日期 ${meta.as_of_date}` : null,
      meta.fallback_date ? `回退日期 ${meta.fallback_date}` : null,
    ].filter((item): item is string => Boolean(item));
    return {
      type: "warning",
      message: stale
        ? `${listLabel}已回退至最近可用快照，且该快照可能偏旧`
        : `${listLabel}已回退到最近可用快照`,
      description:
        dateDetails.length > 0
          ? `${dateDetails.join("，")}。`
          : "当前使用最近可用快照，请确认数据日期后使用。",
    };
  }

  if (stale) {
    const effectiveDate = meta.as_of_date || meta.resolved_report_date || meta.fallback_date;
    return {
      type: "warning",
      message: `${listLabel}数据可能偏旧`,
      description: effectiveDate
        ? `有效日期 ${effectiveDate}，请确认后使用。`
        : "当前数据可能滞后，请确认日期后使用。",
    };
  }

  return null;
}

export function topRatingItem(items: RatingStatsResponse["items"] | undefined) {
  if (!items?.length) {
    return null;
  }
  return items.reduce((best, item) =>
    Number(item.percentage) > Number(best.percentage) ? item : best,
  );
}

// ---------------------------------------------------------------------------
// KPI 横带（首屏业务读数，非筛选回显）
// ---------------------------------------------------------------------------

const BONDS_KPI_CELLS = [
  { key: "avg-daily", label: "日均合计" },
  { key: "range-total", label: "区间累计" },
  { key: "weighted-rate", label: "加权收益率" },
  { key: "coupon-rate", label: "加权付息率" },
  { key: "customers", label: "客户数" },
  { key: "cr10", label: "CR10 集中度" },
] as const;

const INTERBANK_KPI_CELLS = [
  { key: "asset-avg", label: "资产端日均" },
  { key: "asset-rate", label: "资产端加权利率" },
  { key: "asset-customers", label: "资产端户数" },
  { key: "liability-avg", label: "负债端日均" },
  { key: "liability-rate", label: "负债端加权利率" },
  { key: "liability-customers", label: "负债端户数" },
] as const;

/** loading 置 status="loading"；非 loading 无数据则 status 留空。tone 一律不设。 */
function kpiBandPlaceholders(
  cells: ReadonlyArray<{ readonly key: string; readonly label: string }>,
  loading: boolean,
): LabeledValue[] {
  return cells.map((cell) =>
    loading
      ? { key: cell.key, label: cell.label, value: EM_DASH, status: "loading" }
      : { key: cell.key, label: cell.label, value: EM_DASH },
  );
}

/**
 * 债券 KPI 横带（6 格），数据源 /api/positions/counterparty/bonds。
 * `"0"` 金额是真实零（`0.00 亿元`），只有 null/undefined 才 EM_DASH。
 */
export function buildPositionsBondsKpiBand(input: {
  stats: CounterpartyStatsResponse | undefined;
  loading: boolean;
}): LabeledValue[] {
  const { stats, loading } = input;
  if (loading || !stats) {
    return kpiBandPlaceholders(BONDS_KPI_CELLS, loading);
  }
  const [avgDaily, rangeTotal, weightedRate, couponRate, customers, cr10] = BONDS_KPI_CELLS;
  return [
    {
      ...avgDaily,
      value: formatAmountYi(stats.total_avg_daily),
      ...(stats.num_days != null ? { note: `分母 ${stats.num_days} 天` } : {}),
    },
    { ...rangeTotal, value: formatAmountYi(stats.total_amount) },
    {
      ...weightedRate,
      value: stats.total_weighted_rate ? formatRatePercent(stats.total_weighted_rate) : EM_DASH,
    },
    {
      ...couponRate,
      value: stats.total_weighted_coupon_rate
        ? formatRatePercent(stats.total_weighted_coupon_rate)
        : EM_DASH,
    },
    {
      ...customers,
      value: stats.total_customers != null ? `${stats.total_customers} 户` : EM_DASH,
    },
    { ...cr10, value: stats.cr10_ratio ?? EM_DASH },
  ];
}

/**
 * 同业 KPI 横带（6 格），数据源 /api/positions/counterparty/interbank/split。
 * 语义与债券横带一致：真实零保留，缺失才 EM_DASH。
 */
export function buildPositionsInterbankKpiBand(input: {
  split: InterbankCounterpartySplitResponse | undefined;
  loading: boolean;
}): LabeledValue[] {
  const { split, loading } = input;
  if (loading || !split) {
    return kpiBandPlaceholders(INTERBANK_KPI_CELLS, loading);
  }
  const [assetAvg, assetRate, assetCustomers, liabilityAvg, liabilityRate, liabilityCustomers] =
    INTERBANK_KPI_CELLS;
  return [
    {
      ...assetAvg,
      value: formatAmountYi(split.asset_total_avg_daily),
      ...(split.num_days != null ? { note: `分母 ${split.num_days} 天` } : {}),
    },
    {
      ...assetRate,
      value: split.asset_total_weighted_rate
        ? formatRatePercent(split.asset_total_weighted_rate)
        : EM_DASH,
    },
    { ...assetCustomers, value: `${split.asset_customer_count} 户` },
    { ...liabilityAvg, value: formatAmountYi(split.liability_total_avg_daily) },
    {
      ...liabilityRate,
      value: split.liability_total_weighted_rate
        ? formatRatePercent(split.liability_total_weighted_rate)
        : EM_DASH,
    },
    { ...liabilityCustomers, value: `${split.liability_customer_count} 户` },
  ];
}

// ---------------------------------------------------------------------------
// 口径行
// ---------------------------------------------------------------------------

/**
 * 首屏口径行条目（顺序固定）。「当前：债券持仓」等字符串被现有
 * data-status 契约测试锁定，不得改动。
 */
export function buildPositionsCaliberItems(input: {
  tab: PositionsTabKey;
  reportDate: string;
  startDate: string | null;
  endDate: string | null;
  scopeLabel: string;
  peerFilterLabel: string;
}): string[] {
  return [
    `报表日：${input.reportDate || EM_DASH}`,
    `区间：${input.startDate || EM_DASH} ~ ${input.endDate || EM_DASH}`,
    "数据来源：ZQTZ + TYWL",
    "日均分母=有数据 report_date 数",
    input.tab === "bonds" ? "当前：债券持仓" : "当前：同业持仓",
    input.scopeLabel,
    input.peerFilterLabel,
  ];
}
