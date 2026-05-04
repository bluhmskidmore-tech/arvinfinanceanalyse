import type { PortfolioStatistics } from "../../data-structures/PortfolioModel";

export interface PortfolioStatsProps {
  statistics?: PortfolioStatistics;
}

function formatPct(value?: number) {
  return value === undefined ? "--" : `${value.toFixed(2)}%`;
}

export function PortfolioStats({ statistics }: PortfolioStatsProps) {
  const entries = [
    { label: "平均收益率", value: formatPct(statistics?.averageYield) },
    {
      label: "加权久期",
      value: statistics?.weightedDuration === undefined ? "--" : statistics.weightedDuration.toFixed(2),
    },
    {
      label: "集中度",
      value:
        statistics?.concentrationRatio === undefined
          ? "--"
          : `${(statistics.concentrationRatio * 100).toFixed(1)}%`,
    },
    {
      label: "风险评分",
      value: statistics?.riskScore === undefined ? "--" : String(statistics.riskScore),
    },
  ];

  return (
    <section style={{ display: "grid", gap: 12 }}>
      <h3 style={{ margin: 0 }}>组合统计</h3>
      <div style={{ display: "grid", gap: 12, gridTemplateColumns: "repeat(4, minmax(0, 1fr))" }}>
        {entries.map((entry) => (
          <div
            key={entry.label}
            style={{ borderRadius: 16, border: "1px solid #d0d5dd", padding: 16, background: "#fff" }}
          >
            <div style={{ color: "#475467", fontSize: 12 }}>{entry.label}</div>
            <div style={{ fontSize: 24, fontWeight: 700 }}>{entry.value}</div>
          </div>
        ))}
      </div>
    </section>
  );
}
