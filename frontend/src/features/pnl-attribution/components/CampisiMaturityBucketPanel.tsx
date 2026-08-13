import type { CampisiMaturityBucketsPayload } from "../../../api/contracts";
import type { DataSectionState } from "../../../components/DataSection.types";
import { PageDataSection } from "../../../components/page/PageDataSection";
import { designTokens, tabularNumsStyle } from "../../../theme/designSystem";

// 本面板挂在 Nocturne 深色路由（theme-dh-api + pnl-attribution scope）下，
// 面色/文字一律走主题感知 CSS 变量（--dh-api-*），禁止浅色 hex、designTokens
// 浅色 neutral 或 --ib-*（路由边界已算成钢蓝字面值）直灌（迁法同
// CampisiAttributionPanel / CampisiDecisionGradePanel）。
const cardStyle = {
  padding: designTokens.space[5],
  borderRadius: "var(--dh-api-radius)",
  border: "1px solid var(--dh-api-line)",
  background: "var(--dh-api-panel)",
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
    <PageDataSection title="Campisi 到期桶拆解" state={state} onRetry={onRetry}>
      <div style={cardStyle}>
        <p
          style={{
            margin: `0 0 ${designTokens.space[4]}px`,
            fontSize: designTokens.fontSize[13],
            color: "var(--dh-api-soft)",
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
            <tr style={{ background: "var(--dh-api-panel-2)" }}>
              <th style={{ textAlign: "left", padding: designTokens.space[2] }}>
                到期桶
              </th>
              <th
                style={{
                  textAlign: "right",
                  padding: designTokens.space[2],
                  ...tabularNumsStyle,
                }}
              >
                票息(亿)
              </th>
              <th
                style={{
                  textAlign: "right",
                  padding: designTokens.space[2],
                  ...tabularNumsStyle,
                }}
              >
                国债(亿)
              </th>
              <th
                style={{
                  textAlign: "right",
                  padding: designTokens.space[2],
                  ...tabularNumsStyle,
                }}
              >
                利差(亿)
              </th>
              <th
                style={{
                  textAlign: "right",
                  padding: designTokens.space[2],
                  ...tabularNumsStyle,
                }}
              >
                剩余/选券(亿)
              </th>
              <th
                style={{
                  textAlign: "right",
                  padding: designTokens.space[2],
                  ...tabularNumsStyle,
                }}
              >
                总收益(亿)
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map(([bucket, metrics]) => (
              <tr
                key={bucket}
                style={{
                  borderTop: "1px solid var(--dh-api-line-soft)",
                }}
              >
                <td style={{ padding: designTokens.space[2] }}>{bucket}</td>
                <td
                  style={{
                    textAlign: "right",
                    padding: designTokens.space[2],
                    ...tabularNumsStyle,
                  }}
                >
                  {toYi(metrics.income_return)}
                </td>
                <td
                  style={{
                    textAlign: "right",
                    padding: designTokens.space[2],
                    ...tabularNumsStyle,
                  }}
                >
                  {toYi(metrics.treasury_effect)}
                </td>
                <td
                  style={{
                    textAlign: "right",
                    padding: designTokens.space[2],
                    ...tabularNumsStyle,
                  }}
                >
                  {toYi(metrics.spread_effect)}
                </td>
                <td
                  style={{
                    textAlign: "right",
                    padding: designTokens.space[2],
                    ...tabularNumsStyle,
                  }}
                >
                  {toYi(metrics.selection_effect)}
                </td>
                <td
                  style={{
                    textAlign: "right",
                    padding: designTokens.space[2],
                    ...tabularNumsStyle,
                  }}
                >
                  {toYi(metrics.total_return)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </PageDataSection>
  );
}
