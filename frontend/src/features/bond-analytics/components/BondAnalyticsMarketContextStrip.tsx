import { Card } from "antd";

import type { BondAnalyticsTruthStrip } from "../lib/bondAnalyticsOverviewModel";
import { EYEBROW, FIELD, PERIOD_OPTIONS, panelStyle, toneColor } from "./bondAnalyticsCockpitTokens";

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
  const periodLabel = PERIOD_OPTIONS.find((opt) => opt.value === periodType)?.label ?? periodType;

  return (
    <Card
      size="small"
      data-testid="bond-analysis-market-context-strip"
      style={panelStyle("linear-gradient(180deg, #ffffff 0%, #f6f9fd 100%)")}
      styles={{ body: { padding: 14 } }}
    >
      <div style={{ display: "grid", gap: 10 }}>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-start",
            gap: 12,
            flexWrap: "wrap",
          }}
        >
          <div style={{ display: "grid", gap: 4 }}>
            <div style={EYEBROW}>Bond analytics cockpit</div>
            <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
              <h2
                style={{
                  margin: 0,
                  fontSize: 22,
                  lineHeight: 1.1,
                  fontWeight: 800,
                  letterSpacing: "-0.04em",
                  color: "#162a44",
                }}
              >
                债券分析
              </h2>
              <span
                style={{
                  padding: "4px 10px",
                  borderRadius: 999,
                  background: "#eaf1ff",
                  color: "#2954b8",
                  fontSize: 12,
                  fontWeight: 700,
                }}
              >
                Governed homepage
              </span>
            </div>
          </div>

          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", justifyContent: "flex-end" }}>
            <div
              style={{
                border: "1px solid #dbe4f0",
                borderRadius: 14,
                background: "#fbfcfe",
                padding: "8px 10px",
                minWidth: 112,
              }}
            >
              <div style={FIELD}>Report date</div>
              <div style={{ fontSize: 14, fontWeight: 700, color: "#18314d" }}>{reportDate}</div>
            </div>
            <div
              style={{
                border: "1px solid #dbe4f0",
                borderRadius: 14,
                background: "#fbfcfe",
                padding: "8px 10px",
                minWidth: 92,
              }}
            >
              <div style={FIELD}>Period</div>
              <div style={{ fontSize: 14, fontWeight: 700, color: "#18314d" }}>{periodLabel}</div>
            </div>
            <div
              style={{
                border: "1px solid #dbe4f0",
                borderRadius: 14,
                background: "#fbfcfe",
                padding: "8px 10px",
                minWidth: 128,
              }}
            >
              <div style={FIELD}>Drill lead</div>
              <div style={{ fontSize: 13, fontWeight: 700, color: "#18314d" }}>{leadModuleLabel}</div>
              <div style={{ marginTop: 4, color: "#72839a", fontSize: 10 }}>{leadPromotionLabel}</div>
            </div>
          </div>
        </div>

        <div
          style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(145px, 1fr))", gap: 10 }}
          data-testid="bond-analysis-truth-strip"
        >
          {truthStrip.items.map((item) => {
            const colors = toneColor(item.tone);
            return (
              <div
                key={item.key}
                style={{
                  border: `1px solid ${colors.borderColor}`,
                  background: colors.background,
                  borderRadius: 14,
                  padding: "10px 12px",
                  display: "grid",
                  gap: 4,
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
                <div
                  style={{
                    color: colors.color,
                    fontSize: 16,
                    fontWeight: 800,
                    letterSpacing: "-0.03em",
                  }}
                >
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
