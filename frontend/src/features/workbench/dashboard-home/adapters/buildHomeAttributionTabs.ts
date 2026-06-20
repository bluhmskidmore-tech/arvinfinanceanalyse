import type {
  DailyChangesResult,
  Numeric,
  ProductCategoryMonthlyHeadlinePayload,
  ProductCategoryYtdHeadlinePayload,
} from "../../../../api/contracts";
import type { DashboardPnlAttributionVM } from "../../../executive-dashboard/adapters/executiveDashboardAdapter";
import type { HomeAttributionTab, HomeDeltaTone } from "../dashboardHomeView";

const GAP = "—";
const PENDING_SYNC = "待同步";

const TAB_SPECS: ReadonlyArray<{
  id: HomeAttributionTab["id"];
  label: string;
  period: "day" | "week" | "month" | null;
}> = [
  { id: "day", label: "日度", period: "day" },
  { id: "week", label: "周度", period: "week" },
  { id: "month", label: "月度", period: "month" },
  { id: "ytd", label: "YTD", period: null },
];

function isSameReportDate(expected: string, actual: string | null | undefined): boolean {
  return Boolean(expected && actual && expected.trim() === actual.trim());
}

function numericTone(value: Numeric | null | undefined): HomeDeltaTone {
  if (value?.raw == null || !Number.isFinite(value.raw)) {
    return "muted";
  }
  if (value.raw > 0) {
    return "up";
  }
  if (value.raw < 0) {
    return "down";
  }
  return "flat";
}

function findDailyChangePeriod(
  dailyChanges: DailyChangesResult | null | undefined,
  reportDate: string,
  period: "day" | "week" | "month",
) {
  if (!dailyChanges || !isSameReportDate(reportDate, dailyChanges.report_date)) {
    return null;
  }
  return dailyChanges.periods.find((row) => row.period === period) ?? null;
}

export function buildHomeAttributionTabs(input: {
  reportDate: string;
  attribution?: DashboardPnlAttributionVM | null;
  dailyChanges?: DailyChangesResult | null;
  productCategoryYtd?: ProductCategoryYtdHeadlinePayload | null;
  productCategoryMonthly?: ProductCategoryMonthlyHeadlinePayload | null;
}): readonly HomeAttributionTab[] {
  return TAB_SPECS.map((spec) => {
    if (spec.id === "ytd") {
      return {
        id: spec.id,
        label: spec.label,
        pnl: input.productCategoryYtd?.summary_pnl.display ?? GAP,
        change: input.productCategoryYtd?.summary_pnl_detail?.trim() || PENDING_SYNC,
        yield: GAP,
        changeTone: numericTone(input.productCategoryYtd?.summary_pnl),
      };
    }

    if (spec.id === "month") {
      const periodRow = findDailyChangePeriod(input.dailyChanges, input.reportDate, "month");
      return {
        id: spec.id,
        label: spec.label,
        pnl: input.productCategoryMonthly?.monthly_income.display ?? GAP,
        change: periodRow?.net_change.display ?? PENDING_SYNC,
        yield: GAP,
        changeTone: numericTone(periodRow?.net_change),
      };
    }

    if (spec.period) {
      const periodRow = findDailyChangePeriod(input.dailyChanges, input.reportDate, spec.period);
      const pnl =
        spec.id === "day"
          ? input.attribution?.total.display ?? GAP
          : periodRow?.net_change.display ?? GAP;
      return {
        id: spec.id,
        label: spec.label,
        pnl,
        change: periodRow?.net_change.display ?? PENDING_SYNC,
        yield: GAP,
        changeTone: numericTone(periodRow?.net_change),
      };
    }

    return {
      id: spec.id,
      label: spec.label,
      pnl: GAP,
      change: PENDING_SYNC,
      yield: GAP,
      changeTone: "muted" as const,
    };
  });
}
