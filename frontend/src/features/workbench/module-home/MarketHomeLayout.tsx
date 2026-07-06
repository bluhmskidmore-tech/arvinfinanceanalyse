import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ReloadOutlined } from "@ant-design/icons";
import { Collapse, Tabs } from "antd";

import dhStyles from "../dashboard-home/dashboardHome.module.css";
import type { ModuleHomeDetailPanel, ModuleHomeDetailRow, ModuleHomeTone, ModuleHomeView } from "./moduleHomeModel";
import { buildMarketCurveSpreadRows } from "./moduleHomeModel";
import type { ModuleWorkbenchHomeConfig } from "./moduleHomeConfig";
import { MarketActionQueue } from "./MarketActionQueue";
import { MarketCrossAssetBars } from "./MarketCrossAssetBars";
import { MarketCrisisExplainBand } from "./MarketCrisisExplainBand";
import { MarketCurveSpreadBand } from "./MarketCurveSpreadBand";
import { MarketDeskIntelStrip } from "./MarketDeskIntelStrip";
import { MarketDepthPanel } from "./MarketDepthPanel";
import { MarketDecisionMatrix } from "./MarketDecisionMatrix";
import { MarketMacroTickerBar } from "./MarketMacroTickerBar";
import { MARKET_KPI_ACCENT } from "./marketEvidenceVisual";
import { marketChangePresentation, resolveMarketChangeDirection } from "./marketHomeChangeTone";
import { MarketHomeKpiSparkline } from "./MarketHomeKpiSparkline";
import { marketDrillIconLabel } from "./marketHomeDrillIcon";
import { MarketIconYieldCurve } from "./marketHomeIcons";
import MarketMacroToolkitSection from "./MarketMacroToolkitSection";
import { MarketStructureTabPanel } from "./MarketStructureTabPanel";
import marketStyles from "./marketHome.module.css";
import { marketDataPageHref } from "../../market-data/components/marketDataDeskBridgeLinks";

const MARKET_CHANGE_CLASSES = {
  up: dhStyles.dhUpRed,
  down: dhStyles.dhDownGreen,
  neutral: dhStyles.dhMuted,
} as const;

const MARKET_AUDIT_TABS = [
  { key: "formal-rate-series", label: "正式利率序列" },
  { key: "catalog-overview", label: "数据目录" },
  { key: "latest-macro-snapshot", label: "跨资产快讯" },
] as const;

const DETAIL_PANEL_TEST_IDS: Record<string, string> = {
  "yield-curve-quotes": "module-home-yield-curve",
  "latest-macro-snapshot": "module-home-macro-snapshot",
  "formal-rate-series": "module-home-formal-rates",
  "catalog-overview": "module-home-catalog-summary",
  "news-events-snapshot": "module-home-news-events",
};

const THESIS_BRIEFING_TITLES = ["利率快照", "跨资产传导", "事件状态"] as const;

const SPREAD_KPI_KEYS = ["term-spread-10y-2y", "term-spread-10y-1y", "term-spread-10y-5y"] as const;

function panelByKey(panels: ModuleHomeView["detailPanels"], key: string) {
  return panels?.find((panel) => panel.key === key);
}

function toneClass(tone: ModuleHomeTone) {
  if (tone === "watch") return dhStyles.dhMuted;
  if (tone === "error") return dhStyles.dhUpRed;
  return "";
}

function changeDirectionClass(detail: string | undefined, sparkline: readonly number[] | undefined) {
  return marketChangePresentation(detail, sparkline, MARKET_CHANGE_CLASSES).className;
}

function marketStatusDotClass(tone: ModuleHomeTone) {
  if (tone === "error") return dhStyles.dhDotOrange;
  if (tone === "watch" || tone === "muted") return dhStyles.dhDotOrange;
  return dhStyles.dhDotGreen;
}

function evidenceSegments(value: string | undefined) {
  const text = value?.trim();
  if (!text || text === "-") return [];
  return text.match(/[^；;。]+[；;。]?/g)?.map((part) => part.trim()).filter(Boolean) ?? [text];
}

function sourceSegments(value: string | undefined) {
  return value?.split(/\s+\/\s+/).map((part) => part.trim()).filter(Boolean) ?? [];
}

function compactMarketParts(parts: Array<string | undefined | null>) {
  return parts.map((part) => part?.trim()).filter((part): part is string => Boolean(part && part !== "-"));
}

type MarketFocusReading = {
  key: string;
  bucket: string;
  label: string;
  value: string;
  detail: string;
  tone: ModuleHomeTone;
  sparkline?: readonly number[];
};

type MarketDetailPanel = NonNullable<ModuleHomeView["detailPanels"]>[number];

function findMarketRow(panel: MarketDetailPanel | undefined, patterns: string[]) {
  return panel?.rows.find((row) => patterns.some((pattern) => `${row.key} ${row.label} ${row.source}`.includes(pattern)));
}

function rowByKey(panel: ModuleHomeDetailPanel, key: string) {
  return panel.rows.find((row) => row.key === key);
}

function MacroOverviewEvidenceItem({ row }: { row: ModuleHomeDetailRow }) {
  return (
    <div className={marketStyles.macroOverviewEvidenceItem}>
      <span>{row.label}</span>
      <strong className={toneClass(row.tone)}>{row.value}</strong>
    </div>
  );
}

function MarketMacroOverviewCard({ panel }: { panel: ModuleHomeDetailPanel }) {
  const stanceRow = rowByKey(panel, "macro-stance");
  const summaryRow = rowByKey(panel, "macro-summary");
  const actionRow = rowByKey(panel, "macro-action");
  const evidenceRows = [rowByKey(panel, "macro-hit-rate"), rowByKey(panel, "macro-scripts")].filter(
    (row): row is ModuleHomeDetailRow => Boolean(row),
  );
  const dateRow = panel.rows.find((row) => row.tradeDate && row.tradeDate !== "-");
  const sourceRows = Array.from(
    new Set(panel.rows.map((row) => row.source).filter((source) => source && source !== "-")),
  );

  return (
    <article
      className={`${marketStyles.marketDeskPanel} ${marketStyles.macroOverviewCard}`}
      data-testid="module-home-macro-overview-depth"
    >
      <div className={dhStyles.dhSectionTitle}>
        <span>{panel.title}</span>
        <span className={marketStyles.marketStatusOutline}>{panel.stateLabel}</span>
      </div>
      <p className={marketStyles.panelMeta}>{panel.meta}</p>
      <div className={marketStyles.macroOverviewBody}>
        <div className={marketStyles.macroOverviewMain}>
          <span className={marketStyles.macroOverviewLabel}>{stanceRow?.label ?? "工具立场"}</span>
          <strong className={`${marketStyles.macroOverviewStance} ${toneClass(stanceRow?.tone ?? panel.tone)}`}>
            {stanceRow?.value ?? panel.stateLabel}
          </strong>
          {summaryRow ? (
            <p className={marketStyles.macroOverviewSummary}>
              <span>{summaryRow.label}</span>
              {summaryRow.value}
            </p>
          ) : null}
        </div>
        {actionRow ? (
          <div className={marketStyles.macroOverviewAction}>
            <span>{actionRow.label}</span>
            <strong className={toneClass(actionRow.tone)}>{actionRow.value}</strong>
          </div>
        ) : null}
        {evidenceRows.length > 0 ? (
          <div className={marketStyles.macroOverviewEvidenceGrid}>
            {evidenceRows.map((row) => (
              <MacroOverviewEvidenceItem row={row} key={row.key} />
            ))}
          </div>
        ) : null}
        <div className={marketStyles.macroOverviewTrace}>
          {dateRow ? <span>数据日期 {dateRow.tradeDate}</span> : null}
          {sourceRows.length > 0 ? <span>来源 {sourceRows.join(" / ")}</span> : null}
        </div>
      </div>
    </article>
  );
}

function marketCue(rateParts: string[], crossAssetLabel: string | undefined) {
  const crossAssetText = crossAssetLabel ?? "跨资产信号";
  if (rateParts.length === 0) {
    return `先确认利率与流动性信号是否已返回，再看${crossAssetText}对债市判断的传导。`;
  }
  return `先确认 ${rateParts.join(" 与 ")}，再看${crossAssetText}对债市判断的传导。`;
}

function focusReadingFromRow(
  key: string,
  bucket: string,
  row: ModuleHomeDetailRow | undefined,
  fallbackLabel: string,
  fallbackTone: ModuleHomeTone,
): MarketFocusReading {
  return {
    key,
    bucket,
    label: row?.label ?? fallbackLabel,
    value: row?.value ?? "待返回",
    detail: compactMarketParts([row?.detail, row?.tradeDate]).join(" / ") || "待下钻核验",
    tone: row?.tone ?? fallbackTone,
    sparkline: row?.sparkline,
  };
}

type MarketHomeLayoutProps = {
  view: ModuleHomeView;
  config: ModuleWorkbenchHomeConfig;
  latestTradeDate: string;
  formalTradeDate: string;
  isRefreshing: boolean;
  refreshStatus: string;
  refreshError: string;
  onRefreshData: () => void;
};

export default function MarketHomeLayout({
  view,
  config,
  latestTradeDate,
  formalTradeDate,
  isRefreshing,
  refreshStatus,
  refreshError,
  onRefreshData,
}: MarketHomeLayoutProps) {
  const stateTone: ModuleHomeTone =
    view.stateLabel === "读取失败"
      ? "error"
      : view.stateLabel === "部分失败"
        ? "watch"
        : view.stateLabel === "读取中"
          ? "muted"
          : "ok";

  const primaryBriefing = view.briefings[0];
  const thesisBriefingCards = THESIS_BRIEFING_TITLES.map((title) => view.briefings.find((item) => item.title === title)).filter(
    (item): item is NonNullable<typeof item> => Boolean(item),
  );
  const keyRatePanel = panelByKey(view.detailPanels, "key-rate-snapshot");
  const yieldCurvePanel = panelByKey(view.detailPanels, "yield-curve-quotes");
  const macroPanel = panelByKey(view.detailPanels, "latest-macro-snapshot");
  const formalPanel = panelByKey(view.detailPanels, "formal-rate-series");
  const catalogPanel = panelByKey(view.detailPanels, "catalog-overview");
  const macroOverviewPanel = panelByKey(view.detailPanels, "macro-toolkit-overview");
  const macroSignalPanel = panelByKey(view.detailPanels, "macro-toolkit-signals");
  const macroCapabilityPanel = panelByKey(view.detailPanels, "macro-toolkit-capabilities");
  const macroIndicatorPanel = panelByKey(view.detailPanels, "macro-toolkit-indicators");
  const macroStrategyPanel = panelByKey(view.detailPanels, "macro-toolkit-strategies");
  const macroAShareRiskPanel = panelByKey(view.detailPanels, "macro-toolkit-a-share-risk");
  const macroHasonPanel = panelByKey(view.detailPanels, "macro-toolkit-hason");
  const macroShadowPanel = panelByKey(view.detailPanels, "macro-toolkit-shadow");
  const macroRuntimePanel = panelByKey(view.detailPanels, "macro-toolkit-runtime");
  const newsEventsPanel = panelByKey(view.detailPanels, "news-events-snapshot");
  const spreadRows = useMemo(
    () =>
      SPREAD_KPI_KEYS.map((key) => keyRatePanel?.rows.find((row) => row.key === key)).filter(
        (row): row is ModuleHomeDetailRow => Boolean(row),
      ),
    [keyRatePanel],
  );
  const { termSpreadRows, creditSpreadRow } = buildMarketCurveSpreadRows(keyRatePanel);
  const spreadLinkageKeys = useMemo(() => {
    const keys = termSpreadRows.map((row) => row.key);
    if (creditSpreadRow) {
      keys.push(creditSpreadRow.key);
    }
    return keys;
  }, [creditSpreadRow, termSpreadRows]);
  const [linkedSpreadKey, setLinkedSpreadKey] = useState<string | null>(null);
  const activeSpreadKeys = linkedSpreadKey ? [linkedSpreadKey] : [];
  const isMarketTerminalDefaultEmpty = formalPanel
    ? formalPanel.rows.length === 0 && (!formalPanel.chart || formalPanel.chart.categories.length === 0)
    : false;
  const tenYearRow = findMarketRow(keyRatePanel, ["10Y", "10年", "十年", "gov-10y"]);
  const liquidityRow = findMarketRow(keyRatePanel, ["DR007", "SHIBOR", "shibor", "dr007"]);
  const csiRow = findMarketRow(macroPanel, ["沪深300", "CSI300", "csi300", "hs300"]);
  const csiChangeRow = findMarketRow(macroPanel, ["PCT_CHG", "涨跌幅"]);
  const offshoreRow = findMarketRow(macroPanel, ["USD/CNY", "USDCNY", "Brent", "原油", "汇率"]);
  const aShareRiskRow = macroAShareRiskPanel?.rows[0];
  const explicitMacroStanceRow = macroOverviewPanel ? rowByKey(macroOverviewPanel, "macro-stance") : undefined;
  const macroStanceRow =
    explicitMacroStanceRow ??
    macroOverviewPanel?.rows.find((row) => row.key.includes("stance") || row.label.includes("结论")) ??
    macroOverviewPanel?.rows[0];
  const sourceScopeSegments = sourceSegments(view.sourceScope);
  const visibleSourceScope =
    sourceScopeSegments.length > 0 ? sourceScopeSegments.slice(0, 3).join(" / ") : view.sourceScope;
  const marketDataHref = marketDataPageHref("/market-data", latestTradeDate);
  const refreshFeedback = refreshError || refreshStatus || "同步 Choice 宏观与市场快照";
  const refreshFeedbackTone = refreshError ? "error" : refreshStatus ? "ok" : "muted";
  const marketJudgementCue = marketCue(
    compactMarketParts([tenYearRow ? "10Y" : null, liquidityRow?.label]),
    csiRow?.label,
  );
  const marketKpis = useMemo(
    () => [
      {
        key: "ten-year",
        label: "10Y国债",
        value: tenYearRow?.value ?? "待返回",
        detail: compactMarketParts([tenYearRow?.detail, tenYearRow?.tradeDate]).join(" / "),
        tone: tenYearRow?.tone ?? keyRatePanel?.tone ?? "muted",
        sparkline: tenYearRow?.sparkline,
      },
      {
        key: "liquidity",
        label: liquidityRow?.label ?? "DR007",
        value: liquidityRow?.value ?? "待返回",
        detail: compactMarketParts([liquidityRow?.detail, liquidityRow?.tradeDate]).join(" / "),
        tone: liquidityRow?.tone ?? keyRatePanel?.tone ?? "muted",
        sparkline: liquidityRow?.sparkline,
      },
      {
        key: "equity",
        label: csiRow?.label ?? "沪深300",
        value: csiRow?.value ?? "待返回",
        detail: compactMarketParts([csiRow?.detail, csiRow?.tradeDate]).join(" / "),
        tone: csiRow?.tone ?? macroPanel?.tone ?? "muted",
        sparkline: csiRow?.sparkline ?? csiChangeRow?.sparkline,
      },
      {
        key: "macro",
        label: "宏观立场",
        value: macroStanceRow?.value ?? "观察",
        detail: compactMarketParts([macroStanceRow?.detail, macroStanceRow?.tradeDate]).join(" / "),
        tone: macroStanceRow?.tone ?? macroOverviewPanel?.tone ?? "muted",
        sparkline: undefined,
      },
      ...(spreadRows.map((row) => ({
        key: row.key,
        label: row.label,
        value: row.value,
        detail: compactMarketParts([row.detail, row.tradeDate]).join(" / "),
        tone: row.tone,
        sparkline: row.sparkline,
      }))),
      ...(aShareRiskRow
        ? [
            {
              key: "a-share-risk",
              label: aShareRiskRow.label,
              value: aShareRiskRow.value,
              detail: compactMarketParts([aShareRiskRow.detail, aShareRiskRow.tradeDate]).join(" / "),
              tone: aShareRiskRow.tone,
              sparkline: aShareRiskRow.sparkline,
            },
          ]
        : []),
    ],
    [
      aShareRiskRow,
      csiChangeRow,
      csiRow,
      keyRatePanel?.tone,
      liquidityRow,
      macroOverviewPanel?.tone,
      macroPanel?.tone,
      macroStanceRow,
      spreadRows,
      tenYearRow,
    ],
  );
  const newsHeadlineRows =
    newsEventsPanel?.rows.filter((row) => row.key.startsWith("news-event-")).slice(0, 5) ?? [];
  const marketFocusReadings: MarketFocusReading[] = [
    ...spreadRows.map((row) => focusReadingFromRow(row.key, "利差", row, row.label, row.tone)),
    focusReadingFromRow("rates", "利率", tenYearRow, "10Y国债", keyRatePanel?.tone ?? "muted"),
    focusReadingFromRow("liquidity", "资金", liquidityRow, "DR007", keyRatePanel?.tone ?? "muted"),
    focusReadingFromRow("equity", "股债", csiRow, "沪深300", macroPanel?.tone ?? "muted"),
    focusReadingFromRow("equity-change", "异动", csiChangeRow, "沪深300涨跌幅", macroPanel?.tone ?? "muted"),
    focusReadingFromRow("offshore", "外围", offshoreRow, "汇率/商品", macroPanel?.tone ?? "muted"),
    focusReadingFromRow("macro", "宏观", macroStanceRow, "工具立场", macroOverviewPanel?.tone ?? "muted"),
  ];

  const auditTabItems = useMemo(() => {
    const map = new Map(view.detailPanels?.map((panel) => [panel.key, panel]) ?? []);
    return MARKET_AUDIT_TABS.map((tab) => {
      const panel = map.get(tab.key);
      return {
        key: tab.key,
        label: tab.label,
        children: panel ? (
          <div data-testid={DETAIL_PANEL_TEST_IDS[tab.key]}>
            <MarketStructureTabPanel panel={panel} />
          </div>
        ) : (
          <p className={marketStyles.panelEmpty}>暂无数据</p>
        ),
      };
    });
  }, [view.detailPanels]);

  const auditFooterItems = useMemo(
    () => [
      {
        key: "audit",
        forceRender: true,
        label: (
          <span className={marketStyles.marketAuditFooterLabel}>
            数据核验与下钻
            <em>
              行情 {latestTradeDate || "—"} · 正式序列 {formalTradeDate || "—"} · {view.stateLabel}
            </em>
          </span>
        ),
        children: (
          <div className={marketStyles.marketAuditFooterBody}>
            <aside data-testid="module-home-market-evidence-rail" className={marketStyles.evidenceRail}>
              <div className={marketStyles.evidenceRailHeader}>
                <span>市场快照</span>
                <strong data-tone={stateTone}>{view.stateLabel}</strong>
              </div>
              <p className={marketStyles.evidenceRailState} data-testid="module-home-market-evidence-rail-state">
                行情 {latestTradeDate || "—"}，正式序列 {formalTradeDate || "—"}；{view.stateLabel}。
              </p>
              <dl className={marketStyles.evidenceRailDateStack} data-testid="module-home-market-evidence-rail-date-stack">
                <div>
                  <dt>最新行情</dt>
                  <dd className={dhStyles.dhNum}>{latestTradeDate || "—"}</dd>
                </div>
                <div>
                  <dt>正式序列</dt>
                  <dd className={dhStyles.dhNum}>{formalTradeDate || "—"}</dd>
                </div>
                <div>
                  <dt>来源范围</dt>
                  <dd>{visibleSourceScope}</dd>
                </div>
              </dl>
              <div className={marketStyles.evidenceRailScrollBlock} data-testid="module-home-market-evidence-rail-metrics-scroll">
                <div
                  aria-label="市场快照指标"
                  className={marketStyles.evidenceRailMetricGrid}
                  data-testid="module-home-market-evidence-rail-metrics"
                  role="region"
                  tabIndex={0}
                >
                  {marketKpis.map((item) => {
                    const change = marketChangePresentation(item.detail, item.sparkline, MARKET_CHANGE_CLASSES);
                    return (
                      <div className={marketStyles.evidenceRailMetric} data-tone={item.tone} key={item.key}>
                        <span>{item.label}</span>
                        <strong className={`${dhStyles.dhNum} ${marketStyles.marketMetricNum}`}>{item.value}</strong>
                        {item.detail ? (
                          <em
                            className={`${dhStyles.dhNum} ${marketStyles.evidenceRailMetricDetail} ${change.className}`}
                            data-testid={`module-home-market-evidence-rail-${item.key}`}
                            data-change={change.direction ?? "flat"}
                          >
                            {item.detail}
                          </em>
                        ) : null}
                      </div>
                    );
                  })}
                </div>
              </div>
              <section className={marketStyles.evidenceRailCard} data-testid="module-home-market-audit-status" data-tone={stateTone}>
                <span className={marketStyles.evidenceRailLabel}>读链路状态</span>
                <div className={marketStyles.evidenceRailStatusList}>
                  {view.statuses.slice(0, 4).map((item) => (
                    <span data-tone={item.tone} key={item.key}>
                      <b>{item.label}</b>
                      <em>{item.value || item.detail || "待返回"}</em>
                    </span>
                  ))}
                </div>
              </section>
              <div className={marketStyles.evidenceRailScrollBlock} data-testid="module-home-market-evidence-rail-actions-scroll">
                <nav aria-label="市场模块入口" className={marketStyles.evidenceRailActionList}>
                  <Link to={marketDataHref} className={marketStyles.evidenceRailLink}>市场数据</Link>
                  <button
                    type="button"
                    className={`${marketStyles.evidenceRailLink} ${marketStyles.evidenceRailRefreshButton}`}
                    data-testid="module-home-market-evidence-refresh"
                    disabled={isRefreshing}
                    onClick={() => void onRefreshData()}
                  >
                    {isRefreshing ? "刷新中" : "刷新数据"}
                  </button>
                  <Link to="/macro-toolkit" className={marketStyles.evidenceRailLink}>宏观工具</Link>
                  <Link to="/cross-asset" className={marketStyles.evidenceRailLink}>跨资产</Link>
                </nav>
              </div>
            </aside>
            <section className={marketStyles.marketDepthZone} data-testid="module-home-market-depth-zone">
              <div className={dhStyles.dhSectionTitle}>
                <span>深度数据</span>
                <Link to={marketDataHref} className={dhStyles.dhLink}>完整市场数据 →</Link>
              </div>
              <div
                className={`${marketStyles.marketDeskPanel} ${marketStyles.terminalCard} ${marketStyles.marketAnalysisRates} ${isMarketTerminalDefaultEmpty ? marketStyles.marketCompactEmptyTerminal : ""}`}
                data-testid="module-home-market-terminal"
              >
                <div className={dhStyles.dhSectionTitle}><span>正式利率序列 / 目录 / 快讯</span></div>
                <Tabs defaultActiveKey="formal-rate-series" items={auditTabItems} />
              </div>
              <section className={marketStyles.marketDistributionGrid} data-testid="module-home-market-distribution-grid">
                {keyRatePanel && keyRatePanel.rows.length > 0 ? (
                  <MarketDepthPanel compact panel={keyRatePanel} testId="module-home-key-rate-depth" />
                ) : null}
                {macroOverviewPanel && macroOverviewPanel.rows.length > 0 ? (
                  <MarketMacroOverviewCard panel={macroOverviewPanel} />
                ) : null}
              </section>
              <MarketDecisionMatrix
                view={view}
                latestTradeDate={latestTradeDate}
                formalTradeDate={formalTradeDate}
                keyRatePanel={keyRatePanel}
                yieldCurvePanel={yieldCurvePanel}
                macroPanel={macroPanel}
                formalPanel={formalPanel}
                catalogPanel={catalogPanel}
                macroOverviewPanel={macroOverviewPanel}
              />
              <MarketMacroToolkitSection
                overviewPanel={macroOverviewPanel}
                signalPanel={macroSignalPanel}
                capabilityPanel={macroCapabilityPanel}
                indicatorPanel={macroIndicatorPanel}
                strategyPanel={macroStrategyPanel}
                aShareRiskPanel={macroAShareRiskPanel}
                hasonPanel={macroHasonPanel}
                shadowPanel={macroShadowPanel}
                runtimePanel={macroRuntimePanel}
              />
            </section>
          </div>
        ),
      },
    ],
    [
      auditTabItems,
      formalTradeDate,
      isRefreshing,
      isMarketTerminalDefaultEmpty,
      keyRatePanel,
      latestTradeDate,
      macroAShareRiskPanel,
      macroCapabilityPanel,
      macroHasonPanel,
      macroIndicatorPanel,
      macroOverviewPanel,
      macroPanel,
      macroRuntimePanel,
      macroShadowPanel,
      macroSignalPanel,
      macroStrategyPanel,
      marketDataHref,
      marketKpis,
      onRefreshData,
      stateTone,
      view,
      visibleSourceScope,
      yieldCurvePanel,
      catalogPanel,
      formalPanel,
    ],
  );

  const marketModuleDrilldowns = (
    <section className={marketStyles.marketBottomNavSection} data-testid="module-home-drilldowns">
      <nav aria-label="市场模块快捷导航" className={marketStyles.marketBottomNavBar} data-testid="module-home-market-bottom-nav" tabIndex={0}>
        {config.drilldowns.map((item) => {
          const isCurrentHome = item.key === "market-overview";
          return (
            <Link
              key={item.key}
              to={item.path}
              aria-current={isCurrentHome ? "page" : undefined}
              className={`${marketStyles.marketBottomNavItem} ${isCurrentHome ? marketStyles.marketBottomNavItemCurrent : ""}`}
              data-testid={`module-home-drill-${item.key}`}
              title={item.description}
            >
              <span aria-hidden="true" className={marketStyles.marketBottomNavIcon}>{marketDrillIconLabel(item.key)}</span>
              <b>{item.label}</b>
              <em>{isCurrentHome ? "当前首页" : item.statusLabel}</em>
            </Link>
          );
        })}
      </nav>
      {view.dataNote.lines.length > 0 ? (
        <p className={marketStyles.marketBottomNavNote} data-testid="module-home-data-note">{view.dataNote.lines.join(" ")}</p>
      ) : null}
    </section>
  );

  return (
    <>
      <header data-testid="module-home-toolbar" className={`${dhStyles.dhTopbar} ${marketStyles.marketTopbar}`}>
        <div className={`${dhStyles.dhTopbarLeft} ${marketStyles.marketTopbarLeft}`}>
          <div className={dhStyles.dhTitleBrand}><h1 className={dhStyles.dhTitle}>{view.title}</h1></div>
          <div className={marketStyles.topbarCopy}>
            <p className={marketStyles.topbarSummary}>{view.question}</p>
            <p className={marketStyles.topbarScope}>先看利率曲线与流动性，再看跨资产传导，必要时进入下钻复核。</p>
          </div>
        </div>
        <div className={`${dhStyles.dhTopbarRight} ${marketStyles.marketTopbarMeta}`} data-testid="module-home-market-topbar-audit-meta">
          <div className={marketStyles.marketTopbarRefresh} data-testid="module-home-market-refresh-panel">
            <button
              type="button"
              className={marketStyles.marketRefreshButton}
              data-testid="module-home-market-refresh-button"
              disabled={isRefreshing}
              onClick={() => void onRefreshData()}
            >
              <ReloadOutlined aria-hidden />
              {isRefreshing ? "刷新中" : "刷新数据"}
            </button>
            <Link to={marketDataHref} className={marketStyles.marketRefreshSecondaryLink}>
              市场数据页
            </Link>
            <span
              className={marketStyles.marketRefreshFeedback}
              data-testid="module-home-market-refresh-feedback"
              data-tone={refreshFeedbackTone}
            >
              {refreshFeedback}
            </span>
          </div>
          <span className={marketStyles.marketStatusItem} data-tone={stateTone}>
            <i className={`${dhStyles.dhDot} ${marketStatusDotClass(stateTone)}`} aria-hidden="true" />
            {view.stateLabel}
          </span>
          <span className={marketStyles.topbarDateGroup}>
            <span className={dhStyles.dhDateLabel}>最新行情日</span>
            <span className={`${dhStyles.dhNum} ${marketStyles.topbarDate}`}>{latestTradeDate || "—"}</span>
          </span>
          <span className={marketStyles.topbarDateGroup}>
            <span className={dhStyles.dhDateLabel}>正式序列日</span>
            <span className={`${dhStyles.dhNum} ${marketStyles.topbarDate}`}>{formalTradeDate || "—"}</span>
          </span>
        </div>
      </header>
      <main className={`${dhStyles.dhMain} ${marketStyles.marketPageMain}`}>
        <section data-testid="module-home-market-cockpit" className={`${marketStyles.marketInstitutionalCockpit} ${marketStyles.marketCockpitCohesion}`}>
          <MarketMacroTickerBar keyRatePanel={keyRatePanel} macroPanel={macroPanel} macroOverviewPanel={macroOverviewPanel} />
          <section data-testid="module-home-market-primary-grid" className={marketStyles.marketHero}>
            <section data-testid="module-home-briefing" className={marketStyles.marketThesisSection}>
              {primaryBriefing ? (
                <article className={`${marketStyles.marketThesisHero} ${marketStyles.marketJudgementHero} ${marketStyles.marketDeskPanel}`}>
                  <span className={marketStyles.marketThesisKicker}>本日市场判断</span>
                  <h2>{macroStanceRow?.value ? `${macroStanceRow.value} · ${primaryBriefing.conclusion}` : primaryBriefing.conclusion}</h2>
                  <p className={marketStyles.marketHeroEvidence} data-testid="module-home-market-hero-evidence"><span>{marketJudgementCue}</span></p>
                  {thesisBriefingCards.length > 0 ? (
                    <div className={marketStyles.marketThesisBriefingGrid} data-testid="module-home-market-secondary-briefings">
                      {thesisBriefingCards.map((item) => (
                        <article className={marketStyles.marketThesisBriefingCard} data-tone={item.tone} key={item.title}>
                          <span className={marketStyles.marketThesisBriefingTitle}>{item.title}</span>
                          <p className={marketStyles.marketThesisBriefingBody}>{item.conclusion}</p>
                          <em className={marketStyles.marketThesisBriefingEvidence}>{item.evidence}</em>
                        </article>
                      ))}
                    </div>
                  ) : null}
                  <footer className={marketStyles.marketHeroMeta} data-testid="module-home-market-hero-meta">
                    <span>{view.stateDetail}</span>
                    <span>{primaryBriefing.evidence}</span>
                    <span className={marketStyles.marketHeroSources}>
                      {sourceScopeSegments.length > 0
                        ? sourceScopeSegments.map((part, index) => <em key={part}>{index > 0 ? ` / ${part}` : part}</em>)
                        : <em>{view.sourceScope}</em>}
                    </span>
                  </footer>
                </article>
              ) : null}
            </section>
            <div data-testid="module-home-kpi-strip" className={marketStyles.marketKpiBox}>
              {marketKpis.map((item) => {
                const changeDirection = resolveMarketChangeDirection(item.detail, item.sparkline);
                const isSpreadLinkedKpi = spreadLinkageKeys.includes(item.key);
                const isSpreadLinked = linkedSpreadKey === item.key;
                return (
                  <div
                    className={`${marketStyles.marketKpiTile} ${marketStyles.marketDeskPanel} ${MARKET_KPI_ACCENT[item.key] ? marketStyles[`marketAccent_${MARKET_KPI_ACCENT[item.key]}`] : ""} ${item.key === "a-share-risk" ? marketStyles.marketKpiHeroTile : ""} ${isSpreadLinkedKpi ? marketStyles.marketKpiSpreadTile : ""} ${isSpreadLinked ? marketStyles.marketKpiSpreadLinked : ""}`}
                    data-tone={item.tone}
                    data-spread-kpi={isSpreadLinkedKpi ? "true" : undefined}
                    data-linked-active={isSpreadLinked ? "true" : "false"}
                    key={item.key}
                    onMouseEnter={() => {
                      if (isSpreadLinkedKpi) {
                        setLinkedSpreadKey(item.key);
                      }
                    }}
                    onMouseLeave={() => {
                      if (isSpreadLinkedKpi && linkedSpreadKey === item.key) {
                        setLinkedSpreadKey(null);
                      }
                    }}
                  >
                    <div className={dhStyles.dhMetricLabel}>{item.label}</div>
                    <div className={marketStyles.marketKpiValueRow}>
                      <div className={`${dhStyles.dhMetricValue} ${dhStyles.dhNum} ${marketStyles.marketMetricNum} ${toneClass(item.tone)}`}>{item.value}</div>
                      {item.sparkline && item.sparkline.length >= 2 ? (
                        <MarketHomeKpiSparkline values={item.sparkline} tone={item.tone} changeDirection={changeDirection} />
                      ) : null}
                    </div>
                    <div className={dhStyles.dhChange}>
                      <span
                        className={`${changeDirectionClass(item.detail, item.sparkline)} ${marketStyles.marketMetricNum} ${marketStyles.marketKpiDetail}`}
                        data-testid={`module-home-market-kpi-${item.key}-detail`}
                        data-change={changeDirection ?? "flat"}
                      >
                        {evidenceSegments(item.detail).map((part) => <em key={part}>{part}</em>)}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
          <MarketCurveSpreadBand
            activeKeys={activeSpreadKeys}
            creditSpreadRow={creditSpreadRow}
            curveShapeLabel={view.marketDeskIntel?.curveShapeLabel}
            onSpreadHover={setLinkedSpreadKey}
            termSpreadRows={termSpreadRows}
          />
          <MarketDeskIntelStrip intel={view.marketDeskIntel} />
          {marketModuleDrilldowns}
          <section className={marketStyles.marketThreeColDepth} data-testid="module-home-market-analysis-grid">
            {yieldCurvePanel ? (
              <MarketDepthPanel
                chartHeight={200}
                className={marketStyles.marketAnalysisCurve}
                compactLadder
                hideLadderDates
                hideMetaDate
                hideChartTitle
                layout="chart-first"
                panel={yieldCurvePanel}
                shell={{ kicker: "CURVE", icon: MarketIconYieldCurve, accent: "navy" }}
                testId={DETAIL_PANEL_TEST_IDS[yieldCurvePanel.key]}
              />
            ) : null}
            {macroPanel ? (
              <MarketCrossAssetBars
                crisisExplain={view.marketCrisisExplain}
                depthCompact
                deskIntel={view.marketDeskIntel}
                liquidityRow={liquidityRow}
                panel={macroPanel}
                testId={DETAIL_PANEL_TEST_IDS[macroPanel.key]}
              />
            ) : null}
            <MarketMacroToolkitSection
              compact
              depthCompact
              overviewPanel={macroOverviewPanel}
              signalPanel={macroSignalPanel}
              capabilityPanel={macroCapabilityPanel}
              indicatorPanel={macroIndicatorPanel}
              strategyPanel={macroStrategyPanel}
              aShareRiskPanel={macroAShareRiskPanel}
              hasonPanel={macroHasonPanel}
              shadowPanel={macroShadowPanel}
              runtimePanel={macroRuntimePanel}
            />
          </section>
          <MarketCrisisExplainBand explain={view.marketCrisisExplain} />
          <section className={`${marketStyles.marketActionBand} ${marketStyles.marketDeskPanel}`} data-testid="module-home-market-morning-readout">
            <div className={marketStyles.marketActionBandHead}><span>晨会读盘</span><em>重点读数 + 下一步动作</em></div>
            {newsHeadlineRows.length > 0 || newsEventsPanel ? (
              <section className={marketStyles.marketNewsStrip} data-testid="module-home-news-events-strip">
                <div className={marketStyles.marketNewsStripHead}>
                  <span>新闻事件</span>
                  <Link to="/news-events" className={marketStyles.marketIbLink}>全部事件 →</Link>
                </div>
                {newsHeadlineRows.length > 0 ? (
                  <ul className={marketStyles.marketNewsStripList}>
                    {newsHeadlineRows.map((row) => (
                      <li data-testid={`module-home-news-headline-${row.key}`} key={row.key}>
                        <strong>{row.value}</strong>
                        <em>{compactMarketParts([row.tradeDate, row.source]).join(" · ")}</em>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className={marketStyles.panelEmpty}>{newsEventsPanel?.stateDetail ?? "新闻事件摘要待读取。"}</p>
                )}
              </section>
            ) : null}
            <section className={marketStyles.marketFocusTape} data-testid="module-home-market-focus">
              <div className={marketStyles.marketFocusGrid}>
                {marketFocusReadings.map((item) => {
                  const changeDirection = resolveMarketChangeDirection(item.detail, item.sparkline);
                  return (
                    <div className={marketStyles.marketFocusItem} data-testid={`module-home-market-focus-${item.key}`} data-tone={item.tone} key={item.key}>
                      <span className={marketStyles.marketFocusBucket}>{item.bucket}</span>
                      <strong className={`${dhStyles.dhNum} ${marketStyles.marketMetricNum}`}>{item.label} {item.value}</strong>
                      <em className={`${changeDirectionClass(item.detail, item.sparkline)} ${marketStyles.marketMetricNum}`} data-change={changeDirection ?? "flat"}>{item.detail}</em>
                    </div>
                  );
                })}
              </div>
            </section>
            <MarketActionQueue view={view} keyRatePanel={keyRatePanel} yieldCurvePanel={yieldCurvePanel} macroPanel={macroPanel} />
          </section>
          <Collapse bordered={false} className={marketStyles.marketAuditFooter} data-testid="module-home-market-audit-footer" items={auditFooterItems} />
        </section>
      </main>
    </>
  );
}
