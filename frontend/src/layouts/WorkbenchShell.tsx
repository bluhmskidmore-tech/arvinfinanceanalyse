import { lazy, Suspense, useEffect, type MouseEvent, type ReactNode } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";

import { LightIcon } from "../components/LightIcon";
import {
  findWorkbenchSectionByPath,
  isAgentFrontendEnabled,
  pathMatchesWorkbenchSection,
  primaryWorkbenchNavigationGroups,
  resolveWorkbenchGroupKey,
  resolveWorkbenchPathAlias,
  secondaryWorkbenchNavigation,
  type WorkbenchSection,
  visibleWorkbenchNavigation,
  workbenchNavigation,
} from "../app/navigation";
import { DataModeRibbon } from "../components/DataModeRibbon";
import {
  COCKPIT_SHELL_SECTION_KEYS,
  DASHBOARD_COCKPIT_SECTION_KEYS,
  MODULE_HOME_SECTION_KEYS,
  SECTION_SUBNAV_EXCLUDED_SECTION_KEYS,
  TERMINAL_BAR_EXCLUDED_SECTION_KEYS,
} from "./workbenchShellSections";

const WorkbenchShellMarketTicker = lazy(() => import("./WorkbenchShellMarketTicker"));
const institutionalConsoleShellSectionKeys = new Set([
  "cross-asset",
  "ledger-pnl",
  "product-category-pnl",
  "pnl-attribution",
]);

const unknownWorkbenchSection: WorkbenchSection = {
  key: "__unknown-route",
  label: "未知页面",
  path: "",
  icon: "settings",
  description: "当前路径未登记为工作台页面",
  readiness: "live",
  readinessLabel: "未登记",
  readinessNote: "当前路径没有匹配到已登记的工作台页面。",
};

function useInstitutionalConsoleCss(enabled: boolean) {
  useEffect(() => {
    if (!enabled) {
      return undefined;
    }

    void import("../styles/workbenchInstitutionalConsole.css");
    return undefined;
  }, [enabled]);
}

function useWorkbenchChromeCss(enabled: boolean) {
  useEffect(() => {
    if (!enabled) {
      return undefined;
    }

    void import("../styles/workbenchDeferredChrome.css");
    return undefined;
  }, [enabled]);
}

const iconMap: Record<string, ReactNode> = {
  dashboard: <LightIcon name="appstore" />,
  analysis: <LightIcon name="bar-chart" />,
  risk: <LightIcon name="alert" />,
  team: <LightIcon name="team" />,
  kpi: <LightIcon name="trophy" />,
  decision: <LightIcon name="apartment" />,
  bond: <LightIcon name="bank" />,
  settings: <LightIcon name="settings" />,
  market: <LightIcon name="fund" />,
  reports: <LightIcon name="file-text" />,
  agent: <LightIcon name="apartment" />,
};

type ReadinessTone = WorkbenchSection["readiness"] | "warning";

function sectionReadinessTone(
  section: Pick<WorkbenchSection, "readiness" | "governanceStatus">,
): ReadinessTone {
  return section.governanceStatus === "temporary-exception" ? "warning" : section.readiness;
}

const shellSupportEntries = [
  {
    key: "reports",
    label: "报表中心",
    to: "/reports",
    icon: <LightIcon name="file-text" />,
  },
  {
    key: "platform",
    label: "中台配置",
    to: "/platform-config",
    icon: <LightIcon name="settings" />,
  },
  {
    key: "help",
    label: "帮助文档",
    to: "/",
    icon: <LightIcon name="question-circle" />,
  },
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
  const location = useLocation();
  const isAgentLabRoute = location.pathname === "/agent-lab";
  const pathnameResolved = resolveWorkbenchPathAlias(location.pathname);
  const searchParams = new URLSearchParams(location.search);
  const agentFrontendEnabled = isAgentFrontendEnabled();
  const matchedSectionCandidate = findWorkbenchSectionByPath(
    location.pathname,
    workbenchNavigation,
  );
  const matchedSection =
    matchedSectionCandidate?.key === "agent" && !agentFrontendEnabled
      ? null
      : matchedSectionCandidate;
  const currentSection = matchedSection ?? unknownWorkbenchSection;
  const currentRouteKnown = Boolean(matchedSection);
  const showReadinessBanner =
    currentSection.readiness !== "live" &&
    !isAgentLabRoute &&
    (currentSection.key !== "agent" || agentFrontendEnabled);
  const isStockAnalysisShell = currentSection.key === "stock-analysis";
  const agentWorkbenchSection = visibleWorkbenchNavigation.find((section) => section.key === "agent");
  const agentWorkbenchActive = agentWorkbenchSection
    ? pathMatchesWorkbenchSection(agentWorkbenchSection.path, pathnameResolved)
    : false;
  const agentNavSectionLabel = isStockAnalysisShell ? "复核" : "对话";
  const agentNavLabel = isStockAnalysisShell ? "复核助手" : agentWorkbenchSection?.label;
  const agentNavBadgeLabel = isStockAnalysisShell ? "可用" : agentWorkbenchSection?.readinessLabel;
  const agentNavHint = isStockAnalysisShell ? "跨页证据" : "直接提问";
  const currentGroup = currentRouteKnown
    ? (primaryWorkbenchNavigationGroups.find(
        (group) => group.key === resolveWorkbenchGroupKey(currentSection),
      ) ?? primaryWorkbenchNavigationGroups[0])
    : null;
  const currentGroupVisibleSections = currentGroup
    ? visibleWorkbenchNavigation.filter(
        (section) => resolveWorkbenchGroupKey(section) === currentGroup.key,
      )
    : [];
  const currentGroupSections =
    currentGroup?.key === "market" ? currentGroupVisibleSections : (currentGroup?.sections ?? []);
  const isModuleHomePage = MODULE_HOME_SECTION_KEYS.includes(currentSection.key);
  const isPortfolioGroup = currentGroup?.key === "portfolio";
  const isDashboardCockpitShell = DASHBOARD_COCKPIT_SECTION_KEYS.includes(
    currentSection.key,
  );
  const useInstitutionalConsoleShell = institutionalConsoleShellSectionKeys.has(currentSection.key);
  useInstitutionalConsoleCss(useInstitutionalConsoleShell);
  useWorkbenchChromeCss(currentSection.key !== "dashboard");
  const isBondAnalysisMinimalShell = currentSection.key === "bond-analysis";
  const isLedgerPnlShell = currentSection.key === "ledger-pnl";
  const isProductCategoryPnlShell = currentSection.key === "product-category-pnl";
  const isPnlAttributionShell = currentSection.key === "pnl-attribution";
  /** 资产负债页以正式内容为主：壳层只保留页面顶栏，不再重复大号标题与市场条。 */
  const isBalanceAnalysisCompactChrome = currentSection.key === "balance-analysis";
  const isStockAnalysisMinimalShell = currentSection.key === "stock-analysis";
  const useCockpitShellFrame = COCKPIT_SHELL_SECTION_KEYS.includes(currentSection.key);
  const showShellTerminalBar = !TERMINAL_BAR_EXCLUDED_SECTION_KEYS.includes(
    currentSection.key,
  );
  const showShellMarketTicker = showShellTerminalBar && !isDashboardCockpitShell;
  const isBalanceMovementAnalysisCompactChrome =
    currentSection.key === "balance-movement-analysis";
  /** 负债结构分析页以页面正文为主，不显示组合导读 Hero / Suggested Flow 占位。 */
  const isLiabilityAnalyticsCompactChrome = currentSection.key === "liability-analytics";
  /** 与 bond-analysis 类似：去掉 main 外圈大卡片感，让页面自行铺色。跨资产仍保留组内子导航（市场数据 / 跨资产 / 新闻）。 */
  const isCrossAssetImmersiveMain = currentSection.key === "cross-asset";
  const isMarketDataTerminalMain = currentSection.key === "market-data";
  const isPortfolioPageOwnedChrome =
    isBalanceAnalysisCompactChrome ||
    isBalanceMovementAnalysisCompactChrome ||
    isLiabilityAnalyticsCompactChrome ||
    isProductCategoryPnlShell;
  const isMinimalMainChrome =
    isAgentLabRoute ||
    isDashboardCockpitShell ||
    isBondAnalysisMinimalShell ||
    isStockAnalysisMinimalShell ||
    isCrossAssetImmersiveMain ||
    isMarketDataTerminalMain ||
    isPortfolioPageOwnedChrome ||
    isModuleHomePage;
  const showFullWorkspaceGuidance =
    !isAgentLabRoute &&
    currentSection.readiness !== "live" &&
    !isBondAnalysisMinimalShell &&
    !isStockAnalysisMinimalShell &&
    !isCrossAssetImmersiveMain &&
    !isMarketDataTerminalMain &&
    !isBalanceMovementAnalysisCompactChrome &&
    !isLiabilityAnalyticsCompactChrome &&
    (isPortfolioGroup || currentSection.key !== "dashboard");
  const showWorkspaceHeroCard = showFullWorkspaceGuidance && !isBalanceAnalysisCompactChrome;
  const showPortfolioDecisionBoard =
    isPortfolioGroup &&
    currentSection.readiness !== "live" &&
    !isBondAnalysisMinimalShell &&
    !isStockAnalysisMinimalShell &&
    !isPortfolioPageOwnedChrome;
  const currentGroupSectionCount = currentGroupSections.length;
  const explicitReportDate = searchParams.get("report_date")?.trim() ?? "";
  const shellReportDate =
    explicitReportDate ||
    "默认路由";
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

  function focusMainContent(event: MouseEvent<HTMLAnchorElement>) {
    const mainContent = document.getElementById("workbench-main-content");
    if (!mainContent) {
      return;
    }

    event.preventDefault();
    mainContent.focus();
  }

  return (
    <>
    <DataModeRibbon variant={isDashboardCockpitShell ? "cockpit" : "default"} />
    <a
      className="workbench-skip-link"
      href="#workbench-main-content"
      onClick={focusMainContent}
    >
      Skip to main content
    </a>
    <div
      className={`workbench-shell-root workbench-shell-grid${
        useInstitutionalConsoleShell ? " workbench-shell-grid--institutional-console" : ""
      }${
        useCockpitShellFrame ? " workbench-shell-grid--cockpit" : " workbench-shell-grid--desktop-aligned"
      }${isBondAnalysisMinimalShell ? " workbench-shell-grid--bond-analysis" : ""}${
        isStockAnalysisShell ? " workbench-shell-grid--stock-analysis" : ""
      }${isLedgerPnlShell ? " workbench-shell-grid--ledger-pnl" : ""
      }${isProductCategoryPnlShell ? " workbench-shell-grid--product-category-pnl" : ""
      }${isPnlAttributionShell ? " workbench-shell-grid--pnl-attribution" : ""
      }${isCrossAssetImmersiveMain ? " workbench-shell-grid--cross-asset" : ""
      }${isBalanceMovementAnalysisCompactChrome ? " workbench-shell-grid--balance-movement" : ""
      }`}
    >
      <aside
        className={`workbench-shell-aside workbench-shell-rail${
          isMinimalMainChrome ? " workbench-shell-rail--minimal" : ""
        }`}
      >
        <div className="workbench-shell-rail-brand-wrap">
          <div className="workbench-shell-rail-brand-row">
            <div className="workbench-shell-rail-mark">
              M
            </div>
            <div className="workbench-shell-rail-title-stack">
              <span className="workbench-shell-rail-product-name">
                MOSS
              </span>
            </div>
          </div>
        </div>


        <section className="workbench-shell-nav-section">
          <span className="workbench-shell-section-label workbench-shell-section-label--rail">
            工作台
          </span>
          <nav
            aria-label="主工作台"
            data-testid="workbench-group-nav"
            className="workbench-group-nav-shell"
          >
            {primaryWorkbenchNavigationGroups.map((group) => {
              const active = currentGroup ? group.key === currentGroup.key : false;

              return (
                <NavLink
                  key={group.key}
                  to={group.defaultPath}
                  className="workbench-shell-group-link"
                  data-active={active ? "true" : "false"}
                >
                  <span className="workbench-shell-group-icon">
                    {iconMap[group.icon]}
                  </span>
                  <span className="workbench-shell-group-label">
                    {group.label}
                  </span>
                  <span className="workbench-shell-group-count">
                    首页
                  </span>
                </NavLink>
              );
            })}
          </nav>
        </section>

        {agentWorkbenchSection ? (
          <section
            className="workbench-shell-agent-nav"
            data-testid="workbench-agent-nav"
          >
            <span className="workbench-shell-section-label workbench-shell-section-label--rail">
              {agentNavSectionLabel}
            </span>
            <NavLink
              to={agentWorkbenchSection.path}
              className="workbench-shell-agent-nav__link"
              data-active={agentWorkbenchActive ? "true" : "false"}
            >
              <div className="workbench-shell-agent-nav__main">
                <span className="workbench-shell-agent-nav__icon">
                  {iconMap[agentWorkbenchSection.icon]}
                </span>
                <span className="workbench-shell-agent-nav__label">
                  {agentNavLabel}
                </span>
                <span
                  className="workbench-shell-agent-nav__badge"
                  data-readiness-tone={sectionReadinessTone(agentWorkbenchSection)}
                >
                  {agentNavBadgeLabel}
                </span>
              </div>
              <span className="workbench-shell-agent-nav__hint">
                {agentNavHint}
              </span>
            </NavLink>
          </section>
        ) : null}

        {!isBondAnalysisMinimalShell &&
        !isBalanceMovementAnalysisCompactChrome &&
        secondaryWorkbenchNavigation.length > 0 ? (
          <section
            className="workbench-shell-rail-section workbench-shell-rail-section--gap-6"
          >
            <span className="workbench-shell-section-label workbench-shell-section-label--rail">
              规划入口
            </span>
            {secondaryWorkbenchNavigation.map((item) => {
              const active = pathMatchesWorkbenchSection(item.path, pathnameResolved);

              return (
                <NavLink
                  key={item.key}
                  to={item.path}
                  className="workbench-shell-secondary-link"
                  data-active={active ? "true" : "false"}
                >
                  <div className="workbench-shell-secondary-row">
                    <span className="workbench-shell-secondary-icon">{iconMap[item.icon]}</span>
                    <span className="workbench-shell-secondary-label">{item.label}</span>
                    <span
                      className="workbench-shell-secondary-badge"
                      data-readiness-tone={sectionReadinessTone(item)}
                    >
                      {item.readinessLabel}
                    </span>
                  </div>
                </NavLink>
              );
            })}
          </section>
        ) : null}

        <section
          data-testid="workbench-support-nav"
          className="workbench-shell-rail-section"
        >
          <span className="workbench-shell-section-label workbench-shell-section-label--rail">
            支持入口
          </span>
          {shellSupportEntries.map((item) => {
            const active = item.to !== "/" && pathnameResolved === item.to;

            return (
              <NavLink
                key={item.key}
                to={item.to}
                className="workbench-shell-support-link"
                data-active={active ? "true" : "false"}
              >
                <span className="workbench-shell-support-icon">{item.icon}</span>
                <span className="workbench-shell-support-label">{item.label}</span>
              </NavLink>
            );
          })}
        </section>
      </aside>

      <div className="workbench-main-column">
        {showShellTerminalBar ? (
        <header
          data-testid="workbench-terminal-bar"
          className="workbench-terminal-bar"
        >
          <div className="workbench-terminal-bar-split">
            <section
              data-testid="workbench-page-context"
              className="workbench-page-context-shell"
            >
              <div className="workbench-page-title-display">
                {currentSection.label}
              </div>
              <span className="workbench-shell-report-chip">
                {"\u62a5\u544a\u65e5"} {shellReportDate}
              </span>
            </section>

            <section
              data-testid="workbench-operator-zone"
              className="workbench-operator-zone-shell"
            >
              <span className="workbench-operator-pill-quiet">
                <LightIcon name="user" />
                <span>{"\u7ba1\u7406\u89c6\u89d2"}</span>
              </span>
              {shellSupportEntries
                .filter((item) => item.key !== "help")
                .map((item) => {
                  const active = pathnameResolved === item.to;

                  return (
                    <NavLink
                      key={`terminal-${item.key}`}
                      to={item.to}
                      data-active={active ? "true" : "false"}
                      className="workbench-terminal-utility-navlink"
                    >
                      <span className="workbench-terminal-utility-icon">{item.icon}</span>
                      <span>{item.label}</span>
                    </NavLink>
                  );
                })}
            </section>
          </div>

          {showShellMarketTicker ? (
            <Suspense fallback={null}>
              <WorkbenchShellMarketTicker />
            </Suspense>
          ) : null}
        </header>
        ) : null}
        {showWorkspaceHeroCard ? (
          <header
            className="workbench-workspace-hero"
            data-hero-layout={isPortfolioGroup ? "portfolio" : "standard"}
            data-hero-density={isBalanceAnalysisCompactChrome ? "compact" : "comfortable"}
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
                  className="portfolio-workbench-lead"
                >
                  <div className="portfolio-workbench-lead__copy-stack">
                    <span className="portfolio-workbench-lead__eyebrow">
                      组合工作台
                    </span>
                    <div className="portfolio-workbench-lead__title">
                      组合状态先看错配，再看损益，最后定位仓位与归因
                    </div>
                    <div className="portfolio-workbench-lead__description">
                      当前工作台聚合 {currentGroup?.label ?? ""} 的核心页面。首屏不再平铺全部入口，而是先用正式链路做判断，再进入结构、仓位和归因页面解释原因，避免把占位页或分析口径结果误读成正式结论。
                    </div>
                  </div>

                  <div className="portfolio-workbench-lead__stats-grid">
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
                        className="portfolio-workbench-lead__stat-card"
                      >
                        <span className="portfolio-workbench-lead__stat-label">
                          {item.label}
                        </span>
                        <strong
                          className="portfolio-workbench-lead__stat-value"
                          data-value-size={item.value.length > 8 ? "compact" : "normal"}
                        >
                          {item.value}
                        </strong>
                        <span className="portfolio-workbench-lead__stat-detail">
                          {item.detail}
                        </span>
                      </div>
                    ))}
                  </div>
                </section>

                <aside
                  data-testid="portfolio-workbench-flow"
                  className="portfolio-workbench-flow"
                >
                  <div className="portfolio-workbench-flow__header">
                    <span className="portfolio-workbench-flow__eyebrow">
                      Suggested Flow
                    </span>
                    <div className="portfolio-workbench-flow__title">
                      先用正式结果做结论，再下钻解释原因
                    </div>
                  </div>

                  <div className="portfolio-workbench-flow__list">
                    {portfolioLeadSections.map((item, index) => {
                      const active = pathMatchesWorkbenchSection(item.section.path, pathnameResolved);

                      return (
                        <NavLink
                          key={item.section.key}
                          to={item.section.path}
                          className="portfolio-workbench-flow__link"
                          data-active={active ? "true" : "false"}
                        >
                          <div className="portfolio-workbench-flow__row">
                            <span className="portfolio-workbench-flow__step">
                              {index + 1}
                            </span>
                            <span className="portfolio-workbench-flow__link-title">{item.title}</span>
                            <span
                              className="portfolio-workbench-flow__badge"
                              data-readiness-tone={sectionReadinessTone(item.section)}
                            >
                              {item.section.readinessLabel}
                            </span>
                          </div>
                          <div className="portfolio-workbench-flow__detail">
                            {item.detail}
                          </div>
                          <div className="portfolio-workbench-flow__meta">
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
                <div className="workbench-shell-status-summary">
                  <span className="workbench-shell-status-summary__eyebrow">
                    一期状态
                  </span>
                  <div className="workbench-shell-status-summary__title">
                    当前只突出可验证的真实读链路
                  </div>
                  <div className="workbench-shell-status-summary__description">
                    当前工作台：{currentGroup?.label ?? ""}。页面切换收进组内导航，避免在壳层堆满入口。
                  </div>
                </div>

                <div className="workbench-shell-status-meta">
                  <span
                    className="workbench-shell-status-meta__badge"
                    data-readiness-tone={sectionReadinessTone(currentSection)}
                  >
                    {currentSection.label} · {currentSection.readinessLabel}
                  </span>
                  <span className="workbench-shell-status-meta__note">
                    {currentSection.readinessNote}
                  </span>
                </div>
              </>
            )}
          </header>
        ) : null}

        <main
          id="workbench-main-content"
          aria-label="Main content"
          data-testid="workbench-main-content"
          tabIndex={-1}
          className={`workbench-main-surface${
            isMinimalMainChrome ? " workbench-main-surface--minimal" : ""
          }`}
        >
          {showPortfolioDecisionBoard ? (
            <section
              data-testid="portfolio-workbench-board"
              className="portfolio-workbench-board"
            >
              {portfolioBoard.map((stage) => (
                <article
                  key={stage.title}
                  className="portfolio-workbench-board__stage"
                >
                  <div className="portfolio-workbench-board__stage-header">
                    <span className="portfolio-workbench-board__stage-title">
                      {stage.title}
                    </span>
                    <div className="portfolio-workbench-board__stage-description">
                      {stage.description}
                    </div>
                  </div>

                  <div className="portfolio-workbench-board__section-list">
                    {stage.sections.map((section) => {
                      const active = pathMatchesWorkbenchSection(section.path, pathnameResolved);

                      return (
                        <NavLink
                          key={section.key}
                          to={section.path}
                          className="portfolio-workbench-board__section-link"
                        >
                          <div className="portfolio-workbench-board__section-row">
                            <span className="portfolio-workbench-board__section-icon">
                              {iconMap[section.icon]}
                            </span>
                            <span className="portfolio-workbench-board__section-title">{section.label}</span>
                            <span
                              className="portfolio-workbench-board__section-badge"
                              data-readiness-tone={sectionReadinessTone(section)}
                            >
                              {active ? "当前页" : section.readinessLabel}
                            </span>
                          </div>
                          <div className="portfolio-workbench-board__section-description">
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

          {!isAgentLabRoute &&
          !SECTION_SUBNAV_EXCLUDED_SECTION_KEYS.includes(currentSection.key) &&
          currentGroup ? (
            <section
              data-testid="workbench-section-subnav"
              className="workbench-section-subnav"
            >
              <div className="workbench-section-subnav__header">
                <span className="workbench-section-subnav__eyebrow">
                  {isPortfolioGroup ? "全部已开放页面" : "当前工作台页面"}
                </span>
                <div className="workbench-section-subnav__title">
                  {currentGroup.label}
                </div>
              </div>

              <div className="workbench-section-subnav__links">
                {currentGroupSections.map((section) => {
                  const active = pathMatchesWorkbenchSection(section.path, pathnameResolved);

                  return (
                    <NavLink
                      key={section.key}
                      to={section.path}
                      className="workbench-section-subnav__link"
                      data-active={active ? "true" : "false"}
                    >
                      <span className="workbench-section-subnav__icon">{iconMap[section.icon]}</span>
                      <span>{section.label}</span>
                    </NavLink>
                  );
                })}
              </div>
            </section>
          ) : null}

          {showReadinessBanner ? (
            <section
              data-testid="workbench-readiness-banner"
              className="workbench-notice"
              data-readiness={currentSection.readiness}
            >
              <div className="workbench-notice__title">
                {currentSection.readiness === "placeholder"
                  ? "当前页面仍是占位壳层"
                  : "当前页面尚未物化真实数据链路"}
              </div>
              <div className="workbench-notice__body">{currentSection.readinessNote}</div>
              <div className="workbench-notice__hint">
                如需先查看可验证的数据页面，请优先使用当前工作台中的已开放子页面。
              </div>
            </section>
          ) : null}

          {currentSection.governanceStatus === "temporary-exception" ? (
            <section
              data-testid="workbench-governance-banner"
              className="workbench-notice"
              data-notice-tone="governance"
            >
              <div className="workbench-notice__title">临时例外</div>
              <div className="workbench-notice__body">
                {currentSection.governanceBanner ?? currentSection.readinessNote}
              </div>
              <div className="workbench-notice__hint">
                第一阶段仅在页面契约收口期间保留该路由可见；不要把它视为已完全治理的页面。
              </div>
            </section>
          ) : null}

          <Outlet />
        </main>
      </div>
    </div>
    </>
  );
}
