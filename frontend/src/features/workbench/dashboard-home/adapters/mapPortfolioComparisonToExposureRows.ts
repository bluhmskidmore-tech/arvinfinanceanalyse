import type { PortfolioComparisonPayload } from "../../../../api/contracts";
import { formatDv01Wan, formatYi, formatYears, nativeToNumber } from "../../../bond-dashboard/utils/format";
import type { HomeExposureRow } from "../dashboardHomeView";

const GAP = "—";

function formatWeightPct(partYuan: number, totalYuan: number): string {
  if (totalYuan <= 0) {
    return GAP;
  }
  const pct = (partYuan / totalYuan) * 100;
  return `${pct.toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}%`;
}

export function mapPortfolioComparisonToExposureRows(
  payload: PortfolioComparisonPayload | null | undefined,
  reportDate: string,
): { rows: readonly HomeExposureRow[]; hasData: boolean } {
  if (!payload || payload.report_date !== reportDate || payload.items.length === 0) {
    return { rows: [], hasData: false };
  }

  const totalMv = payload.items.reduce(
    (sum, item) => sum + nativeToNumber(item.total_market_value),
    0,
  );

  const rows: HomeExposureRow[] = payload.items.map((item, index) => {
    const mvYuan = nativeToNumber(item.total_market_value);
    return {
      id: `portfolio-${index}-${item.portfolio_name}`,
      account: item.portfolio_name?.trim() || GAP,
      type: "组合",
      assetScale: formatYi(item.total_market_value),
      weight: formatWeightPct(mvYuan, totalMv),
      duration: formatYears(item.weighted_duration),
      dv01: formatDv01Wan(item.total_dv01),
      dailyPnl: GAP,
      tone: "neutral",
    };
  });

  return { rows, hasData: rows.length > 0 };
}
