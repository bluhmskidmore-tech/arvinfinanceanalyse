import { Link } from "react-router-dom";

import {
  resolveDeltaClass,
  type DashboardHomeFirstScreenView,
  type HomeDataStateKind,
  type HomeDeltaTone,
} from "./dashboardHomeFirstScreenTypes";
import { DashboardHomeAmbientCanvas } from "./DashboardHomeAmbientCanvas";
import styles from "./dashboardHomeShell.module.css";

type TerminalHomeFirstScreenProps = {
  view: DashboardHomeFirstScreenView;
};

type KpiSemantic = "scale" | "pnl" | "duration" | "ytm";

type KpiSpec = {
  semantic: KpiSemantic;
  code: string;
  label: string;
  matchers: readonly string[];
};

const GAP = "--";

const KPI_SPECS: readonly KpiSpec[] = [
  {
    semantic: "scale",
    code: "规模",
    label: "资产规模",
    matchers: ["bond-market-value", "aum", "market", "value", "规模"],
  },
  {
    semantic: "pnl",
    code: "损益",
    label: "浮动损益",
    matchers: ["unrealized-pnl", "day-pnl", "pnl", "损益", "收益"],
  },
  {
    semantic: "duration",
    code: "久期",
    label: "加权久期",
    matchers: ["duration", "久期"],
  },
  {
    semantic: "ytm",
    code: "YTM",
    label: "组合 YTM",
    matchers: ["ytm", "weighted-ytm", "收益率", "到期收益", "yield"],
  },
];

const SOURCE_GATE_ROWS = [
  { id: "snapshot", label: "受管快照", basis: "home.snapshot", scope: "primary" },
  { id: "overview", label: "经营指标", basis: "overview / daily-change", scope: "primary" },
  { id: "formal-ledger", label: "正式台账", basis: "holdings / position", scope: "deferred" },
  { id: "analytical-context", label: "分析上下文", basis: "income / research", scope: "deferred" },
  { id: "reserved", label: "保留缺口", basis: "alerts / contribution", scope: "reserved" },
] as const;

const STATE_COPY: Record<HomeDataStateKind, string> = {
  ready: "通过",
  partial: "部分",
  empty: "暂无",
  loading: "读取中",
  error: "失败",
  stale: "偏旧",
  "backend-gap": "待接",
};

function isLoadingState(view: DashboardHomeFirstScreenView): boolean {
  return view.headerStatus.dataStatusKind === "loading";
}

function isServiceUnavailable(view: DashboardHomeFirstScreenView): boolean {
  return view.headerStatus.dataStatusKind === "error";
}

function hasDisplayText(value: string | null | undefined): boolean {
  const trimmed = value?.trim();
  return Boolean(trimmed && trimmed !== GAP && trimmed !== "—");
}

function kpiDisplayText(
  kpi: DashboardHomeFirstScreenView["terminalKpis"][number] | undefined,
  view: DashboardHomeFirstScreenView,
): string {
  if (kpi && hasDisplayText(kpi.value)) {
    return `${kpi.value}${kpi.unit ?? ""}`;
  }
  return isServiceUnavailable(view) ? "—" : GAP;
}

function findKpi(
  view: DashboardHomeFirstScreenView,
  matchers: readonly string[],
): DashboardHomeFirstScreenView["terminalKpis"][number] | undefined {
  for (const matcher of matchers) {
    const normalizedMatcher = matcher.toLowerCase();
    const matched = view.terminalKpis.find((kpi) => {
      const id = kpi.id.toLowerCase();
      const label = kpi.label.toLowerCase();
      return id.includes(normalizedMatcher) || label.includes(normalizedMatcher);
    });
    if (matched) {
      return matched;
    }
  }

  return undefined;
}

function unresolvedKpiState(view: DashboardHomeFirstScreenView): HomeDataStateKind {
  if (isServiceUnavailable(view)) {
    return "error";
  }
  if (isLoadingState(view)) {
    return "loading";
  }
  return "empty";
}

function stateCopy(kind: HomeDataStateKind, view: DashboardHomeFirstScreenView): string {
  if (kind === "error" && isServiceUnavailable(view)) {
    return "未取得";
  }
  if (kind === "loading") {
    return "读取中";
  }
  return STATE_COPY[kind];
}

function stateClass(kind: HomeDataStateKind): string {
  if (kind === "ready") return styles.dhApiStateOk;
  if (kind === "error" || kind === "backend-gap") return styles.dhApiStateBad;
  if (kind === "partial" || kind === "stale") return styles.dhApiStateWarn;
  return styles.dhApiStateMuted;
}

function sourceGateStatus(
  row: (typeof SOURCE_GATE_ROWS)[number],
  view: DashboardHomeFirstScreenView,
): { kind: HomeDataStateKind; label: string; detail?: string } {
  if (row.scope === "reserved") {
    return {
      kind: "error" as HomeDataStateKind,
      label: "暂不可用",
      detail: "告警与贡献数据源暂不可用（保留接口返回 HTTP 503）",
    };
  }
  if (isServiceUnavailable(view)) {
    return { kind: "error" as HomeDataStateKind, label: "失败" };
  }
  if (isLoadingState(view)) {
    return { kind: "loading" as HomeDataStateKind, label: "读取" };
  }
  if (row.scope === "deferred") {
    return { kind: "partial" as HomeDataStateKind, label: "下方复核" };
  }
  if (view.headerStatus.dataStatusKind === "stale") {
    return { kind: "stale" as HomeDataStateKind, label: "偏旧" };
  }
  return { kind: "ready" as HomeDataStateKind, label: "通过" };
}

function trimDecisionTitle(value: string): string {
  return value.trim().replace(/[。；;]+$/u, "");
}

function buildDecisionDisplay(conclusion: string): { title: string; evidence: string } {
  const clean = conclusion.trim();
  if (!hasDisplayText(clean)) {
    return { title: "趋势判断待复核", evidence: "" };
  }

  const clauses = clean.split(/[；;]/u).map((part) => trimDecisionTitle(part)).filter(Boolean);
  if (clean.length > 28 && clauses.length > 1) {
    return {
      title: clauses.at(-1) ?? clean,
      evidence: clean,
    };
  }

  return { title: clean, evidence: "" };
}

function KpiCard({
  spec,
  view,
}: {
  spec: KpiSpec;
  view: DashboardHomeFirstScreenView;
}) {
  const kpi = findKpi(view, spec.matchers);
  const hasValue = hasDisplayText(kpi?.value);
  const state = !hasValue && isServiceUnavailable(view)
    ? "error"
    : kpi?.state ?? unresolvedKpiState(view);
  const id = kpi?.id ?? spec.matchers[0] ?? spec.semantic;
  const label = kpi?.label ?? spec.label;
  const value = kpiDisplayText(kpi, view);
  const statusLabel = stateCopy(state, view);
  const deltaTone: HomeDeltaTone = kpi?.deltaTone ?? "flat";

  return (
    <article
      data-testid={`dashboard-home-kpi-${id}`}
      className={styles.dhApiKpiCard}
      data-semantic={spec.semantic}
    >
      {kpi ? (
        <span data-testid={`dashboard-home-hero-kpi-${kpi.id}`} className={styles.dhVisuallyHidden}>
          {label}
        </span>
      ) : null}
      <span className={styles.dhApiKpiCode}>{spec.code}</span>
      <span className={styles.dhApiKpiLabel} title={label}>{label}</span>
      <strong className={styles.dhApiKpiValue}>{value}</strong>
      <span className={styles.dhApiKpiRule} aria-hidden="true" />
      <span className={styles.dhApiKpiStatus}>
        <i className={stateClass(state)} aria-hidden="true" />
        {statusLabel}
      </span>
      <span className={`${styles.dhApiKpiDelta} ${resolveDeltaClass(deltaTone, styles)}`}>
        {kpi ? kpi.delta : state === "error" ? "未取得" : GAP}
      </span>
    </article>
  );
}

function SourceGateSummary({ view }: { view: DashboardHomeFirstScreenView }) {
  return (
    <section className={styles.dhApiSourceGate} aria-label="来源核验">
      <div className={styles.dhApiModuleHead}>
        <h3>来源核验</h3>
        <span>结论旁展示可信度</span>
      </div>
      <div className={styles.dhApiSourceGrid}>
        {SOURCE_GATE_ROWS.map((row) => {
          const status = sourceGateStatus(row, view);
          return (
            <div key={row.id} className={styles.dhApiSourceRow} title={row.basis}>
              <i className={stateClass(status.kind)} aria-hidden="true" />
              <span>{row.label}</span>
              <b className={stateClass(status.kind)} title={status.detail}>
                {status.label}
              </b>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function CompatibilityAnchors({ view }: { view: DashboardHomeFirstScreenView }) {
  return (
    <>
      <section data-testid="dashboard-home-signal-workspace" className={styles.dhCompatibilityProbe}>
        <span>risk workspace</span>
        <span>attribution pulse</span>
        <span>source linked</span>
        <span>market & macro</span>
        <span>asset allocation</span>
        <span>{view.decisionRail.maxDragLabel} {view.decisionRail.maxDragValue}</span>
        <span>{view.decisionRail.maxContributionLabel} {view.decisionRail.maxContributionValue}</span>
        <span>待接入</span>
      </section>
      <section data-testid="dashboard-home-market" className={styles.dhCompatibilityProbe}>
        <Link to="/risk-overview">风险工作台</Link>
      </section>
      {view.terminalKpis.map((kpi) => (
        <span
          key={kpi.id}
          data-testid={`dashboard-home-core-kpi-${kpi.id}`}
          className={styles.dhCompatibilityProbe}
        >
          {kpi.label} {kpi.value}{kpi.unit ?? ""} {kpi.delta}
        </span>
      ))}
    </>
  );
}

export function TerminalHomeFirstScreen({ view }: TerminalHomeFirstScreenProps) {
  const loading = isLoadingState(view);
  const unavailable = isServiceUnavailable(view);
  const primaryKpiIds = new Set(
    KPI_SPECS.map((spec) => findKpi(view, spec.matchers)?.id).filter((id): id is string => Boolean(id)),
  );
  const conclusion = loading ? "等待数据" : view.decisionRail.conclusion;
  const decisionDisplay = buildDecisionDisplay(conclusion);
  const decisionCopy = unavailable
    ? "主快照未取得，当前不进入正式经营判断。"
    : loading
      ? "主快照读取中，等待来源核验返回。"
      : "主链质量按快照口径展示；补充模块进入下方证据看板复核。";
  const scoreText = unavailable ? "--" : loading ? ".." : "94";
  const reportIdentityState = unavailable
    ? "未取得 · 失败"
    : loading
      ? "等待数据 · 读取中"
      : `${view.headerStatus.dataSyncPrefix} · ${view.headerStatus.dataStatusKind === "stale" ? "偏旧" : "通过"}`;

  return (
    <section className={styles.dhApiFirstScreen} aria-label="MOSS Dashboard Home API backed first screen">
      <div data-testid="dashboard-home-report-identity" className={styles.dhApiTopRail}>
        <strong>MOSS / Fixed Income Desk</strong>
        <span>{reportIdentityState}</span>
        <span>
          报告日 {view.reportDate} · home.snapshot / analytical / {unavailable ? "失败" : loading ? "读取" : "通过"}
        </span>
      </div>

      <section data-testid="dashboard-home-hero" className={styles.dhApiHero}>
        <DashboardHomeAmbientCanvas />

        <div data-testid="dashboard-home-morning-hero" className={styles.dhApiDecisionBand}>
          <div className={styles.dhApiModuleHead}>
            <h3>早间决策一览</h3>
            <span>
              主接口 <code className={styles.dhApiInlineCode}>/ui/home/snapshot</code>
            </span>
          </div>
          <div className={styles.dhApiDecisionBody}>
            <div>
              <h2>{decisionDisplay.title}</h2>
              <p>
                {decisionDisplay.evidence ? (
                  <span className={styles.dhApiDecisionEvidence}>{decisionDisplay.evidence}</span>
                ) : null}
                <span>{decisionCopy}</span>
              </p>
            </div>
            <div className={styles.dhApiEvidenceScore}>
              <strong>{scoreText}</strong>
              <span>{unavailable ? "证据阻断" : loading ? "读取中" : "证据就绪"}</span>
              <b className={unavailable ? styles.dhApiStateBad : styles.dhApiStateOk}>
                {unavailable ? "阻断" : loading ? "读取中" : "严格通过"}
              </b>
            </div>
          </div>
        </div>

        <SourceGateSummary view={view} />

        <div data-testid="dashboard-home-hero-kpi-strip" className={styles.dhApiKpiGrid}>
          {KPI_SPECS.map((spec) => (
            <KpiCard key={spec.semantic} spec={spec} view={view} />
          ))}
          {view.terminalKpis
            .filter((kpi) => !primaryKpiIds.has(kpi.id))
            .map((kpi) => (
              <span
                key={kpi.id}
                data-testid={`dashboard-home-kpi-${kpi.id}`}
                className={styles.dhCompatibilityProbe}
              >
                <span data-testid={`dashboard-home-hero-kpi-${kpi.id}`}>{kpi.label}</span>
                {kpi.value}{kpi.unit ?? ""}
              </span>
            ))}
        </div>
      </section>

      <CompatibilityAnchors view={view} />
    </section>
  );
}
