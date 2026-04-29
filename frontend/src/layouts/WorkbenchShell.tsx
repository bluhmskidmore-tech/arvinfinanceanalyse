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
import { Button, Modal } from "antd";
import { useMemo, useState, type ReactNode } from "react";
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
import { designTokens } from "../theme/designSystem";
import { shellTokens } from "../theme/tokens";
import { formatChoiceMacroDelta, formatChoiceMacroValue } from "../utils/choiceMacroFormat";
import AgentWorkbenchPage from "../features/agent/AgentWorkbenchPage";

/** 左侧主导航整块统一底色（无渐变、不在侧栏内再铺明显第二色层） */
const WORKBENCH_RAIL_SOLID_BACKGROUND = "#121d2a";

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
    padding: "10px 12px",
    borderRadius: 12,
    background: active ? "rgba(255,255,255,0.06)" : "transparent",
    color: active ? "#f4f7fb" : "rgba(220,228,236,0.88)",
    border: "none",
    boxShadow: active ? `inset 4px 0 0 ${designTokens.color.primary[400]}` : "none",
    transition:
      "background-color 160ms ease, color 160ms ease, border-color 160ms ease, box-shadow 160ms ease",
  } as const;
}

function groupSectionPillStyle(active: boolean) {
  return {
    display: "inline-flex",
    alignItems: "center",
    gap: 8,
    padding: "8px 12px",
    borderRadius: 14,
    background: active ? shellTokens.colorAccentSoft : "rgba(245,247,250,0.82)",
    color: active ? shellTokens.colorTextPrimary : shellTokens.colorTextSecondary,
    border: active
      ? `1px solid ${shellTokens.colorBorderStrong}`
      : `1px solid ${shellTokens.colorBorderSoft}`,
    fontSize: 12,
    fontWeight: 600,
    boxShadow: active ? "inset 0 1px 0 rgba(255,255,255,0.64)" : "none",
    transition:
      "background-color 160ms ease, color 160ms ease, border-color 160ms ease, box-shadow 160ms ease",
  } as const;
}

function supportLinkStyle(active: boolean) {
  return {
    display: "flex",
    alignItems: "center",
    gap: 8,
    padding: "7px 10px",
    borderRadius: 10,
    background: active ? "rgba(255,255,255,0.06)" : "transparent",
    color: active ? "#f4f7fb" : "rgba(184,197,210,0.82)",
    border: "none",
    fontSize: 11,
    fontWeight: 600,
    transition: "background-color 160ms ease, color 160ms ease, border-color 160ms ease",
  } as const;
}

type ShellTickerTone = "up" | "down";

type ShellTickerItem = {
  key: string;
  label: string;
  value: string;
  delta: string;
  tone: ShellTickerTone;
};

const fallbackShellTickerItems: ShellTickerItem[] = [
  { key: "cgb10y", label: "10年国债", value: "1.94%", delta: "+2bp", tone: "up" },
  { key: "dr007", label: "DR007", value: "1.82%", delta: "-6bp", tone: "down" },
  { key: "omo7d", label: "7天逆回购", value: "1.75%", delta: "+1bp", tone: "up" },
  { key: "usd-cny", label: "美元/人民币", value: "7.21", delta: "+0.02", tone: "up" },
] as const;

const shellTickerSeriesSpecs = [
  {
    key: "cgb10y",
    label: "10年国债",
    matchers: ["中债国债到期收益率:10年", "10年期国债到期收益率"],
  },
  {
    key: "policyBank10y",
    label: "10年国开",
    matchers: ["中债政策性金融债到期收益率(国开行)10年"],
  },
  {
    key: "us10y",
    label: "10年美债",
    matchers: ["美国10年期国债收益率", "美国:国债收益率:10年"],
  },
  {
    key: "cnUs10ySpread",
    label: "中美10年利差",
    matchers: ["中美国债利差(10Y)", "10Y中国国债-10Y美国国债"],
  },
  {
    key: "dr007",
    label: "DR007",
    matchers: ["DR007"],
  },
  {
    key: "omo7d",
    label: "7天逆回购",
    matchers: ["公开市场7天逆回购利率"],
  },
  {
    key: "usd-cny",
    label: "美元/人民币",
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
    key: "bank-ledger-dashboard",
    title: "再看银行台账",
    detail: "用 as_of_date 台账快照核对资产、发行负债、净敞口和明细 trace。",
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
    description: "先确定规模、久期和正式结果，不把分析估算混成首结论。",
    sectionKeys: ["balance-analysis", "bank-ledger-dashboard", "bond-dashboard", "ledger-pnl"],
  },
  {
    title: "仓位与结构",
    description: "需要解释变化时，再看持仓、负债结构和日均口径的形态变化。",
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
  const [agentDialogOpen, setAgentDialogOpen] = useState(false);
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
  /** 资产负债页以正式内容为主：壳层只保留一句阅读提示，不再占满首屏导读卡片与阶段看板。 */
  const isBalanceAnalysisCompactChrome = currentSection.key === "balance-analysis";
  const isBalanceMovementAnalysisCompactChrome =
    currentSection.key === "balance-movement-analysis";
  /** 负债结构分析页以页面正文为主，不显示组合导读 Hero / Suggested Flow 占位。 */
  const isLiabilityAnalyticsCompactChrome = currentSection.key === "liability-analytics";
  /** 与 bond-analysis 类似：去掉 main 外圈大卡片感，让页面自行铺色。跨资产仍保留组内子导航（市场数据 / 跨资产 / 新闻）。 */
  const isCrossAssetImmersiveMain = currentSection.key === "cross-asset";
  const isPortfolioPageOwnedChrome =
    isBalanceAnalysisCompactChrome ||
    isBalanceMovementAnalysisCompactChrome ||
    isLiabilityAnalyticsCompactChrome;
  const isMinimalMainChrome =
    isBondAnalysisMinimalShell || isCrossAssetImmersiveMain || isPortfolioPageOwnedChrome;
  const showWorkspaceHeroCard =
    !isBondAnalysisMinimalShell &&
    !isCrossAssetImmersiveMain &&
    !isBalanceMovementAnalysisCompactChrome &&
    !isLiabilityAnalyticsCompactChrome &&
    (isPortfolioGroup || currentSection.key !== "dashboard");
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
      ? bondAnalyticsDatesQuery.data?.result?.report_dates[0] ?? "可用最新日"
      : "默认路由");
  const shellTickerItems = useMemo(
    () => buildShellTickerItems(shellTickerQuery.data?.result?.series ?? []),
    [shellTickerQuery.data?.result?.series],
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
  /** 深色主导航轨分割线（与参照图侧栏一致） */
  const railDividerColor = "rgba(255,255,255,0.08)";
  const contentSurfaceShadow = "0 16px 34px rgba(15, 23, 42, 0.08)";

  return (
    <div
      className="workbench-shell-grid"
      style={{
        minHeight: "100vh",
        padding: "14px clamp(14px, 1.6vw, 24px)",
        background:
          "radial-gradient(circle at top left, rgba(233,240,246,0.92) 0%, rgba(244,247,249,0.98) 38%, rgba(239,243,246,1) 100%)",
      }}
    >
      <aside
        className="workbench-shell-aside"
        style={{
          display: "grid",
          alignContent: "start",
          gap: 12,
          padding: isMinimalMainChrome ? "12px" : "14px",
          border: `1px solid ${railDividerColor}`,
          borderRadius: 20,
          boxShadow: "0 22px 48px rgba(10, 21, 33, 0.16)",
          background: WORKBENCH_RAIL_SOLID_BACKGROUND,
        }}
      >
        <div
          style={{
            display: "grid",
            gap: 6,
            padding: "4px 2px 12px",
            borderBottom: `1px solid ${railDividerColor}`,
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
                width: 36,
                height: 36,
                borderRadius: 12,
                background: "rgba(255,255,255,0.1)",
                color: "#f5f7fa",
                fontWeight: 700,
                boxShadow: "none",
              }}
            >
              M
            </div>
            <div style={{ display: "grid", gap: 0, minWidth: 0 }}>
              <span
                style={{
                  color: "#f5f7fa",
                  fontWeight: 700,
                  fontSize: 16,
                  letterSpacing: "-0.02em",
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
              当前范围
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
          aria-label="主工作台"
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
              borderTop: `1px solid ${railDividerColor}`,
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
              borderTop: `1px solid ${railDividerColor}`,
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
              保留模块
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

        <section className="workbench-shell-nav-section">
          <span className="workbench-shell-section-label workbench-shell-section-label--rail">
            工作台
          </span>
          <nav
            aria-label="主工作台"
            data-testid="workbench-group-nav"
            style={{ display: "grid", gap: 4 }}
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
                      border: active ? `1px solid rgba(255,255,255,0.22)` : "none",
                      color: active ? "#ffffff" : "rgba(184,197,210,0.76)",
                      fontSize: 10,
                      background: active ? "rgba(255,255,255,0.1)" : "transparent",
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
                      letterSpacing: "-0.01em",
                    }}
                  >
                    {group.label}
                  </span>
                  <span
                    style={{
                      color: active ? "rgba(223,235,255,0.94)" : "rgba(184,197,210,0.62)",
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
              borderTop: `1px solid ${railDividerColor}`,
            }}
          >
            <span className="workbench-shell-section-label workbench-shell-section-label--rail">
              保留模块
            </span>
            {secondaryWorkbenchNavigation.map((item) => {
              const active = pathMatchesWorkbenchSection(item.path, pathnameResolved);

              if (item.key === "agent") {
                return (
                  <Button
                    key={item.key}
                    type="text"
                    className="workbench-agent-dialog-trigger"
                    onClick={() => setAgentDialogOpen(true)}
                    style={{
                      height: "auto",
                      padding: "8px 10px",
                      borderRadius: 12,
                      border: `1px solid ${railDividerColor}`,
                      background: "transparent",
                      color: "#f4f7fb",
                    }}
                  >
                    <div className="workbench-agent-dialog-trigger__main">
                      <span style={{ fontSize: 12 }}>{iconMap[item.icon]}</span>
                      <span style={{ flex: 1, fontSize: 12, fontWeight: 600 }}>智能体对话</span>
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
                    <span className="workbench-agent-dialog-trigger__hint">
                      基于当前页面提问
                    </span>
                  </Button>
                );
              }

              return (
                <NavLink
                  key={item.key}
                  to={item.path}
                  style={{
                    display: "grid",
                    gap: 2,
                    padding: "8px 10px",
                    borderRadius: 12,
                    background: active ? "rgba(255,255,255,0.06)" : "transparent",
                    color: active ? "#f4f7fb" : "rgba(205,215,224,0.88)",
                    border: "none",
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
            borderTop: `1px solid ${railDividerColor}`,
          }}
        >
          <span className="workbench-shell-section-label workbench-shell-section-label--rail">
            支持入口
          </span>
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
            gap: 10,
            padding: "14px 18px",
            border: `1px solid ${shellTokens.colorBorder}`,
            borderRadius: 22,
            background:
              "linear-gradient(180deg, rgba(250,252,253,0.96) 0%, rgba(242,246,249,0.98) 100%)",
            boxShadow: "0 10px 22px rgba(15, 23, 42, 0.06)",
          }}
        >
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 12,
            }}
          >
            <section
              data-testid="workbench-page-context"
              style={{
                display: "flex",
                flexWrap: "wrap",
                alignItems: "center",
                gap: 10,
                minWidth: 0,
              }}
            >
              <div
                style={{
                  color: shellTokens.colorTextPrimary,
                  fontSize: "clamp(28px, 3.2vw, 36px)",
                  lineHeight: 1.02,
                  fontWeight: 700,
                  letterSpacing: "-0.045em",
                }}
              >
                {currentSection.label}
              </div>
              <span
                style={{
                  color: shellTokens.colorTextSecondary,
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 4,
                  padding: "4px 10px",
                  borderRadius: 999,
                  border: `1px solid ${shellTokens.colorBorderSoft}`,
                  background: "rgba(255,255,255,0.82)",
                  fontSize: 12,
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
                  padding: "5px 10px",
                  borderRadius: 999,
                  border: `1px solid ${shellTokens.colorBorderSoft}`,
                  background: "rgba(241, 245, 249, 0.92)",
                  color: shellTokens.colorTextSecondary,
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
                      padding: "4px 2px",
                      color: shellTokens.colorTextSecondary,
                      fontSize: 12,
                      fontWeight: 600,
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
              gap: 10,
              minWidth: 0,
              paddingTop: 2,
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
              市场快讯
            </span>
            {shellTickerItems.map((item, index) => (
              <div
                key={item.key}
                style={{
                  display: "inline-flex",
                  alignItems: "baseline",
                  gap: 5,
                  minWidth: 0,
                }}
              >
                <span
                  style={{
                    color: shellTokens.colorTextMuted,
                    fontSize: 10,
                    fontWeight: 600,
                    letterSpacing: "0.03em",
                  }}
                >
                  {item.label}
                </span>
                <strong
                  style={{
                    color: shellTokens.colorTextPrimary,
                    fontSize: 15,
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
                {index < shellTickerItems.length - 1 ? (
                  <span
                    style={{
                      width: 1,
                      height: 10,
                      background: shellTokens.colorBorderSoft,
                    }}
                  />
                ) : null}
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
              gap: 16,
              padding: isBalanceAnalysisCompactChrome ? "12px 18px" : "18px 22px",
              border: `1px solid ${shellTokens.colorBorder}`,
              borderRadius: isBalanceAnalysisCompactChrome ? 18 : 24,
              boxShadow: contentSurfaceShadow,
              background: `linear-gradient(180deg, rgba(255,255,255,0.96) 0%, ${shellTokens.colorBgSurface} 100%)`,
            }}
          >
            {isPortfolioGroup && isBalanceAnalysisCompactChrome ? (
              <section
                data-testid="portfolio-workbench-light-hint"
                className="portfolio-workbench-light-hint"
              >
                <span className="portfolio-workbench-light-hint__eyebrow">
                  组合工作台
                </span>
                <p className="portfolio-workbench-light-hint__copy">
                  <strong className="portfolio-workbench-light-hint__strong">先以正式余额下结论</strong>
                  ，再下钻损益、仓位与归因；占位模块不混入首屏判断。
                </p>
                <nav className="portfolio-workbench-light-hint__nav">
                  <span className="portfolio-workbench-light-hint__nav-label">后续：</span>
                  {portfolioFlow
                    .filter((item) => item.key !== "balance-analysis")
                    .map((item) => {
                      const section = findSectionByKey(currentGroupSections, item.key);
                      if (!section) {
                        return null;
                      }
                      return (
                        <NavLink
                          key={item.key}
                          to={section.path}
                          className="portfolio-workbench-light-hint__nav-link"
                        >
                          {section.label}
                        </NavLink>
                      );
                    })}
                </nav>
              </section>
            ) : isPortfolioGroup ? (
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
                      组合工作台
                    </span>
                    <div
                      style={{
                        fontSize: "clamp(24px, 2.6vw, 30px)",
                        lineHeight: 1.18,
                        fontWeight: 700,
                        letterSpacing: "-0.03em",
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
                      当前工作台聚合 {currentGroup.label} 的核心页面。首屏不再平铺全部入口，而是先用正式链路做判断，再进入结构、仓位和归因页面解释原因，避免把占位页或分析口径结果误读成正式结论。
                    </div>
                  </div>

                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
                      gap: 8,
                    }}
                  >
                    {[
                      {
                        label: "可访问页面",
                        value: `${currentGroupSectionCount}`,
                        detail: "当前分组内已开放页面",
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
                          padding: "12px 14px",
                          borderRadius: 16,
                          border: `1px solid ${shellTokens.colorBorderSoft}`,
                          background: "rgba(255,255,255,0.84)",
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
                    padding: 16,
                    borderRadius: 20,
                    border: `1px solid ${shellTokens.colorBorderSoft}`,
                    background:
                      "linear-gradient(180deg, rgba(235, 241, 246, 0.84) 0%, rgba(255,255,255,0.9) 100%)",
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
                            padding: "12px 14px",
                            borderRadius: 16,
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
                    一期状态
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
            padding: isMinimalMainChrome ? 0 : 20,
            border: isMinimalMainChrome ? "none" : `1px solid ${shellTokens.colorBorder}`,
            borderRadius: isMinimalMainChrome ? 0 : 24,
            boxShadow: isMinimalMainChrome ? "none" : contentSurfaceShadow,
            background: isMinimalMainChrome
              ? "transparent"
              : `linear-gradient(180deg, rgba(255,255,255,0.98) 0%, ${shellTokens.colorBgSurface} 100%)`,
            display: "grid",
            alignContent: "start",
            gap: 18,
          }}
        >
          {isPortfolioGroup && !isBondAnalysisMinimalShell && !isPortfolioPageOwnedChrome ? (
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
                  {isPortfolioGroup ? "全部已开放页面" : "当前工作台页面"}
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
                如需先查看可验证的数据页面，请优先使用当前工作台中的已开放子页面。
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
              <div style={{ fontWeight: 700 }}>临时例外</div>
              <div style={{ fontSize: 14, lineHeight: 1.6 }}>
                {currentSection.governanceBanner ?? currentSection.readinessNote}
              </div>
              <div style={{ fontSize: 13, color: shellTokens.colorTextMuted }}>
                第一阶段仅在页面契约收口期间保留该路由可见；不要把它视为已完全治理的页面。
              </div>
            </section>
          ) : null}

          <Outlet />
        </main>
      </div>
      <Modal
        title="智能体对话"
        open={agentDialogOpen}
        onCancel={() => setAgentDialogOpen(false)}
        footer={null}
        width="min(1120px, 92vw)"
        destroyOnHidden={false}
        className="workbench-agent-dialog"
      >
        <AgentWorkbenchPage />
      </Modal>
    </div>
  );
}
