import { useState } from "react";

import { tabularNumsStyle } from "../../../../theme/designSystem";
import type { DashboardAttributionTab, DashboardCockpitHomeViewModel } from "../dashboardCockpitHomeModel";
import { resolveKpiDeltaClass } from "../dashboardCockpitHomeModel";
import type { DashboardCockpitWaterfallItem } from "../dashboardCockpitModel";

type AttributionPanelProps = {
  tabs: DashboardCockpitHomeViewModel["attributionTabs"];
  waterfall: readonly DashboardCockpitWaterfallItem[];
  note: readonly string[];
};

function maxWaterfallRaw(items: readonly DashboardCockpitWaterfallItem[]): number {
  return Math.max(
    ...items.map((item) => {
      const n = parseFloat(item.value.replace(/[^\d.-]/g, ""));
      return Number.isFinite(n) ? Math.abs(n) : 0;
    }),
    1,
  );
}

export function AttributionPanel({ tabs, waterfall, note }: AttributionPanelProps) {
  const [activeTab, setActiveTab] = useState<DashboardAttributionTab>("day");
  const active = tabs.find((tab) => tab.id === activeTab) ?? tabs[0]!;
  const max = maxWaterfallRaw(waterfall);

  return (
    <section
      data-testid="dashboard-attribution-panel"
      className="dashboard-cockpit-panel dashboard-cockpit-panel--attribution"
    >
      <header className="dashboard-cockpit-panel__head">
        <span className="dashboard-cockpit-panel__eyebrow">今日归因</span>
        <h2 className="dashboard-cockpit-panel__title">损益拆解</h2>
        <div className="dashboard-cockpit-tabs" role="tablist" aria-label="归因周期">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              type="button"
              role="tab"
              aria-selected={tab.id === activeTab}
              className={`dashboard-cockpit-tabs__btn${tab.id === activeTab ? " dashboard-cockpit-tabs__btn--active" : ""}`}
              onClick={() => setActiveTab(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </header>
      <div className="dashboard-cockpit-panel__body">
        <div className="dashboard-cockpit-attrib-summary">
          <article>
            <span>当日损益</span>
            <strong style={tabularNumsStyle}>{active.pnl}</strong>
          </article>
          <article>
            <span>变化</span>
            <strong className={resolveKpiDeltaClass(active.changeTone)} style={tabularNumsStyle}>
              {active.change}
            </strong>
          </article>
          <article>
            <span>收益率</span>
            <strong style={tabularNumsStyle}>{active.yield}</strong>
          </article>
        </div>
        <div
          data-testid="dashboard-cockpit-waterfall"
          className="dashboard-cockpit-waterfall"
        >
          {waterfall.map((item) => {
            const n = parseFloat(item.value.replace(/[^\d.-]/g, ""));
            const height = Number.isFinite(n) ? Math.max(14, (Math.abs(n) / max) * 112) : 14;
            return (
              <div key={item.id} className="dashboard-cockpit-attrib-waterfall__step">
                <div
                  className={`dashboard-cockpit-attrib-waterfall__bar dashboard-cockpit-tone-${item.tone}`}
                  style={{ height: `${height}px` }}
                />
                <span className="dashboard-cockpit-attrib-waterfall__label">{item.label}</span>
                <strong style={tabularNumsStyle}>{item.value}</strong>
              </div>
            );
          })}
        </div>
        <div className="dashboard-cockpit-attrib-note">
          <h3>组合变化说明</h3>
          <ul>
            {note.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}
