import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";

import type {
  BalanceAnalysisDecisionItemsPayload,
  BalanceAnalysisEventCalendarRow,
  BalanceAnalysisOverviewPayload,
  BalanceAnalysisPayload,
  BalanceAnalysisRiskAlertRow,
  BalanceAnalysisSummaryTablePayload,
  BalanceAnalysisTableRow,
  BalanceAnalysisWorkbookPayload,
  ResultMeta,
} from "../../../api/contracts";
import { primaryWorkbenchNavigationGroups } from "../../../mocks/navigation";
import { KpiCard } from "../../../components/KpiCard";
import {
  formatBalanceAmountToYiFromWan,
  formatBalanceAmountToYiFromYuan,
  formatBalanceDecisionWorkflowStatusDisplay,
  formatBalanceGovernedSeverityDisplay,
  formatBalanceWorkbookOperationalSectionKeyDisplay,
  formatBalanceWorkbookWanTextDisplay,
} from "../pages/balanceAnalysisPageModel";
import "./balanceWorkbench.css";

export type BalanceWorkbenchMetric = {
  key: string;
  label: string;
  value: string;
  unit?: string;
  detail?: string;
};

export type BalanceWorkbenchKpiBar = {
  key: string;
  label: string;
  value: string;
  detail: string;
  percent: number;
};

type BalanceWorkbenchCard = {
  key: string;
  title: string;
  span: 4 | 6 | 8 | 12;
  body: ReactNode;
};

type BalanceAnalysisWorkbenchLayoutProps = {
  overview: BalanceAnalysisOverviewPayload | undefined;
  summary: BalanceAnalysisSummaryTablePayload | undefined;
  workbook: BalanceAnalysisWorkbookPayload | undefined;
  detail: BalanceAnalysisPayload | undefined;
  formalStatus: ResultMeta | undefined;
  decisionItems: BalanceAnalysisDecisionItemsPayload | undefined;
  riskAlerts: BalanceAnalysisRiskAlertRow[];
  calendarEvents: BalanceAnalysisEventCalendarRow[];
  tableRows: BalanceAnalysisTableRow[];
  metrics: BalanceWorkbenchMetric[];
  kpiBars: BalanceWorkbenchKpiBar[];
  compactFilters: ReactNode;
};

const portfolioNavigationItems =
  primaryWorkbenchNavigationGroups
    .find((group) => group.key === "portfolio")
    ?.sections.filter((section) => section.key !== "balance-analysis") ?? [];

function formatMetricDefinitionDisplayUnit(displayUnit: string | undefined): string {
  if (displayUnit === "yi_yuan") {
    return "亿元";
  }
  return "—";
}

function formatFormalStatus(meta: ResultMeta | undefined) {
  if (!meta) {
    return "result_meta 未返回";
  }
  return [
    meta.basis,
    meta.formal_use_allowed ? "formal_use_allowed=true" : "formal_use_allowed=false",
    meta.quality_flag,
    meta.fallback_mode,
  ].join(" / ");
}

function formatQualityFlag(meta: ResultMeta | undefined): string {
  if (!meta?.quality_flag) {
    return "—";
  }
  if (meta.quality_flag === "ok") {
    return "正常";
  }
  if (meta.quality_flag === "warning") {
    return "预警";
  }
  if (meta.quality_flag === "error") {
    return "错误";
  }
  if (meta.quality_flag === "stale") {
    return "陈旧";
  }
  return meta.quality_flag;
}

function formatFallbackMode(meta: ResultMeta | undefined): string {
  if (!meta?.fallback_mode) {
    return "—";
  }
  if (meta.fallback_mode === "none") {
    return "未降级";
  }
  if (meta.fallback_mode === "latest_snapshot") {
    return "最新快照降级";
  }
  return meta.fallback_mode;
}

function formatFormalAllowed(meta: ResultMeta | undefined): string {
  if (!meta) {
    return "—";
  }
  return meta.formal_use_allowed ? "是" : "否";
}

function clampPercent(value: number) {
  if (!Number.isFinite(value)) {
    return 0;
  }
  return Math.max(0, Math.min(100, value));
}

function renderEmpty(label: string) {
  return <div className="balance-workbench-card__empty">{label}</div>;
}

function firstRows<T>(rows: readonly T[], count = 4): T[] {
  return rows.slice(0, count);
}

function buildCards({
  overview,
  summary,
  workbook,
  detail,
  formalStatus,
  decisionItems,
  riskAlerts,
  calendarEvents,
  tableRows,
}: Pick<
  BalanceAnalysisWorkbenchLayoutProps,
  | "overview"
  | "summary"
  | "workbook"
  | "detail"
  | "formalStatus"
  | "decisionItems"
  | "riskAlerts"
  | "calendarEvents"
  | "tableRows"
>): BalanceWorkbenchCard[] {
  const workbookTables = workbook?.tables ?? [];
  const workbookCards = workbook?.cards ?? [];
  const decisionRows = decisionItems?.rows ?? [];

  return [
    {
      key: "structure",
      title: "资产负债结构",
      span: 8,
      body:
        workbookTables.length > 0 ? (
          <ul className="balance-workbench-card__list">
            {firstRows(workbookTables, 4).map((table) => (
              <li key={table.key} className="balance-workbench-card__item">
                <strong>{table.title}</strong>
                <span className="balance-workbench-card__item-meta">
                  {table.rows.length} 行 / {table.columns.length} 列 / workbook
                </span>
              </li>
            ))}
          </ul>
        ) : (
          renderEmpty("当前筛选未返回工作簿结构表。")
        ),
    },
    {
      key: "attribution",
      title: "损益归因",
      span: 4,
      body: (
        <ul className="balance-workbench-card__list">
          {workbookCards.length > 0
            ? firstRows(workbookCards, 3).map((card) => (
                <li key={card.key} className="balance-workbench-card__item">
                  <strong>
                    {card.label} {formatBalanceAmountToYiFromWan(card.value)} 亿元
                  </strong>
                  <span className="balance-workbench-card__item-meta">
                    {formatBalanceWorkbookWanTextDisplay(card.note ?? "工作簿摘要")}
                  </span>
                </li>
              ))
            : [
                <li key="no-workbook-card" className="balance-workbench-card__item">
                  <strong>暂无工作簿摘要卡</strong>
                  <span className="balance-workbench-card__item-meta">不在前端补造归因值。</span>
                </li>,
              ]}
        </ul>
      ),
    },
    {
      key: "governance",
      title: "治理与行动信号",
      span: 4,
      body:
        decisionRows.length > 0 ? (
          <ul className="balance-workbench-card__list">
            {firstRows(decisionRows, 3).map((row) => (
              <li key={row.decision_key} className="balance-workbench-card__item">
                <strong>{row.title}</strong>
                <span className="balance-workbench-card__item-meta">
                  {formatBalanceGovernedSeverityDisplay(row.severity)} /{" "}
                  {row.latest_status?.status != null
                    ? formatBalanceDecisionWorkflowStatusDisplay(row.latest_status.status)
                    : "未返回状态"}{" "}
                  / {formatBalanceWorkbookOperationalSectionKeyDisplay(row.source_section)}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          renderEmpty("当前报告日没有返回决策事项。")
        ),
    },
    {
      key: "basis",
      title: "口径与币种分布",
      span: 4,
      body: (
        <ul className="balance-workbench-card__list">
          <li className="balance-workbench-card__item">
            <strong>{overview?.currency_basis ?? "—"}</strong>
            <span className="balance-workbench-card__item-meta">
              {overview?.position_scope ?? "—"} / {formatFormalStatus(formalStatus)}
            </span>
          </li>
          <li className="balance-workbench-card__item">
            <strong>{summary?.total_rows ?? 0} 汇总行</strong>
            <span className="balance-workbench-card__item-meta">summary table / 当前分页 {summary?.rows.length ?? 0} 行</span>
          </li>
        </ul>
      ),
    },
    {
      key: "risk",
      title: "风险监控",
      span: 4,
      body:
        riskAlerts.length > 0 ? (
          <ul className="balance-workbench-card__list">
            {firstRows(riskAlerts, 3).map((row) => (
              <li key={`${row.rule_id}:${row.title}`} className="balance-workbench-card__item">
                <strong>{row.title}</strong>
                <span className="balance-workbench-card__item-meta">
                  {row.severity} / {formatBalanceWorkbookWanTextDisplay(row.reason)}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          renderEmpty("当前 workbook 未返回风险预警。")
        ),
    },
    {
      key: "focus",
      title: "今日关注 / 交易要点",
      span: 4,
      body:
        calendarEvents.length > 0 ? (
          <ul className="balance-workbench-card__list">
            {firstRows(calendarEvents, 3).map((row) => (
              <li key={`${row.event_date}:${row.title}`} className="balance-workbench-card__item">
                <strong>{row.title}</strong>
                <span className="balance-workbench-card__item-meta">
                  {row.event_date} / {row.event_type} / {row.impact_hint}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          renderEmpty("当前 workbook 未返回今日事件。")
        ),
    },
    {
      key: "details",
      title: "正式数据明细",
      span: 12,
      body:
        tableRows.length > 0 ? (
          <div className="balance-workbench-card__mini-table">
            <div className="balance-workbench-card__mini-row balance-workbench-card__mini-row--head">
              <span>展示名</span>
              <span>市值(亿元)</span>
              <span>摊余成本(亿元)</span>
              <span>应计利息(亿元)</span>
            </div>
            {firstRows(tableRows, 5).map((row) => (
              <div key={row.row_key} className="balance-workbench-card__mini-row">
                <span>{row.display_name}</span>
                <span>{formatBalanceAmountToYiFromYuan(row.market_value_amount)}</span>
                <span>{formatBalanceAmountToYiFromYuan(row.amortized_cost_amount)}</span>
                <span>{formatBalanceAmountToYiFromYuan(row.accrued_interest_amount)}</span>
              </div>
            ))}
            <div className="balance-workbench-card__subtle">
              明细接口 summary {detail?.summary.length ?? 0} 组，details {detail?.details.length ?? 0} 行。
            </div>
          </div>
        ) : (
          renderEmpty("正式汇总分页尚未返回可展示行。")
        ),
    },
  ];
}

export default function BalanceAnalysisWorkbenchLayout({
  overview,
  summary,
  workbook,
  detail,
  formalStatus,
  decisionItems,
  riskAlerts,
  calendarEvents,
  tableRows,
  metrics,
  kpiBars,
  compactFilters,
}: BalanceAnalysisWorkbenchLayoutProps) {
  const cards = buildCards({
    overview,
    summary,
    workbook,
    detail,
    formalStatus,
    decisionItems,
    riskAlerts,
    calendarEvents,
    tableRows,
  });
  const topDecision = decisionItems?.rows[0];
  const topRisk = riskAlerts[0];
  const topEvent = calendarEvents[0];
  const metricDefinitions = overview?.metric_definitions ?? [];
  const firstMetricDefinition = metricDefinitions[0];

  return (
    <div className="balance-workbench" data-testid="balance-workbench">
      <section
        data-testid="balance-analysis-command-deck"
        className="balance-workbench__command-deck"
      >
        <section data-testid="balance-analysis-priority-board" className="balance-workbench__judgement">
          <div data-testid="balance-analysis-daily-judgement">
            <span className="balance-workbench__eyebrow">正式口径</span>
            <h2 className="balance-workbench__judgement-title">正式状态判断</h2>
            <p className="balance-workbench__judgement-lede">
              当前页先确认正式口径下的规模、质量和治理信号，再进入汇总表与工作簿下钻。
            </p>
            <p className="balance-workbench__judgement-copy">
              {[
                topRisk ? `风险: ${topRisk.title} / ${topRisk.severity}` : null,
                topDecision
                  ? `决策: ${topDecision.title} / ${topDecision.latest_status?.status ?? "未返回状态"}`
                  : null,
                topEvent ? `事件: ${topEvent.title} / ${topEvent.event_date}` : null,
              ]
                .filter(Boolean)
                .join("。") || "当前报告日未返回治理异常信号。"}
            </p>
          </div>
        </section>

        <aside
          aria-labelledby="balance-analysis-status-rail-title"
          data-testid="balance-analysis-status-rail"
          className="balance-workbench__status-rail"
        >
          <div className="balance-workbench__status-head">
            <span className="balance-workbench__eyebrow">链路 / 治理状态</span>
            <strong id="balance-analysis-status-rail-title">
              {formalStatus?.result_kind ?? "result_meta 未返回"}
            </strong>
          </div>
          <dl className="balance-workbench__status-pills">
            <div className="balance-workbench__status-pill">
              <dt>口径</dt>
              <dd>{formalStatus?.basis ?? "—"}</dd>
            </div>
            <div className="balance-workbench__status-pill">
              <dt>正式可用</dt>
              <dd>{formatFormalAllowed(formalStatus)}</dd>
            </div>
            <div className="balance-workbench__status-pill">
              <dt>质量</dt>
              <dd>{formatQualityFlag(formalStatus)}</dd>
            </div>
            <div className="balance-workbench__status-pill">
              <dt>降级</dt>
              <dd>{formatFallbackMode(formalStatus)}</dd>
            </div>
          </dl>
          <div className="balance-workbench__status-grid">
            <div className="balance-workbench__status-metric">
              <span>正式汇总查询</span>
              <strong>{String(overview?.summary_row_count ?? "—")}</strong>
              <small>汇总行</small>
            </div>
            <div className="balance-workbench__status-metric">
              <span>正式明细查询</span>
              <strong>{String(overview?.detail_row_count ?? "—")}</strong>
              <small>明细行</small>
            </div>
            <div className="balance-workbench__status-metric">
              <span>工作簿摘要卡</span>
              <strong>{String(workbook?.cards.length ?? 0)}</strong>
              <small>摘要卡</small>
            </div>
            <div className="balance-workbench__status-metric">
              <span>指标定义</span>
              <strong>{metricDefinitions.length} 项</strong>
              <small>
                {formatMetricDefinitionDisplayUnit(firstMetricDefinition?.display_unit)} /{" "}
                {firstMetricDefinition?.description ?? "—"}
              </small>
            </div>
          </div>
          <div className="balance-workbench__status-meta">
            <span>{formatFormalStatus(formalStatus)}</span>
            <span>trace_id: {formalStatus?.trace_id ?? "—"}</span>
          </div>
          <div className="balance-workbench__filter-note">{compactFilters}</div>
        </aside>
      </section>

      <div data-testid="balance-analysis-overview-cards" className="balance-workbench__metrics">
        {metrics.map((metric) => (
          <div
            key={metric.key}
            data-testid="balance-analysis-horizontal-metric"
            className="balance-workbench__metric"
          >
            <KpiCard
              label={metric.label}
              value={metric.value}
              unit={metric.unit}
              detail={metric.detail}
              valueVariant="text"
            />
          </div>
        ))}
      </div>

      {kpiBars.length > 0 ? (
        <div className="balance-workbench__kpis">
          {kpiBars.map((bar) => (
            <div key={bar.key} data-testid="balance-analysis-kpi-bar" className="balance-workbench__kpi">
              <div className="balance-workbench__kpi-head">
                <span className="balance-workbench__kpi-label">{bar.label}</span>
                <span className="balance-workbench__kpi-value">{bar.value}</span>
              </div>
              <div className="balance-workbench__kpi-track" aria-hidden>
                <div
                  className="balance-workbench__kpi-fill"
                  style={{ width: `${clampPercent(bar.percent)}%` }}
                />
              </div>
              <div className="balance-workbench__kpi-detail">{bar.detail}</div>
            </div>
          ))}
        </div>
      ) : null}

      <section data-testid="balance-analysis-workbench-grid" className="balance-workbench__grid">
        {cards.map((card) => (
          <article
            key={card.key}
            className={`balance-workbench-card balance-workbench-card--span-${card.span}`}
            data-testid={`balance-analysis-workbench-card-${card.key}`}
          >
            <h2 className="balance-workbench-card__heading">{card.title}</h2>
            {card.body}
          </article>
        ))}
      </section>

      <nav
        data-testid="balance-analysis-portfolio-nav"
        className="balance-workbench__portfolio-nav"
        aria-label="组合工作台导航"
      >
        <strong className="balance-workbench__portfolio-nav-title">组合工作台导航</strong>
        <div className="balance-workbench__portfolio-nav-links">
          {portfolioNavigationItems.map((section) => (
            <NavLink
              key={section.key}
              to={section.path}
              className={({ isActive }) =>
                [
                  "balance-workbench__portfolio-nav-link",
                  isActive ? "balance-workbench__portfolio-nav-link--active" : "",
                ]
                  .filter(Boolean)
                  .join(" ")
              }
            >
              {section.label}
            </NavLink>
          ))}
        </div>
      </nav>
    </div>
  );
}
