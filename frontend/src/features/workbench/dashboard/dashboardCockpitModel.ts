import type { BondPortfolioHeadlinesPayload, Numeric } from "../../../api/contracts";
import { EM_DASH } from "../../../utils/format";

export type DashboardCockpitSectionStatus =
  | "landed"
  | "supplemental"
  | "stale"
  | "blocked"
  | "reserved"
  | "demo";

export type DashboardCockpitTone = "positive" | "negative" | "neutral" | "warning";

/** Risk-radar row shared by dashboard-home adapters. */
export type DashboardCockpitRiskItem = {
  id: string;
  label: string;
  value: string;
  hint: string;
  level: number;
  status: DashboardCockpitSectionStatus;
  tone: DashboardCockpitTone;
};

type NumericLike = Numeric | string | number | null | undefined;

const EMPTY_DISPLAY = EM_DASH;

function cleanDate(value: string | null | undefined): string {
  return value?.trim() ?? "";
}

function isSameReportDate(expected: string, actual: string | null | undefined): boolean {
  const expectedDate = cleanDate(expected);
  const actualDate = cleanDate(actual);
  return expectedDate.length > 0 && actualDate.length > 0 && expectedDate === actualDate;
}

function numericObject(value: NumericLike): Numeric | null {
  if (value == null || typeof value === "string" || typeof value === "number") {
    return null;
  }
  return value;
}

function numericRaw(value: NumericLike): number | null {
  if (value == null) {
    return null;
  }
  if (typeof value === "number") {
    return Number.isFinite(value) ? value : null;
  }
  if (typeof value === "string") {
    const parsed = Number(value.replace(/,/g, ""));
    return Number.isFinite(parsed) ? parsed : null;
  }
  const raw = value.raw;
  if (raw == null) {
    return null;
  }
  const parsed = typeof raw === "number" ? raw : Number(String(raw).replace(/,/g, ""));
  return Number.isFinite(parsed) ? parsed : null;
}

function formattedDisplay(value: NumericLike): string | null {
  const display = numericObject(value)?.display?.trim();
  return display && display.length > 0 ? display : null;
}

function formatWithCommas(value: number, digits: number): string {
  return value.toLocaleString("en-US", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function percentDisplay(value: NumericLike, fallback = EMPTY_DISPLAY): string {
  const display = formattedDisplay(value);
  if (display) return display;
  const raw = numericRaw(value);
  return raw == null ? fallback : `${formatWithCommas(raw * 100, 2)}%`;
}

function durationDisplay(value: NumericLike, fallback = EMPTY_DISPLAY): string {
  const display = formattedDisplay(value);
  if (display) return display;
  const raw = numericRaw(value);
  return raw == null ? fallback : formatWithCommas(raw, 2);
}

function dv01Display(value: NumericLike, fallback = EMPTY_DISPLAY): string {
  const raw = numericRaw(value);
  if (raw != null) {
    return `${formatWithCommas(raw / 10_000, 2)} 万`;
  }
  const display = formattedDisplay(value);
  return display ?? fallback;
}

function hasNumericValue(value: NumericLike): boolean {
  return numericRaw(value) !== null || formattedDisplay(value) !== null;
}

function clampPercent(value: number): number {
  return Math.max(0, Math.min(100, Math.round(value)));
}

function scaledLevel(value: NumericLike, maxRaw: number): number {
  const raw = numericRaw(value);
  if (raw == null || maxRaw <= 0) return 0;
  return clampPercent((Math.abs(raw) / maxRaw) * 100);
}

/**
 * 输入为 portfolio-headlines 的权重字段（issuer_top5_weight / credit_weight），
 * 后端契约为 unit="ratio" 的小数比率（占比 ∈ [0,1]），固定 ×100 得到 0–100 级别，
 * 不再使用 |x|<=1 启发式。
 */
function percentLevel(value: NumericLike): number {
  const raw = numericRaw(value);
  if (raw == null) return 0;
  return clampPercent(Math.abs(raw) * 100);
}

export function buildRiskItems(
  portfolio: BondPortfolioHeadlinesPayload | null | undefined,
  reportDate: string,
): DashboardCockpitRiskItem[] {
  const allowed = isSameReportDate(reportDate, portfolio?.report_date);
  if (!allowed || !portfolio) {
    return [
      {
        id: "portfolio-risk-blocked",
        label: "风险摘要",
        value: EMPTY_DISPLAY,
        hint: "风险读面报告日不一致或未返回。",
        level: 0,
        status: "blocked",
        tone: "warning",
      },
    ];
  }

  const hasRiskValues = [
    portfolio.total_dv01,
    portfolio.weighted_duration,
    portfolio.issuer_top5_weight,
    portfolio.credit_weight,
  ].some(hasNumericValue);

  if (!hasRiskValues) {
    return [
      {
        id: "portfolio-risk-empty",
        label: "风险摘要",
        value: EMPTY_DISPLAY,
        hint: "同日报告日已返回，但风险字段缺少可展示数值。",
        level: 0,
        status: "blocked",
        tone: "warning",
      },
    ];
  }

  return [
    {
      id: "dv01",
      label: "DV01",
      value: dv01Display(portfolio.total_dv01),
      hint: "元/1bp",
      level: scaledLevel(portfolio.total_dv01, 150_000_000),
      status: "supplemental",
      tone: "neutral",
    },
    {
      id: "duration",
      label: "久期",
      value: durationDisplay(portfolio.weighted_duration),
      hint: "组合加权",
      level: scaledLevel(portfolio.weighted_duration, 7),
      status: "supplemental",
      tone: "neutral",
    },
    {
      id: "issuer-top5",
      label: "发行人Top5",
      value: percentDisplay(portfolio.issuer_top5_weight),
      hint: "集中度",
      level: percentLevel(portfolio.issuer_top5_weight),
      status: "supplemental",
      tone: "warning",
    },
    {
      id: "credit-weight",
      label: "信用占比",
      value: percentDisplay(portfolio.credit_weight),
      hint: "资产结构",
      level: percentLevel(portfolio.credit_weight),
      status: "supplemental",
      tone: "neutral",
    },
  ];
}
