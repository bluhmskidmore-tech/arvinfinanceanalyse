import { Button, Card } from "antd";

import { designTokens, tabularNumsStyle } from "../../../theme/designSystem";
import type { BondAnalyticsHeadlineTile, BondAnalyticsReadinessItem } from "../lib/bondAnalyticsOverviewModel";
import type { BondAnalyticsModuleKey } from "../lib/bondAnalyticsModuleRegistry";
import { EYEBROW, panelStyle } from "./bondAnalyticsCockpitTokens";

const dt = designTokens;
const headlinePanelBg = `linear-gradient(180deg, ${dt.color.primary[50]} 0%, ${dt.color.primary[100]} 100%)`;
const headlineTileGrad = `linear-gradient(135deg, ${dt.color.info[50]} 0%, ${dt.color.neutral[50]} 48%, ${dt.color.primary[100]} 100%)`;

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
      style={panelStyle(headlinePanelBg)}
    >
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "minmax(0, 1.5fr) minmax(260px, 0.9fr)",
          gap: dt.space[4],
          alignItems: "start",
        }}
      >
        <div style={{ display: "grid", gap: dt.space[4] }}>
          <div style={EYEBROW}>Headline focus</div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: dt.space[3], flexWrap: "wrap" }}>
            <div style={{ display: "grid", gap: dt.space[2] }}>
              <div
                style={{
                  fontSize: dt.fontSize[30],
                  lineHeight: dt.lineHeight.tight,
                  fontWeight: 800,
                  letterSpacing: "-0.04em",
                  color: dt.color.primary[900],
                  maxWidth: 540,
                }}
              >
                Lead only governed content that has already passed the truth gate.
              </div>
              <div style={{ color: dt.color.neutral[600], fontSize: dt.fontSize[13], lineHeight: dt.lineHeight.relaxed, maxWidth: 620 }}>
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
                border: `1px solid ${dt.color.primary[200]}`,
                background: headlineTileGrad,
                borderRadius: dt.radius.xl,
                padding: dt.space[5],
                textAlign: "left",
                cursor: "pointer",
                display: "grid",
                gap: dt.space[3],
              }}
              data-testid={`bond-analysis-headline-${headlineTile.key}`}
            >
              <div style={{ ...EYEBROW, color: dt.color.primary[700] }}>{headlineTile.label}</div>
              <div
                style={{
                  fontSize: dt.fontSize[30],
                  lineHeight: 1,
                  fontWeight: 800,
                  letterSpacing: "-0.05em",
                  color: dt.color.primary[800],
                  ...tabularNumsStyle,
                }}
              >
                {headlineTile.value}
              </div>
              <div style={{ fontSize: dt.fontSize[14], fontWeight: 700, color: dt.color.info[600] }}>{headlineTile.caption}</div>
              <div style={{ fontSize: dt.fontSize[13], color: dt.color.neutral[700], lineHeight: 1.6 }}>{headlineTile.detail}</div>
            </button>
          ) : (
            <div
              style={{
                border: `1px dashed ${dt.color.primary[200]}`,
                borderRadius: dt.radius.xl,
                padding: dt.space[4],
                background: `${dt.color.neutral[50]}D9`,
                display: "grid",
                gap: dt.space[2],
              }}
            >
              <div style={{ ...EYEBROW, color: dt.color.neutral[600] }}>Gate result</div>
              <div style={{ fontSize: dt.fontSize[20], fontWeight: 700, color: dt.color.primary[900] }}>
                No module is eligible for promoted analytics yet.
              </div>
              <div style={{ color: dt.color.neutral[600], fontSize: dt.fontSize[13], lineHeight: dt.lineHeight.relaxed }}>
                The cockpit stays honest here: readiness, anomalies, and drill routes remain visible instead of filling the
                first screen with inferred KPIs.
              </div>
            </div>
          )}
        </div>

        <div
          style={{
            borderRadius: dt.radius.xl,
            border: `1px solid ${dt.color.primary[200]}`,
            background: `${dt.color.primary[50]}EB`,
            padding: dt.space[4],
            display: "grid",
            gap: dt.space[3],
          }}
        >
          <div style={EYEBROW}>Governed boundary</div>

          <div style={{ display: "grid", gap: dt.space[3] }}>
            <div
              style={{
                borderRadius: dt.radius.lg,
                padding: `${dt.space[2]}px ${dt.space[3]}px`,
                background: dt.color.primary[50],
                border: `1px solid ${dt.color.primary[200]}`,
              }}
            >
              <div style={{ color: dt.color.primary[900], fontSize: dt.fontSize[13], fontWeight: 700 }}>Promoted now</div>
              <div style={{ marginTop: dt.space[1], color: dt.color.neutral[600], fontSize: dt.fontSize[12], lineHeight: 1.55 }}>
                {promotedItems.length > 0
                  ? promotedItems.map((item) => item.label).join(", ")
                  : "None. Promotion stays blocked until overview-safe evidence exists."}
              </div>
            </div>
            <div
              style={{
                borderRadius: dt.radius.lg,
                padding: `${dt.space[2]}px ${dt.space[3]}px`,
                background: warningItems.length > 0 ? dt.color.warning[50] : dt.color.primary[50],
                border:
                  warningItems.length > 0 ? `1px solid ${dt.color.warning[200]}` : `1px solid ${dt.color.primary[200]}`,
              }}
            >
              <div style={{ color: dt.color.primary[900], fontSize: dt.fontSize[13], fontWeight: 700 }}>Watchouts</div>
              <div style={{ marginTop: dt.space[1], color: dt.color.neutral[600], fontSize: dt.fontSize[12], lineHeight: 1.55 }}>
                {warningItems.length > 0
                  ? warningItems.map((item) => item.label).join(", ")
                  : "No immediate warning-only modules in the current overview boundary."}
              </div>
            </div>
          </div>

          <div
            style={{
              borderTop: `1px solid ${dt.color.primary[200]}`,
              paddingTop: dt.space[3],
              color: dt.color.neutral[600],
              fontSize: dt.fontSize[12],
              lineHeight: 1.65,
            }}
          >
            Future and deferred surfaces remain visible in the top-right rail so users can see what is intentionally withheld
            from the current governed viewport.
          </div>
        </div>
      </div>
    </Card>
  );
}
