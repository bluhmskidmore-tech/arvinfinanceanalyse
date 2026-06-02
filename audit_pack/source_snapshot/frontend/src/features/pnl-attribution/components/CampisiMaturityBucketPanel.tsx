import type { CampisiMaturityBucketsPayload } from "../../../api/contracts";
import { DataSection } from "../../../components/DataSection";
import type { DataSectionState } from "../../../components/DataSection.types";
import { designTokens, tabularNumsStyle } from "../../../theme/designSystem";

const cardStyle = {
  padding: designTokens.space[6],
  borderRadius: designTokens.radius.lg,
  border: `1px solid ${designTokens.color.neutral[200]}`,
  background: designTokens.color.primary[50],
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
        <p
          style={{
            margin: `0 0 ${designTokens.space[4]}px`,
            fontSize: designTokens.fontSize[13],
            color: designTokens.color.neutral[700],
            lineHeight: designTokens.lineHeight.normal,
          }}
        >
          按剩余期限桶查看票息、国债曲线、利差和选券效应的分布，便于和久期结构联读。
        </p>
        <table
          style={{
            width: "100%",
            borderCollapse: "collapse",
            fontSize: designTokens.fontSize[12],
          }}
        >
          <thead>
            <tr style={{ background: designTokens.color.neutral[100] }}>
              <th style={{ textAlign: "left", padding: designTokens.space[2] }}>到期桶</th>
              <th style={{ textAlign: "right", padding: designTokens.space[2], ...tabularNumsStyle }}>票息(亿)</th>
              <th style={{ textAlign: "right", padding: designTokens.space[2], ...tabularNumsStyle }}>国债(亿)</th>
              <th style={{ textAlign: "right", padding: designTokens.space[2], ...tabularNumsStyle }}>利差(亿)</th>
              <th style={{ textAlign: "right", padding: designTokens.space[2], ...tabularNumsStyle }}>选券(亿)</th>
              <th style={{ textAlign: "right", padding: designTokens.space[2], ...tabularNumsStyle }}>总收益(亿)</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(([bucket, metrics]) => (
              <tr key={bucket} style={{ borderTop: `1px solid ${designTokens.color.neutral[200]}` }}>
                <td style={{ padding: designTokens.space[2] }}>{bucket}</td>
                <td style={{ textAlign: "right", padding: designTokens.space[2], ...tabularNumsStyle }}>
                  {toYi(metrics.income_return)}
                </td>
                <td style={{ textAlign: "right", padding: designTokens.space[2], ...tabularNumsStyle }}>
                  {toYi(metrics.treasury_effect)}
                </td>
                <td style={{ textAlign: "right", padding: designTokens.space[2], ...tabularNumsStyle }}>
                  {toYi(metrics.spread_effect)}
                </td>
                <td style={{ textAlign: "right", padding: designTokens.space[2], ...tabularNumsStyle }}>
                  {toYi(metrics.selection_effect)}
                </td>
                <td style={{ textAlign: "right", padding: designTokens.space[2], ...tabularNumsStyle }}>
                  {toYi(metrics.total_return)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </DataSection>
  );
}
