import type { ColumnsType } from "antd/es/table";
import { Link } from "react-router-dom";

import type {
  AdbComparisonResponse,
  AdbMonthlyBreakdownItem,
} from "../../../api/contracts";
import AdbComparisonChart, {
  type AdbComparisonChartRow,
} from "../../average-balance/components/AdbComparisonChart";
import { computeComparisonDeviationPct } from "../../average-balance/components/adbComparisonMetrics";
import AdbMonthlyBreakdownTable from "../../average-balance/components/AdbMonthlyBreakdownTable";
import AdbMonthlyHorizontalChart, {
  type AdbMonthlyHorizontalChartRow,
} from "../../average-balance/components/AdbMonthlyHorizontalChart";
import { PlaceholderCard } from "../../workbench/components/PlaceholderCard";
import { nocturneTokens } from "../../../theme/designSystem";
import { EM_DASH } from "../../../utils/format";

const YI = 100_000_000;

function formatYiAmount(value: number | null) {
  if (value === null || Number.isNaN(value)) return EM_DASH;
  return value.toLocaleString("zh-CN", {
    maximumFractionDigits: 1,
    minimumFractionDigits: 1,
  });
}

/** null 表示上游缺数（区间日均不可用/期末缺数）：不参与除法，避免 null/YI 的伪零。 */
function toYiOrNull(value: number | null): number | null {
  return value === null ? null : value / YI;
}

const previewBreakdownColumns: ColumnsType<AdbMonthlyBreakdownItem> = [
  { dataIndex: "category", key: "category", title: "分类" },
  {
    align: "right",
    dataIndex: "avg_balance",
    key: "avg_balance",
    render: (value: number | null) => (value === null ? EM_DASH : (value / YI).toFixed(2)),
    title: "日均(亿元)",
  },
  {
    align: "right",
    dataIndex: "proportion",
    key: "proportion",
    render: (value: number | null | undefined) =>
      value === null || value === undefined ? EM_DASH : value.toFixed(2),
    title: "占比(%)",
  },
  {
    align: "right",
    dataIndex: "weighted_rate",
    key: "weighted_rate",
    render: (value: number | null | undefined) =>
      value === null || value === undefined ? EM_DASH : `${value.toFixed(2)}%`,
    title: "加权利率(%)",
  },
];

type AdbAnalyticalPreviewProps = {
  comparison: AdbComparisonResponse;
  href: string;
};

export default function AdbAnalyticalPreview({
  comparison,
  href,
}: AdbAnalyticalPreviewProps) {
  const comparisonAssetRows: AdbComparisonChartRow[] = comparison.assets_breakdown.map((item) => ({
    avg: item.avg_balance,
    deviationPct: computeComparisonDeviationPct(item.spot_balance, item.avg_balance),
    label: `资产 ${item.category}`,
    spot: item.spot_balance,
  }));
  const comparisonLiabilityRows: AdbComparisonChartRow[] = comparison.liabilities_breakdown.map((item) => ({
    avg: item.avg_balance,
    deviationPct: computeComparisonDeviationPct(item.spot_balance, item.avg_balance),
    label: `负债 ${item.category}`,
    spot: item.spot_balance,
  }));

  const monthlyRows: AdbMonthlyHorizontalChartRow[] = [
    {
      avgYi: toYiOrNull(comparison.total_spot_assets),
      category: "期末时点资产",
      weightedRate: comparison.asset_yield,
    },
    {
      avgYi: toYiOrNull(comparison.total_avg_assets),
      category: "日均资产",
      weightedRate: comparison.asset_yield,
    },
    {
      avgYi: toYiOrNull(comparison.total_spot_liabilities),
      category: "期末时点负债",
      weightedRate: comparison.liability_cost,
    },
    {
      avgYi: toYiOrNull(comparison.total_avg_liabilities),
      category: "日均负债",
      weightedRate: comparison.liability_cost,
    },
  ];

  const previewBreakdownRows: AdbMonthlyBreakdownItem[] = [
    {
      avg_balance: comparison.total_avg_assets,
      category: "ADB 资产",
      proportion:
        comparison.total_avg_assets === null ? null : comparison.total_avg_assets > 0 ? 100 : 0,
      weighted_rate: comparison.asset_yield,
    },
    {
      avg_balance: comparison.total_avg_liabilities,
      category: "ADB 负债",
      proportion:
        comparison.total_avg_liabilities === null
          ? null
          : comparison.total_avg_liabilities > 0
            ? 100
            : 0,
      weighted_rate: comparison.liability_cost,
    },
  ];

  return (
    <div data-testid="balance-analysis-adb-preview" style={{ display: "grid", gap: 12 }}>
      <strong style={{ color: "var(--dh-api-ink)", fontSize: 14 }}>日均分析预览</strong>
      <div style={{ color: "var(--dh-api-soft)", fontSize: 13 }}>
        基于当前正式报告日生成的分析口径区间预览，默认观察年初至报告日的日均偏离与净息差。
      </div>
      <div
        style={{
          display: "grid",
          gap: 12,
          gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
        }}
      >
        <PlaceholderCard
          detail={`区间起点 ${comparison.start_date}`}
          title="期末时点资产"
          value={formatYiAmount(toYiOrNull(comparison.total_spot_assets))}
        />
        <PlaceholderCard
          detail={`区间终点 ${comparison.end_date}`}
          title="日均资产"
          value={formatYiAmount(toYiOrNull(comparison.total_avg_assets))}
        />
        <PlaceholderCard
          detail={`${comparison.num_days} 天`}
          title="期末时点负债"
          value={formatYiAmount(toYiOrNull(comparison.total_spot_liabilities))}
        />
        <PlaceholderCard
          detail="分析预览"
          title="NIM"
          value={
            comparison.net_interest_margin === null
              ? EM_DASH
              : `${comparison.net_interest_margin.toFixed(2)}%`
          }
        />
      </div>
      <div>
        <div style={{ color: "var(--dh-api-ink)", fontSize: 13, fontWeight: 600, marginBottom: 8 }}>
          期末时点与日均偏离对比
        </div>
        <div style={{ color: "var(--dh-api-soft)", fontSize: 12, marginBottom: 6 }}>资产</div>
        <AdbComparisonChart height={280} rows={comparisonAssetRows} />
        <div style={{ color: "var(--dh-api-soft)", fontSize: 12, margin: "12px 0 6px" }}>负债</div>
        <AdbComparisonChart height={280} rows={comparisonLiabilityRows} />
      </div>
      <div>
        <div style={{ color: "var(--dh-api-ink)", fontSize: 13, fontWeight: 600, marginBottom: 8 }}>
          日均月度结构预览
        </div>
        <AdbMonthlyHorizontalChart
          color={nocturneTokens.color.blue}
          height={280}
          rows={monthlyRows}
          title="当前区间资产负债结构"
        />
        <AdbMonthlyBreakdownTable
          columns={previewBreakdownColumns}
          rowKeyPrefix="adb-preview"
          rows={previewBreakdownRows}
        />
      </div>
      <div>
        <Link to={href}>打开日均分析页</Link>
      </div>
    </div>
  );
}
