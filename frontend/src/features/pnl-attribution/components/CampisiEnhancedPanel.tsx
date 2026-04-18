import type { CampisiEnhancedPayload } from "../../../api/contracts";
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
  data: CampisiEnhancedPayload | null;
  state: DataSectionState;
  onRetry: () => void;
};

export function CampisiEnhancedPanel({ data, state, onRetry }: Props) {
  const totals = data?.totals;

  return (
    <DataSection title="Campisi 六效应归因（扩展）" state={state} onRetry={onRetry}>
      <div style={cardStyle}>
        <p style={{ margin: "0 0 16px", fontSize: 13, color: "#5c6b82", lineHeight: 1.6 }}>
          将凸性、交叉项与再投资从选券残差中拆出，保留扩展归因的总量与资产类别分布。
        </p>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: 12 }}>
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
            <div key={label} style={{ padding: 12, borderRadius: 12, background: "#f7f9fc" }}>
              <div style={{ fontSize: 12, color: "#5c6b82" }}>{label}</div>
              <div style={{ marginTop: 6, fontWeight: 700, color: "#162033" }}>
                {value === undefined ? "—" : `${toYi(Number(value))} 亿`}
              </div>
            </div>
          ))}
        </div>
      </div>
    </DataSection>
  );
}
