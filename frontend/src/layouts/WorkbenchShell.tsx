import {
  AppstoreOutlined,
  ApartmentOutlined,
  AlertOutlined,
  BarChartOutlined,
  BankOutlined,
  SettingOutlined,
  TeamOutlined,
  FundOutlined,
} from "@ant-design/icons";
import type { ReactNode } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";

import { workbenchNavigation } from "../mocks/navigation";

const iconMap: Record<string, ReactNode> = {
  dashboard: <AppstoreOutlined />,
  analysis: <BarChartOutlined />,
  risk: <AlertOutlined />,
  team: <TeamOutlined />,
  decision: <ApartmentOutlined />,
  bond: <BankOutlined />,
  settings: <SettingOutlined />,
  market: <FundOutlined />,
};

export function WorkbenchShell() {
  const location = useLocation();

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "grid",
        gridTemplateColumns: "264px minmax(0, 1fr)",
        gap: 18,
        padding: 18,
      }}
    >
      <aside
        style={{
          border: "1px solid #d7dfea",
          borderRadius: 28,
          overflow: "hidden",
          boxShadow: "0 18px 40px rgba(19, 37, 70, 0.08)",
          background: "#fbfcfe",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 12,
            padding: "24px 24px 18px",
            borderBottom: "1px solid #e3e9f2",
          }}
        >
          <div
            style={{
              display: "grid",
              placeItems: "center",
              width: 34,
              height: 34,
              borderRadius: 12,
              background: "#162033",
              color: "#fbfcfe",
              fontWeight: 700,
            }}
          >
            M
          </div>
          <div>
            <span
              style={{
                display: "block",
                color: "#162033",
                fontWeight: 600,
                fontSize: 18,
                letterSpacing: "-0.02em",
              }}
            >
              MOSS
            </span>
            <span
              style={{
                color: "#8090a8",
                fontSize: 12,
              }}
            >
              Workbench Shell
            </span>
          </div>
        </div>

        <nav
          aria-label="主导航"
          style={{
            display: "grid",
            gap: 6,
            padding: 16,
          }}
        >
          {workbenchNavigation.map((item) => {
            const active = location.pathname === item.path;

            return (
              <NavLink
                key={item.key}
                to={item.path}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 14,
                  padding: "14px 16px",
                  borderRadius: 16,
                  background: active ? "#e7efff" : "transparent",
                  color: active ? "#1f5eff" : "#485970",
                  fontWeight: active ? 600 : 500,
                  border: active
                    ? "1px solid #cddcff"
                    : "1px solid transparent",
                  transition: "background-color 160ms ease, color 160ms ease",
                }}
              >
                <span style={{ fontSize: 16 }}>{iconMap[item.icon]}</span>
                <span>{item.label}</span>
              </NavLink>
            );
          })}
        </nav>
      </aside>

      <div
        style={{
          display: "grid",
          gridTemplateRows: "84px minmax(0, 1fr)",
          gap: 18,
        }}
      >
        <header
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "0 24px",
            height: 84,
            border: "1px solid #d7dfea",
            borderRadius: 28,
            boxShadow: "0 18px 40px rgba(19, 37, 70, 0.08)",
            background: "#fbfcfe",
          }}
        >
          <div>
            <span
              style={{
                display: "block",
                color: "#8090a8",
                fontSize: 12,
                textTransform: "uppercase",
                letterSpacing: "0.08em",
              }}
            >
              management workspace
            </span>
            <div
              style={{
                margin: "6px 0 0",
                fontSize: 22,
                fontWeight: 600,
              }}
            >
              前端壳层阶段
            </div>
          </div>
          <div style={{ textAlign: "right" }}>
            <span
              style={{
                display: "block",
                color: "#162033",
                fontWeight: 600,
              }}
            >
              数据日期 2026-04-09
            </span>
            <span
              style={{
                color: "#5c6b82",
              }}
            >
              health / result_meta 协议对接预留
            </span>
          </div>
        </header>

        <main
          style={{
            padding: 28,
            border: "1px solid #d7dfea",
            borderRadius: 28,
            boxShadow: "0 18px 40px rgba(19, 37, 70, 0.08)",
            background: "#fbfcfe",
          }}
        >
          <Outlet />
        </main>
      </div>
    </div>
  );
}
