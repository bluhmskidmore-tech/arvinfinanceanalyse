import {
  lazy,
  Suspense,
  useEffect,
  useRef,
  useState,
  type MouseEvent,
  type ReactNode,
} from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";

import { LightIcon } from "../components/LightIcon";
import "../styles/workbenchNavigation.css";
import "../styles/marketOverviewShell.css";
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
  INSTITUTIONAL_CONSOLE_SECTION_KEYS,
  MODULE_HOME_SECTION_KEYS,
  SECTION_SUBNAV_EXCLUDED_SECTION_KEYS,
  TERMINAL_BAR_EXCLUDED_SECTION_KEYS,
} from "./workbenchShellSections";

const WorkbenchShellMarketTicker = lazy(() => import("./WorkbenchShellMarketTicker"));

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
    label: "报表与数据",
    to: "/reports",
    icon: <LightIcon name="file-text" />,
  },
  {
    key: "platform",
    label: "中台配置",
    to: "/platform-config",
    icon: <LightIcon name="settings" />,
  },
] as const;

const unavailableShellSupportEntry = {
  key: "help",
  label: "帮助文档",
  availabilityLabel: "未接入",
  icon: <LightIcon name="question-circle" />,
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
    detail: "按业务口径核对正式余额，确认组合状态和错配位置。",
  },
  {
    key: "bank-ledger-dashboard",
    title: "再看银行台账",
    detail: "按数据日期核对台账资产、发行负债、净敞口与明细。",
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

/** 组内子导航单行内联上限；其余页面收进「更多」下拉（DESIGN.md §6 溯源分层 + 降噪 PRD FR-3）。 */
const SUBNAV_MAX_INLINE = 7;

export function WorkbenchShell() {
  const location = useLocation();
  const [governanceDetailOpen, setGovernanceDetailOpen] = useState(false);
  const [subnavMoreOpen, setSubnavMoreOpen] = useState(false);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const governanceNoticeRef = useRef<HTMLElement | null>(null);
  const governanceToggleRef = useRef<HTMLButtonElement | null>(null);
  const subnavMoreRef = useRef<HTMLDivElement | null>(null);
  const subnavMoreToggleRef = useRef<HTMLButtonElement | null>(null);
  const mobileNavDrawerRef = useRef<HTMLElement | null>(null);
  const mobileNavToggleRef = useRef<HTMLButtonElement | null>(null);
  const mobileNavCloseRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    setGovernanceDetailOpen(false);
    setSubnavMoreOpen(false);
    setMobileNavOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    if (!subnavMoreOpen) {
      return undefined;
    }

    function onPointerDown(event: PointerEvent) {
      if (
        subnavMoreRef.current &&
        !subnavMoreRef.current.contains(event.target as Node)
      ) {
        setSubnavMoreOpen(false);
      }
    }

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        setSubnavMoreOpen(false);
        subnavMoreToggleRef.current?.focus();
      }
    }

    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [subnavMoreOpen]);

  useEffect(() => {
    if (!governanceDetailOpen) return undefined;

    function onPointerDown(event: PointerEvent) {
      if (!governanceNoticeRef.current?.contains(event.target as Node)) {
        setGovernanceDetailOpen(false);
      }
    }

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        setGovernanceDetailOpen(false);
        governanceToggleRef.current?.focus();
      }
    }

    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [governanceDetailOpen]);

  useEffect(() => {
    if (!mobileNavOpen) {
      return undefined;
    }

    const previousBodyOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    mobileNavCloseRef.current?.focus();

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        setMobileNavOpen(false);
        mobileNavToggleRef.current?.focus();
        return;
      }

      if (event.key !== "Tab") {
        return;
      }

      const focusableElements = Array.from(
        mobileNavDrawerRef.current?.querySelectorAll<HTMLElement>(
          'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])',
        ) ?? [],
      );
      const firstFocusable = focusableElements[0];
      const lastFocusable = focusableElements[focusableElements.length - 1];

      if (!firstFocusable || !lastFocusable) {
        return;
      }

      if (event.shiftKey && document.activeElement === firstFocusable) {
        event.preventDefault();
        lastFocusable.focus();
      } else if (!event.shiftKey && document.activeElement === lastFocusable) {
        event.preventDefault();
        firstFocusable.focus();
      }
    }

    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.body.style.overflow = previousBodyOverflow;
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [mobileNavOpen]);

  const isAgentLabRoute = location.pathname === "/agent-lab";
  const pathnameResolved = resolveWorkbenchPathAlias(location.pathname);
  const searchParams = new URLSearchParams(location.search);
  const isPublicationCaptureMode = searchParams.get("publication_capture") === "1";
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
    currentSection.key !== "agent";
  const isStockAnalysisShell = currentSection.key === "stock-analysis";
  const agentWorkbenchSection = visibleWorkbenchNavigation.find((section) => section.key === "agent");
  const agentWorkbenchActive = agentWorkbenchSection
    ? pathMatchesWorkbenchSection(agentWorkbenchSection.path, pathnameResolved)
    : false;
  const agentNavSectionLabel = "对话";
  const agentNavLabel = agentWorkbenchSection?.label;
  const agentNavBadgeLabel = agentWorkbenchSection?.readinessLabel;
  const agentNavHint = "直接提问";
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
  /** 固定前七项，避免切换路由后页签位置变化；当前页在溢出区时由「更多」承接高亮。 */
  const inlineSubnavSections = currentGroupSections.slice(0, SUBNAV_MAX_INLINE);
  const inlineSubnavKeys = new Set(inlineSubnavSections.map((section) => section.key));
  const overflowSubnavSections = currentGroupSections.filter(
    (section) => !inlineSubnavKeys.has(section.key),
  );
  const activeSubnavInOverflow = overflowSubnavSections.some((section) =>
    pathMatchesWorkbenchSection(section.path, pathnameResolved),
  );
  const plannedWorkbenchNavigation = secondaryWorkbenchNavigation.filter(
    (section) => section.key !== "agent",
  );
  const isModuleHomePage = MODULE_HOME_SECTION_KEYS.includes(currentSection.key);
  const isPortfolioHomeShell =
    currentSection.key === "portfolio-home" &&
    pathnameResolved.replace(/\/+$/, "") === currentSection.path;
  const isPortfolioGroup = currentGroup?.key === "portfolio";
  const isDashboardCockpitShell = DASHBOARD_COCKPIT_SECTION_KEYS.includes(
    currentSection.key,
  );
  const useInstitutionalConsoleShell = INSTITUTIONAL_CONSOLE_SECTION_KEYS.includes(
    currentSection.key,
  );
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
  const showShellTerminalBar = pathnameResolved !== "/market-overview" && !TERMINAL_BAR_EXCLUDED_SECTION_KEYS.includes(
    currentSection.key,
  );
  /* 2026-09-02 铬件统一：凡渲染终端条的路由都带行情带（组合首页此前单独抑制，切页时行情带忽隐忽现）。 */
  const showShellMarketTicker = showShellTerminalBar;
  const isBalanceMovementAnalysisCompactChrome =
    currentSection.key === "balance-movement-analysis";
  /** 负债结构分析页以页面正文为主，不显示组合导读 Hero / 阅读路径占位。 */
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
    currentSection.key === "agent" ||
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
    currentSection.key !== "agent" &&
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

  function closeMobileNavigationAndRestoreFocus() {
    setMobileNavOpen(false);
    window.setTimeout(() => mobileNavToggleRef.current?.focus(), 0);
  }

  function onRailClick(event: MouseEvent<HTMLElement>) {
    if (
      mobileNavOpen
      && event.target instanceof Element
      && event.target.closest("a")
    ) {
      closeMobileNavigationAndRestoreFocus();
    }
  }

  const governanceNotice = currentSection.governanceStatus === "temporary-exception" ? (
    <section
      ref={governanceNoticeRef}
      data-testid="workbench-governance-pill"
      className="workbench-governance-pill"
    >
      <button
        ref={governanceToggleRef}
        type="button"
        className="workbench-governance-pill__toggle"
        aria-expanded={governanceDetailOpen}
        aria-controls="workbench-governance-pill-detail"
        onClick={() => {
          setSubnavMoreOpen(false);
          setGovernanceDetailOpen((open) => !open);
        }}
      >
        <span className="workbench-governance-pill__dot" aria-hidden="true" />
        <span>使用说明</span>
        <span aria-hidden="true">{governanceDetailOpen ? "▴" : "▾"}</span>
      </button>
      {governanceDetailOpen ? (
        <div
          id="workbench-governance-pill-detail"
          data-testid="workbench-governance-detail"
          className="workbench-governance-pill__detail"
        >
          <div className="workbench-governance-pill__detail-title">本页使用范围</div>
          <p className="workbench-governance-pill__detail-body">
            {currentSection.usageNote ?? "请以本页标注的数据日期、口径和使用范围为准。"}
          </p>
          <details data-testid="workbench-governance-diagnostics">
            <summary>技术诊断</summary>
            {currentSection.governanceBanner ? (
              <p className="workbench-governance-pill__detail-body">
                {currentSection.governanceBanner}
              </p>
            ) : null}
            <p className="workbench-governance-pill__detail-body">
              {currentSection.readinessNote}
            </p>
            <p className="workbench-governance-pill__detail-hint">
              第一阶段仅在页面契约收口期间保留该路由可见；不要把它视为已完全治理的页面。
            </p>
          </details>
        </div>
      ) : null}
    </section>
  ) : null;

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
      }${isPortfolioHomeShell ? " workbench-shell-grid--portfolio-home" : ""
      }${isBondAnalysisMinimalShell ? " workbench-shell-grid--bond-analysis" : ""}${
        isStockAnalysisShell ? " workbench-shell-grid--stock-analysis" : ""
      }${isLedgerPnlShell ? " workbench-shell-grid--ledger-pnl" : ""
      }${isProductCategoryPnlShell ? " workbench-shell-grid--product-category-pnl" : ""
      }${isPnlAttributionShell ? " workbench-shell-grid--pnl-attribution" : ""
      }${isCrossAssetImmersiveMain ? " workbench-shell-grid--cross-asset" : ""
      }${isBalanceMovementAnalysisCompactChrome ? " workbench-shell-grid--balance-movement" : ""
      }${pathnameResolved === "/market-overview" ? " workbench-shell-grid--market-overview" : ""
      }${isPublicationCaptureMode ? " workbench-shell-root--publication-capture" : ""
      }`}
    >
      <div className="workbench-shell-mobile-nav-bar">
        <button
          ref={mobileNavToggleRef}
          type="button"
          className="workbench-shell-mobile-nav-toggle"
          aria-controls="workbench-primary-navigation"
          aria-expanded={mobileNavOpen}
          aria-label={mobileNavOpen ? "关闭主导航" : "打开主导航"}
          onClick={() => {
            if (mobileNavOpen) {
              closeMobileNavigationAndRestoreFocus();
            } else {
              setMobileNavOpen(true);
            }
          }}
        >
          <LightIcon name="unordered-list" />
        </button>
        <div className="workbench-shell-mobile-nav-context">
          <span>{currentGroup?.label ?? "MOSS 工作台"}</span>
          <strong>{currentSection.label}</strong>
        </div>
      </div>

      <aside
        ref={mobileNavDrawerRef}
        id="workbench-primary-navigation"
        aria-label="全局工作台导航"
        data-mobile-nav-open={mobileNavOpen ? "true" : "false"}
        className={`workbench-shell-aside workbench-shell-rail${
          isMinimalMainChrome ? " workbench-shell-rail--minimal" : ""
        }`}
        onClick={onRailClick}
      >
        <button
          ref={mobileNavCloseRef}
          type="button"
          className="workbench-shell-mobile-nav-close"
          aria-label="关闭主导航"
          onClick={closeMobileNavigationAndRestoreFocus}
        >
          <span aria-hidden="true">×</span>
        </button>
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
            {primaryWorkbenchNavigationGroups.map((group) => ({
                  key: group.key,
                  label: group.label,
                  icon: group.icon,
                  defaultPath: group.defaultPath,
                  // agent（MOSS Chat）在专属「对话」导航区单独承接高亮，
                  // 不再点亮其归属的工作台分组，避免 /agent 双高亮。
                  active:
                    currentGroup && currentSection.key !== "agent"
                      ? group.key === currentGroup.key
                      : false,
                  countLabel: "首页",
                })).map((item) => {
              const active = item.active;

              return (
                <NavLink
                  key={item.key}
                  to={item.defaultPath}
                  aria-label={item.label}
                  title={item.label}
                  className="workbench-shell-group-link"
                  data-active={active ? "true" : "false"}
                >
                  <span className="workbench-shell-group-icon">
                    {iconMap[item.icon]}
                  </span>
                  <span className="workbench-shell-group-label">
                    {item.label}
                  </span>
                  <span className="workbench-shell-group-count">
                    {item.countLabel}
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

        {plannedWorkbenchNavigation.length > 0 ? (
          <section
            className="workbench-shell-rail-section workbench-shell-rail-section--gap-6"
          >
            <span className="workbench-shell-section-label workbench-shell-section-label--rail">
              规划入口
            </span>
            {plannedWorkbenchNavigation.map((item) => {
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
            const active = pathnameResolved === item.to;

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
          <div
            className="workbench-shell-support-unavailable"
            aria-disabled="true"
            title="帮助文档尚未接入，当前不会跳转"
          >
            <span className="workbench-shell-support-icon">
              {unavailableShellSupportEntry.icon}
            </span>
            <span className="workbench-shell-support-label">
              {unavailableShellSupportEntry.label}
            </span>
            <span className="workbench-shell-support-availability">
              {unavailableShellSupportEntry.availabilityLabel}
            </span>
          </div>
        </section>
      </aside>

      <button
        type="button"
        className="workbench-shell-mobile-nav-backdrop"
        aria-label="关闭主导航"
        hidden={!mobileNavOpen}
        tabIndex={-1}
        onClick={closeMobileNavigationAndRestoreFocus}
      />

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
              {/*
               * 终端条不再重复页面 h1（每个 live 路由都自带页标题行），改为「组 › 页」面包屑：
               * 2026-09-02 铬件统一后 12 个原本抑制终端条的页面若再叠一个 30px 大标题，
               * 会与页头 h1 在 100px 内出现两次同名标题。
               */}
              <div className="workbench-page-title-display" data-variant="crumb">
                {currentGroup && currentGroup.label !== currentSection.label ? (
                  <>
                    <span className="workbench-page-crumb-group">{currentGroup.label}</span>
                    <span className="workbench-page-crumb-sep" aria-hidden="true">
                      ›
                    </span>
                  </>
                ) : null}
                <span className="workbench-page-crumb-current">{currentSection.label}</span>
              </div>
              {explicitReportDate ? (
                <span className="workbench-shell-report-chip">
                  {"\u62a5\u544a\u65e5"} {explicitReportDate}
                </span>
              ) : null}
            </section>

            <section
              data-testid="workbench-operator-zone"
              className="workbench-operator-zone-shell"
            >
              {governanceNotice}
              {shellSupportEntries
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
            <Suspense
              fallback={
                // data-testid 必须与真实行情带一致：workbenchShell.css 里
                // `[data-testid="workbench-market-ticker"]` 的 order/flex-basis
                // 几何规则按该属性选择器匹配，占位用不同 testid 会导致占位期
                // order 退回默认值 0（插到 page-context 前面），行情带 chunk
                // 到达后再跳回 order:2，引发比“只是高度变化”更大的整行重排。
                <section
                  className="workbench-market-ticker-shell"
                  aria-hidden="true"
                  data-testid="workbench-market-ticker"
                  data-shell-market-ticker-placeholder="true"
                />
              }
            >
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
                  ，再查看损益、持仓与归因，结合各页使用范围复核。
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
                      当前工作台汇总 {currentGroup?.label ?? ""} 信息。先查看资产负债和损益，再按需要查看结构、持仓与归因；各项结果的适用范围以页面说明为准。
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
                        detail: "先核对结果，再查看原因解释",
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
                      阅读路径
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
                            {item.section.label} · {item.section.usageNote ?? "请查看页面标注的数据日期和使用范围。"}
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
                    从当前可用的分析页面开始
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
                    {currentSection.usageNote ?? "请查看页面标注的数据日期和使用范围。"}
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
              <nav
                aria-label={`${currentGroup.label}页面`}
                className="workbench-section-subnav__links"
              >
                {inlineSubnavSections.map((section) => {
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
              </nav>

              {overflowSubnavSections.length > 0 ? (
                <div className="workbench-section-subnav__more" ref={subnavMoreRef}>
                  <button
                    ref={subnavMoreToggleRef}
                    type="button"
                    className="workbench-section-subnav__more-toggle"
                    aria-expanded={subnavMoreOpen}
                    aria-controls="workbench-section-subnav-more-menu"
                    aria-label={
                      activeSubnavInOverflow
                        ? `更多工作台页面，当前页 ${currentSection.label}`
                        : "更多工作台页面"
                    }
                    data-active={activeSubnavInOverflow ? "true" : "false"}
                    onClick={() => {
                      setGovernanceDetailOpen(false);
                      setSubnavMoreOpen((open) => !open);
                    }}
                  >
                    <span>更多</span>
                    <span aria-hidden="true">{subnavMoreOpen ? "▴" : "▾"}</span>
                  </button>
                  {subnavMoreOpen ? (
                    <nav
                      id="workbench-section-subnav-more-menu"
                      data-testid="workbench-section-subnav-more-menu"
                      aria-label="更多工作台页面"
                      className="workbench-section-subnav__more-menu"
                    >
                      {overflowSubnavSections.map((section) => {
                        const active = pathMatchesWorkbenchSection(
                          section.path,
                          pathnameResolved,
                        );

                        return (
                          <NavLink
                            key={section.key}
                            to={section.path}
                            className="workbench-section-subnav__more-link"
                            data-active={active ? "true" : "false"}
                            onClick={() => setSubnavMoreOpen(false)}
                          >
                            <span className="workbench-section-subnav__icon">
                              {iconMap[section.icon]}
                            </span>
                            <span>{section.label}</span>
                          </NavLink>
                        );
                      })}
                    </nav>
                  ) : null}
                </div>
              ) : null}
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
                  ? "该功能暂未开放"
                  : "该功能暂不可用"}
              </div>
              <div className="workbench-notice__body">
                {currentSection.usageNote ?? "请从工作台选择其他可用页面。"}
              </div>
              <div className="workbench-notice__hint">
                可通过工作台导航继续查看其他分析。
              </div>
              <details>
                <summary>技术诊断</summary>
                <p>{currentSection.readinessNote}</p>
              </details>
            </section>
          ) : null}

          {!showShellTerminalBar ? governanceNotice : null}

          {currentSection.usageRestriction ? (
            <p
              data-testid="workbench-usage-restriction"
              className="workbench-governance-pill__detail-body"
            >
              {currentSection.usageRestriction}
            </p>
          ) : null}

          <Outlet />
        </main>
      </div>
    </div>
    </>
  );
}
