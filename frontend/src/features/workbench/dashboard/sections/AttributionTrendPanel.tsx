import { useMemo } from "react";

import { tabularNumsStyle } from "../../../../theme/designSystem";
import type { DashboardCockpitHomeViewModel } from "../dashboardCockpitHomeModel";
import { resolveKpiDeltaClass } from "../dashboardCockpitHomeModel";
import { parseCockpitDisplayNumber } from "../dashboardCockpitChartTheme";
import type { DashboardCockpitWaterfallItem } from "../dashboardCockpitModel";
import { COCKPIT_CHART_PALETTE } from "../dashboardCockpitVisualTokens";

type AttributionTrendPanelProps = {
  tabs: DashboardCockpitHomeViewModel["attributionTabs"];
  waterfall: readonly DashboardCockpitWaterfallItem[];
  note: readonly string[];
  productPnl: DashboardCockpitHomeViewModel["productPnl"];
};

function isAttributionRow(item: DashboardCockpitWaterfallItem): boolean {
  const label = item.label.trim();
  return label !== "期初" && label !== "期末" && !label.includes("合计");
}

function barWidth(value: string, maxAbs: number): number {
  const parsed = parseCockpitDisplayNumber(value);
  if (parsed == null || maxAbs <= 0) return 0;
  return Math.min(100, (Math.abs(parsed) / maxAbs) * 100);
}

function toneClass(tone: DashboardCockpitWaterfallItem["tone"]): string {
  if (tone === "positive") return "dashboard-cockpit-tone-positive";
  if (tone === "negative") return "dashboard-cockpit-tone-negative";
  return "dashboard-cockpit-tone-neutral";
}

function trendPath(values: readonly number[], width: number, height: number): string {
  if (values.length === 0) {
    return "";
  }
  const allValues = values.filter((value) => Number.isFinite(value));
  if (allValues.length === 0) {
    return "";
  }
  const min = Math.min(...allValues);
  const max = Math.max(...allValues);
  const marginX = 8;
  const marginY = 8;
  const innerW = width - marginX * 2;
  const innerH = height - marginY * 2;
  return values
    .map((value, index) => {
      const x = marginX + (values.length === 1 ? innerW : (index / (values.length - 1)) * innerW);
      const y =
        min === max
          ? height / 2
          : marginY + innerH * (1 - (value - min) / (max - min));
      return `${index === 0 ? "M" : "L"} ${x} ${y}`;
    })
    .join(" ");
}

export function AttributionTrendPanel({
  tabs,
  waterfall,
  note,
  productPnl,
}: AttributionTrendPanelProps) {
  const active = tabs.find((tab) => tab.id === "day") ?? tabs[0]!;
  const rows = useMemo(() => waterfall.filter(isAttributionRow), [waterfall]);
  const maxAbs = useMemo(() => {
    let max = 0;
    for (const row of rows) {
      const parsed = parseCockpitDisplayNumber(row.value);
      if (parsed != null) max = Math.max(max, Math.abs(parsed));
    }
    return max;
  }, [rows]);

  return (
    <section
      data-testid="dashboard-attribution-trend-panel"
      className="dashboard-cockpit-panel dashboard-terminal-attribution-trend"
    >
      <header className="dashboard-cockpit-panel__head dashboard-terminal-panel-head-inline">
        <div>
          <span className="dashboard-cockpit-panel__eyebrow">归因与趋势</span>
          <h2 className="dashboard-cockpit-panel__title">今日归因</h2>
        </div>
        <div className="dashboard-cockpit-tabs dashboard-cockpit-attrib-tabs" aria-label="归因周期">
          {tabs.map((tab) => (
            <span
              key={tab.id}
              className={`dashboard-cockpit-tabs__btn${tab.id === active.id ? " dashboard-cockpit-tabs__btn--active" : ""}`}
              data-active={tab.id === active.id ? "true" : "false"}
            >
              {tab.label}
            </span>
          ))}
        </div>
      </header>
      <div className="dashboard-cockpit-panel__body">
        <div data-testid="dashboard-attribution-panel" className="dashboard-terminal-attribution-block">
          <div className="dashboard-cockpit-attrib-summary dashboard-terminal-attrib-summary">
            <article>
              <span>{active.label}损益</span>
              <strong className={resolveKpiDeltaClass(active.changeTone)} style={tabularNumsStyle}>
                {active.pnl}
              </strong>
            </article>
            <article>
              <span>较昨日变化</span>
              <strong className={resolveKpiDeltaClass(active.changeTone)} style={tabularNumsStyle}>
                {active.change}
              </strong>
            </article>
            <article>
              <span>日度收益率</span>
              <strong
                className={active.yield === "—" ? "dashboard-home-muted" : undefined}
                style={tabularNumsStyle}
                title={active.yield === "—" ? "日度收益率暂未返回" : undefined}
              >
                {active.yield}
              </strong>
            </article>
          </div>
          <div
            data-testid="dashboard-cockpit-waterfall"
            className="dashboard-cockpit-attrib-rows dashboard-terminal-waterfall"
          >
            {rows.map((item) => (
              <div key={item.id} className="dashboard-cockpit-attrib-row">
                <span className="dashboard-cockpit-attrib-row__label">{item.label}</span>
                <span className="dashboard-cockpit-attrib-row__bar">
                  <i
                    className={toneClass(item.tone)}
                    style={{ width: `${barWidth(item.value, maxAbs)}%` }}
                  />
                </span>
                <strong
                  className={`dashboard-cockpit-attrib-row__value ${toneClass(item.tone)}`}
                  style={tabularNumsStyle}
                >
                  {item.value}
                </strong>
              </div>
            ))}
          </div>
          {note[0] ? <p className="dashboard-cockpit-attrib-note-line">{note[0]}</p> : null}
        </div>

        <div
          data-testid="dashboard-attribution-product-trend"
          className="dashboard-terminal-mini-trend"
          aria-label="月度产品分类损益"
        >
          <div className="dashboard-terminal-mini-trend__head">
            <span>
              月度产品分类损益
              <b>补充读面</b>
            </span>
            <em>单位：亿</em>
          </div>
          {productPnl.pending ? (
            <div
              data-testid="dashboard-product-pnl-pending"
              className="dashboard-terminal-mini-trend__empty dashboard-home-muted"
            >
              <strong>月度读面待展开</strong>
              <small>展开深钻读面查看正式月度趋势</small>
            </div>
          ) : (
            <svg
              className="dashboard-terminal-mini-trend__chart"
              viewBox="0 0 360 118"
              role="img"
              aria-label="月度产品分类损益图"
            >
              <path d="M 8 90 L 352 90" className="dashboard-terminal-mini-trend__grid" />
              <path d="M 8 58 L 352 58" className="dashboard-terminal-mini-trend__grid" />
              {productPnl.series.map((series, index) => (
                <path
                  key={series.id}
                  d={trendPath(series.values, 360, 118)}
                  className="dashboard-terminal-mini-trend__line"
                  style={{ stroke: COCKPIT_CHART_PALETTE[index % COCKPIT_CHART_PALETTE.length] }}
                />
              ))}
            </svg>
          )}
          <div className="dashboard-terminal-mini-trend__legend">
            {productPnl.series.map((series, index) => (
              <span key={series.id}>
                <i style={{ background: COCKPIT_CHART_PALETTE[index % COCKPIT_CHART_PALETTE.length] }} />
                {series.name}
              </span>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
