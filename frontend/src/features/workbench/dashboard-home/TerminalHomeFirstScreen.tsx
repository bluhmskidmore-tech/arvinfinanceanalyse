import { useEffect, useRef, useState } from "react";
import type { KeyboardEvent } from "react";
import { Link } from "react-router-dom";

import {
  resolveDeltaClass,
  type DashboardHomeFirstScreenView,
  type HomeDataStateKind,
  type HomeDeltaTone,
} from "./dashboardHomeFirstScreenTypes";
import { DashboardHomeAmbientCanvas } from "./DashboardHomeAmbientCanvas";
import {
  hasReportDateDivergence,
  reportDateContextLabel,
} from "./homeReportDateLabel";
import styles from "./dashboardHomeShell.module.css";

type TerminalHomeFirstScreenProps = {
  view: DashboardHomeFirstScreenView;
};

type KpiSemantic = "aum" | "yield" | "nim" | "dv01";

type KpiSpec = {
  semantic: KpiSemantic;
  id: KpiSemantic;
  code: string;
  label: string;
};

const GAP = "—";

const KPI_SPECS: readonly KpiSpec[] = [
  {
    semantic: "aum",
    id: "aum",
    code: "AUM",
    label: "资产规模",
  },
  {
    semantic: "yield",
    id: "yield",
    code: "损益",
    label: "年度损益",
  },
  {
    semantic: "nim",
    id: "nim",
    code: "NIM",
    label: "净息差",
  },
  {
    semantic: "dv01",
    id: "dv01",
    code: "DV01",

    label: "组合 DV01",
  },
];

function handleHorizontalStripKeyDown(event: KeyboardEvent<HTMLDivElement>) {
  if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") {
    return;
  }

  event.preventDefault();
  const direction = event.key === "ArrowRight" ? 1 : -1;
  const step = Math.max(160, Math.round(event.currentTarget.clientWidth * 0.8));
  event.currentTarget.scrollBy({ behavior: "smooth", left: direction * step });
}

const SOURCE_GATE_ROWS = [
  { id: "snapshot", label: "受管快照", basis: "home.snapshot", scope: "primary" },
  { id: "overview", label: "经营指标", basis: "overview / daily-change", scope: "primary" },
  { id: "product-category", label: "产品分类", basis: "product_category_ytd / monthly", scope: "product" },
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
  const canRenderValue =
    kpi?.state === "ready" ||
    kpi?.state === "partial" ||
    kpi?.state === "stale";
  if (kpi && canRenderValue && hasDisplayText(kpi.value)) {
    return `${kpi.value}${kpi.unit ?? ""}`;
  }
  return isServiceUnavailable(view) ? "—" : GAP;
}

function findKpi(
  view: DashboardHomeFirstScreenView,
  id: KpiSemantic,
): DashboardHomeFirstScreenView["terminalKpis"][number] | undefined {
  return view.terminalKpis.find((kpi) => kpi.id === id);
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

function isGovernanceReviewStatus(
  kind: DashboardHomeFirstScreenView["headerStatus"]["dataStatusKind"],
): boolean {
  return kind === "partial" || kind === "fallback" || kind === "stale";
}

function governanceStatusCopy(
  kind: DashboardHomeFirstScreenView["headerStatus"]["dataStatusKind"],
): string {
  if (kind === "partial") return "不完整";
  if (kind === "fallback") return "回退";
  if (kind === "stale") return "偏旧";
  if (kind === "loading") return "读取中";
  if (kind === "error") return "失败";
  return "通过";
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
  if (view.reportDateContext.mode === "empty") {
    return { kind: "empty" as HomeDataStateKind, label: "暂无" };
  }
  if (row.scope === "deferred") {
    return { kind: "partial" as HomeDataStateKind, label: "下方复核" };
  }
  if (row.scope === "product") {
    const productState = view.productCategoryHeadline.state;
    if (productState === "partial") return { kind: "partial", label: "不完整" };
    if (productState === "empty") return { kind: "empty", label: "未下发" };
    if (productState === "stale") return { kind: "stale", label: "偏旧" };
    if (productState === "loading") return { kind: "loading", label: "读取" };
    if (productState === "error") return { kind: "error", label: "异常" };
    if (view.headerStatus.dataStatusKind === "fallback") {
      return { kind: "partial", label: "回退" };
    }
    if (view.headerStatus.dataStatusKind === "stale") {
      return { kind: "stale", label: "偏旧" };
    }
    if (productState === "ready") return { kind: "ready", label: "通过" };
    return { kind: "backend-gap", label: "待接入" };
  }
  if (row.id === "overview") {
    const overviewMissing = view.missingDomains.some((domain) => domain.id === "overview");
    const overviewIncomplete = overviewMissing || KPI_SPECS.some((spec) => {
      const kpi = findKpi(view, spec.id);
      return !kpi || kpi.state !== "ready" || !hasDisplayText(kpi.value);
    });
    if (overviewIncomplete) {
      return { kind: "partial", label: "不完整" };
    }
    if (view.headerStatus.dataStatusKind === "fallback") {
      return { kind: "partial", label: "回退" };
    }
    if (view.headerStatus.dataStatusKind === "stale") {
      return { kind: "stale", label: "偏旧" };
    }
    return { kind: "ready", label: "通过" };
  }
  if (view.headerStatus.dataStatusKind === "partial") {
    return { kind: "partial", label: "部分" };
  }
  if (view.headerStatus.dataStatusKind === "fallback") {
    return { kind: "partial", label: "回退" };
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

function primaryDecisionAction(
  actions: DashboardHomeFirstScreenView["decisionRail"]["actions"],
) {
  const priorityRank = { high: 0, medium: 1, low: 2 } as const;
  return actions
    .filter((action) => action.statusKind === "ready" && Boolean(action.to))
    .sort((left, right) => priorityRank[left.priority] - priorityRank[right.priority])[0];
}

function KpiCard({
  spec,
  view,
}: {
  spec: KpiSpec;
  view: DashboardHomeFirstScreenView;
}) {
  const kpi = findKpi(view, spec.id);
  const hasValue = hasDisplayText(kpi?.value);
  const state = !hasValue && isServiceUnavailable(view)
    ? "error"
    : kpi?.state ?? unresolvedKpiState(view);
  const id = spec.id;
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
      <span className={styles.dhApiKpiCode}>{spec.code}</span>
      <span className={styles.dhApiKpiLabel} title={label}>{label}</span>
      <strong className={styles.dhApiKpiValue}>{value}</strong>
      <span className={styles.dhApiKpiRule} aria-hidden="true" />
      <span className={styles.dhApiKpiStatus}>
        <i className={stateClass(state)} aria-hidden="true" />
        {statusLabel}
      </span>
      <span className={`${styles.dhApiKpiDelta} ${resolveDeltaClass(deltaTone, styles)}`}>
        {kpi && (state === "ready" || state === "partial" || state === "stale")
          ? kpi.delta
          : state === "error" ? "未取得" : GAP}
      </span>
    </article>
  );
}

function SourceGateSummary({ view }: { view: DashboardHomeFirstScreenView }) {
  const sourceGridRef = useRef<HTMLDivElement>(null);
  const [sourceGridScrollable, setSourceGridScrollable] = useState(false);

  useEffect(() => {
    const sourceGrid = sourceGridRef.current;
    if (!sourceGrid) return;

    const updateScrollableState = () => {
      setSourceGridScrollable(sourceGrid.scrollWidth > sourceGrid.clientWidth + 1);
    };
    updateScrollableState();

    const resizeObserver = typeof ResizeObserver === "undefined"
      ? null
      : new ResizeObserver(updateScrollableState);
    resizeObserver?.observe(sourceGrid);
    window.addEventListener("resize", updateScrollableState);
    return () => {
      resizeObserver?.disconnect();
      window.removeEventListener("resize", updateScrollableState);
    };
  }, [view]);

  const missingDomainText = view.missingDomains
    .map((domain) => `${domain.label}（${domain.id}）`)
    .join("、");

  return (
    <section className={styles.dhApiSourceGate} aria-label="来源核验">
      <div className={styles.dhApiModuleHead}>
        <h2>来源核验</h2>
        <span>结论旁展示可信度</span>
      </div>
      <span
        className={styles.dhApiSourceMobileSummary}
        data-testid="dashboard-home-source-mobile-summary"
      >
        {missingDomainText
          ? `缺失域：${missingDomainText}`
          : "3 项主链 · 2 项下方复核 · 1 项保留缺口"}
      </span>
      {missingDomainText ? (
        <p className={styles.dhApiMissingDomains} data-testid="dashboard-home-missing-domains">
          缺失数据域：{missingDomainText}
        </p>
      ) : null}
      <div
        ref={sourceGridRef}
        className={styles.dhApiSourceGrid}
        role="region"
        aria-label={sourceGridScrollable ? "来源核验明细，可用左右方向键横向浏览" : "来源核验明细"}
        tabIndex={sourceGridScrollable ? 0 : undefined}
        onKeyDown={sourceGridScrollable ? handleHorizontalStripKeyDown : undefined}
      >
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

function ProductCategoryHeadline({ view }: { view: DashboardHomeFirstScreenView }) {
  const headline = view.productCategoryHeadline;
  const [leadMetric, ...supportingMetrics] = headline.metrics;
  const statusLabel = headline.state === "partial"
    ? "部分下发"
    : headline.state === "stale"
      ? "需复核"
      : headline.state === "loading"
        ? "读取中"
        : headline.state === "error"
          ? "读取失败"
          : headline.state === "empty"
            ? "暂无"
            : view.headerStatus.dataStatusKind === "fallback"
              ? "回退快照"
              : view.headerStatus.dataStatusKind === "stale"
                ? "快照偏旧"
                : "快照已下发";

  return (
    <section
      className={styles.dhApiProductCategory}
      data-testid="dashboard-home-product-category-headline"
      data-state={headline.state}
      aria-label="产品分类经营摘要"
    >
      <div className={styles.dhApiModuleHead}>
        <h2>产品分类经营摘要</h2>
        <span>{statusLabel}</span>
      </div>
      {leadMetric ? (
        <div
          className={styles.dhApiProductCategoryBody}
          data-testid="dashboard-home-product-category-strip"
        >
          <div className={`${styles.dhApiProductCategoryMetric} ${styles.dhApiProductCategoryLead}`}>
            <span>{leadMetric.label}</span>
            <strong>{leadMetric.value}</strong>
            <small>{leadMetric.detail || "快照下发口径"}</small>
          </div>
          {supportingMetrics.length > 0 ? (
            <div className={styles.dhApiProductCategoryGrid}>
              {supportingMetrics.map((metric) => (
                <div key={metric.id} className={styles.dhApiProductCategoryMetric}>
                  <span>{metric.label}</span>
                  <strong>{metric.value}</strong>
                  <small>{metric.detail || "快照下发口径"}</small>
                </div>
              ))}
            </div>
          ) : null}
        </div>
      ) : (
        <p className={styles.dhApiProductCategoryEmpty}>暂无产品分类经营摘要</p>
      )}
    </section>
  );
}

export function TerminalHomeFirstScreen({ view }: TerminalHomeFirstScreenProps) {
  const loading = isLoadingState(view);
  const unavailable = isServiceUnavailable(view);
  const conclusion = loading ? "等待数据" : view.decisionRail.conclusion;
  const decisionDisplay = buildDecisionDisplay(conclusion);
  const primaryAction = primaryDecisionAction(view.decisionRail.actions);
  const primarySuggestion = view.decisionRail.suggestions.find((suggestion) => suggestion.to);
  const primaryCta = primaryAction?.to
    ? { title: primaryAction.title, to: primaryAction.to }
    : primarySuggestion?.to
      ? { title: primarySuggestion.text, to: primarySuggestion.to }
      : null;
  const governedReviewRequired = isGovernanceReviewStatus(view.headerStatus.dataStatusKind);
  const emptySnapshot = view.reportDateContext.mode === "empty";
  const decisionCopy = emptySnapshot
    ? "当前快照没有实际数据日。选择其他报告日或刷新后再做判断。"
    : unavailable
    ? "主快照未取得，所有口径暂不可用。恢复首页数据服务后刷新日报即可继续判断。"
    : loading
      ? "主快照读取中，等待来源核验返回后再做结论。"
      : governedReviewRequired
        ? "主链存在部分、回退或偏旧状态；结论仅供复核，不应直接用于正式决策。"
        : "主链质量按快照口径展示；补充模块进入下方证据看板复核。";
  const evidenceStatusLabel = emptySnapshot
    ? "暂无证据"
    : unavailable
    ? "证据暂不可用"
    : loading
      ? "证据读取中"
      : governedReviewRequired
        ? "证据需复核"
        : "证据已就绪";
  const reportIdentityState = emptySnapshot
    ? "暂无数据 · 待同步"
    : unavailable
    ? "未取得 · 失败"
    : loading
      ? "等待数据 · 读取中"
      : `${view.headerStatus.dataSyncPrefix} · ${governanceStatusCopy(view.headerStatus.dataStatusKind)}`;

  return (
    <section
      className={styles.dhApiFirstScreen}
      aria-label="MOSS 组合经营日报首屏"
      aria-busy={loading}
    >
      <div data-testid="dashboard-home-report-identity" className={styles.dhApiTopRail}>
        <strong>MOSS 固收经营日报</strong>
        <span>{reportIdentityState}</span>
        <span
          data-testid="dashboard-home-report-date-line"
          data-report-date-mode={view.reportDateContext.mode}
          title={
            hasReportDateDivergence(view.reportDateContext)
              ? view.reportDateContext.divergenceReason ?? undefined
              : undefined
          }
        >
          {reportDateContextLabel(view.reportDateContext)}
          {` · 数据截至 ${view.reportDateContext.dataAsOfDate || GAP}`}
        </span>
      </div>

      <section data-testid="dashboard-home-hero" className={styles.dhApiHero}>
        <DashboardHomeAmbientCanvas />

        <div data-testid="dashboard-home-morning-hero" className={styles.dhApiDecisionBand}>
          <div className={styles.dhApiModuleHead}>
            <h2>早间决策一览</h2>
            <span>
              数据来源 <code className={styles.dhApiInlineCode}>首页主快照</code>
            </span>
          </div>
          <div className={styles.dhApiDecisionBody}>
            <div>
              <h3>{decisionDisplay.title}</h3>
              <p>
                {decisionDisplay.evidence ? (
                  <span className={styles.dhApiDecisionEvidence}>{decisionDisplay.evidence}</span>
                ) : null}
                <span>{decisionCopy}</span>
              </p>
              {primaryCta ? (
                <Link
                  to={primaryCta.to}
                  className={styles.dhApiPrimaryAction}
                  data-testid="dashboard-home-primary-action"
                >
                  {primaryCta.title}
                  <span aria-hidden="true">→</span>
                </Link>
              ) : null}
            </div>
            <div
              className={styles.dhApiEvidenceScore}
              data-testid="dashboard-home-evidence-score"
              role="status"
              aria-live="polite"
              aria-atomic="true"
            >
              <strong>{evidenceStatusLabel}</strong>
              <span>
                {emptySnapshot
                  ? "主链暂无可核验数据"
                  : unavailable
                  ? "主链未取得，待服务恢复"
                  : loading
                    ? "主链读取中"
                    : governedReviewRequired
                      ? "主链存在部分、回退或偏旧状态"
                      : "主链来源核验通过"}
              </span>
            </div>
          </div>
        </div>

        <SourceGateSummary view={view} />

        <div
          data-testid="dashboard-home-hero-kpi-strip"
          className={styles.dhApiKpiGrid}
        >
          {KPI_SPECS.map((spec) => (
            <KpiCard key={spec.semantic} spec={spec} view={view} />
          ))}
        </div>

        <ProductCategoryHeadline view={view} />
      </section>
    </section>
  );
}
