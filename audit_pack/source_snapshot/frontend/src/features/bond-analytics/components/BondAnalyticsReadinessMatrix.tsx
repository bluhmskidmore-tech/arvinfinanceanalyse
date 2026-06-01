import { Button, Card, Tag } from "antd";

import { designTokens } from "../../../theme/designSystem";
import type { BondAnalyticsReadinessItem } from "../lib/bondAnalyticsOverviewModel";
import type { BondAnalyticsModuleKey } from "../lib/bondAnalyticsModuleRegistry";
import { EYEBROW, panelStyle, promotionLabel, readinessStatusLabel, readinessSurface, readinessTagColor } from "./bondAnalyticsCockpitTokens";

const dt = designTokens;

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
        borderRadius: dt.radius.lg,
        padding: dt.space[4],
        display: "grid",
        gap: dt.space[3],
      }}
      data-testid={`bond-analysis-readiness-${item.key}`}
      data-promotion-destination={item.promotionDestination}
    >
      <div style={{ display: "flex", justifyContent: "space-between", gap: dt.space[3], flexWrap: "wrap" }}>
        <div style={{ display: "grid", gap: dt.space[2], minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: dt.space[2], flexWrap: "wrap" }}>
            <div style={{ fontSize: dt.fontSize[14], fontWeight: 700, color: dt.color.primary[900] }}>{item.label}</div>
            <span
              style={{
                fontSize: dt.fontSize[11],
                color: surface.accent,
                fontWeight: 700,
                textTransform: "uppercase",
                letterSpacing: "0.08em",
              }}
            >
              {promotionLabel(item.promotionDestination)}
            </span>
          </div>
          <div style={{ color: dt.color.neutral[700], fontSize: dt.fontSize[12] }}>{item.description}</div>
        </div>
        <Tag color={readinessTagColor(item.statusLabel)}>{readinessStatusLabel(item.statusLabel)}</Tag>
      </div>
      <div style={{ color: surface.text, fontSize: dt.fontSize[12], lineHeight: 1.6 }}>{item.statusReason}</div>
      <div style={{ color: dt.color.neutral[600], fontSize: dt.fontSize[12], lineHeight: 1.6 }}>{item.detailHint}</div>
      {warningText ? (
        <div
          style={{
            borderRadius: dt.radius.md,
            padding: `${dt.space[2]}px ${dt.space[3]}px`,
            background: `${dt.color.neutral[50]}B8`,
            color: surface.text,
            fontSize: dt.fontSize[12],
            lineHeight: 1.5,
          }}
        >
          {warningText}
        </div>
      ) : null}
      <div style={{ display: "flex", justifyContent: "space-between", gap: dt.space[3], flexWrap: "wrap" }}>
        <Button size="small" type="default" onClick={() => onOpenModuleDetail(item.key)} data-testid={`bond-analysis-open-${item.key}`}>
          打开明细
        </Button>
        <div style={{ color: dt.color.neutral[500], fontSize: dt.fontSize[11] }}>
          当前路径：{item.promotionDestination === "headline" ? "治理头条" : "下钻"}
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
    <Card size="small" data-testid="bond-analysis-readiness-matrix" style={panelStyle(dt.color.neutral[50])}>
      <div style={{ display: "grid", gap: dt.space[3] }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: dt.space[3], flexWrap: "wrap" }}>
          <div style={{ display: "grid", gap: dt.space[2] }}>
            <div style={EYEBROW}>模块就绪</div>
            <div style={{ fontSize: dt.fontSize[18], fontWeight: 700, color: dt.color.primary[900] }}>下钻队列与主位边界</div>
          </div>
          <div style={{ color: dt.color.neutral[600], fontSize: dt.fontSize[12] }}>{readinessItems.length} 个总览关联模块</div>
        </div>

        <div style={{ display: "grid", gap: dt.space[3] }}>
          {readinessItems.map((item) => (
            <ReadinessRow key={item.key} item={item} onOpenModuleDetail={onOpenModuleDetail} />
          ))}
        </div>
      </div>
    </Card>
  );
}
