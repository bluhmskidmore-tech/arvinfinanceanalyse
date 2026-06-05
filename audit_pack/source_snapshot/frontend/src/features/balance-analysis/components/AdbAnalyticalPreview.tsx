import type { ColumnsType } from "antd/es/table";
import { Link } from "react-router-dom";

import type {
  AdbComparisonResponse,
  AdbMonthlyBreakdownItem,
} from "../../../api/contracts";
import AdbComparisonChart, {
  type AdbComparisonChartRow,
} from "../../average-balance/components/AdbComparisonChart";
import AdbMonthlyBreakdownTable from "../../average-balance/components/AdbMonthlyBreakdownTable";
import AdbMonthlyHorizontalChart from "../../average-balance/components/AdbMonthlyHorizontalChart";
import { PlaceholderCard } from "../../workbench/components/PlaceholderCard";

const YI = 100_000_000;

function formatYiAmount(value: number) {
  return value.toLocaleString("zh-CN", {
    maximumFractionDigits: 1,
    minimumFractionDigits: 1,
  });
}

const previewBreakdownColumns: ColumnsType<AdbMonthlyBreakdownItem> = [
  { dataIndex: "category", key: "category", title: "分类" },
  {
    align: "right",
    dataIndex: "avg_balance",
    key: "avg_balance",
    render: (value: number) => (value / YI).toFixed(2),
    title: "日均(亿元)",
  },
  {
    align: "right",
    dataIndex: "proportion",
    key: "proportion",
    render: (value: number | null | undefined) =>
      value === null || value === undefined ? "—" : value.toFixed(2),
    title: "占比(%)",
  },
  {
    align: "right",
    dataIndex: "weighted_rate",
    key: "weighted_rate",
    render: (value: number | null | undefined) =>
      value === null || value === undefined ? "—" : `${value.toFixed(2)}%`,
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
  const comparisonRows: AdbComparisonChartRow[] = [
    ...comparison.assets_breakdown.map((item) => ({
      avg: item.avg_balance,
      deviationPct:
        item.avg_balance > 0
          ? ((item.spot_balance - item.avg_balance) / item.avg_balance) * 100
          : 0,
      label: `资产 ${item.category}`,
      spot: item.spot_balance,
    })),
    ...comparison.liabilities_breakdown.map((item) => ({
      avg: item.avg_balance,
      deviationPct:
        item.avg_balance > 0
          ? ((item.spot_balance - item.avg_balance) / item.avg_balance) * 100
          : 0,
      label: `负债 ${item.category}`,
      spot: item.spot_balance,
    })),
  ];

  const monthlyRows = [
    {
      avgYi: comparison.total_spot_assets / YI,
      category: "期末时点资产",
      weightedRate: comparison.asset_yield,
    },
    {
      avgYi: comparison.total_avg_assets / YI,
      category: "日均资产",
      weightedRate: comparison.asset_yield,
    },
    {
      avgYi: comparison.total_spot_liabilities / YI,
      category: "期末时点负债",
      weightedRate: comparison.liability_cost,
    },
    {
      avgYi: comparison.total_avg_liabilities / YI,
      category: "日均负债",
      weightedRate: comparison.liability_cost,
    },
  ];

  const previewBreakdownRows: AdbMonthlyBreakdownItem[] = [
    {
      avg_balance: comparison.total_avg_assets,
      category: "ADB 资产",
      proportion: comparison.total_avg_assets > 0 ? 100 : 0,
      weighted_rate: comparison.asset_yield,
    },
    {
      avg_balance: comparison.total_avg_liabilities,
      category: "ADB 负债",
      proportion: comparison.total_avg_liabilities > 0 ? 100 : 0,
      weighted_rate: comparison.liability_cost,
    },
  ];

  return (
    <div data-testid="balance-analysis-adb-preview" style={{ display: "grid", gap: 12 }}>
      <strong style={{ color: "#162033", fontSize: 14 }}>日均分析预览</strong>
      <div style={{ color: "#5c6b82", fontSize: 13 }}>
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
          value={formatYiAmount(comparison.total_spot_assets / YI)}
        />
        <PlaceholderCard
          detail={`区间终点 ${comparison.end_date}`}
          title="日均资产"
          value={formatYiAmount(comparison.total_avg_assets / YI)}
        />
        <PlaceholderCard
          detail={`${comparison.num_days} 天`}
          title="期末时点负债"
          value={formatYiAmount(comparison.total_spot_liabilities / YI)}
        />
        <PlaceholderCard
          detail="分析预览"
          title="NIM"
          value={
            comparison.net_interest_margin === null
              ? "—"
              : `${comparison.net_interest_margin.toFixed(2)}%`
          }
        />
      </div>
      <div>
        <div style={{ color: "#162033", fontSize: 13, fontWeight: 600, marginBottom: 8 }}>
          期末时点与日均偏离对比
        </div>
        <AdbComparisonChart height={320} rows={comparisonRows} />
      </div>
      <div>
        <div style={{ color: "#162033", fontSize: 13, fontWeight: 600, marginBottom: 8 }}>
          日均月度结构预览
        </div>
        <AdbMonthlyHorizontalChart
          color="#2563EB"
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
