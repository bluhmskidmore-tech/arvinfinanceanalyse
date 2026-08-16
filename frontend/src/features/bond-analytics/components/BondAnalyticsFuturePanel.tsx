import { Card } from "antd";

import type { BondAnalyticsFutureVisibilityItem } from "../lib/bondAnalyticsOverviewModel";
import { designTokens } from "../../../theme/designSystem";
import { EYEBROW, panelStyle } from "./bondAnalyticsCockpitTokens";

const dt = designTokens;

export interface BondAnalyticsFuturePanelProps {
  futureVisibilityItems: BondAnalyticsFutureVisibilityItem[];
}

export function BondAnalyticsFuturePanel({ futureVisibilityItems }: BondAnalyticsFuturePanelProps) {
  return (
    <Card
      size="small"
      data-testid="bond-analysis-future-panel"
      style={panelStyle(dt.color.institutional.surface /* 近似映射，原值 #fbfcff。 */)}
    >
      <div style={{ display: "grid", gap: 12 }}>
        <div style={EYEBROW}>暂缓与后续</div>
        <div style={{ fontSize: 18, fontWeight: 700, color: dt.color.primary[900] /* 近似映射，原值 #18314d。 */ }}>
          保留下阶段驾驶舱层级
        </div>
        <div
          style={{
            color: dt.color.cockpit.ink600, // 近似映射，原值 #60748d。
            fontSize: 12,
            lineHeight: 1.65,
          }}
        >
          这些页面保留在右上侧栏，用户可以看到规划范围，同时不会把路线图可见性误读成当前受治理事实。
        </div>
        <div style={{ display: "grid", gap: 10 }}>
          {futureVisibilityItems.map((item) => (
            <div
              key={item.key}
              style={{
                border: `1px dashed ${dt.color.cockpit.border200}`, // 近似映射，原值 #d5e0ee。
                borderRadius: 6,
                padding: "12px 13px",
                background: dt.color.cockpit.white,
                display: "grid",
                gap: 5,
              }}
            >
              <div style={{ fontSize: 13, fontWeight: 700, color: dt.color.primary[900] /* 近似映射，原值 #18314d。 */ }}>
                {item.label}
              </div>
              <div
                style={{
                  fontSize: 12,
                  color: dt.color.cockpit.ink600, // 近似映射，原值 #60748d。
                  lineHeight: 1.55,
                }}
              >
                {item.description}
              </div>
            </div>
          ))}
        </div>
      </div>
    </Card>
  );
}
