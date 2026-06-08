import { Suspense, lazy, useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";

import type { ApiEnvelope, Numeric, ResultMeta } from "../../../api/contracts";
import { useApiClient } from "../../../api/client";
import { runPollingTask } from "../../../app/jobs/polling";
import { DataQualityBanner } from "../../../components/page/DataQualityBanner";
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
import { classifyWarningSignals } from "../lib/bondAnalyticsModuleReadiness";
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

type BondDecisionTrustState = "loading" | "ok" | "warning" | "blocked";

interface BondAnalyticsDecisionCockpitProps {
  reportDate: string;
  periodType: PeriodType;
  clientMode: "mock" | "real";
  result: ActionAttributionResponse | null;
  resultMeta: ResultMeta | null | undefined;
  errorMessage: string | null;
  isFetching: boolean;
  topAnomalies: string[];
  onOpenActionAttribution: () => void;
}

const BOND_ANALYTICS_CURRENCY_BASIS_TEXT =
  "金额指标按人民币/CNY口径展示，外币债券金额已折算为人民币。";

function formatDecisionNumeric(value: Numeric | null | undefined): string {
  return value?.display ?? "—";
}

function formatDecisionBasis(meta: ResultMeta | null | undefined): string {
  if (!meta) return "证据加载中";
  if (meta.basis === "formal" && meta.formal_use_allowed) return "正式口径";
  if (meta.basis === "formal") return "正式口径待放行";
  if (meta.basis === "analytical") return "分析口径";
  if (meta.basis === "scenario") return "情景口径";
  if (meta.basis === "mock") return "演示口径";
  return "非正式口径";
}

function deriveDecisionTrustState({
  clientMode,
  errorMessage,
  isFetching,
  resultMeta,
  warningCount,
}: {
  clientMode: "mock" | "real";
  errorMessage: string | null;
  isFetching: boolean;
  resultMeta: ResultMeta | null | undefined;
  warningCount: number;
}): BondDecisionTrustState {
  if (errorMessage || resultMeta?.quality_flag === "error" || resultMeta?.quality_flag === "missing") {
    return "blocked";
  }
  if (isFetching && !resultMeta) {
    return "loading";
  }
  if (
    clientMode !== "real" ||
    resultMeta?.formal_use_allowed === false ||
    resultMeta?.basis !== "formal" ||
    resultMeta?.quality_flag === "warning" ||
    resultMeta?.quality_flag === "stale" ||
    resultMeta?.fallback_mode !== "none" ||
    resultMeta?.vendor_status !== "ok" ||
    warningCount > 0
  ) {
    return "warning";
  }
  return "ok";
}

function labelDecisionTrustState(state: BondDecisionTrustState): string {
  if (state === "ok") return "可用于复核";
  if (state === "warning") return "需带条件复核";
  if (state === "blocked") return "归因证据受阻";
  return "证据加载中";
}

function BondAnalyticsDecisionCockpit({
  reportDate,
  periodType,
  clientMode,
  result,
  resultMeta,
  errorMessage,
  isFetching,
  topAnomalies,
  onOpenActionAttribution,
}: BondAnalyticsDecisionCockpitProps) {
  if (!reportDate) {
    return null;
  }

  const warningCount = result?.warnings.length ?? (errorMessage ? 1 : 0);
  const trustState = deriveDecisionTrustState({
    clientMode,
    errorMessage,
    isFetching,
    resultMeta,
    warningCount,
  });
  const pnlDisplay = formatDecisionNumeric(result?.total_pnl_from_actions);
  const durationDisplay = formatDecisionNumeric(result?.duration_change_from_actions);
  const startDv01Display = formatDecisionNumeric(result?.period_start_dv01);
  const endDv01Display = formatDecisionNumeric(result?.period_end_dv01);
  const hasMetricEvidence = [
    result?.total_pnl_from_actions,
    result?.duration_change_from_actions,
    result?.period_start_dv01,
    result?.period_end_dv01,
  ].some((value) => value?.raw !== null && value?.raw !== undefined);
  const dv01Display =
    result?.period_start_dv01 || result?.period_end_dv01
      ? `${startDv01Display} -> ${endDv01Display}`
      : "—";
  const warningDetail =
    errorMessage ?? result?.warnings[0] ?? topAnomalies[0] ?? "未发现需要提前阻断的动作归因告警";
  const primaryConclusion = errorMessage
    ? `动作归因证据不可用：${errorMessage}`
    : isFetching && !result
      ? "正在装载动作归因、久期与 DV01 证据。"
      : result && !hasMetricEvidence
        ? `动作归因已返回，但 PnL、久期与 DV01 当前为空；需先复核 ${warningDetail}。`
      : `动作归因贡献 ${pnlDisplay}，久期变动 ${durationDisplay}，DV01 ${dv01Display}。`;
  const sourceDetail = [
    `报告日 ${result?.report_date ?? reportDate}`,
    periodType,
    clientMode === "real" ? "管理视角" : "演示视角",
    formatDecisionBasis(resultMeta),
  ].join(" / ");
  const nextActionLabel =
    trustState === "blocked"
      ? "打开归因错误复核"
      : trustState === "ok"
        ? "进入动作归因明细"
        : "打开动作归因复核";

  return (
    <section
      data-testid="bond-analysis-decision-cockpit"
      className={styles.decisionCockpit}
      aria-label="债券持仓首屏决策"
    >
      <div className={styles.decisionHeader}>
        <div className={styles.decisionCopy}>
          <span className={styles.decisionEyebrow}>FI RISK DECISION</span>
          <p
            data-testid="bond-analysis-decision-primary"
            className={styles.decisionPrimary}
          >
            {primaryConclusion}
          </p>
          <span
            data-testid="bond-analysis-decision-source"
            className={styles.decisionSource}
          >
            {sourceDetail}
          </span>
        </div>
        <span
          data-testid="bond-analysis-decision-trust"
          className={styles.decisionTrust}
          data-state={trustState}
        >
          {labelDecisionTrustState(trustState)}
        </span>
      </div>

      <div className={styles.decisionBody}>
        <div className={styles.decisionMetrics}>
          <div className={styles.decisionMetric}>
            <span className={styles.decisionMetricLabel}>动作 PnL（人民币/CNY）</span>
            <strong
              data-testid="bond-analysis-decision-pnl"
              className={styles.decisionMetricValue}
            >
              {pnlDisplay}
            </strong>
          </div>
          <div className={styles.decisionMetric}>
            <span className={styles.decisionMetricLabel}>久期动作</span>
            <strong
              data-testid="bond-analysis-decision-duration"
              className={styles.decisionMetricValue}
            >
              {durationDisplay}
            </strong>
          </div>
          <div className={styles.decisionMetric}>
            <span className={styles.decisionMetricLabel}>DV01 起止</span>
            <strong
              data-testid="bond-analysis-decision-dv01"
              className={styles.decisionMetricValue}
            >
              {dv01Display}
            </strong>
          </div>
          <div className={styles.decisionMetric}>
            <span className={styles.decisionMetricLabel}>告警</span>
            <strong
              data-testid="bond-analysis-decision-warning"
              className={styles.decisionMetricValue}
            >
              {warningCount}
            </strong>
          </div>
        </div>

        <div className={styles.decisionAction}>
          <div
            data-testid="bond-analysis-currency-basis-note"
            className={styles.decisionBasisNote}
          >
            {BOND_ANALYTICS_CURRENCY_BASIS_TEXT}
          </div>
          <span className={styles.decisionWarning} title={warningDetail}>
            {warningDetail}
          </span>
          <button
            type="button"
            data-testid="bond-analysis-decision-next-action"
            className={styles.decisionNextButton}
            onClick={onOpenActionAttribution}
          >
            {nextActionLabel}
          </button>
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

  const actionAttributionResult = actionAttributionQuery.data?.result ?? null;
  const actionAttributionResultMeta: ResultMeta | null | undefined =
    actionAttributionQuery.data?.result_meta;
  const dataQualityWarningSignals = useMemo(
    () => classifyWarningSignals(actionAttributionResult?.warnings ?? []),
    [actionAttributionResult],
  );

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

  if (showDatesErrorState) {
    return (
      <section className={styles.stateCard}>
        <div className={styles.stateTitle}>债券分析日期载入失败。</div>
        <div className={styles.stateBody}>
          无法确定可用报告日，当前不启动债券分析默认首屏查询。请重试或通过地址栏报告日参数显式传入。
        </div>
        <button
          type="button"
          onClick={() => void datesQuery.refetch()}
          className="dashboard-home-action-button dashboard-home-action-button--secondary"
        >
          重试日期载入
        </button>
      </section>
    );
  }

  if (datesEmpty && !effectiveReportDate) {
    return (
      <section className={styles.stateCard}>
        <div className={styles.stateTitle}>债券分析暂无可用报告日。</div>
        <div className={styles.stateBody}>
          后端尚未返回可消费的债券分析报告日，因此默认首屏保持等待状态，不在前端自行推导日期。
        </div>
        <button
          type="button"
          onClick={() => void datesQuery.refetch()}
          className="dashboard-home-action-button dashboard-home-action-button--secondary"
        >
          重试日期载入
        </button>
      </section>
    );
  }

  return (
    <section data-testid="bond-analysis-overview" className="dashboard-home-shell">
      <header data-testid="bond-analysis-toolbar" className="dashboard-home-toolbar">
        <div className="dashboard-home-toolbar__identity">
          <h1 className="dashboard-home-toolbar__title">债券持仓</h1>
          <span className="dashboard-home-toolbar__eyebrow">
            报告日 {effectiveReportDate || "最新可用"}
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
            >
              {dateOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
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
            disabled={isBondAnalyticsRefreshing || !effectiveReportDate}
            className={
              isBondAnalyticsRefreshing || !effectiveReportDate
                ? `dashboard-home-action-button dashboard-home-action-button--disabled ${styles.refreshButton}`
                : `dashboard-home-action-button dashboard-home-action-button--primary ${styles.refreshButton}`
            }
          >
            {isBondAnalyticsRefreshing ? "刷新中" : "刷新"}
          </button>
        </div>
      </header>

      <BondAnalyticsDecisionCockpit
        reportDate={effectiveReportDate}
        periodType={periodType}
        clientMode={client.mode}
        result={actionAttributionResult}
        resultMeta={actionAttributionResultMeta}
        errorMessage={actionAttributionErrorMessage}
        isFetching={actionAttributionQuery.isFetching}
        topAnomalies={overviewModel.topAnomalies}
        onOpenActionAttribution={() => openModuleDetail("action-attribution")}
      />

      <DataQualityBanner
        resultMeta={actionAttributionResultMeta}
        warnings={
          dataQualityWarningSignals.hasPlaceholderSignals
            ? ["部分模块数据为占位值，尚未填充真实计算结果"]
            : dataQualityWarningSignals.hasPartialSignals
              ? ["部分指标因输入不可用暂设为零"]
              : []
        }
      />

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
      </details>
    </section>
  );
}

export default BondAnalyticsViewContent;
