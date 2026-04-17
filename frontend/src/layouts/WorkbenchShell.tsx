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
  findWorkbenchSectionByPath,
  pathMatchesWorkbenchSection,
  primaryWorkbenchNavigationGroups,
  resolveWorkbenchGroupKey,
  secondaryWorkbenchNavigation,
  workbenchNavigation,
} from "../mocks/navigation";
import { shellTokens } from "../theme/tokens";

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
      background: shellTokens.colorBgSuccessSoft,
      color: shellTokens.colorSuccess,
      border: `1px solid ${shellTokens.colorBorderSoft}`,
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

function groupButtonStyle(active: boolean) {
  return {
    display: "grid",
    gap: 8,
    padding: "14px 16px",
    borderRadius: 18,
    background: active ? shellTokens.colorAccentSoft : "#ffffff",
    color: active ? shellTokens.colorAccent : shellTokens.colorTextPrimary,
    border: active
      ? `1px solid ${shellTokens.colorBorderStrong}`
      : `1px solid ${shellTokens.colorBorderSoft}`,
    boxShadow: active ? shellTokens.shadowPanel : "none",
    transition: "background-color 160ms ease, color 160ms ease, border-color 160ms ease",
  } as const;
}

function groupSectionPillStyle(active: boolean) {
  return {
    display: "inline-flex",
    alignItems: "center",
    gap: 8,
    padding: "10px 14px",
    borderRadius: 999,
    background: active ? shellTokens.colorAccent : "#ffffff",
    color: active ? "#ffffff" : shellTokens.colorTextSecondary,
    border: active
      ? `1px solid ${shellTokens.colorAccent}`
      : `1px solid ${shellTokens.colorBorderSoft}`,
    fontSize: 13,
    fontWeight: 600,
    transition: "background-color 160ms ease, color 160ms ease, border-color 160ms ease",
  } as const;
}

export function WorkbenchShell() {
  const location = useLocation();
  const currentSection = findWorkbenchSectionByPath(location.pathname, workbenchNavigation);
  const currentGroup =
    primaryWorkbenchNavigationGroups.find(
      (group) => group.key === resolveWorkbenchGroupKey(currentSection),
    ) ?? primaryWorkbenchNavigationGroups[0];
  const currentGroupSections = currentGroup.sections;
  const dataSourceRaw = import.meta.env.VITE_DATA_SOURCE;
  const isMockDataSource =
    typeof dataSourceRaw !== "string" || dataSourceRaw.trim().toLowerCase() !== "real";

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "grid",
        gridTemplateColumns: "280px minmax(0, 1fr)",
        gap: 20,
        padding: 20,
        background: shellTokens.colorBgApp,
      }}
    >
      <aside
        style={{
          display: "grid",
          alignContent: "start",
          gap: 18,
          padding: 18,
          border: `1px solid ${shellTokens.colorBorder}`,
          borderRadius: 28,
          boxShadow: shellTokens.shadowPanel,
          background: shellTokens.colorBgSurface,
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 12,
            paddingBottom: 18,
            borderBottom: `1px solid ${shellTokens.colorBorderSoft}`,
          }}
        >
          <div
            style={{
              display: "grid",
              placeItems: "center",
              width: 34,
              height: 34,
              borderRadius: 12,
              background: shellTokens.colorTextPrimary,
              color: shellTokens.colorBgSurface,
              fontWeight: 700,
            }}
          >
            M
          </div>
          <div>
            <span
              style={{
                display: "block",
                color: shellTokens.colorTextPrimary,
                fontWeight: 700,
                fontSize: 18,
                letterSpacing: "-0.02em",
              }}
            >
              MOSS
            </span>
            <span style={{ color: shellTokens.colorTextMuted, fontSize: 12 }}>
              Phase 1 workbench shell
            </span>
          </div>
        </div>

        <section
          style={{
            display: "grid",
            gap: 8,
            paddingBottom: 18,
            borderBottom: `1px solid ${shellTokens.colorBorderSoft}`,
          }}
        >
          <span
            style={{
              fontSize: 11,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              color: shellTokens.colorTextMuted,
            }}
          >
            Current Scope
          </span>
          <div
            style={{
              color: shellTokens.colorTextPrimary,
              fontSize: 13,
              lineHeight: 1.7,
            }}
          >
            当前左侧只保留工作台分组。具体分析页收进当前分组的子导航，减少首页扫描负担。
          </div>
        </section>

        <nav
          aria-label="Primary workspaces"
          data-testid="workbench-group-nav"
          style={{ display: "grid", gap: 10 }}
        >
          {primaryWorkbenchNavigationGroups.map((group) => {
            const active = group.key === currentGroup.key;

            return (
              <NavLink key={group.key} to={group.defaultPath} style={groupButtonStyle(active)}>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 10,
                  }}
                >
                  <span style={{ fontSize: 16 }}>{iconMap[group.icon]}</span>
                  <span style={{ flex: 1, fontWeight: 700 }}>{group.label}</span>
                  <span
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      justifyContent: "center",
                      minWidth: 28,
                      height: 28,
                      paddingInline: 8,
                      borderRadius: 999,
                      background: active ? "rgba(255,255,255,0.2)" : shellTokens.colorBgMuted,
                      color: active ? "#ffffff" : shellTokens.colorTextSecondary,
                      fontSize: 12,
                      fontWeight: 700,
                    }}
                  >
                    {group.sections.length}
                  </span>
                </div>
                <div
                  style={{
                    color: active ? "#dbe6ff" : shellTokens.colorTextMuted,
                    fontSize: 12,
                    lineHeight: 1.6,
                  }}
                >
                  {group.description}
                </div>
              </NavLink>
            );
          })}
        </nav>

        <section
          style={{
            display: "grid",
            gap: 10,
            paddingTop: 4,
            borderTop: `1px solid ${shellTokens.colorBorderSoft}`,
          }}
        >
          <div
            style={{
              fontSize: 11,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              color: shellTokens.colorTextMuted,
            }}
          >
            Reserved Modules
          </div>
          {secondaryWorkbenchNavigation.map((item) => {
            const active = pathMatchesWorkbenchSection(item.path, location.pathname);

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
                  border: active
                    ? `1px solid ${shellTokens.colorBorder}`
                    : `1px solid ${shellTokens.colorBorderSoft}`,
                  color: shellTokens.colorTextPrimary,
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <span style={{ fontSize: 16 }}>{iconMap[item.icon]}</span>
                  <span style={{ flex: 1, fontWeight: 700 }}>{item.label}</span>
                  <span
                    style={{
                      ...readinessBadgeStyle(item.readiness),
                      borderRadius: 999,
                      padding: "2px 8px",
                      fontSize: 11,
                      fontWeight: 700,
                    }}
                  >
                    {item.readinessLabel}
                  </span>
                </div>
                <div style={{ color: shellTokens.colorTextMuted, fontSize: 12, lineHeight: 1.6 }}>
                  {item.readinessNote}
                </div>
              </NavLink>
            );
          })}
        </section>
      </aside>

      <div
        style={{
          display: "grid",
          gridTemplateRows: "auto minmax(0, 1fr)",
          gap: 20,
        }}
      >
        <header
          style={{
            display: "flex",
            alignItems: "flex-start",
            justifyContent: "space-between",
            gap: 18,
            padding: "20px 24px",
            border: `1px solid ${shellTokens.colorBorder}`,
            borderRadius: 28,
            boxShadow: shellTokens.shadowPanel,
            background: shellTokens.colorBgSurface,
          }}
        >
          <div style={{ display: "grid", gap: 8 }}>
            <span
              style={{
                color: shellTokens.colorTextMuted,
                fontSize: 12,
                textTransform: "uppercase",
                letterSpacing: "0.08em",
              }}
            >
              Phase 1 Status
            </span>
            <div
              style={{
                fontSize: 22,
                fontWeight: 700,
                color: shellTokens.colorTextPrimary,
              }}
            >
              当前只突出可验证的真实读链路
            </div>
            <div style={{ color: shellTokens.colorTextSecondary, fontSize: 14, lineHeight: 1.7 }}>
              当前工作台：{currentGroup.label}。页面切换收进组内导航，避免在壳层堆满入口。
            </div>
          </div>

          <div style={{ display: "grid", justifyItems: "end", gap: 8 }}>
            <span
              style={{
                ...readinessBadgeStyle(currentSection.readiness),
                borderRadius: 999,
                padding: "6px 12px",
                fontSize: 12,
                fontWeight: 700,
              }}
            >
              {currentSection.label} · {currentSection.readinessLabel}
            </span>
            <span
              style={{
                maxWidth: 420,
                color: shellTokens.colorTextSecondary,
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
            padding: 24,
            border: `1px solid ${shellTokens.colorBorder}`,
            borderRadius: 28,
            boxShadow: shellTokens.shadowPanel,
            background: shellTokens.colorBgSurface,
            display: "grid",
            alignContent: "start",
            gap: 18,
          }}
        >
          <section
            data-testid="workbench-section-subnav"
            style={{
              display: "grid",
              gap: 12,
              paddingBottom: 18,
              borderBottom: `1px solid ${shellTokens.colorBorderSoft}`,
            }}
          >
            <div style={{ display: "grid", gap: 4 }}>
              <span
                style={{
                  color: shellTokens.colorTextMuted,
                  fontSize: 11,
                  fontWeight: 700,
                  letterSpacing: "0.08em",
                  textTransform: "uppercase",
                }}
              >
                In This Workspace
              </span>
              <div
                style={{
                  color: shellTokens.colorTextPrimary,
                  fontSize: 18,
                  fontWeight: 700,
                }}
              >
                {currentGroup.label}
              </div>
            </div>

            <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
              {currentGroupSections.map((section) => {
                const active = pathMatchesWorkbenchSection(section.path, location.pathname);

                return (
                  <NavLink
                    key={section.key}
                    to={section.path}
                    style={groupSectionPillStyle(active)}
                  >
                    <span style={{ fontSize: 14 }}>{iconMap[section.icon]}</span>
                    <span>{section.label}</span>
                  </NavLink>
                );
              })}
            </div>
          </section>

          {currentSection.readiness !== "live" ? (
            <section
              data-testid="workbench-readiness-banner"
              style={{
                borderRadius: 18,
                border: `1px solid ${shellTokens.colorBorderSoft}`,
                background:
                  currentSection.readiness === "placeholder" ? "#faf7ff" : "#fff8f1",
                color: shellTokens.colorTextPrimary,
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
              <div style={{ fontSize: 14, lineHeight: 1.6 }}>{currentSection.readinessNote}</div>
              <div style={{ fontSize: 13, color: shellTokens.colorTextMuted }}>
                如需先查看可验证的数据页面，请优先使用当前工作台中的 live 子页面。
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
            background: shellTokens.colorTextPrimary,
            color: shellTokens.colorBgSurface,
            fontSize: 12,
            fontWeight: 700,
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
