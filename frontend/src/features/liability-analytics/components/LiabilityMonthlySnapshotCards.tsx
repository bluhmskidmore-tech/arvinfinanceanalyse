import type { Numeric } from "../../../api/contracts";
import type { LiabilitiesMonthlySummaryItem } from "../../../api/liabilityAdbContracts";
import { isNumeric } from "../../../api/numeric";
import { EM_DASH, formatNumeric } from "../../../utils/format";
import { numericToYiNumeric } from "../utils/money";

function dispNumeric(n: Numeric | null | undefined): string {
  if (!n || !isNumeric(n)) {
    return EM_DASH;
  }
  return formatNumeric(n);
}

function dispYi(n: Numeric | null | undefined): string {
  const yiNumeric = numericToYiNumeric(n);
  return yiNumeric ? formatNumeric(yiNumeric).replace(" 亿", " 亿元") : EM_DASH;
}

/** 月度概览读数：单框 4×3 横带（月日均与期间变化 8 格 + 年初至今 2 个宽格），分区帧由页面 01 区持有。 */
export function LiabilityMonthlySnapshotCards({
  month,
  ytdAvgTotalLiabilities,
  ytdAvgLiabilityCost,
}: {
  month: LiabilitiesMonthlySummaryItem | null;
  ytdAvgTotalLiabilities: Numeric | null;
  ytdAvgLiabilityCost: Numeric | null;
}) {
  if (!month) {
    return null;
  }

  const cells: Array<{ key: string; label: string; value: string; wide?: boolean }> = [
    { key: "total", label: "总负债（月日均）", value: dispYi(month.avg_total_liabilities) },
    { key: "interbank", label: "同业负债（月日均）", value: dispYi(month.avg_interbank_liabilities) },
    { key: "issued", label: "发行负债（月日均）", value: dispYi(month.avg_issued_liabilities) },
    { key: "cost", label: "负债付息率", value: dispNumeric(month.avg_liability_cost) },
    { key: "mom", label: "环比变动（额）", value: dispYi(month.mom_change) },
    { key: "mom-pct", label: "环比变动（%）", value: dispNumeric(month.mom_change_pct) },
    { key: "yoy", label: "同比变动（额）", value: dispYi(month.yoy_change) },
    { key: "yoy-pct", label: "同比变动（%）", value: dispNumeric(month.yoy_change_pct) },
    { key: "ytd-total", label: "年初至今日均总负债", value: dispYi(ytdAvgTotalLiabilities), wide: true },
    { key: "ytd-cost", label: "年初至今平均负债成本", value: dispNumeric(ytdAvgLiabilityCost), wide: true },
  ];

  return (
    <>
      <p className="liability-caption">源值来自治理后的数值对象；金额统一按亿元展示，百分比保留后端精度。</p>
      <div className="liability-kpi-band" data-cols="4">
        {cells.map((cell) => (
          <div
            key={cell.key}
            className={`liability-kpi-cell${cell.wide ? " liability-kpi-cell--wide" : ""}`}
          >
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
