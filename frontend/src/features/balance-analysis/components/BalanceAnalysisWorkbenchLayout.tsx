import type { ReactNode } from "react";
import {
  AuditOutlined,
  BankOutlined,
  BarChartOutlined,
  BranchesOutlined,
  CalendarOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  ClusterOutlined,
  ControlOutlined,
  DatabaseOutlined,
  DeploymentUnitOutlined,
  ExceptionOutlined,
  FileSearchOutlined,
  FundProjectionScreenOutlined,
  LineChartOutlined,
  PartitionOutlined,
  ProfileOutlined,
  SafetyCertificateOutlined,
  TableOutlined,
  WarningOutlined,
} from "@ant-design/icons";
import { NavLink } from "react-router-dom";

import type {
  BalanceAnalysisCurrentUserPayload,
  BalanceAnalysisDecisionItemStatusRow,
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
import {
  formatBalanceAmountToYiFromWan,
  formatBalanceAmountToYiFromYuan,
  formatBalanceBusinessTextDisplay,
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

export type BalanceEndpointStatus = "ready" | "loading" | "deferred" | "idle" | "error";

export type BalanceEndpointChip = {
  key: string;
  label: string;
  path: string;
  status: BalanceEndpointStatus;
  value?: string;
  detail: string;
};

export type BalanceEndpointGroup = {
  key: string;
  title: string;
  description: string;
  count: number;
  tone: "primary" | "info" | "action";
  endpoints: BalanceEndpointChip[];
};

export type BalanceDeferredSurface = {
  key: string;
  title: string;
  endpoint: string;
  status: BalanceEndpointStatus;
  value: string;
  detail: string;
};

export type BalanceStateSentinel = {
  key: string;
  label: string;
  status: BalanceEndpointStatus;
  active: boolean;
  detail: string;
};

type BalanceMetricComparison = {
  key: string;
  title: string;
  asset: BalanceWorkbenchMetric;
  liability: BalanceWorkbenchMetric;
  assetWidth: string;
  liabilityWidth: string;
};

type BalanceHomepageKpi = {
  key: string;
  label: string;
  value: string;
  unit: string;
  source: string;
};

type BalanceWorkbenchCard = {
  key: string;
  title: string;
  icon: ReactNode;
  tone: "asset" | "liability" | "risk" | "evidence" | "action";
  span: 4 | 6 | 8 | 12;
  body: ReactNode;
};

type BalanceAnalysisWorkbenchLayoutProps = {
  overview: BalanceAnalysisOverviewPayload | undefined;
  summary: BalanceAnalysisSummaryTablePayload | undefined;
  workbook: BalanceAnalysisWorkbookPayload | undefined;
  detail: BalanceAnalysisPayload | undefined;
  formalStatus: ResultMeta | undefined;
  currentUser: BalanceAnalysisCurrentUserPayload | undefined;
  decisionRows: BalanceAnalysisDecisionItemStatusRow[];
  riskAlerts: BalanceAnalysisRiskAlertRow[];
  calendarEvents: BalanceAnalysisEventCalendarRow[];
  tableRows: BalanceAnalysisTableRow[];
  metrics: BalanceWorkbenchMetric[];
  kpiBars: BalanceWorkbenchKpiBar[];
  endpointGroups: BalanceEndpointGroup[];
  deferredSurfaces: BalanceDeferredSurface[];
  stateSentinels: BalanceStateSentinel[];
  compactFilters: ReactNode;
};

const portfolioNavigationItems =
  primaryWorkbenchNavigationGroups
    .find((group) => group.key === "portfolio")
    ?.sections.filter((section) => section.key !== "balance-analysis") ?? [];

const endpointStatusLabels: Record<BalanceEndpointStatus, string> = {
  ready: "正常",
  loading: "加载",
  deferred: "延迟",
  idle: "待触发",
  error: "需关注",
};

function formatEndpointStatus(status: BalanceEndpointStatus): string {
  return endpointStatusLabels[status];
}

function renderEndpointStatusIcon(status: BalanceEndpointStatus) {
  if (status === "ready") {
    return <CheckCircleOutlined />;
  }
  if (status === "error") {
    return <WarningOutlined />;
  }
  if (status === "deferred") {
    return <BranchesOutlined />;
  }
  return <ClockCircleOutlined />;
}

function renderEndpointChip(endpoint: BalanceEndpointChip) {
  const shouldShowStatus = endpoint.status === "error";
  return (
    <span
      key={endpoint.key}
      className="balance-workbench__endpoint-chip"
      data-status={endpoint.status}
      data-testid={`balance-analysis-endpoint-chip-${endpoint.key}`}
      title={`${endpoint.label}：${endpoint.detail}`}
      data-endpoint-path={endpoint.path}
      aria-label={`${endpoint.label}，${endpoint.detail}，返回摘要 ${endpoint.value ?? "未返回"}`}
    >
      <span className="balance-workbench__endpoint-state-icon" aria-hidden>
        {renderEndpointStatusIcon(endpoint.status)}
      </span>
      <span className="balance-workbench__endpoint-copy">
        <b>{endpoint.label}</b>
        <small className="balance-workbench__endpoint-detail">{endpoint.detail}</small>
      </span>
      {shouldShowStatus ? (
        <em className="balance-workbench__endpoint-status">
          {formatEndpointStatus(endpoint.status)}
        </em>
      ) : null}
      <small className="balance-workbench__endpoint-value">{endpoint.value ?? "—"}</small>
    </span>
  );
}

function formatEndpointGroupStatusSummary(group: BalanceEndpointGroup): string {
  const errorCount = group.endpoints.filter((endpoint) => endpoint.status === "error").length;
  if (errorCount > 0) {
    return `${group.description} · ${errorCount} 项需关注`;
  }
  return group.description;
}

function formatFormalStatus(meta: ResultMeta | undefined) {
  if (!meta) {
    return "读面未返回";
  }
  return [
    meta.basis === "formal" ? "正式口径" : meta.basis,
    meta.formal_use_allowed ? "可用于判断" : "待确认",
    formatQualityFlag(meta),
    formatFallbackMode(meta),
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

function parseMetricDisplayNumber(value: string): number | null {
  const n = Number(value.replace(/,/g, "").trim());
  return Number.isFinite(n) ? Math.abs(n) : null;
}

function comparisonWidth(value: number | null, scale: number): string {
  if (value === null || value <= 0 || scale <= 0) {
    return "0%";
  }
  return `${Math.max(8, Math.min(100, (value / scale) * 100))}%`;
}

function metricValueDisplay(value: string): string {
  return value === "—" ? "待返回" : value;
}

function metricDisplay(metric: BalanceWorkbenchMetric): string {
  const value = metricValueDisplay(metric.value);
  return metric.unit && metric.value !== "—" ? `${value} ${metric.unit}` : value;
}

function renderDeferredVisual(surface: BalanceDeferredSurface) {
  if (surface.key === "detail-ledger") {
    return (
      <div className="balance-workbench__deferred-visual balance-workbench__deferred-visual--pill" aria-hidden>
        底稿
      </div>
    );
  }
  if (surface.key === "basis-breakdown") {
    return (
      <div className="balance-workbench__deferred-visual balance-workbench__deferred-visual--segments" aria-hidden>
        <i />
        <i />
        <i />
      </div>
    );
  }
  if (surface.key === "adb-comparison") {
    return (
      <div className="balance-workbench__deferred-visual balance-workbench__deferred-visual--line" aria-hidden>
        <i />
      </div>
    );
  }
  if (surface.key === "movement-link") {
    return (
      <div className="balance-workbench__deferred-visual balance-workbench__deferred-visual--bars" aria-hidden>
        <i />
        <i />
        <i />
        <i />
        <i />
      </div>
    );
  }
  if (surface.key === "advanced-attribution") {
    return (
      <div className="balance-workbench__deferred-visual balance-workbench__deferred-visual--pill" aria-hidden>
        归因
      </div>
    );
  }
  return (
    <div className="balance-workbench__deferred-visual balance-workbench__deferred-visual--count" aria-hidden>
      {surface.value}
    </div>
  );
}

function formatOverviewAmount(value: number | string | null | undefined): string {
  return formatBalanceAmountToYiFromYuan(value);
}

function formatHomepageScope(value: string | undefined) {
  if (value === "all") return "全部";
  if (value === "asset") return "资产";
  if (value === "liability") return "负债";
  return value;
}

function formatHomepageCurrency(value: string | undefined) {
  if (value === "CNY") return "人民币";
  if (value === "native") return "原币";
  return value;
}

function workbookCardDisplay(card: BalanceAnalysisWorkbookPayload["cards"][number] | undefined): string {
  return card ? `${formatBalanceAmountToYiFromWan(card.value)} 亿元` : "—";
}

function findWorkbookCardByKey(workbook: BalanceAnalysisWorkbookPayload | undefined, key: string) {
  return workbook?.cards.find((card) => card.key === key);
}

function findMetricByKey(metrics: readonly BalanceWorkbenchMetric[], key: string) {
  return metrics.find((metric) => metric.key === key);
}

function buildMetricComparisons(metrics: readonly BalanceWorkbenchMetric[]): BalanceMetricComparison[] {
  const definitions = [
    {
      key: "market-value",
      title: "市值规模",
      assetKey: "asset-market-value",
      liabilityKey: "liability-market-value",
    },
    {
      key: "amortized-cost",
      title: "摊余成本",
      assetKey: "asset-amortized-cost",
      liabilityKey: "liability-amortized-cost",
    },
    {
      key: "accrued-interest",
      title: "应计利息",
      assetKey: "asset-accrued-interest",
      liabilityKey: "liability-accrued-interest",
    },
  ] as const;

  return definitions.flatMap((definition) => {
    const asset = findMetricByKey(metrics, definition.assetKey);
    const liability = findMetricByKey(metrics, definition.liabilityKey);
    if (!asset || !liability) {
      return [];
    }
    const assetValue = parseMetricDisplayNumber(asset.value);
    const liabilityValue = parseMetricDisplayNumber(liability.value);
    const scale = Math.max(assetValue ?? 0, liabilityValue ?? 0);
    return [
      {
        key: definition.key,
        title: definition.title,
        asset,
        liability,
        assetWidth: comparisonWidth(assetValue, scale),
        liabilityWidth: comparisonWidth(liabilityValue, scale),
      },
    ];
  });
}

function renderEmpty(label: string) {
  return <div className="balance-workbench-card__empty">{label}</div>;
}

function firstRows<T>(rows: readonly T[], count = 4): T[] {
  return rows.slice(0, count);
}

function IconBadge({ tone, icon }: { tone: BalanceWorkbenchCard["tone"]; icon: ReactNode }) {
  return <span className={`balance-workbench__icon-badge balance-workbench__icon-badge--${tone}`}>{icon}</span>;
}

function MetricIcon({ group, label }: { group: "asset" | "liability" | "evidence"; label: string }) {
  if (group === "asset") {
    return label.includes("利息") ? <LineChartOutlined /> : <BankOutlined />;
  }
  if (group === "liability") {
    return label.includes("利息") ? <LineChartOutlined /> : <ProfileOutlined />;
  }
  return label.includes("明细") ? <TableOutlined /> : <DatabaseOutlined />;
}

function buildCards({
  overview,
  summary,
  workbook,
  detail,
  formalStatus,
  decisionRows,
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
  | "decisionRows"
  | "riskAlerts"
  | "calendarEvents"
  | "tableRows"
>): BalanceWorkbenchCard[] {
  const workbookTables = workbook?.tables ?? [];
  const workbookCards = workbook?.cards ?? [];

  const orderedCards: BalanceWorkbenchCard[] = [
    {
      key: "structure",
      title: "资产负债结构",
      icon: <PartitionOutlined />,
      tone: "asset",
      span: 8,
      body:
        workbookTables.length > 0 ? (
          <ul className="balance-workbench-card__list">
            {firstRows(workbookTables, 4).map((table) => (
              <li key={table.key} className="balance-workbench-card__item">
                <strong>{formatBalanceBusinessTextDisplay(table.title)}</strong>
                <span className="balance-workbench-card__item-meta">
                  {table.rows.length} 行 / {table.columns.length} 列 / 工作簿
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
      title: "工作簿规模拆分",
      icon: <BranchesOutlined />,
      tone: "evidence",
      span: 4,
      body: (
        <ul className="balance-workbench-card__list">
          {workbookCards.length > 0
            ? firstRows(workbookCards, 5).map((card) => (
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
      title: "治理行动台",
      icon: <AuditOutlined />,
      tone: "action",
      span: 4,
      body:
        decisionRows.length > 0 ? (
          <ul className="balance-workbench-card__list">
            {firstRows(decisionRows, 3).map((row) => (
              <li key={row.decision_key} className="balance-workbench-card__item">
                <strong>{formatBalanceBusinessTextDisplay(row.title)}</strong>
                <span className="balance-workbench-card__item-meta">
                  {formatBalanceGovernedSeverityDisplay(row.severity)} /{" "}
                  {row.latest_status?.status != null
                    ? formatBalanceDecisionWorkflowStatusDisplay(row.latest_status.status)
                    : "待治理反馈"}{" "}
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
      icon: <ControlOutlined />,
      tone: "evidence",
      span: 4,
      body: (
        <ul className="balance-workbench-card__list">
          <li className="balance-workbench-card__item">
            <strong>{formatHomepageCurrency(overview?.currency_basis) ?? "—"}</strong>
            <span className="balance-workbench-card__item-meta">
              {formatHomepageScope(overview?.position_scope) ?? "—"} / {formatFormalStatus(formalStatus)}
            </span>
          </li>
          <li className="balance-workbench-card__item">
            <strong>{summary?.total_rows ?? 0} 汇总行</strong>
            <span className="balance-workbench-card__item-meta">当前分页 {summary?.rows.length ?? 0} 行</span>
          </li>
        </ul>
      ),
    },
    {
      key: "risk",
      title: "风险监控",
      icon: <WarningOutlined />,
      tone: "risk",
      span: 4,
      body:
        riskAlerts.length > 0 ? (
          <ul className="balance-workbench-card__list">
            {firstRows(riskAlerts, 3).map((row) => (
              <li key={`${row.rule_id}:${row.title}`} className="balance-workbench-card__item">
                <strong>{formatBalanceBusinessTextDisplay(row.title)}</strong>
                <span className="balance-workbench-card__item-meta">
                  {formatBalanceGovernedSeverityDisplay(row.severity)} /{" "}
                  {formatBalanceBusinessTextDisplay(row.reason)}
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
      icon: <CalendarOutlined />,
      tone: "action",
      span: 4,
      body:
        calendarEvents.length > 0 ? (
          <ul className="balance-workbench-card__list">
            {firstRows(calendarEvents, 3).map((row) => (
              <li key={`${row.event_date}:${row.title}`} className="balance-workbench-card__item">
                <strong>{formatBalanceBusinessTextDisplay(row.title)}</strong>
                <span className="balance-workbench-card__item-meta">
                  {row.event_date} / {formatBalanceBusinessTextDisplay(row.event_type)} /{" "}
                  {formatBalanceBusinessTextDisplay(row.impact_hint)}
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
      title: "证据工作区",
      icon: <FileSearchOutlined />,
      tone: "evidence",
      span: 8,
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
              明细汇总 {detail?.summary.length ?? 0} 组，明细行 {detail?.details.length ?? 0} 行。
            </div>
          </div>
        ) : (
          renderEmpty("正式汇总分页尚未返回可展示行。")
        ),
    },
  ];
  const conclusionFirstOrder = [
    "details",
    "governance",
    "risk",
    "focus",
    "structure",
    "attribution",
    "basis",
  ];

  return conclusionFirstOrder.flatMap((key) => {
    const card = orderedCards.find((candidate) => candidate.key === key);
    return card ? [card] : [];
  });
}

function getMetricGroup(metric: BalanceWorkbenchMetric): "asset" | "liability" | "evidence" {
  if (metric.label.startsWith("资产")) {
    return "asset";
  }
  if (metric.label.startsWith("负债")) {
    return "liability";
  }
  return "evidence";
}

const metricGroupLabels = {
  asset: { label: "资产端", icon: <BankOutlined /> },
  liability: { label: "负债端", icon: <ProfileOutlined /> },
  evidence: { label: "证据规模", icon: <DatabaseOutlined /> },
} as const;

export default function BalanceAnalysisWorkbenchLayout({
  overview,
  summary,
  workbook,
  detail,
  formalStatus,
  decisionRows,
  riskAlerts,
  calendarEvents,
  tableRows,
  metrics,
  kpiBars,
  endpointGroups,
  deferredSurfaces,
  stateSentinels,
  compactFilters,
}: BalanceAnalysisWorkbenchLayoutProps) {
  const cards = buildCards({
    overview,
    summary,
    workbook,
    detail,
    formalStatus,
    decisionRows,
    riskAlerts,
    calendarEvents,
    tableRows,
  });
  const topDecision = decisionRows[0];
  const topRisk = riskAlerts[0];
  const topEvent = calendarEvents[0];
  const topDecisionTitle = topDecision ? formatBalanceBusinessTextDisplay(topDecision.title) : null;
  const topRiskTitle = topRisk ? formatBalanceBusinessTextDisplay(topRisk.title) : null;
  const topEventTitle = topEvent ? formatBalanceBusinessTextDisplay(topEvent.title) : null;
  const comparisonPairs = buildMetricComparisons(metrics);
  const assetMarketMetric = findMetricByKey(metrics, "asset-market-value");
  const liabilityMarketMetric = findMetricByKey(metrics, "liability-market-value");
  const netPositionCard = findWorkbookCardByKey(workbook, "net_position");
  const issuanceCard = findWorkbookCardByKey(workbook, "issuance_liabilities");
  const homepageActionTitle = topDecisionTitle ?? topRiskTitle ?? "暂无治理动作";
  const homepageActionMeta = topDecision
    ? `${formatBalanceGovernedSeverityDisplay(topDecision.severity)} / ${
        topDecision.latest_status?.status
          ? formatBalanceDecisionWorkflowStatusDisplay(topDecision.latest_status.status)
          : "待治理反馈"
      }`
    : topRisk
      ? `${formatBalanceGovernedSeverityDisplay(topRisk.severity)} / 风险待核`
      : "暂无治理队列";
  const reportDateFocus = overview?.report_date ?? "等待报告日";
  const scopeFocus =
    [
      formatHomepageScope(overview?.position_scope),
      formatHomepageCurrency(overview?.currency_basis),
    ]
      .filter(Boolean)
      .join(" / ") ||
    "等待筛选结果";
  const rowCoverageFocus = `${String(overview?.summary_row_count ?? "—")} / ${String(
    overview?.detail_row_count ?? "—",
  )}`;
  const governanceQueueFocus = `${decisionRows.length} / ${riskAlerts.length}`;
  const formalStatusWarnings = [
    formalStatus?.basis && formalStatus.basis !== "formal"
      ? { key: "basis", label: "口径", value: formalStatus.basis }
      : null,
    formalStatus && !formalStatus.formal_use_allowed
      ? { key: "allowed", label: "正式可用", value: formatFormalAllowed(formalStatus) }
      : null,
    formalStatus?.quality_flag && formalStatus.quality_flag !== "ok"
      ? { key: "quality", label: "质量", value: formatQualityFlag(formalStatus) }
      : null,
    formalStatus?.fallback_mode && formalStatus.fallback_mode !== "none"
      ? { key: "fallback", label: "降级", value: formatFallbackMode(formalStatus) }
      : null,
  ].filter((item): item is { key: string; label: string; value: string } => item !== null);
  const activeStateSentinels = stateSentinels.filter((sentinel) => sentinel.active);
  const decisionFlowSteps = [
    {
      key: "availability",
      label: "读面",
      detail: formalStatus?.formal_use_allowed ? "正式读面可用" : "等待正式读面",
      active: Boolean(formalStatus?.formal_use_allowed),
    },
    {
      key: "scale",
      label: "规模",
      detail: assetMarketMetric && liabilityMarketMetric ? "资产/负债已对齐" : "等待规模读面",
      active: Boolean(assetMarketMetric || liabilityMarketMetric),
    },
    {
      key: "risk",
      label: "风险",
      detail: topRisk ? formatBalanceGovernedSeverityDisplay(topRisk.severity) : "无风险预警",
      active: Boolean(topRisk),
    },
    {
      key: "action",
      label: "治理动作",
      detail: topDecision?.latest_status?.status
        ? formatBalanceDecisionWorkflowStatusDisplay(topDecision.latest_status.status)
        : "等待治理反馈",
      active: Boolean(topDecision),
    },
  ];
  const totalEndpointCount = endpointGroups.reduce((sum, group) => sum + group.count, 0);
  const endpointStatusCounts = endpointGroups
    .flatMap((group) => group.endpoints)
    .reduce(
      (counts, endpoint) => ({
        ...counts,
        [endpoint.status]: counts[endpoint.status] + 1,
      }),
      {
        ready: 0,
        loading: 0,
        deferred: 0,
        idle: 0,
        error: 0,
      } satisfies Record<BalanceEndpointStatus, number>,
    );
  const endpointSummaryLine =
    endpointStatusCounts.error > 0
      ? `${endpointStatusCounts.error} 项需关注 · ${totalEndpointCount} 个读面`
      : `${totalEndpointCount} 个读面 · 覆盖首屏、补充读面、动作`;
  const endpointMatrixHiddenSummary = endpointGroups
    .map((group) => `${group.title}${group.count}：${group.description}`)
    .join(" / ");
  const homepageKpis: BalanceHomepageKpi[] = [
    {
      key: "total-market-value",
      label: "总市值规模",
      value: formatOverviewAmount(overview?.total_market_value_amount),
      unit: "亿元",
      source: "MTR-BAL-001",
    },
    {
      key: "total-amortized-cost",
      label: "总摊余成本",
      value: formatOverviewAmount(overview?.total_amortized_cost_amount),
      unit: "亿元",
      source: "MTR-BAL-002",
    },
    {
      key: "total-accrued-interest",
      label: "总应计利息",
      value: formatOverviewAmount(overview?.total_accrued_interest_amount),
      unit: "亿元",
      source: "MTR-BAL-003",
    },
    {
      key: "detail-row-count",
      label: "明细行数",
      value: String(overview?.detail_row_count ?? "—"),
      unit: "行",
      source: "MTR-BAL-101",
    },
    {
      key: "summary-row-count",
      label: "汇总行数",
      value: String(overview?.summary_row_count ?? summary?.total_rows ?? "—"),
      unit: "行",
      source: "MTR-BAL-102/103",
    },
    {
      key: "decision-action-count",
      label: "治理动作",
      value: String(decisionRows.length),
      unit: "项",
      source: "治理队列",
    },
  ];
  const metricGroups = (["asset", "liability", "evidence"] as const)
    .map((key) => ({
      key,
      metrics: metrics.filter((metric) => getMetricGroup(metric) === key),
    }))
    .filter((group) => group.metrics.length > 0);

  return (
    <div className="balance-workbench" data-testid="balance-workbench">
      <section
        data-testid="balance-analysis-command-deck"
        className="balance-workbench__command-deck"
      >
        <section data-testid="balance-analysis-priority-board" className="balance-workbench__judgement">
          <div data-testid="balance-analysis-daily-judgement">
            <div className="balance-workbench__terminal-header">
              <IconBadge tone="asset" icon={<FundProjectionScreenOutlined />} />
              <div>
                <span className="balance-workbench__eyebrow">缺口判断台</span>
                <h2 className="balance-workbench__judgement-title">资产负债缺口判断</h2>
                <p className="balance-workbench__judgement-lede">
                  {topRiskTitle ? `${topRiskTitle}需复核` : "净头寸、期限缺口与治理动作可读"}
                </p>
              </div>
            </div>
            <div className="balance-workbench__decision-flow" aria-label="首页判断流程">
              {decisionFlowSteps.map((step, index) => (
                <div
                  key={step.key}
                  className="balance-workbench__decision-step"
                  data-active={step.active ? "true" : "false"}
                >
                  <span>{index + 1}</span>
                  <strong>{step.label}</strong>
                  <small>{step.detail}</small>
                </div>
              ))}
            </div>
            <p className="balance-workbench__judgement-copy">
              {[
                topRisk
                  ? `风险: ${topRiskTitle} / ${formatBalanceGovernedSeverityDisplay(topRisk.severity)}`
                  : null,
                topDecision
                  ? `决策: ${topDecisionTitle} / ${
                      topDecision.latest_status?.status
                        ? formatBalanceDecisionWorkflowStatusDisplay(topDecision.latest_status.status)
                        : "待治理反馈"
                    }`
                  : null,
                topEvent ? `事件: ${topEventTitle} / ${topEvent.event_date}` : null,
              ]
                .filter(Boolean)
                .join("。") || "当前报告日未返回治理风险信号。"}
            </p>
            <div className="balance-workbench__terminal-tape" data-testid="balance-analysis-terminal-tape">
              <div className="balance-workbench__tape-item balance-workbench__tape-item--asset">
                <BankOutlined aria-hidden />
                <span>资产市值</span>
                <strong>{assetMarketMetric ? metricDisplay(assetMarketMetric) : "—"}</strong>
              </div>
              <div className="balance-workbench__tape-item balance-workbench__tape-item--liability">
                <ProfileOutlined aria-hidden />
                <span>负债市值</span>
                <strong>{liabilityMarketMetric ? metricDisplay(liabilityMarketMetric) : "—"}</strong>
              </div>
              <div className="balance-workbench__tape-item balance-workbench__tape-item--action">
                <DeploymentUnitOutlined aria-hidden />
                <span>净头寸</span>
                <strong>{workbookCardDisplay(netPositionCard)}</strong>
              </div>
              <div className="balance-workbench__tape-item balance-workbench__tape-item--risk">
                <ExceptionOutlined aria-hidden />
                <span>发行类负债</span>
                <strong>{workbookCardDisplay(issuanceCard)}</strong>
              </div>
            </div>
            <div data-testid="balance-analysis-signal-strip" className="balance-workbench__signal-strip">
              <div className="balance-workbench__signal">
                <IconBadge tone="risk" icon={<WarningOutlined />} />
                <span>最高风险</span>
                <strong>{topRiskTitle ?? "未返回风险预警"}</strong>
                <small>{topRisk ? formatBalanceGovernedSeverityDisplay(topRisk.severity) : "未返回预警"}</small>
              </div>
              <div className="balance-workbench__signal">
                <IconBadge tone="action" icon={<AuditOutlined />} />
                <span>待办决策</span>
                <strong>{topDecisionTitle ?? "未返回决策事项"}</strong>
                <small>
                  {topDecision?.latest_status?.status
                    ? formatBalanceDecisionWorkflowStatusDisplay(topDecision.latest_status.status)
                    : "未返回决策"}
                </small>
              </div>
              <div className="balance-workbench__signal">
                <IconBadge tone="evidence" icon={<ClockCircleOutlined />} />
                <span>最近事件</span>
                <strong>{topEventTitle ?? "未返回事件日历"}</strong>
                <small>{topEvent?.event_date ?? "未返回事件"}</small>
              </div>
            </div>
          </div>
        </section>

        <aside
          aria-labelledby="balance-analysis-status-rail-title"
          data-testid="balance-analysis-status-rail"
          className="balance-workbench__status-rail"
        >
          <div className="balance-workbench__status-head">
            <span className="balance-workbench__eyebrow">首页组合 / 行动摘要</span>
            <strong id="balance-analysis-status-rail-title">
              <SafetyCertificateOutlined aria-hidden />{" "}
              首页行动摘要
            </strong>
            <small>只保留会影响判断和处置的信息，常规校验收进证据链路。</small>
          </div>
          {formalStatusWarnings.length > 0 ? (
            <div className="balance-workbench__status-badges">
              {formalStatusWarnings.map((warning) => (
                <span key={warning.key}>
                  <b>{warning.label}</b>
                  {warning.value}
                </span>
              ))}
            </div>
          ) : null}
          <div className="balance-workbench__status-list balance-workbench__status-grid balance-workbench__status-grid--homepage">
            <div className="balance-workbench__status-metric">
              <CalendarOutlined aria-hidden className="balance-workbench__status-icon" />
              <span>报告日 / 口径</span>
              <strong>{reportDateFocus}</strong>
              <small>{scopeFocus}</small>
            </div>
            <div className="balance-workbench__status-metric">
              <TableOutlined aria-hidden className="balance-workbench__status-icon" />
              <span>有效读面</span>
              <strong>{rowCoverageFocus}</strong>
              <small>汇总行 / 明细行</small>
            </div>
            <div className="balance-workbench__status-metric">
              <AuditOutlined aria-hidden className="balance-workbench__status-icon" />
              <span>治理队列</span>
              <strong>{governanceQueueFocus}</strong>
              <small>决策项 / 风险预警</small>
            </div>
            <div className="balance-workbench__status-metric">
              <ClockCircleOutlined aria-hidden className="balance-workbench__status-icon" />
              <span>最近事件</span>
              <strong>{topEvent?.event_date ?? "未返回"}</strong>
              <small>{topEventTitle ?? "事件日历未返回"}</small>
            </div>
            <div className="balance-workbench__status-metric">
              <BranchesOutlined aria-hidden className="balance-workbench__status-icon" />
              <span>首页主动作</span>
              <strong>{homepageActionTitle}</strong>
              <small>{homepageActionMeta}</small>
            </div>
          </div>
          <div className="balance-workbench__status-bottom">
            {activeStateSentinels.length > 0 ? (
              <div
                data-testid="balance-analysis-abnormal-sentinels"
                className="balance-workbench__sentinels"
              >
                <div className="balance-workbench__sentinels-head">
                  <span className="balance-workbench__eyebrow">需关注</span>
                  <strong>需处理事项</strong>
                </div>
                <div className="balance-workbench__sentinel-list">
                  {activeStateSentinels.map((sentinel) => (
                    <span
                      key={sentinel.key}
                      className="balance-workbench__sentinel"
                      data-active="true"
                      data-status={sentinel.status}
                      title={sentinel.detail}
                    >
                      <i aria-hidden />
                      <b>{sentinel.label}</b>
                      <small>{sentinel.detail}</small>
                    </span>
                  ))}
                </div>
              </div>
            ) : null}
            <div
              className="balance-workbench__status-callout"
              data-testid="balance-analysis-homepage-focus"
              hidden
            >
              <IconBadge tone={topDecision ? "action" : topRisk ? "risk" : "evidence"} icon={<AuditOutlined />} />
              <div>
                <span>首页主动作 / Next best action</span>
                <strong>{homepageActionTitle}</strong>
                <small>{homepageActionMeta}</small>
                <div className="balance-workbench__action-chips" aria-label="首页主动作入口">
                  <span>确认</span>
                  <span>暂缓</span>
                  <span>查看证据</span>
                </div>
              </div>
            </div>
          </div>
          <div className="balance-workbench__filter-note">{compactFilters}</div>
        </aside>
      </section>

      <section className="balance-workbench__homepage-kpis" data-testid="balance-analysis-contract-kpis">
        <div className="balance-workbench__homepage-kpis-head">
          <span className="balance-workbench__eyebrow">核心指标速览</span>
          <strong>正式汇总</strong>
        </div>
        <div className="balance-workbench__homepage-kpi-grid">
          {homepageKpis.map((kpi) => (
            <article key={kpi.key} className="balance-workbench__homepage-kpi">
              <span>{kpi.label}</span>
              <strong>
                {metricValueDisplay(kpi.value)}
                {kpi.value === "—" ? null : <small>{kpi.unit}</small>}
              </strong>
              <em>{kpi.source}</em>
            </article>
          ))}
        </div>
      </section>

      <section className="balance-workbench__lower-grid" aria-label="核心对比与下钻工作区">
        {comparisonPairs.length > 0 ? (
          <section
            data-testid="balance-analysis-comparison-matrix"
            className="balance-workbench__comparison-matrix"
          >
            <div className="balance-workbench__comparison-head">
              <IconBadge tone="asset" icon={<BarChartOutlined />} />
              <span className="balance-workbench__eyebrow">核心规模对比</span>
              <h2>资产端 / 负债端并排判断</h2>
            </div>
            <div className="balance-workbench__comparison-grid">
              {comparisonPairs.map((pair) => (
                <article
                  key={pair.key}
                  data-testid={`balance-analysis-comparison-row-${pair.key}`}
                  className="balance-workbench__comparison-card"
                >
                  <h3>
                    <LineChartOutlined aria-hidden />
                    {pair.title}
                  </h3>
                  <div className="balance-workbench__comparison-row balance-workbench__comparison-row--asset">
                    <span>{pair.asset.label}</span>
                    <strong>{metricDisplay(pair.asset)}</strong>
                    <div className="balance-workbench__comparison-track" aria-hidden>
                      <i style={{ width: pair.assetWidth }} />
                    </div>
                  </div>
                  <div className="balance-workbench__comparison-row balance-workbench__comparison-row--liability">
                    <span>{pair.liability.label}</span>
                    <strong>{metricDisplay(pair.liability)}</strong>
                    <div className="balance-workbench__comparison-track" aria-hidden>
                      <i style={{ width: pair.liabilityWidth }} />
                    </div>
                  </div>
                </article>
              ))}
            </div>
          </section>
        ) : null}

        <section
          data-testid="balance-analysis-secondary-workbench"
          className="balance-workbench__secondary-workbench"
          aria-label="资产负债分析下钻工作台"
        >
          <div className="balance-workbench__secondary-heading">
            <span className="balance-workbench__eyebrow">下钻工作台</span>
            <strong>汇总、工作簿与治理闭环</strong>
            <small>把首屏判断导向可执行读面，技术路径和审计字段收在抽屉。</small>
          </div>
          <article className="balance-workbench__secondary-panel">
            <div className="balance-workbench__secondary-title">
              <IconBadge tone="asset" icon={<TableOutlined />} />
              <div>
                <strong>汇总驾驶舱</strong>
                <span>汇总与明细</span>
              </div>
            </div>
            <dl className="balance-workbench__secondary-stats">
              <div>
                <dt>汇总行</dt>
                <dd>{summary?.total_rows ?? 0}</dd>
              </div>
              <div>
                <dt>当前页</dt>
                <dd>{summary?.rows.length ?? 0}</dd>
              </div>
            </dl>
            <ul className="balance-workbench__secondary-list">
              {tableRows.length > 0
                ? firstRows(tableRows, 3).map((row) => (
                    <li key={row.row_key}>
                      <strong>{row.display_name}</strong>
                      <span>{formatBalanceAmountToYiFromYuan(row.market_value_amount)} 亿元</span>
                    </li>
                  ))
                : [
                    <li key="summary-empty">
                      <strong>等待汇总读面</strong>
                      <span>暂无可展示明细</span>
                    </li>,
                  ]}
            </ul>
          </article>
          <article className="balance-workbench__secondary-panel">
            <div className="balance-workbench__secondary-title">
              <IconBadge tone="evidence" icon={<PartitionOutlined />} />
              <div>
                <strong>工作簿图谱</strong>
                <span>结构与分布</span>
              </div>
            </div>
            <dl className="balance-workbench__secondary-stats">
              <div>
                <dt>表</dt>
                <dd>{workbook?.tables.length ?? 0}</dd>
              </div>
              <div>
                <dt>卡片</dt>
                <dd>{workbook?.cards.length ?? 0}</dd>
              </div>
            </dl>
            <ul className="balance-workbench__secondary-list">
              {(workbook?.tables.length ?? 0) > 0
                ? firstRows(workbook?.tables ?? [], 4).map((table) => (
                    <li key={table.key}>
                      <strong>{formatBalanceBusinessTextDisplay(table.title)}</strong>
                      <span>{table.rows.length} 行 / {table.columns.length} 列</span>
                    </li>
                  ))
                : [
                    <li key="workbook-empty">
                      <strong>等待工作簿图谱</strong>
                      <span>暂无结构面板</span>
                    </li>,
                  ]}
            </ul>
          </article>
          <article className="balance-workbench__secondary-panel">
            <div className="balance-workbench__secondary-title">
              <IconBadge tone="action" icon={<AuditOutlined />} />
              <div>
                <strong>治理闭环</strong>
                <span>决策与预警</span>
              </div>
            </div>
            <dl className="balance-workbench__secondary-stats">
              <div>
                <dt>决策项</dt>
                <dd>{decisionRows.length}</dd>
              </div>
              <div>
                <dt>预警</dt>
                <dd>{riskAlerts.length}</dd>
              </div>
            </dl>
            <ul className="balance-workbench__secondary-list">
              {decisionRows.length > 0
                ? firstRows(decisionRows, 3).map((row) => (
                    <li key={row.decision_key}>
                      <strong>{formatBalanceBusinessTextDisplay(row.title)}</strong>
                      <span>
                        {formatBalanceGovernedSeverityDisplay(row.severity)} /{" "}
                        {row.latest_status?.status
                          ? formatBalanceDecisionWorkflowStatusDisplay(row.latest_status.status)
                          : "待治理反馈"}
                      </span>
                    </li>
                  ))
                : [
                    <li key="decision-empty">
                      <strong>暂无治理动作</strong>
                      <span>暂无待办事项</span>
                    </li>,
                  ]}
            </ul>
          </article>
        </section>
      </section>

      <details
        data-testid="balance-analysis-endpoint-matrix"
        className="balance-workbench__endpoint-matrix balance-workbench__endpoint-drawer"
        aria-label="资产负债分析数据读面链路"
      >
        <summary className="balance-workbench__endpoint-summary">
          <div className="balance-workbench__endpoint-head">
            <div>
              <span className="balance-workbench__eyebrow">数据读面链路</span>
              <strong>读面目录与返回摘要</strong>
            </div>
            <span className="balance-workbench__endpoint-auto">
              {endpointSummaryLine}
            </span>
          </div>
        </summary>
        <span className="balance-workbench__endpoint-a11y-summary">
          {endpointMatrixHiddenSummary} 首屏 高级归因 决策处理
        </span>
        <div className="balance-workbench__endpoint-body">
          {endpointGroups.map((group) => (
            <article
              key={group.key}
              className={`balance-workbench__endpoint-group${
                group.key === "first-screen" ? " balance-workbench__endpoint-group--hero" : ""
              }`}
              data-testid={`balance-analysis-endpoint-group-${group.key}`}
              data-tone={group.tone}
            >
              <div className="balance-workbench__endpoint-group-head">
                <strong>
                  {group.title}
                </strong>
                <em>{group.count} 个读面 · {formatEndpointGroupStatusSummary(group)}</em>
              </div>
              <div className="balance-workbench__endpoint-chip-grid">
                {group.endpoints.map(renderEndpointChip)}
              </div>
            </article>
          ))}
        </div>
      </details>

      <details
        data-testid="balance-analysis-deferred-strip"
        className="balance-workbench__deferred-strip"
        aria-label="资产负债分析自动补充分析"
      >
        <summary className="balance-workbench__deferred-summary">
          <span className="balance-workbench__section-tab">补充分析</span>
          <div className="balance-workbench__deferred-head">
            <span className="balance-workbench__eyebrow">解释材料</span>
            <strong>自动补充分析 5</strong>
            <small>首屏稳定后补充解释材料，不替代正式结论。</small>
          </div>
        </summary>
        <div className="balance-workbench__deferred-grid">
          {deferredSurfaces.map((surface) => (
            <article
              key={surface.key}
              className="balance-workbench__deferred-card"
              data-status={surface.status}
            >
              <div>
                <strong>{surface.title}</strong>
                <span>{surface.endpoint}</span>
              </div>
              {surface.status === "error" ? <em>{formatEndpointStatus(surface.status)}</em> : null}
              {renderDeferredVisual(surface)}
              <b>{surface.value}</b>
              <small>{surface.detail}</small>
            </article>
          ))}
        </div>
      </details>

      <details className="balance-workbench__metric-drawer">
        <summary className="balance-workbench__metric-drawer-summary">
          <span className="balance-workbench__eyebrow">完整指标卡片</span>
          <strong>资产端、负债端与证据规模明细</strong>
          <span>默认收起，首屏以并排规模矩阵和证据工作区为主。</span>
        </summary>
        <div data-testid="balance-analysis-overview-cards" className="balance-workbench__metrics">
          {metricGroups.map((group) => (
            <section key={group.key} className={`balance-workbench__metric-group balance-workbench__metric-group--${group.key}`}>
              <h2 className="balance-workbench__metric-group-title">
                <IconBadge tone={group.key === "asset" ? "asset" : group.key === "liability" ? "liability" : "evidence"} icon={metricGroupLabels[group.key].icon} />
                {metricGroupLabels[group.key].label}
              </h2>
              <div className="balance-workbench__metric-group-grid">
                {group.metrics.map((metric) => (
                  <div
                    key={metric.key}
                    data-testid="balance-analysis-horizontal-metric"
                    className="balance-workbench__metric"
                  >
                    <div className="balance-workbench__metric-card">
                      <IconBadge
                        tone={group.key === "asset" ? "asset" : group.key === "liability" ? "liability" : "evidence"}
                        icon={<MetricIcon group={group.key} label={metric.label} />}
                      />
                      <div className="balance-workbench__metric-copy">
                        <span>{metric.label}</span>
                        <strong>
                          {metricValueDisplay(metric.value)}
                          {metric.unit && metric.value !== "—" ? <small>{metric.unit}</small> : null}
                        </strong>
                        {metric.detail ? <em>{metric.detail}</em> : null}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          ))}
        </div>
      </details>

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

      <details className="balance-workbench__legacy-drawer">
        <summary className="balance-workbench__legacy-drawer-summary">
          <span className="balance-workbench__eyebrow">更多底稿</span>
          <strong>治理、结构与证据工作卡片</strong>
          <span>默认收起，首页先保留判断和下钻动作。</span>
        </summary>
        <section data-testid="balance-analysis-workbench-grid" className="balance-workbench__grid">
          {cards.map((card) => (
            <article
              key={card.key}
              className={`balance-workbench-card balance-workbench-card--span-${card.span} balance-workbench-card--${card.key}`}
              data-testid={`balance-analysis-workbench-card-${card.key}`}
            >
              <h2 className="balance-workbench-card__heading">
                <IconBadge tone={card.tone} icon={card.icon} />
                {card.title}
              </h2>
              {card.body}
            </article>
          ))}
        </section>
      </details>

      <nav
        data-testid="balance-analysis-portfolio-nav"
        className="balance-workbench__portfolio-nav"
        aria-label="组合工作台导航"
      >
        <strong className="balance-workbench__portfolio-nav-title">
          <ClusterOutlined aria-hidden />
          组合工作台导航
        </strong>
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
