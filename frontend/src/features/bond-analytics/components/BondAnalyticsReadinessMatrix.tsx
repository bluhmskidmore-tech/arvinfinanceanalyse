import { Button, Card, Tag } from "antd";

import type { BondAnalyticsReadinessItem } from "../lib/bondAnalyticsOverviewModel";
import type { BondAnalyticsModuleKey } from "../lib/bondAnalyticsModuleRegistry";
import { EYEBROW, panelStyle, promotionLabel, readinessSurface, readinessTagColor } from "./bondAnalyticsCockpitTokens";

function ReadinessRow({
  item,
  onOpenModuleDetail,
}: {
  item: BondAnalyticsReadinessItem;
  onOpenModuleDetail: (key: BondAnalyticsModuleKey) => void;
}) {
  const surface = readinessSurface(item.statusLabel);
  const warningText = item.warnings[0] ?? null;

  return (
    <div
      style={{
        border: `1px solid ${surface.borderColor}`,
        background: surface.background,
        borderRadius: 18,
        padding: 14,
        display: "grid",
        gap: 10,
      }}
      data-testid={`bond-analysis-readiness-${item.key}`}
      data-promotion-destination={item.promotionDestination}
    >
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
        <div style={{ display: "grid", gap: 5, minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            <div style={{ fontSize: 14, fontWeight: 700, color: "#16304f" }}>{item.label}</div>
            <span
              style={{
                fontSize: 11,
                color: surface.accent,
                fontWeight: 700,
                textTransform: "uppercase",
                letterSpacing: "0.08em",
              }}
            >
              {promotionLabel(item.promotionDestination)}
            </span>
          </div>
          <div style={{ color: "#52657f", fontSize: 12 }}>{item.description}</div>
        </div>
        <Tag color={readinessTagColor(item.statusLabel)}>{item.statusLabel}</Tag>
      </div>
      <div style={{ color: surface.text, fontSize: 12, lineHeight: 1.6 }}>{item.statusReason}</div>
      <div style={{ color: "#73859e", fontSize: 12, lineHeight: 1.6 }}>{item.detailHint}</div>
      {warningText ? (
        <div
          style={{
            borderRadius: 14,
            padding: "9px 11px",
            background: "rgba(255,255,255,0.72)",
            color: surface.text,
            fontSize: 12,
            lineHeight: 1.5,
          }}
        >
          {warningText}
        </div>
      ) : null}
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
        <Button size="small" type="default" onClick={() => onOpenModuleDetail(item.key)} data-testid={`bond-analysis-open-${item.key}`}>
          Open detail
        </Button>
        <div style={{ color: "#7f90a6", fontSize: 11 }}>
          Current lane: {item.promotionDestination === "headline" ? "governed headline" : "drill"}
        </div>
      </div>
    </div>
  );
}

export interface BondAnalyticsReadinessMatrixProps {
  readinessItems: BondAnalyticsReadinessItem[];
  onOpenModuleDetail: (key: BondAnalyticsModuleKey) => void;
}

export function BondAnalyticsReadinessMatrix({ readinessItems, onOpenModuleDetail }: BondAnalyticsReadinessMatrixProps) {
  return (
    <Card size="small" data-testid="bond-analysis-readiness-matrix" style={panelStyle("#ffffff")}>
      <div style={{ display: "grid", gap: 12 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12, flexWrap: "wrap" }}>
          <div style={{ display: "grid", gap: 6 }}>
            <div style={EYEBROW}>Module readiness</div>
            <div style={{ fontSize: 18, fontWeight: 700, color: "#18314d" }}>Drill queue and promotion boundary</div>
          </div>
          <div style={{ color: "#7a8da5", fontSize: 12 }}>{readinessItems.length} overview-linked module(s)</div>
        </div>

        <div style={{ display: "grid", gap: 10 }}>
          {readinessItems.map((item) => (
            <ReadinessRow key={item.key} item={item} onOpenModuleDetail={onOpenModuleDetail} />
          ))}
        </div>
      </div>
    </Card>
  );
}
