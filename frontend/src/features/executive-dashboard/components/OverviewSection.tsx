import { DataSection } from "../../../components/DataSection";
import { TONE_COLOR } from "../../../utils/tone";
import type { DashboardAdapterOutput } from "../adapters/executiveDashboardAdapter";
import { selectOverviewCards } from "../selectors/executiveDashboardSelectors";

type OverviewSectionProps = {
  overview: DashboardAdapterOutput["overview"];
  onRetry: () => void;
};

const CARD_STYLE = {
  display: "grid",
  gap: 10,
  padding: 18,
  borderRadius: 20,
  background: "linear-gradient(180deg, rgba(255,255,255,0.98) 0%, rgba(246,249,253,0.98) 100%)",
  border: "1px solid #e4ebf5",
} as const;

const LABEL_STYLE = { color: "#8090a8", fontSize: 12, letterSpacing: "0.04em" } as const;

const DELTA_BADGE_STYLE = {
  width: "fit-content",
  padding: "4px 10px",
  borderRadius: 999,
  background: "#eef3fb",
  fontSize: 12,
  fontWeight: 600,
} as const;

const VALUE_STYLE = { margin: 0, fontSize: 28, fontWeight: 600 } as const;

const DETAIL_STYLE = {
  margin: 0,
  color: "#5c6b82",
  fontSize: 13,
  lineHeight: 1.6,
} as const;

export function OverviewSection({ overview, onRetry }: OverviewSectionProps) {
  const cards = selectOverviewCards(overview.vm);

  return (
    <DataSection
      title="经营总览"
      state={overview.state}
      onRetry={onRetry}
      extra={
        <span
          style={{
            padding: "4px 10px",
            borderRadius: 999,
            background: "#dfe8ff",
            color: "#1f5eff",
            fontSize: 12,
          }}
        >
          {cards.length} 项
        </span>
      }
    >
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
          gap: 16,
        }}
      >
        {cards.map((metric) => (
          <div key={metric.id} style={CARD_STYLE}>
            <span style={LABEL_STYLE}>{metric.label}</span>
            <span
              style={{
                ...DELTA_BADGE_STYLE,
                color: TONE_COLOR[metric.tone],
              }}
            >
              {metric.delta.display}
            </span>
            <div style={VALUE_STYLE}>{metric.value.display}</div>
            <p style={DETAIL_STYLE}>{metric.detail}</p>
          </div>
        ))}
      </div>
    </DataSection>
  );
}
