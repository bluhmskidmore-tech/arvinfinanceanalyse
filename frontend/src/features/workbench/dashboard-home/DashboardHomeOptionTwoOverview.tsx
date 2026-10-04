import { Link } from "react-router-dom";

import { LightIcon } from "../../../components/LightIcon";
import { mapStatusEntry } from "../../../components/StatusContract";
import type {
  DashboardHomeFirstScreenView,
  HomeDecisionAction,
  HomeTerminalKpi,
} from "./dashboardHomeFirstScreenTypes";
import { VERDICT_REASON_SEPARATOR } from "./dashboardHomeFirstScreenView";
import {
  type HomeStatusKind,
  reportDatePath,
  stateLabel,
  statusTone,
} from "./dashboardHomeOptionTwoShared";
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

/** 结论标题只做修剪，不补「趋势判断」前缀：读数事实不能被包装成判断（§7）。 */
function conclusionHeadline(value: string): string {
  return value.trim().replace(/[。；;]+$/u, "") || "暂无观察结论";
}

/**
 * 依据行「标签 · 数值 · 溯源说明」：正文只留前两段业务事实（单行 ≤1 个「·」，§7），
 * 溯源说明连同全文由 title 承载（§6 来源细节不占正文）。
 */
function splitReasonForDisplay(reason: string): { visible: string; full: string } {
  const segments = reason
    .split(VERDICT_REASON_SEPARATOR)
    .map((segment) => segment.trim())
    .filter(Boolean);
  if (segments.length <= 2) {
    return { visible: reason, full: reason };
  }
  return {
    visible: segments.slice(0, 2).join(VERDICT_REASON_SEPARATOR),
    full: reason,
  };
}

/** 演示数据披露文案统一取自状态契约（dataSource.mock），避免另造词汇。 */
const MOCK_DATA_DISCLOSURE = mapStatusEntry("dataSource", "mock");

/**
 * §6 状态去重：叙述句中与报告日相同的日期在可见文本折叠为「报告日」，
 * 原文（含具体日期）由调用处 title 全量保留；与报告日不一致的日期
 * 是分叉信号，保持显式不折叠。
 */
function foldReportDateMention(text: string, reportDate: string): string {
  const date = reportDate.trim();
  if (!date || !text.includes(date)) return text;
  return text.replaceAll(`在 ${date} 的`, "在报告日的").replaceAll(date, "报告日");
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
  const attentionTitle = conclusionHeadline(view.decisionRail.conclusion);
  const reportDateValue = view.reportDateContext.actualDataDate.trim();
  // 依据行由视图模型去重后给出；没有可用依据时不渲染，也不用填充语占位（§7）。
  const keyRisk = view.decisionRail.keyRisk.trim();
  const attentionReason =
    keyRisk && keyRisk !== EM_DASH ? splitReasonForDisplay(keyRisk) : null;
  const attentionReasonDisplay = attentionReason
    ? foldReportDateMention(attentionReason.visible, reportDateValue)
    : null;
  const dataAsOfText = view.reportDateContext.dataAsOfDate.trim() || "无";
  // 分域截至日与报告日一致时正文折叠为「同报告日」（§6 卡片内不重复全局报告日），
  // 日期分叉时保持显式；dd 的 title 恒为全文日期。
  const dataAsOfSegments = dataAsOfText.split(" · ").map((segment) => {
    const matched = /^(.*?)\s*(\d{4}-\d{2}-\d{2})$/.exec(segment.trim());
    return matched && reportDateValue && matched[2] === reportDateValue
      ? `${matched[1]}同报告日`
      : segment.trim();
  });
  const coreDomainsOnReportDate =
    dataAsOfText !== "无" && dataAsOfSegments.every((segment) => segment.endsWith("同报告日"));
  const missingDomainText =
    view.missingDomains.map((domain) => domain.label.trim()).filter(Boolean).join("、") || "无";
  // 结论 17「常态收声」：质量 ok、估值完成、无缺失域时只留一行 muted 事实 + 暗点，
  // 明细全部进 title；任一异常态沿用两行语义色呈现。
  const statusQuiet =
    dataKind === "ready" &&
    view.headerStatus.valuationTone === "ok" &&
    view.missingDomains.length === 0;
  const statusQuietDetail = [
    `数据质量 ${stateLabel(dataKind)}`,
    `核心域截至 ${dataAsOfText}`,
    `估值数据 ${view.headerStatus.valuationLabel}`,
    `缺失域 ${missingDomainText}`,
  ].join("；");
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
            {attentionReason ? (
              <small title={attentionReason.full}>{attentionReasonDisplay}</small>
            ) : null}
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
              {statusQuiet ? (
                <div data-quiet="true">
                  <dt>数据质量</dt>
                  <dd title={statusQuietDetail}>
                    <i aria-hidden="true" />
                    {coreDomainsOnReportDate ? (
                      "核心域同报告日"
                    ) : (
                      <>
                        {"核心域截至 "}
                        {dataAsOfSegments.flatMap((segment, index) => [
                          index > 0 ? " · " : null,
                          <span key={`${index}-${segment}`}>{segment}</span>,
                        ])}
                      </>
                    )}
                  </dd>
                </div>
              ) : (
                <>
                  <div>
                    <dt>数据质量</dt>
                    <dd title={`数据质量 ${stateLabel(dataKind)} · 核心域截至 ${dataAsOfText}`}>
                      <span>{stateLabel(dataKind)}</span>
                      <small>
                        {"核心域截至 "}
                        {/* 每个「域 日期」分段 nowrap，换行只落在分段间，避免日期被拆断。 */}
                        {dataAsOfSegments.flatMap((segment, index) => [
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
                </>
              )}
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
            {/* 结论与依据只在 01 区出现一次（§6 状态去重、§9.2 hero 承载判断）；本格只留归因独有内容。 */}
            <div className={styles.overviewEyebrow}>
              <strong>归因要点</strong>
            </div>
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
            ) : (
              <p className={styles.attributionEmpty}>暂无经营贡献拆解</p>
            )}
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
                    {display.value}
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
