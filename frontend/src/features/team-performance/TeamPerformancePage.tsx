import { useEffect, useMemo, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";

import type { ResultMeta } from "../../api/contracts";
import { useApiClient } from "../../api/client";
import { DataQualityBanner } from "../../components/page/DataQualityBanner";
import { FormalResultMetaPanel } from "../../components/page/FormalResultMetaPanel";
import { FilterBar } from "../../components/FilterBar";
import { KpiCard } from "../../components/KpiCard";
import { SectionLead } from "../../components/page/SectionLead";
import { AsyncSection } from "../executive-dashboard/components/AsyncSection";
import {
  ASSESSMENT_CENTERS_2025,
  buildTeamPerformanceQ1CaliberModel,
  buildTeamPerformanceViewModel,
  formatConfidenceLabel,
  formatQ1AllocationLabel,
  formatQ1EvidenceStatusLabel,
  formatRatePct,
  formatScore,
  formatWanFromYuan,
  formatYiFromYuan,
} from "./teamPerformancePageModel";
import "./TeamPerformancePage.css";

const DEFAULT_YEAR = 2025;
const DEFAULT_AS_OF_DATE = "2025-12-31";
const Q1_CALIBER_YEAR = 2026;
const Q1_CALIBER_AS_OF_DATE = "2026-03-31";

type CenterId = (typeof ASSESSMENT_CENTERS_2025)[number]["centerId"];

function scoreTone(scoreRate: number | null) {
  if (scoreRate === null) {
    return "default" as const;
  }
  if (scoreRate >= 1) {
    return "positive" as const;
  }
  if (scoreRate >= 0.85) {
    return "warning" as const;
  }
  return "negative" as const;
}

function mappingStatusTone(status: string) {
  if (status === "已映射") {
    return "positive" as const;
  }
  if (status === "挂钩引用") {
    return "default" as const;
  }
  return "warning" as const;
}

function q1StatusTone(status: string) {
  if (status === "direct") {
    return "positive" as const;
  }
  if (status === "excluded") {
    return "default" as const;
  }
  return "warning" as const;
}

function q1RulePillTone(allocation: string, evidenceStatus: string) {
  if (allocation === "subtract") {
    return "subtract";
  }
  if (allocation === "reference") {
    return "reference";
  }
  if (evidenceStatus === "split-needed" || allocation === "pending") {
    return "pending";
  }
  if (evidenceStatus === "aggregate") {
    return "aggregate";
  }
  return "include";
}

const Q1_CALIBER_DECISION_LINES = [
  "自营中心：10项投资口径纳入，人民币资管产品扣除J4产业基金。",
  "债券交易室：只接政策性金融债、同业存单、地方债、国债、铁道债。",
  "金融同业部：人民币拆放同业和人民币同业负债，外币剥离。",
  "外汇与衍生品室：只接外币债、外币拆放和外币负债；derivatives不进。",
  "代客交易：外汇远期/掉期归这里，当前聚合行只作待拆证据。",
  "产品与市场室：产业基金按J4开头资产映射，来源页面名保持现状。",
];

function evidenceHeadline(endpoint: string) {
  return endpoint === "by-business-ytd" ? "按业务口径" : "按产品口径";
}

function formatMetaQuality(flag: ResultMeta["quality_flag"]) {
  if (flag === "warning") {
    return "预警";
  }
  if (flag === "error") {
    return "错误";
  }
  if (flag === "stale") {
    return "陈旧";
  }
  return "正常";
}

function formatMetaFallback(mode: ResultMeta["fallback_mode"]) {
  return mode === "latest_snapshot" ? "最新快照降级" : "未降级";
}

function formatMetaGeneratedAt(value: string) {
  const parsed = Date.parse(value);
  if (Number.isNaN(parsed)) {
    return value;
  }
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(parsed));
}

function resultMetaTone(meta: ResultMeta) {
  if (
    meta.quality_flag === "ok" &&
    meta.fallback_mode === "none" &&
    meta.vendor_status === "ok"
  ) {
    return "positive" as const;
  }
  if (meta.quality_flag === "error" || meta.quality_flag === "stale") {
    return "negative" as const;
  }
  return "warning" as const;
}

function resultMetaSummaryLabel(meta: ResultMeta) {
  if (meta.quality_flag === "error") {
    return "质量错误";
  }
  if (meta.quality_flag === "stale") {
    return "数据陈旧";
  }
  if (meta.fallback_mode !== "none") {
    return "存在降级";
  }
  if (meta.quality_flag === "warning") {
    return "质量预警";
  }
  return "链路正常";
}

type StateTone = "warning" | "error" | "empty";

type StateFact = {
  label: string;
  value: string;
};

type DashboardStatePanelProps = {
  testId: string;
  tone: StateTone;
  badge: string;
  title: string;
  description: string;
  facts: StateFact[];
  impacts: string[];
  action?: ReactNode;
};

function DashboardStatePanel({
  testId,
  tone,
  badge,
  title,
  description,
  facts,
  impacts,
  action,
}: DashboardStatePanelProps) {
  return (
    <section
      data-testid={testId}
      className={`team-performance-page__state-card team-performance-page__state-card--${tone}`}
    >
      <div className="team-performance-page__state-card-header">
        <div className="team-performance-page__state-card-heading">
          <span className={`team-performance-page__state-badge team-performance-page__state-badge--${tone}`}>
            {badge}
          </span>
          <h2>{title}</h2>
        </div>
        {action ? <div className="team-performance-page__state-card-action">{action}</div> : null}
      </div>

      <div className="team-performance-page__state-card-layout">
        <div className="team-performance-page__state-card-main">
          <p>{description}</p>
          <dl className="team-performance-page__state-facts">
            {facts.map((fact) => (
              <div key={fact.label} className="team-performance-page__state-fact">
                <dt>{fact.label}</dt>
                <dd>{fact.value}</dd>
              </div>
            ))}
          </dl>
        </div>

        <div className="team-performance-page__state-aside">
          <h3>当前影响</h3>
          <ul className="team-performance-page__state-impact-list">
            {impacts.map((impact) => (
              <li key={impact}>{impact}</li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}

export default function TeamPerformancePage() {
  const client = useApiClient();
  const [selectedYear] = useState(DEFAULT_YEAR);
  const [selectedDate, setSelectedDate] = useState("");
  const [selectedCenterId, setSelectedCenterId] = useState<CenterId>("product-market");

  const datesQuery = useQuery({
    queryKey: ["team-performance", "formal-dates", client.mode],
    queryFn: () => client.getFormalPnlDates(),
    retry: false,
  });

  const availableDates = datesQuery.data?.result.report_dates ?? [];
  const hasDefaultDate = availableDates.includes(DEFAULT_AS_OF_DATE);
  const hasQ1CaliberDate = availableDates.includes(Q1_CALIBER_AS_OF_DATE);

  useEffect(() => {
    if (hasDefaultDate) {
      setSelectedDate((current) => current || DEFAULT_AS_OF_DATE);
      return;
    }
    if (!datesQuery.isLoading) {
      setSelectedDate("");
    }
  }, [datesQuery.isLoading, hasDefaultDate]);

  const canLoadEvidence = hasDefaultDate && selectedDate === DEFAULT_AS_OF_DATE;
  const canLoadQ1CaliberEvidence = canLoadEvidence && hasQ1CaliberDate;

  const byBusinessQuery = useQuery({
    queryKey: ["team-performance", "by-business-ytd", client.mode, selectedYear, selectedDate],
    queryFn: () => client.getPnlByBusinessYtd(selectedYear, selectedDate),
    enabled: canLoadEvidence,
    retry: false,
  });

  const productCategoryQuery = useQuery({
    queryKey: ["team-performance", "product-category-ytd", client.mode, selectedDate],
    queryFn: () =>
      client.getProductCategoryPnl({
        reportDate: selectedDate,
        view: "ytd",
      }),
    enabled: canLoadEvidence,
    retry: false,
  });

  const q1ByBusinessMonthlyQuery = useQuery({
    queryKey: [
      "team-performance",
      "q1-caliber",
      "by-business-monthly",
      client.mode,
      Q1_CALIBER_YEAR,
      Q1_CALIBER_AS_OF_DATE,
    ],
    queryFn: () => client.getPnlByBusinessMonthly(Q1_CALIBER_YEAR, Q1_CALIBER_AS_OF_DATE),
    enabled: canLoadQ1CaliberEvidence,
    retry: false,
  });

  const q1ProductCategoryQuery = useQuery({
    queryKey: [
      "team-performance",
      "q1-caliber",
      "product-category-ytd",
      client.mode,
      Q1_CALIBER_AS_OF_DATE,
    ],
    queryFn: () =>
      client.getProductCategoryPnl({
        reportDate: Q1_CALIBER_AS_OF_DATE,
        view: "ytd",
      }),
    enabled: canLoadQ1CaliberEvidence,
    retry: false,
  });

  const viewModel = useMemo(
    () =>
      buildTeamPerformanceViewModel({
        byBusinessItems: byBusinessQuery.data?.result.items,
        productCategoryRows: productCategoryQuery.data?.result.rows,
        byBusinessMeta: byBusinessQuery.data?.result_meta ?? null,
        productCategoryMeta: productCategoryQuery.data?.result_meta ?? null,
      }),
    [byBusinessQuery.data, productCategoryQuery.data],
  );

  const q1CaliberModel = useMemo(
    () =>
      buildTeamPerformanceQ1CaliberModel({
        byBusinessMonthly: q1ByBusinessMonthlyQuery.data?.result,
        productCategoryRows: q1ProductCategoryQuery.data?.result.rows,
      }),
    [q1ByBusinessMonthlyQuery.data, q1ProductCategoryQuery.data],
  );

  const selectedCenter =
    viewModel.centers.find((center) => center.centerId === selectedCenterId) ?? viewModel.centers[0];
  const q1CaliberRows = q1CaliberModel.centers.flatMap((center) =>
    center.rules.map((rule) => ({ center, rule })),
  );
  const q1CaliberSummaries = q1CaliberModel.centers.map((center) => ({
    center,
    includedRules: center.rules.filter((rule) => rule.allocation === "include"),
    exceptionRules: center.rules.filter(
      (rule) => rule.allocation !== "include" || rule.evidenceStatus === "split-needed",
    ),
  }));

  const loading =
    datesQuery.isLoading ||
    (canLoadEvidence && (byBusinessQuery.isLoading || productCategoryQuery.isLoading));
  const error =
    datesQuery.isError || (canLoadEvidence && (byBusinessQuery.isError || productCategoryQuery.isError));
  const showNoSubstitution = !datesQuery.isLoading && !hasDefaultDate;
  const noMappedEvidence = canLoadEvidence && !loading && !error && viewModel.mappedCenterCount === 0;
  const q1CaliberLoading =
    canLoadQ1CaliberEvidence &&
    (q1ByBusinessMonthlyQuery.isLoading || q1ProductCategoryQuery.isLoading);
  const q1CaliberError =
    canLoadQ1CaliberEvidence &&
    (q1ByBusinessMonthlyQuery.isError || q1ProductCategoryQuery.isError);
  const resultMetaSections = [
    {
      key: "by-business-ytd",
      title: "业务种类损益 YTD",
      meta: byBusinessQuery.data?.result_meta,
    },
    {
      key: "product-category-ytd",
      title: "产品分类损益 YTD",
      meta: productCategoryQuery.data?.result_meta,
    },
  ] satisfies Array<{ key: string; title: string; meta: ResultMeta | null | undefined }>;
  const visibleResultMetaSections = resultMetaSections.filter(
    (section): section is { key: string; title: string; meta: ResultMeta } => Boolean(section.meta),
  );

  return (
    <section data-testid="team-performance-page" className="team-performance-page">
      <div className="team-performance-page__hero">
        <div className="team-performance-page__hero-copy">
          <h1 data-testid="team-performance-page-title" className="team-performance-page__title">
            Team Performance 工作损益分析
          </h1>
          <p className="team-performance-page__subtitle">
            聚焦回答“2025 年各部室考核得分如何，相关工作损益证据是多少”。Excel
            仍是方案底稿，页面只并排展示正式接口中可见的 YTD 损益证据。
          </p>
        </div>
        <span
          className={
            client.mode === "real"
              ? "team-performance-page__mode-badge team-performance-page__mode-badge--real"
              : "team-performance-page__mode-badge team-performance-page__mode-badge--mock"
          }
        >
          {client.mode === "real" ? "正式只读链路" : "本地演示数据"}
        </span>
      </div>

      <FilterBar className="team-performance-page__filter-bar">
        <label className="team-performance-page__filter">
          <span>考核年度</span>
          <select
            aria-label="team-performance-report-year"
            value={String(selectedYear)}
            className="team-performance-page__select"
            disabled
          >
            <option value="2025">2025</option>
          </select>
        </label>
        <label className="team-performance-page__filter">
          <span>证据日期</span>
          <select
            aria-label="team-performance-report-date"
            value={selectedDate}
            onChange={(event) => setSelectedDate(event.target.value)}
            className="team-performance-page__select"
            disabled={!hasDefaultDate}
          >
            {selectedDate ? null : <option value="">未提供 2025-12-31</option>}
            {hasDefaultDate ? <option value={DEFAULT_AS_OF_DATE}>{DEFAULT_AS_OF_DATE}</option> : null}
          </select>
        </label>
      </FilterBar>

      <SectionLead
        eyebrow="Assessment"
        title="2025 部室考核矩阵"
        description="首屏先看各部室总分、映射证据覆盖情况和正式读链路状态。所有损益都明确标为“映射分析”，不替代正式中心归属口径。"
      />

      <div data-testid="team-performance-summary-cards" className="team-performance-page__summary-grid">
        <KpiCard
          label="工作簿总得分"
          value={viewModel.totalWorkbookScore.toFixed(2)}
          unit="分"
          detail="直接汇总 Excel 底稿已有得分，不重算评分规则。"
          tone="positive"
        />
        <KpiCard
          label="部室数量"
          value={String(viewModel.totalCenterCount)}
          detail="2025 年度方案涉及的考核部室。"
        />
        <KpiCard
          label="已映射部室"
          value={String(viewModel.mappedCenterCount)}
          detail="至少存在一条正式 YTD 损益映射证据。"
          tone={viewModel.mappedCenterCount > 0 ? "positive" : "warning"}
        />
        <KpiCard
          label="证据状态"
          value={viewModel.visibleEvidenceStatus}
          detail="用于判断首屏结论是否已有正式接口支撑。"
          valueVariant="text"
          tone={viewModel.mappedCenterCount === 0 ? "warning" : "default"}
        />
      </div>

      <div data-testid="team-performance-warning-banner" className="team-performance-page__warning-stack">
        <DataQualityBanner
          resultMeta={byBusinessQuery.data?.result_meta ?? productCategoryQuery.data?.result_meta ?? null}
          warnings={viewModel.warnings}
          degradedReasons={
            showNoSubstitution
              ? ["正式日期列表未包含 2025-12-31，当前页面不会自动改用 2026 数据。"]
              : []
          }
        />
      </div>

      <section data-testid="team-performance-q1-caliber" className="team-performance-page__q1-panel">
        <div className="team-performance-page__q1-header">
          <div>
            <div className="team-performance-page__meta-eyebrow">Q1 Actual</div>
            <h2 className="team-performance-page__q1-title">2026 Q1实际口径拆解</h2>
            <p className="team-performance-page__q1-copy">
              只展示实际证据、来源行和口径状态；年度目标、达成判断和 Excel 外推数均不进入本区汇总。
            </p>
          </div>
          <div className="team-performance-page__q1-date-card">
            <span>证据期间</span>
            <strong>{q1CaliberModel.periodLabel}</strong>
          </div>
        </div>

        <div className="team-performance-page__q1-source-row">
          <span>{q1CaliberModel.sourceLabel}</span>
          <span>
            {canLoadQ1CaliberEvidence
              ? q1CaliberLoading
                ? "Q1证据加载中"
                : q1CaliberError
                  ? "Q1证据加载失败"
                  : "Q1证据已按业务种类FTP后净损益与产品分类净收入展示"
              : "正式日期列表暂未同时满足2025底稿和2026Q1证据"}
          </span>
        </div>

        <div className="team-performance-page__q1-warning-list">
          {q1CaliberModel.warnings.map((warning) => (
            <span key={warning}>{warning}</span>
          ))}
        </div>

        <div className="team-performance-page__q1-map">
          <div className="team-performance-page__q1-center-stack">
            {q1CaliberSummaries.map(
              ({ center, includedRules, exceptionRules }) => (
                <section key={center.centerId} className="team-performance-page__q1-center-band">
                  <div className="team-performance-page__q1-center-head">
                    <span>{center.centerName}</span>
                    <strong>{formatYiFromYuan(center.includedTotalYuan)}</strong>
                    <em>
                      纳入 {center.includedRuleCount} · 另列 {exceptionRules.length} · 待拆 {center.pendingRuleCount}
                    </em>
                  </div>
                  <div className="team-performance-page__q1-lane-grid">
                    <div className="team-performance-page__q1-lane">
                      <span className="team-performance-page__q1-lane-title">纳入汇总</span>
                      {includedRules.length > 0 ? (
                        <div className="team-performance-page__q1-pill-row">
                          {includedRules.map((rule) => (
                            <span
                              key={`${rule.businessLabel}-${rule.rowId ?? "pending"}-${rule.amountField ?? "none"}`}
                              className={`team-performance-page__q1-rule-pill team-performance-page__q1-rule-pill--${q1RulePillTone(
                                rule.allocation,
                                rule.evidenceStatus,
                              )}`}
                              title={`${formatQ1AllocationLabel(rule.allocation)} · ${formatQ1EvidenceStatusLabel(
                                rule.evidenceStatus,
                              )}`}
                            >
                              <span>{rule.businessLabel}</span>
                              <em>{formatQ1EvidenceStatusLabel(rule.evidenceStatus)}</em>
                            </span>
                          ))}
                        </div>
                      ) : (
                        <span className="team-performance-page__q1-empty">无纳入项</span>
                      )}
                    </div>
                    <div className="team-performance-page__q1-lane team-performance-page__q1-lane--attention">
                      <span className="team-performance-page__q1-lane-title">待拆 / 扣除 / 参考</span>
                      {exceptionRules.length > 0 ? (
                        <div className="team-performance-page__q1-pill-row">
                          {exceptionRules.map((rule) => (
                            <span
                              key={`${rule.businessLabel}-${rule.rowId ?? "pending"}-${rule.amountField ?? "none"}`}
                              className={`team-performance-page__q1-rule-pill team-performance-page__q1-rule-pill--${q1RulePillTone(
                                rule.allocation,
                                rule.evidenceStatus,
                              )}`}
                              title={`${formatQ1AllocationLabel(rule.allocation)} · ${formatQ1EvidenceStatusLabel(
                                rule.evidenceStatus,
                              )}`}
                            >
                              <span>{rule.businessLabel}</span>
                              <em>{formatQ1AllocationLabel(rule.allocation)}</em>
                            </span>
                          ))}
                        </div>
                      ) : (
                        <span className="team-performance-page__q1-empty">无待拆或扣除项</span>
                      )}
                    </div>
                  </div>
                </section>
              ),
            )}
          </div>

          <aside className="team-performance-page__q1-guide-panel" aria-label="Q1口径锚点">
            <span>口径锚点</span>
            <ul>
              {Q1_CALIBER_DECISION_LINES.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </aside>
        </div>

        <details className="team-performance-page__q1-ledger">
          <summary>
            <span>来源行明细</span>
            <strong>{q1CaliberRows.length} 条</strong>
          </summary>
          <div className="team-performance-page__q1-table-shell">
            <table className="team-performance-page__q1-table">
              <thead>
                <tr>
                  <th>中心</th>
                  <th>口径</th>
                  <th>来源</th>
                  <th>动作</th>
                  <th className="team-performance-page__table-cell--numeric">来源金额</th>
                  <th className="team-performance-page__table-cell--numeric">汇总贡献</th>
                  <th>状态</th>
                </tr>
              </thead>
              <tbody>
                {q1CaliberRows.map(({ center, rule }) => (
                  <tr key={`${rule.centerId}-${rule.businessLabel}-${rule.rowId ?? "pending"}-${rule.amountField ?? "none"}`}>
                    <td data-label="中心">{center.centerName}</td>
                    <td data-label="口径">
                      <strong className="team-performance-page__q1-business-name">{rule.businessLabel}</strong>
                      {rule.note ? <span className="team-performance-page__q1-note">{rule.note}</span> : null}
                    </td>
                    <td data-label="来源">
                      <div className="team-performance-page__q1-source-cell">
                        <span>{rule.sourceLabel}</span>
                        <code>{rule.rowId ?? "暂无独立行"}</code>
                        <span>{rule.amountField ?? "-"}</span>
                        <span>来源行：{rule.rowName}</span>
                      </div>
                    </td>
                    <td data-label="动作">{formatQ1AllocationLabel(rule.allocation)}</td>
                    <td data-label="来源金额" className="team-performance-page__table-cell--numeric">
                      {formatYiFromYuan(rule.amountYuan)}
                    </td>
                    <td data-label="汇总贡献" className="team-performance-page__table-cell--numeric">
                      {formatYiFromYuan(rule.contributionYuan)}
                    </td>
                    <td data-label="状态">
                      <span
                        className={`team-performance-page__status-pill team-performance-page__status-pill--${q1StatusTone(rule.evidenceStatus)}`}
                      >
                        {formatQ1EvidenceStatusLabel(rule.evidenceStatus)}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      </section>

      {showNoSubstitution ? (
        <DashboardStatePanel
          testId="team-performance-empty"
          tone="warning"
          badge="待正式日期"
          title="2025 证据日期未就绪"
          description="正式日期列表未包含 2025-12-31，因此当前页面只保留 2025 方案底稿视图，不会 silently substitute 2026。"
          facts={[
            { label: "考核年度", value: "锁定 2025" },
            { label: "目标日期", value: "2025-12-31" },
            { label: "页面策略", value: "不自动替代为 2026 数据" },
          ]}
          impacts={[
            "首屏仍可查看各部室 Excel 得分、权重和明细指标。",
            "映射分析证据将在正式日期可用后恢复并排展示。",
          ]}
        />
      ) : null}

      {error ? (
        <DashboardStatePanel
          testId="team-performance-error"
          tone="error"
          badge="链路异常"
          title="2025 工作损益证据加载失败"
          description="请先恢复 `getPnlByBusinessYtd` 与 `getProductCategoryPnl` 的正式读链路，再查看部室映射分析。"
          facts={[
            { label: "失败范围", value: "正式 YTD 证据接口" },
            { label: "目标日期", value: selectedDate || DEFAULT_AS_OF_DATE },
            { label: "页面策略", value: "保留底稿，不形成映射结论" },
          ]}
          impacts={[
            "工作簿得分和指标底稿仍可继续查看。",
            "重试成功后会按同一日期重新拉取两条证据链路。",
          ]}
          action={
            <button
              type="button"
              className="team-performance-page__retry-button"
              onClick={() => {
                void Promise.all([datesQuery.refetch(), byBusinessQuery.refetch(), productCategoryQuery.refetch()]);
              }}
            >
              重试
            </button>
          }
        />
      ) : null}

      {noMappedEvidence ? (
        <DashboardStatePanel
          testId="team-performance-empty"
          tone="empty"
          badge="未命中映射"
          title="暂无可展示证据"
          description="未找到可展示的部室工作损益证据。考核底稿仍可查看，但首屏不会给出映射损益结论。"
          facts={[
            { label: "接口日期", value: selectedDate || DEFAULT_AS_OF_DATE },
            { label: "映射结果", value: "未命中部室证据行" },
            { label: "页面策略", value: "不输出正式损益归因结论" },
          ]}
          impacts={[
            "各部室工作簿得分、权重和底稿指标仍可正常浏览。",
            "如后续补齐映射表或接口数据，页面会直接恢复映射分析展示。",
          ]}
        />
      ) : null}

      <AsyncSection
        title="部室工作损益矩阵"
        isLoading={loading}
        isError={false}
        isEmpty={false}
        fillHeight={false}
        onRetry={() => {
          void Promise.all([datesQuery.refetch(), byBusinessQuery.refetch(), productCategoryQuery.refetch()]);
        }}
      >
        <div className="team-performance-page__section-stack">
          <section className="team-performance-page__panel">
            <SectionLead
              eyebrow="Matrix"
              title="部室矩阵"
              description="按部室汇总显示 Excel 得分、映射损益、映射规模和覆盖状态。点击任一部室，下方查看对应的底稿指标和映射证据。"
            />

            <div className="team-performance-page__table-shell team-performance-page__table-shell--matrix">
              <table data-testid="team-performance-center-matrix" className="team-performance-page__table">
                <thead>
                  <tr>
                    <th>部室</th>
                    <th className="team-performance-page__table-cell--numeric">权重</th>
                    <th className="team-performance-page__table-cell--numeric">工作簿得分</th>
                    <th className="team-performance-page__table-cell--numeric">得分率</th>
                    <th className="team-performance-page__table-cell--numeric">映射损益</th>
                    <th className="team-performance-page__table-cell--numeric">映射规模</th>
                    <th>映射状态</th>
                  </tr>
                </thead>
                <tbody>
                  {viewModel.centers.map((center) => {
                    const isActive = center.centerId === selectedCenter.centerId;
                    return (
                      <tr
                        key={center.centerId}
                        className={isActive ? "team-performance-page__table-row-active" : undefined}
                      >
                        <td>
                          <button
                            type="button"
                            className="team-performance-page__matrix-button"
                            aria-label={center.centerName}
                            onClick={() => setSelectedCenterId(center.centerId as CenterId)}
                          >
                            <span className="team-performance-page__matrix-button-name">{center.centerName}</span>
                            <span className="team-performance-page__matrix-button-meta" aria-hidden="true">
                              查看该部室明细
                            </span>
                          </button>
                        </td>
                        <td className="team-performance-page__table-cell--numeric">{formatScore(center.weightTotal)}</td>
                        <td className="team-performance-page__table-cell--numeric">{formatScore(center.workbookScore)}</td>
                        <td className="team-performance-page__table-cell--numeric">{formatRatePct(center.scoreRate)}</td>
                        <td className="team-performance-page__table-cell--numeric">
                          {formatWanFromYuan(center.mappedPnlTotalYuan)}
                        </td>
                        <td className="team-performance-page__table-cell--numeric">
                          {formatYiFromYuan(center.mappedScaleTotalYuan)}
                        </td>
                        <td>
                          <span
                            className={`team-performance-page__status-pill team-performance-page__status-pill--${mappingStatusTone(center.mappingStatus)}`}
                          >
                            {center.mappingStatus}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <div className="team-performance-page__matrix-cards" aria-label="部室矩阵卡片">
              {viewModel.centers.map((center) => {
                const isActive = center.centerId === selectedCenter.centerId;
                return (
                  <article
                    key={center.centerId}
                    className={
                      isActive
                        ? "team-performance-page__matrix-card team-performance-page__matrix-card--active"
                        : "team-performance-page__matrix-card"
                    }
                  >
                    <button
                      type="button"
                      className="team-performance-page__matrix-card-button"
                      aria-label={center.centerName}
                      onClick={() => setSelectedCenterId(center.centerId as CenterId)}
                    >
                      <div className="team-performance-page__matrix-card-header">
                        <div>
                          <h3 className="team-performance-page__matrix-card-title">{center.centerName}</h3>
                          <p className="team-performance-page__matrix-card-caption">点击查看该部室明细</p>
                        </div>
                        <span
                          className={`team-performance-page__status-pill team-performance-page__status-pill--${mappingStatusTone(center.mappingStatus)}`}
                        >
                          {center.mappingStatus}
                        </span>
                      </div>

                      <dl className="team-performance-page__matrix-card-stats">
                        <div>
                          <dt>权重</dt>
                          <dd>{formatScore(center.weightTotal)}</dd>
                        </div>
                        <div>
                          <dt>工作簿得分</dt>
                          <dd>{formatScore(center.workbookScore)}</dd>
                        </div>
                        <div>
                          <dt>得分率</dt>
                          <dd>{formatRatePct(center.scoreRate)}</dd>
                        </div>
                        <div>
                          <dt>映射损益</dt>
                          <dd>{formatWanFromYuan(center.mappedPnlTotalYuan)}</dd>
                        </div>
                        <div>
                          <dt>映射规模</dt>
                          <dd>{formatYiFromYuan(center.mappedScaleTotalYuan)}</dd>
                        </div>
                      </dl>
                    </button>
                  </article>
                );
              })}
            </div>
          </section>

          <section data-testid="team-performance-detail" className="team-performance-page__panel">
            <SectionLead
              eyebrow="Detail"
              title={`${selectedCenter.centerName} 明细`}
              description="左侧保留 Excel 底稿指标，右侧展示正式接口中的映射分析证据。页面不会重算得分，只显示方案底稿中的分值和完成情况。"
            />

            <div className="team-performance-page__detail-summary-grid">
              <KpiCard
                label="工作簿得分"
                value={selectedCenter.workbookScore.toFixed(2)}
                unit="分"
                detail={`权重 ${selectedCenter.weightTotal} 分`}
                tone={scoreTone(selectedCenter.scoreRate)}
              />
              <KpiCard
                label="映射损益"
                value={formatWanFromYuan(selectedCenter.mappedPnlTotalYuan)}
                detail="API 原值为元，页面统一换算为万元。"
                valueVariant="text"
                tone={mappingStatusTone(selectedCenter.mappingStatus)}
              />
              <KpiCard
                label="映射规模"
                value={formatYiFromYuan(selectedCenter.mappedScaleTotalYuan)}
                detail="规模类字段统一换算为亿元。"
                valueVariant="text"
              />
            </div>

            <div className="team-performance-page__detail-layout">
              <section className="team-performance-page__detail-card">
                <div className="team-performance-page__detail-card-header">
                  <h3>Excel 考核指标</h3>
                  <span className="team-performance-page__detail-card-note">
                    共 {selectedCenter.indicators.length} 项
                  </span>
                </div>

                <div className="team-performance-page__indicator-list">
                  {selectedCenter.indicators.map((indicator) => (
                    <article
                      key={`${indicator.centerId}-${indicator.sourceRow}`}
                      className="team-performance-page__indicator-item"
                    >
                      <div className="team-performance-page__indicator-main">
                        <div className="team-performance-page__indicator-title-row">
                          <div className="team-performance-page__indicator-heading">
                            <h4 className="team-performance-page__metric-name">{indicator.metric}</h4>
                            <div className="team-performance-page__indicator-context">
                              <span className="team-performance-page__indicator-chip">
                                底稿行 {indicator.sourceRow}
                              </span>
                              {indicator.blockLabel ? (
                                <span className="team-performance-page__indicator-chip team-performance-page__indicator-chip--muted">
                                  {indicator.blockLabel}
                                </span>
                              ) : null}
                            </div>
                          </div>
                          <div className="team-performance-page__indicator-tags">
                            <span className="team-performance-page__indicator-tag">
                              {indicator.indicatorCategory}
                            </span>
                          </div>
                        </div>
                        <div className="team-performance-page__indicator-target-panel">
                          <div className="team-performance-page__indicator-target-label">目标 / 说明</div>
                          <div className="team-performance-page__metric-target">{indicator.target}</div>
                        </div>
                      </div>

                      <dl className="team-performance-page__indicator-stats">
                        <div>
                          <dt>分值</dt>
                          <dd>{formatScore(indicator.weight)}</dd>
                        </div>
                        <div>
                          <dt>得分</dt>
                          <dd>{formatScore(indicator.score)}</dd>
                        </div>
                        <div>
                          <dt>完成情况</dt>
                          <dd>{indicator.actual}</dd>
                        </div>
                        <div>
                          <dt>进度</dt>
                          <dd>{indicator.progress}</dd>
                        </div>
                      </dl>
                    </article>
                  ))}
                </div>
              </section>

              <section className="team-performance-page__detail-card">
                <div className="team-performance-page__detail-card-header">
                  <h3>映射分析证据</h3>
                  <span className="team-performance-page__detail-card-note">{selectedCenter.mappingStatus}</span>
                </div>
                <p className="team-performance-page__detail-copy">
                  “映射分析”仅用于把部室方案与现有系统正式 YTD 损益证据并排对照，不代表正式中心归因。
                </p>

                <section className="team-performance-page__evidence-summary">
                  <div className="team-performance-page__evidence-summary-header">
                    <div>
                      <div className="team-performance-page__evidence-summary-label">结论摘要</div>
                      <h4 className="team-performance-page__evidence-summary-title">
                        {selectedCenter.mappingStatus === "已映射"
                          ? "当前部室已有较完整的正式映射证据"
                          : selectedCenter.mappingStatus === "挂钩引用"
                            ? "当前部室展示的是挂钩引用证据"
                            : selectedCenter.mappingStatus === "部分映射"
                              ? "当前部室仅完成部分映射"
                              : "当前部室暂未形成正式映射证据"}
                      </h4>
                    </div>
                    <span
                      className={`team-performance-page__status-pill team-performance-page__status-pill--${mappingStatusTone(selectedCenter.mappingStatus)}`}
                    >
                      {selectedCenter.mappingStatus}
                    </span>
                  </div>

                  <dl className="team-performance-page__evidence-summary-stats">
                    <div>
                      <dt>已命中证据</dt>
                      <dd>{selectedCenter.evidenceRows.length} 条</dd>
                    </div>
                    <div>
                      <dt>待补确认</dt>
                      <dd>{selectedCenter.coverageWarnings.length} 项</dd>
                    </div>
                  </dl>
                </section>

                <section className="team-performance-page__evidence-group">
                  <div className="team-performance-page__evidence-group-header">
                    <h4>已命中正式证据</h4>
                    <span className="team-performance-page__detail-card-note">
                      共 {selectedCenter.evidenceRows.length} 条
                    </span>
                  </div>

                  <div className="team-performance-page__evidence-list">
                    {selectedCenter.evidenceRows.length === 0 ? (
                      <div className="team-performance-page__evidence-empty">
                        当前部室暂无正式接口映射证据，仅保留 Excel 底稿分值。
                      </div>
                    ) : (
                      selectedCenter.evidenceRows.map((row) => (
                        <article
                          key={`${row.endpoint}-${row.rowId}`}
                          className="team-performance-page__evidence-item"
                        >
                          <div className="team-performance-page__evidence-header">
                            <div>
                              <div className="team-performance-page__evidence-title">{row.sourceLabel}</div>
                              <div className="team-performance-page__metric-meta">{evidenceHeadline(row.endpoint)}</div>
                            </div>
                            <div className="team-performance-page__evidence-badges">
                              <span className="team-performance-page__indicator-tag">
                                置信度 {formatConfidenceLabel(row.confidence)}
                              </span>
                            </div>
                          </div>

                          <div className="team-performance-page__evidence-row-name">
                            <code>{row.rowId}</code>
                            <span>{row.rowName}</span>
                          </div>

                          <dl className="team-performance-page__evidence-stats">
                            <div>
                              <dt>金额</dt>
                              <dd>{formatWanFromYuan(row.amountYuan)}</dd>
                            </div>
                            <div>
                              <dt>规模</dt>
                              <dd>{formatYiFromYuan(row.scaleYuan)}</dd>
                            </div>
                          </dl>

                          <div className="team-performance-page__evidence-note">
                            {row.note ?? row.unitLabel}
                          </div>
                        </article>
                      ))
                    )}
                  </div>
                </section>

                {selectedCenter.coverageWarnings.length > 0 ? (
                  <section className="team-performance-page__evidence-group team-performance-page__evidence-group--warning">
                    <div className="team-performance-page__evidence-group-header">
                      <h4>待补确认项</h4>
                      <span className="team-performance-page__detail-card-note">
                        共 {selectedCenter.coverageWarnings.length} 项
                      </span>
                    </div>

                    <div className="team-performance-page__coverage-list">
                      {selectedCenter.coverageWarnings.map((warning) => (
                        <div key={warning} className="team-performance-page__coverage-item">
                          {warning}
                        </div>
                      ))}
                    </div>
                  </section>
                ) : null}
              </section>
            </div>
          </section>
        </div>

        {visibleResultMetaSections.length > 0 ? (
          <section data-testid="team-performance-result-meta" className="team-performance-page__meta-shell">
            <div className="team-performance-page__meta-header">
              <div>
                <div className="team-performance-page__meta-eyebrow">Evidence</div>
                <h3 className="team-performance-page__meta-title">结果元信息摘要</h3>
              </div>
              <p className="team-performance-page__meta-copy">
                先看两条正式读链路的质量、降级和更新时间；完整口径、版本和追踪编号收在下方折叠区。
              </p>
            </div>

            <div className="team-performance-page__meta-grid">
              {visibleResultMetaSections.map((section) => (
                <article key={section.key} className="team-performance-page__meta-card">
                  <div className="team-performance-page__meta-card-header">
                    <div>
                      <div className="team-performance-page__meta-card-label">正式证据链路</div>
                      <h4 className="team-performance-page__meta-card-title">{section.title}</h4>
                    </div>
                    <span
                      className={`team-performance-page__meta-pill team-performance-page__meta-pill--${resultMetaTone(section.meta)}`}
                    >
                      {resultMetaSummaryLabel(section.meta)}
                    </span>
                  </div>

                  <dl className="team-performance-page__meta-stats">
                    <div>
                      <dt>结果类型</dt>
                      <dd>{section.meta.result_kind}</dd>
                    </div>
                    <div>
                      <dt>质量</dt>
                      <dd>{formatMetaQuality(section.meta.quality_flag)}</dd>
                    </div>
                    <div>
                      <dt>降级</dt>
                      <dd>{formatMetaFallback(section.meta.fallback_mode)}</dd>
                    </div>
                    <div>
                      <dt>更新时间</dt>
                      <dd>{formatMetaGeneratedAt(section.meta.generated_at)}</dd>
                    </div>
                  </dl>

                  <div className="team-performance-page__meta-trace">
                    追踪编号 <code>{section.meta.trace_id}</code>
                  </div>
                </article>
              ))}
            </div>

            <details className="team-performance-page__meta-details">
              <summary>展开完整结果元信息与溯源字段</summary>
              <div className="team-performance-page__meta-details-body">
                <FormalResultMetaPanel sections={resultMetaSections} title="完整结果元信息 / 溯源字段" />
              </div>
            </details>
          </section>
        ) : null}
      </AsyncSection>
    </section>
  );
}
