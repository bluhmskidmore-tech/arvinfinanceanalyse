import {
  AlertOutlined,
  ApartmentOutlined,
  AppstoreOutlined,
  BankOutlined,
  BarChartOutlined,
  FileTextOutlined,
  FundOutlined,
  QuestionCircleOutlined,
  SettingOutlined,
  TeamOutlined,
  TrophyOutlined,
  UserOutlined,
} from "@ant-design/icons";
import { useMemo, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { NavLink, Outlet, useLocation } from "react-router-dom";

import { useApiClient } from "../api/client";
import type { ChoiceMacroLatestPoint } from "../api/contracts";
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
import { formatChoiceMacroDelta, formatChoiceMacroValue } from "../utils/choiceMacroFormat";

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

function sectionBadgeStyle(section: Pick<WorkbenchSection, "readiness" | "governanceStatus">) {
  if (section.governanceStatus === "temporary-exception") {
    return {
      background: shellTokens.colorBgWarningSoft,
      color: shellTokens.colorWarning,
      border: `1px solid ${shellTokens.colorBorderWarning}`,
    } as const;
  }

  return readinessBadgeStyle(section.readiness);
}

function groupButtonStyle(active: boolean) {
  return {
    display: "flex",
    alignItems: "center",
    gap: 10,
    padding: "9px 10px",
    borderRadius: 12,
    background: active ? "rgba(221, 233, 241, 0.64)" : "transparent",
    color: active ? shellTokens.colorTextPrimary : shellTokens.colorTextSecondary,
    border: "1px solid transparent",
    boxShadow: active ? "inset 2px 0 0 #2c5a79" : "none",
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

function supportLinkStyle(active: boolean) {
  return {
    display: "flex",
    alignItems: "center",
    gap: 8,
    padding: "6px 8px",
    borderRadius: 10,
    background: active ? "rgba(233, 238, 235, 0.72)" : "transparent",
    color: active ? shellTokens.colorTextPrimary : shellTokens.colorTextMuted,
    border: "1px solid transparent",
    fontSize: 11,
    fontWeight: 600,
    transition: "background-color 160ms ease, color 160ms ease, border-color 160ms ease",
  } as const;
}

const shellSectionLabelStyle = {
  fontSize: 9,
  letterSpacing: "0.18em",
  textTransform: "uppercase",
  color: shellTokens.colorTextMuted,
  fontWeight: 700,
} as const;

type ShellTickerTone = "up" | "down";

type ShellTickerItem = {
  key: string;
  label: string;
  value: string;
  delta: string;
  tone: ShellTickerTone;
};

const fallbackShellTickerItems: ShellTickerItem[] = [
  { key: "cgb10y", label: "10Y CGB", value: "1.94%", delta: "+2bp", tone: "up" },
  { key: "dr007", label: "DR007", value: "1.82%", delta: "-6bp", tone: "down" },
  { key: "omo7d", label: "OMO 7D", value: "1.75%", delta: "+1bp", tone: "up" },
  { key: "usd-cny", label: "USD/CNY", value: "7.21", delta: "+0.02", tone: "up" },
] as const;

const shellTickerSeriesSpecs = [
  {
    key: "cgb10y",
    label: "10Y CGB",
    matchers: ["中债国债到期收益率:10年", "10年期国债到期收益率"],
  },
  {
    key: "policyBank10y",
    label: "Policy 10Y",
    matchers: ["中债政策性金融债到期收益率(国开行)10年"],
  },
  {
    key: "us10y",
    label: "US 10Y",
    matchers: ["美国10年期国债收益率", "美国:国债收益率:10年"],
  },
  {
    key: "cnUs10ySpread",
    label: "CN-US 10Y",
    matchers: ["中美国债利差(10Y)", "10Y中国国债-10Y美国国债"],
  },
  {
    key: "dr007",
    label: "DR007",
    matchers: ["DR007"],
  },
  {
    key: "omo7d",
    label: "OMO 7D",
    matchers: ["公开市场7天逆回购利率"],
  },
  {
    key: "usd-cny",
    label: "USD/CNY",
    matchers: ["即期汇率:美元兑人民币", "USD/CNY"],
  },
] as const;

type ShellTickerKey = (typeof shellTickerSeriesSpecs)[number]["key"];

const shellTickerDisplayKeys: ShellTickerKey[] = [
  "cgb10y",
  "policyBank10y",
  "us10y",
  "cnUs10ySpread",
  "dr007",
  "omo7d",
  "usd-cny",
];

const shellTickerSeriesIdsByKey: Record<ShellTickerKey, string[]> = {
  // Cross-asset / latest payload aliases for China 10Y sovereign.
  cgb10y: ["CA.CN_GOV_10Y", "E1000180", "EMM00166466"],
  // Policy-bank 10Y is currently anchored on the CDB lane.
  policyBank10y: ["EMM00166502"],
  // US 10Y can come from cross-asset or EDB-oriented identifiers.
  us10y: ["CA.US_GOV_10Y", "EMG00001310", "E1003238"],
  // CN-US spread can arrive directly as cross-asset headline or legacy spread id.
  cnUs10ySpread: ["CA.CN_US_SPREAD", "EM1"],
  // DR007 appears both as raw choice macro and catalog-aligned headline lanes.
  dr007: ["CA.DR007", "M002", "EMM00167613"],
  // Open-market 7D reverse repo currently only exposes one stable series id locally.
  omo7d: ["M001"],
  // USD/CNY can arrive from middle-rate or spot-oriented lanes.
  "usd-cny": ["CA.USDCNY", "EMM00058124"],
};

function formatShellTickerValue(point: ChoiceMacroLatestPoint) {
  return formatChoiceMacroValue(point, { spaceBeforeUnit: false });
}

function formatShellTickerDelta(point: ChoiceMacroLatestPoint) {
  return formatChoiceMacroDelta(point, { spaceBeforeUnit: false });
}

function buildShellTickerItems(
  series: ChoiceMacroLatestPoint[],
  keys: ShellTickerKey[] = shellTickerDisplayKeys,
): ShellTickerItem[] {
  const resolved: ShellTickerItem[] = [];

  for (const spec of shellTickerSeriesSpecs.filter((item) => keys.includes(item.key))) {
    const stableSeriesIds = shellTickerSeriesIdsByKey[spec.key] ?? [];
    const point =
      series.find((candidate) => stableSeriesIds.includes(candidate.series_id)) ??
      series.find((candidate) =>
        spec.matchers.some((matcher) => candidate.series_name.includes(matcher)),
      );
    if (!point) {
      continue;
    }

    resolved.push({
      key: spec.key,
      label: spec.label,
      value: formatShellTickerValue(point),
      delta: formatShellTickerDelta(point),
      tone: point.latest_change != null && point.latest_change < 0 ? "down" : "up",
    });
  }

  return resolved.length > 0 ? resolved : fallbackShellTickerItems;
}

const shellUtilityEntries = [
  {
    key: "reports",
    label: "\u62a5\u8868\u4e2d\u5fc3",
    to: "/reports",
    icon: <FileTextOutlined />,
  },
  {
    key: "platform",
    label: "\u4e2d\u53f0\u914d\u7f6e",
    to: "/platform-config",
    icon: <SettingOutlined />,
  },
  {
    key: "help",
    label: "\u5e2e\u52a9\u6587\u6863",
    to: "/",
    icon: <QuestionCircleOutlined />,
  },
] as const;

const _shellSupportEntries = [
  { key: "reports", label: "鎶ヨ〃涓績", to: "/reports", icon: <FileTextOutlined /> },
  { key: "platform", label: "涓彴閰嶇疆", to: "/platform-config", icon: <SettingOutlined /> },
  { key: "help", label: "甯姪鏂囨。", to: "/", icon: <QuestionCircleOutlined /> },
] as const;

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
  const client = useApiClient();
  const location = useLocation();
  const pathnameResolved = resolveWorkbenchPathAlias(location.pathname);
  const searchParams = new URLSearchParams(location.search);
  const currentSection = findWorkbenchSectionByPath(location.pathname, workbenchNavigation);
  const currentGroup =
    primaryWorkbenchNavigationGroups.find(
      (group) => group.key === resolveWorkbenchGroupKey(currentSection),
    ) ?? primaryWorkbenchNavigationGroups[0];
  const currentGroupSections = currentGroup.sections;
  const isPortfolioGroup = currentGroup.key === "portfolio";
  const isBondAnalysisMinimalShell = currentSection.key === "bond-analysis";
  const showWorkspaceHeroCard =
    !isBondAnalysisMinimalShell && (isPortfolioGroup || currentSection.key !== "dashboard");
  const currentGroupSectionCount = currentGroupSections.length;
  const explicitReportDate = searchParams.get("report_date")?.trim() ?? "";
  const bondAnalyticsDatesQuery = useQuery({
    queryKey: ["workbench-shell", "bond-analytics-dates", client.mode],
    queryFn: () => client.getBondAnalyticsDates(),
    enabled: isBondAnalysisMinimalShell && !explicitReportDate,
    retry: false,
    staleTime: 60_000,
  });
  const shellTickerQuery = useQuery({
    queryKey: ["workbench-shell", "choice-macro-latest", client.mode],
    queryFn: () => client.getChoiceMacroLatest(),
    retry: false,
    staleTime: 60_000,
  });
  const shellReportDate =
    explicitReportDate ||
    (isBondAnalysisMinimalShell
      ? bondAnalyticsDatesQuery.data?.result.report_dates[0] ?? "Latest available"
      : "Route default");
  const shellTickerItems = useMemo(
    () => buildShellTickerItems(shellTickerQuery.data?.result.series ?? []),
    [shellTickerQuery.data?.result.series],
  );
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
        padding: "18px clamp(16px, 1.8vw, 28px)",
        background: shellTokens.colorBgApp,
      }}
    >
      <aside
        className="workbench-shell-aside"
        style={{
          display: "grid",
          alignContent: "start",
          gap: 14,
          padding: isBondAnalysisMinimalShell ? "8px 12px 14px 0" : "10px 14px 16px 0",
          border: "none",
          borderRight: `1px solid ${shellTokens.colorBorderSoft}`,
          borderRadius: 0,
          boxShadow: "none",
          background: "transparent",
        }}
      >
        <div
          style={{
            display: "grid",
            gap: 8,
            padding: "6px 4px 14px 8px",
            borderBottom: `1px solid ${shellTokens.colorBorderSoft}`,
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 12,
            }}
          >
            <div
              style={{
                display: "grid",
                placeItems: "center",
                width: 40,
                height: 40,
                borderRadius: 12,
                background: shellTokens.colorTextPrimary,
                color: shellTokens.colorBgCanvas,
                fontWeight: 700,
                boxShadow: "0 10px 22px rgba(22, 35, 46, 0.14)",
              }}
            >
              M
            </div>
            <div style={{ display: "grid", gap: 0, minWidth: 0 }}>
              <span
                style={{
                  color: shellTokens.colorTextPrimary,
                  fontWeight: 700,
                  fontSize: 17,
                  letterSpacing: "-0.03em",
                }}
              >
                MOSS
              </span>
            </div>
          </div>
        </div>

        {/* {!isBondAnalysisMinimalShell ? (
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
        ) : null} */}

        {/* <nav
          aria-label="Primary workspaces"
          data-testid="workbench-group-nav"
          style={{ display: "grid", gap: isBondAnalysisMinimalShell ? 6 : 10 }}
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

        {isBondAnalysisMinimalShell ? (
          <section
            data-testid="workbench-sidebar-sections"
            style={{
              display: "grid",
              gap: 6,
              paddingTop: 6,
              borderTop: `1px solid ${shellTokens.colorBorderSoft}`,
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
              组合工作台
            </span>
            {currentGroupSections.map((section) => {
              const active = pathMatchesWorkbenchSection(section.path, pathnameResolved);

              return (
                <NavLink
                  key={section.key}
                  to={section.path}
                  style={sidebarSectionLinkStyle(active)}
                >
                  <span style={{ fontSize: 14 }}>{iconMap[section.icon]}</span>
                  <span style={{ flex: 1 }}>{section.label}</span>
                </NavLink>
              );
            })}
          </section>
        ) : (
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
                        ...sectionBadgeStyle(item),
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
        )} */}

        <section style={{ display: "grid", gap: 6 }}>
          <span style={shellSectionLabelStyle}>Workspaces</span>
          <nav
            aria-label="Primary workspaces"
            data-testid="workbench-group-nav"
            style={{ display: "grid", gap: 2 }}
          >
            {primaryWorkbenchNavigationGroups.map((group) => {
              const active = group.key === currentGroup.key;

              return (
                <NavLink
                  key={group.key}
                  to={group.defaultPath}
                  data-active={active ? "true" : "false"}
                  style={groupButtonStyle(active)}
                >
                  <span
                    style={{
                      display: "grid",
                      placeItems: "center",
                      width: 18,
                      height: 18,
                      borderRadius: 999,
                      border: `1px solid ${active ? shellTokens.colorAccent : shellTokens.colorBorderStrong}`,
                      color: active ? shellTokens.colorAccent : shellTokens.colorTextMuted,
                      fontSize: 10,
                      background: active ? "rgba(255,255,255,0.72)" : "transparent",
                    }}
                  >
                    {iconMap[group.icon]}
                  </span>
                  <span
                    style={{
                      flex: 1,
                      minWidth: 0,
                      fontWeight: active ? 700 : 600,
                      fontSize: 13,
                    }}
                  >
                    {group.label}
                  </span>
                  <span
                    style={{
                      color: active ? shellTokens.colorAccent : shellTokens.colorTextMuted,
                      fontSize: 10,
                      fontWeight: 700,
                      letterSpacing: "0.06em",
                    }}
                  >
                    {String(group.sections.length).padStart(2, "0")}
                  </span>
                </NavLink>
              );
            })}
          </nav>
        </section>

        {isBondAnalysisMinimalShell ? null : (
          <section
            style={{
              display: "grid",
              gap: 6,
              paddingTop: 8,
              borderTop: `1px solid ${shellTokens.colorBorderSoft}`,
            }}
          >
            <span style={shellSectionLabelStyle}>Reserved Modules</span>
            {secondaryWorkbenchNavigation.map((item) => {
              const active = pathMatchesWorkbenchSection(item.path, pathnameResolved);

              return (
                <NavLink
                  key={item.key}
                  to={item.path}
                  style={{
                    display: "grid",
                    gap: 2,
                    padding: "8px 10px",
                    borderRadius: 10,
                    background: active ? "rgba(255,255,255,0.64)" : "transparent",
                    color: shellTokens.colorTextSecondary,
                    border: "1px solid transparent",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span style={{ fontSize: 12 }}>{iconMap[item.icon]}</span>
                    <span style={{ flex: 1, fontSize: 12, fontWeight: 600 }}>{item.label}</span>
                    <span
                      style={{
                        ...sectionBadgeStyle(item),
                        borderRadius: 999,
                        padding: "1px 6px",
                        fontSize: 10,
                        fontWeight: 700,
                      }}
                    >
                      {item.readinessLabel}
                    </span>
                  </div>
                </NavLink>
              );
            })}
          </section>
        )}

        <section
          data-testid="workbench-support-nav"
          style={{
            display: "grid",
            gap: 4,
            paddingTop: 8,
            borderTop: `1px solid ${shellTokens.colorBorderSoft}`,
          }}
        >
          <span style={shellSectionLabelStyle}>Support</span>
          {shellUtilityEntries.map((item) => {
            const active = item.to !== "/" && pathnameResolved === item.to;

            return (
              <NavLink key={item.key} to={item.to} style={supportLinkStyle(active)}>
                <span style={{ fontSize: 11 }}>{item.icon}</span>
                <span style={{ flex: 1 }}>{item.label}</span>
              </NavLink>
            );
          })}
        </section>
      </aside>

      <div className="workbench-main-column">
        <header
          data-testid="workbench-terminal-bar"
          style={{
            display: "grid",
            gap: 8,
            padding: "0 0 10px",
            borderBottom: `1px solid ${shellTokens.colorBorderSoft}`,
            background: "transparent",
          }}
        >
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              alignItems: "flex-end",
              justifyContent: "space-between",
              gap: 16,
            }}
          >
            <section
              data-testid="workbench-page-context"
              style={{
                display: "flex",
                flexWrap: "wrap",
                alignItems: "baseline",
                gap: 8,
                minWidth: 0,
              }}
            >
              <div
                style={{
                  color: shellTokens.colorTextPrimary,
                  fontSize: "clamp(36px, 4.4vw, 52px)",
                  lineHeight: 0.96,
                  fontWeight: 700,
                  letterSpacing: "-0.07em",
                }}
              >
                {currentSection.label}
              </div>
              <span
                style={{
                  color: shellTokens.colorTextSecondary,
                  fontSize: 14,
                  fontWeight: 600,
                }}
              >
                {"\u62a5\u544a\u65e5"} {shellReportDate}
              </span>
            </section>

            <section
              data-testid="workbench-operator-zone"
              style={{
                display: "flex",
                flexWrap: "wrap",
                alignItems: "center",
                justifyContent: "flex-end",
                gap: 8,
                minWidth: 0,
              }}
            >
              <span
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 6,
                  padding: "6px 10px",
                  borderRadius: 999,
                  background: "rgba(221, 233, 241, 0.76)",
                  color: shellTokens.colorAccent,
                  fontSize: 11,
                  fontWeight: 700,
                }}
              >
                <UserOutlined />
                <span>{"\u7ba1\u7406\u89c6\u89d2"}</span>
              </span>
              {shellUtilityEntries
                .filter((item) => item.key !== "help")
                .map((item) => (
                  <NavLink
                    key={`terminal-${item.key}`}
                    to={item.to}
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 6,
                      padding: "6px 2px",
                      color: shellTokens.colorTextPrimary,
                      fontSize: 12,
                      fontWeight: 700,
                      borderBottom: `1px solid transparent`,
                    }}
                  >
                    <span style={{ fontSize: 11 }}>{item.icon}</span>
                    <span>{item.label}</span>
                  </NavLink>
                ))}
            </section>
          </div>

          <section
            data-testid="workbench-market-ticker"
            style={{
              display: "flex",
              flexWrap: "wrap",
              alignItems: "center",
              gap: 12,
              minWidth: 0,
            }}
          >
            <span
              style={{
                color: shellTokens.colorTextMuted,
                fontSize: 11,
                fontWeight: 700,
                letterSpacing: "0.12em",
                textTransform: "uppercase",
              }}
            >
              Shell Market Ticker
            </span>
            {shellTickerItems.map((item) => (
              <div
                key={item.key}
                style={{
                  display: "inline-flex",
                  alignItems: "baseline",
                  gap: 6,
                  minWidth: 0,
                }}
              >
                <span
                  style={{
                    color: shellTokens.colorTextMuted,
                    fontSize: 10,
                    fontWeight: 600,
                    letterSpacing: "0.02em",
                  }}
                >
                  {item.label}
                </span>
                <strong
                  style={{
                    color: shellTokens.colorTextPrimary,
                    fontSize: 16,
                    lineHeight: 1,
                    fontWeight: 700,
                    fontVariantNumeric: "tabular-nums",
                  }}
                >
                  {item.value}
                </strong>
                <span
                  style={{
                    color: item.tone === "down" ? shellTokens.colorSuccess : shellTokens.colorWarning,
                    fontSize: 10,
                    fontWeight: 700,
                  }}
                >
                  {item.delta}
                </span>
                <span
                  style={{
                    width: 1,
                    height: 10,
                    background: shellTokens.colorBorderSoft,
                  }}
                />
              </div>
            ))}
          </section>
        </header>
        {showWorkspaceHeroCard ? (
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
                                ...sectionBadgeStyle(item.section),
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
                      ...sectionBadgeStyle(currentSection),
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
        ) : null}

        <main
          style={{
            padding: isBondAnalysisMinimalShell ? 0 : 24,
            border: isBondAnalysisMinimalShell ? "none" : `1px solid ${shellTokens.colorBorder}`,
            borderRadius: isBondAnalysisMinimalShell ? 0 : 30,
            boxShadow: isBondAnalysisMinimalShell ? "none" : shellTokens.shadowPanel,
            background: isBondAnalysisMinimalShell
              ? "transparent"
              : `linear-gradient(180deg, ${shellTokens.colorBgSurface} 0%, ${shellTokens.colorBgCanvas} 100%)`,
            display: "grid",
            alignContent: "start",
            gap: 20,
          }}
        >
          {isPortfolioGroup && !isBondAnalysisMinimalShell ? (
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
                                ...sectionBadgeStyle(section),
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

          {!isBondAnalysisMinimalShell ? (
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
          ) : null}

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

          {currentSection.governanceStatus === "temporary-exception" ? (
            <section
              data-testid="workbench-governance-banner"
              style={{
                borderRadius: 18,
                border: `1px solid ${shellTokens.colorBorderWarning}`,
                background: shellTokens.colorBgWarningSoft,
                color: shellTokens.colorTextPrimary,
                padding: 18,
                display: "grid",
                gap: 8,
              }}
            >
              <div style={{ fontWeight: 700 }}>Temporary exception</div>
              <div style={{ fontSize: 14, lineHeight: 1.6 }}>
                {currentSection.governanceBanner ?? currentSection.readinessNote}
              </div>
              <div style={{ fontSize: 13, color: shellTokens.colorTextMuted }}>
                Wave 1 keeps this route visible only while its page contract closes; do not treat
                it as a fully governed surface.
              </div>
            </section>
          ) : null}

          <Outlet />
        </main>
      </div>
    </div>
  );
}
