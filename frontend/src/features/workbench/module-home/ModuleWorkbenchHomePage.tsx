import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { useApiClient } from "../../../api/client";
import {
  buildModuleHomeView,
  moduleHomeQueriesMemoDeps,
  type ModuleHomeDetailPanel,
  type ModuleHomeTone,
} from "./moduleHomeModel";
import {
  moduleWorkbenchHomeConfigs,
  type ModuleWorkbenchHomeKind,
} from "./moduleHomeConfig";
import styles from "./moduleWorkbenchHome.module.css";

type ModuleWorkbenchHomePageProps = {
  kind: ModuleWorkbenchHomeKind;
};

function toneClassName(tone: ModuleHomeTone) {
  if (tone === "ok") {
    return styles.toneOk;
  }
  if (tone === "watch") {
    return styles.toneWatch;
  }
  if (tone === "error") {
    return styles.toneError;
  }
  return styles.toneMuted;
}

function statePillClassName(tone: ModuleHomeTone) {
  if (tone === "ok") {
    return `${styles.pill} ${styles.pillOk}`;
  }
  if (tone === "error") {
    return `${styles.pill} ${styles.pillError}`;
  }
  if (tone === "watch") {
    return `${styles.pill} ${styles.pillWatch}`;
  }
  return styles.pill;
}

function currentYear() {
  return new Date().getFullYear();
}

function riskDetailPanelTestId(panelKey: string) {
  if (panelKey === "risk-tensor-detail") {
    return "module-home-risk-tensor";
  }
  if (panelKey === "cashflow-projection-detail") {
    return "module-home-cashflow";
  }
  return "module-home-detail-panels";
}

function performanceDetailPanelTestId(panelKey: string) {
  if (panelKey === "kpi-metric-detail") {
    return "module-home-kpi-detail";
  }
  if (panelKey === "business-pnl-detail") {
    return "module-home-business-pnl";
  }
  return "module-home-detail-panels";
}

function governanceDetailPanelTestId(panelKey: string) {
  if (panelKey === "source-status") {
    return "module-home-source-status";
  }
  if (panelKey === "cube-dimensions") {
    return "module-home-cube-dimensions";
  }
  if (panelKey === "health-checks") {
    return "module-home-health-checks";
  }
  return "module-home-detail-panels";
}

function normalizedDetailSectionTitle(title: string) {
  if (title === "KRD 明细") {
    return "KRD 分布";
  }
  if (title === "会计分类 DV01") {
    return "DV01 构成";
  }
  if (title === "现金流预测") {
    return "久期与敏感度";
  }
  return title;
}

function normalizedDetailPanelTitle(title: string) {
  if (title === "现金流与缺口") {
    return "现金流预测";
  }
  return title;
}

function DetailRows({ rows }: { rows: ModuleHomeDetailPanel["rows"] }) {
  return (
    <ul className={styles.detailList}>
      {rows.map((row) => (
        <li className={styles.detailRow} key={row.key}>
          <div className={styles.detailRowTop}>
            <span className={styles.detailLabel}>{row.label}</span>
            <span className={`${styles.detailValue} ${styles.num} ${toneClassName(row.tone)}`}>
              {row.value}
            </span>
            <span className={`${styles.detailDate} ${styles.num}`}>{row.tradeDate}</span>
          </div>
          <span className={styles.detailSource}>{row.source}</span>
        </li>
      ))}
    </ul>
  );
}

function DetailPanelBody({
  panel,
  variant = "nested",
}: {
  panel: ModuleHomeDetailPanel;
  variant?: "nested" | "standalone";
}) {
  const sections = panel.sections?.filter((section) => section.rows.length > 0) ?? [];
  const hasSections = sections.length > 0;

  return (
    <article className={styles.detailPanel}>
      {variant === "nested" ? (
        <>
          <div className={styles.detailHead}>
            <span className={styles.detailTitle}>{normalizedDetailPanelTitle(panel.title)}</span>
            <span className={`${styles.detailState} ${toneClassName(panel.tone)}`}>
              {panel.stateLabel}
            </span>
          </div>
          <span className={styles.detailMeta}>{panel.meta}</span>
        </>
      ) : (
        <div className={styles.detailHead}>
          <span className={`${styles.detailState} ${toneClassName(panel.tone)}`}>
            {panel.stateLabel}
          </span>
        </div>
      )}
      {hasSections ? (
        <div className={styles.detailSections}>
          {sections.map((section) => (
            <section className={styles.detailSection} key={section.key}>
              <div className={styles.detailSectionHeader}>
                <span className={styles.detailTitle}>
                  {normalizedDetailSectionTitle(section.title)}
                </span>
                {section.subtitle ? (
                  <span className={styles.detailMeta}>{section.subtitle}</span>
                ) : null}
              </div>
              <DetailRows rows={section.rows} />
            </section>
          ))}
        </div>
      ) : panel.rows.length > 0 ? (
        <DetailRows rows={panel.rows} />
      ) : (
        <p className={`${styles.detailEmpty} ${toneClassName(panel.tone)}`}>{panel.stateDetail}</p>
      )}
    </article>
  );
}

export default function ModuleWorkbenchHomePage({
  kind,
}: ModuleWorkbenchHomePageProps) {
  const client = useApiClient();

  const choiceLatestQuery = useQuery({
    queryKey: ["module-home", "choice-latest", client.mode],
    queryFn: () => client.getChoiceMacroLatest(),
    enabled: kind === "market",
    retry: false,
    staleTime: 60_000,
  });
  const marketRatesQuery = useQuery({
    queryKey: ["module-home", "market-rates", client.mode],
    queryFn: () => client.getMarketDataRates(),
    enabled: kind === "market",
    retry: false,
    staleTime: 60_000,
  });
  const marketCatalogQuery = useQuery({
    queryKey: ["module-home", "market-catalog", client.mode],
    queryFn: () => client.getMarketDataCatalog(),
    enabled: kind === "market",
    retry: false,
    staleTime: 60_000,
  });

  const riskDatesQuery = useQuery({
    queryKey: ["module-home", "risk-dates", client.mode],
    queryFn: () => client.getRiskTensorDates(),
    enabled: kind === "risk",
    retry: false,
    staleTime: 60_000,
  });
  const riskReportDate = riskDatesQuery.data?.result.report_dates[0] ?? "";
  const riskTensorQuery = useQuery({
    queryKey: ["module-home", "risk-tensor", client.mode, riskReportDate],
    queryFn: () => client.getRiskTensor(riskReportDate),
    enabled: kind === "risk" && Boolean(riskReportDate),
    retry: false,
    staleTime: 60_000,
  });
  const cashflowQuery = useQuery({
    queryKey: ["module-home", "cashflow", client.mode, riskReportDate],
    queryFn: () => client.getCashflowProjection(riskReportDate),
    enabled: kind === "risk" && Boolean(riskReportDate),
    retry: false,
    staleTime: 60_000,
  });

  const year = useMemo(() => currentYear(), []);
  const kpiOwnersQuery = useQuery({
    queryKey: ["module-home", "kpi-owners", client.mode, year],
    queryFn: () => client.getKpiOwners({ year, is_active: true }),
    enabled: kind === "performance",
    retry: false,
    staleTime: 60_000,
  });
  const firstOwnerId = kpiOwnersQuery.data?.owners[0]?.owner_id;
  const kpiSummaryQuery = useQuery({
    queryKey: ["module-home", "kpi-summary", client.mode, year, firstOwnerId ?? "none"],
    queryFn: () =>
      client.getKpiValuesSummary({
        owner_id: firstOwnerId ?? 0,
        year,
        period_type: "YEAR",
      }),
    enabled: kind === "performance" && firstOwnerId !== undefined,
    retry: false,
    staleTime: 60_000,
  });
  const pnlYtdQuery = useQuery({
    queryKey: ["module-home", "pnl-ytd", client.mode, year],
    queryFn: () => client.getPnlByBusinessYtd(year),
    enabled: kind === "performance",
    retry: false,
    staleTime: 60_000,
  });

  const healthLiveQuery = useQuery({
    queryKey: ["module-home", "health-live", client.mode],
    queryFn: () => client.getHealthLive(),
    enabled: kind === "governance",
    retry: false,
    staleTime: 60_000,
  });
  const healthSummaryQuery = useQuery({
    queryKey: ["module-home", "health-summary", client.mode],
    queryFn: () => client.getHealthSummary(),
    enabled: kind === "governance",
    retry: false,
    staleTime: 60_000,
  });
  const sourceFoundationQuery = useQuery({
    queryKey: ["module-home", "source-foundation", client.mode],
    queryFn: () => client.getSourceFoundation(),
    enabled: kind === "governance",
    retry: false,
    staleTime: 60_000,
  });
  const cubeDimensionsQuery = useQuery({
    queryKey: ["module-home", "cube-dimensions", client.mode, "bond_analytics"],
    queryFn: () => client.getCubeDimensions("bond_analytics"),
    enabled: kind === "governance",
    retry: false,
    staleTime: 60_000,
  });

  const queries = {
    choiceLatest: choiceLatestQuery,
    marketRates: marketRatesQuery,
    marketCatalog: marketCatalogQuery,
    riskDates: riskDatesQuery,
    riskTensor: riskTensorQuery,
    cashflow: cashflowQuery,
    kpiOwners: kpiOwnersQuery,
    kpiSummary: kpiSummaryQuery,
    pnlYtd: pnlYtdQuery,
    healthLive: healthLiveQuery,
    healthSummary: healthSummaryQuery,
    sourceFoundation: sourceFoundationQuery,
    cubeDimensions: cubeDimensionsQuery,
  };
  const config = moduleWorkbenchHomeConfigs[kind];
  const view = useMemo(
    () => buildModuleHomeView(kind, client, queries),
    [kind, client, ...moduleHomeQueriesMemoDeps(queries)],
  );
  const isRiskView = view.kind === "risk";
  const decisionBand = view.decision ? (
    <section className={styles.decisionBand} data-testid="module-home-decision">
      <div className={styles.decisionMain}>
        <span className={`${styles.decisionKicker} ${toneClassName(view.decision.tone)}`}>
          {view.decision.title}
        </span>
        <strong className={`${styles.decisionConclusion} ${toneClassName(view.decision.tone)}`}>
          {view.decision.conclusion}
        </strong>
        <span className={styles.decisionDetail}>{view.decision.detail}</span>
      </div>
      <div className={styles.decisionFacts}>
        {view.decision.facts.map((fact) => (
          <span className={styles.decisionFact} key={fact.label}>
            <span>{fact.label}</span>
            <strong className={`${styles.num} ${toneClassName(fact.tone)}`}>{fact.value}</strong>
          </span>
        ))}
      </div>
    </section>
  ) : null;
  const kpiStrip = (
    <section className={styles.kpiStrip} data-testid="module-home-kpi-strip">
      {view.kpis.map((item) => (
        <article className={styles.kpi} key={item.key}>
          <span className={styles.kpiLabel}>{item.label}</span>
          <strong className={`${styles.kpiValue} ${styles.num} ${toneClassName(item.tone)}`}>
            {item.value}
          </strong>
          <span className={styles.kpiDetail}>{item.detail}</span>
        </article>
      ))}
    </section>
  );
  const statusStrip = (
    <section className={styles.statusStrip} data-testid="module-home-status-strip">
      {view.statuses.map((item) => (
        <article className={styles.statusItem} key={item.key}>
          <div className={styles.statusTop}>
            <span className={styles.statusLabel}>{item.label}</span>
            <strong className={`${styles.statusValue} ${styles.num} ${toneClassName(item.tone)}`}>
              {item.value}
            </strong>
          </div>
          <span className={styles.statusDetail}>{item.detail}</span>
        </article>
      ))}
    </section>
  );
  const stateTone =
    view.stateLabel === "读取失败"
      ? "error"
      : view.stateLabel === "部分失败"
        ? "watch"
      : view.stateLabel === "读取中"
        ? "muted"
        : "ok";

  return (
    <section className={styles.moduleHome} data-testid="module-workbench-home">
      <header className={styles.topbar}>
        <div className={styles.titleBlock}>
          <div className={styles.titleRow}>
            <span className={styles.titleBar} aria-hidden="true" />
            <h1 className={styles.title}>{view.title}</h1>
            <span className={statePillClassName(stateTone)}>{view.stateLabel}</span>
          </div>
          <p className={styles.question}>{view.question}</p>
          <p className={styles.summary}>{view.summary}</p>
        </div>
        <div className={styles.topMeta}>
          <div className={styles.credibilityStrip}>
            <span className={styles.credibilityLabel}>来源</span>
            <span className={styles.pill}>{view.sourceScope}</span>
          </div>
          <div className={styles.credibilityStrip}>
            <span className={styles.credibilityLabel}>状态</span>
            <span className={statePillClassName(stateTone)}>{view.stateDetail}</span>
          </div>
        </div>
      </header>

      {isRiskView ? (
        <div className={styles.riskReviewDesk} data-testid="module-home-risk-review-desk">
          {decisionBand ? (
            <div data-testid="module-home-risk-decision-zone">{decisionBand}</div>
          ) : null}
          <div className={styles.riskReadoutBand} data-testid="module-home-risk-readout-band">
            <div data-testid="module-home-risk-summary-cards">{kpiStrip}</div>
            {statusStrip}
          </div>
        </div>
      ) : (
        decisionBand
      )}

      <div className={styles.layout}>
        <main className={styles.main}>
          {isRiskView ? null : kpiStrip}

          {isRiskView ? null : statusStrip}

          <section className={styles.card} data-testid="module-home-briefing">
            <div className={styles.sectionTitle}>
              <span>主结论区</span>
            </div>
            <div className={styles.briefGrid}>
              {view.briefings.map((item) => (
                <article className={styles.brief} key={item.title}>
                  <span className={styles.briefTitle}>{item.title}</span>
                  <strong
                    className={`${styles.briefConclusion} ${styles.num} ${toneClassName(item.tone)}`}
                  >
                    {item.conclusion}
                  </strong>
                  <span className={styles.briefEvidence}>{item.evidence}</span>
                </article>
              ))}
            </div>
          </section>

          {view.distributionPanels && view.distributionPanels.length > 0 ? (
            <section className={styles.card} data-testid="module-home-holdings-structure">
              <div className={styles.sectionTitle}>
                <span>持仓结构</span>
                <span className={styles.sectionMeta}>{view.distributionPanels[0]?.meta}</span>
              </div>
              <div className={styles.distributionGrid}>
                {view.distributionPanels.map((panel) => (
                  <article className={styles.distributionPanel} key={panel.key}>
                    <div className={styles.distributionHead}>
                      <span className={styles.distributionTitle}>{panel.title}</span>
                      <span className={`${styles.distributionState} ${toneClassName(panel.tone)}`}>
                        {panel.stateLabel}
                      </span>
                    </div>
                    <span className={styles.distributionMeta}>{panel.meta}</span>
                    {panel.rows.length > 0 ? (
                      <ul className={styles.distributionList}>
                        {panel.rows.map((row) => (
                          <li className={styles.distributionRow} key={row.key}>
                            <div className={styles.distributionRowTop}>
                              <span className={styles.distributionLabel}>{row.label}</span>
                              <span className={`${styles.distributionValue} ${styles.num}`}>
                                {row.marketValue}
                              </span>
                              <span className={`${styles.distributionShare} ${styles.num}`}>
                                {row.share}
                              </span>
                            </div>
                            <div className={styles.distBarTrack} aria-hidden="true">
                              <div
                                className={styles.distBarFill}
                                style={{ width: `${row.barPct}%` }}
                              />
                            </div>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className={`${styles.distributionEmpty} ${toneClassName(panel.tone)}`}>
                        {panel.stateDetail}
                      </p>
                    )}
                  </article>
                ))}
              </div>
            </section>
          ) : null}

          {view.detailPanels && view.detailPanels.length > 0 ? (
            view.kind === "risk" ? (
              <section className={styles.card} data-testid="module-home-risk-evidence">
                <div className={styles.sectionTitle}>
                  <span data-testid="module-home-risk-evidence-heading">
                    风险证据板
                  </span>
                  <span className={styles.sectionMeta}>字段级读数，不在首页补算</span>
                </div>
                <div className={styles.detailGrid}>
                  {view.detailPanels.map((panel) => (
                    <div data-testid={riskDetailPanelTestId(panel.key)} key={panel.key}>
                      <DetailPanelBody panel={panel} />
                    </div>
                  ))}
                </div>
              </section>
            ) : view.kind === "performance" ? (
              view.detailPanels.map((panel) => (
                <section
                  className={styles.card}
                  data-testid={performanceDetailPanelTestId(panel.key)}
                  key={panel.key}
                >
                  <div className={styles.sectionTitle}>
                    <span>{panel.title}</span>
                    <span className={styles.sectionMeta}>{panel.meta}</span>
                  </div>
                  <DetailPanelBody panel={panel} variant="standalone" />
                </section>
              ))
            ) : view.kind === "governance" ? (
              view.detailPanels.map((panel) => (
                <section
                  className={styles.card}
                  data-testid={governanceDetailPanelTestId(panel.key)}
                  key={panel.key}
                >
                  <div className={styles.sectionTitle}>
                    <span>{panel.title}</span>
                    <span className={styles.sectionMeta}>{panel.meta}</span>
                  </div>
                  <DetailPanelBody panel={panel} variant="standalone" />
                </section>
              ))
            ) : (
              <section
                className={styles.card}
                data-testid={
                  view.kind === "market" ? "module-home-rate-snapshot" : "module-home-detail-panels"
                }
              >
                <div className={styles.sectionTitle}>
                  <span>市场数据</span>
                  <span className={styles.sectionMeta}>{view.detailPanels[0]?.meta}</span>
                </div>
                <div className={styles.detailGrid}>
                  {view.detailPanels.map((panel) => (
                    <DetailPanelBody panel={panel} key={panel.key} />
                  ))}
                </div>
              </section>
            )
          ) : null}
        </main>

        <aside className={styles.rail}>
          <section className={styles.railCard} data-testid="module-home-drilldowns">
            <div className={styles.sectionTitle}>
              <span>下钻入口</span>
            </div>
            <p className={styles.railLead}>
              首页只做摘要和状态聚合，明细解释进入对应页面继续看。
            </p>
            <div className={styles.drillList}>
              {config.drilldowns.map((item) => (
                <Link className={styles.drill} to={item.path} key={item.key}>
                  <span className={styles.drillHead}>
                    <strong className={styles.drillTitle}>{item.label}</strong>
                    <span className={styles.drillBadge}>{item.statusLabel}</span>
                  </span>
                  <span className={styles.drillDesc}>{item.description}</span>
                </Link>
              ))}
            </div>
          </section>

          <section className={styles.railCard} data-testid="module-home-data-note">
            <div className={styles.sectionTitle}>
              <span>{view.dataNote.title}</span>
            </div>
            <ul className={styles.dataNote}>
              {view.dataNote.lines.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </section>
        </aside>
      </div>
    </section>
  );
}
