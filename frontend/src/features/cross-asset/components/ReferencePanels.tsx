import type { ReactNode } from "react";

import { LightIcon } from "../../../components/LightIcon";
import { DataStatusStrip } from "../../../components/page/PagePrimitives";
import { StatusPill } from "../../../components/StatusPill";
import type { ResultMeta } from "../../../api/contracts";
import { CrossAssetSparkline } from "./CrossAssetSparkline";
import {
  correlationColor,
  formatCorrelation,
  type CorrelationMatrix,
  type MomentumRow,
} from "../lib/crossAssetAnalytics";
import {
  type CrossAssetCandidateAction,
  type CrossAssetClassAnalysisRow,
  type CrossAssetFirstScreenDisplayContract,
  type CrossAssetResearchViewCard,
  type CrossAssetStatusFlag,
  type CrossAssetTransmissionAxisRow,
} from "../lib/crossAssetDriversPageModel";
import { buildEnvironmentTags } from "../lib/crossAssetDriversModel";
import type { ResolvedCrossAssetKpi } from "../lib/crossAssetKpiModel";

function resultMetaQualityLabel(value: string | null | undefined): string {
  if (value === "ok") return "正常";
  if (value === "warning") return "预警";
  if (value === "error") return "错误";
  if (value === "stale") return "陈旧";
  return value ?? "待定";
}

function compactGeneratedAt(value: string | null | undefined): string {
  if (!value) return "待定";
  const clock = value.match(/T(\d{2}:\d{2})/);
  return clock?.[1] ?? value;
}

function sourceNameForKpi(kpi: ResolvedCrossAssetKpi | null | undefined) {
  if (!kpi) return "待定";
  if (kpi.sourceKind === "choice") return "中债估值";
  if (kpi.sourceKind === "public" && kpi.vendorName) return kpi.vendorName;
  if (kpi.sourceKind === "public") return "公共补充";
  if (kpi.sourceKind === "derived") return "中债估值 + UST";
  return "待补源";
}

function credibilityForKpi(
  kpi: ResolvedCrossAssetKpi | null | undefined,
  isSourceBlocked = false,
) {
  if (!kpi || kpi.sourceKind === "missing") return { label: "低", tone: "low" as const };
  if (isSourceBlocked && kpi.sourceKind === "choice") return { label: "低", tone: "low" as const };
  if (kpi.qualityFlag === "stale") return { label: "中", tone: "medium" as const };
  if (kpi.sourceKind === "public") return { label: "中", tone: "medium" as const };
  return { label: "高", tone: "high" as const };
}

function referenceDirectionForKpi(kpi: ResolvedCrossAssetKpi | null | undefined) {
  if (!kpi || kpi.changeLabel === "—") return { label: "—", tone: "flat" as const };
  if (kpi.changeTone === "positive") return { label: "↑", tone: "up" as const };
  if (kpi.changeTone === "negative") return { label: "↓", tone: "down" as const };
  return { label: "—", tone: "flat" as const };
}

function findReferenceKpi(kpis: ResolvedCrossAssetKpi[], labels: string[]) {
  return kpis.find((kpi) => labels.some((label) => kpi.label.includes(label) || kpi.key.includes(label))) ?? null;
}

type ReferenceEvidenceIcon = "rates" | "equity" | "commodity" | "fx";

const referenceEvidenceSpecs = [
  { category: "利率与流动性", icon: "rates" as const, labels: ["10Y国债"], fallback: "10Y国债" },
  { category: "利率与流动性", icon: "rates" as const, labels: ["DR007", "银拆"], fallback: "DR007" },
  { category: "权益风险偏好", icon: "equity" as const, labels: ["沪深300指数", "沪深300"], fallback: "沪深300指数" },
  { category: "权益风险偏好", icon: "equity" as const, labels: ["沪深300市盈率"], fallback: "沪深300市盈率" },
  { category: "商品通胀", icon: "commodity" as const, labels: ["布油"], fallback: "布油" },
  { category: "商品通胀", icon: "commodity" as const, labels: ["钢"], fallback: "钢" },
  { category: "汇率与中美利差", icon: "fx" as const, labels: ["USD/CNY"], fallback: "USD/CNY" },
  { category: "汇率与中美利差", icon: "fx" as const, labels: ["中美10Y利差", "国开-国债10Y"], fallback: "中美10Y利差" },
];

const referenceTrendLabels = ["10Y国债", "DR007", "沪深300", "布油", "USD/CNY", "中美10Y利差"];

const referenceTrendCardSpecs = [
  { label: "10Y国债收益率（%）", lookup: ["10Y国债"] },
  { label: "DR007（%）", lookup: ["DR007"] },
  { label: "沪深300指数", lookup: ["沪深300"] },
  { label: "布油（ICE）", lookup: ["布油"] },
  { label: "USD/CNY", lookup: ["USD/CNY"] },
  { label: "中美10Y利差（bp）", lookup: ["中美10Y利差"] },
] as const;

function ReferenceEvidenceCategoryIcon({ icon }: { icon: ReferenceEvidenceIcon }) {
  if (icon === "rates") return <LightIcon name="line-chart" />;
  if (icon === "equity") return <LightIcon name="bar-chart" />;
  if (icon === "commodity") return <LightIcon name="fund" />;
  return <LightIcon name="bank" />;
}

export function CrossAssetReferenceToolbar({
  reportDate,
  onRefresh,
}: {
  reportDate: string;
  onRefresh: () => void;
}) {
  return (
    <header className="cross-asset-reference-toolbar" data-testid="cross-asset-reference-toolbar">
      <div className="cross-asset-reference-toolbar__title">
        <h1>跨资产驱动</h1>
        <button type="button" className="cross-asset-reference-toolbar__follow">
          <LightIcon name="star" />
          加入关注
        </button>
      </div>
      <div className="cross-asset-reference-toolbar__actions" aria-label="跨资产页面操作">
        <button type="button" className="cross-asset-reference-toolbar__date">
          <LightIcon name="calendar" />
          <span>报告日</span>
          <strong>{reportDate || "待定"}</strong>
        </button>
        <button type="button" onClick={onRefresh}>
          <LightIcon name="reload" />
          刷新
        </button>
        <button type="button" className="cross-asset-reference-toolbar__export">
          <LightIcon name="arrow-down" />
          导出报告
        </button>
      </div>
    </header>
  );
}

export function CrossAssetReferenceSummary({
  display,
  latestMeta,
  linkageMeta,
}: {
  display: CrossAssetFirstScreenDisplayContract;
  latestMeta?: ResultMeta;
  linkageMeta?: ResultMeta;
}) {
  const { bond, stock } = display.judgments;
  const warningCount = display.status.warningCount;

  return (
    <section className="cross-asset-reference-summary" data-testid="cross-asset-reference-summary">
      <section className="cross-asset-decision-header cross-asset-reference-summary__conclusion" data-testid="cross-asset-decision-header">
        <div className="cross-asset-reference-summary__icon" aria-hidden>
          <LightIcon name="fund-projection" />
        </div>
        <section
          className="cross-asset-decision-hero cross-asset-decision-header__decision"
          data-testid="cross-asset-decision-hero"
          aria-label="今日传导结论"
        >
          <span className="moss-page-v2-decision-hero__eyebrow">核心结论</span>
          <h1 className="moss-page-v2-decision-hero__title" title={display.hero.summary}>
            {display.hero.headline}
          </h1>
          <p className="moss-page-v2-decision-hero__question">
            {display.hero.question}
          </p>
          <div className="moss-page-v2-decision-hero__report">
            数据日期 <strong className="cross-asset-drivers-page__report-date">{display.hero.reportDate}</strong>
          </div>
          <div className="moss-page-v2-decision-hero__conclusion">
            <span>今日传导结论：{display.hero.summary}</span>
          </div>
        </section>
      </section>

      <section className="cross-asset-driver-chain" data-testid="cross-asset-dominant-driver-chain" aria-label="主导跨资产链路">
        <div className="cross-asset-driver-chain__head">
          <span>主导跨资产链路</span>
          <strong>{display.driverChain.primary}</strong>
          <em>{display.driverChain.secondary} · {display.driverChain.style}</em>
        </div>
        <div className="cross-asset-driver-chain__items">
          {display.driverChain.items.map((item) => (
            <article className={`cross-asset-driver-chain__item cross-asset-driver-chain__item--${item.tone}`} key={item.title}>
              <div>
                <span>{item.title}</span>
                <strong>{item.stance}</strong>
              </div>
              <p>{item.bullets[0] ?? "等待治理后输入"}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="cross-asset-first-screen-judgments" data-testid="cross-asset-first-screen-judgments" aria-label="债券与股票判断">
        <article className="cross-asset-first-screen-judgment" data-testid="cross-asset-first-screen-judgment-bond">
          <span>{bond.label}</span>
          <strong>{bond.headline}</strong>
          <p>{bond.summary}</p>
        </article>
        <article className="cross-asset-first-screen-judgment" data-testid="cross-asset-first-screen-judgment-stock">
          <span>{stock.label}</span>
          <strong>{stock.headline}</strong>
          <p>{stock.summary}</p>
        </article>
      </section>

      <div className="cross-asset-market-state-strip cross-asset-reference-summary__regime" data-testid="cross-asset-market-state-strip">
        <div className="ca-regime" data-testid="cross-asset-regime-indicator">
          <span className="ca-regime__signal" aria-hidden />
          <div className="ca-regime__body">
            <span className="cross-asset-reference-summary__label">当前格局</span>
            <strong className="ca-regime__label">{display.hero.regimeLabel}</strong>
            <span className="ca-regime__desc">{display.hero.regimeDescription}</span>
          </div>
        </div>
      </div>

      <div className="cross-asset-reference-summary__quality">
        <span>宏观质量</span>
        <strong>
          <LightIcon name="warning" />
          {resultMetaQualityLabel(latestMeta?.quality_flag)}
        </strong>
      </div>
      <div className="cross-asset-reference-summary__quality">
        <span>联动质量</span>
        <strong>
          <LightIcon name="warning" />
          {resultMetaQualityLabel(linkageMeta?.quality_flag)}
        </strong>
      </div>
      <div className="cross-asset-reference-summary__review">
        <strong>{display.loading.isLoading ? "加载中" : warningCount || "0"} 项提示</strong>
        <span>{display.loading.isLoading ? display.loading.label : warningCount ? "查看详情" : "暂无阻断"}</span>
      </div>
      <div className="cross-asset-reference-summary__boundary">
        <strong>仅分析口径</strong>
        <span>不替代交易指令</span>
      </div>
    </section>
  );
}

export function CrossAssetReferenceMarketTape({ kpis }: { kpis: ResolvedCrossAssetKpi[] }) {
  const tickerKpis = referenceTrendLabels.map((label) => ({
    label,
    kpi: findReferenceKpi(kpis, [label]),
  }));

  return (
    <div className="cross-asset-reference-market-tape cross-asset-market-tape" data-testid="cross-asset-market-tape" role="list" aria-label="跨资产市场快讯">
      {tickerKpis.map(({ label, kpi }) => (
        <div className={`cross-asset-market-tape__item cross-asset-market-tape__item--${kpi?.changeTone ?? "default"}`} role="listitem" key={label}>
          <span>{kpi?.label ?? label}</span>
          <strong>{kpi?.valueLabel ?? "待定"}</strong>
          <em>{kpi?.changeLabel ?? "—"}</em>
        </div>
      ))}
    </div>
  );
}

export function CrossAssetReferenceEvidenceMatrix({
  kpis,
  sourceBlockedFlag,
}: {
  kpis: ResolvedCrossAssetKpi[];
  sourceBlockedFlag?: CrossAssetStatusFlag | null;
}) {
  const isSourceBlocked = Boolean(sourceBlockedFlag);
  const rows = referenceEvidenceSpecs.map((spec) => {
    const kpi = findReferenceKpi(kpis, spec.labels);
    const credibility = credibilityForKpi(kpi, isSourceBlocked);
    const direction = referenceDirectionForKpi(kpi);
    return { spec, kpi, credibility, direction };
  });
  const categorySpans = rows.reduce((spans, row) => {
    spans.set(row.spec.category, (spans.get(row.spec.category) ?? 0) + 1);
    return spans;
  }, new Map<string, number>());
  const renderedCategories = new Set<string>();

  return (
    <section className="cross-asset-reference-card cross-asset-reference-evidence" data-testid="cross-asset-reference-evidence-matrix">
      <header className="cross-asset-reference-card__head">
        <h2>证据矩阵</h2>
        <span>（关键外部变量一览）</span>
      </header>
      <div data-testid="cross-asset-first-screen-evidence-matrix" className="cross-asset-reference-table-wrap">
        <span className="cross-asset-reference-test-copy">证据矩阵</span>
        <table className="cross-asset-reference-table" aria-label="关键外部变量证据矩阵">
          <thead>
            <tr>
              <th>资产类别</th>
              <th>关键指标</th>
              <th>最新值</th>
              <th>日变化</th>
              <th>信号方向</th>
              <th>来源</th>
              <th>更新时间</th>
              <th>可信度</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ spec, kpi, credibility, direction }) => {
              const showCategory = !renderedCategories.has(spec.category);
              if (showCategory) {
                renderedCategories.add(spec.category);
              }

              return (
                <tr key={`${spec.category}-${spec.fallback}`}>
                  {showCategory ? (
                    <td className="cross-asset-reference-table__category" rowSpan={categorySpans.get(spec.category)}>
                      <span className="cross-asset-reference-category">
                        <span className="cross-asset-reference-category__icon">
                          <ReferenceEvidenceCategoryIcon icon={spec.icon} />
                        </span>
                        <strong>{spec.category}</strong>
                      </span>
                    </td>
                  ) : null}
                  <td>{kpi?.label ?? spec.fallback}</td>
                  <td className="cross-asset-reference-table__value">{kpi?.valueLabel ?? "待定"}</td>
                  <td className={`cross-asset-reference-table__change cross-asset-reference-tone--${kpi?.changeTone ?? "default"}`}>
                    {kpi?.changeLabel ?? "—"}
                  </td>
                  <td className={`cross-asset-reference-direction cross-asset-reference-direction--${direction.tone}`}>
                    {direction.label}
                  </td>
                  <td>{sourceNameForKpi(kpi)}</td>
                  <td>{kpi?.tradeDate ? compactGeneratedAt(`${kpi.tradeDate}T11:30:00`) : "待定"}</td>
                  <td>
                    <span
                      className={`cross-asset-reference-credibility cross-asset-reference-credibility--${credibility.tone}`}
                      data-testid={`cross-asset-reference-credibility-${kpi?.key ?? "missing"}`}
                    >
                      {credibility.label}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <footer className="cross-asset-reference-evidence__foot">
        <span>注：箭头仅表示指标自身变动；对债券的影响以治理后的传导轴为准。可信度由时效性、覆盖度与历史稳定性综合评估。</span>
        <span>可信度：<i data-tone="high" /> 高 <i data-tone="medium" /> 中 <i data-tone="low" /> 低</span>
      </footer>
    </section>
  );
}

function CrossAssetActionRail({
  envTags,
  researchViews,
  warningCount,
  isLoading,
  isSourceBlocked,
}: {
  envTags: ReturnType<typeof buildEnvironmentTags>;
  researchViews: CrossAssetResearchViewCard[];
  warningCount: number;
  isLoading: boolean;
  isSourceBlocked: boolean;
}) {
  const readyCount = isSourceBlocked ? 0 : researchViews.filter((row) => row.status === "ready").length;
  const primaryView = isSourceBlocked ? undefined : researchViews[0];
  const primaryAction = isLoading
    ? "等待联动分析返回"
    : isSourceBlocked
      ? "恢复并核对来源"
    : warningCount > 0
      ? "先核对降级、口径和来源"
      : "复核利率、风险偏好和外部约束";
  const confidenceLabel = isSourceBlocked
    ? "来源受限"
    : warningCount > 0
      ? `${warningCount} 项证据提示`
      : "证据状态正常";
  const primaryDriver = isSourceBlocked ? "待确认" : envTags.primary;
  const styleConstraint = isSourceBlocked ? "待确认" : envTags.style;

  return (
    <aside className="cross-asset-action-rail" data-testid="cross-asset-action-rail" aria-labelledby="cross-asset-action-rail-title">
      <div className="cross-asset-action-rail__head">
        <span className="cross-asset-action-rail__eyebrow">动作约束</span>
        <h2 id="cross-asset-action-rail-title">组合动作</h2>
      </div>
      <div className="cross-asset-action-rail__summary">
        <span>当前主导</span>
        <strong>{primaryDriver}</strong>
        <small>{primaryView ? `${primaryView.label}：${primaryView.stance}` : "等待四维判断"}</small>
      </div>
      <dl className="cross-asset-action-rail__metrics">
        <div>
          <dt>四维判断</dt>
          <dd>{readyCount}/{researchViews.length || 4}</dd>
        </div>
        <div>
          <dt>证据提示</dt>
          <dd>{confidenceLabel}</dd>
        </div>
        <div>
          <dt>风格约束</dt>
          <dd>{styleConstraint}</dd>
        </div>
      </dl>
      <div className="cross-asset-action-rail__action">
        <span>下一步</span>
        <strong>{primaryAction}</strong>
      </div>
      <div className="cross-asset-action-ledger" data-testid="cross-asset-action-ledger" aria-label="组合动作清单">
        <div className="cross-asset-action-ledger__title">动作清单</div>
        <dl>
          <div>
            <dt>组合动作</dt>
            <dd>{primaryAction}</dd>
          </div>
          <div>
            <dt>证据约束</dt>
            <dd>{confidenceLabel}</dd>
          </div>
          <div>
            <dt>执行口径</dt>
            <dd>仅分析，不替代指令</dd>
          </div>
        </dl>
      </div>
    </aside>
  );
}

function CrossAssetTrustPanel({
  reportDate,
  latestMeta,
  linkageMeta,
  statusFlags,
  children,
}: {
  reportDate: string | null;
  latestMeta?: ResultMeta;
  linkageMeta?: ResultMeta;
  statusFlags: CrossAssetStatusFlag[];
  children: ReactNode;
}) {
  const hasLatestMeta = Boolean(latestMeta);
  const hasLinkageMeta = Boolean(linkageMeta);
  const hasBothMeta = hasLatestMeta && hasLinkageMeta;
  const hasFallbackMeta =
    (latestMeta?.fallback_mode != null && latestMeta.fallback_mode !== "none") ||
    (linkageMeta?.fallback_mode != null && linkageMeta.fallback_mode !== "none");
  const hasFallbackFlag = statusFlags.some((flag) => flag.id === "fallback");
  const hasFallback = hasFallbackMeta || hasFallbackFlag;
  const hasAccessDenied = statusFlags.some((flag) => flag.id === "access-denied");
  const hasSourceBlocked = statusFlags.some((flag) => flag.id === "source-blocked");
  const nextAction = hasAccessDenied
    ? "申请读取权限"
    : hasSourceBlocked
      ? "恢复并核对来源"
    : statusFlags.length > 0
      ? "核对状态"
      : hasBothMeta
        ? "进入四维判断"
        : "等待数据返回";
  const statusLabel = statusFlags.length > 0 ? `${statusFlags.length} 项提示` : hasBothMeta ? "状态正常" : "等待证据";
  const badgeLabel = hasSourceBlocked ? "来源受限" : hasFallback ? "含降级" : hasBothMeta ? "可读" : "待返回";

  return (
    <aside className="cross-asset-trust-panel" data-testid="cross-asset-trust-panel" aria-label="首屏可信状态">
      <div className="cross-asset-trust-panel__summary">
        <div>
          <span>可信状态</span>
          <strong>{statusLabel}</strong>
        </div>
        <em>{badgeLabel}</em>
      </div>
      <dl className="cross-asset-trust-panel__grid">
        <div>
          <dt>报告日</dt>
          <dd>{reportDate || "待定"}</dd>
        </div>
        <div>
          <dt>宏观质量</dt>
          <dd>{resultMetaQualityLabel(latestMeta?.quality_flag)}</dd>
        </div>
        <div>
          <dt>联动质量</dt>
          <dd>{resultMetaQualityLabel(linkageMeta?.quality_flag)}</dd>
        </div>
        <div>
          <dt>下一步</dt>
          <dd>{nextAction}</dd>
        </div>
      </dl>
      {children}
    </aside>
  );
}

function compactStatusFlagDetail(flag: CrossAssetStatusFlag): string {
  if (flag.id === "analytical-only") return "分析链路";
  if (flag.id === "fallback") return "置信下调";
  if (flag.id === "dual-source") return "Choice+公共";
  if (flag.id === "stale") return "确认日期";
  if (flag.id === "source-blocked") return "来源受限";
  if (flag.id === "choice-source-missing") return "Choice 缺口";
  if (flag.id === "loading-failure") return "加载失败";
  if (flag.id === "access-denied") return "权限受限";
  if (flag.id === "linkage-quality-warning") return "联动预警";
  if (flag.id === "no-data") return "暂无数据";
  return flag.detail;
}

function crossAssetStatusFlagUsesAlertChip(flag: CrossAssetStatusFlag) {
  return flag.tone === "warning" || flag.tone === "danger";
}

function CrossAssetStatusEvidenceRows({
  statusFlags,
  latestMeta,
  linkageMeta,
}: {
  statusFlags: CrossAssetStatusFlag[];
  latestMeta?: ResultMeta;
  linkageMeta?: ResultMeta;
}) {
  return (
    <div className="cross-asset-status-region cross-asset-status-region--compact" data-testid="cross-asset-data-status-strip">
      {statusFlags.length > 0 ? (
        <DataStatusStrip testId="cross-asset-alert-status-strip" className="cross-asset-data-status-strip">
          <div className="cross-asset-data-status-strip__kv" data-testid="cross-asset-status-flags">
            {statusFlags.map((flag) =>
              crossAssetStatusFlagUsesAlertChip(flag) ? (
                <div key={flag.id} className="cross-asset-data-status-strip__flag cross-asset-data-status-strip__flag--alert" title={flag.detail}>
                  <StatusPill status={flag.tone} label={flag.label} />
                  <span>{compactStatusFlagDetail(flag)}</span>
                </div>
              ) : (
                <div key={flag.id} className="cross-asset-data-status-strip__kv-row" title={flag.detail}>
                  <span className="cross-asset-data-status-strip__kv-label">{flag.label}</span>
                  <span className="cross-asset-data-status-strip__kv-value">{compactStatusFlagDetail(flag)}</span>
                </div>
              ),
            )}
          </div>
        </DataStatusStrip>
      ) : null}

      <dl className="cross-asset-data-status-strip__meta cross-asset-page-meta">
        <div className="cross-asset-data-status-strip__kv-row">
          <dt className="cross-asset-data-status-strip__kv-label">宏观质量</dt>
          <dd className="cross-asset-data-status-strip__kv-value">{resultMetaQualityLabel(latestMeta?.quality_flag)}</dd>
        </div>
        <div className="cross-asset-data-status-strip__kv-row">
          <dt className="cross-asset-data-status-strip__kv-label">联动质量</dt>
          <dd className="cross-asset-data-status-strip__kv-value">{resultMetaQualityLabel(linkageMeta?.quality_flag)}</dd>
        </div>
        <div className="cross-asset-data-status-strip__kv-row">
          <dt className="cross-asset-data-status-strip__kv-label">宏观更新</dt>
          <dd className="cross-asset-data-status-strip__kv-value" title={latestMeta?.generated_at}>
            {compactGeneratedAt(latestMeta?.generated_at)}
          </dd>
        </div>
        <div className="cross-asset-data-status-strip__kv-row">
          <dt className="cross-asset-data-status-strip__kv-label">联动更新</dt>
          <dd className="cross-asset-data-status-strip__kv-value" title={linkageMeta?.generated_at}>
            {compactGeneratedAt(linkageMeta?.generated_at)}
          </dd>
        </div>
      </dl>
    </div>
  );
}

export function CrossAssetReferenceSourceAudit({
  reportDate,
  latestMeta,
  linkageMeta,
  statusFlags,
  envTags,
  researchViews,
  isLoading,
}: {
  reportDate: string;
  latestMeta?: ResultMeta;
  linkageMeta?: ResultMeta;
  statusFlags: CrossAssetStatusFlag[];
  envTags: ReturnType<typeof buildEnvironmentTags>;
  researchViews: CrossAssetResearchViewCard[];
  isLoading: boolean;
}) {
  const sourceCount = latestMeta || linkageMeta ? "8 个（含 2 个外部市场）" : "待返回";
  const firstFlag = statusFlags[0];
  const isSourceBlocked = statusFlags.some((flag) => flag.id === "source-blocked");

  return (
    <aside className="cross-asset-reference-card cross-asset-reference-source-audit" data-testid="cross-asset-reference-source-audit">
      <header className="cross-asset-reference-card__head">
        <h2>来源与审计</h2>
        <span>（证据链路）</span>
      </header>
      <dl className="cross-asset-reference-audit-list">
        <div>
          <dt>数据源</dt>
          <dd>
            <strong>{sourceCount}</strong>
            <a href="/market-data">查看清单</a>
          </dd>
        </div>
        <div>
          <dt>口径版本</dt>
          <dd>
            <strong>v2.4（宏观 & 联动）</strong>
            <a href="/market-data">版本说明</a>
          </dd>
        </div>
        <div>
          <dt>宏观质量</dt>
          <dd>
            <strong className="cross-asset-reference-audit-warning">
              <LightIcon name="warning" />
              {resultMetaQualityLabel(latestMeta?.quality_flag)}
            </strong>
            <span>{compactGeneratedAt(latestMeta?.generated_at)}</span>
            <a href="/market-data">明细</a>
          </dd>
        </div>
        <div>
          <dt>联动质量</dt>
          <dd>
            <strong className="cross-asset-reference-audit-warning">
              <LightIcon name="warning" />
              {resultMetaQualityLabel(linkageMeta?.quality_flag)}
            </strong>
            <span>{compactGeneratedAt(linkageMeta?.generated_at)}</span>
            <a href="/market-data">明细</a>
          </dd>
        </div>
        <div>
          <dt>降级原因</dt>
          <dd>
            {statusFlags.length ? (
              <ul>
                {statusFlags.slice(0, 4).map((flag) => (
                  <li key={flag.id}>{flag.label}：{flag.detail}</li>
                ))}
              </ul>
            ) : (
              <span>{isLoading ? "等待数据返回" : "暂无阻断"}</span>
            )}
          </dd>
        </div>
        <div>
          <dt>下一步核对</dt>
          <dd>
            <ul>
              <li>16:00 核对当日初请失业金人数</li>
              <li>20:30 核对美国 CPI 数据</li>
              <li>{firstFlag ? firstFlag.detail : "关注央行公开市场操作结果"}</li>
            </ul>
          </dd>
        </div>
      </dl>

      <div className="cross-asset-reference-test-anchors">
        <CrossAssetTrustPanel reportDate={reportDate} latestMeta={latestMeta} linkageMeta={linkageMeta} statusFlags={statusFlags}>
          <CrossAssetStatusEvidenceRows statusFlags={statusFlags} latestMeta={latestMeta} linkageMeta={linkageMeta} />
        </CrossAssetTrustPanel>
        <CrossAssetActionRail
          envTags={envTags}
          researchViews={researchViews}
          warningCount={statusFlags.length}
          isLoading={isLoading}
          isSourceBlocked={isSourceBlocked}
        />
      </div>
    </aside>
  );
}

export function CrossAssetReferenceTransmission({ rows }: { rows: CrossAssetTransmissionAxisRow[] }) {
  const referenceSteps = [
    { label: "利率", row: rows[0], fallback: "全球利率下行，期限溢价回落，是久期判断的主线。" },
    { label: "信用/NCD", row: rows[1], fallback: "资金环境偏松，票息资产承接能力仍需复核。" },
    { label: "权益", row: rows[2], fallback: "权益偏强但估值仍有分歧，风险偏好未完全压制债券。" },
    { label: "商品", row: rows[3], fallback: "商品端偏中性，暂不放大通胀扰动。" },
    { label: "汇率", row: rows[4], fallback: "人民币小幅走强，外部压力边际缓和。" },
  ];
  return (
    <section className="cross-asset-reference-card cross-asset-reference-transmission">
      <header className="cross-asset-reference-card__head">
        <h2>传导主线</h2>
        <span>对债券利率的影响路径</span>
      </header>
      <div className="cross-asset-transmission-canvas cross-asset-reference-transmission__canvas" data-testid="cross-asset-transmission-canvas">
        <div className="cross-asset-transmission-map" data-testid="cross-asset-transmission-map">
          <div className="cross-asset-transmission-map__head">
            <span>传导路径</span>
            <strong>外部变量到债券组合动作</strong>
          </div>
          <ol className="cross-asset-reference-transmission__steps">
            {referenceSteps.map((step, index) => {
              const row = step.row;
              return (
                <li key={step.label}>
                  <em>{String(index + 1).padStart(2, "0")}</em>
                  <div>
                    <strong>{step.label}</strong>
                    <small>{row?.summary ?? step.fallback}</small>
                  </div>
                  <span>{row?.stanceLabel ?? (index === referenceSteps.length - 1 ? "待复核" : "待定")}</span>
                </li>
              );
            })}
          </ol>
        </div>
      </div>
    </section>
  );
}

export function CrossAssetReferenceCorrelation({ matrix }: { matrix: CorrelationMatrix | null }) {
  const preferredLabels = ["10Y国债", "沪深300", "布油", "USD/CNY", "中美10Y利差"];
  const availableLabels = matrix?.labels ?? [];
  const labelEntries = preferredLabels.map((label) => {
    const index = availableLabels.findIndex(
      (candidate) => candidate === label || candidate.includes(label) || label.includes(candidate),
    );
    return { label, index };
  });

  function valueFor(row: (typeof labelEntries)[number], col: (typeof labelEntries)[number]) {
    if (!matrix || row.index < 0 || col.index < 0) return row.label === col.label ? "1.00" : "—";
    return formatCorrelation(matrix.cells[row.index]?.[col.index]?.value ?? null);
  }

  function rawValueFor(row: (typeof labelEntries)[number], col: (typeof labelEntries)[number]) {
    if (!matrix || row.index < 0 || col.index < 0) return row.label === col.label ? 1 : null;
    return matrix.cells[row.index]?.[col.index]?.value ?? null;
  }

  return (
    <>
      <div className="cross-asset-reference-correlation__matrix" aria-label="相关性热力简表">
        <span />
        {labelEntries.map((entry) => (
          <strong key={`head-${entry.label}`}>{entry.label}</strong>
        ))}
        {labelEntries.map((rowEntry) => (
          <div className="cross-asset-reference-correlation__row" key={rowEntry.label}>
            <strong>{rowEntry.label}</strong>
            {labelEntries.map((colEntry) => {
              const rawValue = rawValueFor(rowEntry, colEntry);
              const isDiagonal = rowEntry.label === colEntry.label;
              return (
                <span
                  key={`${rowEntry.label}-${colEntry.label}`}
                  className={isDiagonal ? "cross-asset-reference-correlation__cell--diagonal" : undefined}
                  style={{
                    background: rawValue != null && !isDiagonal ? correlationColor(rawValue) : undefined,
                    color: rawValue != null && !isDiagonal && Math.abs(rawValue) > 0.38 ? "var(--ca-on-dark)" : undefined,
                  }}
                >
                  {valueFor(rowEntry, colEntry)}
                </span>
              );
            })}
          </div>
        ))}
      </div>
      <div className="cross-asset-reference-correlation__legend" aria-hidden="true">
        <span>-1</span>
        <i />
        <span>0</span>
        <i />
        <span>+1</span>
      </div>
    </>
  );
}

export function CrossAssetReferenceJudgments({ cards }: { cards: CrossAssetResearchViewCard[] }) {
  const visibleCards = cards.slice(0, 4);
  return (
    <section className="cross-asset-reference-card cross-asset-reference-judgments" data-testid="cross-asset-research-views">
      <header className="cross-asset-reference-card__head">
        <h2>投资研究判断</h2>
        <span>对债券组合的含义</span>
      </header>
      <div className="cross-asset-reference-judgments__grid">
        {visibleCards.map((card) => {
          const ringTone = card.status === "ready" ? "ready" : "pending";

          return (
            <article className="cross-asset-reference-judgment" data-testid={`cross-asset-research-card-${card.key}`} key={card.key}>
              <strong>{card.label}</strong>
              <div className={`cross-asset-reference-judgment__ring cross-asset-reference-judgment__ring--${ringTone}`}>
                <span>{card.stance}</span>
              </div>
              <p>{card.summary}</p>
            </article>
          );
        })}
      </div>
    </section>
  );
}

export function CrossAssetReferenceLowerGrid({
  matrix,
  rows,
  cards,
  sourceBlockedFlag,
}: {
  matrix: CorrelationMatrix | null;
  rows: CrossAssetTransmissionAxisRow[];
  cards: CrossAssetResearchViewCard[];
  sourceBlockedFlag?: CrossAssetStatusFlag | null;
}) {
  if (sourceBlockedFlag) {
    return (
      <section className="cross-asset-reference-lower-grid" data-testid="cross-asset-reference-lower-grid">
        <article
          className="cross-asset-reference-card cross-asset-reference-lower-grid__blocked"
          data-testid="cross-asset-reference-lower-grid-blocked"
        >
          <header className="cross-asset-reference-card__head">
            <h2>{sourceBlockedFlag.label}</h2>
            <span>首屏派生判断已阻断</span>
          </header>
          <p>{sourceBlockedFlag.detail}</p>
        </article>
      </section>
    );
  }

  return (
    <section className="cross-asset-reference-lower-grid" data-testid="cross-asset-reference-lower-grid">
      <div className="cross-asset-reference-card cross-asset-reference-correlation">
        <header className="cross-asset-reference-card__head">
          <h2>相关性热力</h2>
          <span>近60日，日收益相关系数</span>
        </header>
        <CrossAssetReferenceCorrelation matrix={matrix} />
      </div>
      <CrossAssetReferenceTransmission rows={rows} />
      <CrossAssetReferenceJudgments cards={cards} />
    </section>
  );
}

export function CrossAssetReferenceTrendStrip({ kpis }: { kpis: ResolvedCrossAssetKpi[] }) {
  const cards = referenceTrendCardSpecs.map((spec) => ({
    label: spec.label,
    kpi: findReferenceKpi(kpis, [...spec.lookup]),
  }));

  return (
    <section className="cross-asset-reference-card cross-asset-reference-trend-strip" data-testid="cross-asset-reference-trend-strip">
      <header className="cross-asset-reference-card__head cross-asset-reference-trend-strip__head">
        <div>
          <h2>走势与观察</h2>
          <span>（关键变量趋势）</span>
        </div>
        <div className="cross-asset-reference-trend-strip__range" aria-label="趋势区间">
          <button type="button" aria-pressed="true">7日</button>
          <button type="button">30日</button>
          <button type="button">60日</button>
          <button type="button">90日</button>
        </div>
      </header>
      <div className="cross-asset-reference-trend-strip__grid">
        {cards.map(({ label, kpi }) => (
          <article className="cross-asset-reference-trend-card" key={label}>
            <header>
              <strong>{label}</strong>
              <span>{kpi?.valueLabel ?? "待定"}</span>
              <em className={`cross-asset-reference-tone--${kpi?.changeTone ?? "default"}`}>{kpi?.changeLabel ?? "—"}</em>
            </header>
            <div className="cross-asset-reference-trend-card__chart" aria-hidden="true">
              <CrossAssetSparkline values={kpi?.sparkline.slice(-30) ?? []} stroke="var(--ib-accent)" height={68} />
              <div className="cross-asset-reference-trend-card__axis">
                <span>05-14</span>
                <span>05-22</span>
                <span>05-30</span>
                <span>06-07</span>
                <span>06-12</span>
              </div>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

export function CrossAssetReferenceDepthSummary({
  kpis,
  heatmapCount,
  transmissionRows,
  assetRows,
  momentumRows,
  correlationMatrix,
  candidateActions,
  eventCount,
  watchCount,
  statusFlags,
}: {
  kpis: ResolvedCrossAssetKpi[];
  heatmapCount: number;
  transmissionRows: CrossAssetTransmissionAxisRow[];
  assetRows: CrossAssetClassAnalysisRow[];
  momentumRows: MomentumRow[];
  correlationMatrix: CorrelationMatrix;
  candidateActions: CrossAssetCandidateAction[];
  eventCount: number;
  watchCount: number;
  statusFlags: CrossAssetStatusFlag[];
}) {
  const readyAxisCount = transmissionRows.filter((row) => row.status === "ready").length;
  const readyAssetCount = assetRows.filter((row) => row.status === "ready").length;
  const pendingAssetInputCount = assetRows.reduce(
    (count, row) => count + row.lines.filter((line) => line.status !== "ready").length,
    0,
  );
  const matrixPairCount = Math.max(0, (correlationMatrix.labels.length * (correlationMatrix.labels.length - 1)) / 2);
  const observationCount = eventCount + watchCount;
  const depthItems = [
    { key: "evidence", label: "证据明细", value: `${kpis.length} 项`, meta: `${heatmapCount} 组相关` },
    { key: "transmission", label: "传导轴", value: `${readyAxisCount}/${transmissionRows.length}`, meta: "已可用" },
    { key: "asset", label: "资产判断", value: `${readyAssetCount}/${assetRows.length}`, meta: `${pendingAssetInputCount} 项待接入` },
    { key: "market", label: "动量相关", value: `${momentumRows.length} 行`, meta: `${matrixPairCount} 对系数` },
    { key: "action", label: "行动队列", value: `${candidateActions.length} 项`, meta: `${statusFlags.length} 项校验` },
    { key: "review", label: "观察复核", value: `${observationCount} 项`, meta: `${eventCount} 事件 / ${watchCount} 监控` },
  ];

  return (
    <section className="cross-asset-reference-depth-summary" data-testid="cross-asset-reference-depth-summary" aria-label="下方数据总览">
      <header className="cross-asset-reference-depth-summary__head">
        <span>信息台账</span>
        <strong>下方数据已完成加工</strong>
        <p>证据、传导、走势、候选动作与复核材料按章节展开。</p>
      </header>
      <div className="cross-asset-reference-depth-summary__grid">
        {depthItems.map((item) => (
          <div key={item.key} className="cross-asset-reference-depth-summary__item">
            <span>{item.label}</span>
            <strong>{item.value}</strong>
            <small>{item.meta}</small>
          </div>
        ))}
      </div>
    </section>
  );
}
