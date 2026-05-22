import { useState } from "react";
import { NavLink } from "react-router-dom";

import type { DashboardCockpitNavGroup } from "../dashboardMockData";

type DashboardCockpitSidebarProps = {
  groups: readonly DashboardCockpitNavGroup[];
};

export function DashboardCockpitSidebar({ groups }: DashboardCockpitSidebarProps) {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <aside
      data-testid="dashboard-cockpit-sidebar"
      className={`dashboard-cockpit-sidebar${collapsed ? " dashboard-cockpit-sidebar--collapsed" : ""}`}
      aria-label="经营驾驶舱导航"
    >
      <nav className="dashboard-cockpit-sidebar__nav">
        {groups.map((group) => (
          <div key={group.id} className="dashboard-cockpit-sidebar__group">
            {group.label ? (
              <span className="dashboard-cockpit-sidebar__group-label">{group.label}</span>
            ) : null}
            <ul className="dashboard-cockpit-sidebar__list">
              {group.items.map((item) => (
                <li key={item.id}>
                  <NavLink
                    to={item.path}
                    end={item.path === "/"}
                    className={({ isActive }) =>
                      `dashboard-cockpit-sidebar__link${isActive ? " dashboard-cockpit-sidebar__link--active" : ""}`
                    }
                  >
                    {item.label}
                  </NavLink>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </nav>
      <button
        type="button"
        className="dashboard-cockpit-sidebar__collapse"
        onClick={() => setCollapsed((value) => !value)}
      >
        {collapsed ? "展开菜单" : "收起菜单"}
      </button>
    </aside>
  );
}
