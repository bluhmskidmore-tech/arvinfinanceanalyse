import { useMemo } from "react";
import { Link } from "react-router-dom";
import { Tabs } from "antd";
import type { ReactNode } from "react";

import { LightIcon } from "../../../components/LightIcon";
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
  dashboard: <LightIcon name="appstore" />,
  analysis: <LightIcon name="bar-chart" />,
  risk: <LightIcon name="alert" />,
  team: <LightIcon name="bar-chart" />,
  kpi: <LightIcon name="trophy" />,
  decision: <LightIcon name="bar-chart" />,
  bond: <LightIcon name="bank" />,
  settings: <LightIcon name="settings" />,
  market: <LightIcon name="fund" />,
  reports: <LightIcon name="file-text" />,
  agent: <LightIcon name="bar-chart" />,
};

type PortfolioHomeLayoutProps = {
  view: ModuleHomeView;
  config: ModuleWorkbenchHomeConfig;
  balanceReportDate: string;
  bondReportDate: string;
};

type PortfolioDecisionFact = NonNullable<ModuleHomeView["decision"]>["facts"][number];

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

function PortfolioAiDecisionRail({ view }: { view: ModuleHomeView }) {
  const decision = view.decision;
  const actions = decision?.actions ?? [];
  const leadingBriefing = view.briefings[0];

  return (
    <aside data-testid="module-home-portfolio-ai-rail" className={styles.aiDecisionRail}>
      <div className={styles.aiRailHeader}>
        <span>AI 决策舱</span>
        <strong data-tone={decision?.tone ?? "muted"}>{decision ? decisionUseLabel(decision) : view.stateLabel}</strong>
      </div>
      <p className={styles.aiRailState}>{view.stateDetail}</p>

      <div className={styles.aiRailMetricGrid}>
        {view.kpis.slice(0, 4).map((item) => (
          <div className={styles.aiRailMetric} data-tone={item.tone} key={item.key}>
            <span>{item.label}</span>
            <strong>{item.value}</strong>
          </div>
        ))}
      </div>

      {decision ? (
        <section className={styles.aiRailCard} data-tone={decision.tone}>
          <span className={styles.aiRailLabel}>{decision.title}</span>
          <strong>{decision.conclusion}</strong>
          <p>{compactDecisionDetail(decision.detail) || decision.detail}</p>
        </section>
      ) : null}

      {leadingBriefing ? (
        <section className={styles.aiRailCard} data-tone={leadingBriefing.tone}>
          <span className={styles.aiRailLabel}>{leadingBriefing.title}</span>
          <strong>{leadingBriefing.conclusion}</strong>
          <p>{leadingBriefing.evidence}</p>
        </section>
      ) : null}

      <section className={styles.aiRailCard}>
        <span className={styles.aiRailLabel}>Source Gate</span>
        <div className={styles.aiRailStatusList}>
          {view.statuses.slice(0, 5).map((item) => (
            <span data-tone={item.tone} key={item.key}>
              {item.label}
            </span>
          ))}
        </div>
      </section>

      {actions.length > 0 ? (
        <nav className={styles.aiRailActionList} aria-label="组合决策动作">
          {actions.map((action) => (
            <Link className={styles.aiRailLink} to={action.path} data-tone={action.tone} key={action.title}>
              <span>{action.title}</span>
              <strong>{action.label ?? "下钻"}</strong>
            </Link>
          ))}
        </nav>
      ) : null}
    </aside>
  );
}

function SectionHead({ label, title }: { label: string; title: string }) {
  return (
    <div className={styles.sectionHead}>
      <span>{label}</span>
      <strong>{title}</strong>
    </div>
  );
}

function splitDecisionFacts(facts: PortfolioDecisionFact[]) {
  return {
    exposure: facts.slice(0, 6),
    evidence: facts.slice(6),
  };
}

function decisionUseLabel(decision: NonNullable<ModuleHomeView["decision"]>) {
  const decisionText = `${decision.conclusion} ${decision.detail}`;
  if (decisionText.includes("仅供分析")) return "仅供分析";
  if (decisionText.includes("仅供监控")) return "仅供监控";
  if (decisionText.includes("不可用于业务决策") || decision.tone === "error") return "不可用于业务决策";
  return "待复核";
}

function compactDecisionDetail(detail: string) {
  const parts = [
    detail.includes("不生成调仓建议") ? "不生成调仓建议" : "",
    detail.includes("不使用前端补数") ? "不使用前端补数" : "",
    detail.match(/风险闭合：([^；。]+)/)?.[0] ?? "",
  ].filter(Boolean);
  return parts.join(" / ");
}

function compactFactValue(fact: PortfolioDecisionFact) {
  if (fact.label.includes("源日期")) {
    const entries = fact.value
      .split("；")
      .map((entry) => entry.match(/^(.+?)=(\d{4}-\d{2}-\d{2})$/))
      .filter((entry): entry is RegExpMatchArray => Boolean(entry));
    const dates = Array.from(new Set(entries.map((entry) => entry[2])));
    if (entries.length > 0 && dates.length === 1) return `${entries.length} 个来源 / ${dates[0]}`;
    if (entries.length > 0 && dates.length > 1) return `${entries.length} 个来源 / ${dates.join(" / ")}`;
  }
  return fact.value;
}

function compactActionEvidence(evidence: string) {
  return evidence
    .replace(/债券总览 basis=analytical/g, "债券总览为分析口径")
    .replace(/basis=analytical/g, "分析口径")
    .replace(/债券总览 formal_use_allowed=false/g, "债券总览尚未允许正式使用")
    .replace(/formal_use_allowed=false/g, "尚未允许正式使用")
    .replace(/债券总览 quality=warning/g, "债券总览质量标记为关注")
    .replace(/quality=warning/g, "质量标记为关注")
    .replace(/report_date 缺失/g, "报告日缺失")
    .replace(/bond-dashboard 的 result_meta、正式使用许可、质量标记和报告日/g, "债券总览的来源版本、使用许可、质量标记和报告日")
    .replace(/pnl-attribution 的正式口径、质量标记和报告日/g, "收益归因的正式口径、质量标记和报告日")
    .replace(/result_meta/g, "来源元数据");
}

function DecisionPanel({ view }: { view: ModuleHomeView }) {
  if (!view.decision) {
    return null;
  }

  const actions = view.decision.actions ?? [];
  const factGroups = splitDecisionFacts(view.decision.facts);
  const useLabel = decisionUseLabel(view.decision);

  return (
    <section
      data-testid="module-home-decision"
      className={`${dhStyles.dhCard} ${styles.decisionPanel}`}
    >
      <div className={styles.decisionLedger}>
        <div className={styles.decisionLedgerHead}>
          <span className={styles.decisionKicker}>组合复核</span>
          <span hidden>{view.decision.title}</span>
          <span
            className={`${styles.terminalStatus} ${toneClass(view.decision.tone)}`}
            data-testid="module-home-decision-use-level"
          >
            {useLabel}
          </span>
        </div>
        <h2 className={`${styles.decisionTitle} ${toneClass(view.decision.tone)}`}>
          {view.decision.conclusion}
        </h2>
        <p className={styles.decisionDetail}>{compactDecisionDetail(view.decision.detail)}</p>
        <span className={styles.srOnly}>{view.decision.detail}</span>
        <div className={styles.decisionReadinessBar} aria-label={`${view.decision.title}: ${useLabel}`}>
          <span>业务可用</span>
          <strong className={toneClass(view.decision.tone)}>{useLabel}</strong>
        </div>
      </div>

      <div className={styles.decisionMatrix} data-testid="module-home-exposure-matrix">
        <div className={styles.terminalPanelHead}>
          <span>风险暴露</span>
          <strong>核心读数</strong>
        </div>
        <div className={styles.decisionFactGrid}>
          {factGroups.exposure.map((fact) => (
            <div className={styles.decisionFact} key={fact.label} aria-label={`${fact.label}: ${fact.value}`}>
              <span>{fact.label}</span>
              <strong className={toneClass(fact.tone)}>{compactFactValue(fact)}</strong>
            </div>
          ))}
        </div>
      </div>

      <div className={styles.evidenceConsole} data-testid="module-home-evidence-console">
        <div className={styles.terminalPanelHead}>
          <span>证据口径</span>
          <strong>来源 / 日期 / 闭合</strong>
        </div>
        <div className={styles.evidenceFactList}>
          {factGroups.evidence.map((fact) => (
            <div className={styles.decisionFact} key={fact.label} aria-label={`${fact.label}: ${fact.value}`}>
              <span>{fact.label}</span>
              <strong className={toneClass(fact.tone)}>{compactFactValue(fact)}</strong>
            </div>
          ))}
        </div>
        {actions.length > 0 ? (
          <div className={styles.decisionActionQueue}>
            <span className={styles.decisionActionLabel}>待复核</span>
            <div className={styles.decisionActionList}>
              {actions.map((action) => (
                <Link className={styles.decisionAction} to={action.path} key={action.title}>
                  <span className={`${styles.decisionActionDot} ${toneClass(action.tone)}`} />
                  <span className={styles.decisionActionText}>
                    <strong className={toneClass(action.tone)}>{action.title}</strong>
                    <small>{compactActionEvidence(action.evidence)}</small>
                  </span>
                  <span className={styles.decisionActionTarget}>
                    {action.label ?? "下钻"}
                    <LightIcon name="arrow-right" />
                  </span>
                </Link>
              ))}
            </div>
          </div>
        ) : null}
      </div>
    </section>
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
          <p className={`${styles.detailSource} ${styles.toneWatch}`}>
            当前无可用正式结构读数；样例明细不作为业务决策依据。
          </p>
        ),
      };
    });
  }, [view.detailPanels]);

  return (
    <>
      <header data-testid="module-home-toolbar" className={`${dhStyles.dhTopbar} ${styles.portfolioTopbar}`}>
        <div className={`${dhStyles.dhTopbarLeft} ${styles.portfolioTopbarLeft}`}>
          <div className={dhStyles.dhTitleBrand}>
            <span className={dhStyles.dhTitleBar} aria-hidden="true" />
            <span className={dhStyles.dhTitleMark} aria-hidden="true">
              M
            </span>
            <h1 className={dhStyles.dhTitle}>{view.title}</h1>
          </div>
          <div className={styles.topbarCopy}>
            <p className={styles.topbarSubtitle}>{view.question}</p>
            <p className={styles.topbarSummary}>{view.summary}</p>
          </div>
        </div>
        <div className={`${dhStyles.dhTopbarRight} ${styles.portfolioTopbarMeta}`}>
          <div className={styles.toolbarMeta}>
            <span className={statePillClass(stateTone)} data-tone={stateTone}>{view.stateLabel}</span>
            <span className={styles.datePill}>
              资产负债日 <strong>{balanceReportDate || "—"}</strong>
            </span>
            <span className={styles.datePill}>
              债券总览日 <strong>{bondReportDate || "—"}</strong>
            </span>
          </div>
        </div>
      </header>

      <main className={`${dhStyles.dhMain} ${styles.portfolioPageMain}`}>
        <section data-testid="module-home-portfolio-cockpit" className={styles.portfolioCockpit}>
          <section data-testid="module-home-portfolio-first-screen" className={styles.portfolioPrimaryGrid}>
            <div className={styles.portfolioPrimaryColumn}>
              <DecisionPanel view={view} />

              <section data-testid="module-home-briefing" className={styles.sectionBlock}>
                <SectionHead label="组合" title="组合摘要" />
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
                <SectionHead label="指标" title="核心指标" />
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
            </div>

            <PortfolioAiDecisionRail view={view} />
          </section>

          <section
            data-testid="module-home-status-strip"
            className={`${dhStyles.dhCard} ${dhStyles.dhTerminalRiskStrip} ${styles.statusStrip} ${styles.sectionBlock}`}
          >
            <div className={styles.sectionHead}>
              <span>来源链路</span>
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
              <span>持仓</span>
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
        ) : (
          <section data-testid="module-home-holdings-structure" className={styles.sectionBlock}>
            <div className={styles.sectionHead}>
              <span>持仓</span>
              <strong>持仓结构</strong>
            </div>
            <p className={`${styles.dataNote} ${styles.toneWatch}`}>
              当前无可用正式持仓结构读数；样例明细不展示为组合事实。
            </p>
          </section>
        )}

        <section
          data-testid="module-home-portfolio-terminal"
          className={`${dhStyles.dhCard} ${styles.terminalCard} ${styles.sectionBlock}`}
        >
          <SectionHead label="结构" title="结构拆解" />
          <Tabs items={tabItems} />
        </section>

        <section className={styles.sectionBlock}>
          <SectionHead label="归因" title="风险与归因" />
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
          <SectionHead label="明细" title="下钻入口" />
          <div className={styles.drillGrid}>
            {config.drilldowns.map((item) => {
              const icon = (item.icon && DRILL_ICON_MAP[item.icon]) ?? <LightIcon name="arrow-right" />;
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
              {compactActionEvidence(view.dataNote.lines.join(" "))}
            </p>
          ) : null}
        </section>
        </section>
      </main>
    </>
  );
}
