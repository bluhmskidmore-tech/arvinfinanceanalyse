import { Alert, Button, Card } from "antd";

import type { Numeric, RiskIndicatorsPayload } from "../../../api/contracts";
import { formatDv01Wan, formatRatePercent, formatYears, formatYi, nativeToNumber } from "../utils/format";

function withUnit(value: string, unit: string): string {
  const separator = unit === "%" ? "" : " ";
  return value === "—" ? "—" : `${value}${separator}${unit}`;
}

function formatConvexity(value: Numeric | null | undefined): string {
  const raw = nativeToNumber(value);
  return raw === null ? "—" : raw.toFixed(4);
}

const ROWS: {
  label: string;
  key: keyof RiskIndicatorsPayload;
  format: (v: Numeric | null | undefined) => string;
}[] = [
  { label: "组合市值", key: "total_market_value", format: (v) => withUnit(formatYi(v), "亿") },
  { label: "DV01", key: "total_dv01", format: (v) => withUnit(formatDv01Wan(v), "万元") },
  { label: "加权久期", key: "weighted_duration", format: (v) => withUnit(formatYears(v), "年") },
  { label: "信用占比", key: "credit_ratio", format: (v) => withUnit(formatRatePercent(v), "%") },
  { label: "凸性(加权)", key: "weighted_convexity", format: formatConvexity },
  { label: "利差 DV01", key: "total_spread_dv01", format: (v) => withUnit(formatDv01Wan(v), "万元") },
  { label: "1年内再投资占比", key: "reinvestment_ratio_1y", format: (v) => withUnit(formatRatePercent(v), "%") },
];

export function RiskIndicatorsPanel({
  data,
  loading,
}: {
  data: RiskIndicatorsPayload | undefined;
  loading: boolean;
}) {
  return (
    <Card
      data-testid="bond-dashboard-risk-indicators-panel"
      loading={loading}
      title="风险指标"
      extra={<Button type="link">更多</Button>}
      style={{ borderRadius: 8 }}
    >
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        <Alert
          data-testid="bond-dashboard-risk-source-boundary"
          type="warning"
          showIcon
          message="风险卡边界"
          description="GAP-BOND-DASH-RISK 尚未冻结 MTR-RSK-* 同源关系；本面板不自动继承 GS-RISK-A。"
        />
        {ROWS.map((r) => (
          <div
            key={r.key}
            data-testid={`bond-dashboard-risk-row-${String(r.key)}`}
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              borderBottom: "1px solid #f0f0f0",
              paddingBottom: 8,
            }}
          >
            <span style={{ color: "rgba(0,0,0,0.65)" }}>{r.label}</span>
            <span style={{ fontWeight: 600, color: "#1677ff" }}>
              {data ? r.format(data[r.key] as Numeric | null | undefined) : "—"}
            </span>
          </div>
        ))}
      </div>
    </Card>
  );
}
