import { Suspense, lazy, useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";

import type { ApiEnvelope } from "../../../api/contracts";
import { useApiClient } from "../../../api/client";
import { runPollingTask } from "../../../app/jobs/polling";
import { mapResearchCalendarEventToCalendarItem } from "../../../lib/researchCalendarToCalendarItem";
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
      ? "无法确定可用报告日，当前不启动债券分析默认查询。请重试或通过地址栏 report_date 参数显式传入。"
      : "后端尚未返回可消费的债券分析报告日，因此默认首屏保持等待状态，不在前端自行推导日期。";

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
              <strong>—</strong>
              <small>待读取</small>
            </div>
          ),
        )}
      </div>

      <div className={styles.fallbackJudgment} data-testid="bond-analysis-daily-judgment">
        <div className={styles.fallbackSectionTitle}>核心读面</div>
        <p>报告日未解析前，仅保留利率、曲线、信用和资金读面状态，不展示方向性结论。</p>
      </div>

      <div className={styles.fallbackGrid}>
        <div className={styles.fallbackPanel} data-testid="bond-analysis-yield-curve-panel">
          <span>收益率曲线与日变动</span>
          <strong>待报告日确认</strong>
        </div>
        <div className={styles.fallbackPanel} data-testid="bond-analysis-return-attribution-panel">
          <span>收益归因</span>
          <strong>待动作归因读链路返回</strong>
        </div>
        <div className={styles.fallbackPanel} data-testid="bond-analysis-risk-monitor">
          <span>风险监控</span>
          <strong>待 DV01 / 久期读面返回</strong>
        </div>
      </div>
    </section>
  );
}

export function BondAnalyticsViewContent() {
  const client = useApiClient();
  const queryClient = useQueryClient();

  useEffect(() => {
    void import("./BondAnalyticsOverviewPanels");
    void import("./BondAnalyticsDetailSection");
  }, []);

  const [searchParams] = useSearchParams();
  const explicitReportDate = searchParams.get("report_date")?.trim() || "";
  const datesQuery = useQuery({
    queryKey: [...bondAnalyticsQueryKeyRoot, "dates", client.mode],
    queryFn: () => client.getBondAnalyticsDates(),
    retry: false,
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
  const [detailRemountKey, setDetailRemountKey] = useState(0);
  const [isDetailDrilldownOpen, setIsDetailDrilldownOpen] = useState(false);

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
    retry: false,
  });

  const actionAttributionErrorMessage =
    actionAttributionQuery.error instanceof Error
      ? actionAttributionQuery.error.message
      : null;

  async function handleBondAnalyticsRefresh() {
    if (!effectiveReportDate) {
      return;
    }
    setIsBondAnalyticsRefreshing(true);
    setBondAnalyticsRefreshError(null);
    try {
      const payload = await runPollingTask({
        start: () => client.refreshBondAnalytics(effectiveReportDate),
        getStatus: (runId) => client.getBondAnalyticsRefreshStatus(runId),
        onUpdate: (nextPayload) => {
          if (nextPayload.run_id) {
            setLastBondAnalyticsRefreshRunId(nextPayload.run_id);
          }
        },
      });
      if (payload.status !== "completed") {
        const hint =
          typeof payload.error_message === "string" && payload.error_message.trim()
            ? payload.error_message
            : `债券分析刷新未完成：${payload.status}`;
        const rid = payload.run_id ? ` run_id: ${payload.run_id}` : "";
        throw new Error(`${hint}${rid}`);
      }
      await queryClient.invalidateQueries({ queryKey: [...bondAnalyticsQueryKeyRoot] });
      setDetailRemountKey((key) => key + 1);
    } catch (error: unknown) {
      setBondAnalyticsRefreshError(
        error instanceof Error ? error.message : "刷新债券分析失败",
      );
    } finally {
      setIsBondAnalyticsRefreshing(false);
    }
  }

  const overviewModel = buildBondAnalyticsOverviewModel({
    reportDate: effectiveReportDate,
    periodType,
    activeModuleKey: activeTab,
    actionAttributionEnvelope: actionAttributionQuery.data ?? null,
    actionAttributionLoading: actionAttributionQuery.isFetching,
    actionAttributionError: actionAttributionErrorMessage,
  });

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

  const toolbarModeLabel = client.mode === "real" ? "管理视角" : "演示视角";

  const dateFallbackKind: BondAnalyticsDateFallbackKind | null = showDatesErrorState
    ? "error"
    : datesEmpty && !effectiveReportDate
      ? "empty"
      : null;
  const canRenderAnalytics = Boolean(effectiveReportDate) && !dateFallbackKind;

  return (
    <section data-testid="bond-analysis-overview" className="dashboard-home-shell">
      <header data-testid="bond-analysis-toolbar" className="dashboard-home-toolbar">
        <div className="dashboard-home-toolbar__identity">
          <h1 className="dashboard-home-toolbar__title">债券分析</h1>
          <span className="dashboard-home-toolbar__eyebrow">
            报告日 {effectiveReportDate || "待确认"}
          </span>
        </div>
        <div className="dashboard-home-actions">
          <span
            className={
              client.mode === "real"
                ? "dashboard-home-view-pill dashboard-governance-tone-ok"
                : "dashboard-home-view-pill dashboard-governance-tone-warning"
            }
          >
            {toolbarModeLabel}
          </span>
          <label className="dashboard-home-control">
            <span>报告日</span>
            <select
              aria-label="报告日"
              className={`${styles.toolbarSelect} ${styles.toolbarSelectWide}`}
              value={effectiveReportDate}
              onChange={(event) => setReportDate(event.target.value)}
              disabled={dateOptions.length === 0}
            >
              {dateOptions.length > 0 ? (
                dateOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))
              ) : (
                <option value="">待确认</option>
              )}
            </select>
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
          <Link
            to="/source-preview"
            className="dashboard-home-action-button dashboard-home-action-button--secondary"
          >
            报表中心
          </Link>
          <Link
            to="/platform-config"
            className="dashboard-home-action-button dashboard-home-action-button--secondary"
          >
            中台配置
          </Link>
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
              overviewModel={overviewModel}
              onOpenModuleDetail={openModuleDetail}
              onRefreshAnalytics={() => void handleBondAnalyticsRefresh()}
              isAnalyticsRefreshing={isBondAnalyticsRefreshing}
              analyticsRefreshError={bondAnalyticsRefreshError}
              lastAnalyticsRefreshRunId={lastBondAnalyticsRefreshRunId}
              calendarItems={calendarItems}
            />
          </Suspense>
        </>
      )}

      <details
        data-testid="bond-analysis-detail-drilldown"
        className="dashboard-detail-drilldown dashboard-progressive-disclosure"
        open={isDetailDrilldownOpen}
        onToggle={(event) => setIsDetailDrilldownOpen(event.currentTarget.open)}
      >
        <summary className="dashboard-detail-drilldown__header dashboard-progressive-disclosure__summary">
          <div className="dashboard-home-section-heading">
            <span className="dashboard-home-section-eyebrow">下钻复核区</span>
            <h2 className="dashboard-detail-drilldown__title">分析明细</h2>
          </div>
          <span className="dashboard-progressive-disclosure__description">
            展开后查看动作归因、收益拆解、信用利差、重仓券和组合头条。
          </span>
          <span className="dashboard-progressive-disclosure__cue">展开</span>
        </summary>

        {canRenderAnalytics ? (
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
        ) : (
          <div className={styles.detailFallback} data-testid="bond-analysis-detail-loading">
            报告日确认后加载明细模块。
          </div>
        )}
      </details>
    </section>
  );

}

export default BondAnalyticsViewContent;
