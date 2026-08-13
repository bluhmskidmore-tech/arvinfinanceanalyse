import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { LightIcon } from "../../../components/LightIcon";
import { mapStatusEntry } from "../../../components/StatusContract";
import type {
  DashboardHomeFirstScreenView,
  HomeDataStateKind,
  HomeDecisionAction,
  HomeTerminalKpi,
} from "./dashboardHomeFirstScreenTypes";
import {
  type HomeStatusKind,
  reportDatePath,
  stateLabel,
  statusTone,
} from "./dashboardHomeOptionTwoShared";
import { formatKpiNumeric, parseKpiNumeric } from "./kpiCountUpFormat";
import { OptionTwoSparkline } from "./OptionTwoSparkline";
import styles from "./dashboardHomeOptionTwo.module.css";

import { EM_DASH } from "../../../utils/format";
type DashboardHomeOptionTwoOverviewProps = {
  view: DashboardHomeFirstScreenView;
};

const OVERVIEW_KPI_SPECS = [
  { id: "aum", label: "债券资产规模", sourceIds: ["aum"] },
  { id: "yield", label: "年度损益（不含FTP）", sourceIds: ["yield"] },
  { id: "nim", label: "净息差", sourceIds: ["nim"] },
  { id: "dv01-wan", label: "DV01", sourceIds: ["dv01-wan", "dv01"] },
] as const;

function overviewKpiSlot(
  terminalKpis: readonly HomeTerminalKpi[],
  spec: (typeof OVERVIEW_KPI_SPECS)[number],
  pagePartial: boolean,
): HomeTerminalKpi {
  const matched = spec.sourceIds
    .map((sourceId) => terminalKpis.find((kpi) => kpi.id === sourceId))
    .find((kpi): kpi is HomeTerminalKpi => Boolean(kpi));
  if (matched) return matched;
  return {
    id: spec.id,
    label: spec.label,
    value: EM_DASH,
    delta: EM_DASH,
    deltaTone: "muted",
    sparkline: [],
    state: pagePartial ? "partial" : "empty",
  };
}

function governanceKind(
  kind: DashboardHomeFirstScreenView["headerStatus"]["dataStatusKind"],
): HomeStatusKind {
  if (kind === "ok") return "ready";
  return kind;
}

function productHeadlineKind(view: DashboardHomeFirstScreenView): HomeStatusKind {
  const headlineState = view.productCategoryHeadline.state;
  if (headlineState === "ready" && view.headerStatus.dataStatusKind === "fallback") {
    return "fallback";
  }
  if (headlineState === "ready" && view.headerStatus.dataStatusKind === "stale") {
    return "stale";
  }
  return headlineState;
}

function primaryAction(view: DashboardHomeFirstScreenView): HomeDecisionAction | null {
  return (
    view.decisionRail.actions.find((action) => action.to && action.priority === "high") ??
    view.decisionRail.actions.find((action) => action.to) ??
    null
  );
}

function decisionTitle(value: string): string {
  const source = value.trim().replace(/[。；;]+$/u, "");
  const clauses = source
    .split(/[；;]+/u)
    .map((part) => part.trim().replace(/[。；;]+$/u, ""))
    .filter(Boolean);
  const title = source.length > 28 && clauses.length > 1
    ? (clauses.at(-1) ?? source)
    : source;
  if (!title) return "趋势判断待复核";
  return /^趋势判断/.test(title) ? title : `趋势判断：${title}`;
}

/** 演示数据披露文案统一取自状态契约（dataSource.mock），避免另造词汇。 */
const MOCK_DATA_DISCLOSURE = mapStatusEntry("dataSource", "mock");

const KPI_COUNT_UP_MS = 900;

function isTestRuntime(): boolean {
  return (
    import.meta.env.MODE === "test" ||
    (import.meta.env as Record<string, unknown>).VITEST != null
  );
}

function canAnimateKpiValue(): boolean {
  return (
    !isTestRuntime() &&
    typeof window !== "undefined" &&
    typeof window.requestAnimationFrame === "function" &&
    !(
      typeof window.matchMedia === "function" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches
    )
  );
}

/**
 * 数字滚动（交接包 Interactions 规范）：900ms ease-out；测试与 reduced-motion 直接落定。
 * 动画帧对读屏隐藏，最终值以 sr-only 常驻，避免辅助技术连读中间帧。
 */
function AnimatedKpiValue({
  value,
  state,
}: {
  value: string;
  state: HomeDataStateKind;
}) {
  const parsed = state === "ready" ? parseKpiNumeric(value) : null;
  const animatable = parsed != null && canAnimateKpiValue();
  const [display, setDisplay] = useState(() =>
    animatable && parsed ? formatKpiNumeric(parsed, 0) : value,
  );

  useEffect(() => {
    if (!animatable || !parsed) {
      setDisplay(value);
      return undefined;
    }
    let frame = 0;
    let active = true;
    const start = performance.now();
    setDisplay(formatKpiNumeric(parsed, 0));
    const tick = (now: number) => {
      if (!active) return;
      const k = Math.min((now - start) / KPI_COUNT_UP_MS, 1);
      if (k >= 1) {
        setDisplay(value);
        return;
      }
      const eased = 1 - (1 - k) ** 3;
      setDisplay(formatKpiNumeric(parsed, parsed.abs * eased));
      frame = window.requestAnimationFrame(tick);
    };
    frame = window.requestAnimationFrame(tick);
    return () => {
      active = false;
      window.cancelAnimationFrame(frame);
    };
    // parsed 由 value/state 派生，依赖以两个源为准。
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [animatable, state, value]);

  if (!animatable) {
    return <>{display}</>;
  }
  return (
    <>
      <span aria-hidden="true">{display}</span>
      <span className={styles.srOnly}>{value}</span>
    </>
  );
}

function kpiDisplay(
  kpi: DashboardHomeFirstScreenView["terminalKpis"][number],
  semanticId: string,
): { value: string; unit: string | undefined } {
  if (semanticId !== "dv01-wan" || kpi.unit?.includes("万")) {
    return { value: kpi.value, unit: kpi.unit };
  }
  const numeric = Number(kpi.value.replaceAll(",", ""));
  if (!Number.isFinite(numeric) || Math.abs(numeric) < 10_000) {
    return { value: kpi.value, unit: kpi.unit };
  }
  return {
    value: (numeric / 10_000).toLocaleString("zh-CN", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }),
    unit: "万元/bp",
  };
}

export function DashboardHomeOptionTwoOverview({
  view,
}: DashboardHomeOptionTwoOverviewProps) {
  const action = primaryAction(view);
  const decisionReasons = [
    action?.reason,
    view.decisionRail.keyRisk,
    view.decisionRail.suggestions[0]?.text,
    view.decisionRail.pendingSummary,
  ]
    .map((value) => value?.trim() ?? "")
    .filter(Boolean);
  const decisionReason = [...new Set(decisionReasons)].slice(0, 2).join("；") ||
    "当前结论暂无补充说明";
  const dataKind = governanceKind(view.headerStatus.dataStatusKind);
  const productKind = productHeadlineKind(view);
  const governanceFeedAvailable = view.headerStatus.governanceFeedAvailable === true;
  const formalUseLabel =
    view.headerStatus.formalUseAllowed === false
      ? "分析快照，非正式报表"
      : view.headerStatus.formalUseAllowed === true
        ? "正式报表"
        : "使用范围未返回";
  const narrativeActionTo = action?.to ?? reportDatePath("/bond-analysis", view.reportDate);
  const nextActionTo = action?.to ?? reportDatePath("/risk-overview", view.reportDate);
  const nextActionTitle =
    action?.title ??
    (governanceFeedAvailable
      ? `查看风险清单（${view.headerStatus.riskReviewCount}项）`
      : "打开治理入口");
  const governedCount = governanceFeedAvailable
    ? view.headerStatus.riskReviewCount
    : 0;
  const attentionSummary =
    view.decisionRail.keyRisk?.trim() ||
    view.decisionRail.pendingSummary?.trim() ||
    decisionReason;
  const attentionTitle = decisionTitle(view.decisionRail.conclusion);
  const dataAsOfText = view.reportDateContext.dataAsOfDate.trim() || "无";
  const missingDomainText =
    view.missingDomains.map((domain) => domain.label.trim()).filter(Boolean).join("、") || "无";
  const productStateText = stateLabel(productKind);

  return (
    <>
      {view.useMockFallback ? (
        <p
          role="status"
          data-testid="dashboard-home-mock-banner"
          className={styles.mockBanner}
        >
          <strong>{MOCK_DATA_DISCLOSURE.label}</strong>
          <span>{MOCK_DATA_DISCLOSURE.description}</span>
        </p>
      ) : null}
    <section
      data-testid="dashboard-home-hero"
      className={styles.overview}
      aria-label="组合经营日报今日概览"
    >
      <section className={styles.todayPanel} aria-labelledby="option-two-today-title">
        <header className={styles.overviewSectionHeader}>
          <span>01</span>
          <h2 id="option-two-today-title">今日需处理</h2>
          <strong>
            {governanceFeedAvailable ? `治理待办 ${governedCount} 项` : "治理待办未接入"}
          </strong>
        </header>

        <div className={styles.decisionStrip}>
          <div className={styles.governedStatus}>
            <span>当前状态</span>
            <strong
              data-tone={!governanceFeedAvailable || governedCount > 0 ? "warn" : "ok"}
              data-emphasis={
                governanceFeedAvailable && governedCount > 0 ? "high" : "low"
              }
            >
              {!governanceFeedAvailable
                ? "暂无正式待办源"
                : governedCount > 0
                  ? `${governedCount} 项待处理`
                  : "暂无治理待办"}
            </strong>
            <Link to={nextActionTo} title={nextActionTitle}>
              {governanceFeedAvailable ? "查看治理入口" : "打开治理入口"}
              <LightIcon name="arrow-right" />
            </Link>
          </div>

          <div className={styles.overviewAttention}>
            <span>观察与数据状态 · 不计入治理待办</span>
            <strong title={attentionTitle}>{attentionTitle}</strong>
            <small title={attentionSummary}>{attentionSummary}</small>
          </div>

          <aside className={styles.overviewStatus} aria-label="首页数据状态">
            <div className={styles.statusHeading}>
              <span>使用范围</span>
              <strong
                data-tone={
                  view.headerStatus.formalUseAllowed === true
                    ? statusTone(dataKind)
                    : "warn"
                }
              >
                <i aria-hidden="true" />
                {formalUseLabel}
              </strong>
            </div>
            <dl className={styles.statusRows}>
              <div>
                <dt>数据质量</dt>
                <dd title={`数据质量 ${stateLabel(dataKind)} · 核心域截至 ${dataAsOfText}`}>
                  <span>{stateLabel(dataKind)}</span>
                  <small>
                    {"核心域截至 "}
                    {/* 每个「域 日期」分段 nowrap，换行只落在分段间，避免日期被拆断。 */}
                    {dataAsOfText.split(" · ").flatMap((segment, index) => [
                      index > 0 ? " · " : null,
                      <span key={`${index}-${segment}`}>{segment}</span>,
                    ])}
                  </small>
                </dd>
              </div>
              <div>
                <dt>估值数据</dt>
                <dd
                  title={`估值数据 ${view.headerStatus.valuationLabel} · 缺失域 ${missingDomainText}`}
                >
                  <span>{view.headerStatus.valuationLabel}</span>
                  <small>{`缺失域 ${missingDomainText}`}</small>
                </dd>
              </div>
            </dl>
          </aside>
        </div>
      </section>

      <section
        className={styles.productCategoryPanel}
        data-testid="dashboard-home-product-category-headline"
        data-state={view.productCategoryHeadline.state}
        aria-label="产品分类经营摘要"
      >
        <div
          className={styles.productCategoryStrip}
          data-testid="dashboard-home-product-category-strip"
          data-state={view.productCategoryHeadline.state}
        >
          <article className={styles.productCategoryLeadCell}>
            <span>产品分类经营摘要</span>
            {productKind === "ready" ? (
              <i
                data-tone={statusTone(productKind)}
                title={productStateText}
                aria-hidden="true"
              />
            ) : (
              <strong data-tone={statusTone(productKind)}>{productStateText}</strong>
            )}
          </article>
          {view.productCategoryHeadline.metrics.length > 0 ? (
            view.productCategoryHeadline.metrics.map((metric) => (
              <article
                key={metric.id}
                className={styles.productCategoryMetric}
                title={metric.detail || undefined}
                aria-description={metric.detail || undefined}
              >
                <span>{metric.label}</span>
                <strong>{metric.value}</strong>
              </article>
            ))
          ) : (
            <p className={styles.productCategoryEmpty}>暂无产品分类经营摘要</p>
          )}
        </div>
      </section>

      <section className={styles.portfolioSummaryPanel} aria-labelledby="option-two-summary-title">
        <header className={styles.overviewSectionHeader}>
          <span>02</span>
          <h2 id="option-two-summary-title">组合变化</h2>
        </header>

        <div className={styles.portfolioSummaryBody}>
          <div
            data-testid="dashboard-home-morning-hero"
            className={styles.overviewNarrative}
          >
            <div className={styles.overviewEyebrow}>
              <strong>观察结论</strong>
            </div>
            <h3>{decisionTitle(view.decisionRail.conclusion)}</h3>
            <p title={decisionReason}>{decisionReason}</p>
            {view.decisionRail.hasContribution || view.decisionRail.hasDrag ? (
              <div
                className={styles.attributionHints}
                data-testid="dashboard-home-attribution-hints"
              >
                {view.decisionRail.hasContribution ? (
                  <span
                    title={`最大贡献 ${view.decisionRail.maxContributionLabel} ${view.decisionRail.maxContributionValue}（来自快照经营贡献拆解）`}
                  >
                    贡献 {view.decisionRail.maxContributionLabel}
                    <em data-tone="up">{view.decisionRail.maxContributionValue}</em>
                  </span>
                ) : null}
                {view.decisionRail.hasDrag ? (
                  <span
                    title={`最大拖累 ${view.decisionRail.maxDragLabel} ${view.decisionRail.maxDragValue}（来自快照经营贡献拆解）`}
                  >
                    拖累 {view.decisionRail.maxDragLabel}
                    <em data-tone="down">{view.decisionRail.maxDragValue}</em>
                  </span>
                ) : null}
              </div>
            ) : null}
            <Link
              to={narrativeActionTo}
              className={styles.overviewLink}
              data-testid="dashboard-home-primary-action"
            >
              进入专题页
              <LightIcon name="arrow-right" />
            </Link>
          </div>

          <div
            data-testid="dashboard-home-hero-kpi-strip"
            className={styles.kpiRail}
          >
            {OVERVIEW_KPI_SPECS.map((spec) => {
              const kpi = overviewKpiSlot(
                view.terminalKpis,
                spec,
                dataKind === "partial",
              );
              const display = kpiDisplay(kpi, spec.id);
              const compactValue =
                display.value.length >= 9 ||
                `${display.value}${display.unit ?? ""}`.length > 10;
              return (
                <article
                  key={kpi.id}
                  className={styles.kpiItem}
                  data-state={kpi.state}
                  data-compact-value={compactValue ? "true" : "false"}
                  data-testid={`dashboard-home-kpi-${spec.id}`}
                >
                  <span title={kpi.label}>{kpi.label || spec.label}</span>
                  <strong>
                    <AnimatedKpiValue value={display.value} state={kpi.state} />
                    {display.unit ? <small>{display.unit}</small> : null}
                  </strong>
                  <em data-tone={kpi.deltaTone}>{kpi.delta || EM_DASH}</em>
                  {kpi.sparkline.length > 1 ? (
                    <span className={styles.kpiSparkSlot} aria-hidden="true">
                      <OptionTwoSparkline values={kpi.sparkline} endDot />
                    </span>
                  ) : (
                    <small className={styles.kpiSparkNote}>无历史序列</small>
                  )}
                </article>
              );
            })}
          </div>
        </div>
      </section>
    </section>
    </>
  );
}
