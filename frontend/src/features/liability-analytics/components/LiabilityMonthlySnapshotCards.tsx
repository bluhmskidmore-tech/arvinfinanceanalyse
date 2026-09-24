import type { Numeric } from "../../../api/contracts";
import type { LiabilitiesMonthlyItem } from "../../../api/liabilityAdbContracts";
import { isNumeric } from "../../../api/numeric";
import { EM_DASH, formatNumeric } from "../../../utils/format";

function dispNumeric(n: Numeric | null | undefined): string {
  if (!n || !isNumeric(n)) {
    return EM_DASH;
  }
  return formatNumeric(n);
}

/** 月度概览读数：单框 4×2 横带（月日均 6 格 + 年初至今 2 格），分区帧由页面 01 区持有。 */
export function LiabilityMonthlySnapshotCards({
  month,
  ytdAvgTotalLiabilities,
  ytdAvgLiabilityCost,
}: {
  month: LiabilitiesMonthlyItem | null;
  ytdAvgTotalLiabilities: Numeric | null;
  ytdAvgLiabilityCost: Numeric | null;
}) {
  if (!month) {
    return null;
  }

  const cells: Array<{ key: string; label: string; value: string }> = [
    { key: "total", label: "总负债（月日均）", value: dispNumeric(month.avg_total_liabilities) },
    { key: "interbank", label: "同业负债（月日均）", value: dispNumeric(month.avg_interbank_liabilities) },
    { key: "issued", label: "发行负债（月日均）", value: dispNumeric(month.avg_issued_liabilities) },
    { key: "cost", label: "负债付息率", value: dispNumeric(month.avg_liability_cost) },
    { key: "mom", label: "环比变动（额）", value: dispNumeric(month.mom_change) },
    { key: "mom-pct", label: "环比变动（%）", value: dispNumeric(month.mom_change_pct) },
    { key: "ytd-total", label: "年初至今日均总负债", value: dispNumeric(ytdAvgTotalLiabilities) },
    { key: "ytd-cost", label: "年初至今平均负债成本", value: dispNumeric(ytdAvgLiabilityCost) },
  ];

  return (
    <>
      <p className="liability-caption">数值均来自治理后的数值对象（展示以后端下发显示值为准）。</p>
      <div className="liability-kpi-band" data-cols="4">
        {cells.map((cell) => (
          <div key={cell.key} className="liability-kpi-cell">
            <span className="liability-kpi-cell__label" title={cell.label}>
              {cell.label}
            </span>
            <span className="liability-kpi-cell__value">{cell.value}</span>
          </div>
        ))}
      </div>
    </>
  );
}
