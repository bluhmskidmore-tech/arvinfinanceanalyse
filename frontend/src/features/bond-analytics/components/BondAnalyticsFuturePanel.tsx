import { Card } from "antd";

import type { BondAnalyticsFutureVisibilityItem } from "../lib/bondAnalyticsOverviewModel";
import { EYEBROW, panelStyle } from "./bondAnalyticsCockpitTokens";

export interface BondAnalyticsFuturePanelProps {
  futureVisibilityItems: BondAnalyticsFutureVisibilityItem[];
}

export function BondAnalyticsFuturePanel({ futureVisibilityItems }: BondAnalyticsFuturePanelProps) {
  return (
    <Card size="small" data-testid="bond-analysis-future-panel" style={panelStyle("#fbfcff")}>
      <div style={{ display: "grid", gap: 12 }}>
        <div style={EYEBROW}>暂缓与后续</div>
        <div style={{ fontSize: 18, fontWeight: 700, color: "#18314d" }}>保留下阶段驾驶舱层级</div>
        <div style={{ color: "#60748d", fontSize: 12, lineHeight: 1.65 }}>
          这些页面保留在右上侧栏，用户可以看到规划范围，同时不会把路线图可见性误读成当前受治理事实。
        </div>
        <div style={{ display: "grid", gap: 10 }}>
          {futureVisibilityItems.map((item) => (
            <div
              key={item.key}
              style={{
                border: "1px dashed #d5e0ee",
                borderRadius: 16,
                padding: "12px 13px",
                background: "#ffffff",
                display: "grid",
                gap: 5,
              }}
            >
              <div style={{ fontSize: 13, fontWeight: 700, color: "#18314d" }}>{item.label}</div>
              <div style={{ fontSize: 12, color: "#60748d", lineHeight: 1.55 }}>{item.description}</div>
            </div>
          ))}
        </div>
      </div>
    </Card>
  );
}
