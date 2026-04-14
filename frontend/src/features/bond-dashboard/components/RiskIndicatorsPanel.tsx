import { Button, Card } from "antd";

import type { RiskIndicatorsPayload } from "../../../api/contracts";
import { formatDv01Wan, formatRatePercent, formatYi, nativeToNumber } from "../utils/format";

const ROWS: {
  label: string;
  key: keyof RiskIndicatorsPayload;
  format: (v: string) => string;
}[] = [
  { label: "组合市值", key: "total_market_value", format: (v) => `${formatYi(v)} 亿` },
  { label: "DV01", key: "total_dv01", format: (v) => `${formatDv01Wan(v)} 万元` },
  { label: "加权久期", key: "weighted_duration", format: (v) => `${nativeToNumber(v).toFixed(2)} 年` },
  { label: "信用占比", key: "credit_ratio", format: (v) => `${formatRatePercent(v)}%` },
  { label: "凸性(加权)", key: "weighted_convexity", format: (v) => nativeToNumber(v).toFixed(4) },
  { label: "Spread DV01", key: "total_spread_dv01", format: (v) => `${formatDv01Wan(v)} 万元` },
  { label: "1年内再投资占比", key: "reinvestment_ratio_1y", format: (v) => `${formatRatePercent(v)}%` },
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
      loading={loading}
      title="风险指标"
      extra={<Button type="link">更多</Button>}
      style={{ borderRadius: 8 }}
    >
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {ROWS.map((r) => (
          <div
            key={r.key}
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
              {data ? r.format(String(data[r.key])) : "—"}
            </span>
          </div>
        ))}
      </div>
    </Card>
  );
}
