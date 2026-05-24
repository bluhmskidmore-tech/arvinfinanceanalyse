import { Link } from "react-router-dom";

import type { DashboardQuickDrilldownMock } from "../dashboardMockData";

type QuickDrilldownProps = {
  items: readonly DashboardQuickDrilldownMock[];
  showStaticNavigationNote?: boolean;
  testId?: string;
  variant?: "default" | "compact";
};

export function QuickDrilldown({
  items,
  showStaticNavigationNote = true,
  testId = "dashboard-quick-drilldown",
  variant = "default",
}: QuickDrilldownProps) {
  return (
    <section
      data-testid={testId}
      className={`dashboard-cockpit-panel dashboard-cockpit-panel--drill${variant === "compact" ? " dashboard-cockpit-panel--drill-compact" : ""}`}
    >
      <header className="dashboard-cockpit-panel__head">
        <span className="dashboard-cockpit-panel__eyebrow">下钻</span>
        <h2 className="dashboard-cockpit-panel__title">快捷入口</h2>
      </header>
      <div className="dashboard-cockpit-drill-grid">
        {items.map((item) => {
          const pending = item.path === "#";
          const card = (
            <>
              <strong>{item.label}</strong>
              <span>{item.description}</span>
            </>
          );
          const testId =
            item.id === "trades" ? "dashboard-drill-trades" : `dashboard-drill-${item.id}`;

          if (pending) {
            return (
              <a
                key={item.id}
                href="#"
                className="dashboard-cockpit-drill-card dashboard-cockpit-drill-card--pending"
                data-testid={testId}
                title="待开放"
                onClick={(event) => event.preventDefault()}
              >
                {card}
              </a>
            );
          }

          return (
            <Link key={item.id} to={item.path} className="dashboard-cockpit-drill-card" data-testid={testId}>
              {card}
            </Link>
          );
        })}
      </div>
      {showStaticNavigationNote ? (
        <p className="dashboard-cockpit-panel__disclaimer">固定导航入口；同日摘要数字请进入专题页查看</p>
      ) : null}
    </section>
  );
}
