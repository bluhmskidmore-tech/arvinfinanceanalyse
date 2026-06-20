import { Button, Card, Tag } from "antd";

import type { BondAnalyticsActiveModuleContext, BondAnalyticsReadinessItem } from "../lib/bondAnalyticsOverviewModel";
import type { BondAnalyticsModuleKey } from "../lib/bondAnalyticsModuleRegistry";
import { EYEBROW, panelStyle, readinessStatusLabel, readinessSurface, readinessTagColor } from "./bondAnalyticsCockpitTokens";

export interface BondAnalyticsDecisionRailProps {
  activeModuleContext: BondAnalyticsActiveModuleContext;
  activeReadinessItem: BondAnalyticsReadinessItem;
  watchlistItems: BondAnalyticsReadinessItem[];
  onOpenModuleDetail: (key: BondAnalyticsModuleKey) => void;
}

export function BondAnalyticsDecisionRail({
  activeModuleContext,
  activeReadinessItem,
  watchlistItems,
  onOpenModuleDetail,
}: BondAnalyticsDecisionRailProps) {
  const activeSurface = readinessSurface(activeReadinessItem.statusLabel);

  return (
    <Card size="small" style={panelStyle("linear-gradient(180deg, #ffffff 0%, #f8fbff 100%)")}>
      <div style={{ display: "grid", gap: 14 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12, flexWrap: "wrap" }}>
          <div style={{ display: "grid", gap: 6 }}>
            <div style={EYEBROW}>决策侧栏</div>
            <div style={{ fontSize: 18, fontWeight: 700, color: "#18314d" }}>{activeModuleContext.label}</div>
          </div>
          <Tag color={readinessTagColor(activeReadinessItem.statusLabel)}>
            {readinessStatusLabel(activeReadinessItem.statusLabel)}
          </Tag>
        </div>

        <div
          style={{
            borderRadius: 18,
            border: `1px solid ${activeSurface.borderColor}`,
            background: activeSurface.background,
            padding: "14px 15px",
            display: "grid",
            gap: 8,
          }}
        >
          <div
            style={{
              color: activeSurface.accent,
              fontSize: 11,
              fontWeight: 700,
              textTransform: "uppercase",
              letterSpacing: "0.08em",
            }}
          >
            当前决策上下文
          </div>
          <div style={{ color: "#18314d", fontSize: 13, lineHeight: 1.65 }}>{activeModuleContext.description}</div>
          <div style={{ color: activeSurface.text, fontSize: 12, lineHeight: 1.65 }}>{activeModuleContext.statusReason}</div>
        </div>

        <div style={{ display: "grid", gap: 8 }}>
          <div
            style={{
              color: "#6b7f99",
              fontSize: 11,
              fontWeight: 700,
              textTransform: "uppercase",
              letterSpacing: "0.08em",
            }}
          >
            下一步观察项
          </div>
          {watchlistItems.slice(0, 2).map((item) => (
            <div key={item.key} style={{ display: "grid", gap: 4, paddingBottom: 8, borderBottom: "1px solid #ebf0f5" }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: "#18314d" }}>{item.label}</div>
              <div style={{ color: "#60748d", fontSize: 12, lineHeight: 1.55 }}>{item.statusReason}</div>
            </div>
          ))}
        </div>

        <Button size="small" type="default" onClick={() => onOpenModuleDetail(activeModuleContext.key)}>
          打开当前下钻
        </Button>
      </div>
    </Card>
  );
}
