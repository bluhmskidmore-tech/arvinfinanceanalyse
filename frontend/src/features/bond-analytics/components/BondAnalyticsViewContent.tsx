import { Suspense, lazy, useContext, useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Select } from "antd";
import { useSearchParams } from "react-router-dom";

import type { ApiEnvelope } from "../../../api/contracts";
import { useApiClient } from "../../../api/client";
import { runPollingTask } from "../../../app/jobs/polling";
import { usePollingTaskSignal } from "../../../app/jobs/usePollingTaskSignal";
import { PageStateSurface } from "../../../components/page/PagePrimitives";
import { SystemReadInteractionContext } from "../../../router/systemReadInteractionContext";
import { mapResearchCalendarEventToCalendarItem } from "../../../lib/researchCalendarToCalendarItem";
import { isAgentFrontendEnabled } from "../../../app/navigation";
import type {
  ActionAttributionResponse,
  BondAnalyticsAccountingClassFilter,
  BondAnalyticsAssetClassFilter,
  BondAnalyticsScenarioSetFilter,
  PeriodType,
} from "../types";
import type { BondAnalyticsModuleKey } from "../lib/bondAnalyticsModuleRegistry";
import { buildBondAnalyticsOverviewModel } from "../lib/bondAnalyticsOverviewModel";
import { bondAnalyticsQueryKeyRoot } from "../lib/bondAnalyticsQueryKeys";
import { EM_DASH } from "../../../utils/format";
import { PERIOD_OPTIONS } from "./bondAnalyticsCockpitTokens";
import styles from "./BondAnalyticsViewContent.module.css";

const BondAnalyticsOverviewPanels = lazy(() =>
  import("./BondAnalyticsOverviewPanels").then((module) => ({
    default: module.BondAnalyticsOverviewPanels,
  })),
);

const BondAnalyticsDetailSection = lazy(() =>
  import("./BondAnalyticsDetailSection").then((module) => ({
    default: module.BondAnalyticsDetailSection,
  })),
);

const LazyBondAnalyticsAgentDrawer = lazy(() =>
  import("./BondAnalyticsAgentDrawer").then((module) => ({
    default: module.BondAnalyticsAgentDrawer,
  })),
);

type BondAnalyticsDateFallbackKind = "error" | "empty";

function BondAnalyticsDateFallbackWorkbench({
  kind,
  onRetry,
}: {
  kind: BondAnalyticsDateFallbackKind;
  onRetry: () => void;
}) {
  const title = kind === "error" ? "债券分析日期载入失败" : "债券分析暂无可用报告日";
  const body =
    kind === "error"
      ? "可用报告日加载失败，暂时无法展示债券分析。请重试。"
      : "暂无可用报告日，债券分析暂不可用。";

  return (
    <section
      data-testid="bond-analysis-date-fallback-workbench"
      className={styles.fallbackWorkbench}
      aria-label={title}
    >
      <div className={styles.fallbackNotice}>
        <div>
          <div className={styles.stateTitle}>{title}</div>
          <div className={styles.stateBody}>{body}</div>
        </div>
        <button
          type="button"
          onClick={onRetry}
          className="dashboard-home-action-button dashboard-home-action-button--secondary"
        >
          重试日期载入
        </button>
      </div>

      <div className={styles.fallbackMarketStrip} data-testid="bond-analysis-market-ticker">
        {["10年国债", "10年国开", "中美10年利差", "DR007", "美元/人民币", "原油", "沪深300"].map(
          (label) => (
            <div key={label} className={styles.fallbackTickerCell}>
              <span>{label}</span>
              <strong>{EM_DASH}</strong>
              <small>待读取</small>
            </div>
          ),
        )}
      </div>

      <div className={styles.fallbackJudgment} data-testid="bond-analysis-daily-judgment">
        <div className={styles.fallbackSectionTitle}>核心指标</div>
        <p>报告日尚未确认，暂时无法形成债券分析结论。</p>
      </div>

      <div className={styles.fallbackGrid}>
        <div className={styles.fallbackPanel} data-testid="bond-analysis-yield-curve-panel">
          <span>收益率曲线与日变动</span>
          <strong>待报告日确认</strong>
        </div>
        <div className={styles.fallbackPanel} data-testid="bond-analysis-return-attribution-panel">
          <span>收益归因</span>
          <strong>暂无动作归因数据</strong>
        </div>
        <div className={styles.fallbackPanel} data-testid="bond-analysis-risk-monitor">
          <span>风险监控</span>
          <strong>暂无 DV01 和久期数据</strong>
        </div>
      </div>
    </section>
  );
}

export function BondAnalyticsViewContent() {
  const client = useApiClient();
  const getPollingSignal = usePollingTaskSignal();
  const queryClient = useQueryClient();
  const systemReadInteraction = useContext(SystemReadInteractionContext);

  useEffect(() => {
    void import("./BondAnalyticsOverviewPanels");
  }, []);

  const [searchParams] = useSearchParams();
  const explicitReportDate = searchParams.get("report_date")?.trim() || "";
  const datesQuery = useQuery({
    queryKey: [...bondAnalyticsQueryKeyRoot, "dates", client.mode],
    queryFn: () => client.getBondAnalyticsDates(),
    // 报告日决定整页可用性：后端闪断（如重启窗口内的 502）先按 TanStack 默认退避重试，
    // 重试仍失败才翻转到日期兜底工作台。
    retry: 2,
  });
  const dateOptions = useMemo(() => {
    const reportDates = datesQuery.data?.result.report_dates ?? [];
    const options = reportDates.map((value) => ({ value, label: value }));
    if (
      explicitReportDate &&
      !options.some((option) => option.value === explicitReportDate)
    ) {
      return [{ value: explicitReportDate, label: explicitReportDate }, ...options];
    }
    return options;
  }, [datesQuery.data?.result.report_dates, explicitReportDate]);

  const [reportDate, setReportDate] = useState("");
  const [periodType, setPeriodType] = useState<PeriodType>("MoM");
  const [assetClass, setAssetClass] = useState<BondAnalyticsAssetClassFilter>("all");
  const [accountingClass, setAccountingClass] =
    useState<BondAnalyticsAccountingClassFilter>("all");
  const [scenarioSet, setScenarioSet] =
    useState<BondAnalyticsScenarioSetFilter>("standard");
  const [spreadScenarios, setSpreadScenarios] = useState("10,25,50");
  const [activeTab, setActiveTab] =
    useState<BondAnalyticsModuleKey>("action-attribution");
  const [isBondAnalyticsRefreshing, setIsBondAnalyticsRefreshing] = useState(false);
  const [bondAnalyticsRefreshError, setBondAnalyticsRefreshError] =
    useState<string | null>(null);
  const [lastBondAnalyticsRefreshRunId, setLastBondAnalyticsRefreshRunId] =
    useState<string | null>(null);
  const [bondAnalyticsRefreshAwaitingPublication, setBondAnalyticsRefreshAwaitingPublication] =
    useState(false);
  const [detailRemountKey, setDetailRemountKey] = useState(0);
  const [isDetailDrilldownOpen, setIsDetailDrilldownOpen] = useState(false);
  const [agentPanelOpen, setAgentPanelOpen] = useState(false);
  const [agentPanelMounted, setAgentPanelMounted] = useState(false);

  const resolvedReportDate = useMemo(() => {
    if (explicitReportDate) {
      return explicitReportDate;
    }
    return datesQuery.data?.result.report_dates[0] ?? "";
  }, [datesQuery.data?.result.report_dates, explicitReportDate]);

  const effectiveReportDate = reportDate || resolvedReportDate;
  const datesEmpty =
    !explicitReportDate &&
    !datesQuery.isLoading &&
    !datesQuery.isError &&
    (datesQuery.data?.result.report_dates.length ?? 0) === 0;
  const showDatesErrorState = datesQuery.isError && !effectiveReportDate;

  const actionAttributionQuery = useQuery({
    queryKey: [
      ...bondAnalyticsQueryKeyRoot,
      "overview-action-attribution",
      client.mode,
      effectiveReportDate,
      periodType,
    ],
    queryFn: async (): Promise<ApiEnvelope<ActionAttributionResponse>> =>
      client.getBondAnalyticsActionAttribution(effectiveReportDate, periodType),
    enabled: Boolean(effectiveReportDate),
    // 失败不决定整页可用性：工作台保持可见，错误经 overviewModel 显式呈现，保持快速失败。
    retry: false,
  });

  const researchCalendarQuery = useQuery({
    queryKey: [
      ...bondAnalyticsQueryKeyRoot,
      "research-calendar",
      client.mode,
      effectiveReportDate,
    ],
    queryFn: () => client.getResearchCalendarEvents({ reportDate: effectiveReportDate }),
    enabled: Boolean(effectiveReportDate),
    // 纯展示性日历条：失败仅降级为空列表，保持快速失败。
    retry: false,
  });

  const actionAttributionErrorMessage =
    actionAttributionQuery.error instanceof Error
      ? actionAttributionQuery.error.message
      : null;

  async function handleBondAnalyticsRefresh() {
    const signal = getPollingSignal();
    if (!effectiveReportDate) {
      return;
    }
    setIsBondAnalyticsRefreshing(true);
    setBondAnalyticsRefreshError(null);
    setBondAnalyticsRefreshAwaitingPublication(false);
    try {
      const payload = await runPollingTask({
        signal,
        start: () => client.refreshBondAnalytics(effectiveReportDate),
        getStatus: (runId) => client.getBondAnalyticsRefreshStatus(runId),
        onUpdate: (nextPayload) => {
          if (nextPayload.run_id) {
            setLastBondAnalyticsRefreshRunId(nextPayload.run_id);
          }
        },
      });
      if (signal?.aborted) return;
      if (payload.status !== "completed") {
        const hint =
          typeof payload.error_message === "string" && payload.error_message.trim()
            ? payload.error_message
            : `债券分析刷新未完成：${payload.status}`;
        const rid = payload.run_id ? ` run_id: ${payload.run_id}` : "";
        throw new Error(`${hint}${rid}`);
      }
      if (systemReadInteraction?.generation) {
        setBondAnalyticsRefreshAwaitingPublication(true);
        return;
      }
      await queryClient.invalidateQueries({ queryKey: [...bondAnalyticsQueryKeyRoot] });
      if (!signal?.aborted) setDetailRemountKey((key) => key + 1);
    } catch (error: unknown) {
      if (signal?.aborted) return;
      setBondAnalyticsRefreshError(
        error instanceof Error ? error.message : "刷新债券分析失败",
      );
    } finally {
      if (!signal?.aborted) setIsBondAnalyticsRefreshing(false);
    }
  }

  const overviewModel = buildBondAnalyticsOverviewModel({
    reportDate: effectiveReportDate,
    periodType,
    activeModuleKey: activeTab,
    actionAttributionEnvelope: actionAttributionQuery.data ?? null,
    actionAttributionLoading:
      actionAttributionQuery.isPending && !actionAttributionQuery.isError,
    actionAttributionError: actionAttributionErrorMessage,
  });

  const agentPanelFilters = useMemo(
    () => ({
      period_type: periodType,
      asset_class: assetClass,
      accounting_class: accountingClass,
      scenario_set: scenarioSet,
      spread_scenarios: spreadScenarios,
    }),
    [periodType, assetClass, accountingClass, scenarioSet, spreadScenarios],
  );

  function openAgentPanel() {
    setAgentPanelMounted(true);
    setAgentPanelOpen(true);
  }

  const calendarItems = useMemo(
    () =>
      (researchCalendarQuery.data ?? [])
        .map(mapResearchCalendarEventToCalendarItem)
        .slice(0, 4),
    [researchCalendarQuery.data],
  );

  function openModuleDetail(moduleKey: BondAnalyticsModuleKey) {
    setActiveTab(moduleKey);
    setIsDetailDrilldownOpen(true);
  }

  const dateFallbackKind: BondAnalyticsDateFallbackKind | null = showDatesErrorState
    ? "error"
    : datesEmpty && !effectiveReportDate
      ? "empty"
      : null;
  const canRenderAnalytics = Boolean(effectiveReportDate) && !dateFallbackKind;

  return (
    <section
      data-testid="bond-analysis-overview"
      data-moss-theme-scope="bond-analysis"
      className={`dashboard-home-shell ${styles.bondWorkbenchPage}`}
    >
      <header data-testid="bond-analysis-toolbar" className="dashboard-home-toolbar">
        <div className="dashboard-home-toolbar__identity">
          <h1 className="dashboard-home-toolbar__title">债券分析</h1>
        </div>
        <div className="dashboard-home-actions">
          <label className="dashboard-home-control">
            <span>报告日</span>
            <Select<string>
              aria-label="报告日"
              className={`${styles.toolbarDateSelect} ${styles.toolbarSelectWide}`}
              classNames={{ popup: { root: styles.toolbarDateDropdown } }}
              value={effectiveReportDate || undefined}
              onChange={setReportDate}
              disabled={dateOptions.length === 0}
              loading={datesQuery.isLoading}
              options={dateOptions}
              placeholder="待确认"
              showSearch
              optionFilterProp="label"
              virtual
              getPopupContainer={(trigger) => trigger.parentElement ?? document.body}
            />
          </label>
          <label className="dashboard-home-control">
            <span>期间</span>
            <select
              aria-label="统计区间"
              className={styles.toolbarSelect}
              value={periodType}
              onChange={(event) => setPeriodType(event.target.value as PeriodType)}
            >
              {PERIOD_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <span aria-hidden="true" className="dashboard-home-actions__divider" />
          {isAgentFrontendEnabled() ? (
            <button
              type="button"
              data-testid="bond-analysis-agent-open"
              onClick={openAgentPanel}
              aria-label="打开复核助手"
              className="dashboard-home-action-button dashboard-home-action-button--secondary"
            >
              复核助手
            </button>
          ) : null}
          <button
            type="button"
            onClick={() => void handleBondAnalyticsRefresh()}
            disabled={isBondAnalyticsRefreshing || !canRenderAnalytics}
            className={
              isBondAnalyticsRefreshing || !canRenderAnalytics
                ? `dashboard-home-action-button dashboard-home-action-button--disabled ${styles.refreshButton}`
                : `dashboard-home-action-button dashboard-home-action-button--primary ${styles.refreshButton}`
            }
          >
            {isBondAnalyticsRefreshing ? "刷新中" : "刷新"}
          </button>
        </div>
      </header>

      {bondAnalyticsRefreshAwaitingPublication ? (
        <PageStateSurface
          variant="stale"
          title="计算任务完成"
          description="当前页面仍显示已发布的数据。请在数据中心完成发布后重新进入本页。"
          testId="bond-analysis-refresh-awaiting-publication"
        />
      ) : null}

      {dateFallbackKind ? (
        <BondAnalyticsDateFallbackWorkbench
          kind={dateFallbackKind}
          onRetry={() => void datesQuery.refetch()}
        />
      ) : (
        <>
          <Suspense
            fallback={
              <div className={styles.detailFallback} data-testid="bond-analysis-overview-loading">
                正在加载总览...
              </div>
            }
          >
            <BondAnalyticsOverviewPanels
              dateOptions={dateOptions}
              reportDate={effectiveReportDate}
              onReportDateChange={setReportDate}
              periodType={periodType}
              onPeriodTypeChange={setPeriodType}
              assetClass={assetClass}
              onAssetClassChange={setAssetClass}
              accountingClass={accountingClass}
              onAccountingClassChange={setAccountingClass}
              scenarioSet={scenarioSet}
              onScenarioSetChange={setScenarioSet}
              spreadScenarios={spreadScenarios}
              onSpreadScenariosChange={setSpreadScenarios}
              actionAttributionResult={actionAttributionQuery.data?.result ?? null}
              actionAttributionPending={
                actionAttributionQuery.isPending && !actionAttributionQuery.isError
              }
              actionAttributionError={actionAttributionErrorMessage}
              overviewModel={overviewModel}
              onOpenModuleDetail={openModuleDetail}
              onRefreshAnalytics={() => void handleBondAnalyticsRefresh()}
              isAnalyticsRefreshing={isBondAnalyticsRefreshing}
              analyticsRefreshError={bondAnalyticsRefreshError}
              lastAnalyticsRefreshRunId={lastBondAnalyticsRefreshRunId}
              calendarItems={calendarItems}
              calendarLoading={researchCalendarQuery.isPending}
              calendarError={researchCalendarQuery.isError}
            />
          </Suspense>
        </>
      )}

      <details
        data-testid="bond-analysis-detail-drilldown"
        className={`dashboard-detail-drilldown dashboard-progressive-disclosure ${styles.detailDrilldown}`}
        open={isDetailDrilldownOpen}
        onToggle={(event) => setIsDetailDrilldownOpen(event.currentTarget.open)}
      >
        <summary className={`dashboard-detail-drilldown__header dashboard-progressive-disclosure__summary ${styles.detailDrilldownSummary}`}>
          <div className="dashboard-home-section-heading">
            {/* 上方参数条眉标已用「复核入口」：连续两条横带不重复同名眉标（§6 去重）。 */}
            <span className="dashboard-home-section-eyebrow">进一步分析</span>
            <h2 className="dashboard-detail-drilldown__title">分析明细</h2>
          </div>
          <span className={`dashboard-progressive-disclosure__description ${styles.detailDrilldownDescription}`}>
            查看动作归因、收益拆解、信用利差和持仓明细。
          </span>
          <span className="dashboard-progressive-disclosure__cue">展开</span>
        </summary>

        <details className={styles.detailDrilldownDescription} data-testid="bond-analysis-page-diagnostics">
          <summary>技术诊断</summary>
          <p data-testid="bond-analysis-page-evidence">
            页面契约：<code>PAGE-BOND-ANALYSIS-001</code>；状态：<code>candidate</code>（待业主正式批准）。
          </p>
        </details>

        {canRenderAnalytics && isDetailDrilldownOpen ? (
          <Suspense
            fallback={
              <div className={styles.detailFallback} data-testid="bond-analysis-detail-loading">
                正在加载明细模块...
              </div>
            }
          >
            <div key={detailRemountKey}>
              <BondAnalyticsDetailSection
                activeTab={activeTab}
                onActiveTabChange={setActiveTab}
                reportDate={effectiveReportDate}
                periodType={periodType}
                assetClass={assetClass}
                accountingClass={accountingClass}
                scenarioSet={scenarioSet}
                spreadScenarios={spreadScenarios}
              />
            </div>
          </Suspense>
        ) : !canRenderAnalytics ? (
          <div className={styles.detailFallback} data-testid="bond-analysis-detail-loading">
            报告日确认后加载明细模块。
          </div>
        ) : null}
      </details>

      {agentPanelMounted ? (
        <Suspense fallback={null}>
          <LazyBondAnalyticsAgentDrawer
            open={agentPanelOpen}
            reportDate={effectiveReportDate}
            currentFilters={agentPanelFilters}
            onClose={() => setAgentPanelOpen(false)}
          />
        </Suspense>
      ) : null}
    </section>
  );

}

export default BondAnalyticsViewContent;
