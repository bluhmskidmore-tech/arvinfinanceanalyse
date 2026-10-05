import { useRiskTensorDiagnostics } from "./useRiskTensorDiagnostics";
import { useRiskTensorQualityEvidence } from "./useRiskTensorQualityEvidence";
import { useRiskTensorQueries } from "./useRiskTensorQueries";
import { useRiskTensorCharts } from "./useRiskTensorCharts";

import InteractiveEChart from "../../lib/echarts";
import { ChartCard } from "../../components/charts/ChartCard";
import { CHART_CARD_HEIGHTS } from "../../components/charts/chartCardScale";

import { FormalResultMetaPanel } from "../../components/page/FormalResultMetaPanel";
import { PageAsyncSection } from "../../components/page/PageAsyncSection";

import { KpiCard } from "../../components/KpiCard";
import { SectionHead } from "../../components/layout";

import { toneFromSignedDisplayString } from "../workbench/components/kpiFormat";

import { EM_DASH } from "../../utils/format";
import {
  durationExclusionTone,
  liquidityGapLabel,
  liquidityGapTone,
  projectionQualityTone,
} from "./riskTensorPageModel";
import "./RiskTensorPage.css";
import {
  describeRiskTensorWarning,
  qualityFlagLabel,
  qualityTone,
  formatTimestampDisplay,
  compactVersion,
  riskTensorErrorMessage,
} from "./riskTensorPresentation";
import {
  WAN_YUAN_UNIT,
  YI_YUAN_UNIT,
  displayStr,
  amountUnit,
  yuanAsWanDisplay,
  yuanAsYiDisplay,
  yuanAsWanWithUnit,
  yuanAsYiWithUnit,
  ratioPercentDisplay,
  ratioTone,
  countDisplay,
  projectionQualityStatusLabel,
  projectionQualityAmountDisplay,
  projectionQualityAmountUnit,
  projectionQualityCountDisplay,
  excludedLiabilityCountDisplay,
  regulatoryDv01Display,
  regulatoryDv01DisplayWithUnit,
  regulatoryDv01Tone,
} from "./riskTensorDisplay";
import { PROJECTION_QUALITY_FIELDS, riskTensorScalarIssue } from "./riskTensorQuality";
import { scrollRiskTensorTargetIntoView } from "./riskTensorNavigation";
import { RiskScenarioStressPanel } from "./RiskScenarioStressPanel";

export default function RiskTensorPage() {
  const queries = useRiskTensorQueries();
  const {
    setSearchParams,
    datesQuery,
    blockedReportDates,
    selectedBlockedReportDate,
    highlightedBlockedReportDate,
    latestAvailableReportDate,
    reportDate,
    reportDateOptions,
    datesBlockingError,
    datesEmpty,
    tensorBlockedByReportDate,
    tensorQueryEnabled,
    tensorQuery,
    scenarioStressQuery,
    envelope,
    result,
    isEmpty,
    tensorErrorStatusCode,
    datesErrorStatusCode,
    tensorErrorReportDate,
    datesGovernanceMeta,
    datesEmptyTraceId,
    handleUseLatestAvailableReportDate,
  } = queries;
  const {
    selectedTenor,
    krdChartOption,
    tenorRows,
    invalidKrdRows,
    invalidRadarRows,
    issuerConcentrationIssue,
    liquidityGapRatioIssue,
    durationRadarIssue,
    kpiRadarIssues,
    dominantTenorRow,
    selectedTenorRow,
    showDurationScope,
    radarNavigationItems,
    handlePrimaryTenorDrill,
    handleKrdTenorSelect,
    handleKrdChartClick,
    radarChartOption,
  } = useRiskTensorCharts(result);
  const tensorMeta = envelope?.result_meta;
  const evidence = useRiskTensorQualityEvidence({ result, tensorMeta, reportDate, blockedReportDates, highlightedBlockedReportDate });
  const {
    fallbackStatus,
    blockedReportDateSummary,
    metadataTablesUsed,
    metadataFiltersApplied,
    qualityReviewReasonSummary,
    qualityTraceFallbackDetail,
    qualityTraceBlockedDetail,
    qualityTraceWarningDetail,
    qualityTraceMetadataDetail,
    payloadQualityIssues,
    durationCoverageQualityIssues,
    payloadQualityIssueSummary,
    qualityStateKey,
    qualityEvidenceReviewItems,
    hasMissingQualityEvidence,
    missingQualityEvidenceLabels,
    qualityTraceCopyText,
    qualityEvidenceRequestCopyText,
    payloadQualityRequestCopyText,
    combinedQualityRequestCopyText,
    qualityWarningsCopyText,
    qualityEvidenceReviewRecordCopyText,
    qualityEvidenceReviewConfirmed,
    qualityEvidenceReviewRecordCopiedStateKey,
    qualityEvidenceReviewRecordCopyStatus,
    qualityWarningsCopiedStateKey,
    qualityWarningsCopyStatus,
    qualityEvidenceCopyStatusForCurrentState,
    canConfirmQualityEvidenceReview,
    qualityReviewStateLabel,
    qualityEvidenceCopyMessage,
    qualityEvidenceRequestCopyStatusForCurrentState,
    qualityEvidenceRequestCopyMessage,
    qualityEvidenceReviewRecordCopyMessage,
    payloadQualityRequestCopyStatusForCurrentState,
    payloadQualityRequestCopyMessage,
    combinedQualityRequestCopyStatusForCurrentState,
    combinedQualityRequestCopyMessage,
    qualityWarningsCopyMessage,
    handleCopyQualityEvidence,
    handleCopyQualityEvidenceRequest,
    handleCopyPayloadQualityRequest,
    handleCopyCombinedQualityRequest,
    handleCopyQualityWarnings,
    handleConfirmQualityEvidenceReview,
    handleCopyQualityEvidenceReviewRecord,
  } = evidence;
  const {
    tensorErrorCopyText,
    tensorErrorCopyStatusForCurrentState,
    tensorErrorCopyMessage,
    blockedDateCopyText,
    blockedDateCopyStatusForCurrentState,
    blockedDateCopyMessage,
    datesErrorCopyText,
    datesErrorCopyStatusForCurrentState,
    datesErrorCopyMessage,
    datesEmptyCopyText,
    datesEmptyCopyStatusForCurrentState,
    datesEmptyCopyMessage,
    emptyPositionCopyText,
    emptyPositionCopyStatusForCurrentState,
    emptyPositionCopyMessage,
    handleCopyTensorError,
    handleCopyBlockedDate,
    handleRetryDatesGovernance,
    handleRetryTensorMainRead,
    handleCopyDatesError,
    handleCopyDatesEmpty,
    handleCopyEmptyPosition,
  } = useRiskTensorDiagnostics(queries, evidence);
  const primaryTenor = dominantTenorRow?.tenor ?? EM_DASH;
  const primaryTenorValue = dominantTenorRow ? yuanAsWanWithUnit(dominantTenorRow.value) : EM_DASH;
  const liquidity30dValue = result?.liquidity_gap_30d;
  const actionTileRawWarning = result?.warnings[0];
  const actionTileDetail =
    actionTileRawWarning ? describeRiskTensorWarning(actionTileRawWarning) : "暂无待补信息，可继续查看压力情景。";
  const actionTileDetailEvidence =
    actionTileRawWarning && actionTileDetail !== actionTileRawWarning ? actionTileRawWarning : undefined;
  const actionTileCanJump = Boolean(result?.warnings.length);
  const actionTileTone = (result?.warnings.length ?? 0) > 0 ? "warning" : "ok";
  const actionTileSummary = result?.warnings.length ? `${result.warnings.length} 条需核对` : "暂无待补项";
  const topLineSummary = result
    ? [
        `主风险桶 ${primaryTenor}`,
        liquidityGapLabel(liquidity30dValue),
        `质量标记：${qualityFlagLabel(result.quality_flag)}`,
      ].join(" / ")
    : "";
  const conclusionNeedsQualityReview = result?.quality_flag === "stale" || result?.quality_flag === "error";

  const handleQualityDetailJump = () => {
    scrollRiskTensorTargetIntoView(
      document.querySelector<HTMLElement>('[data-testid="risk-tensor-quality-detail"]'),
    );
  };

  const handleLiquidityDetailJump = () => {
    scrollRiskTensorTargetIntoView(
      document.querySelector<HTMLElement>('[data-testid="risk-tensor-liquidity-gap-detail"]'),
    );
  };

  const handleIssuerConcentrationJump = () => {
    scrollRiskTensorTargetIntoView(
      document.querySelector<HTMLElement>('[data-testid="risk-tensor-issuer-concentration-detail"]'),
    );
  };

  const handlePayloadChecklistJump = () => {
    const target =
      document.querySelector<HTMLElement>('[data-testid="risk-tensor-quality-payload-checklist"]') ??
      document.querySelector<HTMLElement>('[data-testid="risk-tensor-quality-detail"]');
    scrollRiskTensorTargetIntoView(target);
  };

  const handleSectionJump = (targetTestId: string) => {
    scrollRiskTensorTargetIntoView(document.querySelector<HTMLElement>(`[data-testid="${targetTestId}"]`));
  };

  const handleRequiredInformationJump = () => {
    if (!result?.warnings.length) {
      return;
    }
    handleQualityDetailJump();
  };

  const krdQualityNote =
    invalidKrdRows.length > 0 ? (
      <div className="risk-tensor-tenor-drill__quality" data-testid="risk-tensor-krd-quality-note">
        {invalidKrdRows.map((row) => `${row.key} ${riskTensorScalarIssue(row.value) ?? "不可解析"}`).join(" / ")}
        ；未参与前端主风险桶排序和图表数值。
        <button type="button" className="risk-tensor-brief__link-button" onClick={handlePayloadChecklistJump}>
          查看字段复核
        </button>
        <button type="button" className="risk-tensor-brief__link-button" onClick={handleRetryTensorMainRead}>
          重试主读面
        </button>
      </div>
    ) : null;

  const mainReadBlocked = tensorBlockedByReportDate || tensorQuery.isError || datesBlockingError;

  return (
    <section
      className="risk-tensor-page theme-dh-api"
      data-moss-theme-scope="risk-tensor"
      data-testid="risk-tensor-page"
      data-read-state={mainReadBlocked ? "blocked" : undefined}
    >
      <div className="risk-tensor-page__hero">
        <h1>风险张量</h1>
        <p>
          查看利率敏感度、流动性缺口与风险集中情况。
        </p>
      </div>

      <div className="risk-tensor-control-bar">
        {reportDateOptions.length > 0 ? (
          <label className="risk-tensor-report-date-select">
            <span>风险报告日</span>
            <select
              value={reportDate}
              onChange={(event) => {
                const nextReportDate = event.target.value;
                setSearchParams((previous) => {
                  const next = new URLSearchParams(previous);
                  next.set("report_date", nextReportDate);
                  return next;
                });
              }}
            >
              {reportDateOptions.map((dateValue) => (
                <option key={dateValue} value={dateValue}>
                  {dateValue}
                </option>
              ))}
            </select>
          </label>
        ) : null}
        <div className="risk-tensor-report-date-status">
          {datesEmpty ? (
            <span>后端未返回可用风险报告日。</span>
          ) : datesBlockingError ? (
            <span>风险报告日载入失败。</span>
          ) : null}
          {highlightedBlockedReportDate ? (
            <>
              <br />
              <span data-testid="risk-tensor-blocked-dates">
                后端拦截陈旧日期：{blockedReportDates.length} 个。当前提示日期：{" "}
                <strong>{highlightedBlockedReportDate.report_date}</strong>
                {highlightedBlockedReportDate.reason
                  ? ` (${highlightedBlockedReportDate.reason})`
                  : null}
                {selectedBlockedReportDate
                  ? " 当前选择的报告日已被新鲜度校验拦截。"
                  : null}
              </span>
            </>
          ) : null}
        </div>
      </div>

      {selectedBlockedReportDate ? (
        <div className="risk-tensor-error-context" data-testid="risk-tensor-error-context">
          <strong>风险报告日已被新鲜度校验拦截</strong>
          <span>
            报告日 {selectedBlockedReportDate.report_date}；原因{" "}
            {selectedBlockedReportDate.reason || "后端未返回原因"}。trace_id{" "}
            {datesQuery.data?.result_meta.trace_id ?? EM_DASH}。主读面未读取；请切换到可用报告日。
          </span>
          <div className="risk-tensor-quality-detail__trace-actions">
            <button
              type="button"
              className="risk-tensor-quality-detail__trace-action"
              onClick={() => handleSectionJump("risk-tensor-result-meta-panel")}
            >
              定位元数据
            </button>
            <button type="button" className="risk-tensor-quality-detail__trace-action" onClick={handleCopyBlockedDate}>
              复制拦截信息
            </button>
            <button
              type="button"
              className="risk-tensor-quality-detail__trace-action"
              onClick={handleRetryDatesGovernance}
            >
              重试日期治理
            </button>
            {latestAvailableReportDate ? (
              <button
                type="button"
                className="risk-tensor-quality-detail__trace-action"
                onClick={handleUseLatestAvailableReportDate}
              >
                切换到最新可用报告日
              </button>
            ) : null}
          </div>
          {blockedDateCopyMessage ? (
            <small className="risk-tensor-quality-detail__trace-feedback" aria-live="polite">
              {blockedDateCopyMessage}
            </small>
          ) : null}
          {blockedDateCopyStatusForCurrentState === "failed" ? (
            <pre
              className="risk-tensor-quality-detail__manual-copy"
              data-testid="risk-tensor-blocked-date-manual-copy"
              tabIndex={0}
            >
              {blockedDateCopyText}
            </pre>
          ) : null}
        </div>
      ) : tensorQuery.isError ? (
        <div className="risk-tensor-error-context" data-testid="risk-tensor-error-context">
          <strong>{riskTensorErrorMessage(tensorErrorStatusCode)}</strong>
          <span>
            报告日 {tensorErrorReportDate}；HTTP 状态{" "}
            {tensorErrorStatusCode || "未知"}。日期治理 trace_id{" "}
            {datesGovernanceMeta?.trace_id ?? EM_DASH}；主读面 trace_id {EM_DASH}。请先核对正式风险张量物化和
            lineage 新鲜度；页面不会使用缓存或前端补算替代正式主读结果。
          </span>
          <span>
            日期治理元数据：basis {datesGovernanceMeta?.basis ?? EM_DASH}；cache_version{" "}
            {datesGovernanceMeta?.cache_version ?? EM_DASH}；generated_at{" "}
            <span title={datesGovernanceMeta?.generated_at}>
              {formatTimestampDisplay(datesGovernanceMeta?.generated_at)}
            </span>
            ；source_version {datesGovernanceMeta?.source_version ?? EM_DASH}；rule_version{" "}
            {datesGovernanceMeta?.rule_version ?? EM_DASH}。
          </span>
          <div className="risk-tensor-quality-detail__trace-actions">
            <button
              type="button"
              className="risk-tensor-quality-detail__trace-action"
              onClick={() => handleSectionJump("risk-tensor-result-meta-panel")}
            >
              定位元数据
            </button>
            <button
              type="button"
              className="risk-tensor-quality-detail__trace-action"
              onClick={handleRetryTensorMainRead}
            >
              重试主读面
            </button>
            <button type="button" className="risk-tensor-quality-detail__trace-action" onClick={handleCopyTensorError}>
              复制排查信息
            </button>
          </div>
          {tensorErrorCopyMessage ? (
            <small className="risk-tensor-quality-detail__trace-feedback" aria-live="polite">
              {tensorErrorCopyMessage}
            </small>
          ) : null}
          {tensorErrorCopyStatusForCurrentState === "failed" ? (
            <pre
              className="risk-tensor-quality-detail__manual-copy"
              data-testid="risk-tensor-error-manual-copy"
              tabIndex={0}
            >
              {tensorErrorCopyText}
            </pre>
          ) : null}
        </div>
      ) : datesBlockingError ? (
        <div className="risk-tensor-error-context" data-testid="risk-tensor-error-context">
          <strong>风险报告日列表加载失败</strong>
          <span>
            HTTP 状态 {datesErrorStatusCode || "未知"}。页面不会回退到硬编码报告日。
          </span>
          <div className="risk-tensor-quality-detail__trace-actions">
            <button
              type="button"
              className="risk-tensor-quality-detail__trace-action"
              onClick={handleRetryDatesGovernance}
            >
              重试日期治理
            </button>
            <button type="button" className="risk-tensor-quality-detail__trace-action" onClick={handleCopyDatesError}>
              复制日期排查信息
            </button>
          </div>
          {datesErrorCopyMessage ? (
            <small className="risk-tensor-quality-detail__trace-feedback" aria-live="polite">
              {datesErrorCopyMessage}
            </small>
          ) : null}
          {datesErrorCopyStatusForCurrentState === "failed" ? (
            <pre
              className="risk-tensor-quality-detail__manual-copy"
              data-testid="risk-tensor-dates-error-manual-copy"
              tabIndex={0}
            >
              {datesErrorCopyText}
            </pre>
          ) : null}
        </div>
      ) : null}

      <PageAsyncSection
        title="组合风险张量"
        isLoading={datesQuery.isLoading || tensorQuery.isLoading}
        isError={datesBlockingError || tensorBlockedByReportDate || tensorQuery.isError}
        isEmpty={isEmpty && !result}
        onRetry={() => {
          void datesQuery.refetch();
          if (tensorQueryEnabled) {
            void tensorQuery.refetch();
          }
        }}
      >
        {datesEmpty ? (
          <div className="risk-tensor-empty-state" data-testid="risk-tensor-dates-empty-state">
            <strong>后端未返回可用风险报告日</strong>
            <span>trace_id {datesEmptyTraceId}</span>
            <span>可用报告日 0 个</span>
            <p>页面不会回退到硬编码报告日；请核对风险张量报告日物化任务和日期治理结果。</p>
            <div className="risk-tensor-quality-detail__trace-actions">
              <button
                type="button"
                className="risk-tensor-quality-detail__trace-action"
                onClick={() => handleSectionJump("risk-tensor-result-meta-panel")}
              >
                定位元数据
              </button>
              <button
                type="button"
                className="risk-tensor-quality-detail__trace-action"
                onClick={handleRetryDatesGovernance}
              >
                重试日期治理
              </button>
              <button type="button" className="risk-tensor-quality-detail__trace-action" onClick={handleCopyDatesEmpty}>
                复制空日期排查信息
              </button>
            </div>
            {datesEmptyCopyMessage ? (
              <small className="risk-tensor-quality-detail__trace-feedback" aria-live="polite">
                {datesEmptyCopyMessage}
              </small>
            ) : null}
            {datesEmptyCopyStatusForCurrentState === "failed" ? (
              <pre
                className="risk-tensor-quality-detail__manual-copy"
                data-testid="risk-tensor-dates-empty-manual-copy"
                tabIndex={0}
              >
                {datesEmptyCopyText}
              </pre>
            ) : null}
          </div>
        ) : isEmpty && result ? (
          <div className="risk-tensor-empty-state" data-testid="risk-tensor-empty-state">
            <strong>当前报告日无风险张量持仓</strong>
            <span>报告日 {result.report_date}</span>
            <span>trace_id {tensorMeta?.trace_id ?? EM_DASH}</span>
            <span>质量标记：{qualityFlagLabel(result.quality_flag)}</span>
            <span>{qualityTraceMetadataDetail}</span>
            <p>后端返回 bond_count 为 0，页面不会在前端补算正式指标；请核对持仓快照、风险张量物化任务和元数据证据。</p>
            <div className="risk-tensor-quality-detail__trace-actions">
              <button
                type="button"
                className="risk-tensor-quality-detail__trace-action"
                onClick={() => handleSectionJump("risk-tensor-result-meta-panel")}
              >
                定位元数据
              </button>
              <button
                type="button"
                className="risk-tensor-quality-detail__trace-action"
                onClick={handleRetryTensorMainRead}
              >
                重试主读面
              </button>
              <button
                type="button"
                className="risk-tensor-quality-detail__trace-action"
                onClick={handleCopyEmptyPosition}
              >
                复制空持仓排查信息
              </button>
            </div>
            {emptyPositionCopyMessage ? (
              <small className="risk-tensor-quality-detail__trace-feedback" aria-live="polite">
                {emptyPositionCopyMessage}
              </small>
            ) : null}
            {emptyPositionCopyStatusForCurrentState === "failed" ? (
              <pre
                className="risk-tensor-quality-detail__manual-copy"
                data-testid="risk-tensor-empty-position-manual-copy"
                tabIndex={0}
              >
                {emptyPositionCopyText}
              </pre>
            ) : null}
          </div>
        ) : result ? (
          <>
            <section className="risk-tensor-brief" data-testid="risk-tensor-brief">
              <div className="risk-tensor-brief__lead" data-tone={qualityTone(result.quality_flag)}>
                <span>风险判读</span>
                <h2>{topLineSummary}</h2>
                <p>
                  先核对主要敞口与数据限制，再查看压力情景。
                </p>
                {conclusionNeedsQualityReview ? (
                  <button
                    type="button"
                    className="risk-tensor-brief__review-button"
                    data-testid="risk-tensor-quality-review-action"
                    onClick={handleQualityDetailJump}
                  >
                    结论需复核：数据状态为{qualityFlagLabel(result.quality_flag)}；原因：{qualityReviewReasonSummary}
                  </button>
                ) : null}
                {result.warnings.length > 0 ? (
                  <ul aria-label="risk tensor warnings">
                    {result.warnings.slice(0, 2).map((warning, index) => {
                      const warningSummary = describeRiskTensorWarning(warning);
                      return (
                        <li key={index} title={warningSummary !== warning ? warning : undefined}>
                          {warningSummary}
                        </li>
                      );
                    })}
                    {result.warnings.length > 2 ? (
                      <li>
                        <button
                          type="button"
                          className="risk-tensor-brief__link-button"
                          data-testid="risk-tensor-quality-detail-action"
                          onClick={handleQualityDetailJump}
                        >
                          另有 {result.warnings.length - 2} 条预警见下方质量明细。
                        </button>
                      </li>
                    ) : null}
                  </ul>
                ) : null}
                <div className="risk-tensor-brief__badges" aria-label="risk tensor data status">
                  <span>报告日 {result.report_date}</span>
                  {tensorMeta?.basis && tensorMeta.basis !== "formal" ? <span title={tensorMeta.basis}>数据口径需复核</span> : null}
                  {result.report_date !== reportDate ? <span>实际数据日 {result.report_date}</span> : null}
                  {tensorMeta?.fallback_mode !== "none" ? <span>{fallbackStatus}</span> : null}
                  {tensorMeta?.fallback_date ? <span>回退数据日 {tensorMeta.fallback_date}</span> : null}
                  {blockedReportDates.length > 0 ? <span>{blockedReportDateSummary}</span> : null}
                </div>
              </div>

              <div className="risk-tensor-brief__tiles">
                <button
                  type="button"
                  className="risk-tensor-brief__tile risk-tensor-brief__tile--action"
                  data-testid="risk-tensor-primary-tenor-action"
                  data-tone="neutral"
                  onClick={handlePrimaryTenorDrill}
                >
                  <span>主风险桶</span>
                  <strong>{primaryTenor}</strong>
                  <span className="risk-tensor-brief__tile-detail">
                    KRD {primaryTenorValue}，绝对敞口最大的期限。
                  </span>
                </button>
                <button
                  type="button"
                  className="risk-tensor-brief__tile risk-tensor-brief__tile--action"
                  data-testid="risk-tensor-scenario-stress-action"
                  data-tone="neutral"
                  onClick={() => handleSectionJump("risk-tensor-scenario-stress")}
                >
                  <span>压力情景</span>
                  <strong>查看冲击影响</strong>
                  <span className="risk-tensor-brief__tile-detail">
                    监管 DV01 {regulatoryDv01DisplayWithUnit(result.regulatory_dv01)}；情景结果需复核。
                  </span>
                </button>
                <button
                  type="button"
                  className="risk-tensor-brief__tile risk-tensor-brief__tile--action"
                  data-testid="risk-tensor-liquidity-action"
                  data-tone={liquidityGapTone(liquidity30dValue)}
                  onClick={handleLiquidityDetailJump}
                >
                  <span>流动性</span>
                  <strong>{ratioPercentDisplay(result.liquidity_gap_30d_ratio)}</strong>
                  <span className="risk-tensor-brief__tile-detail">
                    {yuanAsYiWithUnit(result.liquidity_gap_30d)} = 30 日资产现金流 - 负债现金流。
                  </span>
                </button>
                <button
                  type="button"
                  className="risk-tensor-brief__tile risk-tensor-brief__tile--action"
                  data-testid="risk-tensor-issuer-concentration-action"
                  data-tone="neutral"
                  onClick={handleIssuerConcentrationJump}
                >
                  <span>发行人集中度</span>
                  <strong>{ratioPercentDisplay(result.issuer_top5_weight)}</strong>
                  <span className="risk-tensor-brief__tile-detail">
                    前五大权重；HHI {displayStr(result.issuer_concentration_hhi)}。
                  </span>
                </button>
                <button
                  type="button"
                  className="risk-tensor-brief__tile risk-tensor-brief__tile--action"
                  data-testid="risk-tensor-data-status-action"
                  data-tone={qualityTone(result.quality_flag)}
                  onClick={handleQualityDetailJump}
                >
                  <span>数据状态</span>
                  <strong>{qualityFlagLabel(result.quality_flag)}</strong>
                  <span className="risk-tensor-brief__tile-detail">
                    {result.warnings.length} 条风险提示，查看数据与计算说明。
                  </span>
                </button>
                {actionTileCanJump ? (
                  <button
                    type="button"
                    className="risk-tensor-brief__tile risk-tensor-brief__tile--action"
                    data-testid="risk-tensor-required-action"
                    data-tone={actionTileTone}
                    onClick={handleRequiredInformationJump}
                  >
                    <span>待补信息</span>
                    <strong>{actionTileSummary}</strong>
                    <span className="risk-tensor-brief__tile-detail" title={actionTileDetailEvidence}>{actionTileDetail}</span>
                  </button>
                ) : (
                  <article className="risk-tensor-brief__tile" data-tone={actionTileTone}>
                    <span>待补信息</span>
                    <strong>{actionTileSummary}</strong>
                    <p title={actionTileDetailEvidence}>{actionTileDetail}</p>
                  </article>
                )}
              </div>
            </section>

            {payloadQualityIssues.length > 0 ? (
              <div className="risk-tensor-payload-quality" data-testid="risk-tensor-payload-quality-warning">
                <strong>主读 payload 字段待核对</strong>
                <span>报告日 {result.report_date}</span>
                <span>trace_id {tensorMeta?.trace_id ?? EM_DASH}</span>
                <span>字段 {payloadQualityIssueSummary}</span>
                <span>{qualityTraceMetadataDetail}</span>
                <p>
                  后端主读返回了缺失或不可解析字段；页面只保留后端原始展示/占位，不会在前端补算正式指标，请结合下方
                  result_meta 与质量证据复核。
                </p>
                <button
                  type="button"
                  className="risk-tensor-brief__link-button"
                  data-testid="risk-tensor-payload-quality-review-action"
                  onClick={handlePayloadChecklistJump}
                >
                  查看字段复核与补证请求
                </button>
                <button
                  type="button"
                  className="risk-tensor-brief__link-button"
                  data-testid="risk-tensor-payload-quality-meta-action"
                  onClick={() => handleSectionJump("risk-tensor-result-meta-panel")}
                >
                  查看 result_meta
                </button>
                <button
                  type="button"
                  className="risk-tensor-brief__link-button"
                  onClick={handleRetryTensorMainRead}
                >
                  重试主读面
                </button>
                <button
                  type="button"
                  className="risk-tensor-brief__link-button"
                  onClick={handleCopyPayloadQualityRequest}
                >
                  复制字段补证请求
                </button>
                {missingQualityEvidenceLabels.length > 0 ? (
                  <>
                    <button
                      type="button"
                      className="risk-tensor-brief__link-button"
                      onClick={handleCopyQualityEvidenceRequest}
                    >
                      复制证据补证请求
                    </button>
                    <button
                      type="button"
                      className="risk-tensor-brief__link-button"
                      onClick={handleCopyCombinedQualityRequest}
                    >
                      复制完整补证包
                    </button>
                  </>
                ) : null}
                {payloadQualityRequestCopyMessage ? (
                  <small className="risk-tensor-quality-detail__trace-feedback" aria-live="polite">
                    {payloadQualityRequestCopyMessage}
                  </small>
                ) : null}
                {qualityEvidenceRequestCopyMessage ? (
                  <small className="risk-tensor-quality-detail__trace-feedback" aria-live="polite">
                    {qualityEvidenceRequestCopyMessage}
                  </small>
                ) : null}
                {combinedQualityRequestCopyMessage ? (
                  <small className="risk-tensor-quality-detail__trace-feedback" aria-live="polite">
                    {combinedQualityRequestCopyMessage}
                  </small>
                ) : null}
                {qualityEvidenceRequestCopyStatusForCurrentState === "failed" ? (
                  <pre
                    className="risk-tensor-quality-detail__manual-copy"
                    data-testid="risk-tensor-quality-evidence-warning-request-manual-copy"
                    tabIndex={0}
                  >
                    {qualityEvidenceRequestCopyText}
                  </pre>
                ) : null}
                {combinedQualityRequestCopyStatusForCurrentState === "failed" ? (
                  <pre
                    className="risk-tensor-quality-detail__manual-copy"
                    data-testid="risk-tensor-combined-quality-warning-request-manual-copy"
                    tabIndex={0}
                  >
                    {combinedQualityRequestCopyText}
                  </pre>
                ) : null}
                {payloadQualityRequestCopyStatusForCurrentState === "failed" ? (
                  <pre
                    className="risk-tensor-quality-detail__manual-copy"
                    data-testid="risk-tensor-payload-quality-warning-manual-copy"
                    tabIndex={0}
                  >
                    {payloadQualityRequestCopyText}
                  </pre>
                ) : null}
              </div>
            ) : null}

            <div data-testid="risk-tensor-kpi-grid" className="risk-tensor-summary-grid">
              <KpiCard
                title="面值口径 DV01"
                value={yuanAsWanDisplay(result.portfolio_dv01)}
                detail="持仓面值敏感性，非监管限额口径；万元/bp。"
                unit={WAN_YUAN_UNIT}
                tone={toneFromSignedDisplayString(yuanAsWanDisplay(result.portfolio_dv01))}
                testId="risk-tensor-portfolio-dv01-kpi"
              />
              <KpiCard
                title="监管口径 DV01"
                value={regulatoryDv01Display(result.regulatory_dv01)}
                detail="监管及限额口径；万元/bp。"
                unit={amountUnit(result.regulatory_dv01, WAN_YUAN_UNIT)}
                tone={regulatoryDv01Tone(result.regulatory_dv01)}
                testId="risk-tensor-regulatory-dv01-kpi"
              />
              <KpiCard
                title="修正久期"
                value={displayStr(result.portfolio_modified_duration)}
                detail="按利率风险适用资产加权。"
                unit="年"
                testId="risk-tensor-duration-kpi"
              />
              <KpiCard
                title="CS01"
                value={yuanAsWanDisplay(result.cs01)}
                detail="信用利差敏感度；万元/bp。"
                unit={WAN_YUAN_UNIT}
                tone={toneFromSignedDisplayString(yuanAsWanDisplay(result.cs01))}
                testId="risk-tensor-cs01-kpi"
              />
              <KpiCard
                title="组合凸性"
                value={displayStr(result.portfolio_convexity)}
                tone={toneFromSignedDisplayString(displayStr(result.portfolio_convexity))}
                testId="risk-tensor-convexity-kpi"
              />
              <KpiCard
                title="持仓记录数"
                value={String(result.bond_count)}
                unit="条"
              />
              <KpiCard
                title="总市值"
                value={yuanAsYiDisplay(result.total_market_value)}
                unit={YI_YUAN_UNIT}
                tone={toneFromSignedDisplayString(yuanAsYiDisplay(result.total_market_value))}
              />
            </div>
            {kpiRadarIssues.length > 0 ? (
              <div className="risk-tensor-radar-quality" data-testid="risk-tensor-kpi-quality-note">
                {kpiRadarIssues.map((row) => `${row.key} ${row.issue}`).join(" / ")}
                ；相关字段未参与前端雷达图数值。
                <button type="button" className="risk-tensor-brief__link-button" onClick={handlePayloadChecklistJump}>
                  查看字段复核
                </button>
                <button type="button" className="risk-tensor-brief__link-button" onClick={handleRetryTensorMainRead}>
                  重试主读面
                </button>
              </div>
            ) : null}

            {showDurationScope ? (
              <section className="risk-tensor-duration-scope" data-testid="risk-tensor-duration-scope">
                <div className="risk-tensor-duration-scope__header">
                  <span>久期口径</span>
                  <h2>利率风险适用资产覆盖</h2>
                  <p>
                    组合久期只按有到期日且正久期的资产加权；基金不编造合同期限，底层利率风险尚未穿透，未覆盖范围不能解释为零风险。
                  </p>
                </div>
                <div className="risk-tensor-duration-scope__grid">
                  <KpiCard
                    title="利率风险市值"
                    value={yuanAsYiDisplay(result.rate_risk_market_value)}
                    detail="参与久期加权的市值。"
                    unit={YI_YUAN_UNIT}
                    tone={toneFromSignedDisplayString(yuanAsYiDisplay(result.rate_risk_market_value))}
                  />
                  <KpiCard
                    title="利率风险 DV01"
                    value={yuanAsWanDisplay(result.rate_risk_dv01)}
                    detail="参与久期加权的资产敞口；万元/bp。"
                    unit={amountUnit(result.rate_risk_dv01, WAN_YUAN_UNIT)}
                    tone={toneFromSignedDisplayString(yuanAsWanDisplay(result.rate_risk_dv01))}
                  />
                  <KpiCard
                    title="利率风险久期"
                    value={displayStr(result.rate_risk_modified_duration)}
                    detail="参与加权资产的修正久期。"
                    unit={amountUnit(result.rate_risk_modified_duration, "年")}
                  />
                  <KpiCard
                    title="久期排除市值"
                    value={yuanAsYiDisplay(result.duration_excluded_market_value)}
                    detail={`${countDisplay(result.duration_excluded_count)} 条持仓未计入久期。`}
                    unit={amountUnit(result.duration_excluded_market_value, YI_YUAN_UNIT)}
                    tone={durationExclusionTone(result)}
                  />
                </div>
                <div className="risk-tensor-duration-scope__header" data-testid="risk-tensor-maturity-breakdown">
                  <h3>久期排除原因</h3>
                  {result.maturity_breakdown_status !== "available" ? (
                    <p>该报告日的旧版物化行尚未提供排除原因拆分，以下空值不能视为零。</p>
                  ) : (
                    <p>四类金额及记录数合计为上方久期排除总量；基金未列固定到期日不属于要求补造日期的异常。</p>
                  )}
                </div>
                <div className="risk-tensor-duration-scope__grid">
                  <KpiCard
                    title="基金未列固定到期日"
                    value={yuanAsYiDisplay(result.fund_no_maturity_market_value)}
                    detail={`${countDisplay(result.fund_no_maturity_count)} 条；底层利率风险尚未穿透。`}
                    unit={amountUnit(result.fund_no_maturity_market_value, YI_YUAN_UNIT)}
                  />
                  <KpiCard
                    title="期限属性待核实"
                    value={yuanAsYiDisplay(result.unknown_maturity_market_value)}
                    detail={`${countDisplay(result.unknown_maturity_count)} 条；核对来源日期或产品属性。`}
                    unit={amountUnit(result.unknown_maturity_market_value, YI_YUAN_UNIT)}
                  />
                  <KpiCard
                    title="已到期仍有余额"
                    value={yuanAsYiDisplay(result.matured_outstanding_market_value)}
                    detail={`${countDisplay(result.matured_outstanding_count)} 条；需核对余额，不据此推断违约。`}
                    unit={amountUnit(result.matured_outstanding_market_value, YI_YUAN_UNIT)}
                  />
                  <KpiCard
                    title="未来到期但久期非正"
                    value={yuanAsYiDisplay(result.nonpositive_duration_market_value)}
                    detail={`${countDisplay(result.nonpositive_duration_count)} 条；需核查久期输入。`}
                    unit={amountUnit(result.nonpositive_duration_market_value, YI_YUAN_UNIT)}
                  />
                </div>
                {durationCoverageQualityIssues.length > 0 ? (
                  <div
                    className="risk-tensor-radar-quality"
                    data-testid="risk-tensor-duration-coverage-quality-note"
                  >
                    {durationCoverageQualityIssues.map((row) => `${row.key} ${row.issue}`).join(" / ")}
                    ；相关久期覆盖字段只保留后端原始展示/占位，页面不会在前端补算正式指标。
                    <button type="button" className="risk-tensor-brief__link-button" onClick={handlePayloadChecklistJump}>
                      查看字段复核
                    </button>
                    <button type="button" className="risk-tensor-brief__link-button" onClick={handleRetryTensorMainRead}>
                      重试主读面
                    </button>
                  </div>
                ) : null}
                {durationRadarIssue ? (
                  <div className="risk-tensor-radar-quality" data-testid="risk-tensor-duration-quality-note">
                    portfolio_modified_duration {durationRadarIssue}；该字段未参与前端雷达图数值。
                    <button type="button" className="risk-tensor-brief__link-button" onClick={handlePayloadChecklistJump}>
                      查看字段复核
                    </button>
                    <button type="button" className="risk-tensor-brief__link-button" onClick={handleRetryTensorMainRead}>
                      重试主读面
                    </button>
                  </div>
                ) : null}
              </section>
            ) : null}

            {result ? (
              <section className="risk-tensor-duration-scope" data-testid="risk-tensor-projection-quality">
                <div className="risk-tensor-duration-scope__header">
                  <span>现金流投影质量</span>
                  <h2>投影质量披露</h2>
                  <p>
                    状态：{projectionQualityStatusLabel(result.projection_quality_status)}；未列到期日资产单列展示，含基金，不并入合同期限桶；
                    浮息债按冻结票息代理，未模拟 reset；付息频率采用年付代理，非合同确认；起息日缺失时使用一年利息代理。
                  </p>
                </div>
                <div className="risk-tensor-duration-scope__grid">
                  {PROJECTION_QUALITY_FIELDS.map((item) => (
                    <KpiCard
                      key={item.marketValueKey}
                      title={item.title}
                      value={projectionQualityAmountDisplay(result[item.marketValueKey])}
                      detail={`${projectionQualityCountDisplay(result[item.countKey])}；${item.detail}`}
                      unit={projectionQualityAmountUnit(result[item.marketValueKey])}
                      tone={projectionQualityTone(
                        result[item.marketValueKey],
                        result[item.countKey],
                        result.projection_quality_status,
                      )}
                    />
                  ))}
                </div>
              </section>
            ) : null}

            {result ? (
              <RiskScenarioStressPanel
                payload={scenarioStressQuery.data?.result}
                meta={scenarioStressQuery.data?.result_meta}
                isLoading={scenarioStressQuery.isLoading}
                error={scenarioStressQuery.error}
                reportDate={reportDate}
                onRetry={() => void scenarioStressQuery.refetch()}
                onMetaJump={() => handleSectionJump("risk-tensor-result-meta-panel")}
              />
            ) : null}

            <div className="risk-tensor-chart-row">
              <div className="risk-tensor-chart-column">
                <ChartCard
                  testId="risk-tensor-radar-card"
                  title="风险张量雷达"
                  asOf={result?.report_date}
                  height={CHART_CARD_HEIGHTS.hero}
                  legend="none"
                  option={radarChartOption}
                >
                  {invalidRadarRows.length > 0 ? (
                    <div className="risk-tensor-radar-quality" data-testid="risk-tensor-radar-quality-note">
                      {invalidRadarRows.map((row) => `${row.key} ${row.issue}`).join(" / ")}
                      ；未参与前端雷达图数值。
                      <button
                        type="button"
                        className="risk-tensor-brief__link-button"
                        onClick={handlePayloadChecklistJump}
                      >
                        查看字段复核
                      </button>
                      <button
                        type="button"
                        className="risk-tensor-brief__link-button"
                        onClick={handleRetryTensorMainRead}
                      >
                        重试主读面
                      </button>
                    </div>
                  ) : null}
                  {radarNavigationItems.length > 0 ? (
                    <div className="risk-tensor-radar-actions" aria-label="risk tensor radar dimension navigation">
                      {radarNavigationItems.map((item) => (
                        <button
                          key={item.key}
                          type="button"
                          data-testid={`risk-tensor-radar-action-${item.key}`}
                          onClick={() => handleSectionJump(item.targetTestId)}
                        >
                          {item.name}
                        </button>
                      ))}
                    </div>
                  ) : null}
                </ChartCard>
              </div>
              <div className="risk-tensor-chart-column">
                <ChartCard
                  title="KRD分档"
                  question="面值DV01"
                  unit="万元/bp"
                  asOf={result?.report_date}
                  height={CHART_CARD_HEIGHTS.hero}
                  legend="none"
                  option={krdChartOption}
                  chartRenderer={({ option }) => (
                    <InteractiveEChart
                      option={option}
                      onEvents={{ click: handleKrdChartClick }}
                      className="risk-tensor-chart risk-tensor-chart--krd"
                      notMerge
                      lazyUpdate
                    />
                  )}
                />
              {!selectedTenorRow ? krdQualityNote : null}

              {selectedTenorRow ? (
                <div data-testid="risk-tensor-tenor-drill" className="risk-tensor-tenor-drill">
                  <div className="risk-tensor-tenor-drill__title">
                    期限桶下钻
                  </div>
                  <div className="risk-tensor-tenor-drill__desc">
                    选择期限，查看对应的利率敏感度。
                  </div>
                  {krdQualityNote}
                  <div className="risk-tensor-chip-row">
                    {tenorRows.map((row) => (
                      <button
                        key={row.tenor}
                        aria-pressed={row.tenor === selectedTenor}
                        type="button"
                        className="risk-tensor-chip-button"
                        onClick={() => handleKrdTenorSelect(row)}
                      >
                        {row.tenor}
                      </button>
                    ))}
                  </div>
                  <div className="risk-tensor-tenor-drill__current">
                    当前桶：<strong>{selectedTenorRow.tenor}</strong>
                  </div>
                  <div className="risk-tensor-tenor-drill__value">
                    KRD：{yuanAsWanWithUnit(selectedTenorRow.value)}
                  </div>
                </div>
              ) : null}
            </div>
          </div>

            <section
              data-testid="risk-tensor-issuer-concentration-detail"
              aria-label="发行人集中度明细"
              className="risk-tensor-section-head-gap"
            >
              <SectionHead title="发行人集中度" numbered={false} />
              <div className="risk-tensor-summary-grid">
                <KpiCard
                  title="发行人 HHI"
                  value={displayStr(result.issuer_concentration_hhi)}
                  testId="risk-tensor-issuer-hhi"
                />
                <KpiCard
                  title="前五大权重"
                  value={ratioPercentDisplay(result.issuer_top5_weight)}
                />
              </div>
              {issuerConcentrationIssue ? (
                <div className="risk-tensor-radar-quality" data-testid="risk-tensor-issuer-quality-note">
                  issuer_concentration_hhi {issuerConcentrationIssue}；该字段未参与前端雷达图数值。
                  <button type="button" className="risk-tensor-brief__link-button" onClick={handlePayloadChecklistJump}>
                    查看字段复核
                  </button>
                  <button type="button" className="risk-tensor-brief__link-button" onClick={handleRetryTensorMainRead}>
                    重试主读面
                  </button>
                </div>
              ) : null}
            </section>

            <section
              data-testid="risk-tensor-liquidity-gap-detail"
              aria-label="流动性现金流缺口明细"
              className="risk-tensor-section-head-gap"
            >
              <SectionHead title="流动性现金流缺口" numbered={false} />
              <div className="risk-tensor-summary-grid">
                <KpiCard
                  title="30 日资产现金流 - 负债现金流"
                  value={yuanAsYiDisplay(result.liquidity_gap_30d)}
                  unit={YI_YUAN_UNIT}
                  tone={toneFromSignedDisplayString(yuanAsYiDisplay(result.liquidity_gap_30d))}
                />
                <KpiCard
                  title="90 日资产现金流 - 负债现金流"
                  value={yuanAsYiDisplay(result.liquidity_gap_90d)}
                  unit={YI_YUAN_UNIT}
                  tone={toneFromSignedDisplayString(yuanAsYiDisplay(result.liquidity_gap_90d))}
                />
                <KpiCard
                  title="30 日流动性缺口比例"
                  value={ratioPercentDisplay(result.liquidity_gap_30d_ratio)}
                  tone={ratioTone(result.liquidity_gap_30d_ratio)}
                  testId="risk-tensor-liquidity-gap-ratio"
                />
                <KpiCard
                  title="无到期日负债排除"
                  value={projectionQualityAmountDisplay(result.missing_liability_maturity_principal_amount)}
                  detail={`${excludedLiabilityCountDisplay(result.missing_liability_maturity_count)}；未纳入 30/90 日负债现金流与流动性缺口。`}
                  unit={projectionQualityAmountUnit(result.missing_liability_maturity_principal_amount)}
                  testId="risk-tensor-missing-liability-maturity"
                />
              </div>
              {liquidityGapRatioIssue ? (
                <div className="risk-tensor-radar-quality" data-testid="risk-tensor-liquidity-quality-note">
                  liquidity_gap_30d_ratio {liquidityGapRatioIssue}；该字段未参与前端雷达图数值。
                  <button type="button" className="risk-tensor-brief__link-button" onClick={handlePayloadChecklistJump}>
                    查看字段复核
                  </button>
                  <button type="button" className="risk-tensor-brief__link-button" onClick={handleRetryTensorMainRead}>
                    重试主读面
                  </button>
                </div>
              ) : null}
            </section>

            <div className="risk-tensor-section-head-gap">
              <SectionHead title="现金流构成" numbered={false} />
            </div>
            <div data-testid="risk-tensor-cashflow-grid" className="risk-tensor-summary-grid">
              <KpiCard
                title="30 日资产现金流"
                value={yuanAsYiDisplay(result.asset_cashflow_30d)}
                unit={YI_YUAN_UNIT}
              />
              <KpiCard
                title="30 日负债现金流"
                value={yuanAsYiDisplay(result.liability_cashflow_30d)}
                unit={YI_YUAN_UNIT}
              />
              <KpiCard
                title="90 日资产现金流"
                value={yuanAsYiDisplay(result.asset_cashflow_90d)}
                unit={YI_YUAN_UNIT}
              />
              <KpiCard
                title="90 日负债现金流"
                value={yuanAsYiDisplay(result.liability_cashflow_90d)}
                unit={YI_YUAN_UNIT}
              />
            </div>

            <details
              data-testid="risk-tensor-quality-detail"
              className="risk-tensor-quality-detail risk-tensor-disclosure"
              data-tone={result.quality_flag === "ok" ? "ok" : result.quality_flag}
            >
              <summary className="risk-tensor-quality-detail__title">
                数据与计算说明 · <span>质量标记：
                {result.quality_flag === "ok"
                  ? "正常"
                  : result.quality_flag === "warning"
                    ? "预警"
                    : result.quality_flag === "error"
                      ? "错误"
                      : result.quality_flag === "stale"
                        ? "陈旧"
                        : result.quality_flag}</span>
              </summary>
              <div className="risk-tensor-quality-detail__evidence" data-testid="risk-tensor-quality-evidence">
                <strong>证据范围</strong>
                <span>trace_id {tensorMeta?.trace_id ?? EM_DASH}</span>
                <span>basis {tensorMeta?.basis ?? EM_DASH}</span>
                <span>cache_version {tensorMeta?.cache_version ?? EM_DASH}</span>
                <span title={tensorMeta?.generated_at}>
                  generated_at {formatTimestampDisplay(tensorMeta?.generated_at)}
                </span>
                <span>来源 {compactVersion(tensorMeta?.source_version)}</span>
                <span>规则 {compactVersion(tensorMeta?.rule_version)}</span>
                <span>{fallbackStatus}</span>
                {tensorMeta?.fallback_date ? <span>fallback_date {tensorMeta.fallback_date}</span> : null}
                <span>{blockedReportDateSummary}</span>
                <span>evidence_rows {typeof tensorMeta?.evidence_rows === "number" ? tensorMeta.evidence_rows : EM_DASH}</span>
                <span>tables_used {metadataTablesUsed || EM_DASH}</span>
                <span>filters_applied {metadataFiltersApplied || EM_DASH}</span>
              </div>
              <div className="risk-tensor-quality-detail__trace" data-testid="risk-tensor-quality-trace-priority">
                <strong>证据优先级</strong>
                <div className="risk-tensor-quality-detail__review-state" aria-live="polite">
                  复核状态：{qualityReviewStateLabel}
                </div>
                <ol>
                  <li>
                    <span>来源/规则</span>
                    <p>
                      来源 {compactVersion(tensorMeta?.source_version)}；规则 {compactVersion(tensorMeta?.rule_version)}
                    </p>
                  </li>
                  <li>
                    <span>降级</span>
                    <p>{qualityTraceFallbackDetail}</p>
                  </li>
                  <li>
                    <span>陈旧日期</span>
                    <p>{qualityTraceBlockedDetail}</p>
                  </li>
                  <li>
                    <span>预警</span>
                    <p>{qualityTraceWarningDetail}</p>
                  </li>
                  <li>
                    <span>证据范围</span>
                    <p>{qualityTraceMetadataDetail}</p>
                    <div className="risk-tensor-quality-detail__trace-actions">
                      <button
                        type="button"
                        className="risk-tensor-quality-detail__trace-action"
                        onClick={() => handleSectionJump("risk-tensor-result-meta-panel")}
                      >
                        定位元数据
                      </button>
                      <button
                        type="button"
                        className="risk-tensor-quality-detail__trace-action"
                        onClick={handleCopyQualityEvidence}
                      >
                        复制证据
                      </button>
                    </div>
                    {qualityEvidenceCopyMessage ? (
                      <small className="risk-tensor-quality-detail__trace-feedback" aria-live="polite">
                        {qualityEvidenceCopyMessage}
                      </small>
                    ) : null}
                    {qualityEvidenceCopyStatusForCurrentState === "failed" ? (
                      <pre
                        className="risk-tensor-quality-detail__manual-copy"
                        data-testid="risk-tensor-quality-evidence-manual-copy"
                        tabIndex={0}
                      >
                        {qualityTraceCopyText}
                      </pre>
                    ) : null}
                    <div className="risk-tensor-quality-detail__evidence-checklist">
                      <strong>证据字段复核</strong>
                      <ul>
                        {qualityEvidenceReviewItems.map((item) => (
                          <li key={item.key} data-status={item.status === "已提供" ? "provided" : "missing"}>
                            <span>{item.label} </span>
                            <b>{item.status}</b>
                          </li>
                        ))}
                      </ul>
                      {canConfirmQualityEvidenceReview ? (
                        <div className="risk-tensor-quality-detail__evidence-request">
                          <button
                            type="button"
                            className="risk-tensor-quality-detail__trace-action"
                            onClick={handleConfirmQualityEvidenceReview}
                          >
                            确认业务复核
                          </button>
                        </div>
                      ) : null}
                      {qualityEvidenceReviewConfirmed ? (
                        <div className="risk-tensor-quality-detail__evidence-request">
                          <button
                            type="button"
                            className="risk-tensor-quality-detail__trace-action"
                            onClick={handleCopyQualityEvidenceReviewRecord}
                          >
                            复制确认记录
                          </button>
                          {qualityEvidenceReviewRecordCopyMessage ? (
                            <small className="risk-tensor-quality-detail__trace-feedback" aria-live="polite">
                              {qualityEvidenceReviewRecordCopyMessage}
                            </small>
                          ) : null}
                          {qualityEvidenceReviewRecordCopiedStateKey === qualityStateKey &&
                          qualityEvidenceReviewRecordCopyStatus === "failed" ? (
                            <pre
                              className="risk-tensor-quality-detail__manual-copy"
                              data-testid="risk-tensor-quality-evidence-review-record-manual-copy"
                              tabIndex={0}
                            >
                              {qualityEvidenceReviewRecordCopyText}
                            </pre>
                          ) : null}
                        </div>
                      ) : null}
                      {hasMissingQualityEvidence ? (
                        <div className="risk-tensor-quality-detail__evidence-request">
                          <button
                            type="button"
                            className="risk-tensor-quality-detail__trace-action"
                            onClick={handleCopyQualityEvidenceRequest}
                          >
                            复制补证请求
                          </button>
                          {qualityEvidenceRequestCopyMessage ? (
                            <small className="risk-tensor-quality-detail__trace-feedback" aria-live="polite">
                              {qualityEvidenceRequestCopyMessage}
                            </small>
                          ) : null}
                          {qualityEvidenceRequestCopyStatusForCurrentState === "failed" ? (
                            <pre
                              className="risk-tensor-quality-detail__manual-copy"
                              data-testid="risk-tensor-quality-evidence-request-manual-copy"
                              tabIndex={0}
                            >
                              {qualityEvidenceRequestCopyText}
                            </pre>
                          ) : null}
                        </div>
                      ) : null}
                    </div>
                    {payloadQualityIssues.length > 0 ? (
                      <div
                        className="risk-tensor-quality-detail__payload-checklist"
                        data-testid="risk-tensor-quality-payload-checklist"
                      >
                        <strong>主读 payload 字段复核</strong>
                        <p>trace_id {tensorMeta?.trace_id ?? EM_DASH}；不会在前端补算正式指标。</p>
                        <ul>
                          {payloadQualityIssues.map((item) => (
                            <li key={item.key}>
                              <span>{item.label}</span>
                              <b>{item.issue}</b>
                            </li>
                          ))}
                        </ul>
                        <div className="risk-tensor-quality-detail__evidence-request">
                          <button
                            type="button"
                            className="risk-tensor-quality-detail__trace-action"
                            onClick={handleCopyPayloadQualityRequest}
                          >
                            复制字段补证请求
                          </button>
                          {payloadQualityRequestCopyMessage ? (
                            <small className="risk-tensor-quality-detail__trace-feedback" aria-live="polite">
                              {payloadQualityRequestCopyMessage}
                            </small>
                          ) : null}
                          {payloadQualityRequestCopyStatusForCurrentState === "failed" ? (
                            <pre
                              className="risk-tensor-quality-detail__manual-copy"
                              data-testid="risk-tensor-payload-quality-request-manual-copy"
                              tabIndex={0}
                            >
                              {payloadQualityRequestCopyText}
                            </pre>
                          ) : null}
                        </div>
                      </div>
                    ) : null}
                  </li>
                </ol>
              </div>
              {highlightedBlockedReportDate ? (
                <div className="risk-tensor-quality-detail__blocked" data-testid="risk-tensor-quality-blocked-date">
                  <strong>{highlightedBlockedReportDate.report_date}</strong>
                  <span>{highlightedBlockedReportDate.reason}</span>
                </div>
              ) : null}
              {result.warnings.length === 0 ? (
                <div className="risk-tensor-quality-detail__warning-empty">无预警。</div>
              ) : (
                <div>
                  <div className="risk-tensor-quality-detail__trace-actions">
                    <button
                      type="button"
                      className="risk-tensor-quality-detail__trace-action"
                      onClick={handleCopyQualityWarnings}
                    >
                      复制预警清单
                    </button>
                    {qualityWarningsCopyMessage ? (
                      <small className="risk-tensor-quality-detail__trace-feedback" aria-live="polite">
                        {qualityWarningsCopyMessage}
                      </small>
                    ) : null}
                  </div>
                  {qualityWarningsCopiedStateKey === qualityStateKey && qualityWarningsCopyStatus === "failed" ? (
                    <pre
                      className="risk-tensor-quality-detail__manual-copy"
                      data-testid="risk-tensor-quality-warnings-manual-copy"
                    >
                      {qualityWarningsCopyText}
                    </pre>
                  ) : null}
                  <ul className="risk-tensor-quality-detail__warnings">
                    {result.warnings.map((warning, index) => (
                      <li key={index}>{warning}</li>
                    ))}
                  </ul>
                </div>
              )}
            </details>
          </>
        ) : null}
      </PageAsyncSection>

      <details className="risk-tensor-disclosure" data-testid="risk-tensor-technical-details">
        <summary>技术信息与数据血缘</summary>
        <FormalResultMetaPanel
        testId="risk-tensor-result-meta-panel"
        sections={[
          { key: "dates", title: "风险报告日列表", meta: datesQuery.data?.result_meta },
          { key: "tensor", title: "风险张量主读面", meta: envelope?.result_meta },
          { key: "scenario", title: "风险情景压力", meta: scenarioStressQuery.data?.result_meta },
        ]}
        />
      </details>
    </section>
  );
}
