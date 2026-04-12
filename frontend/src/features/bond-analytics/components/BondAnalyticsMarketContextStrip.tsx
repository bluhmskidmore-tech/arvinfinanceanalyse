import { Card } from "antd";

import type { BondAnalyticsTruthStrip } from "../lib/bondAnalyticsOverviewModel";
import { EYEBROW, FIELD, panelStyle, toneColor } from "./bondAnalyticsCockpitTokens";

export interface BondAnalyticsMarketContextStripProps {
  reportDate: string;
  periodType: string;
  leadModuleLabel: string;
  leadPromotionLabel: string;
  truthStrip: BondAnalyticsTruthStrip;
}

export function BondAnalyticsMarketContextStrip({
  reportDate,
  periodType,
  leadModuleLabel,
  leadPromotionLabel,
  truthStrip,
}: BondAnalyticsMarketContextStripProps) {
  return (
    <Card
      size="small"
      data-testid="bond-analysis-market-context-strip"
      style={panelStyle("linear-gradient(180deg, #ffffff 0%, #f6f9fd 100%)")}
    >
      <div style={{ display: "grid", gap: 14 }}>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "minmax(0, 1.65fr) minmax(280px, 1fr)",
            gap: 16,
            alignItems: "start",
          }}
        >
          <div style={{ display: "grid", gap: 10 }}>
            <div style={EYEBROW}>Bond analytics cockpit</div>
            <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
              <h2
                style={{
                  margin: 0,
                  fontSize: 28,
                  lineHeight: 1.1,
                  fontWeight: 800,
                  letterSpacing: "-0.04em",
                  color: "#162a44",
                }}
              >
                Bond analytics
              </h2>
              <span
                style={{
                  padding: "5px 11px",
                  borderRadius: 999,
                  background: "#eaf1ff",
                  color: "#2954b8",
                  fontSize: 12,
                  fontWeight: 700,
                }}
              >
                Hybrid governed cockpit
              </span>
            </div>
            <div style={{ color: "#556982", fontSize: 13, lineHeight: 1.7, maxWidth: 820 }}>
              The first viewport answers what is true, what is blocked, and which analytic path is ready to
              lead without widening the overview boundary.
            </div>
          </div>
          <div style={{ display: "grid", gap: 10, gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))" }}>
            <div style={{ border: "1px solid #dbe4f0", borderRadius: 16, background: "#fbfcfe", padding: "12px 13px" }}>
              <div style={FIELD}>Report date</div>
              <div style={{ fontSize: 16, fontWeight: 700, color: "#18314d" }}>{reportDate}</div>
            </div>
            <div style={{ border: "1px solid #dbe4f0", borderRadius: 16, background: "#fbfcfe", padding: "12px 13px" }}>
              <div style={FIELD}>Period</div>
              <div style={{ fontSize: 16, fontWeight: 700, color: "#18314d" }}>{periodType}</div>
            </div>
            <div style={{ border: "1px solid #dbe4f0", borderRadius: 16, background: "#fbfcfe", padding: "12px 13px" }}>
              <div style={FIELD}>Lead module</div>
              <div style={{ fontSize: 15, fontWeight: 700, color: "#18314d" }}>{leadModuleLabel}</div>
              <div style={{ marginTop: 5, color: "#72839a", fontSize: 11 }}>{leadPromotionLabel}</div>
            </div>
          </div>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(145px, 1fr))", gap: 10 }} data-testid="bond-analysis-truth-strip">
          {truthStrip.items.map((item) => {
            const colors = toneColor(item.tone);
            return (
              <div
                key={item.key}
                style={{
                  border: `1px solid ${colors.borderColor}`,
                  background: colors.background,
                  borderRadius: 18,
                  padding: "12px 14px",
                  display: "grid",
                  gap: 6,
                }}
              >
                <div
                  style={{
                    fontSize: 11,
                    color: colors.accent,
                    textTransform: "uppercase",
                    letterSpacing: "0.08em",
                    fontWeight: 700,
                  }}
                >
                  {item.label}
                </div>
                <div style={{ color: colors.color, fontSize: 18, fontWeight: 800, letterSpacing: "-0.03em" }}>
                  {item.value}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </Card>
  );
}
