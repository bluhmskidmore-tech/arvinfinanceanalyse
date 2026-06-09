import { useMemo } from "react";
import { Link } from "react-router-dom";
import { Tabs } from "antd";

import dhStyles from "../dashboard-home/dashboardHome.module.css";
import type { ModuleHomeTone, ModuleHomeView } from "./moduleHomeModel";
import type { ModuleWorkbenchHomeConfig } from "./moduleHomeConfig";
import { MarketActionQueue } from "./MarketActionQueue";
import { MarketDepthPanel } from "./MarketDepthPanel";
import { MarketDecisionMatrix } from "./MarketDecisionMatrix";
import { MarketRateLadder } from "./MarketKeyRateCard";
import MarketMacroToolkitSection from "./MarketMacroToolkitSection";
import { MarketStructureTabPanel } from "./MarketStructureTabPanel";
import marketStyles from "./marketHome.module.css";

const MARKET_TABS = [
  { key: "formal-rate-series", label: "正式利率序列" },
  { key: "catalog-overview", label: "数据目录" },
  { key: "latest-macro-snapshot", label: "跨资产快讯" },
] as const;

const DETAIL_PANEL_TEST_IDS: Record<string, string> = {
  "yield-curve-quotes": "module-home-yield-curve",
  "latest-macro-snapshot": "module-home-macro-snapshot",
  "formal-rate-series": "module-home-formal-rates",
  "catalog-overview": "module-home-catalog-summary",
};

function panelByKey(panels: ModuleHomeView["detailPanels"], key: string) {
  return panels?.find((panel) => panel.key === key);
}

function toneClass(tone: ModuleHomeTone) {
  if (tone === "watch") return dhStyles.dhMuted;
  if (tone === "error") return dhStyles.dhUpRed;
  return "";
}

function statePillClass(tone: ModuleHomeTone) {
  if (tone === "error") return `${dhStyles.dhStatusPill} ${dhStyles.dhStatusPillWarning}`;
  if (tone === "watch") return `${dhStyles.dhStatusPill} ${dhStyles.dhStatusPillWarning}`;
  return dhStyles.dhStatusPill;
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

type MarketDetailPanel = NonNullable<ModuleHomeView["detailPanels"]>[number];

function findMarketRow(panel: MarketDetailPanel | undefined, patterns: string[]) {
  return panel?.rows.find((row) => patterns.some((pattern) => `${row.key} ${row.label} ${row.source}`.includes(pattern)));
}

function marketCue(rateParts: string[], crossAssetLabel: string | undefined) {
  const crossAssetText = crossAssetLabel ?? "跨资产信号";
  if (rateParts.length === 0) {
    return `先确认利率与流动性信号是否已返回，再看${crossAssetText}对债市判断的传导。`;
  }
  return `先确认 ${rateParts.join(" 与 ")}，再看${crossAssetText}对债市判断的传导。`;
}

type MarketHomeLayoutProps = {
  view: ModuleHomeView;
  config: ModuleWorkbenchHomeConfig;
  latestTradeDate: string;
  formalTradeDate: string;
};

export default function MarketHomeLayout({
  view,
  config,
  latestTradeDate,
  formalTradeDate,
}: MarketHomeLayoutProps) {
  const stateTone: ModuleHomeTone =
    view.stateLabel === "读取失败" ? "error" : view.stateLabel === "读取中" ? "muted" : "ok";

  const primaryBriefing = view.briefings[0];
  const secondaryBriefings = view.briefings.slice(1);
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
  const isMarketTerminalDefaultEmpty = formalPanel
    ? formalPanel.rows.length === 0 &&
      (!formalPanel.chart || formalPanel.chart.categories.length === 0)
    : false;
  const tenYearRow = findMarketRow(keyRatePanel, ["10Y", "10年", "十年"]);
  const liquidityRow = findMarketRow(keyRatePanel, ["DR007", "SHIBOR", "shibor"]);
  const crossAssetRow = macroPanel?.rows[0];
  const macroStanceRow =
    macroOverviewPanel?.rows.find((row) => row.key.includes("stance") || row.label.includes("结论")) ??
    macroOverviewPanel?.rows[0];
  const marketPulse = [
    {
      key: "ten-year",
      label: "10Y国债",
      value: tenYearRow?.value ?? "待返回",
      detail: compactMarketParts([tenYearRow?.detail, tenYearRow?.tradeDate]).join(" / "),
      tone: tenYearRow?.tone ?? keyRatePanel?.tone ?? "muted",
    },
    {
      key: "liquidity",
      label: liquidityRow?.label ?? "流动性",
      value: liquidityRow?.value ?? "待返回",
      detail: compactMarketParts([liquidityRow?.detail, liquidityRow?.tradeDate]).join(" / "),
      tone: liquidityRow?.tone ?? keyRatePanel?.tone ?? "muted",
    },
    {
      key: "cross-asset",
      label: crossAssetRow?.label ?? "跨资产",
      value: crossAssetRow?.value ?? "待返回",
      detail: compactMarketParts([crossAssetRow?.detail, crossAssetRow?.tradeDate]).join(" / "),
      tone: crossAssetRow?.tone ?? macroPanel?.tone ?? "muted",
    },
    {
      key: "macro",
      label: "宏观信号",
      value: macroStanceRow?.value ?? macroStanceRow?.label ?? "观察",
      detail: compactMarketParts([macroStanceRow?.detail, macroStanceRow?.tradeDate]).join(" / "),
      tone: macroStanceRow?.tone ?? macroOverviewPanel?.tone ?? "muted",
    },
  ];
  const sourceScopeSegments = sourceSegments(view.sourceScope);
  const marketKpis = marketPulse.slice(0, 3);
  const marketReadingOrder = "先看利率曲线与流动性，再看跨资产传导，必要时进入下钻复核。";
  const marketJudgementCue = marketCue(
    compactMarketParts([tenYearRow ? "10Y" : null, liquidityRow?.label]),
    crossAssetRow?.label,
  );

  const tabItems = useMemo(() => {
    const map = new Map(view.detailPanels?.map((panel) => [panel.key, panel]) ?? []);
    return MARKET_TABS.map((tab) => {
      const panel = map.get(tab.key);
      return {
        key: tab.key,
        label: tab.label,
        children: panel ? (
          <MarketStructureTabPanel panel={panel} />
        ) : (
          <p className={marketStyles.panelEmpty}>暂无数据</p>
        ),
      };
    });
  }, [view.detailPanels]);

  return (
    <>
      <header data-testid="module-home-toolbar" className={`${dhStyles.dhTopbar} ${marketStyles.marketTopbar}`}>
        <div className={`${dhStyles.dhTopbarLeft} ${marketStyles.marketTopbarLeft}`}>
          <div className={dhStyles.dhTitleBrand}>
            <span className={dhStyles.dhTitleBar} aria-hidden="true" />
            <h1 className={dhStyles.dhTitle}>{view.title}</h1>
          </div>
          <div className={marketStyles.topbarCopy}>
            <p className={marketStyles.topbarSummary}>{view.question}</p>
            <p className={marketStyles.topbarScope}>{marketReadingOrder}</p>
          </div>
        </div>
        <div
          className={`${dhStyles.dhTopbarRight} ${marketStyles.marketTopbarMeta}`}
          data-testid="module-home-market-topbar-audit-meta"
          hidden
        >
          <span className={statePillClass(stateTone)} data-tone={stateTone}>
            {view.stateLabel}
          </span>
          <span className={dhStyles.dhDateLabel}>最新行情日</span>
          <span className={`${dhStyles.dhNum} ${marketStyles.topbarDate}`}>{latestTradeDate || "—"}</span>
          <span className={dhStyles.dhDateLabel}>正式序列日</span>
          <span className={`${dhStyles.dhNum} ${marketStyles.topbarDate}`}>{formalTradeDate || "—"}</span>
        </div>
      </header>

      <main className={`${dhStyles.dhMain} ${marketStyles.marketPageMain}`}>
        <section
          data-testid="module-home-market-cockpit"
          className={marketStyles.marketInstitutionalCockpit}
        >
          <section
            data-testid="module-home-market-primary-grid"
            className={marketStyles.marketPrimaryGrid}
          >
            <div className={marketStyles.marketPrimaryColumn}>
              <section className={marketStyles.decisionSection}>
                <section data-testid="module-home-briefing" className={`${dhStyles.dhHero} ${marketStyles.marketHero}`}>
          {primaryBriefing ? (
            <article className={`${dhStyles.dhCard} ${dhStyles.dhTerminalJudgement} ${marketStyles.judgementCard}`}>
              <span className={dhStyles.dhTerminalEyebrow}>本日市场判断</span>
              <h2>{primaryBriefing.conclusion}</h2>
              <p className={`${dhStyles.dhImpact} ${marketStyles.marketHeroEvidence}`} data-testid="module-home-market-hero-evidence">
                <span>{marketJudgementCue}</span>
              </p>
              <div className={`${dhStyles.dhTerminalJudgementFoot} ${marketStyles.marketHeroMeta}`} data-testid="module-home-market-hero-meta" hidden>
                <span>{view.stateDetail}</span>
                <span>{primaryBriefing.evidence}</span>
                <span className={marketStyles.marketHeroSources}>
                  {sourceScopeSegments.length > 0
                    ? sourceScopeSegments.map((part, index) => <em key={part}>{index > 0 ? ` / ${part}` : part}</em>)
                    : <em>{view.sourceScope}</em>}
                </span>
              </div>
            </article>
          ) : null}
          <article
            data-testid="module-home-kpi-strip"
            className={`${dhStyles.dhCard} ${marketStyles.marketKpiBox}`}
          >
            {marketKpis.map((item) => (
              <div className={`${dhStyles.dhMetricTile} ${marketStyles.marketKpiTile}`} data-tone={item.tone} key={item.key}>
                <div className={dhStyles.dhMetricLabel}>{item.label}</div>
                <div className={`${dhStyles.dhMetricValue} ${dhStyles.dhNum} ${toneClass(item.tone)}`}>
                  {item.value}
                </div>
                <div className={dhStyles.dhChange}>
                  <span className={`${dhStyles.dhMuted} ${marketStyles.marketKpiDetail}`} data-testid={`module-home-market-kpi-${item.key}-detail`}>
                    {evidenceSegments(item.detail).map((part) => (
                      <em key={part}>{part}</em>
                    ))}
                  </span>
                </div>
              </div>
            ))}
          </article>
                </section>

                {secondaryBriefings.length > 0 ? (
                  <section className={`${marketStyles.insightRow} ${marketStyles.marketAuditOnly}`} hidden>
                    {secondaryBriefings.map((item) => (
                      <article className={marketStyles.insightCell} key={item.title}>
                        <span className={marketStyles.insightLabel}>{item.title}</span>
                        <p className={marketStyles.insightCopy}>{item.conclusion}</p>
                        <span className={`${marketStyles.insightEvidence} ${marketStyles.marketAuditOnly}`} hidden>
                          {item.evidence}
                        </span>
                      </article>
                    ))}
                  </section>
                ) : null}

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

                <MarketActionQueue
                  view={view}
                  keyRatePanel={keyRatePanel}
                  yieldCurvePanel={yieldCurvePanel}
                  macroPanel={macroPanel}
                />

              </section>
            </div>

            <aside
              data-testid="module-home-market-evidence-rail"
              className={marketStyles.evidenceRail}
            >
              <div className={marketStyles.evidenceRailHeader}>
                <span>交易检查清单</span>
                <strong data-tone={stateTone}>
                  {view.stateLabel}
                </strong>
              </div>
              <p
                className={marketStyles.evidenceRailState}
                data-testid="module-home-market-evidence-rail-state"
              >
                行情 {latestTradeDate || "—"}，正式序列 {formalTradeDate || "—"}；{view.stateLabel}。
              </p>

              <div className={marketStyles.evidenceRailMetricGrid} data-testid="module-home-market-evidence-rail-metrics">
                {marketKpis.map((item) => (
                  <div className={marketStyles.evidenceRailMetric} data-tone={item.tone} key={item.key}>
                    <span>{item.label}</span>
                    <strong className={dhStyles.dhNum}>{item.value}</strong>
                  </div>
                ))}
              </div>

              <section
                className={marketStyles.evidenceRailCard}
                data-testid="module-home-market-audit-status"
              >
                <span className={marketStyles.evidenceRailLabel}>约束检查结果</span>
                <div className={marketStyles.evidenceRailStatusList}>
                  {view.statuses.slice(0, 5).map((item) => (
                    <span data-tone={item.tone} key={item.key}>
                      <b>{item.label}</b>
                      <em>{item.value || item.detail || "待返回"}</em>
                    </span>
                  ))}
                </div>
              </section>

              <nav className={marketStyles.evidenceRailActionList} aria-label="市场模块入口">
                <Link to="/market-data" className={marketStyles.evidenceRailLink}>
                  市场数据
                </Link>
                <Link to="/macro-toolkit" className={marketStyles.evidenceRailLink}>
                  宏观工具
                </Link>
                <Link to="/cross-asset" className={marketStyles.evidenceRailLink}>
                  跨资产
                </Link>
              </nav>
            </aside>
          </section>

        <section className={marketStyles.marketWorkbenchSection}>
          <div className={dhStyles.dhSectionTitle}>
            <span>市场工作台</span>
            <Link to="/market-data" className={dhStyles.dhLink}>
              完整市场数据 →
            </Link>
          </div>
          <div className={marketStyles.workGrid}>
          {keyRatePanel ? <MarketRateLadder panel={keyRatePanel} viewAllPath="/market-data" /> : null}
          <div
            data-testid="module-home-market-terminal"
            className={`${dhStyles.dhCard} ${marketStyles.terminalCard} ${
              isMarketTerminalDefaultEmpty ? marketStyles.marketCompactEmptyTerminal : ""
            }`}
          >
            <div className={dhStyles.dhSectionTitle}>
              <span>行情序列</span>
            </div>
            <Tabs defaultActiveKey="formal-rate-series" items={tabItems} />
          </div>
          </div>
        </section>

        <section className={marketStyles.depthSection}>
          <div className={dhStyles.dhSectionTitle}>
            <span>市场深度</span>
          </div>
          <div className={marketStyles.depthQuad}>
            {yieldCurvePanel ? (
              <MarketDepthPanel
                panel={yieldCurvePanel}
                testId={DETAIL_PANEL_TEST_IDS[yieldCurvePanel.key]}
              />
            ) : null}
            {macroPanel ? (
              <MarketDepthPanel panel={macroPanel} testId={DETAIL_PANEL_TEST_IDS[macroPanel.key]} />
            ) : null}
            {formalPanel ? (
              <MarketDepthPanel
                panel={formalPanel}
                testId={DETAIL_PANEL_TEST_IDS[formalPanel.key]}
                compact
              />
            ) : null}
            {catalogPanel ? (
              <MarketDepthPanel
                panel={catalogPanel}
                testId={DETAIL_PANEL_TEST_IDS[catalogPanel.key]}
                compact
              />
            ) : null}
          </div>
        </section>

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

        <section className={marketStyles.navigationSection}>
        <section data-testid="module-home-observation" className={marketStyles.observationSection}>
          <div className={dhStyles.dhSectionTitle}>
            <span>观察入口</span>
          </div>
          <div className={marketStyles.observationGrid}>
            <Link className={`${dhStyles.dhCard} ${marketStyles.observationCard}`} to="/cross-asset">
              <strong>跨资产驱动</strong>
              <span className={marketStyles.observationBadge}>观察口径</span>
              <p>宏观、汇率与权益向债券组合的传导解释。</p>
            </Link>
            <Link className={`${dhStyles.dhCard} ${marketStyles.observationCard}`} to="/news-events">
              <strong>新闻事件</strong>
              <span className={marketStyles.observationBadge}>已开放</span>
              <p>Choice 新闻事件、回调异常与事件列表摘要。</p>
            </Link>
            <Link className={`${dhStyles.dhCard} ${marketStyles.observationCard}`} to="/macro-toolkit">
              <strong>宏观工具</strong>
              <span className={marketStyles.observationBadge}>工具口径</span>
              <p>脚本注册表、信号卡片与能力模块完整页。</p>
            </Link>
          </div>
        </section>

        <section data-testid="module-home-drilldowns" className={marketStyles.drillSection}>
          <div className={dhStyles.dhSectionTitle}>
            <span>模块下钻</span>
          </div>
          <div className={marketStyles.drillGrid}>
            {config.drilldowns.map((item) => {
              const isCurrentHome = item.key === "market-overview";
              return (
                <Link
                  key={item.key}
                  to={item.path}
                  aria-current={isCurrentHome ? "page" : undefined}
                  className={`${marketStyles.drillLink} ${isCurrentHome ? marketStyles.drillLinkCurrent : ""}`}
                  title={item.description}
                >
                  <b>{item.label}</b>
                  <em>{isCurrentHome ? "当前首页" : item.statusLabel}</em>
                  <span className={marketStyles.drillDesc}>{item.description}</span>
                </Link>
              );
            })}
          </div>
          {view.dataNote.lines.length > 0 ? (
            <p className={marketStyles.dataNote} data-testid="module-home-data-note">
              {view.dataNote.lines.join(" ")}
            </p>
          ) : null}
        </section>
        </section>
        </section>
      </main>
    </>
  );
}
