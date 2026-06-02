import { useMemo } from "react";
import { Link } from "react-router-dom";
import {
  AlertOutlined,
  AppstoreOutlined,
  ArrowRightOutlined,
  BankOutlined,
  BarChartOutlined,
  FileTextOutlined,
  FundOutlined,
  SettingOutlined,
  TrophyOutlined,
} from "@ant-design/icons";
import { Tabs } from "antd";
import type { ReactNode } from "react";

import dhStyles from "../dashboard-home/dashboardHome.module.css";
import type {
  ModuleHomeDetailPanel,
  ModuleHomeDistributionPanel,
  ModuleHomeTone,
  ModuleHomeView,
} from "./moduleHomeModel";
import type { ModuleWorkbenchHomeConfig } from "./moduleHomeConfig";
import { PortfolioDistributionPanel } from "./PortfolioDistributionPanel";
import { PortfolioStructureTabPanel } from "./PortfolioStructureTabPanel";
import styles from "./portfolioHome.module.css";

const ANALYSIS_TABS = [
  { key: "portfolio-comparison", label: "子组合" },
  { key: "yield-distribution", label: "收益率" },
  { key: "spread-analysis", label: "利差" },
  { key: "business-type-metrics", label: "业务类型" },
] as const;

const DRILL_ICON_MAP: Record<string, ReactNode> = {
  dashboard: <AppstoreOutlined />,
  analysis: <BarChartOutlined />,
  risk: <AlertOutlined />,
  team: <BarChartOutlined />,
  kpi: <TrophyOutlined />,
  decision: <BarChartOutlined />,
  bond: <BankOutlined />,
  settings: <SettingOutlined />,
  market: <FundOutlined />,
  reports: <FileTextOutlined />,
  agent: <BarChartOutlined />,
};

type PortfolioHomeLayoutProps = {
  view: ModuleHomeView;
  config: ModuleWorkbenchHomeConfig;
  balanceReportDate: string;
  bondReportDate: string;
};

function toneClass(tone: ModuleHomeTone) {
  if (tone === "ok") return styles.toneOk;
  if (tone === "watch") return styles.toneWatch;
  if (tone === "error") return styles.toneError;
  return styles.toneMuted;
}

function briefCardClass(tone: ModuleHomeTone, primary = false) {
  const toneKey =
    tone === "ok"
      ? styles.briefCardOk
      : tone === "watch"
        ? styles.briefCardWatch
        : tone === "error"
          ? styles.briefCardError
          : "";
  return `${styles.briefCard} ${toneKey} ${primary ? styles.briefCardPrimary : ""}`.trim();
}

function statePillClass(tone: ModuleHomeTone) {
  if (tone === "ok") return `${styles.statePill} ${styles.stateOk}`;
  if (tone === "error") return `${styles.statePill} ${styles.stateError}`;
  if (tone === "watch") return `${styles.statePill} ${styles.stateWatch}`;
  return styles.statePill;
}

function panelByKey(panels: ModuleHomeDetailPanel[] | undefined, key: string) {
  return panels?.find((panel) => panel.key === key);
}

function detailPanelTestId(panelKey: string) {
  if (panelKey === "risk-indicators-detail") return "module-home-portfolio-risk";
  if (panelKey === "portfolio-comparison") return "module-home-portfolio-comparison";
  if (panelKey === "yield-distribution") return "module-home-portfolio-yield";
  if (panelKey === "spread-analysis") return "module-home-portfolio-spread";
  if (panelKey === "business-type-metrics") return "module-home-portfolio-business-type";
  if (panelKey === "balance-basis") return "module-home-balance-basis";
  if (panelKey === "pnl-attribution-summary") return "module-home-pnl-summary";
  return "module-home-detail-panels";
}

function DetailPanelBody({
  panel,
  embedded = false,
}: {
  panel: ModuleHomeDetailPanel;
  embedded?: boolean;
}) {
  const body = (
    <>
      <div className={embedded ? styles.embeddedPanelHead : dhStyles.dhTerminalPanelHead}>
        {!embedded ? <h3>{panel.title}</h3> : null}
        <span className={statePillClass(panel.tone)}>{panel.stateLabel}</span>
      </div>
      <p className={styles.detailSource}>{panel.meta}</p>
      {panel.rows.length > 0 ? (
        <ul className={styles.detailList}>
          {panel.rows.map((row) => (
            <li className={styles.detailRow} key={row.key}>
              <div className={styles.detailTop}>
                <span className={styles.detailLabel}>{row.label}</span>
                <span className={`${styles.detailValue} ${toneClass(row.tone)}`}>{row.value}</span>
              </div>
              {row.source ? <span className={styles.detailSource}>{row.source}</span> : null}
            </li>
          ))}
        </ul>
      ) : (
        <p className={`${styles.detailSource} ${toneClass(panel.tone)}`}>{panel.stateDetail}</p>
      )}
    </>
  );

  if (embedded) {
    return <div className={styles.embeddedPanel}>{body}</div>;
  }

  return body;
}

function DetailPanelCard({
  panel,
  testId,
}: {
  panel: ModuleHomeDetailPanel;
  testId: string;
}) {
  return (
    <article className={`${dhStyles.dhCard} ${dhStyles.dhTerminalPanel}`} data-testid={testId}>
      <DetailPanelBody panel={panel} />
    </article>
  );
}

function DistributionPanelCard({ panel }: { panel: ModuleHomeDistributionPanel }) {
  return <PortfolioDistributionPanel panel={panel} />;
}

function SectionHead({ label, title }: { label: string; title: string }) {
  return (
    <div className={styles.sectionHead}>
      <span>{label}</span>
      <strong>{title}</strong>
    </div>
  );
}

export default function PortfolioHomeLayout({
  view,
  config,
  balanceReportDate,
  bondReportDate,
}: PortfolioHomeLayoutProps) {
  const stateTone: ModuleHomeTone =
    view.stateLabel === "读取失败" ? "error" : view.stateLabel === "读取中" ? "muted" : "ok";

  const riskPanel = panelByKey(view.detailPanels, "risk-indicators-detail");
  const basisPanel = panelByKey(view.detailPanels, "balance-basis");
  const pnlPanel = panelByKey(view.detailPanels, "pnl-attribution-summary");

  const tabItems = useMemo(() => {
    const map = new Map(view.detailPanels?.map((panel) => [panel.key, panel]) ?? []);
    return ANALYSIS_TABS.map((tab) => {
      const panel = map.get(tab.key);
      return {
        key: tab.key,
        label: tab.label,
        children: panel ? (
          <PortfolioStructureTabPanel panel={panel} />
        ) : (
          <p className={styles.detailSource}>暂无数据</p>
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
          <p className={styles.topbarSubtitle}>{view.question}</p>
        </div>
        <div className={dhStyles.dhTopbarRight}>
          <div className={styles.toolbarMeta}>
            <span className={statePillClass(stateTone)}>{view.stateLabel}</span>
            <span className={styles.datePill}>
              资产负债日 <strong>{balanceReportDate || "—"}</strong>
            </span>
            <span className={styles.datePill}>
              债券总览日 <strong>{bondReportDate || "—"}</strong>
            </span>
          </div>
          <p className={styles.detailSource}>{view.stateDetail}</p>
        </div>
      </header>

      <main className={`${dhStyles.dhMain} ${styles.pageStack}`}>
        <section data-testid="module-home-briefing" className={styles.sectionBlock}>
          <SectionHead label="Portfolio Brief" title="组合摘要" />
          <div className={styles.briefGrid}>
            {view.briefings.map((item, index) => (
              <article
                className={`${dhStyles.dhCard} ${briefCardClass(item.tone, index === 0)}`}
                key={item.title}
              >
                <span className={styles.briefTitle}>{item.title}</span>
                <strong className={`${styles.briefConclusion} ${toneClass(item.tone)}`}>
                  {item.conclusion}
                </strong>
                <span className={styles.briefEvidence}>{item.evidence}</span>
              </article>
            ))}
          </div>
        </section>

        <section data-testid="module-home-kpi-strip" className={styles.sectionBlock}>
          <SectionHead label="Core Metrics" title="核心指标" />
          <div className={styles.kpiGrid}>
            {view.kpis.map((item) => (
              <article className={`${dhStyles.dhCard} ${dhStyles.dhTerminalKpi}`} key={item.key}>
                <div className={dhStyles.dhTerminalKpiTop}>
                  <span className={styles.kpiLabel}>{item.label}</span>
                </div>
                <div className={`${styles.kpiValue} ${toneClass(item.tone)}`}>{item.value}</div>
                <div className={styles.kpiDetail}>{item.detail}</div>
              </article>
            ))}
          </div>
        </section>

        <section
          data-testid="module-home-status-strip"
          className={`${dhStyles.dhCard} ${dhStyles.dhTerminalRiskStrip} ${styles.statusStrip} ${styles.sectionBlock}`}
        >
          <div className={styles.sectionHead}>
            <span>Read Path</span>
            <strong>读链路状态</strong>
            <span className={styles.statusScope}>{view.sourceScope}</span>
          </div>
          <div className={styles.statusGrid}>
            {view.statuses.map((item) => (
              <div className={styles.statusCell} key={item.key}>
                <span>{item.label}</span>
                <b className={toneClass(item.tone)}>{item.value}</b>
                <em>{item.detail}</em>
              </div>
            ))}
          </div>
        </section>

        {view.distributionPanels && view.distributionPanels.length > 0 ? (
          <section data-testid="module-home-holdings-structure" className={styles.sectionBlock}>
            <div className={styles.sectionHead}>
              <span>Holdings</span>
              <strong>持仓结构</strong>
              <Link className={styles.holdingsSectionLink} to="/positions">
                持仓透视
              </Link>
            </div>
            <div className={styles.holdingsGrid}>
              {view.distributionPanels.map((panel) => (
                <DistributionPanelCard panel={panel} key={panel.key} />
              ))}
            </div>
          </section>
        ) : null}

        <section
          data-testid="module-home-portfolio-terminal"
          className={`${dhStyles.dhCard} ${styles.terminalCard} ${styles.sectionBlock}`}
        >
          <SectionHead label="Structure" title="结构拆解" />
          <Tabs items={tabItems} />
        </section>

        <section className={styles.sectionBlock}>
          <SectionHead label="Risk & PnL" title="风险与归因" />
          <div className={styles.detailGrid}>
            {riskPanel ? (
              <DetailPanelCard panel={riskPanel} testId={detailPanelTestId(riskPanel.key)} />
            ) : null}
            {pnlPanel ? (
              <DetailPanelCard panel={pnlPanel} testId={detailPanelTestId(pnlPanel.key)} />
            ) : null}
            {basisPanel ? (
              <DetailPanelCard panel={basisPanel} testId={detailPanelTestId(basisPanel.key)} />
            ) : null}
          </div>
        </section>

        <section data-testid="module-home-drilldowns" className={styles.sectionBlock}>
          <SectionHead label="Drilldown" title="下钻入口" />
          <div className={styles.drillGrid}>
            {config.drilldowns.map((item) => {
              const icon = (item.icon && DRILL_ICON_MAP[item.icon]) ?? <ArrowRightOutlined />;
              const isCurrentHome = item.key === "portfolio-home";
              return (
                <Link
                  key={item.key}
                  to={item.path}
                  aria-current={isCurrentHome ? "page" : undefined}
                  className={`${dhStyles.dhCard} ${dhStyles.dhTerminalQuick} ${styles.drillCard} ${
                    isCurrentHome ? styles.drillCardCurrent : ""
                  }`}
                  title={item.description}
                >
                  <span>{icon}</span>
                  <b>{item.label}</b>
                  <em>{isCurrentHome ? "当前首页" : item.statusLabel}</em>
                </Link>
              );
            })}
          </div>
          {view.dataNote.lines.length > 0 ? (
            <p className={styles.dataNote} data-testid="module-home-data-note">
              {view.dataNote.lines.join(" ")}
            </p>
          ) : null}
        </section>
      </main>
    </>
  );
}
