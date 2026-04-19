import { DataSection } from "../../../components/DataSection";
import { shellTokens } from "../../../theme/tokens";
import { TONE_COLOR } from "../../../utils/tone";
import type { DashboardAdapterOutput } from "../adapters/executiveDashboardAdapter";
import { selectOverviewCards } from "../selectors/executiveDashboardSelectors";

type OverviewSectionProps = {
  overview: DashboardAdapterOutput["overview"];
  onRetry: () => void;
};

const CARD_STYLE = {
  display: "grid",
  gap: 14,
  padding: 20,
  borderRadius: 22,
  background: `linear-gradient(180deg, ${shellTokens.colorBgCanvas} 0%, ${shellTokens.colorBgSurface} 100%)`,
  border: `1px solid ${shellTokens.colorBorderSoft}`,
  boxShadow: "inset 0 1px 0 rgba(255,255,255,0.72)",
} as const;

const LABEL_ROW_STYLE = {
  display: "flex",
  justifyContent: "space-between",
  gap: 12,
  alignItems: "center",
} as const;

const DELTA_BADGE_STYLE = {
  width: "fit-content",
  padding: "5px 10px",
  borderRadius: 999,
  background: shellTokens.colorBgMuted,
  fontSize: 12,
  fontWeight: 600,
} as const;

const LABEL_STYLE = {
  color: shellTokens.colorTextMuted,
  fontSize: 12,
  letterSpacing: "0.04em",
  textTransform: "uppercase" as const,
} as const;

const VALUE_BLOCK_STYLE = {
  display: "grid",
  gap: 8,
} as const;

const VALUE_STYLE = {
  margin: 0,
  fontSize: 34,
  lineHeight: 1.08,
  letterSpacing: "-0.04em",
  fontWeight: 700,
  color: shellTokens.colorTextPrimary,
} as const;

const DETAIL_STYLE = {
  margin: 0,
  color: shellTokens.colorTextSecondary,
  fontSize: 13,
  lineHeight: 1.7,
} as const;

const CARD_TOPLINE_STYLE = {
  width: 52,
  height: 4,
  borderRadius: 999,
  opacity: 0.24,
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
            padding: "5px 10px",
            borderRadius: 999,
            background: shellTokens.colorAccentSoft,
            color: shellTokens.colorAccent,
            fontSize: 12,
            fontWeight: 700,
            letterSpacing: "0.04em",
          }}
        >
          {cards.length} 项
        </span>
      }
    >
      <div className="overview-card-grid" style={{ display: "grid" }}>
        {cards.map((metric) => (
          <div key={metric.id} style={CARD_STYLE}>
            <div style={{ ...CARD_TOPLINE_STYLE, background: TONE_COLOR[metric.tone] }} />
            <div style={LABEL_ROW_STYLE}>
              <span style={LABEL_STYLE}>{metric.label}</span>
              <span
                style={{
                  ...DELTA_BADGE_STYLE,
                  color: TONE_COLOR[metric.tone],
                }}
              >
                {metric.delta.display}
              </span>
            </div>
            <div style={VALUE_BLOCK_STYLE}>
              <div style={VALUE_STYLE}>{metric.value.display}</div>
            </div>
            <p style={DETAIL_STYLE}>{metric.detail}</p>
          </div>
        ))}
      </div>
    </DataSection>
  );
}
