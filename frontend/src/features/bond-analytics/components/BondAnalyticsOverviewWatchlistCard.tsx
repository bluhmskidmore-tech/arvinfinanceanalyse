import { Card } from "antd";

import { designTokens } from "../../../theme/designSystem";
import { EYEBROW, panelStyle } from "./bondAnalyticsCockpitTokens";

const dt = designTokens;

export interface BondAnalyticsOverviewWatchlistCardProps {
  topAnomalies: string[];
}

export function BondAnalyticsOverviewWatchlistCard({ topAnomalies }: BondAnalyticsOverviewWatchlistCardProps) {
  return (
    <Card size="small" style={panelStyle(dt.color.cockpit.white)}>
      <div style={{ display: "grid", gap: 12 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12, flexWrap: "wrap" }}>
          <div style={{ display: "grid", gap: 6 }}>
            <div style={EYEBROW}>总览观察清单</div>
            <div style={{ fontSize: 18, fontWeight: 700, color: dt.color.primary[900] /* 近似映射，原值 #18314d。 */ }}>
              异常与就绪信号
            </div>
          </div>
          <div style={{ color: dt.color.cockpit.ink450 /* 近似映射，原值 #7a8da5。 */, fontSize: 12 }}>
            {topAnomalies.length > 0
              ? `${topAnomalies.length} 个标记信号`
              : "当前总览载荷未触发异常。"}
          </div>
        </div>

        {topAnomalies.length > 0 ? (
          <div style={{ display: "grid", gap: 10 }}>
            {topAnomalies.map((anomaly) => (
              <div
                key={anomaly}
                style={{
                  borderRadius: 6,
                  border: `1px solid ${dt.color.cockpit.amber100}`, // 近似映射，原值 #efd9b6。
                  background: dt.color.cockpit.amber25, // 近似映射，原值 #fff8ef。
                  padding: "12px 14px",
                  color: dt.color.cockpit.amber800, // 近似映射，原值 #88591a。
                  fontSize: 13,
                  lineHeight: 1.6,
                }}
              >
                {anomaly}
              </div>
            ))}
          </div>
        ) : (
          <div
            style={{
              borderRadius: 6,
              border: `1px solid ${dt.color.institutional.divider}`, // 近似映射，原值 #e2eaf2。
              background: dt.color.cockpit.blueMist, // 近似映射，原值 #f8fbfe。
              padding: "13px 14px",
              color: dt.color.cockpit.ink600, // 近似映射，原值 #5c718b。
              fontSize: 13,
              lineHeight: 1.65,
            }}
          >
            当前总览载荷平稳。可使用右侧决策队列选择下一步下钻页面，不强行生成合成首屏指标。
          </div>
        )}
      </div>
    </Card>
  );
}
