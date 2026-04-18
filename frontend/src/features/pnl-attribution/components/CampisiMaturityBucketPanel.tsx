import type { CampisiMaturityBucketsPayload } from "../../../api/contracts";
import { DataSection } from "../../../components/DataSection";
import type { DataSectionState } from "../../../components/DataSection.types";

const cardStyle = {
  padding: 24,
  borderRadius: 16,
  border: "1px solid #e4ebf5",
  background: "#ffffff",
} as const;

function toYi(value: number) {
  return (value / 100_000_000).toFixed(2);
}

type Props = {
  data: CampisiMaturityBucketsPayload | null;
  state: DataSectionState;
  onRetry: () => void;
};

export function CampisiMaturityBucketPanel({ data, state, onRetry }: Props) {
  const rows = Object.entries(data?.buckets ?? {});

  return (
    <DataSection title="Campisi 到期桶拆解" state={state} onRetry={onRetry}>
      <div style={cardStyle}>
        <p style={{ margin: "0 0 16px", fontSize: 13, color: "#5c6b82", lineHeight: 1.6 }}>
          按剩余期限桶查看票息、国债曲线、利差和选券效应的分布，便于和久期结构联读。
        </p>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
          <thead>
            <tr style={{ background: "#f0f3f8" }}>
              <th style={{ textAlign: "left", padding: 8 }}>到期桶</th>
              <th style={{ textAlign: "right", padding: 8 }}>票息(亿)</th>
              <th style={{ textAlign: "right", padding: 8 }}>国债(亿)</th>
              <th style={{ textAlign: "right", padding: 8 }}>利差(亿)</th>
              <th style={{ textAlign: "right", padding: 8 }}>选券(亿)</th>
              <th style={{ textAlign: "right", padding: 8 }}>总收益(亿)</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(([bucket, metrics]) => (
              <tr key={bucket} style={{ borderTop: "1px solid #eef2f7" }}>
                <td style={{ padding: 8 }}>{bucket}</td>
                <td style={{ textAlign: "right", padding: 8 }}>{toYi(metrics.income_return)}</td>
                <td style={{ textAlign: "right", padding: 8 }}>{toYi(metrics.treasury_effect)}</td>
                <td style={{ textAlign: "right", padding: 8 }}>{toYi(metrics.spread_effect)}</td>
                <td style={{ textAlign: "right", padding: 8 }}>{toYi(metrics.selection_effect)}</td>
                <td style={{ textAlign: "right", padding: 8 }}>{toYi(metrics.total_return)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </DataSection>
  );
}
