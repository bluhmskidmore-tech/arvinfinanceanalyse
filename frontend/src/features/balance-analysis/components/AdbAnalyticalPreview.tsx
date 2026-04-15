import { Link } from "react-router-dom";

import type { AdbComparisonResponse } from "../../../api/contracts";
import { PlaceholderCard } from "../../workbench/components/PlaceholderCard";
import AdbComparisonChart, {
  type AdbComparisonChartRow,
} from "../../average-balance/components/AdbComparisonChart";
import AdbMonthlyHorizontalChart from "../../average-balance/components/AdbMonthlyHorizontalChart";

const YI = 100_000_000;

function formatYiAmount(value: number) {
  return value.toLocaleString("zh-CN", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  });
}

type AdbAnalyticalPreviewProps = {
  comparison: AdbComparisonResponse;
  href: string;
};

export default function AdbAnalyticalPreview({
  comparison,
  href,
}: AdbAnalyticalPreviewProps) {
  const rows: AdbComparisonChartRow[] = [
    ...comparison.assets_breakdown.map((item) => ({
      label: `资产 ${item.category}`,
      spot: item.spot_balance,
      avg: item.avg_balance,
      deviationPct:
        item.avg_balance > 0
          ? ((item.spot_balance - item.avg_balance) / item.avg_balance) * 100
          : 0,
    })),
    ...comparison.liabilities_breakdown.map((item) => ({
      label: `负债 ${item.category}`,
      spot: item.spot_balance,
      avg: item.avg_balance,
      deviationPct:
        item.avg_balance > 0
          ? ((item.spot_balance - item.avg_balance) / item.avg_balance) * 100
          : 0,
    })),
  ];
  const monthlyRows = [
    { category: "Spot 资产", avgYi: comparison.total_spot_assets / YI, weightedRate: comparison.asset_yield },
    { category: "ADB 资产", avgYi: comparison.total_avg_assets / YI, weightedRate: comparison.asset_yield },
    { category: "Spot 负债", avgYi: comparison.total_spot_liabilities / YI, weightedRate: comparison.liability_cost },
    { category: "ADB 负债", avgYi: comparison.total_avg_liabilities / YI, weightedRate: comparison.liability_cost },
  ];

  return (
    <div data-testid="balance-analysis-adb-preview" style={{ display: "grid", gap: 12 }}>
      <strong style={{ color: "#162033", fontSize: 14 }}>ADB Analytical Preview</strong>
      <div style={{ color: "#5c6b82", fontSize: 13 }}>
        基于当前正式报告日生成的 analytical 区间预览，默认观察年初至报告日的 ADB 偏离与净息差。
      </div>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
          gap: 12,
        }}
      >
        <PlaceholderCard
          title="Spot 资产"
          value={formatYiAmount(comparison.total_spot_assets / YI)}
          detail={`区间起点 ${comparison.start_date}`}
        />
        <PlaceholderCard
          title="ADB 资产"
          value={formatYiAmount(comparison.total_avg_assets / YI)}
          detail={`区间终点 ${comparison.end_date}`}
        />
        <PlaceholderCard
          title="Spot 负债"
          value={formatYiAmount(comparison.total_spot_liabilities / YI)}
          detail={`${comparison.num_days} 天`}
        />
        <PlaceholderCard
          title="NIM"
          value={
            comparison.net_interest_margin === null
              ? "—"
              : `${comparison.net_interest_margin.toFixed(2)}%`
          }
          detail="Analytical preview"
        />
      </div>
      <div>
        <div style={{ color: "#162033", fontSize: 13, fontWeight: 600, marginBottom: 8 }}>
          Spot vs ADB 偏离对比
        </div>
        <AdbComparisonChart rows={rows} height={320} />
      </div>
      <div>
        <div style={{ color: "#162033", fontSize: 13, fontWeight: 600, marginBottom: 8 }}>
          ADB 月度结构预览
        </div>
        <AdbMonthlyHorizontalChart rows={monthlyRows} title="当前区间资产负债结构" color="#2563EB" height={280} />
      </div>
      <div>
        <Link to={href}>打开 ADB 分析页</Link>
      </div>
    </div>
  );
}
