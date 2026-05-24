import { Link } from "react-router-dom";

import type { DashboardCockpitHomeViewModel } from "../dashboardCockpitHomeModel";
import { resolveKpiDeltaClass } from "../dashboardCockpitHomeModel";

type DashboardEvidenceLaneProps = {
  viewModel: DashboardCockpitHomeViewModel;
};

function formatTrendValue(value: number | null): string {
  if (value == null || Number.isNaN(value)) return "--";
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)} 亿`;
}

function trendTone(value: number | null): "up" | "down" | "flat" {
  if (value == null || Number.isNaN(value)) return "flat";
  if (value > 0) return "up";
  if (value < 0) return "down";
  return "flat";
}

function latestTrendValue(values: readonly number[]): number | null {
  for (let index = values.length - 1; index >= 0; index -= 1) {
    const value = values[index];
    if (typeof value === "number" && !Number.isNaN(value)) return value;
  }
  return null;
}

export function DashboardEvidenceLane({ viewModel }: DashboardEvidenceLaneProps) {
  const maxAbsTrend = Math.max(
    1,
    ...viewModel.productPnl.series.flatMap((series) =>
      series.values.map((value) => Math.abs(value)),
    ),
  );
  const trendRows = viewModel.productPnl.series.map((series) => {
    const latest = latestTrendValue(series.values);
    return {
      ...series,
      latest,
      width: latest == null ? 0 : Math.min(100, Math.abs(latest) / maxAbsTrend * 100),
    };
  });

  return (
    <section
      data-testid="dashboard-evidence-lane"
      className="dashboard-cockpit-evidence-lane"
      aria-label="首屏证据补充"
    >
      <section
        data-testid="dashboard-evidence-balance"
        className="dashboard-cockpit-panel dashboard-cockpit-evidence-panel dashboard-cockpit-evidence-panel--balance"
      >
        <header className="dashboard-cockpit-panel__head">
          <span className="dashboard-cockpit-panel__eyebrow">经营与资产负债</span>
          <h2 className="dashboard-cockpit-panel__title">关键补充指标</h2>
        </header>
        <div className="dashboard-cockpit-evidence-metrics">
          {viewModel.balanceMetrics.map((metric) => (
            <article key={metric.id} data-testid={`dashboard-evidence-balance-${metric.id}`}>
              <span>{metric.label}</span>
              <strong className="dashboard-cockpit-tabular">{metric.value}</strong>
              <em
                className={resolveKpiDeltaClass(
                  metric.tone === "positive"
                    ? "up"
                    : metric.tone === "negative"
                      ? "down"
                      : metric.tone === "warning"
                        ? "warn"
                        : "flat",
                )}
              >
                {metric.delta}
              </em>
            </article>
          ))}
        </div>
      </section>

      <section
        data-testid="dashboard-evidence-trend"
        className="dashboard-cockpit-panel dashboard-cockpit-evidence-panel dashboard-cockpit-evidence-panel--trend"
      >
        <header className="dashboard-cockpit-panel__head">
          <span className="dashboard-cockpit-panel__eyebrow">产品损益</span>
          <h2 className="dashboard-cockpit-panel__title">月度趋势快照</h2>
        </header>
        <div className="dashboard-cockpit-evidence-trends">
          {trendRows.map((series) => (
            <article key={series.id} data-testid={`dashboard-evidence-trend-${series.id}`}>
              <span>{series.name}</span>
              <i aria-hidden="true">
                <b
                  data-tone={trendTone(series.latest)}
                  style={{ width: `${series.width}%` }}
                />
              </i>
              <strong className={`dashboard-cockpit-tabular ${resolveKpiDeltaClass(trendTone(series.latest))}`}>
                {formatTrendValue(series.latest)}
              </strong>
            </article>
          ))}
        </div>
      </section>

      <section
        data-testid="dashboard-evidence-exposure"
        className="dashboard-cockpit-panel dashboard-cockpit-evidence-panel dashboard-cockpit-evidence-panel--exposure"
      >
        <header className="dashboard-cockpit-panel__head">
          <span className="dashboard-cockpit-panel__eyebrow">账户与暴露</span>
          <h2 className="dashboard-cockpit-panel__title">账户暴露摘要</h2>
        </header>
        <div className="dashboard-cockpit-evidence-table-wrap">
          <table className="dashboard-cockpit-evidence-table">
            <thead>
              <tr>
                <th>账户</th>
                <th>类型</th>
                <th>资产规模</th>
                <th>占比</th>
                <th>久期</th>
                <th>DV01</th>
                <th>日收益</th>
              </tr>
            </thead>
            <tbody>
              {viewModel.exposureRows.map((row) => (
                <tr key={row.id} data-row-tone={row.tone}>
                  <td>{row.account}</td>
                  <td>{row.type}</td>
                  <td className="dashboard-cockpit-tabular">{row.assetScale}</td>
                  <td className="dashboard-cockpit-tabular">{row.weight}</td>
                  <td className="dashboard-cockpit-tabular">{row.duration}</td>
                  <td className="dashboard-cockpit-tabular">{row.dv01}</td>
                  <td
                    className={`dashboard-cockpit-tabular ${resolveKpiDeltaClass(
                      row.tone === "positive" ? "up" : row.tone === "negative" ? "down" : "flat",
                    )}`}
                  >
                    {row.dailyPnl}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="dashboard-cockpit-evidence-links" aria-label="证据下钻入口">
          {viewModel.quickDrilldowns.slice(0, 5).map((item) => (
            <Link key={item.id} to={item.path}>
              {item.label}
            </Link>
          ))}
        </div>
      </section>
    </section>
  );
}
