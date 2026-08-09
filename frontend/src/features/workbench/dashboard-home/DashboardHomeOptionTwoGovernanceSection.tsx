import {
  useRef,
  useState,
  type KeyboardEvent,
} from "react";

import type {
  DashboardHomeBodyView,
  HomeDataStateKind,
  HomeTerminalListState,
} from "./dashboardHomeBodyView";
import type { DashboardHomeAvailability } from "./dashboardHomeAvailability";
import styles from "./dashboardHomeOptionTwoGovernanceSection.module.css";

type DashboardHomeOptionTwoGovernanceSectionProps = {
  view: DashboardHomeBodyView;
  availability?: DashboardHomeAvailability;
  supplementalStateLabel?: string;
};

type GovernanceTabId = "source" | "evidence" | "api" | "lineage";
type LedgerTone = "ok" | "warn" | "bad" | "muted";
type LedgerStatus = { label: string; tone: LedgerTone };

const GAP = "—";
const GOVERNANCE_TABS: ReadonlyArray<{
  id: GovernanceTabId;
  label: string;
}> = [
  { id: "source", label: "来源核验" },
  { id: "evidence", label: "证据覆盖" },
  { id: "api", label: "接口台账" },
  { id: "lineage", label: "数据链路" },
];

const STATE_FALLBACK: Record<HomeDataStateKind, string> = {
  ready: "已就绪",
  partial: "部分可用",
  empty: "暂无数据",
  loading: "读取中",
  error: "不可用",
  stale: "数据偏旧",
  "backend-gap": "待接入",
};

const UNREQUESTED_STATUS: LedgerStatus = {
  label: "未请求",
  tone: "muted",
};
const RESERVED_STATUS: LedgerStatus = { label: "保留", tone: "muted" };
const UNKNOWN_STATUS: LedgerStatus = { label: GAP, tone: "muted" };

function optionalText(value: string | null | undefined): string {
  const normalized = value?.trim() ?? "";
  return normalized && normalized !== GAP
    ? normalized
    : "";
}

function displayText(value: string | null | undefined): string {
  return optionalText(value) || GAP;
}

function reportDateFrom(value: string | null | undefined): string {
  return optionalText(value).match(/^\d{4}-\d{2}-\d{2}/)?.[0] ?? "";
}

function periodFrom(value: string | null | undefined): string {
  return optionalText(value).match(/^\d{4}-\d{2}(?:-\d{2})?/)?.[0] ?? "";
}

function latestValue<T>(
  rows: readonly T[],
  select: (row: T) => string,
): string {
  return rows.reduce((latest, row) => {
    const candidate = select(row);
    return candidate > latest ? candidate : latest;
  }, "");
}

function visibleAsOf(value: string | null | undefined): string {
  const normalized = optionalText(value).replace(
    /^(?:数据截至|截至|更新于)[：:]\s*/,
    "",
  );
  return /^(?:暂无|未知|待更新|未提供)/.test(normalized)
    ? GAP
    : normalized || GAP;
}

function toneForState(kind: HomeDataStateKind): LedgerTone {
  if (kind === "ready") return "ok";
  if (kind === "error") return "bad";
  if (kind === "partial" || kind === "stale" || kind === "backend-gap") {
    return "warn";
  }
  return "muted";
}

function statusFromState(state: HomeTerminalListState): LedgerStatus {
  return {
    label: optionalText(state.label) || STATE_FALLBACK[state.kind],
    tone: toneForState(state.kind),
  };
}

function aggregateStatus(
  states: readonly HomeTerminalListState[],
): LedgerStatus {
  const priority: readonly HomeDataStateKind[] = [
    "error",
    "backend-gap",
    "stale",
    "partial",
    "loading",
    "empty",
    "ready",
  ];
  const kind =
    priority.find((candidate) =>
      states.some((state) => state.kind === candidate),
    ) ?? "empty";
  return {
    label: STATE_FALLBACK[kind],
    tone: toneForState(kind),
  };
}

function availabilityStatus(
  availability: DashboardHomeAvailability | undefined,
): LedgerStatus {
  if (!availability) return UNKNOWN_STATUS;
  const label = optionalText(availability.label);
  if (availability.kind === "available") {
    return { label: label || "数据可用", tone: "ok" };
  }
  if (availability.kind === "error") {
    return { label: label || "不可用", tone: "bad" };
  }
  return { label: label || "部分可用", tone: "warn" };
}

function supplementalStatus(label: string | undefined): LedgerStatus {
  const normalized = optionalText(label);
  if (!normalized) return UNKNOWN_STATUS;
  // Only the upstream state label reaches this boundary. Keep its tone neutral
  // instead of reverse-engineering business status from copy.
  return { label: normalized, tone: "muted" };
}

function Status({ status }: { status: LedgerStatus }) {
  return (
    <span className={styles.status} data-tone={status.tone}>
      {status.label}
    </span>
  );
}

export function DashboardHomeOptionTwoGovernanceSection({
  view,
  availability,
  supplementalStateLabel,
}: DashboardHomeOptionTwoGovernanceSectionProps) {
  const [activeTab, setActiveTab] = useState<GovernanceTabId>("source");
  const tabRefs = useRef<Partial<Record<GovernanceTabId, HTMLButtonElement>>>({});

  const availabilityResolved = availability
    ? availability.hasResolvedReportDate && availability.kind !== "error"
    : Boolean(reportDateFrom(view.reportDate));
  const reportDate = availabilityResolved
    ? reportDateFrom(availability?.actualReportDate) ||
      reportDateFrom(view.reportDate)
    : "";
  const latestResearchDate = latestValue(view.researchReports, (row) =>
    reportDateFrom(row.publishedAt),
  );
  const latestIncomePeriod = latestValue(view.incomeTrend, (row) =>
    periodFrom(row.date),
  );
  const bondNewsCount =
    view.bondNews.holdingHits.length +
    view.bondNews.marketNews.length +
    view.bondNews.creditAndIssuanceNews.length;
  const macroNewsCount = view.macroBriefing.newsItems.length;

  const bondNewsStatus: LedgerStatus =
    bondNewsCount === 0
      ? { label: "暂无数据", tone: "muted" }
      : {
          label: optionalText(view.bondNews.statusLabel) || "部分可用",
          tone: "warn",
        };
  const macroNewsStatus: LedgerStatus =
    macroNewsCount === 0
      ? { label: "暂无数据", tone: "muted" }
      : view.macroBriefing.newsStale
        ? { label: "数据偏旧", tone: "warn" }
        : {
            label:
              optionalText(view.macroBriefing.newsStatusLabel) || "部分可用",
            tone: "warn",
          };

  const sourceRows = [
    {
      id: "holdings",
      label: "重点持仓",
      basis: "/api/bond-analytics/top-holdings",
      date: view.holdingRows.length > 0 ? displayText(reportDate) : GAP,
      count: view.holdingRows.length,
      status: statusFromState(view.holdingsState),
    },
    {
      id: "position",
      label: "仓位变动",
      basis: "/api/bond-analytics/position-changes",
      date: view.positionChanges.length > 0 ? displayText(reportDate) : GAP,
      count: view.positionChanges.length,
      status: statusFromState(view.positionChangesState),
    },
    {
      id: "research",
      label: "研究报告",
      basis: "/ui/home/research-reports",
      date: displayText(latestResearchDate),
      count: view.researchReports.length,
      status: statusFromState(view.researchReportsState),
    },
    {
      id: "income",
      label: "收益趋势",
      basis:
        optionalText(view.incomeTrendSection.source) || "/ui/home/income-trend",
      date: displayText(latestIncomePeriod),
      count: view.incomeTrend.length,
      status: statusFromState(view.incomeTrendState),
    },
    {
      id: "bond-news",
      label: "债券新闻",
      basis: displayText(view.bondNews.sourceLabel),
      date: visibleAsOf(view.bondNews.asOfLabel),
      count: bondNewsCount,
      status: bondNewsStatus,
    },
    {
      id: "macro-news",
      label: "宏观新闻",
      basis: displayText(view.macroBriefing.newsSourceLabel),
      date: visibleAsOf(view.macroBriefing.newsAsOfLabel),
      count: macroNewsCount,
      status: macroNewsStatus,
    },
  ] as const;

  const formalCount = view.holdingRows.length + view.positionChanges.length;
  const analyticalCount =
    view.researchReports.length + view.incomeTrend.length;
  const snapshotDate =
    optionalText(availability?.generatedAt) ||
    reportDateFrom(availability?.actualReportDate) ||
    reportDate;
  const formalStatus = availabilityResolved
    ? aggregateStatus([view.holdingsState, view.positionChangesState])
    : UNREQUESTED_STATUS;
  const analyticalStatus = availabilityResolved
    ? aggregateStatus([view.researchReportsState, view.incomeTrendState])
    : UNREQUESTED_STATUS;
  const evidenceRows = [
    {
      id: "snapshot",
      label: "页面快照",
      date: displayText(snapshotDate),
      count: GAP,
      status: availabilityStatus(availability),
    },
    {
      id: "formal",
      label: "正式数据",
      date: availabilityResolved && formalCount > 0 ? displayText(reportDate) : GAP,
      count: availabilityResolved ? String(formalCount) : GAP,
      status: formalStatus,
    },
    {
      id: "analytical",
      label: "分析数据",
      date:
        availabilityResolved && analyticalCount > 0
          ? displayText(latestResearchDate > latestIncomePeriod
              ? latestResearchDate
              : latestIncomePeriod)
          : GAP,
      count: availabilityResolved ? String(analyticalCount) : GAP,
      status: analyticalStatus,
    },
    {
      id: "reserved",
      label: "保留接口",
      date: GAP,
      count: GAP,
      status: RESERVED_STATUS,
    },
  ] as const;

  const structureStatus = aggregateStatus([
    view.assetDistributionState,
    view.ratingDistributionState,
    view.maturityDistributionState,
    view.industryDistributionState,
    view.yieldDistributionState,
    view.portfolioComparisonState,
    view.riskExposureState,
  ]);
  const dependentStatus = (state: HomeTerminalListState) =>
    availabilityResolved ? statusFromState(state) : UNREQUESTED_STATUS;
  const apiRows = [
    {
      id: "snapshot",
      endpoint: "/ui/home/snapshot",
      scope: "判断、治理与核心指标",
      handling: "快照",
      status: availabilityStatus(availability),
    },
    {
      id: "supplemental",
      endpoint: "/api/dashboard/core_metrics + daily-changes",
      scope: "日期门控补充指标",
      handling: "补充",
      status: availabilityResolved
        ? supplementalStatus(supplementalStateLabel)
        : UNREQUESTED_STATUS,
    },
    {
      id: "summary",
      endpoint: "/api/bond-dashboard/home-summary",
      scope: "风险与结构看板",
      handling: "看板",
      status: availabilityResolved ? structureStatus : UNREQUESTED_STATUS,
    },
    {
      id: "holdings",
      endpoint: "/api/bond-analytics/top-holdings",
      scope: "重点持仓",
      handling: "正式",
      status: dependentStatus(view.holdingsState),
    },
    {
      id: "changes",
      endpoint: "/api/bond-analytics/position-changes",
      scope: "仓位变动",
      handling: "正式",
      status: dependentStatus(view.positionChangesState),
    },
    {
      id: "research",
      endpoint: "/ui/home/research-reports",
      scope: "研究资讯",
      handling: "分析",
      status: dependentStatus(view.researchReportsState),
    },
    {
      id: "income",
      endpoint: "/ui/home/income-trend",
      scope: "收益趋势",
      handling: "分析",
      status: dependentStatus(view.incomeTrendState),
    },
    {
      id: "reserved",
      endpoint: "/ui/home/alerts + contribution",
      scope: "预警与贡献保留区",
      handling: "保留",
      status: RESERVED_STATUS,
    },
  ] as const;

  const lineageRows = sourceRows.slice(0, 4);

  function onTabKeyDown(
    event: KeyboardEvent<HTMLButtonElement>,
    tabId: GovernanceTabId,
  ) {
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
    event.preventDefault();
    const currentIndex = GOVERNANCE_TABS.findIndex((tab) => tab.id === tabId);
    const offset = event.key === "ArrowRight" ? 1 : -1;
    const nextTab =
      GOVERNANCE_TABS[
        (currentIndex + offset + GOVERNANCE_TABS.length) %
          GOVERNANCE_TABS.length
      ];
    setActiveTab(nextTab.id);
    tabRefs.current[nextTab.id]?.focus();
  }

  return (
    <section
      className={styles.ledger}
      data-testid="dashboard-home-governance-ledger"
      aria-labelledby="dashboard-home-governance-ledger-title"
    >
      <header className={styles.header}>
        <div>
          <h2 id="dashboard-home-governance-ledger-title">数据治理台账</h2>
          <small>仅列示当前页面可见状态</small>
        </div>
        <span>4 个读链视图</span>
      </header>

      <div className={styles.tabs} role="tablist" aria-label="数据治理台账视图">
        {GOVERNANCE_TABS.map((tab) => (
          <button
            key={tab.id}
            ref={(node) => {
              if (node) tabRefs.current[tab.id] = node;
            }}
            id={`dashboard-home-governance-tab-${tab.id}`}
            type="button"
            role="tab"
            aria-controls={`dashboard-home-governance-panel-${tab.id}`}
            aria-selected={activeTab === tab.id}
            tabIndex={activeTab === tab.id ? 0 : -1}
            onClick={() => setActiveTab(tab.id)}
            onKeyDown={(event) => onTabKeyDown(event, tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className={styles.panels}>
        <div
          id="dashboard-home-governance-panel-source"
          role="tabpanel"
          aria-labelledby="dashboard-home-governance-tab-source"
          hidden={activeTab !== "source"}
          className={styles.panel}
          data-testid="dashboard-home-source-gate"
        >
          <div className={styles.tableWrap}>
            <table aria-label="来源核验明细">
              <thead>
                <tr>
                  <th scope="col">来源</th>
                  <th scope="col">日期</th>
                  <th scope="col">落地</th>
                  <th scope="col">状态</th>
                </tr>
              </thead>
              <tbody>
                {sourceRows.map((row) => (
                  <tr
                    key={row.id}
                    data-source-id={row.id}
                    data-testid="dashboard-home-source-gate-row"
                  >
                    <td className={styles.primary} title={row.basis}>
                      <strong>{row.label}</strong>
                      <small>{row.basis}</small>
                    </td>
                    <td className={styles.numeric}>{row.date}</td>
                    <td className={styles.numeric}>{row.count}</td>
                    <td><Status status={row.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div
          id="dashboard-home-governance-panel-evidence"
          role="tabpanel"
          aria-labelledby="dashboard-home-governance-tab-evidence"
          hidden={activeTab !== "evidence"}
          className={styles.panel}
          data-testid="dashboard-home-evidence-chain"
        >
          <div className={styles.tableWrap}>
            <table aria-label="页面证据覆盖">
              <thead>
                <tr>
                  <th scope="col">覆盖层</th>
                  <th scope="col">日期依据</th>
                  <th scope="col">落地</th>
                  <th scope="col">状态</th>
                </tr>
              </thead>
              <tbody>
                {evidenceRows.map((row) => (
                  <tr
                    key={row.id}
                    data-testid={`dashboard-home-evidence-row-${row.id}`}
                  >
                    <td className={styles.primary}><strong>{row.label}</strong></td>
                    <td className={styles.numeric}>{row.date}</td>
                    <td className={styles.numeric}>{row.count}</td>
                    <td><Status status={row.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div
          id="dashboard-home-governance-panel-api"
          role="tabpanel"
          aria-labelledby="dashboard-home-governance-tab-api"
          hidden={activeTab !== "api"}
          className={styles.panel}
        >
          <div className={styles.tableWrap}>
            <table aria-label="接口台账">
              <thead>
                <tr>
                  <th scope="col">接口</th>
                  <th scope="col">页面范围</th>
                  <th scope="col">处理</th>
                  <th scope="col">状态</th>
                </tr>
              </thead>
              <tbody>
                {apiRows.map((row) => (
                  <tr
                    key={row.id}
                    data-testid={`dashboard-home-api-row-${row.id}`}
                  >
                    <td className={styles.endpoint}>{row.endpoint}</td>
                    <td>{row.scope}</td>
                    <td>{row.handling}</td>
                    <td><Status status={row.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div
          id="dashboard-home-governance-panel-lineage"
          role="tabpanel"
          aria-labelledby="dashboard-home-governance-tab-lineage"
          hidden={activeTab !== "lineage"}
          className={styles.panel}
        >
          <div className={styles.tableWrap}>
            <table aria-label="页面数据链路">
              <thead>
                <tr>
                  <th scope="col">链路</th>
                  <th scope="col">日期依据</th>
                  <th scope="col">落地</th>
                  <th scope="col">状态</th>
                </tr>
              </thead>
              <tbody>
                {lineageRows.map((row) => (
                  <tr
                    key={row.id}
                    data-lineage-id={row.id}
                    data-testid="dashboard-home-data-task-row"
                  >
                    <td className={styles.primary}><strong>{row.label}</strong></td>
                    <td className={styles.numeric}>{row.date}</td>
                    <td className={styles.numeric}>{row.count}</td>
                    <td><Status status={row.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <footer className={styles.footer}>页面读链 · 非审计结论</footer>
    </section>
  );
}
