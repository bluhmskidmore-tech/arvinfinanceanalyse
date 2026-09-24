import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useState } from "react";
import { Link } from "react-router-dom";

import { useApiClient } from "../../../api/clientContext";
import type { ApiEnvelope } from "../../../api/contracts";
import type { MacroToolkitAnalysisPayload } from "../../../api/macroToolkitClient";
import { formatObservationDeferredSectionLabel } from "../../macro-toolkit/lib/macroToolkitDataHealthSupport";
import {
  formatQueryError,
  isMacroToolkitReadForbidden,
} from "../../macro-toolkit/lib/macroToolkitDisplayFormat";
import {
  MACRO_TOOLKIT_CRISIS_SCORE_HISTORY_LIMIT,
  MACRO_TOOLKIT_FULL_ANALYSIS_QUERY_KEY,
} from "../../macro-toolkit/lib/macroToolkitPageModel";
import MacroObservationSectionLead from "../components/MacroObservationSectionLead";
import {
  buildAShareRiskView,
  buildCrisisEvidenceView,
  buildDataHealthView,
  buildEvidenceMetaView,
  buildObservationConclusion,
  buildObservationKpiBand,
  buildObservationSectionStates,
  buildObservationToolbarStatus,
  buildReportBundleView,
  buildSignalCardViews,
  buildStrategyEvidenceView,
  isCoreAnalysisScope,
  observationRuntimeSummary,
  pickCrisisScoreResult,
  pickDecisionSummaryResult,
  strategySupplyState,
  mergeStrategySummaries,
} from "../model/macroObservationPageModel";
import type { MacroObservationSectionState } from "../model/macroObservationPageModel";
import MacroObservationConclusionSection from "../sections/MacroObservationConclusionSection";
import MacroObservationCrisisSection from "../sections/MacroObservationCrisisSection";
import MacroObservationDataHealthSection from "../sections/MacroObservationDataHealthSection";
import MacroObservationEvidenceSection from "../sections/MacroObservationEvidenceSection";
import MacroObservationModelStrategySection from "../sections/MacroObservationModelStrategySection";
import MacroObservationSignalRiskSection from "../sections/MacroObservationSignalRiskSection";
import "./MacroObservationPage.css";

const MACRO_OBSERVATION_READ_STALE_MS = 60_000;

/**
 * /macro-observation 只读观察页（首页 Nocturne 标准骨架）。
 * 数据编排与 /macro-toolkit 共享 query key；首屏只请求 core + strategy，
 * 完整分析由「查看完整分析」显式触发，不预取 full。
 */
export default function MacroObservationPage() {
  const client = useApiClient();
  const queryClient = useQueryClient();
  const [fullAnalysisEnvelope, setFullAnalysisEnvelope] = useState<
    ApiEnvelope<MacroToolkitAnalysisPayload> | null
  >(
    () =>
      queryClient.getQueryData<ApiEnvelope<MacroToolkitAnalysisPayload>>(
        MACRO_TOOLKIT_FULL_ANALYSIS_QUERY_KEY,
      ) ?? null,
  );
  const [fullAnalysisError, setFullAnalysisError] = useState<string | null>(null);
  const [isLoadingFullAnalysis, setIsLoadingFullAnalysis] = useState(false);

  const analysisQuery = useQuery({
    queryKey: ["macro-toolkit", "analysis"],
    queryFn: () => client.getMacroToolkitAnalysis({ detail: "core" }),
    staleTime: MACRO_OBSERVATION_READ_STALE_MS,
  });

  const strategyQuery = useQuery({
    queryKey: ["macro-toolkit", "strategy-summaries"],
    queryFn: () => client.getMacroToolkitStrategySummaries(),
    staleTime: MACRO_OBSERVATION_READ_STALE_MS,
  });

  const fetchFullAnalysis = useCallback(
    () =>
      client.getMacroToolkitAnalysis({
        detail: "full",
        historyLimit: MACRO_TOOLKIT_CRISIS_SCORE_HISTORY_LIMIT,
      }),
    [client],
  );

  const loadFullAnalysis = useCallback(async () => {
    setIsLoadingFullAnalysis(true);
    setFullAnalysisError(null);
    try {
      const response = await queryClient.fetchQuery({
        queryKey: MACRO_TOOLKIT_FULL_ANALYSIS_QUERY_KEY,
        queryFn: fetchFullAnalysis,
        staleTime: MACRO_OBSERVATION_READ_STALE_MS,
      });
      setFullAnalysisEnvelope(response);
      return response;
    } catch (error) {
      setFullAnalysisError(formatQueryError(error));
      return null;
    } finally {
      setIsLoadingFullAnalysis(false);
    }
  }, [fetchFullAnalysis, queryClient]);

  const analysisEnvelope = fullAnalysisEnvelope ?? analysisQuery.data;
  const analysis = analysisEnvelope?.result;
  const analysisMeta = analysisEnvelope?.result_meta;
  const strategyPayload = strategyQuery.data?.result;
  const strategyMeta = strategyQuery.data?.result_meta;
  const isAnalysisLoading = analysisQuery.isLoading && !analysis;

  const isCore = isCoreAnalysisScope(analysis);
  const deferredRuntimeSections = analysis?.runtime_status?.deferred_sections ?? [];
  const runtimeSummary = analysis
    ? observationRuntimeSummary(isCore, deferredRuntimeSections.length)
    : "观察证据加载中";
  const showFullAnalysisAction = isCore && deferredRuntimeSections.length > 0;
  const supplyState = strategySupplyState(
    strategyQuery.isFetching,
    strategyQuery.isError,
    mergeStrategySummaries(strategyPayload, analysis).length > 0,
  );

  const toolbarStatus = buildObservationToolbarStatus(analysis, analysisMeta);
  const kpiItems = buildObservationKpiBand({
    analysis,
    strategyPayload,
    analysisLoading: isAnalysisLoading,
    strategySupply: supplyState,
  });
  const conclusion = buildObservationConclusion(analysis);
  const signalCards = buildSignalCardViews(analysis?.signal_cards ?? []);
  const riskView = buildAShareRiskView(analysis?.a_share_risk, analysis?.runtime_status?.analysis_scope);
  const strategyView = buildStrategyEvidenceView(strategyPayload, analysis);
  const crisisView = buildCrisisEvidenceView(
    pickCrisisScoreResult(analysis),
    analysis?.runtime_status?.analysis_scope,
  );
  const healthView = buildDataHealthView(analysis?.data_health);
  const metaView = buildEvidenceMetaView(analysisMeta, strategyMeta);
  const reportBundle = buildReportBundleView(analysis?.report_bundle);
  const sectionStates = buildObservationSectionStates({
    analysis,
    analysisLoading: isAnalysisLoading,
    analysisError: analysisQuery.isError,
    analysisMeta,
    strategyPayload,
    strategySupply: supplyState,
  });
  const conclusionLead: MacroObservationSectionState = isAnalysisLoading
    ? { state: "loading", note: "观察证据加载中" }
    : null;

  const observationFailedReadMessages = [
    analysisQuery.isError ? "读取核心分析失败" : "",
    strategyQuery.isError ? "读取策略摘要失败" : "",
  ].filter(Boolean);
  const hasReadScopeBlocker = [analysisQuery.error, strategyQuery.error]
    .filter(Boolean)
    .map(formatQueryError)
    .some(isMacroToolkitReadForbidden);
  const isRetrying = analysisQuery.isFetching || strategyQuery.isFetching;
  const retryReads = () => {
    void analysisQuery.refetch();
    void strategyQuery.refetch();
  };

  const header = (
    <header className="macro-observation-view__header">
      <div className="macro-observation-view__header-copy">
        <h1 className="macro-observation-view__title">宏观观察</h1>
        {/* 只读边界声明集中在页头徽标与下方细注一处；副题只答「本页看什么」。 */}
        <p className="macro-observation-view__subtitle">
          宏观信号、模型与策略证据的当日观察。
        </p>
      </div>
      <div className="macro-observation-view__header-side">
        <span className="macro-observation-view__mode-badge">只读观察</span>
        <Link className="macro-observation-view__toolkit-link" to="/macro-toolkit">
          前往宏观工具页
        </Link>
      </div>
    </header>
  );

  // Playwright dark-theme readySelector 与 liveRoute 契约锚点：三态都必须渲染。
  const readonlyBoundary = (
    <p
      className="macro-observation-view__readonly-boundary"
      data-testid="macro-observation-readonly-boundary"
    >
      只读宏观观察 · 本页只展示宏观分析证据；刷新、脚本执行和运营注册表保留在宏观工具页。
    </p>
  );

  if (!analysis && analysisQuery.isError) {
    return (
      <section
        className="macro-observation-view theme-dh-api"
        data-testid="macro-observation-page"
        data-moss-theme-scope="macro-toolkit"
      >
        {header}
        {readonlyBoundary}
        <div
          className="macro-observation-view__error-state"
          data-testid="macro-observation-error-state"
          role="alert"
        >
          <h2>宏观观察暂不可用</h2>
          <p>核心分析暂时没有返回；请稍后重试或打开宏观工具页查看诊断。</p>
          {hasReadScopeBlocker ? (
            <p className="macro-observation-view__error-permission">
              缺少宏观工具读取权限 macro_toolkit/read；当前账号未被允许读取宏观工具，授权后点击重试读取。
            </p>
          ) : null}
          <div className="macro-observation-view__error-sources" aria-label="宏观观察读取状态">
            <span>读取状态</span>
            {observationFailedReadMessages.length ? (
              observationFailedReadMessages.map((message, index) => (
                <small key={`${message}-${index}`}>{message}</small>
              ))
            ) : (
              <small>宏观观察暂时没有可展示数据。</small>
            )}
          </div>
          <div className="macro-observation-view__error-actions">
            <button type="button" onClick={retryReads} disabled={isRetrying}>
              重试读取
            </button>
            <Link className="macro-observation-view__toolkit-link" to="/macro-toolkit">
              前往宏观工具页
            </Link>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section
      className="macro-observation-view theme-dh-api"
      data-testid="macro-observation-page"
      data-moss-theme-scope="macro-toolkit"
    >
      {header}

      <div className="macro-observation-view__toolbar" data-testid="macro-observation-toolbar">
        <div className="macro-observation-view__status-chips" aria-label="宏观观察状态">
          {toolbarStatus.map((item) => (
            <span key={item.key} className="macro-observation-view__status-chip">
              <span className="macro-observation-view__filters-label">{item.label}</span>
              <strong className="macro-observation-view__status-chip-value">{item.value}</strong>
              {item.note ? (
                <small className="macro-observation-view__filters-note">{item.note}</small>
              ) : null}
            </span>
          ))}
        </div>
        {showFullAnalysisAction ? (
          <div className="macro-observation-view__toolbar-actions">
            <button
              type="button"
              className="macro-observation-view__full-analysis-button"
              disabled={isLoadingFullAnalysis}
              onClick={() => void loadFullAnalysis()}
            >
              {isLoadingFullAnalysis ? "读取完整分析…" : "查看完整分析"}
            </button>
          </div>
        ) : null}
      </div>

      {readonlyBoundary}

      {isAnalysisLoading ? (
        <p
          className="macro-observation-view__loading-note"
          data-testid="macro-observation-loading-note"
        >
          核心分析加载中：页面口径边界已就绪；观察结论和证据对照会在后端返回后自动补上。
        </p>
      ) : null}
      {analysis && analysisQuery.isError ? (
        <p className="macro-observation-view__refresh-error" role="alert">
          宏观分析结果加载失败
        </p>
      ) : null}
      {fullAnalysisError ? (
        <p className="macro-observation-view__refresh-error" role="alert">
          完整分析加载失败：{fullAnalysisError}
        </p>
      ) : null}

      <section id="mo-section-01" className="macro-observation-view__section">
        <MacroObservationSectionLead title="当日观察结论" state={conclusionLead} />
        <MacroObservationConclusionSection
          kpiItems={kpiItems}
          conclusion={conclusion}
          decisionResult={pickDecisionSummaryResult(analysis)}
          isCoreAnalysis={isCore}
          analysisBasis={analysisMeta?.basis ?? null}
        />
      </section>

      <section id="mo-section-02" className="macro-observation-view__section">
        <MacroObservationSectionLead title="信号与风险对照" state={sectionStates.signalRisk} />
        <MacroObservationSignalRiskSection signalCards={signalCards} risk={riskView} />
      </section>

      <section id="mo-section-03" className="macro-observation-view__section">
        <MacroObservationSectionLead title="模型与策略证据" state={sectionStates.modelStrategy} />
        <MacroObservationModelStrategySection
          modelReadiness={analysis?.model_readiness ?? []}
          hasonStrategy={analysis?.hason_strategy ?? null}
          strategy={strategyView}
        />
      </section>

      <section id="mo-section-04" className="macro-observation-view__section">
        <MacroObservationSectionLead title="危机分证据" state={sectionStates.crisis} />
        <MacroObservationCrisisSection crisis={crisisView} />
      </section>

      <section id="mo-section-05" className="macro-observation-view__section">
        <MacroObservationSectionLead title="数据健康与修复项" state={sectionStates.dataHealth} />
        <MacroObservationDataHealthSection health={healthView} />
      </section>

      <section id="mo-section-06" className="macro-observation-view__section">
        <MacroObservationSectionLead title="证据与口径" state={sectionStates.evidence} />
        <MacroObservationEvidenceSection
          metaView={metaView}
          analysisMeta={analysisMeta}
          strategyMeta={strategyMeta}
          reportBundle={reportBundle}
          runtimeSummary={runtimeSummary}
          deferredSectionLabels={deferredRuntimeSections.map((section) =>
            formatObservationDeferredSectionLabel(section.label ?? section.key),
          )}
        />
      </section>
    </section>
  );
}
