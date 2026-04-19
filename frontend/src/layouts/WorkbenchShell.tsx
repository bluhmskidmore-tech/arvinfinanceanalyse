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
  resolveWorkbenchPathAlias,
  secondaryWorkbenchNavigation,
  type WorkbenchSection,
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
      background: "#f2edf8",
      color: "#654594",
      border: "1px solid #ddd2ee",
    } as const;
  }

  return {
    background: shellTokens.colorBgWarningSoft,
    color: shellTokens.colorWarning,
    border: `1px solid ${shellTokens.colorBorderWarning}`,
  } as const;
}

function groupButtonStyle(active: boolean) {
  return {
    display: "grid",
    gap: 10,
    padding: "14px 16px",
    borderRadius: 18,
    background: active ? shellTokens.colorAccentSoft : "rgba(255,255,255,0.45)",
    color: active ? shellTokens.colorAccent : shellTokens.colorTextPrimary,
    border: active
      ? `1px solid ${shellTokens.colorBorderStrong}`
      : `1px solid ${shellTokens.colorBorderSoft}`,
    boxShadow: active ? "0 14px 26px rgba(22, 35, 46, 0.08)" : "none",
    transition:
      "background-color 160ms ease, color 160ms ease, border-color 160ms ease, box-shadow 160ms ease",
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

const sidePanelStyle = {
  display: "grid",
  gap: 12,
  padding: 16,
  borderRadius: 22,
  border: `1px solid ${shellTokens.colorBorderSoft}`,
  background: "rgba(255,255,255,0.55)",
  boxShadow: "inset 0 1px 0 rgba(255,255,255,0.7)",
} as const;

type PortfolioStage = {
  title: string;
  description: string;
  sectionKeys: string[];
};

const portfolioFlow = [
  {
    key: "balance-analysis",
    title: "先看资产负债",
    detail: "用正式余额与 basis 分解确认今天的组合状态和错配位置。",
  },
  {
    key: "ledger-pnl",
    title: "再看正式损益",
    detail: "优先判断科目口径结果、账户聚合异动和是否需要继续解释。",
  },
  {
    key: "positions",
    title: "然后定位仓位",
    detail: "需要落到组合、券种或客户时，直接进入持仓透视继续下钻。",
  },
  {
    key: "pnl-attribution",
    title: "最后做原因解释",
    detail: "把规模、利率和市场相关性拆开，沉淀为可以执行的动作。",
  },
] as const;

const portfolioStages: PortfolioStage[] = [
  {
    title: "状态判断",
    description: "先确定规模、久期和正式结果，不把 analytical 估算混成首结论。",
    sectionKeys: ["balance-analysis", "bond-dashboard", "ledger-pnl"],
  },
  {
    title: "仓位与结构",
    description: "需要解释变化时，再看持仓、负债结构和 ADB 口径的形态变化。",
    sectionKeys: ["positions", "liability-analytics", "average-balance"],
  },
  {
    title: "原因解释",
    description: "最后才进入债券分析、桥接和归因，把现象拆成可验证的来源。",
    sectionKeys: ["bond-analysis", "pnl-bridge", "pnl-attribution"],
  },
];

function findSectionByKey(sections: WorkbenchSection[], key: string) {
  return sections.find((section) => section.key === key);
}

export function WorkbenchShell() {
  const location = useLocation();
  const pathnameResolved = resolveWorkbenchPathAlias(location.pathname);
  const currentSection = findWorkbenchSectionByPath(location.pathname, workbenchNavigation);
  const currentGroup =
    primaryWorkbenchNavigationGroups.find(
      (group) => group.key === resolveWorkbenchGroupKey(currentSection),
    ) ?? primaryWorkbenchNavigationGroups[0];
  const currentGroupSections = currentGroup.sections;
  const dataSourceRaw = import.meta.env.VITE_DATA_SOURCE;
  const isMockDataSource =
    typeof dataSourceRaw !== "string" || dataSourceRaw.trim().toLowerCase() !== "real";
  const isPortfolioGroup = currentGroup.key === "portfolio";
  const currentGroupSectionCount = currentGroupSections.length;
  const portfolioLeadSections = portfolioFlow
    .map((item) => ({
      ...item,
      section: findSectionByKey(currentGroupSections, item.key),
    }))
    .filter(
      (
        item,
      ): item is (typeof portfolioFlow)[number] & {
        section: WorkbenchSection;
      } => Boolean(item.section),
    );
  const portfolioBoard = portfolioStages
    .map((stage) => ({
      ...stage,
      sections: stage.sectionKeys
        .map((sectionKey) => findSectionByKey(currentGroupSections, sectionKey))
        .filter((section): section is WorkbenchSection => Boolean(section)),
    }))
    .filter((stage) => stage.sections.length > 0);

  return (
    <div
      className="workbench-shell-grid"
      style={{
        minHeight: "100vh",
        padding: "24px clamp(18px, 2vw, 30px)",
        background: shellTokens.colorBgApp,
      }}
    >
      <aside
        className="workbench-shell-aside"
        style={{
          display: "grid",
          alignContent: "start",
          gap: 18,
          padding: 18,
          border: `1px solid ${shellTokens.colorBorder}`,
          borderRadius: 32,
          boxShadow: shellTokens.shadowPanel,
          background: `linear-gradient(180deg, ${shellTokens.colorBgSurface} 0%, ${shellTokens.colorBgCanvas} 100%)`,
          backdropFilter: "blur(16px)",
        }}
      >
        <div style={sidePanelStyle}>
          <div
            style={{
              display: "flex",
              alignItems: "flex-start",
              justifyContent: "space-between",
              gap: 12,
            }}
          >
            <div
              style={{
                display: "grid",
                placeItems: "center",
                width: 40,
                height: 40,
                borderRadius: 14,
                background: shellTokens.colorTextPrimary,
                color: shellTokens.colorBgCanvas,
                fontWeight: 700,
                boxShadow: "0 12px 24px rgba(22, 35, 46, 0.18)",
              }}
            >
              M
            </div>
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                padding: "6px 10px",
                borderRadius: 999,
                background: isMockDataSource
                  ? shellTokens.colorBgWarningSoft
                  : shellTokens.colorAccentSoft,
                color: isMockDataSource ? shellTokens.colorWarning : shellTokens.colorAccent,
                fontSize: 11,
                fontWeight: 700,
                letterSpacing: "0.04em",
                textTransform: "uppercase",
              }}
            >
              {isMockDataSource ? "Mock mode" : "Real API"}
            </span>
          </div>
          <div style={{ display: "grid", gap: 4 }}>
            <span
              style={{
                display: "block",
                color: shellTokens.colorTextPrimary,
                fontWeight: 700,
                fontSize: 20,
                letterSpacing: "-0.03em",
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
            ...sidePanelStyle,
            gap: 8,
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
            const active = pathMatchesWorkbenchSection(item.path, pathnameResolved);

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

      <div className="workbench-main-column">
        <header
          style={{
            display: "flex",
            flexWrap: isPortfolioGroup ? "wrap" : "nowrap",
            alignItems: isPortfolioGroup ? "stretch" : "flex-start",
            justifyContent: "space-between",
            gap: 18,
            padding: "22px 26px",
            border: `1px solid ${shellTokens.colorBorder}`,
            borderRadius: 30,
            boxShadow: shellTokens.shadowPanel,
            background: `linear-gradient(145deg, ${shellTokens.colorBgCanvas} 0%, ${shellTokens.colorBgSurface} 88%)`,
          }}
        >
          {isPortfolioGroup ? (
            <>
              <section
                data-testid="portfolio-workbench-lead"
                style={{
                  flex: "1 1 0",
                  display: "grid",
                  gap: 18,
                  minWidth: 0,
                }}
              >
                <div style={{ display: "grid", gap: 10 }}>
                  <span
                    style={{
                      color: shellTokens.colorTextMuted,
                      fontSize: 12,
                      textTransform: "uppercase",
                      letterSpacing: "0.08em",
                    }}
                  >
                    Portfolio Workbench
                  </span>
                  <div
                    style={{
                      fontSize: "clamp(26px, 3vw, 34px)",
                      lineHeight: 1.15,
                      fontWeight: 700,
                      letterSpacing: "-0.04em",
                      color: shellTokens.colorTextPrimary,
                      maxWidth: 700,
                    }}
                  >
                    组合状态先看错配，再看损益，最后定位仓位与归因
                  </div>
                  <div
                    style={{
                      maxWidth: 760,
                      color: shellTokens.colorTextSecondary,
                      fontSize: 14,
                      lineHeight: 1.8,
                    }}
                  >
                    当前工作台聚合 {currentGroup.label} 的核心 live 页面。首屏不再平铺全部入口，而是先用正式链路做判断，再进入结构、仓位和归因页面解释原因，避免把 placeholder 或 analytical 结果误读成正式结论。
                  </div>
                </div>

                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
                    gap: 10,
                  }}
                >
                  {[
                    {
                      label: "可访问页面",
                      value: `${currentGroupSectionCount}`,
                      detail: "当前分组内 live route",
                    },
                    {
                      label: "默认入口",
                      value: "资产负债分析",
                      detail: "优先用正式余额判断状态",
                    },
                    {
                      label: "阅读原则",
                      value: "先正式后解释",
                      detail: "占位模块不混入首屏判断",
                    },
                  ].map((item) => (
                    <div
                      key={item.label}
                      style={{
                        display: "grid",
                        gap: 4,
                        padding: "14px 16px",
                        borderRadius: 20,
                        border: `1px solid ${shellTokens.colorBorderSoft}`,
                        background: "rgba(255,255,255,0.72)",
                      }}
                    >
                      <span style={{ color: shellTokens.colorTextMuted, fontSize: 12 }}>
                        {item.label}
                      </span>
                      <strong
                        style={{
                          color: shellTokens.colorTextPrimary,
                          fontSize: item.value.length > 8 ? 16 : 24,
                          lineHeight: 1.2,
                        }}
                      >
                        {item.value}
                      </strong>
                      <span style={{ color: shellTokens.colorTextSecondary, fontSize: 12 }}>
                        {item.detail}
                      </span>
                    </div>
                  ))}
                </div>
              </section>

              <aside
                data-testid="portfolio-workbench-flow"
                style={{
                  flex: "0 0 min(360px, 100%)",
                  display: "grid",
                  gap: 10,
                  padding: 18,
                  borderRadius: 24,
                  border: `1px solid ${shellTokens.colorBorderSoft}`,
                  background:
                    "linear-gradient(180deg, rgba(225, 235, 242, 0.72) 0%, rgba(255,255,255,0.82) 100%)",
                  boxShadow: "inset 0 1px 0 rgba(255,255,255,0.78)",
                }}
              >
                <div style={{ display: "grid", gap: 6 }}>
                  <span
                    style={{
                      color: shellTokens.colorTextMuted,
                      fontSize: 12,
                      textTransform: "uppercase",
                      letterSpacing: "0.08em",
                    }}
                  >
                    Suggested Flow
                  </span>
                  <div
                    style={{
                      fontSize: 18,
                      fontWeight: 700,
                      color: shellTokens.colorTextPrimary,
                    }}
                  >
                    先用正式结果做结论，再下钻解释原因
                  </div>
                </div>

                <div style={{ display: "grid", gap: 10 }}>
                  {portfolioLeadSections.map((item, index) => {
                    const active = pathMatchesWorkbenchSection(item.section.path, pathnameResolved);

                    return (
                      <NavLink
                        key={item.section.key}
                        to={item.section.path}
                        style={{
                          display: "grid",
                          gap: 6,
                          padding: "14px 16px",
                          borderRadius: 18,
                          background: active ? shellTokens.colorAccentSoft : "rgba(255,255,255,0.76)",
                          border: active
                            ? `1px solid ${shellTokens.colorBorderStrong}`
                            : `1px solid ${shellTokens.colorBorderSoft}`,
                          color: shellTokens.colorTextPrimary,
                        }}
                      >
                        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                          <span
                            style={{
                              display: "grid",
                              placeItems: "center",
                              width: 28,
                              height: 28,
                              borderRadius: 999,
                              background: active ? shellTokens.colorAccent : shellTokens.colorBgMuted,
                              color: active ? "#ffffff" : shellTokens.colorTextSecondary,
                              fontSize: 12,
                              fontWeight: 700,
                            }}
                          >
                            {index + 1}
                          </span>
                          <span style={{ flex: 1, fontWeight: 700 }}>{item.title}</span>
                          <span
                            style={{
                              ...readinessBadgeStyle(item.section.readiness),
                              borderRadius: 999,
                              padding: "2px 8px",
                              fontSize: 11,
                              fontWeight: 700,
                            }}
                          >
                            {item.section.readinessLabel}
                          </span>
                        </div>
                        <div style={{ color: shellTokens.colorTextSecondary, fontSize: 13, lineHeight: 1.6 }}>
                          {item.detail}
                        </div>
                        <div style={{ color: shellTokens.colorTextMuted, fontSize: 12 }}>
                          {item.section.label} · {item.section.readinessNote}
                        </div>
                      </NavLink>
                    );
                  })}
                </div>
              </aside>
            </>
          ) : (
            <>
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

              <div
                style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 10 }}
              >
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
            </>
          )}
        </header>

        <main
          style={{
            padding: 24,
            border: `1px solid ${shellTokens.colorBorder}`,
            borderRadius: 30,
            boxShadow: shellTokens.shadowPanel,
            background: `linear-gradient(180deg, ${shellTokens.colorBgSurface} 0%, ${shellTokens.colorBgCanvas} 100%)`,
            display: "grid",
            alignContent: "start",
            gap: 20,
          }}
        >
          {isPortfolioGroup ? (
            <section
              data-testid="portfolio-workbench-board"
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
                gap: 14,
                paddingBottom: 18,
                borderBottom: `1px solid ${shellTokens.colorBorderSoft}`,
              }}
            >
              {portfolioBoard.map((stage) => (
                <article
                  key={stage.title}
                  style={{
                    display: "grid",
                    gap: 14,
                    padding: "18px 18px 16px",
                    borderRadius: 24,
                    border: `1px solid ${shellTokens.colorBorderSoft}`,
                    background: "linear-gradient(180deg, rgba(255,255,255,0.88) 0%, rgba(245,247,244,0.92) 100%)",
                  }}
                >
                  <div style={{ display: "grid", gap: 6 }}>
                    <span
                      style={{
                        color: shellTokens.colorTextMuted,
                        fontSize: 12,
                        textTransform: "uppercase",
                        letterSpacing: "0.08em",
                      }}
                    >
                      {stage.title}
                    </span>
                    <div
                      style={{
                        color: shellTokens.colorTextSecondary,
                        fontSize: 13,
                        lineHeight: 1.7,
                      }}
                    >
                      {stage.description}
                    </div>
                  </div>

                  <div style={{ display: "grid", gap: 10 }}>
                    {stage.sections.map((section) => {
                      const active = pathMatchesWorkbenchSection(section.path, pathnameResolved);

                      return (
                        <NavLink
                          key={section.key}
                          to={section.path}
                          style={{
                            display: "grid",
                            gap: 4,
                            paddingBottom: 10,
                            borderBottom: `1px solid ${shellTokens.colorBorderSoft}`,
                            color: shellTokens.colorTextPrimary,
                          }}
                        >
                          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                            <span style={{ fontSize: 15 }}>{iconMap[section.icon]}</span>
                            <span style={{ flex: 1, fontWeight: 700 }}>{section.label}</span>
                            <span
                              style={{
                                ...readinessBadgeStyle(section.readiness),
                                borderRadius: 999,
                                padding: "2px 8px",
                                fontSize: 11,
                                fontWeight: 700,
                              }}
                            >
                              {active ? "当前页" : section.readinessLabel}
                            </span>
                          </div>
                          <div style={{ color: shellTokens.colorTextSecondary, fontSize: 13, lineHeight: 1.6 }}>
                            {section.description}
                          </div>
                        </NavLink>
                      );
                    })}
                  </div>
                </article>
              ))}
            </section>
          ) : null}

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
                {isPortfolioGroup ? "All Live Pages" : "In This Workspace"}
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
                const active = pathMatchesWorkbenchSection(section.path, pathnameResolved);

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
