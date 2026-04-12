import { Button, Card } from "antd";

import type { BondAnalyticsHeadlineTile, BondAnalyticsReadinessItem } from "../lib/bondAnalyticsOverviewModel";
import type { BondAnalyticsModuleKey } from "../lib/bondAnalyticsModuleRegistry";
import { EYEBROW, panelStyle } from "./bondAnalyticsCockpitTokens";

export interface BondAnalyticsHeadlineZoneProps {
  headlineTile: BondAnalyticsHeadlineTile | null;
  headlineCtaLabel: string | null;
  promotedItems: BondAnalyticsReadinessItem[];
  warningItems: BondAnalyticsReadinessItem[];
  onOpenModuleDetail: (key: BondAnalyticsModuleKey) => void;
}

export function BondAnalyticsHeadlineZone({
  headlineTile,
  headlineCtaLabel,
  promotedItems,
  warningItems,
  onOpenModuleDetail,
}: BondAnalyticsHeadlineZoneProps) {
  return (
    <Card
      size="small"
      data-testid="bond-analysis-headline-zone"
      style={panelStyle("linear-gradient(180deg, #ffffff 0%, #f7faff 100%)")}
    >
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "minmax(0, 1.5fr) minmax(260px, 0.9fr)",
          gap: 16,
          alignItems: "start",
        }}
      >
        <div style={{ display: "grid", gap: 14 }}>
          <div style={EYEBROW}>Headline focus</div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12, flexWrap: "wrap" }}>
            <div style={{ display: "grid", gap: 8 }}>
              <div
                style={{
                  fontSize: 28,
                  lineHeight: 1.12,
                  fontWeight: 800,
                  letterSpacing: "-0.04em",
                  color: "#12263f",
                  maxWidth: 540,
                }}
              >
                Lead only governed content that has already passed the truth gate.
              </div>
              <div style={{ color: "#566a82", fontSize: 13, lineHeight: 1.7, maxWidth: 620 }}>
                The first-screen analytic slot stays narrow by design: action attribution can lead when provenance is
                clean, while every other module remains a readiness or drill surface.
              </div>
            </div>

            {headlineTile && headlineCtaLabel ? (
              <Button
                size="small"
                type="default"
                onClick={() => onOpenModuleDetail(headlineTile.key)}
                data-testid={`bond-analysis-open-headline-${headlineTile.key}`}
              >
                {headlineCtaLabel}
              </Button>
            ) : null}
          </div>

          {headlineTile ? (
            <button
              type="button"
              onClick={() => onOpenModuleDetail(headlineTile.key)}
              style={{
                border: "1px solid #d4e1f6",
                background:
                  "linear-gradient(135deg, rgba(41,84,184,0.08) 0%, rgba(255,255,255,0.96) 48%, rgba(22,38,63,0.04) 100%)",
                borderRadius: 24,
                padding: 20,
                textAlign: "left",
                cursor: "pointer",
                display: "grid",
                gap: 10,
              }}
              data-testid={`bond-analysis-headline-${headlineTile.key}`}
            >
              <div style={{ ...EYEBROW, color: "#3d5f98" }}>{headlineTile.label}</div>
              <div style={{ fontSize: 40, lineHeight: 1, fontWeight: 800, letterSpacing: "-0.05em", color: "#163b83" }}>
                {headlineTile.value}
              </div>
              <div style={{ fontSize: 14, fontWeight: 700, color: "#1e54b6" }}>{headlineTile.caption}</div>
              <div style={{ fontSize: 13, color: "#51657f", lineHeight: 1.6 }}>{headlineTile.detail}</div>
            </button>
          ) : (
            <div
              style={{
                border: "1px dashed #d5e0ee",
                borderRadius: 22,
                padding: 18,
                background: "rgba(255,255,255,0.84)",
                display: "grid",
                gap: 8,
              }}
            >
              <div style={{ ...EYEBROW, color: "#677d98" }}>Gate result</div>
              <div style={{ fontSize: 20, fontWeight: 700, color: "#18314d" }}>No module is eligible for promoted analytics yet.</div>
              <div style={{ color: "#566a82", fontSize: 13, lineHeight: 1.7 }}>
                The cockpit stays honest here: readiness, anomalies, and drill routes remain visible instead of filling the
                first screen with inferred KPIs.
              </div>
            </div>
          )}
        </div>

        <div
          style={{
            borderRadius: 22,
            border: "1px solid #dfe8f3",
            background: "rgba(251,253,255,0.92)",
            padding: 16,
            display: "grid",
            gap: 14,
          }}
        >
          <div style={EYEBROW}>Governed boundary</div>

          <div style={{ display: "grid", gap: 10 }}>
            <div style={{ borderRadius: 16, padding: "10px 12px", background: "#f5f8fc", border: "1px solid #e3eaf1" }}>
              <div style={{ color: "#18314d", fontSize: 13, fontWeight: 700 }}>Promoted now</div>
              <div style={{ marginTop: 4, color: "#5d718b", fontSize: 12, lineHeight: 1.55 }}>
                {promotedItems.length > 0
                  ? promotedItems.map((item) => item.label).join(", ")
                  : "None. Promotion stays blocked until overview-safe evidence exists."}
              </div>
            </div>
            <div
              style={{
                borderRadius: 16,
                padding: "10px 12px",
                background: warningItems.length > 0 ? "#fff7ec" : "#f5f8fc",
                border: warningItems.length > 0 ? "1px solid #efdcb8" : "1px solid #e3eaf1",
              }}
            >
              <div style={{ color: "#18314d", fontSize: 13, fontWeight: 700 }}>Watchouts</div>
              <div style={{ marginTop: 4, color: "#5d718b", fontSize: 12, lineHeight: 1.55 }}>
                {warningItems.length > 0
                  ? warningItems.map((item) => item.label).join(", ")
                  : "No immediate warning-only modules in the current overview boundary."}
              </div>
            </div>
          </div>

          <div style={{ borderTop: "1px solid #e4ebf3", paddingTop: 12, color: "#667a95", fontSize: 12, lineHeight: 1.65 }}>
            Future and deferred surfaces remain visible in the top-right rail so users can see what is intentionally withheld
            from the current governed viewport.
          </div>
        </div>
      </div>
    </Card>
  );
}
