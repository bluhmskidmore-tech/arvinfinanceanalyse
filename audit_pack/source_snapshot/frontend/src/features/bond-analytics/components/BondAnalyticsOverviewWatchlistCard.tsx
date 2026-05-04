import { Card } from "antd";

import { EYEBROW, panelStyle } from "./bondAnalyticsCockpitTokens";

export interface BondAnalyticsOverviewWatchlistCardProps {
  topAnomalies: string[];
}

export function BondAnalyticsOverviewWatchlistCard({ topAnomalies }: BondAnalyticsOverviewWatchlistCardProps) {
  return (
    <Card size="small" style={panelStyle("#ffffff")}>
      <div style={{ display: "grid", gap: 12 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12, flexWrap: "wrap" }}>
          <div style={{ display: "grid", gap: 6 }}>
            <div style={EYEBROW}>总览观察清单</div>
            <div style={{ fontSize: 18, fontWeight: 700, color: "#18314d" }}>异常与就绪信号</div>
          </div>
          <div style={{ color: "#7a8da5", fontSize: 12 }}>
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
                  borderRadius: 16,
                  border: "1px solid #efd9b6",
                  background: "#fff8ef",
                  padding: "12px 14px",
                  color: "#88591a",
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
              borderRadius: 16,
              border: "1px solid #e2eaf2",
              background: "#f8fbfe",
              padding: "13px 14px",
              color: "#5c718b",
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
