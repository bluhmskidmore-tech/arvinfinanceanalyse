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
            <div style={EYEBROW}>Overview watchlist</div>
            <div style={{ fontSize: 18, fontWeight: 700, color: "#18314d" }}>Anomalies and readiness signals</div>
          </div>
          <div style={{ color: "#7a8da5", fontSize: 12 }}>
            {topAnomalies.length > 0
              ? `${topAnomalies.length} flagged signal(s)`
              : "No anomaly is currently raised in the overview payload."}
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
            The overview payload is currently calm. Use the right-rail decision queue to pick the next drill surface without
            forcing synthetic top-line metrics.
          </div>
        )}
      </div>
    </Card>
  );
}
