import {
  AlertOutlined,
  ApartmentOutlined,
  AppstoreOutlined,
  BankOutlined,
  BarChartOutlined,
  FileTextOutlined,
  FundOutlined,
  SettingOutlined,
  TeamOutlined,
  TrophyOutlined,
} from "@ant-design/icons";
import type { ReactNode } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";

import {
  primaryWorkbenchNavigation,
  secondaryWorkbenchNavigation,
  workbenchNavigation,
} from "../mocks/navigation";
import { resolveDataSourceMode } from "../api/client";

const iconMap: Record<string, ReactNode> = {
  dashboard: <AppstoreOutlined />,
  analysis: <BarChartOutlined />,
  risk: <AlertOutlined />,
  team: <TeamOutlined />,
  kpi: <TrophyOutlined />,
  decision: <ApartmentOutlined />,
  bond: <BankOutlined />,
  settings: <SettingOutlined />,
  market: <FundOutlined />,
  reports: <FileTextOutlined />,
  agent: <ApartmentOutlined />,
};

function readinessBadgeStyle(kind: "live" | "placeholder" | "gated") {
  if (kind === "live") {
    return {
      background: "#e8f6ee",
      color: "#2f8f63",
      border: "1px solid #c8e8d5",
    } as const;
  }

  if (kind === "placeholder") {
    return {
      background: "#f6f0ff",
      color: "#6d3bb3",
      border: "1px solid #e4d6fb",
    } as const;
  }

  return {
    background: "#fff4e8",
    color: "#b35a16",
    border: "1px solid #f1d3b5",
  } as const;
}

function pathMatchesSection(sectionPath: string, pathname: string) {
  if (sectionPath === "/") {
    return pathname === "/" || pathname === "/dashboard";
  }
  return sectionPath === pathname;
}

export function WorkbenchShell() {
  const location = useLocation();
  const currentSection =
    workbenchNavigation.find((item) => pathMatchesSection(item.path, location.pathname)) ??
    workbenchNavigation[0];
  const isMockDataSource = resolveDataSourceMode(import.meta.env.VITE_DATA_SOURCE) === "mock";

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "grid",
        gridTemplateColumns: "300px minmax(0, 1fr)",
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
              Phase 1 workbench shell
            </span>
          </div>
        </div>

        <div
          style={{
            padding: 16,
            borderBottom: "1px solid #e3e9f2",
            background: "#f7f9fc",
            display: "grid",
            gap: 8,
          }}
        >
          <span
            style={{
              fontSize: 11,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              color: "#8090a8",
            }}
          >
            Current Scope
          </span>
          <div style={{ color: "#162033", fontSize: 13, lineHeight: 1.6 }}>
            当前主导航只突出已接真实读链路的模块。其余页面保留入口，但明确标注为占位或未就绪。
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
          {primaryWorkbenchNavigation.map((item) => {
            const active = pathMatchesSection(item.path, location.pathname);

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
                  border: active ? "1px solid #cddcff" : "1px solid transparent",
                  transition: "background-color 160ms ease, color 160ms ease",
                }}
              >
                <span style={{ fontSize: 16 }}>{iconMap[item.icon]}</span>
                <span style={{ flex: 1 }}>{item.label}</span>
                <span
                  style={{
                    ...readinessBadgeStyle(item.readiness),
                    borderRadius: 999,
                    padding: "2px 8px",
                    fontSize: 11,
                    fontWeight: 600,
                  }}
                >
                  {item.readinessLabel}
                </span>
              </NavLink>
            );
          })}
        </nav>

        <div
          style={{
            padding: "0 16px 16px",
            display: "grid",
            gap: 10,
          }}
        >
          <div
            style={{
              paddingTop: 8,
              borderTop: "1px solid #e3e9f2",
              fontSize: 11,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              color: "#8090a8",
            }}
          >
            Reserved Modules
          </div>
          <div style={{ display: "grid", gap: 8 }}>
            {secondaryWorkbenchNavigation.map((item) => {
              const active = pathMatchesSection(item.path, location.pathname);

              return (
                <NavLink
                  key={item.key}
                  to={item.path}
                  style={{
                    display: "grid",
                    gap: 6,
                    padding: "12px 14px",
                    borderRadius: 16,
                    background: active ? "#f4f7fb" : "#ffffff",
                    border: active ? "1px solid #d7dfea" : "1px solid #e8edf5",
                    color: "#485970",
                    textDecoration: "none",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 10,
                    }}
                  >
                    <span style={{ fontSize: 16 }}>{iconMap[item.icon]}</span>
                    <span style={{ flex: 1, fontWeight: 600 }}>{item.label}</span>
                    <span
                      style={{
                        ...readinessBadgeStyle(item.readiness),
                        borderRadius: 999,
                        padding: "2px 8px",
                        fontSize: 11,
                        fontWeight: 600,
                      }}
                    >
                      {item.readinessLabel}
                    </span>
                  </div>
                  <div style={{ fontSize: 12, lineHeight: 1.5, color: "#708197" }}>
                    {item.readinessNote}
                  </div>
                </NavLink>
              );
            })}
          </div>
        </div>
      </aside>

      <div
        style={{
          display: "grid",
          gridTemplateRows: "96px minmax(0, 1fr)",
          gap: 18,
        }}
      >
        <header
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "0 24px",
            minHeight: 96,
            border: "1px solid #d7dfea",
            borderRadius: 28,
            boxShadow: "0 18px 40px rgba(19, 37, 70, 0.08)",
            background: "#fbfcfe",
            gap: 16,
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
              Phase 1 Status
            </span>
            <div
              style={{
                margin: "6px 0 0",
                fontSize: 22,
                fontWeight: 600,
                color: "#162033",
              }}
            >
              当前只突出可验证的真实读链路
            </div>
          </div>
          <div
            style={{
              display: "grid",
              justifyItems: "end",
              gap: 8,
            }}
          >
            <span
              style={{
                ...readinessBadgeStyle(currentSection.readiness),
                borderRadius: 999,
                padding: "6px 12px",
                fontSize: 12,
                fontWeight: 600,
              }}
            >
              {currentSection.label} · {currentSection.readinessLabel}
            </span>
            <span
              style={{
                maxWidth: 460,
                color: "#5c6b82",
                fontSize: 13,
                lineHeight: 1.6,
                textAlign: "right",
              }}
            >
              {currentSection.readinessNote}
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
            display: "grid",
            gap: 18,
          }}
        >
          {currentSection.readiness !== "live" ? (
            <section
              data-testid="workbench-readiness-banner"
              style={{
                borderRadius: 18,
                border: "1px solid #e4ebf5",
                background: currentSection.readiness === "placeholder" ? "#faf7ff" : "#fff8f1",
                color: "#31425b",
                padding: 18,
                display: "grid",
                gap: 8,
              }}
            >
              <div style={{ fontWeight: 700 }}>
                {currentSection.readiness === "placeholder"
                  ? "当前页面仍是占位壳层"
                  : "当前页面尚未物化真实数据链路"}
              </div>
              <div style={{ fontSize: 14, lineHeight: 1.6 }}>
                {currentSection.readinessNote}
              </div>
              <div style={{ fontSize: 13, color: "#708197" }}>
                若需要先看可跑出数据的模块，请优先使用主导航中的 Live 页面。
              </div>
            </section>
          ) : null}

          <Outlet />
        </main>
      </div>

      {isMockDataSource ? (
        <div
          data-testid="workbench-mock-mode-badge"
          style={{
            position: "fixed",
            right: 16,
            bottom: 16,
            zIndex: 1000,
            padding: "6px 12px",
            borderRadius: 999,
            background: "#162033",
            color: "#fbfcfe",
            fontSize: 12,
            fontWeight: 600,
            boxShadow: "0 8px 24px rgba(19, 37, 70, 0.2)",
            pointerEvents: "none",
          }}
        >
          Mock Mode
        </div>
      ) : null}
    </div>
  );
}
