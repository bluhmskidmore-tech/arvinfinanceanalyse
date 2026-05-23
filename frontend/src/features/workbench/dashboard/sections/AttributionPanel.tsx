import { useMemo } from "react";

import { tabularNumsStyle } from "../../../../theme/designSystem";
import type { DashboardCockpitHomeViewModel } from "../dashboardCockpitHomeModel";
import { resolveKpiDeltaClass } from "../dashboardCockpitHomeModel";
import { parseCockpitDisplayNumber } from "../dashboardCockpitChartTheme";
import type { DashboardCockpitWaterfallItem } from "../dashboardCockpitModel";

type AttributionPanelProps = {
  tabs: DashboardCockpitHomeViewModel["attributionTabs"];
  waterfall: readonly DashboardCockpitWaterfallItem[];
  note: readonly string[];
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

export function AttributionPanel({ tabs, waterfall, note }: AttributionPanelProps) {
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
      data-testid="dashboard-attribution-panel"
      className="dashboard-cockpit-panel dashboard-cockpit-panel--attribution"
    >
      <header className="dashboard-cockpit-panel__head">
        <span className="dashboard-cockpit-panel__eyebrow">归因</span>
        <h2 className="dashboard-cockpit-panel__title">收益拆解</h2>
      </header>
      <div className="dashboard-cockpit-panel__body">
        <p
          className={`dashboard-cockpit-attrib-total ${resolveKpiDeltaClass(active.changeTone)}`}
          style={tabularNumsStyle}
        >
          {active.pnl}
        </p>
        <div
          data-testid="dashboard-cockpit-waterfall"
          className="dashboard-cockpit-attrib-rows"
        >
          {rows.map((item) => (
            <div key={item.id} className="dashboard-cockpit-attrib-row">
              <span className="dashboard-cockpit-attrib-row__label">{item.label}</span>
              <span className="dashboard-cockpit-attrib-row__bar">
                <i className={toneClass(item.tone)} style={{ width: `${barWidth(item.value, maxAbs)}%` }} />
              </span>
              <strong className={`dashboard-cockpit-attrib-row__value ${toneClass(item.tone)}`} style={tabularNumsStyle}>
                {item.value}
              </strong>
            </div>
          ))}
        </div>
        {note[0] ? (
          <p className="dashboard-cockpit-attrib-note-line">{note[0]}</p>
        ) : null}
      </div>
    </section>
  );
}
