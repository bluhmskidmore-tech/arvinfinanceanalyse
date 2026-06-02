import { useMemo } from "react";
import { Link } from "react-router-dom";
import { Tabs } from "antd";

import dhStyles from "../dashboard-home/dashboardHome.module.css";
import type { ModuleHomeTone, ModuleHomeView } from "./moduleHomeModel";
import type { ModuleWorkbenchHomeConfig } from "./moduleHomeConfig";
import { MarketDepthPanel } from "./MarketDepthPanel";
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
      <header data-testid="module-home-toolbar" className={dhStyles.dhTopbar}>
        <div className={dhStyles.dhTopbarLeft}>
          <div className={dhStyles.dhTitleBrand}>
            <span className={dhStyles.dhTitleBar} aria-hidden="true" />
            <span className={dhStyles.dhTitleMark} aria-hidden="true">
              M
            </span>
            <h1 className={dhStyles.dhTitle}>{view.title}</h1>
          </div>
          <p className={marketStyles.topbarSummary}>{view.question}</p>
          <p className={marketStyles.topbarScope}>{view.summary}</p>
        </div>
        <div className={dhStyles.dhTopbarRight}>
          <span className={statePillClass(stateTone)}>{view.stateLabel}</span>
          <span className={dhStyles.dhDateLabel}>最新行情日</span>
          <span className={`${dhStyles.dhNum} ${marketStyles.topbarDate}`}>{latestTradeDate || "—"}</span>
          <span className={dhStyles.dhDateLabel}>正式序列日</span>
          <span className={`${dhStyles.dhNum} ${marketStyles.topbarDate}`}>{formalTradeDate || "—"}</span>
        </div>
      </header>

      <main className={`${dhStyles.dhMain} ${marketStyles.marketPageMain}`}>
        <section data-testid="module-home-briefing" className={`${dhStyles.dhHero} ${marketStyles.marketHero}`}>
          {primaryBriefing ? (
            <article className={`${dhStyles.dhCard} ${dhStyles.dhTerminalJudgement}`}>
              <span className={dhStyles.dhTerminalEyebrow}>本日市场判断</span>
              <h2>{primaryBriefing.conclusion}</h2>
              <p className={dhStyles.dhImpact}>{primaryBriefing.evidence}</p>
              <div className={dhStyles.dhTerminalJudgementFoot}>
                <span>{view.stateDetail}</span>
                <span className={dhStyles.dhMuted}> · {view.sourceScope}</span>
              </div>
            </article>
          ) : null}
          <article
            data-testid="module-home-kpi-strip"
            className={`${dhStyles.dhCard} ${marketStyles.marketKpiBox}`}
          >
            {view.kpis.map((item) => (
              <div className={dhStyles.dhMetricTile} key={item.key}>
                <div className={dhStyles.dhMetricLabel}>{item.label}</div>
                <div className={`${dhStyles.dhMetricValue} ${dhStyles.dhNum} ${toneClass(item.tone)}`}>
                  {item.value}
                </div>
                <div className={dhStyles.dhChange}>
                  <span className={dhStyles.dhMuted}>{item.detail}</span>
                </div>
              </div>
            ))}
          </article>
        </section>

        {secondaryBriefings.length > 0 ? (
          <section className={marketStyles.insightRow}>
            {secondaryBriefings.map((item) => (
              <article className={marketStyles.insightCell} key={item.title}>
                <span className={marketStyles.insightLabel}>{item.title}</span>
                <p className={marketStyles.insightCopy}>{item.conclusion}</p>
                <span className={marketStyles.insightEvidence}>{item.evidence}</span>
              </article>
            ))}
            <article className={marketStyles.insightCell}>
              <span className={marketStyles.insightLabel}>接入概览</span>
              <p className={marketStyles.insightCopy}>{view.stateDetail}</p>
              <span className={marketStyles.insightEvidence}>{view.sourceScope}</span>
            </article>
          </section>
        ) : null}

        <section
          data-testid="module-home-status-strip"
          className={`${dhStyles.dhCardSecondary} ${marketStyles.readPathBand}`}
        >
          <div className={marketStyles.readPathGrid}>
            {view.statuses.map((item) => (
              <div className={marketStyles.readPathCell} key={item.key}>
                <span className={marketStyles.readPathLabel}>{item.label}</span>
                <b className={`${dhStyles.dhNum} ${toneClass(item.tone)}`}>{item.value}</b>
                <em>{item.detail}</em>
              </div>
            ))}
          </div>
        </section>

        <section className={marketStyles.workGrid}>
          {keyRatePanel ? <MarketRateLadder panel={keyRatePanel} viewAllPath="/market-data" /> : null}
          <div
            data-testid="module-home-market-terminal"
            className={`${dhStyles.dhCard} ${marketStyles.terminalCard}`}
          >
            <div className={dhStyles.dhSectionTitle}>
              <span>行情序列</span>
              <Link to="/market-data" className={dhStyles.dhLink}>
                完整市场数据 →
              </Link>
            </div>
            <Tabs defaultActiveKey="formal-rate-series" items={tabItems} />
          </div>
        </section>

        <section className={marketStyles.depthQuad}>
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

        <section data-testid="module-home-drilldowns">
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
      </main>
    </>
  );
}
