import type {
  ContributionPayload,
} from "../../../api/contracts";
import { designTokens } from "../../../theme/designSystem";
import { AsyncSection } from "./AsyncSection";

type ContributionSectionProps = {
  data?: ContributionPayload;
  isLoading: boolean;
  isError: boolean;
  onRetry: () => void;
};

export default function ContributionSection({
  data,
  isLoading,
  isError,
  onRetry,
}: ContributionSectionProps) {
  return (
    <AsyncSection
      title="团队 / 账户 / 策略贡献"
      isLoading={isLoading}
      isError={isError}
      isEmpty={!data || data.rows.length === 0}
      onRetry={onRetry}
    >
      <div style={{ overflowX: "auto" }}>
        <table
          style={{
            width: "100%",
            borderCollapse: "collapse",
            fontSize: 14,
          }}
        >
          <thead>
            <tr style={{ color: "#8090a8", textAlign: "left" }}>
              <th style={{ paddingBottom: 12 }}>名称</th>
              <th style={{ paddingBottom: 12 }}>维度</th>
              <th style={{ paddingBottom: 12 }}>贡献</th>
              <th style={{ paddingBottom: 12 }}>完成度</th>
              <th style={{ paddingBottom: 12 }}>状态</th>
            </tr>
          </thead>
          <tbody>
            {data?.rows.map((row) => (
              <tr key={row.id} style={{ borderTop: `1px solid ${designTokens.color.neutral[100]}` }}>
                <td style={{ paddingBlock: 14 }}>{row.name}</td>
                <td style={{ paddingBlock: 14, color: designTokens.color.neutral[600] }}>{row.owner}</td>
                <td style={{ paddingBlock: 14, color: designTokens.color.semantic.profit, fontWeight: 600 }}>
                  {row.contribution.display}
                </td>
                <td style={{ paddingBlock: 14, minWidth: 140 }}>
                  <div
                    style={{
                      height: 8,
                      borderRadius: 999,
                      background: designTokens.color.neutral[100],
                      overflow: "hidden",
                    }}
                  >
                    <div
                      style={{
                        width: `${row.completion}%`,
                        height: "100%",
                        borderRadius: 999,
                        background: designTokens.color.primary[600],
                      }}
                    />
                  </div>
                </td>
                <td style={{ paddingBlock: 14 }}>
                  <span
                    style={{
                      padding: "4px 10px",
                      borderRadius: 999,
                      background: designTokens.color.neutral[100],
                      color: designTokens.color.neutral[600],
                      fontSize: 12,
                    }}
                  >
                    {row.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </AsyncSection>
  );
}
