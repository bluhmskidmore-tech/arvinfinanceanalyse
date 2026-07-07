import { useMemo } from "react";
import { Link } from "react-router-dom";
import { Tabs } from "antd";
import type { CSSProperties, ReactNode } from "react";

import { LightIcon } from "../../../components/LightIcon";
import dhStyles from "../dashboard-home/dashboardHome.module.css";
import { ModuleHomeSectionHead } from "./ModuleHomeSectionHead";
import type {
  ModuleHomeDetailPanel,
  ModuleHomeDistributionPanel,
  ModuleHomeKpi,
  ModuleHomeTone,
  ModuleHomeView,
} from "./moduleHomeModel";
import type { ModuleWorkbenchHomeConfig } from "./moduleHomeConfig";
import { MarketHomeKpiSparkline } from "./MarketHomeKpiSparkline";
import { marketChangePresentation, resolveMarketChangeDirection } from "./marketHomeChangeTone";
import { PortfolioHoldingsHeroBand } from "./PortfolioHoldingsHeroBand";
import { PORTFOLIO_QUICK_ACCESS_TILES } from "./portfolioHomeQuickAccess";
import { PortfolioRiskTickerBar } from "./PortfolioRiskTickerBar";
import { PortfolioStructureTabPanel } from "./PortfolioStructureTabPanel";
import styles from "./portfolioHome.module.css";

const PORTFOLIO_KPI_CHANGE_CLASSES = {
  up: dhStyles.dhUpRed,
  down: dhStyles.dhDownGreen,
  neutral: dhStyles.dhMuted,
} as const;

const ANALYSIS_TABS = [
  { key: "portfolio-comparison", label: "子组合" },
  { key: "yield-distribution", label: "收益率" },
  { key: "spread-analysis", label: "利差" },
  { key: "business-type-metrics", label: "业务类型" },
] as const;

type PortfolioStructureTab = (typeof ANALYSIS_TABS)[number] & {
  panel?: ModuleHomeDetailPanel;
};

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

const WORKBENCH_NAV_ITEMS = [
  { href: "#portfolio-holdings-workbench", code: "H", label: "持仓结构", detail: "全景" },
  { href: "#portfolio-risk-workbench", code: "G", label: "收益/风险", detail: "闭合前门" },
  { href: "#portfolio-structure-workbench", code: "S", label: "结构拆解", detail: "表格" },
  { href: "#portfolio-action-workbench", code: "A", label: "明细入口", detail: "入口" },
] as const;

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

function snapshotRows(panel: ModuleHomeDistributionPanel) {
  return [...panel.rows].sort((left, right) => right.barPct - left.barPct).slice(0, 3);
}

function PortfolioChartSnapshot({ panels }: { panels: ModuleHomeDistributionPanel[] | undefined }) {
  const visiblePanels = panels?.slice(0, 3) ?? [];

  if (visiblePanels.length === 0) {
    return null;
  }

  return (
    <section data-testid="module-home-portfolio-chart-snapshot" className={styles.chartSnapshot}>
      <div className={styles.chartSnapshotHead}>
        <span>Chart Tape</span>
        <strong>结构快照</strong>
      </div>
      <div className={styles.chartSnapshotGrid}>
        {visiblePanels.map((panel) => {
          const rows = snapshotRows(panel);
          return (
            <article
              className={styles.chartSnapshotCard}
              data-tone={panel.tone}
              data-testid={`module-home-distribution-${panel.key}`}
              key={panel.key}
            >
              <div className={styles.chartSnapshotCardHead}>
                <span title={panel.title}>{panel.title}</span>
                <strong>{panel.totalDisplay ?? panel.stateLabel}</strong>
              </div>
              <span className={styles.srOnly}>
                {[panel.meta, panel.stateDetail].filter(Boolean).join(" ")}
              </span>
              {rows.length > 0 ? (
                <div className={styles.chartMiniBars}>
                  {rows.map((row, index) => {
                    const width = `${Math.max(5, Math.min(row.barPct, 100))}%`;
                    return (
                      <div className={styles.chartMiniRow} key={row.key}>
                        <span className={styles.chartMiniLabel} title={row.label}>
                          {row.label}
                        </span>
                        <span className={styles.chartMiniMetric}>
                          {row.share !== "-" ? row.share : `${row.barPct.toFixed(2)}%`}
                        </span>
                        <span className={styles.chartMiniTrack} aria-hidden="true">
                          <span
                            className={styles.chartMiniFill}
                            data-color-index={index}
                            style={{ "--chart-mini-width": width } as CSSProperties}
                          />
                        </span>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className={styles.chartMiniSkeleton} aria-hidden="true">
                  <span />
                  <span />
                  <span />
                </div>
              )}
            </article>
          );
        })}
      </div>
    </section>
  );
}

function WorkbenchSectionHead({
  titleId,
  code,
  title,
  detail,
  meta,
  action,
}: {
  titleId: string;
  code: string;
  title: string;
  detail: string;
  meta?: string;
  action?: ReactNode;
}) {
  return (
    <div className={styles.workbenchSectionHead}>
      <div>
        <span>{code}</span>
        <h2 id={titleId}>{title}</h2>
        <p>{detail}</p>
      </div>
      {meta || action ? (
        <div className={styles.workbenchSectionMeta}>
          {meta ? <em>{meta}</em> : null}
          {action}
        </div>
      ) : null}
    </div>
  );
}

const FACT_KPI_LABEL_MAP: Record<string, string> = {
  信用占比: "信用占比",
  DV01: "DV01 合计",
};

function isEmptyReading(value: string) {
  return value === "-" || value === "—";
}

function PortfolioExposureLedger({ view }: { view: ModuleHomeView }) {
  const exposureFacts = view.decision ? splitDecisionFacts(view.decision.facts).exposure : [];
  const matchedKpiLabels = new Set<string>();

  const factRows = exposureFacts.map((fact) => {
    const mappedLabel = FACT_KPI_LABEL_MAP[fact.label];
    const matchedKpi = mappedLabel ? view.kpis.find((item) => item.label === mappedLabel) : undefined;
    if (matchedKpi) {
      matchedKpiLabels.add(matchedKpi.label);
    }
    const fallbackKpi =
      isEmptyReading(fact.value) && matchedKpi && !isEmptyReading(matchedKpi.value)
        ? matchedKpi
        : undefined;
    const value = fallbackKpi ? fallbackKpi.value : compactFactValue(fact);
    const tone = fallbackKpi ? fallbackKpi.tone : fact.tone;
    return {
      key: `fact-${fact.label}`,
      label: fact.label,
      value,
      tone,
      state: tone === "ok" ? "可读" : tone === "error" ? "阻断" : "仅分析",
      action: tone === "ok" ? "持仓透视" : "风险复核",
    };
  });

  const kpiRows = view.kpis
    .filter((item) => !matchedKpiLabels.has(item.label))
    .slice(0, 5)
    .map((item) => ({
      key: `kpi-${item.key}`,
      label: item.label,
      value: item.value,
      tone: item.tone,
      state: item.tone === "ok" ? "可读" : item.tone === "error" ? "阻断" : "仅分析",
      action: item.detail || "组合复核",
    }));

  const rows = [...factRows, ...kpiRows].slice(0, 5);

  return (
    <div data-testid="module-home-portfolio-exposure-ledger" className={styles.exposureLedger}>
      {rows.length > 0 ? (
        <div className={styles.exposureLedgerTable} role="table" aria-label="关键暴露账本">
          <div className={styles.exposureLedgerHeader} role="row">
            <span role="columnheader">维度</span>
            <span role="columnheader">读数</span>
            <span role="columnheader">状态</span>
            <span role="columnheader">动作</span>
          </div>
          {rows.map((row) => (
            <div className={styles.exposureLedgerRow} data-tone={row.tone} role="row" key={row.key}>
              <span role="cell">{row.label}</span>
              <strong className={toneClass(row.tone)} role="cell">{row.value}</strong>
              <span role="cell">{row.state}</span>
              <em role="cell">{compactActionEvidence(row.action)}</em>
            </div>
          ))}
        </div>
      ) : (
        <p className={`${styles.dataNote} ${styles.toneWatch}`}>当前无可用暴露事实；不展示样例读数。</p>
      )}
    </div>
  );
}

function structureTabBadge(panel: ModuleHomeDetailPanel | undefined) {
  return panel && panel.rows.length > 0 ? String(panel.rows.length) : "空";
}

function structureStatusSummary(tabs: PortfolioStructureTab[]) {
  const emptyTabs = tabs.filter((tab) => !tab.panel || tab.panel.rows.length === 0);
  if (emptyTabs.length === 0) {
    return `${tabs.length}/${tabs.length} 个结构就绪`;
  }
  return `${emptyTabs.length} 个结构为空：${emptyTabs.map((tab) => tab.label).join("、")}`;
}

function StructureTabLabel({ tab }: { tab: PortfolioStructureTab }) {
  return (
    <span
      className={styles.structureTabLabel}
      data-testid={`module-home-analysis-tab-${tab.key}`}
    >
      <span>{tab.label}</span>
      <small className={styles.structureTabBadge}>{structureTabBadge(tab.panel)}</small>
    </span>
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

function uniqueTextParts(parts: Array<string | null | undefined | false>) {
  return Array.from(new Set(parts.filter((part): part is string => Boolean(part))));
}

function compactKpiDetail(detail: string) {
  const movement = detail.match(/(?:环比|较前日)\s*[+＋−-]?\d+(?:\.\d+)?\s*(?:%|只|bp)?/)?.[0];
  const parts = uniqueTextParts([
    detail.includes("资产负债口径") ? "资产负债口径" : null,
    detail.includes("风险指标") ? "风险指标" : null,
    detail.includes("按亿元展示") ? "亿元" : null,
    detail.includes("按万元展示") ? "万元" : null,
    detail.includes("未返回") ? "未返回" : null,
    movement,
  ]);

  return parts.join(" · ");
}

const PRIMARY_KPI_KEYS = ["bond-market", "bond-duration", "bond-ytm", "bond-dv01", "bond-credit-ratio"] as const;

function splitKpisByPriority(kpis: ModuleHomeKpi[]) {
  const primaryKeySet = new Set<string>(PRIMARY_KPI_KEYS);
  const primary = PRIMARY_KPI_KEYS.map((key) => kpis.find((item) => item.key === key)).filter(
    (item): item is ModuleHomeKpi => Boolean(item),
  );
  const secondary = kpis.filter((item) => !primaryKeySet.has(item.key));
  return { primary, secondary };
}

function kpiScopeNote(kpis: ModuleHomeKpi[]) {
  const text = kpis.map((item) => item.detail).join(" ");
  return uniqueTextParts([
    text.includes("债券总览") ? "债券总览" : null,
    text.includes("分析/复核口径") ? "分析/复核口径" : null,
    text.includes("仅展示读数") ? "仅展示读数" : null,
    text.includes("不形成调仓建议") ? "不形成调仓建议" : null,
    text.includes("不纳入风险 ticker") ? "不纳入风险 ticker" : null,
  ]).join(" · ");
}

function PortfolioKpiCard({ item, variant }: { item: ModuleHomeKpi; variant: "primary" | "secondary" }) {
  const value = splitKpiValue(item.value);
  const missingValue = value.number === "-" || value.number === "—";
  const changeDirection = resolveMarketChangeDirection(item.detail, item.sparkline);
  const detail = compactKpiDetail(item.detail);
  const variantClass = variant === "primary" ? styles.kpiCardPrimary : styles.kpiCardSecondary;

  return (
    <article
      className={`${dhStyles.dhCard} ${dhStyles.dhTerminalKpi} ${styles.kpiCard} ${variantClass}`}
      data-tone={item.tone}
      data-empty={missingValue ? "true" : undefined}
      data-testid={`module-home-portfolio-kpi-${item.key}`}
    >
      <div className={dhStyles.dhTerminalKpiTop}>
        <span className={styles.kpiLabel}>{item.label}</span>
      </div>
      <div className={styles.portfolioKpiValueRow}>
        <div
          className={`${styles.kpiValue} ${toneClass(item.tone)}`}
          data-empty={missingValue ? "true" : undefined}
        >
          <span>{missingValue ? "待核验" : value.number}</span>
          {value.unit ? (
            <>
              {" "}
              <small>{value.unit}</small>
            </>
          ) : null}
        </div>
        {item.sparkline && item.sparkline.length >= 2 ? (
          <MarketHomeKpiSparkline
            values={item.sparkline}
            tone={item.tone}
            changeDirection={changeDirection}
            className={styles.portfolioKpiSparkline}
          />
        ) : null}
      </div>
      {detail ? (
        <div
          className={`${styles.kpiDetail} ${marketChangePresentation(
            item.detail,
            item.sparkline,
            PORTFOLIO_KPI_CHANGE_CLASSES,
          ).className}`}
          data-testid={`module-home-portfolio-kpi-${item.key}-detail`}
          data-change={changeDirection ?? "flat"}
          title={item.detail}
          aria-label={`${item.label}: ${item.detail}`}
        >
          {detail}
        </div>
      ) : null}
    </article>
  );
}

function sourceEvidenceSummary(lines: string[]) {
  const text = lines.join(" ");
  const reportDate = text.match(/report_date=\d{4}-\d{2}-\d{2}/)?.[0];
  const sources = Array.from(new Set(Array.from(text.matchAll(/\bfact_[a-z0-9_]+/g), (match) => match[0])));
  const fallback = text.includes("fallback=none") ? "无回退" : null;
  return uniqueTextParts([
    reportDate ? reportDate.replace("report_date=", "日期 ") : null,
    sources.length > 0 ? `${sources.length} 个正式来源` : `${lines.length} 条证据`,
    fallback,
  ]).join(" · ");
}

function splitKpiValue(value: string) {
  const trimmed = value.trim();
  const match = trimmed.match(/^([+-]?\d[\d,]*(?:\.\d+)?)(.*)$/);

  if (!match) {
    return { number: trimmed, unit: "" };
  }

  return {
    number: match[1],
    unit: match[2].trim(),
  };
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
            <div
              className={styles.decisionActionList}
              data-testid="module-home-portfolio-action-loop"
            >
              {actions.map((action, index) => (
                <Link
                  className={styles.decisionAction}
                  to={action.path}
                  key={action.title}
                  data-testid={index === 0 ? "module-home-portfolio-action-loop-primary" : undefined}
                >
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

function hasAnalyticalOnlySource(decision: ModuleHomeView["decision"]) {
  const readiness = decision?.readiness;
  return Boolean(
    readiness?.sourceFacts.some(
      (fact) =>
        fact.includes("basis=analytical") ||
        fact.includes("formal_use_allowed=false") ||
        fact.includes("quality=warning"),
    ) ||
      readiness?.blockingReasons.some(
        (reason) =>
          reason.includes("basis=analytical") ||
          reason.includes("formal_use_allowed=false") ||
          reason.includes("quality=warning"),
      ),
  );
}

function PortfolioClosureGate({ decision }: { decision: ModuleHomeView["decision"] }) {
  if (!decision?.readiness) {
    return null;
  }

  const { readiness } = decision;
  const riskBlocked = !readiness.riskClosureReady;
  const sourceBlocked = !readiness.decisionReady;
  const analyticalOnly = hasAnalyticalOnlySource(decision);
  const gateTone: ModuleHomeTone = riskBlocked || sourceBlocked ? "watch" : "ok";
  const gateTitle = riskBlocked
    ? "风险张量不可用"
    : sourceBlocked
      ? "决策口径未通过"
      : "风险闭合同日可用";
  const gateDetail = riskBlocked
    ? readiness.riskClosureFact
    : sourceBlocked
      ? readiness.blockingReasons.join("；") || "来源证据未达到决策级口径。"
      : `同日闭合 ${readiness.sourceDates}`;
  const badges = [
    riskBlocked ? "闭合状态已阻断" : "风险张量已闭合",
    analyticalOnly ? "分析口径已隔离" : "正式口径",
    "不使用前端补数",
  ];

  return (
    <section
      className={`${dhStyles.dhCard} ${styles.closureGate} ${riskBlocked ? styles.closureGateBlocked : ""}`}
      data-testid="module-home-portfolio-closure-gate"
      data-state={riskBlocked ? "blocked" : sourceBlocked ? "source-review" : "ready"}
    >
      <div className={styles.closureGateHead}>
        <span>闭合状态</span>
        <strong className={toneClass(gateTone)}>{gateTitle}</strong>
      </div>
      <p className={styles.closureGateDetail}>{compactActionEvidence(gateDetail)}</p>
      <div className={styles.closureGateBadges}>
        {badges.map((badge) => (
          <span key={badge}>{badge}</span>
        ))}
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
  const assetTypePanel = view.distributionPanels?.find((panel) => panel.key === "asset-type");
  const portfolioComparisonPanel = panelByKey(view.detailPanels, "portfolio-comparison");
  const secondaryDistributionPanels =
    view.distributionPanels?.filter((panel) => panel.key !== "asset-type") ?? [];
  const readiness = view.decision?.readiness;
  const riskClosureBlocked = Boolean(readiness && !readiness.riskClosureReady);
  const analyticalOnlySource = hasAnalyticalOnlySource(view.decision);
  const riskTickerUnavailable = riskClosureBlocked || riskPanel?.tone !== "ok";
  const riskTickerUnavailableTitle = riskClosureBlocked ? "风险张量不可用" : "风险读数不可用";
  const riskTickerUnavailableDetail = riskClosureBlocked
    ? `${readiness?.riskClosureFact ?? "风险闭合证据未返回"}，闭合状态已阻断。`
    : riskPanel?.stateDetail;
  const workbenchMeta = [
    `${secondaryDistributionPanels.length} 个结构面板`,
    `${view.statuses.length} 条来源状态`,
    riskClosureBlocked ? "风险闭合待复核" : "风险闭合可用",
  ];
  const kpiGroups = useMemo(() => {
    const { primary, secondary } = splitKpisByPriority(view.kpis);
    return { primary, secondary, scopeNote: kpiScopeNote(view.kpis) };
  }, [view.kpis]);

  const structureTabs = useMemo<PortfolioStructureTab[]>(() => {
    const map = new Map(view.detailPanels?.map((panel) => [panel.key, panel]) ?? []);
    return ANALYSIS_TABS.map((tab) => ({
      ...tab,
      panel: map.get(tab.key),
    }));
  }, [view.detailPanels]);

  const structureGapTabs = structureTabs.filter((tab) => !tab.panel || tab.panel.rows.length === 0);

  const tabItems = useMemo(() => {
    return structureTabs.map((tab) => {
      const panel = tab.panel;
      return {
        key: tab.key,
        label: <StructureTabLabel tab={tab} />,
        children: panel ? (
          <PortfolioStructureTabPanel panel={panel} />
        ) : (
          <p className={`${styles.detailSource} ${styles.toneWatch}`}>
            当前无可用正式结构读数；样例明细不作为业务决策依据。
          </p>
        ),
      };
    });
  }, [structureTabs]);

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
          <section data-testid="module-home-portfolio-review-band" className={styles.portfolioReviewBand}>
            <section data-testid="module-home-portfolio-first-screen" className={styles.portfolioPrimaryGrid}>
              <div className={styles.portfolioPrimaryColumn}>
                <DecisionPanel view={view} />

                <section data-testid="module-home-kpi-strip" className={styles.sectionBlock}>
                  <ModuleHomeSectionHead label="指标" title="核心指标" className={styles.sectionHead} />
                  {kpiGroups.scopeNote ? (
                    <p className={styles.kpiScopeNote} data-testid="module-home-portfolio-kpi-scope-note">
                      {kpiGroups.scopeNote}
                    </p>
                  ) : null}
                  <div className={styles.kpiGridTape}>
                    <div className={styles.kpiGrid}>
                      {kpiGroups.primary.map((item) => (
                        <PortfolioKpiCard item={item} variant="primary" key={item.key} />
                      ))}
                    </div>
                    <div className={`${styles.kpiGrid} ${styles.kpiGridSecondary}`}>
                      {kpiGroups.secondary.map((item) => (
                        <PortfolioKpiCard item={item} variant="secondary" key={item.key} />
                      ))}
                    </div>
                  </div>
                </section>

                <PortfolioRiskTickerBar
                  riskPanel={riskPanel}
                  unavailable={riskTickerUnavailable}
                  unavailableTitle={riskTickerUnavailableTitle}
                  unavailableDetail={compactActionEvidence(riskTickerUnavailableDetail ?? "")}
                />
              </div>
            </section>

            <section data-testid="module-home-portfolio-data-workbench" className={styles.portfolioDataWorkbench}>
              <div className={styles.workbenchMain}>
                  <nav
                    data-testid="module-home-portfolio-data-nav"
                    className={styles.workbenchNav}
                    aria-label="组合数据工作台"
                  >
                    <strong className={styles.workbenchNavTitle}>组合复盘驾驶舱</strong>
                    {WORKBENCH_NAV_ITEMS.map((item) => (
                      <a href={item.href} key={item.href}>
                        <span>{item.code}</span>
                        <strong>{item.label}</strong>
                        <em>{item.detail}</em>
                      </a>
                    ))}
                    <p>结构、归因、明细按业务动作串联，保留来源状态与复核入口。</p>
                  </nav>

                  <section
                    id="portfolio-holdings-workbench"
                    aria-labelledby="portfolio-holdings-workbench-title"
                    data-testid="module-home-portfolio-holdings-workbench"
                    className={`${styles.workbenchSection} ${styles.holdingsWorkbenchSection}`}
                  >
                    <WorkbenchSectionHead
                      titleId="portfolio-holdings-workbench-title"
                      code="图表"
                      title="持仓结构全景"
                      detail="券种、子组合与关键暴露并排复核。"
                      meta={assetTypePanel?.totalDisplay ?? "结构总览待返回"}
                    />
                    <div className={styles.holdingsPanoramaGrid}>
                      <PortfolioHoldingsHeroBand
                        panel={assetTypePanel}
                        portfolioComparisonPanel={portfolioComparisonPanel}
                      />
                      <section
                        id="portfolio-exposure-workbench"
                        aria-labelledby="portfolio-exposure-workbench-title"
                        data-testid="module-home-portfolio-exposure-workbench"
                        className={styles.exposureWorkbenchSection}
                      >
                        <div className={styles.exposureWorkbenchHead}>
                          <span>持仓</span>
                          <h2 id="portfolio-exposure-workbench-title">关键暴露账本</h2>
                          <p>评级、期限、品种集中在一个可扫区域。</p>
                        </div>
                        <PortfolioExposureLedger view={view} />
                      </section>
                    </div>
                  </section>

                  <section
                    id="portfolio-structure-workbench"
                    aria-labelledby="portfolio-structure-workbench-title"
                    data-testid="module-home-portfolio-structure-workbench"
                    className={`${styles.portfolioStructureWorkbench} ${styles.workbenchSection}`}
                  >
                    <WorkbenchSectionHead
                      titleId="portfolio-structure-workbench-title"
                      code="结构"
                      title="结构拆解工作台"
                      detail="子组合、收益率、利差、业务类型统一按表格核对。"
                      meta={`${structureTabs.length} 个结构维度`}
                    />
                    <section
                      data-testid="module-home-portfolio-terminal"
                      className={`${dhStyles.dhCard} ${styles.terminalCard} ${styles.sectionBlock} ${styles.structureTableWorkbench}`}
                    >
                      <div className={styles.structureTableHead}>
                        <div
                          className={styles.structureStatusBar}
                          data-testid="module-home-structure-status-summary"
                        >
                          {structureStatusSummary(structureTabs)}
                        </div>
                        <span>结构明细按页签核对</span>
                      </div>
                      {structureGapTabs.length > 0 ? (
                        <div className={styles.structureGapActions} data-testid="module-home-structure-gap-actions">
                          {structureGapTabs.map((tab) => (
                            <Link
                              key={tab.key}
                              className={styles.structureGapAction}
                              to={`/bond-dashboard?report_date=${encodeURIComponent(bondReportDate || "-")}#${tab.key}`}
                              data-testid={`module-home-structure-gap-action-${tab.key}`}
                            >
                              {tab.label}为空 · 去债券总览复核
                            </Link>
                          ))}
                        </div>
                      ) : null}
                      <Tabs items={tabItems} />
                    </section>
                  </section>

                  <section
                    id="portfolio-risk-workbench"
                    aria-labelledby="portfolio-risk-workbench-title"
                    data-testid="module-home-portfolio-closure-band"
                    className={`${styles.portfolioClosureBand} ${styles.workbenchSection}`}
                  >
                    <WorkbenchSectionHead
                      titleId="portfolio-risk-workbench-title"
                      code="收益"
                      title={riskClosureBlocked || analyticalOnlySource ? "分析读数与归因" : "收益与风险"}
                      detail="闭合前门、风险读数、收益归因和日期闭合线并排复核。"
                      meta={riskClosureBlocked ? "闭合阻断" : "可进入复核"}
                    />
                    <div className={styles.closureWorkbenchGrid}>
                      <PortfolioClosureGate decision={view.decision} />
                      {riskPanel ? (
                        <article className={`${styles.closureReviewCard} ${styles.closureReviewCardRisk}`} data-testid={detailPanelTestId(riskPanel.key)}>
                          <ModuleHomeSectionHead label="风险" title="风险读数" className={styles.sectionHead} />
                          <DetailPanelBody panel={riskPanel} embedded />
                        </article>
                      ) : null}
                      {pnlPanel ? (
                        <article className={styles.closureReviewCard} data-testid={detailPanelTestId(pnlPanel.key)}>
                          <ModuleHomeSectionHead label="归因" title="收益归因" className={styles.sectionHead} />
                          <DetailPanelBody panel={pnlPanel} embedded />
                        </article>
                      ) : null}
                      {basisPanel ? (
                        <article className={styles.closureReviewCard} data-testid={detailPanelTestId(basisPanel.key)}>
                          <ModuleHomeSectionHead label="来源" title="日期闭合线" className={styles.sectionHead} />
                          <DetailPanelBody panel={basisPanel} embedded />
                        </article>
                      ) : null}
                    </div>
                  </section>

                  <section
                    id="portfolio-source-workbench"
                    aria-labelledby="portfolio-source-workbench-title"
                    data-testid="module-home-portfolio-source-workbench"
                    className={`${styles.sourceWorkbenchSection} ${styles.workbenchSection}`}
                  >
                    <h2 id="portfolio-source-workbench-title" className={styles.srOnly}>
                      组合复盘摘要
                    </h2>
                    <section data-testid="module-home-holdings-structure" className={styles.summaryLedgerCard}>
                      <ModuleHomeSectionHead label="复盘" title="评级 / 期限 / 行业分布" className={styles.sectionHead} />
                      <PortfolioChartSnapshot panels={secondaryDistributionPanels} />
                    </section>

                    <section data-testid="module-home-briefing" className={styles.summaryLedgerCard}>
                      <ModuleHomeSectionHead label="复盘" title="组合摘要" className={styles.sectionHead} />
                      <div className={styles.briefGrid} data-testid="module-home-briefing-ledger">
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

                    <section
                      data-testid="module-home-status-strip"
                      className={`${dhStyles.dhCard} ${styles.summaryLedgerCard} ${styles.statusStrip}`}
                    >
                      <ModuleHomeSectionHead label="复盘" title="来源与状态" className={styles.sectionHead} />
                      <div className={styles.statusGrid} data-testid="module-home-status-ledger">
                        {view.statuses.slice(0, 4).map((item) => (
                          <div className={styles.statusCell} key={item.key}>
                            <span>{item.label}</span>
                            <b className={toneClass(item.tone)}>{item.value}</b>
                            <em>{item.detail}</em>
                          </div>
                        ))}
                      </div>
                    </section>
                  </section>

                  <section
                    id="portfolio-action-workbench"
                    aria-labelledby="portfolio-action-workbench-title"
                    data-testid="module-home-portfolio-action-workbench"
                    className={`${styles.workbenchSection} ${styles.actionWorkbenchSection}`}
                  >
                    <WorkbenchSectionHead
                      titleId="portfolio-action-workbench-title"
                      code="入口"
                      title="快捷分析入口 / 全部明细入口"
                      detail="按业务动作而不是页面名称分组。"
                      meta={workbenchMeta.join(" · ")}
                    />
                    <div className={styles.actionMatrixGrid}>
                      <section
                        data-testid="module-home-portfolio-quick-access"
                        className={`${styles.sectionBlock} ${styles.quickAccessBlock}`}
                      >
                        <ModuleHomeSectionHead label="快捷" title="分析入口" className={styles.sectionHead} />
                        <div className={styles.quickAccessGrid}>
                          {PORTFOLIO_QUICK_ACCESS_TILES.map((tile) => (
                            <Link
                              key={tile.key}
                              to={tile.path}
                              className={`${dhStyles.dhCard} ${dhStyles.dhTerminalQuick} ${styles.quickAccessCard}`}
                              title={tile.description}
                              data-testid={`module-home-portfolio-quick-${tile.key}`}
                            >
                              <span>{tile.icon}</span>
                              <b>{tile.label}</b>
                              <em>{tile.badge}</em>
                            </Link>
                          ))}
                        </div>
                      </section>

                      <section data-testid="module-home-drilldowns" className={`${styles.sectionBlock} ${styles.drilldownBlock}`}>
                        <ModuleHomeSectionHead label="明细" title="全部分组入口" className={styles.sectionHead} />
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
                      </section>
                    </div>
                    {view.dataNote.lines.length > 0 ? (
                      <details
                        className={`${styles.dataNote} ${styles.dataNoteDisclosure}`}
                        data-testid="module-home-data-note"
                      >
                        <summary>
                          <span>来源证据摘要</span>
                          <strong>{sourceEvidenceSummary(view.dataNote.lines)}</strong>
                        </summary>
                        <span className={styles.dataNoteBody}>
                          {compactActionEvidence(view.dataNote.lines.join(" "))}
                        </span>
                      </details>
                    ) : null}
                  </section>
                </div>
            </section>
          </section>
        </section>
      </main>
    </>
  );
}
