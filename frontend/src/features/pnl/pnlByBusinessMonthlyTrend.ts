import type { PnlByBusinessMonthlyBucket } from "../../api/contracts";

const YUAN_PER_WAN = 10_000;
const YUAN_PER_YI = 100_000_000;

export type PnlByBusinessTrendSelection = {
  row_key: string;
  business_type: string;
};

export type PnlByBusinessTrendPeriod = {
  periodStartDate?: string | null;
  periodEndDate?: string | null;
};

export type PnlByBusinessMonthlyTrendPoint = {
  monthKey: string;
  periodStartDate: string;
  periodEndDate: string;
  bucketAvailable: boolean;
  coverageDays: number | null;
  expectedDays: number | null;
  sampleFilled: boolean;
  rowAvailable: boolean;
  avgBalanceYi: number | null;
  currentBalanceYi: number | null;
  totalPnlWan: number | null;
  ftpNetPnlWan: number | null;
  annualizedYieldPct: number | null;
  ftpRatePct: number | null;
  ftpNetAnnualizedYieldPct: number | null;
};

export type PnlByBusinessMonthlyTrendModel = {
  businessKey: string | null;
  businessLabel: string;
  points: PnlByBusinessMonthlyTrendPoint[];
  availablePointCount: number;
  missingBucketMonths: string[];
  missingRowMonths: string[];
  coverageWarningMonths: string[];
};

function finiteNumber(raw: string | number | null | undefined): number | null {
  if (raw === null || raw === undefined || (typeof raw === "string" && raw.trim() === "")) {
    return null;
  }
  const value = Number(raw);
  return Number.isFinite(value) ? value : null;
}

function convertYuan(raw: string | number | null | undefined, divisor: number): number | null {
  const value = finiteNumber(raw);
  return value === null ? null : value / divisor;
}

function hasCoverageWarning(month: PnlByBusinessMonthlyBucket): boolean {
  const coverageDays = finiteNumber(month.coverage_days);
  const expectedDays = finiteNumber(month.expected_days ?? month.calendar_days);
  return month.sample_filled === true ||
    (coverageDays !== null && expectedDays !== null && coverageDays < expectedDays);
}

function parseMonthKey(monthKey: string): { year: number; month: number } | null {
  const match = /^(\d{4})-(\d{2})$/.exec(monthKey);
  if (!match) return null;
  const year = Number(match[1]);
  const month = Number(match[2]);
  return month >= 1 && month <= 12 ? { year, month } : null;
}

function monthKeyFromDate(raw: string | null | undefined): string | null {
  const monthKey = raw?.slice(0, 7) ?? "";
  return parseMonthKey(monthKey) ? monthKey : null;
}

function buildContinuousMonthKeys(
  months: PnlByBusinessMonthlyBucket[],
  period: PnlByBusinessTrendPeriod,
): string[] {
  if (months.length === 0 && (!period.periodStartDate || !period.periodEndDate)) return [];
  const parsed = months.map((month) => parseMonthKey(month.month_key));
  if (parsed.some((value) => value === null)) {
    return months.map((month) => month.month_key);
  }
  const periodStartKey = monthKeyFromDate(period.periodStartDate);
  const periodEndKey = monthKeyFromDate(period.periodEndDate);
  const first = (periodStartKey ? parseMonthKey(periodStartKey) : null) ?? parsed[0];
  const last = (periodEndKey ? parseMonthKey(periodEndKey) : null) ?? parsed[parsed.length - 1];
  if (!first || !last) return months.map((month) => month.month_key);
  const firstIndex = first.year * 12 + first.month - 1;
  const lastIndex = last.year * 12 + last.month - 1;
  if (lastIndex < firstIndex) return months.map((month) => month.month_key);
  return Array.from({ length: lastIndex - firstIndex + 1 }, (_, offset) => {
    const index = firstIndex + offset;
    const year = Math.floor(index / 12);
    const month = (index % 12) + 1;
    return `${year}-${String(month).padStart(2, "0")}`;
  });
}

export function buildSelectedBusinessMonthlyTrend(
  months: PnlByBusinessMonthlyBucket[],
  selectedBusiness: PnlByBusinessTrendSelection | undefined,
  period: PnlByBusinessTrendPeriod = {},
): PnlByBusinessMonthlyTrendModel {
  if (!selectedBusiness?.row_key) {
    return {
      businessKey: null,
      businessLabel: "未选择业务",
      points: [],
      availablePointCount: 0,
      missingBucketMonths: [],
      missingRowMonths: [],
      coverageWarningMonths: [],
    };
  }

  const orderedMonths = [...months].sort((left, right) => {
    const leftKey = left.period_end_date || left.month_key;
    const rightKey = right.period_end_date || right.month_key;
    return leftKey.localeCompare(rightKey);
  });
  const monthByKey = new Map(orderedMonths.map((month) => [month.month_key, month]));
  const monthKeys = buildContinuousMonthKeys(orderedMonths, period);
  const points = monthKeys.map<PnlByBusinessMonthlyTrendPoint>((monthKey) => {
    const month = monthByKey.get(monthKey);
    if (!month) {
      return {
        monthKey,
        periodStartDate: `${monthKey}-01`,
        periodEndDate: "",
        bucketAvailable: false,
        coverageDays: null,
        expectedDays: null,
        sampleFilled: false,
        rowAvailable: false,
        avgBalanceYi: null,
        currentBalanceYi: null,
        totalPnlWan: null,
        ftpNetPnlWan: null,
        annualizedYieldPct: null,
        ftpRatePct: null,
        ftpNetAnnualizedYieldPct: null,
      };
    }
    const row = month.items.find((item) => item.row_key === selectedBusiness.row_key);
    return {
      monthKey: month.month_key,
      periodStartDate: month.period_start_date,
      periodEndDate: month.period_end_date,
      bucketAvailable: true,
      coverageDays: finiteNumber(month.coverage_days),
      expectedDays: finiteNumber(month.expected_days ?? month.calendar_days),
      sampleFilled: month.sample_filled === true,
      rowAvailable: Boolean(row),
      avgBalanceYi: convertYuan(row?.avg_balance, YUAN_PER_YI),
      currentBalanceYi: convertYuan(row?.current_balance, YUAN_PER_YI),
      totalPnlWan: convertYuan(row?.total_pnl, YUAN_PER_WAN),
      ftpNetPnlWan: convertYuan(row?.ftp_net_pnl, YUAN_PER_WAN),
      annualizedYieldPct: finiteNumber(row?.annualized_yield_pct),
      ftpRatePct: finiteNumber(row?.ftp_rate_pct),
      ftpNetAnnualizedYieldPct: finiteNumber(row?.ftp_net_annualized_yield_pct),
    };
  });

  return {
    businessKey: selectedBusiness.row_key,
    businessLabel: selectedBusiness.business_type,
    points,
    availablePointCount: points.filter((point) => point.rowAvailable).length,
    missingBucketMonths: points.filter((point) => !point.bucketAvailable).map((point) => point.monthKey),
    missingRowMonths: points
      .filter((point) => point.bucketAvailable && !point.rowAvailable)
      .map((point) => point.monthKey),
    coverageWarningMonths: orderedMonths.filter(hasCoverageWarning).map((month) => month.month_key),
  };
}
