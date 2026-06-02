import type { CampisiEnhancedPayload } from "../../../api/contracts";
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
  data: CampisiEnhancedPayload | null;
  state: DataSectionState;
  onRetry: () => void;
};

export function CampisiEnhancedPanel({ data, state, onRetry }: Props) {
  const totals = data?.totals;

  return (
    <DataSection title="Campisi 六效应归因（扩展）" state={state} onRetry={onRetry}>
      <div style={cardStyle}>
        <p
          style={{
            margin: `0 0 ${designTokens.space[4]}px`,
            fontSize: designTokens.fontSize[13],
            color: designTokens.color.neutral[700],
            lineHeight: designTokens.lineHeight.normal,
          }}
        >
          将凸性、交叉项与再投资从选券残差中拆出，保留扩展归因的总量与资产类别分布。
        </p>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
            gap: designTokens.space[3],
          }}
        >
          {[
            ["票息", totals?.income_return],
            ["国债曲线", totals?.treasury_effect],
            ["利差", totals?.spread_effect],
            ["凸性", totals?.convexity_effect],
            ["交叉项", totals?.cross_effect],
            ["再投资", totals?.reinvestment_effect],
            ["选券", totals?.selection_effect],
            ["总收益", totals?.total_return],
          ].map(([label, value]) => (
            <div
              key={label}
              style={{
                padding: designTokens.space[3],
                borderRadius: designTokens.radius.md,
                background: designTokens.color.neutral[50],
              }}
            >
              <div style={{ fontSize: designTokens.fontSize[12], color: designTokens.color.neutral[700] }}>{label}</div>
              <div
                style={{
                  marginTop: designTokens.space[2],
                  fontWeight: 700,
                  color: designTokens.color.neutral[900],
                  ...tabularNumsStyle,
                }}
              >
                {value === undefined ? "—" : `${toYi(Number(value))} 亿`}
              </div>
            </div>
          ))}
        </div>
      </div>
    </DataSection>
  );
}
