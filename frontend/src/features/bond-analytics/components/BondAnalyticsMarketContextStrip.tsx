import { Card } from "antd";

import { designTokens, tabularNumsStyle } from "../../../theme/designSystem";
import type { BondAnalyticsTruthStrip } from "../lib/bondAnalyticsOverviewModel";
import { EYEBROW, FIELD, PERIOD_OPTIONS, panelStyle, toneColor } from "./bondAnalyticsCockpitTokens";

const dt = designTokens;
const stripPanelBg = `linear-gradient(180deg, ${dt.color.primary[50]} 0%, ${dt.color.primary[100]} 100%)`;

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
      style={panelStyle(stripPanelBg)}
      styles={{ body: { padding: dt.space[4] } }}
    >
      <div style={{ display: "grid", gap: dt.space[3] }}>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-start",
            gap: dt.space[3],
            flexWrap: "wrap",
          }}
        >
          <div style={{ display: "grid", gap: dt.space[1] }}>
            <div style={EYEBROW}>Bond analytics cockpit</div>
            <div style={{ display: "flex", alignItems: "center", gap: dt.space[3], flexWrap: "wrap" }}>
              <h2
                style={{
                  margin: 0,
                  fontSize: dt.fontSize[24],
                  lineHeight: dt.lineHeight.tight,
                  fontWeight: 800,
                  letterSpacing: "-0.04em",
                  color: dt.color.primary[900],
                }}
              >
                债券分析
              </h2>
              <span
                style={{
                  padding: `${dt.space[1]}px ${dt.space[3]}px`,
                  borderRadius: 999,
                  background: dt.color.info[50],
                  color: dt.color.info[600],
                  fontSize: dt.fontSize[12],
                  fontWeight: 700,
                }}
              >
                Governed homepage
              </span>
            </div>
          </div>

          <div style={{ display: "flex", gap: dt.space[2], flexWrap: "wrap", justifyContent: "flex-end" }}>
            <div
              style={{
                border: `1px solid ${dt.color.primary[200]}`,
                borderRadius: dt.radius.md,
                background: dt.color.neutral[50],
                padding: `${dt.space[2]}px ${dt.space[3]}px`,
                minWidth: 112,
              }}
            >
              <div style={FIELD}>Report date</div>
              <div style={{ fontSize: dt.fontSize[14], fontWeight: 700, color: dt.color.primary[900], ...tabularNumsStyle }}>{reportDate}</div>
            </div>
            <div
              style={{
                border: `1px solid ${dt.color.primary[200]}`,
                borderRadius: dt.radius.md,
                background: dt.color.neutral[50],
                padding: `${dt.space[2]}px ${dt.space[3]}px`,
                minWidth: 92,
              }}
            >
              <div style={FIELD}>Period</div>
              <div style={{ fontSize: dt.fontSize[14], fontWeight: 700, color: dt.color.primary[900], ...tabularNumsStyle }}>{periodLabel}</div>
            </div>
            <div
              style={{
                border: `1px solid ${dt.color.primary[200]}`,
                borderRadius: dt.radius.md,
                background: dt.color.neutral[50],
                padding: `${dt.space[2]}px ${dt.space[3]}px`,
                minWidth: 128,
              }}
            >
              <div style={FIELD}>Drill lead</div>
              <div style={{ fontSize: dt.fontSize[13], fontWeight: 700, color: dt.color.primary[900] }}>{leadModuleLabel}</div>
              <div style={{ marginTop: dt.space[1], color: dt.color.neutral[600], fontSize: dt.fontSize[11] }}>{leadPromotionLabel}</div>
            </div>
          </div>
        </div>

        <div
          style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(145px, 1fr))", gap: dt.space[3] }}
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
                  borderRadius: dt.radius.md,
                  padding: `${dt.space[2]}px ${dt.space[3]}px`,
                  display: "grid",
                  gap: dt.space[1],
                }}
              >
                <div
                  style={{
                    fontSize: dt.fontSize[11],
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
                    fontSize: dt.fontSize[16],
                    fontWeight: 800,
                    letterSpacing: "-0.03em",
                    ...tabularNumsStyle,
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
