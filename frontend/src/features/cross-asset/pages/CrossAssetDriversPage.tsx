import { useMemo, useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { useApiClient } from "../../../api/client";
import type {
  LivermoreManualPositionInput,
  LivermoreSignalConfluencePayload,
  LivermoreStrategyPayload,
  MacroBondLinkageEnvironmentScore,
  MacroBondLinkagePayload,
  MacroBondLinkageTopCorrelation,
} from "../../../api/contracts";
import { SectionCard } from "../../../components/SectionCard";
import { AsyncSection } from "../../../components/AsyncSection";
import { DataStatusStrip, PageDecisionHero, PageSectionLead } from "../../../components/page/PagePrimitives";
import { StatusPill } from "../../../components/StatusPill";
import ReactECharts from "../../../lib/echarts";
import { designTokens, tabularNumsStyle } from "../../../theme/designSystem";
import { KpiCard } from "../../../components/KpiCard";
import { toneFromSignedNumber } from "../../workbench/components/kpiFormat";
import { CrossAssetEventCalendar } from "../components/CrossAssetEventCalendar";
import { CrossAssetSparkline } from "../components/CrossAssetSparkline";
import { MarketCandidateActions } from "../components/MarketCandidateActions";
import { PageOutput } from "../components/PageOutput";
import { WatchList } from "../components/WatchList";
import {
  buildCrossAssetCandidateActions,
  buildCrossAssetClassAnalysisRows,
  buildCrossAssetEquityEvidenceItems,
  buildCrossAssetEventItems,
  buildCrossAssetNcdProxyEvidence,
  buildCrossAssetStatusFlags,
  buildCrossAssetWatchList,
  buildResearchSummaryCards,
  buildTransmissionAxisRows,
  formatImpactedViewsForDisplay,
  formatLinkageCorrelationDisplay,
  type CrossAssetClassAnalysisLine,
  type CrossAssetClassAnalysisRow,
  type CrossAssetEquityEvidenceItem,
  type CrossAssetNcdProxyEvidence,
  type CrossAssetResearchViewCard,
  type CrossAssetTransmissionAxisRow,
} from "../lib/crossAssetDriversPageModel";
import { buildDriverColumns, buildEnvironmentTags, driverStanceStyle } from "../lib/crossAssetDriversModel";
import { buildCrossAssetTrendOption, buildCrossAssetTrendSummary } from "../lib/crossAssetTrendChart";
import {
  buildCorrelationMatrix,
  correlationColor,
  formatCorrelation,
  identifyMarketRegime,
  computeSparklinePercentile,
  percentileZoneColor,
  buildMomentumScoreboard,
  detectVolatilityClustering,
  computeEquityBondERP,
  buildDriverWaterfall,
  TREND_GROUPS,
  trendGroupLabels,
  type TrendGroupKey,
  type CorrelationMatrix,
  type MomentumRow,
  type VolatilityAlert,
  type EquityBondERP,
  type WaterfallBar,
} from "../lib/crossAssetAnalytics";
import {
  maxCrossAssetHeadlineTradeDate,
  resolveCrossAssetKpis,
  type ResolvedCrossAssetKpi,
} from "../lib/crossAssetKpiModel";
import "./CrossAssetDriversPage.css";

const t = designTokens;

const crossAssetPanelClass = "cross-asset-drivers-page__panel";

const sparkStroke: Record<ResolvedCrossAssetKpi["changeTone"], string> = {
  positive: t.color.semantic.profit,
  negative: t.color.semantic.loss,
  warning: t.color.warning[500],
  default: t.color.primary[600],
};

function linkageHeatmapRows(correlations: MacroBondLinkageTopCorrelation[]) {
  if (correlations.length === 0) {
    return [
      {
        id: "empty",
        indicator: "暂无治理后的联动排序",
        current: "不可用",
        mid: "不可用",
        eval: "待定",
        evalTone: "warning" as const,
      },
    ];
  }

  return correlations.slice(0, 8).map((row, index) => {
    const indicator = `${row.series_name} -> ${row.target_family}${row.target_tenor ? ` (${row.target_tenor})` : ""}`;
    const id = [
      row.series_id,
      row.series_name,
      row.target_family,
      row.target_tenor,
      row.direction,
      index,
    ]
      .filter(Boolean)
      .join("|");
    const current = formatLinkageCorrelationDisplay(row.correlation_3m);
    const mid = formatLinkageCorrelationDisplay(row.correlation_6m);
    let evalLabel = "混合";
    let evalTone: "bull" | "bear" | "warning" = "warning";
    if (row.direction === "positive") {
      evalLabel = "正向";
      evalTone = "bull";
    } else if (row.direction === "negative") {
      evalLabel = "负向";
      evalTone = "bear";
    }
    return { id, indicator, current, mid, eval: evalLabel, evalTone };
  });
}

function formatSignedNumber(value: number | string | null | undefined, suffix = "") {
  if (value == null || value === "") {
    return "不可用";
  }
  const numericValue = typeof value === "number" ? value : Number.parseFloat(String(value));
  if (Number.isNaN(numericValue)) {
    return String(value);
  }
  const sign = numericValue > 0 ? "+" : "";
  return `${sign}${numericValue.toFixed(2)}${suffix}`;
}

function resultMetaQualityLabel(value: string | null | undefined): string {
  if (value === "ok") return "正常";
  if (value === "warning") return "预警";
  if (value === "error") return "错误";
  if (value === "stale") return "陈旧";
  return value ?? "待定";
}

type LivermoreReadinessKey = LivermoreStrategyPayload["rule_readiness"][number]["key"];
type LivermoreOutputKey = LivermoreStrategyPayload["unsupported_outputs"][number]["key"];

type LivermoreConfluenceDiagnostic = {
  severity: string;
  code: string;
  message: string;
};

const defaultObservationOnlyDiagnostic = "Observation-only output. This service does not generate trading instructions.";

type LivermoreConfluenceEntryObservation = {
  action: string;
  stockCode: string;
  stockName: string;
  currentPrice: string;
  triggerPrice: string;
  invalidationReferencePrice: string;
  positionSizeHint: string;
  evidence: string[];
};

type LivermoreConfluenceExitObservation = {
  action: string;
  stockCode: string;
  stockName: string;
  currentPrice: string;
  exitWatchPrice: string;
  triggered: boolean;
  evidence: string[];
};

function livermoreReadiness(payload: LivermoreStrategyPayload | null, key: LivermoreReadinessKey) {
  return payload?.rule_readiness.find((item) => item.key === key) ?? null;
}

function livermoreUnsupportedReason(payload: LivermoreStrategyPayload | null, key: LivermoreOutputKey) {
  return payload?.unsupported_outputs.find((item) => item.key === key)?.reason ?? "";
}

function formatLivermoreExposure(value: number | null | undefined) {
  if (value == null || Number.isNaN(value)) {
    return "待定";
  }
  return `${Math.round(value * 100)}%`;
}

function parseOptionalNumeric(value: unknown): number | null {
  if (value == null || value === "") {
    return null;
  }
  if (typeof value === "number") {
    return Number.isFinite(value) ? value : null;
  }
  if (typeof value === "string") {
    const parsed = Number.parseFloat(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function formatConfluencePrice(value: unknown) {
  const parsed = parseOptionalNumeric(value);
  if (parsed == null) {
    return "待定";
  }
  return parsed.toFixed(2);
}

function normalizeConfluenceEvidence(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value
      .map((item) => (typeof item === "string" ? item.trim() : ""))
      .filter((item) => item.length > 0);
  }
  if (typeof value === "string" && value.trim()) {
    return [value.trim()];
  }
  return [];
}

function translateConfluenceDiagnosticMessage(message: string) {
  if (message === defaultObservationOnlyDiagnostic) {
    return "仅供观察，不构成交易指令。";
  }
  if (message === "Missing macro composite score; macro context is unknown.") {
    return "缺少宏观综合分，当前只能保留观察口径。";
  }
  if (message === "Missing Livermore market gate; entry observations are blocked.") {
    return "缺少 Livermore 市场门控，入场观察已关闭。";
  }
  if (message === "No stock candidates available for observation.") {
    return "当前没有可展示的入场观察点位。";
  }
  if (message === "No risk exit watch items or triggered exit items available.") {
    return "当前没有可展示的退出观察点位。";
  }

  const missingBreakout = message.match(/^Stock (.+) is missing breakout_level; entry trigger price is unavailable\.$/);
  if (missingBreakout) {
    return `${missingBreakout[1]} 缺少突破位，候选触发价待定。`;
  }
  const missingInvalidation = message.match(/^Stock (.+) is missing EMA10; invalidation reference price is unavailable\.$/);
  if (missingInvalidation) {
    return `${missingInvalidation[1]} 缺少 EMA10，失效参考价待定。`;
  }
  const missingExit = message.match(/^Stock (.+) is missing EMA10; exit watch price is unavailable\.$/);
  if (missingExit) {
    return `${missingExit[1]} 缺少 EMA10，退出观察价待定。`;
  }
  return message;
}

function normalizeConfluenceDiagnostics(
  value: LivermoreSignalConfluencePayload["diagnostics"] | null | undefined,
): LivermoreConfluenceDiagnostic[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((item, index) => {
      if (typeof item === "string") {
        const message = translateConfluenceDiagnosticMessage(item.trim());
        return message
          ? {
              severity: "info",
              code: `message-${index}`,
              message,
            }
          : null;
      }
      if (!item || typeof item !== "object") {
        return null;
      }
      const message = typeof item.message === "string" ? translateConfluenceDiagnosticMessage(item.message.trim()) : "";
      if (!message) {
        return null;
      }
      return {
        severity: typeof item.severity === "string" && item.severity.trim() ? item.severity.trim() : "info",
        code: typeof item.code === "string" && item.code.trim() ? item.code.trim() : `message-${index}`,
        message,
      };
    })
    .filter((item): item is LivermoreConfluenceDiagnostic => item != null);
}

function visibleConfluenceDiagnostics(diagnostics: LivermoreConfluenceDiagnostic[]) {
  return diagnostics.filter(
    (item) =>
      item.code !== "observation_only" &&
      item.message !== defaultObservationOnlyDiagnostic &&
      item.message !== "仅供观察，不构成交易指令。",
  );
}

function confluenceDiagnosticCodeLabel(code: string) {
  if (/^message-\d+$/.test(code)) {
    return "";
  }
  if (code === "missing_macro_score") return "宏观缺数";
  if (code === "no_observations") return "暂无点位";
  return code;
}

function normalizeConfluenceDisclaimer(
  value: string | null | undefined,
  diagnostics: LivermoreConfluenceDiagnostic[],
) {
  const raw =
    (typeof value === "string" && value.trim()) ||
    diagnostics.find((item) => item.code === "observation_only")?.message ||
    "";
  if (!raw || raw === defaultObservationOnlyDiagnostic) {
    return "仅供观察，不构成交易指令。";
  }
  return raw;
}

function livermoreConfluenceStatusLabel(status: string | null | undefined) {
  if (status === "supportive") return "偏支持";
  if (status === "neutral") return "中性";
  if (status === "restrictive") return "偏收敛";
  if (status === "unknown") return "待确认";
  return status || "待确认";
}

function livermoreConfluenceActionLabel(action: string | null | undefined, triggered = false) {
  if (triggered) {
    return "退出观察已触发";
  }
  if (action === "observe_entry_setup") return "入场结构观察";
  if (action === "observe_only") return "仅观察";
  if (action === "observe_exit_watch") return "退出位观察";
  if (action === "exit_triggered") return "退出观察已触发";
  return action || "观察";
}

type LivermoreManualPositionDraft = {
  stockCode: string;
  stockName: string;
  entryCost: string;
  barsSinceEntry: string;
  positionQuantity: string;
};

function LivermoreManualPositionForm({
  onSubmit,
  asOfDate,
  isSubmitting,
  errorMessage,
  resultRowCount,
}: {
  onSubmit: (positions: LivermoreManualPositionInput[], asOfDate: string) => Promise<unknown>;
  asOfDate: string;
  isSubmitting: boolean;
  errorMessage: string | null;
  resultRowCount: number | null;
}) {
  const [draft, setDraft] = useState<LivermoreManualPositionDraft>({
    stockCode: "",
    stockName: "",
    entryCost: "",
    barsSinceEntry: "",
    positionQuantity: "",
  });
  const [localError, setLocalError] = useState<string | null>(null);

  const updateDraft = (key: keyof LivermoreManualPositionDraft, value: string) => {
    setDraft((current) => ({ ...current, [key]: value }));
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const stockCode = draft.stockCode.trim().toUpperCase();
    const stockName = draft.stockName.trim();
    const entryCost = Number.parseFloat(draft.entryCost);
    const barsSinceEntry = Number.parseInt(draft.barsSinceEntry, 10);
    const positionQuantityText = draft.positionQuantity.trim();
    const positionQuantity = positionQuantityText ? Number.parseFloat(positionQuantityText) : undefined;

    if (!stockCode) {
      setLocalError("请填写股票代码。");
      return;
    }
    if (!Number.isFinite(entryCost) || entryCost <= 0) {
      setLocalError("入场成本必须大于 0。");
      return;
    }
    if (!Number.isFinite(barsSinceEntry) || barsSinceEntry <= 0) {
      setLocalError("持有天数必须大于 0。");
      return;
    }
    if (positionQuantityText && (!Number.isFinite(positionQuantity) || Number(positionQuantity) < 0)) {
      setLocalError("持仓数量不能为负。");
      return;
    }

    const position: LivermoreManualPositionInput = {
      stockCode,
      entryCost,
      barsSinceEntry,
    };
    if (stockName) {
      position.stockName = stockName;
    }
    if (positionQuantity != null) {
      position.positionQuantity = positionQuantity;
    }

    setLocalError(null);
    await onSubmit([position], asOfDate);
  };

  return (
    <form className="cross-asset-livermore__manual-form" onSubmit={handleSubmit}>
      <div className="cross-asset-livermore__manual-header">
        <strong>录入持仓快照</strong>
        <span>写入后用于风险退出规则，不生成交易指令。</span>
      </div>
      <div className="cross-asset-livermore__manual-fields">
        <label>
          <span>股票代码</span>
          <input
            value={draft.stockCode}
            onChange={(event) => updateDraft("stockCode", event.target.value)}
            placeholder="000001.SZ"
          />
        </label>
        <label>
          <span>股票名称</span>
          <input
            value={draft.stockName}
            onChange={(event) => updateDraft("stockName", event.target.value)}
            placeholder="平安银行"
          />
        </label>
        <label>
          <span>入场成本</span>
          <input
            inputMode="decimal"
            value={draft.entryCost}
            onChange={(event) => updateDraft("entryCost", event.target.value)}
            placeholder="10.50"
          />
        </label>
        <label>
          <span>持有天数</span>
          <input
            inputMode="numeric"
            value={draft.barsSinceEntry}
            onChange={(event) => updateDraft("barsSinceEntry", event.target.value)}
            placeholder="6"
          />
        </label>
        <label>
          <span>持仓数量</span>
          <input
            inputMode="decimal"
            value={draft.positionQuantity}
            onChange={(event) => updateDraft("positionQuantity", event.target.value)}
            placeholder="10000"
          />
        </label>
      </div>
      <div className="cross-asset-livermore__manual-actions">
        <button type="submit" disabled={isSubmitting}>
          {isSubmitting ? "保存中" : "保存持仓"}
        </button>
        {resultRowCount != null ? (
          <span className="cross-asset-livermore__manual-success">已写入 {resultRowCount} 条持仓快照。</span>
        ) : null}
        {localError || errorMessage ? (
          <span className="cross-asset-livermore__manual-error">{localError ?? errorMessage}</span>
        ) : null}
      </div>
    </form>
  );
}

function LivermoreStrategyStatusPanel({
  payload,
  isLoading,
  isError,
  asOfDate,
  onManualSubmit,
  manualSubmitPending,
  manualSubmitError,
  manualResultRowCount,
}: {
  payload: LivermoreStrategyPayload | null;
  isLoading: boolean;
  isError: boolean;
  asOfDate: string;
  onManualSubmit: (positions: LivermoreManualPositionInput[], asOfDate: string) => Promise<unknown>;
  manualSubmitPending: boolean;
  manualSubmitError: string | null;
  manualResultRowCount: number | null;
}) {
  const gateReadiness = livermoreReadiness(payload, "market_gate");
  const candidatesReadiness = livermoreReadiness(payload, "stock_pivot");
  const riskReadiness = livermoreReadiness(payload, "risk_exit");
  const riskReason = livermoreUnsupportedReason(payload, "risk_exit");
  const riskClosed = Boolean(payload?.risk_exit) && !riskReason;
  const riskLabel = riskClosed
    ? `${payload?.risk_exit?.signal_count ?? 0}/${payload?.risk_exit?.position_count ?? 0}`
    : "缺持仓快照";
  const riskDetail = riskClosed
    ? `退出信号 ${payload?.risk_exit?.signal_count ?? 0} 条，覆盖持仓 ${payload?.risk_exit?.position_count ?? 0} 条。`
    : riskReason
      ? `position snapshot 输入未闭合：${riskReason}`
      : riskReadiness?.summary || "缺少 livermore_position_snapshot 持仓输入，风险退出规则无法闭环。";
  const candidateCount = payload?.stock_candidates?.candidate_count ?? 0;
  const manualAsOfDate = (payload?.as_of_date ?? asOfDate) || "";
  const requestedDate = manualAsOfDate || "待定";

  return (
    <section data-testid="cross-asset-livermore-status" className={`${crossAssetPanelClass} cross-asset-livermore`}>
      <div className="cross-asset-livermore__header">
        <div className="cross-asset-livermore__heading">
          <span className="cross-asset-livermore__eyebrow">股票策略</span>
          <h2 className="cross-asset-livermore__title">A股策略状态</h2>
          <p className="cross-asset-livermore__description">
            Livermore A-Share Defended Trend 当前只做分析读链路，先看输入是否足够支撑输出。
          </p>
        </div>
        <Link to="/market-data" className="cross-asset-livermore__link">
          市场数据
        </Link>
      </div>

      {isLoading ? (
        <div className="cross-asset-livermore__message">正在读取 Livermore 策略状态。</div>
      ) : isError ? (
        <div className="cross-asset-livermore__message cross-asset-livermore__message--warning">
          Livermore 策略状态加载失败。
        </div>
      ) : !payload ? (
        <div className="cross-asset-livermore__message cross-asset-livermore__message--warning">
          暂无 Livermore 策略状态。
        </div>
      ) : (
        <>
          <div className="cross-asset-livermore__grid">
            <div className="cross-asset-livermore__metric">
              <span className="cross-asset-livermore__label">市场门控</span>
              <strong className="cross-asset-livermore__value">{payload.market_gate.state}</strong>
              <small className="cross-asset-livermore__detail">
                {payload.market_gate.passed_conditions}/{payload.market_gate.required_conditions} 条通过 · 暴露{" "}
                {formatLivermoreExposure(payload.market_gate.exposure)} · {gateReadiness?.summary ?? "门控状态待定"}
              </small>
            </div>
            <div className="cross-asset-livermore__metric">
              <span className="cross-asset-livermore__label">个股候选</span>
              <strong className="cross-asset-livermore__value">{candidateCount}</strong>
              <small className="cross-asset-livermore__detail">
                {payload.supported_outputs.includes("stock_candidates") ? "候选筛选已就绪" : "候选筛选未开放"} ·{" "}
                {candidatesReadiness?.summary ?? "候选状态待定"}
              </small>
            </div>
            <div
              data-testid="cross-asset-livermore-risk-exit"
              className={`cross-asset-livermore__metric cross-asset-livermore__risk${
                riskClosed ? " cross-asset-livermore__risk--ready" : " cross-asset-livermore__risk--blocked"
              }`}
            >
              <span className="cross-asset-livermore__label">风险退出</span>
              <strong className="cross-asset-livermore__value">{riskLabel}</strong>
              <small className="cross-asset-livermore__detail">
                <b>{riskClosed ? "已闭环" : "未闭环"}</b> · {riskDetail}
              </small>
            </div>
          </div>
          <div className="cross-asset-livermore__footer">
            <span>日期 {requestedDate}</span>
            <span>分析口径 · 不生成交易指令</span>
            <span>输出 {payload.supported_outputs.length}/{payload.supported_outputs.length + payload.unsupported_outputs.length}</span>
          </div>
          <LivermoreManualPositionForm
            onSubmit={onManualSubmit}
            asOfDate={manualAsOfDate}
            isSubmitting={manualSubmitPending}
            errorMessage={manualSubmitError}
            resultRowCount={manualResultRowCount}
          />
        </>
      )}
    </section>
  );
}

function LivermoreSignalConfluencePanel({
  payload,
  isLoading,
  isError,
  asOfDate,
}: {
  payload: LivermoreSignalConfluencePayload | null;
  isLoading: boolean;
  isError: boolean;
  asOfDate: string;
}) {
  const diagnostics = normalizeConfluenceDiagnostics(payload?.diagnostics ?? null);
  const visibleDiagnostics = visibleConfluenceDiagnostics(diagnostics);
  const disclaimer = normalizeConfluenceDisclaimer(payload?.disclaimer, diagnostics);
  const macroStatus = livermoreConfluenceStatusLabel(payload?.macro_context?.status);
  const compositeScore = parseOptionalNumeric(payload?.macro_context?.composite_score);
  const marketGateState = payload?.strategy_context?.market_gate_state?.trim() || "待定";
  const strategyPositionSizeHint =
    parseOptionalNumeric(payload?.strategy_context?.position_size_hint) ?? parseOptionalNumeric(payload?.position_size_hint);
  const newEntryObservationAllowed =
    payload?.strategy_context?.new_entry_observation_allowed ??
    payload?.strategy_context?.allows_new_entry_observations ??
    false;
  const entryObservations: LivermoreConfluenceEntryObservation[] = (payload?.entry_observations ?? []).map((item, index) => ({
    action: livermoreConfluenceActionLabel(item?.action),
    stockCode: item?.stock_code?.trim() || `ENTRY-${index + 1}`,
    stockName: item?.stock_name?.trim() || "未命名标的",
    currentPrice: formatConfluencePrice(item?.current_price),
    triggerPrice: formatConfluencePrice(item?.buy_trigger_price ?? item?.trigger_price),
    invalidationReferencePrice: formatConfluencePrice(item?.invalidation_reference_price),
    positionSizeHint: formatLivermoreExposure(
      parseOptionalNumeric(item?.position_size_hint) ?? strategyPositionSizeHint,
    ),
    evidence: normalizeConfluenceEvidence(item?.evidence),
  }));
  const exitObservations: LivermoreConfluenceExitObservation[] = (payload?.exit_observations ?? []).map((item, index) => {
    const triggered = Boolean(item?.triggered) || item?.action === "exit_triggered";
    return {
      action: livermoreConfluenceActionLabel(item?.action, triggered),
      stockCode: item?.stock_code?.trim() || `EXIT-${index + 1}`,
      stockName: item?.stock_name?.trim() || "未命名标的",
      currentPrice: formatConfluencePrice(item?.current_price),
      exitWatchPrice: formatConfluencePrice(item?.exit_watch_price),
      triggered,
      evidence: normalizeConfluenceEvidence(item?.evidence),
    };
  });
  const hasObservations = entryObservations.length > 0 || exitObservations.length > 0;
  const resolvedDate = payload?.as_of_date?.trim() || asOfDate || "待定";

  return (
    <section
      data-testid="cross-asset-livermore-confluence"
      className={`${crossAssetPanelClass} cross-asset-livermore-confluence`}
    >
      <div className="cross-asset-livermore-confluence__header">
        <div className="cross-asset-livermore-confluence__heading">
          <span className="cross-asset-livermore-confluence__eyebrow">跨资产观察</span>
          <h2 className="cross-asset-livermore-confluence__title">宏观 × 策略观察点位</h2>
          <p className="cross-asset-livermore-confluence__description">
            同步宏观环境与 Livermore 观察位，只保留研究与复核所需的价格事实，不生成交易指令。
          </p>
        </div>
        <div className="cross-asset-livermore-confluence__meta">
          <span>日期 {resolvedDate}</span>
          <span>{disclaimer}</span>
        </div>
      </div>

      {isLoading ? (
        <div className="cross-asset-livermore-confluence__message">正在读取宏观 × 策略观察点位。</div>
      ) : isError ? (
        <div className="cross-asset-livermore-confluence__message cross-asset-livermore-confluence__message--warning">
          宏观 × 策略观察点位加载失败。
        </div>
      ) : !payload ? (
        <div className="cross-asset-livermore-confluence__message cross-asset-livermore-confluence__message--warning">
          暂无宏观 × 策略观察点位。
        </div>
      ) : (
        <>
          <div className="cross-asset-livermore-confluence__summary">
            <article className="cross-asset-livermore-confluence__summary-card">
              <span className="cross-asset-livermore-confluence__summary-label">宏观环境</span>
              <strong className="cross-asset-livermore-confluence__summary-value">{macroStatus}</strong>
              <small className="cross-asset-livermore-confluence__summary-detail">
                综合分 {compositeScore == null ? "待定" : compositeScore.toFixed(2)}
              </small>
            </article>
            <article className="cross-asset-livermore-confluence__summary-card">
              <span className="cross-asset-livermore-confluence__summary-label">市场门控</span>
              <strong className="cross-asset-livermore-confluence__summary-value">{marketGateState}</strong>
              <small className="cross-asset-livermore-confluence__summary-detail">
                {newEntryObservationAllowed ? "允许保留入场观察" : "仅保留观察，不追加新动作"}
              </small>
            </article>
            <article className="cross-asset-livermore-confluence__summary-card">
              <span className="cross-asset-livermore-confluence__summary-label">观察仓位提示</span>
              <strong className="cross-asset-livermore-confluence__summary-value">
                {formatLivermoreExposure(strategyPositionSizeHint)}
              </strong>
              <small className="cross-asset-livermore-confluence__summary-detail">{disclaimer}</small>
            </article>
          </div>

          {payload.macro_context?.description ? (
            <p className="cross-asset-livermore-confluence__context">{payload.macro_context.description}</p>
          ) : null}

          {visibleDiagnostics.length > 0 ? (
            <ul className="cross-asset-livermore-confluence__diagnostics">
              {visibleDiagnostics.map((item, index) => {
                const codeLabel = confluenceDiagnosticCodeLabel(item.code);
                return (
                  <li
                    key={`${item.code}-${item.message}-${index}`}
                    className={`cross-asset-livermore-confluence__diagnostic cross-asset-livermore-confluence__diagnostic--${item.severity}`}
                  >
                    {codeLabel ? (
                      <span className="cross-asset-livermore-confluence__diagnostic-code">{codeLabel}</span>
                    ) : null}
                    <span>{item.message}</span>
                  </li>
                );
              })}
            </ul>
          ) : null}

          {!hasObservations ? (
            <div className="cross-asset-livermore-confluence__empty">暂无可观察点位</div>
          ) : null}

          <div className="cross-asset-livermore-confluence__groups">
            <section className="cross-asset-livermore-confluence__group">
              <div className="cross-asset-livermore-confluence__group-header">
                <h3>入场观察</h3>
                <span>{entryObservations.length} 条</span>
              </div>
              {entryObservations.length === 0 ? (
                <div className="cross-asset-livermore-confluence__subempty">暂无入场观察。</div>
              ) : (
                <div className="cross-asset-livermore-confluence__list">
                  {entryObservations.map((item) => (
                    <article
                      key={`${item.stockCode}-${item.triggerPrice}`}
                      className="cross-asset-livermore-confluence__item"
                    >
                      <div className="cross-asset-livermore-confluence__item-header">
                        <div className="cross-asset-livermore-confluence__item-identity">
                          <span className="cross-asset-livermore-confluence__item-action">{item.action}</span>
                          <strong className="cross-asset-livermore-confluence__item-stock">
                            {item.stockName} · {item.stockCode}
                          </strong>
                        </div>
                      </div>
                      <dl className="cross-asset-livermore-confluence__metrics">
                        <div>
                          <dt>现价</dt>
                          <dd>{item.currentPrice}</dd>
                        </div>
                        <div>
                          <dt>候选触发价</dt>
                          <dd>{item.triggerPrice}</dd>
                        </div>
                        <div>
                          <dt>失效参考价</dt>
                          <dd>{item.invalidationReferencePrice}</dd>
                        </div>
                        <div>
                          <dt>观察仓位提示</dt>
                          <dd>{item.positionSizeHint}</dd>
                        </div>
                      </dl>
                      {item.evidence.length > 0 ? (
                        <ul className="cross-asset-livermore-confluence__evidence">
                          {item.evidence.map((evidence) => (
                            <li key={evidence}>{evidence}</li>
                          ))}
                        </ul>
                      ) : null}
                    </article>
                  ))}
                </div>
              )}
            </section>

            <section className="cross-asset-livermore-confluence__group">
              <div className="cross-asset-livermore-confluence__group-header">
                <h3>退出观察</h3>
                <span>{exitObservations.length} 条</span>
              </div>
              {exitObservations.length === 0 ? (
                <div className="cross-asset-livermore-confluence__subempty">暂无退出观察。</div>
              ) : (
                <div className="cross-asset-livermore-confluence__list">
                  {exitObservations.map((item) => (
                    <article
                      key={`${item.stockCode}-${item.exitWatchPrice}`}
                      className="cross-asset-livermore-confluence__item"
                    >
                      <div className="cross-asset-livermore-confluence__item-header">
                        <div className="cross-asset-livermore-confluence__item-identity">
                          <span
                            className={`cross-asset-livermore-confluence__item-action${
                              item.triggered ? " cross-asset-livermore-confluence__item-action--warning" : ""
                            }`}
                          >
                            {item.action}
                          </span>
                          <strong className="cross-asset-livermore-confluence__item-stock">
                            {item.stockName} · {item.stockCode}
                          </strong>
                        </div>
                      </div>
                      <dl className="cross-asset-livermore-confluence__metrics">
                        <div>
                          <dt>现价</dt>
                          <dd>{item.currentPrice}</dd>
                        </div>
                        <div>
                          <dt>退出观察价</dt>
                          <dd>{item.exitWatchPrice}</dd>
                        </div>
                      </dl>
                      {item.evidence.length > 0 ? (
                        <ul className="cross-asset-livermore-confluence__evidence">
                          {item.evidence.map((evidence) => (
                            <li key={evidence}>{evidence}</li>
                          ))}
                        </ul>
                      ) : null}
                    </article>
                  ))}
                </div>
              )}
            </section>
          </div>
        </>
      )}
    </section>
  );
}

function PercentileGauge({ sparkline }: { sparkline: number[] }) {
  const info = computeSparklinePercentile(sparkline);
  if (!info) return null;
  const markerColor = percentileZoneColor(info.zone);
  return (
    <div className="ca-percentile" title={`近期 ${sparkline.length} 日分位：第 ${info.percentile} 百分位`}>
      <div className="ca-percentile__track">
        <div
          className="ca-percentile__marker"
          style={{ left: `${info.percentile}%`, background: markerColor }}
        />
      </div>
      <span className="ca-percentile__label">{info.label}</span>
    </div>
  );
}

function MiniKpiCard({ kpi }: { kpi: ResolvedCrossAssetKpi }) {
  const stroke = sparkStroke[kpi.changeTone];
  return (
    <article className="cross-asset-drivers-page__mini-kpi" aria-label={kpi.label}>
      <div className="cross-asset-drivers-page__mini-kpi-main">
        <div className="cross-asset-drivers-page__mini-kpi-copy">
          <div className="cross-asset-drivers-page__mini-kpi-label">{kpi.label}</div>
          <div className="cross-asset-drivers-page__mini-kpi-value" style={tabularNumsStyle}>
            {kpi.valueLabel}
          </div>
          <div className="cross-asset-drivers-page__mini-kpi-delta" style={{ color: stroke }}>
            {kpi.changeLabel}
          </div>
          <PercentileGauge sparkline={kpi.sparkline} />
          {kpi.tag ? <div className="cross-asset-drivers-page__mini-kpi-tag">{kpi.tag}</div> : null}
        </div>
        <div className="cross-asset-drivers-page__mini-kpi-chart">
          <CrossAssetSparkline values={kpi.sparkline} stroke={stroke} height={40} />
        </div>
      </div>
    </article>
  );
}

function ResearchViewsPanel({ rows }: { rows: CrossAssetResearchViewCard[] }) {
  return (
    <section data-testid="cross-asset-research-views" className={`${crossAssetPanelClass} cross-asset-research-views`}>
      <div className="cross-asset-panel-head">
        <h2 className="cross-asset-drivers-page__panel-title">投资研究判断</h2>
        <p className="cross-asset-panel-note">
          第一屏先给出久期、曲线、信用和工具结论，再往下看证据和执行观察。
        </p>
      </div>
      <div className="cross-asset-research-views__grid">
        {rows.map((row) => (
          <article
            key={row.key}
            data-testid={`cross-asset-research-card-${row.key}`}
            className="cross-asset-research-views__card"
          >
            <div className="cross-asset-research-views__card-top">
              <div className="cross-asset-research-views__label">{row.label}</div>
              <div className="cross-asset-research-views__pills">
                <StatusPill status={row.status === "ready" ? "normal" : "caution"} label={researchStatusLabel(row.status)} />
                <StatusPill status={row.source === "backend" ? "normal" : "warning"} label={researchSourceLabel(row.source)} />
              </div>
            </div>
            <div className="cross-asset-drivers-page__chip-row">
              <StatusPill status="normal" label={row.stance} />
              <StatusPill status="caution" label={row.confidence} />
            </div>
            <p className="cross-asset-research-views__summary">{row.summary}</p>
            <div className="cross-asset-research-views__meta">
              影响对象：{row.affectedTargets.length > 0 ? formatImpactedViewsForDisplay(row.affectedTargets) : "待映射"}
            </div>
            {row.evidence.length > 0 ? (
              <div className="cross-asset-research-views__evidence">
                证据：{row.evidence[0]}
              </div>
            ) : null}
          </article>
        ))}
      </div>
    </section>
  );
}

function HeadlineKpiDeck({ kpis }: { kpis: ResolvedCrossAssetKpi[] }) {
  return (
    <div className="cross-asset-headline-kpis" data-testid="cross-asset-headline-kpis">
      {kpis.map((kpi) => (
        <MiniKpiCard key={kpi.key} kpi={kpi} />
      ))}
    </div>
  );
}

function NcdProxyEvidencePanel({
  evidence,
  isLoading,
}: {
  evidence: CrossAssetNcdProxyEvidence;
  isLoading?: boolean;
}) {
  const isProxyNotMatrix = !evidence.isActualNcdMatrix;
  return (
    <section
      data-testid="cross-asset-ncd-proxy"
      className={
        isProxyNotMatrix
          ? `${crossAssetPanelClass} cross-asset-drivers-page__panel--ncd-warn`
          : crossAssetPanelClass
      }
    >
      <div style={{ display: "flex", justifyContent: "space-between", gap: t.space[3], flexWrap: "wrap" }}>
        <h2 style={{ margin: 0, fontSize: t.fontSize[16], fontWeight: 700, color: t.color.neutral[900] }}>NCD / 资金代理</h2>
        {isLoading ? (
          <StatusPill status="caution" label="loading" />
        ) : (
          <StatusPill
            status={isProxyNotMatrix ? "warning" : "normal"}
            label={isProxyNotMatrix ? "proxy · not NCD matrix" : "actual matrix (verify)"}
          />
        )}
      </div>
      <p style={{ margin: `${t.space[2]}px 0 0`, color: t.color.neutral[600], fontSize: t.fontSize[12] }}>{evidence.proxyLabel}</p>
      {evidence.asOfDate ? (
        <p data-testid="cross-asset-ncd-asof" style={{ margin: `${t.space[1]}px 0 0`, color: t.color.neutral[500], fontSize: t.fontSize[12] }}>
          as of {evidence.asOfDate}
        </p>
      ) : null}
      <p
        data-testid="cross-asset-ncd-proxy-warning"
        style={{
          margin: `${t.space[3]}px 0 0`,
          color: isLoading ? t.color.neutral[500] : t.color.warning[800],
          fontSize: t.fontSize[13],
          lineHeight: t.lineHeight.relaxed,
        }}
      >
        {isLoading ? "正在加载资金代理…" : evidence.proxyWarning}
      </p>
      {evidence.rowCaptions.length > 0 ? (
        <ul
          data-testid="cross-asset-ncd-proxy-rows"
          style={{ margin: `${t.space[2]}px 0 0`, paddingLeft: t.space[5], color: t.color.neutral[700], fontSize: t.fontSize[12] }}
        >
          {evidence.rowCaptions.map((line) => (
            <li key={line} style={{ marginBottom: t.space[1] }}>
              {line}
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}

function TransmissionAxesPanel({ rows }: { rows: CrossAssetTransmissionAxisRow[] }) {
  return (
    <section data-testid="cross-asset-transmission-axes" className={`${crossAssetPanelClass} cross-asset-transmission-axes`}>
      <div className="cross-asset-panel-head">
        <h2 className="cross-asset-drivers-page__panel-title">传导主线</h2>
        <p className="cross-asset-panel-note">
          缺数据的主线会标为「待信号」，不会用无关序列去硬猜结论。
        </p>
      </div>
      <div className="cross-asset-transmission-axes__grid">
        {rows.map((row) => (
          <article
            key={row.axisKey}
            data-testid={`cross-asset-transmission-axis-${row.axisKey}`}
            className={`cross-asset-transmission-axes__card${
              row.status === "pending_signal" ? " cross-asset-transmission-axes__card--pending" : ""
            }`}
          >
            <div className="cross-asset-transmission-axes__card-top">
              <div className="cross-asset-transmission-axes__label">{row.label}</div>
              <div className="cross-asset-transmission-axes__pills">
                <StatusPill
                  status={row.status === "ready" ? "normal" : "caution"}
                  label={row.status === "ready" ? "已就绪" : "待信号"}
                />
                <StatusPill status={row.source === "backend" ? "normal" : "warning"} label={row.source === "backend" ? "后端" : "兜底"} />
              </div>
            </div>
            <div className="cross-asset-drivers-page__chip-row">
              <StatusPill status={row.status === "ready" ? "normal" : "warning"} label={row.stanceLabel} />
              {row.impactedViews.length > 0 ? (
                <StatusPill status="caution" label={`影响：${formatImpactedViewsForDisplay(row.impactedViews)}`} />
              ) : null}
            </div>
            <p className="cross-asset-transmission-axes__summary">{row.summary}</p>
            {row.requiredSeriesIds.length > 0 ? (
              <div className="cross-asset-transmission-axes__meta">
                依赖序列：{row.requiredSeriesIds.join("、")}
              </div>
            ) : null}
            {row.warnings.length > 0 ? (
              <div className="cross-asset-transmission-axes__warning">{row.warnings[0]}</div>
            ) : null}
          </article>
        ))}
      </div>
    </section>
  );
}

function resolveAssetBondJudgmentHeadline(stockTone: string, commodityTone: string, pendingLineCount: number) {
  if (stockTone === UI.restrictive && commodityTone === UI.neutral) {
    return "\u80a1\u7968\u94fe\u6761\u538b\u5236\u98ce\u9669\u504f\u597d\uff0c\u5546\u54c1\u94fe\u6761\u6682\u4e0d\u5f3a\u5316\u901a\u80c0\u4ea4\u6613\u3002";
  }
  if (stockTone === UI.restrictive && commodityTone === UI.supportive) {
    return "\u98ce\u9669\u504f\u597d\u627f\u538b\u4f46\u5546\u54c1\u4ecd\u6709\u901a\u80c0\u6270\u52a8\uff0c\u503a\u5238\u5224\u65ad\u9700\u770b\u5229\u7387\u4e3b\u7ebf\u786e\u8ba4\u3002";
  }
  if (stockTone === UI.supportive && commodityTone === UI.neutral) {
    return "\u98ce\u9669\u504f\u597d\u6539\u5584\uff0c\u5546\u54c1\u7aef\u4e2d\u6027\uff0c\u503a\u5238\u538b\u529b\u6682\u4e0d\u6765\u81ea\u8de8\u8d44\u4ea7\u5171\u632f\u3002";
  }
  if (pendingLineCount > 0) {
    return "\u5df2\u63a5\u5165\u4fe1\u53f7\u5148\u7ea6\u675f\u98ce\u9669\u504f\u597d\u4e0e\u901a\u80c0\u65b9\u5411\uff0c\u5f85\u63a5\u5165\u9879\u53ea\u9650\u5b9a\u7f6e\u4fe1\u5ea6\u3002";
  }
  return "\u8de8\u8d44\u4ea7\u8bc1\u636e\u53ef\u8fdb\u5165\u503a\u5238\u4f20\u5bfc\u5224\u65ad\uff0c\u7ee7\u7eed\u8ddf\u8e2a\u65b9\u5411\u5171\u632f\u3002";
}

function buildAssetBondJudgment(input: {
  stockRow: CrossAssetClassAnalysisRow | undefined;
  commodityRow: CrossAssetClassAnalysisRow | undefined;
  optionsRow: CrossAssetClassAnalysisRow | undefined;
  pendingLineCount: number;
}) {
  const stockTone = input.stockRow ? assetDirectionLabel(input.stockRow.direction) : UI.pending;
  const commodityTone = input.commodityRow ? assetDirectionLabel(input.commodityRow.direction) : UI.pending;
  const optionsTone =
    input.optionsRow?.status === "ready" ? assetDirectionLabel(input.optionsRow.direction) : UI.pending;
  const boundary =
    input.pendingLineCount > 0
      ? `\u5f53\u524d\u4ecd\u6709 ${input.pendingLineCount} \u9879\u5f85\u63a5\u5165\uff0c\u7f3a\u53e3\u53ea\u964d\u4f4e\u7ed3\u8bba\u7f6e\u4fe1\u5ea6\uff0c\u4e0d\u7528\u76f8\u90bb\u8d44\u4ea7\u66ff\u4ee3\u3002`
      : "\u5f53\u524d\u5f85\u63a5\u5165\u7f3a\u53e3\u8f83\u5c11\uff0c\u53ef\u66f4\u76f4\u63a5\u8ffd\u8e2a\u8de8\u8d44\u4ea7\u5171\u632f\u5bf9\u503a\u5238\u7684\u4f20\u5bfc\u3002";

  return {
    headline: resolveAssetBondJudgmentHeadline(stockTone, commodityTone, input.pendingLineCount),
    summary: `${input.stockRow?.label ?? UI.stock}${stockTone}${UI.joiner}${
      input.commodityRow?.label ?? UI.commodity
    }${commodityTone}${UI.joiner}${input.optionsRow?.label ?? UI.options}${optionsTone}\u3002${boundary}`,
    items: [
      {
        key: "stock",
        label: input.stockRow?.label ?? UI.stock,
        tone: stockTone,
        direction: input.stockRow?.direction ?? "pending",
        detail:
          input.stockRow?.explanation ??
          "\u80a1\u7968\u94fe\u6761\u6682\u65e0\u6cbb\u7406\u540e\u8f93\u5165\uff0c\u4e0d\u8fdb\u5165\u503a\u5238\u4e3b\u5224\u65ad\u3002",
      },
      {
        key: "commodities",
        label: input.commodityRow?.label ?? UI.commodity,
        tone: commodityTone,
        direction: input.commodityRow?.direction ?? "pending",
        detail:
          input.commodityRow?.explanation ??
          "\u5546\u54c1\u94fe\u6761\u6682\u65e0\u6cbb\u7406\u540e\u8f93\u5165\uff0c\u4e0d\u653e\u5927\u901a\u80c0\u6216\u9700\u6c42\u5224\u65ad\u3002",
      },
      {
        key: "options",
        label: input.optionsRow?.label ?? UI.options,
        tone: optionsTone,
        direction: input.optionsRow?.status === "ready" ? input.optionsRow.direction : "pending",
        detail:
          input.optionsRow?.status === "ready"
            ? input.optionsRow.explanation
            : "\u671f\u6743\u548c\u6ce2\u52a8\u7387\u53e3\u5f84\u5c1a\u5728\u5f85\u63a5\u5165\u6e05\u5355\uff0c\u53ea\u4f5c\u4e3a\u98ce\u9669\u4fe1\u53f7\u7f3a\u53e3\u63d0\u793a\u3002",
      },
    ],
  };
}

function AssetClassAnalysisPanel({
  rows,
  equityEvidenceItems,
}: {
  rows: CrossAssetClassAnalysisRow[];
  equityEvidenceItems: CrossAssetEquityEvidenceItem[];
}) {
  const stockRow = rows.find((row) => row.key === "stock");
  const commodityRow = rows.find((row) => row.key === "commodities");
  const optionsRow = rows.find((row) => row.key === "options");
  const readyRows = rows.filter((row) => row.status === "ready");
  const primaryRows = readyRows;
  const pendingGroups = rows
    .map((row) => ({
      row,
      lines: row.lines.filter((line) => line.status !== "ready"),
    }))
    .filter((group) => group.lines.length > 0);
  const pendingLineCount = pendingGroups.reduce((count, group) => count + group.lines.length, 0);
  const verdictParts = [
    stockRow ? `${UI.stock}${assetDirectionLabel(stockRow.direction)}` : "",
    commodityRow ? `${UI.commodity}${assetDirectionLabel(commodityRow.direction)}` : "",
    optionsRow ? `${UI.options}${optionsRow.status === "ready" ? assetDirectionLabel(optionsRow.direction) : UI.pending}` : "",
  ].filter(Boolean);
  const bondJudgment = buildAssetBondJudgment({ stockRow, commodityRow, optionsRow, pendingLineCount });

  return (
    <section data-testid="cross-asset-asset-class-analysis" className="cross-asset-class-analysis">
      <div className="cross-asset-class-analysis__header">
        <div className="cross-asset-class-analysis__eyebrow">{UI.verdictKicker}</div>
        <h2 className="cross-asset-class-analysis__title">{verdictParts.join(UI.joiner)}</h2>
        <p className="cross-asset-class-analysis__description">{UI.verdictDescription}</p>
      </div>
      <div className="cross-asset-class-analysis__body">
        <div className="cross-asset-class-analysis__primary">
          <div className="cross-asset-class-analysis__column-head">
            <span>{UI.readyJudgment}</span>
            <span>{readyRows.length}/{rows.length}</span>
          </div>
          <div className="cross-asset-class-analysis__cards">
            {primaryRows.map((row) => (
              <article
                key={row.key}
                data-testid={`cross-asset-asset-analysis-${row.key}`}
                className="cross-asset-class-analysis__card"
              >
                <div className="cross-asset-class-analysis__card-header">
                  <div>
                    <div className="cross-asset-class-analysis__card-title">{row.label}</div>
                    <div className="cross-asset-class-analysis__card-subtitle">{analysisStatusLabel(row.status)}</div>
                  </div>
                  <span
                    className={`cross-asset-class-analysis__direction cross-asset-class-analysis__direction--${directionClassName(row.direction)}`}
                  >
                    {assetDirectionLabel(row.direction)}
                  </span>
                </div>
                <p className="cross-asset-class-analysis__summary">{row.explanation}</p>
                <div className="cross-asset-class-analysis__lines">
                  {row.lines.map((line) => (
                    <div
                      key={line.key}
                      data-testid={`cross-asset-asset-analysis-${row.key}-${line.key}`}
                      className={`cross-asset-class-analysis__line${
                        line.status === "ready" ? "" : " cross-asset-class-analysis__line--pending"
                      }`}
                    >
                      <div className="cross-asset-class-analysis__line-header">
                        <span className="cross-asset-class-analysis__line-title">{line.label}</span>
                        <span className="cross-asset-class-analysis__line-status">{lineStatusLabel(line.stateLabel)}</span>
                      </div>
                      <div className="cross-asset-class-analysis__line-source" title={line.sourceLabel}>
                        <strong>{line.dataLabel}</strong>
                      </div>
                      <p className="cross-asset-class-analysis__line-explanation">{line.explanation}</p>
                    </div>
                  ))}
                </div>
                {row.key === "stock" ? (
                  <div className="cross-asset-class-analysis__evidence" data-testid="cross-asset-equity-evidence">
                    {equityEvidenceItems.map((item) => (
                      <div
                        key={item.key}
                        className={`cross-asset-class-analysis__evidence-item${
                          item.status === "ready" ? "" : ` cross-asset-class-analysis__evidence-item--${item.status}`
                        }`}
                        data-testid={`cross-asset-equity-evidence-${item.key}`}
                        title={item.sourceLabel}
                      >
                        <span>{item.label}</span>
                        <strong>{item.valueLabel}</strong>
                        <small>
                          {evidenceStatusLabel(item.status)} · {item.changeLabel} · {item.unitLabel} · {item.tradeDate ?? "—"} ·{" "}
                          {item.sourceLabel}
                        </small>
                      </div>
                    ))}
                  </div>
                ) : null}
              </article>
            ))}
            <div className="cross-asset-class-analysis__judgment" data-testid="cross-asset-asset-class-judgment">
              <div className="cross-asset-class-analysis__judgment-kicker">{UI.bondTransmissionJudgment}</div>
              <h3 className="cross-asset-class-analysis__judgment-title">{bondJudgment.headline}</h3>
              <p className="cross-asset-class-analysis__judgment-summary">{bondJudgment.summary}</p>
              <div className="cross-asset-class-analysis__judgment-items">
                {bondJudgment.items.map((item) => (
                  <div key={item.key} className="cross-asset-class-analysis__judgment-item">
                    <div className="cross-asset-class-analysis__judgment-item-head">
                      <span>{item.label}</span>
                      <strong
                        className={`cross-asset-class-analysis__judgment-tone cross-asset-class-analysis__direction--${directionClassName(item.direction)}`}
                      >
                        {item.tone}
                      </strong>
                    </div>
                    <p>{item.detail}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        <aside className="cross-asset-class-analysis__pending">
          <div className="cross-asset-class-analysis__column-head">
            <span>{UI.pendingList}</span>
            <span>{pendingLineCount} {UI.items}</span>
          </div>
          {pendingGroups.map(({ row, lines }) => {
            const hasPrimaryCard = primaryRows.some((primaryRow) => primaryRow.key === row.key);
            const testIdSuffix = hasPrimaryCard ? "-pending" : "";
            return (
              <article
                key={row.key}
                data-testid={`cross-asset-asset-analysis-${row.key}${testIdSuffix}`}
                className="cross-asset-class-analysis__pending-card"
              >
                <div className="cross-asset-class-analysis__card-header">
                  <div>
                    <div className="cross-asset-class-analysis__card-title">{row.label}</div>
                    <div className="cross-asset-class-analysis__card-subtitle">{analysisStatusLabel(row.status)}</div>
                  </div>
                  <span className="cross-asset-class-analysis__direction cross-asset-class-analysis__direction--pending">
                    {UI.pending}
                  </span>
                </div>
                <p className="cross-asset-class-analysis__summary">{row.explanation}</p>
                <div className="cross-asset-class-analysis__pending-lines">
                  {lines.map((line) => (
                    <div
                      key={line.key}
                      data-testid={`cross-asset-asset-analysis-${row.key}-${line.key}${testIdSuffix}`}
                      className="cross-asset-class-analysis__pending-line"
                      title={line.sourceLabel}
                    >
                      <span>{line.label}</span>
                      <span>{assetDirectionLabel(line.direction)}</span>
                      <small>
                        {lineStatusLabel(line.stateLabel)} · {line.dataLabel}
                      </small>
                    </div>
                  ))}
                </div>
              </article>
            );
          })}
          <p className="cross-asset-class-analysis__pending-note">{UI.pendingNote}</p>
        </aside>
      </div>
    </section>
  );
}

const UI = {
  verdictKicker: "\u8de8\u8d44\u4ea7\u7ed3\u8bba",
  verdictDescription:
    "\u53cc\u6570\u636e\u6765\u6e90\u53e3\u5f84\uff1aChoice \u63a5\u5165\u7801\u4e0e Tushare/\u516c\u5171\u8865\u5145\u6e90\u5e76\u5217\u5c55\u793a\uff1b\u5df2\u63a5\u5165\u8bc1\u636e\u8fdb\u5165\u4e3b\u5224\u65ad\uff0c\u7f3a\u53e3\u6536\u655b\u5230\u5f85\u63a5\u5165\u6e05\u5355\u3002",
  readyJudgment: "\u5df2\u5f62\u6210\u5224\u65ad",
  bondTransmissionJudgment: "\u503a\u5238\u4f20\u5bfc\u5224\u65ad",
  pendingList: "\u5f85\u63a5\u5165\u6e05\u5355",
  pendingNote:
    "\u671f\u6743\u3001\u6ce2\u52a8\u7387\u548c\u90e8\u5206\u5546\u54c1\u94fe\u6761\u4ecd\u6309\u5f85\u786e\u8ba4\u5904\u7406\uff1b\u7f3a\u53e3\u4f18\u5148\u8865 Choice \u63a5\u5165\u7801\uff0c\u4e5f\u53ef\u63a5 Tushare/\u516c\u5171\u8865\u5145\u6cbb\u7406\u6e90\uff0c\u4e0d\u7528\u76f8\u90bb\u8d44\u4ea7\u66ff\u4ee3\u3002",
  stock: "\u80a1\u7968",
  commodity: "\u5546\u54c1",
  options: "\u671f\u6743",
  pending: "\u5f85\u63a5\u5165",
  dataReady: "\u6570\u636e\u53ef\u7528",
  inputPending: "\u8f93\u5165\u5f85\u63a5\u5165",
  supportive: "\u652f\u6491",
  restrictive: "\u538b\u5236",
  neutral: "\u4e2d\u6027",
  conflicted: "\u5206\u6b67",
  joiner: "\uff0c",
  items: "\u9879",
} as const;

function analysisStatusLabel(status: CrossAssetClassAnalysisRow["status"]) {
  return status === "ready" ? UI.dataReady : UI.inputPending;
}

function lineStatusLabel(stateLabel: CrossAssetClassAnalysisLine["stateLabel"]) {
  const labels: Record<CrossAssetClassAnalysisLine["stateLabel"], string> = {
    ready: "已就绪",
    stale: "可能陈旧",
    source_blocked: "来源受限",
    missing_dependency: "缺少依赖",
    pending_definition: "定义待确认",
  };
  return labels[stateLabel];
}

function researchStatusLabel(status: CrossAssetResearchViewCard["status"]) {
  return status === "ready" ? "已就绪" : "待信号";
}

function researchSourceLabel(source: CrossAssetResearchViewCard["source"]) {
  if (source === "backend") {
    return "后端";
  }
  return source === "unavailable" ? "待确认" : "兜底";
}

function evidenceStatusLabel(status: CrossAssetEquityEvidenceItem["status"]) {
  const labels: Record<CrossAssetEquityEvidenceItem["status"], string> = {
    ready: "已就绪",
    stale: "可能陈旧",
    fallback: "降级",
    source_blocked: "来源受限",
    missing_dependency: "缺少依赖",
  };
  return labels[status];
}

function assetDirectionLabel(direction: string) {
  const normalized = direction.toLowerCase();
  if (normalized.includes("supportive")) {
    return UI.supportive;
  }
  if (normalized.includes("restrictive")) {
    return UI.restrictive;
  }
  if (normalized.includes("neutral")) {
    return UI.neutral;
  }
  if (normalized.includes("conflicted")) {
    return UI.conflicted;
  }
  if (normalized.includes("pending") || normalized.includes("definition")) {
    return UI.pending;
  }
  return direction;
}

function directionClassName(direction: string) {
  const normalized = direction.toLowerCase();
  if (normalized.includes("supportive")) {
    return "supportive";
  }
  if (normalized.includes("restrictive")) {
    return "restrictive";
  }
  if (normalized.includes("conflicted")) {
    return "conflicted";
  }
  if (normalized.includes("pending") || normalized.includes("definition")) {
    return "pending";
  }
  return "neutral";
}
function MarketRegimePanel({ kpis }: { kpis: ResolvedCrossAssetKpi[] }) {
  const regime = useMemo(() => identifyMarketRegime(kpis), [kpis]);
  return (
    <div
      className="ca-regime"
      style={{ background: regime.bgColor, borderColor: regime.color + "40" }}
      data-testid="cross-asset-regime-indicator"
    >
      <span className="ca-regime__icon">{regime.icon}</span>
      <div className="ca-regime__body">
        <div className="ca-regime__label" style={{ color: regime.color }}>
          当前体制：{regime.label}
        </div>
        <div className="ca-regime__desc" style={{ color: regime.color }}>
          {regime.description}
        </div>
      </div>
    </div>
  );
}

function CorrelationHeatmapPanel({ matrix }: { matrix: CorrelationMatrix }) {
  if (matrix.keys.length < 2) return null;
  const n = matrix.keys.length;
  return (
    <section className="ca-correlation" data-testid="cross-asset-correlation-heatmap">
      <h2 className="ca-correlation__title">资产相关性矩阵</h2>
      <p className="ca-correlation__subtitle">
        基于 sparkline 窗口滚动 Pearson 相关系数，一眼看清哪些资产在共振或背离。
      </p>
      <div className="ca-correlation__matrix-wrap" data-testid="cross-asset-correlation-matrix-wrap">
        <div
          className="ca-correlation__grid"
          style={{ gridTemplateColumns: `92px repeat(${n}, minmax(54px, 1fr))` }}
        >
        {/* Top-left corner: empty */}
        <div className="ca-correlation__cell ca-correlation__cell--header" />
        {/* Column headers */}
        {matrix.labels.map((label) => (
          <div key={`col-${label}`} className="ca-correlation__cell ca-correlation__cell--header ca-correlation__cell--header-top">
            {label}
          </div>
        ))}
        {/* Rows */}
        {matrix.cells.map((row, ri) => (
          <div key={`row-group-${matrix.keys[ri]}`} style={{ display: "contents" }}>
            <div className="ca-correlation__cell ca-correlation__cell--header">
              {matrix.labels[ri]}
            </div>
            {row.map((cell, ci) => {
              const isDiag = ri === ci;
              return (
                <div
                  key={`${cell.rowKey}-${cell.colKey}`}
                  className={`ca-correlation__cell${isDiag ? " ca-correlation__cell--diagonal" : ""}`}
                  style={{
                    background: isDiag ? undefined : correlationColor(cell.value),
                    color: cell.value != null && Math.abs(cell.value) > 0.5 ? "var(--ca-on-dark)" : undefined,
                  }}
                  title={`${matrix.labels[ri]} × ${matrix.labels[ci]}: ${formatCorrelation(cell.value)}`}
                >
                  {isDiag ? "1" : formatCorrelation(cell.value)}
                </div>
              );
            })}
          </div>
        ))}
        </div>
      </div>
      <div className="ca-correlation__legend">
        <span>−1</span>
        <div className="ca-correlation__legend-bar" />
        <span>+1</span>
        <span style={{ marginLeft: 8 }}>负相关 ← 中性 → 正相关</span>
      </div>
    </section>
  );
}

function MomentumScoreboardPanel({ rows }: { rows: MomentumRow[] }) {
  if (rows.length === 0) return null;

  function fmtChg(v: number | null) {
    if (v == null) return "—";
    const sign = v > 0 ? "+" : "";
    return `${sign}${v.toFixed(2)}%`;
  }

  function chgClass(v: number | null) {
    if (v == null || Math.abs(v) < 0.001) return "ca-momentum__chg--neutral";
    return v > 0 ? "ca-momentum__chg--positive" : "ca-momentum__chg--negative";
  }

  function dirArrow(d: MomentumRow["direction"]) {
    if (d === "up") return "↑";
    if (d === "down") return "↓";
    return "→";
  }

  function accelLabel(a: MomentumRow["acceleration"]) {
    if (a === "accelerating") return "加速";
    if (a === "decelerating") return "减速";
    return "稳定";
  }

  return (
    <section className="ca-momentum" data-testid="cross-asset-momentum-scoreboard">
      <h2 className="ca-momentum__title">跨资产动量计分板</h2>
      <p className="ca-momentum__subtitle">各资产的 1日/5日/20日 涨跌幅，方向箭头与加速/减速标记。</p>
      <div className="ca-momentum__table-wrap" data-testid="cross-asset-momentum-table-wrap">
        <table className="ca-momentum__table">
        <thead>
          <tr>
            <th>资产</th>
            <th>方向</th>
            <th>1日</th>
            <th>5日</th>
            <th>20日</th>
            <th>动能</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.key}>
              <td>
                <span className="ca-momentum__asset-name">{row.label}</span>
                <span className="ca-momentum__tag">{row.tag}</span>
              </td>
              <td>
                <span className={`ca-momentum__dir ca-momentum__dir--${row.direction}`}>
                  {dirArrow(row.direction)}
                </span>
              </td>
              <td className={chgClass(row.chg1d)}>{fmtChg(row.chg1d)}</td>
              <td className={chgClass(row.chg5d)}>{fmtChg(row.chg5d)}</td>
              <td className={chgClass(row.chg20d)}>{fmtChg(row.chg20d)}</td>
              <td>
                <span className={`ca-momentum__accel ca-momentum__accel--${row.acceleration}`}>
                  {accelLabel(row.acceleration)}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
        </table>
      </div>
    </section>
  );
}

function TrendGroupToggle({
  active,
  onChange,
}: {
  active: TrendGroupKey;
  onChange: (key: TrendGroupKey) => void;
}) {
  return (
    <div className="ca-trend-groups" data-testid="cross-asset-trend-groups">
      {TREND_GROUPS.map((g) => (
        <button
          key={g.key}
          className={`ca-trend-groups__btn${active === g.key ? " ca-trend-groups__btn--active" : ""}`}
          onClick={() => onChange(g.key)}
          type="button"
        >
          {g.label}
        </button>
      ))}
    </div>
  );
}

function VolatilityClusteringPanel({ alert }: { alert: VolatilityAlert }) {
  const severityLabel: Record<VolatilityAlert["severity"], string> = {
    normal: "正常",
    elevated: "偏高",
    critical: "警告",
  };
  return (
    <section
      className={`ca-vol-alert ca-vol-alert--${alert.severity}`}
      data-testid="cross-asset-vol-alert"
    >
      <div className="ca-vol-alert__header">
        <h2 className="ca-vol-alert__title">波动率聚类</h2>
        <span className={`ca-vol-alert__badge ca-vol-alert__badge--${alert.severity}`}>
          {severityLabel[alert.severity]}
        </span>
      </div>
      <p className="ca-vol-alert__headline">{alert.headline}</p>
      {alert.assets.length > 0 ? (
        <div className="ca-vol-alert__bars">
          {alert.assets.map((a) => {
            const fillPct = Math.min(100, (a.volRatio / 3) * 100);
            const fillColor = a.isElevated ? "var(--ca-warning-fill)" : "var(--ca-neutral-fill)";
            return (
              <div
                key={a.key}
                className={`ca-vol-alert__bar-item${a.isElevated ? " ca-vol-alert__bar-item--elevated" : ""}`}
              >
                <div className="ca-vol-alert__bar-label">{a.label}</div>
                <div className="ca-vol-alert__bar-track">
                  <div
                    className="ca-vol-alert__bar-fill"
                    style={{ width: `${fillPct}%`, background: fillColor }}
                  />
                </div>
                <div className="ca-vol-alert__bar-value">
                  {a.volRatio.toFixed(2)}× {a.isElevated ? "⚡" : ""}
                </div>
              </div>
            );
          })}
        </div>
      ) : null}
    </section>
  );
}

function EquityBondERPPanel({ erp }: { erp: EquityBondERP }) {
  // Map ERP to a gauge position (0-100)
  // ERP range roughly -2 to 6; map 0% = -2, 100% = 6
  const gaugeMin = -2;
  const gaugeMax = 6;
  const gaugePct = erp.erpPct != null
    ? Math.max(0, Math.min(100, ((erp.erpPct - gaugeMin) / (gaugeMax - gaugeMin)) * 100))
    : 50;

  return (
    <section
      className="ca-erp"
      style={{ background: erp.verdictBg, borderColor: erp.verdictColor + "30" }}
      data-testid="cross-asset-erp-gauge"
    >
      <div className="ca-erp__header">
        <h2 className="ca-erp__title">股债性价比</h2>
        <span
          className="ca-erp__verdict-pill"
          style={{ background: erp.verdictColor + "18", color: erp.verdictColor }}
        >
          {erp.verdictLabel}
        </span>
      </div>
      {erp.available ? (
        <>
          <div className="ca-erp__metrics">
            <div className="ca-erp__metric">
              <div className="ca-erp__metric-label">盈利收益率</div>
              <div className="ca-erp__metric-value" style={{ color: t.color.neutral[900] }}>
                {erp.earningsYieldPct?.toFixed(2)}%
              </div>
            </div>
            <div className="ca-erp__metric">
              <div className="ca-erp__metric-label">10Y国债</div>
              <div className="ca-erp__metric-value" style={{ color: t.color.neutral[900] }}>
                {erp.bondYieldPct?.toFixed(2)}%
              </div>
            </div>
            <div className="ca-erp__metric">
              <div className="ca-erp__metric-label">ERP</div>
              <div className="ca-erp__metric-value" style={{ color: erp.verdictColor }}>
                {erp.erpPct?.toFixed(2)}%
              </div>
            </div>
          </div>
          <div>
            <div className="ca-erp__gauge-track">
              <div
                className="ca-erp__gauge-marker"
                style={{ left: `${gaugePct}%`, background: erp.verdictColor }}
              />
            </div>
            <div className="ca-erp__gauge-labels">
              <span>股票贵</span>
              <span>中性</span>
              <span>股票便宜</span>
            </div>
          </div>
        </>
      ) : null}
      <p className="ca-erp__desc">{erp.verdictDescription}</p>
    </section>
  );
}

type WaterfallEvidenceStatus = "ready" | "neutral" | "missing" | "total";

const WATERFALL_FACTOR_CATEGORY: Record<string, string> = {
  liquidity: "liquidity",
  rate: "rate",
  growth: "growth",
  inflation: "inflation",
};

const WATERFALL_MISSING_REASON: Record<string, string> = {
  liquidity: "SHIBOR/回购等流动性序列历史样本不足，后端未形成流动性贡献。",
  growth: "工业增加值/GDP 等增长序列历史样本不足，后端未形成增长贡献。",
  inflation: "通胀序列缺少可用最新点，后端未形成通胀贡献。",
  rate: "利率期限序列历史样本不足，后端未形成利率贡献。",
};

function factorTextValue(value: unknown) {
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(2) : null;
}

function waterfallFactorEvidence(
  bar: WaterfallBar,
  env: Partial<MacroBondLinkageEnvironmentScore>,
): { status: WaterfallEvidenceStatus; label: string; reason: string } {
  if (bar.kind === "total") {
    return {
      status: "total",
      label: "综合",
      reason: "综合分按利率、流动性、增长、通胀权重汇总；缺少有效因子的子项当前按 0 进入汇总。",
    };
  }

  const category = WATERFALL_FACTOR_CATEGORY[bar.key] ?? bar.key;
  const factors = (env.contributing_factors ?? []).filter((factor) => String(factor.category ?? "") === category);
  const hasEvidence = factors.length > 0;
  const isFlat = Math.abs(bar.value) < 0.005;

  if (!hasEvidence && isFlat) {
    return {
      status: "missing",
      label: "样本不足",
      reason: WATERFALL_MISSING_REASON[category] ?? "该因子没有进入 contributing_factors，当前按 0 展示。",
    };
  }

  if (isFlat) {
    const factor = factors[0];
    const latestValue = factorTextValue(factor?.latest_value);
    const seriesName = typeof factor?.series_name === "string" ? factor.series_name : bar.label;
    return {
      status: "neutral",
      label: "中性",
      reason: latestValue
        ? `${seriesName} 最新值 ${latestValue}，规则判为中性贡献 0。`
        : `${bar.label} 有有效输入，但标准化后贡献接近 0。`,
    };
  }

  const factorCount = factors.length;
  return {
    status: "ready",
    label: factorCount > 0 ? `${factorCount} 项证据` : "有分值",
    reason:
      factorCount > 0
        ? `${bar.label} 已进入环境评分，贡献 ${bar.value.toFixed(2)}。`
        : `${bar.label} 接口返回了分值，但未展开 contributing_factors 明细。`,
  };
}

function DriverWaterfallPanel({
  bars,
  env,
}: {
  bars: WaterfallBar[];
  env: Partial<MacroBondLinkageEnvironmentScore>;
}) {
  if (bars.length === 0) return null;

  const maxAbs = Math.max(
    ...bars.map((b) => Math.abs(b.value)),
    0.01, // prevent division by zero
  );
  const chartHeight = 120; // px available for bars

  return (
    <section className="ca-waterfall" data-testid="cross-asset-driver-waterfall">
      <h2 className="ca-waterfall__title">驱动力归因瀑布</h2>
      <p className="ca-waterfall__subtitle">
        环境综合评分由各子因子累加构成，正值利好债市，负值利空。
      </p>
      <div className="ca-waterfall__chart">
        <div className="ca-waterfall__zero-line" style={{ bottom: `${chartHeight / 2 + 28}px` }} />
        {bars.map((bar) => {
          const evidence = waterfallFactorEvidence(bar, env);
          const barHeight = Math.max(4, (Math.abs(bar.value) / maxAbs) * (chartHeight / 2));
          const isNeg = bar.value < 0;
          const isTotal = bar.kind === "total";
          const sign = bar.value > 0 ? "+" : "";
          const valueLabel = evidence.status === "missing" ? "缺数据" : `${sign}${bar.value.toFixed(2)}`;

          return (
            <div
              key={bar.key}
              className={`ca-waterfall__bar-group ca-waterfall__bar-group--${evidence.status}`}
            >
              <div
                className={`ca-waterfall__bar${isNeg ? " ca-waterfall__bar--negative" : ""}${isTotal ? " ca-waterfall__bar--total" : ""}`}
                style={{
                  height: `${barHeight}px`,
                  background: bar.color,
                  marginBottom: isNeg ? "auto" : undefined,
                  marginTop: isNeg ? undefined : "auto",
                }}
                title={`${bar.label}: ${valueLabel}；${evidence.reason}`}
              >
                <span
                  className={`ca-waterfall__bar-value ${isNeg ? "ca-waterfall__bar-value--below" : "ca-waterfall__bar-value--above"}`}
                  style={{ color: bar.color }}
                >
                  {valueLabel}
                </span>
                <span className="ca-waterfall__bar-label">{bar.label}</span>
                <span className={`ca-waterfall__bar-status ca-waterfall__bar-status--${evidence.status}`}>
                  {evidence.label}
                </span>
              </div>
            </div>
          );
        })}
      </div>
      <div className="ca-waterfall__evidence" data-testid="cross-asset-driver-waterfall-evidence">
        {bars.map((bar) => {
          const evidence = waterfallFactorEvidence(bar, env);
          return (
            <div
              key={`evidence-${bar.key}`}
              className={`ca-waterfall__evidence-item ca-waterfall__evidence-item--${evidence.status}`}
            >
              <span>{bar.label}</span>
              <strong>{evidence.label}</strong>
              <p>{evidence.reason}</p>
            </div>
          );
        })}
      </div>
    </section>
  );
}

export default function CrossAssetDriversPage() {
  const client = useApiClient();
  const queryClient = useQueryClient();
  const [trendGroup, setTrendGroup] = useState<TrendGroupKey>("all");
  const latestQuery = useQuery({
    queryKey: ["cross-asset", "choice-macro-latest", client.mode],
    queryFn: () => client.getChoiceMacroLatest(),
    retry: false,
  });
  const latestSeries = useMemo(() => latestQuery.data?.result.series ?? [], [latestQuery.data?.result.series]);
  const latestMeta = latestQuery.data?.result_meta;

  const crossAssetDataDate = useMemo(() => maxCrossAssetHeadlineTradeDate(latestSeries), [latestSeries]);
  const linkageReportDate = useMemo(() => {
    if (latestSeries.length === 0) {
      return "";
    }
    return latestSeries.map((point) => point.trade_date).sort((left, right) => right.localeCompare(left))[0];
  }, [latestSeries]);

  const researchCalendarQuery = useQuery({
    queryKey: ["cross-asset", "research-calendar", client.mode, linkageReportDate],
    queryFn: () => client.getResearchCalendarEvents({ reportDate: linkageReportDate }),
    enabled: Boolean(linkageReportDate),
    retry: false,
  });

  const macroBondLinkageQuery = useQuery({
    queryKey: ["cross-asset", "macro-bond-linkage", client.mode, linkageReportDate],
    queryFn: () => client.getMacroBondLinkageAnalysis({ reportDate: linkageReportDate }),
    enabled: Boolean(linkageReportDate),
    retry: false,
  });

  const ncdFundingProxyQuery = useQuery({
    queryKey: ["cross-asset", "ncd-funding-proxy", client.mode],
    queryFn: () => client.getNcdFundingProxy(),
    retry: false,
  });
  const livermoreAsOfDate = crossAssetDataDate || linkageReportDate;
  const livermoreStrategyQuery = useQuery({
    queryKey: ["cross-asset", "livermore-strategy", client.mode, livermoreAsOfDate],
    queryFn: () => client.getLivermoreStrategy({ asOfDate: livermoreAsOfDate }),
    enabled: Boolean(livermoreAsOfDate),
    retry: false,
  });
  const livermoreStrategyResolvedAsOfDate = livermoreStrategyQuery.data?.result?.as_of_date || livermoreAsOfDate;
  const livermoreSignalConfluenceQueryKey = [
    "cross-asset",
    "livermore-signal-confluence",
    client.mode,
    livermoreStrategyResolvedAsOfDate,
  ] as const;
  const livermoreSignalConfluenceQuery = useQuery({
    queryKey: livermoreSignalConfluenceQueryKey,
    queryFn: () => client.getLivermoreSignalConfluence({ asOfDate: livermoreStrategyResolvedAsOfDate }),
    enabled: Boolean(livermoreStrategyResolvedAsOfDate && !livermoreStrategyQuery.isLoading),
    retry: false,
  });
  const livermoreManualPositionMutation = useMutation({
    mutationFn: (options: { asOfDate: string; positions: LivermoreManualPositionInput[] }) => {
      if (!options.asOfDate) {
        throw new Error("缺少策略日期，无法写入持仓。");
      }
      return client.materializeLivermoreManualPositionSnapshot({
        asOfDate: options.asOfDate,
        positions: options.positions,
      });
    },
    onSuccess: () => {
      void livermoreStrategyQuery.refetch();
      void queryClient.invalidateQueries({ queryKey: livermoreSignalConfluenceQueryKey });
      void queryClient.refetchQueries({
        queryKey: livermoreSignalConfluenceQueryKey,
        type: "active",
      });
    },
  });
  const livermoreManualSubmitError =
    livermoreManualPositionMutation.error instanceof Error
      ? livermoreManualPositionMutation.error.message
      : livermoreManualPositionMutation.error
        ? String(livermoreManualPositionMutation.error)
        : null;

  const macroBondLinkage = useMemo(
    () => macroBondLinkageQuery.data?.result ?? ({} as Partial<MacroBondLinkagePayload>),
    [macroBondLinkageQuery.data?.result],
  );
  const linkageMeta = macroBondLinkageQuery.data?.result_meta;
  const macroBondLinkageWarnings = useMemo(() => macroBondLinkage.warnings ?? [], [macroBondLinkage.warnings]);
  const macroBondLinkageUnavailable = macroBondLinkageQuery.isError;
  const hasPortfolioImpact = Object.keys(macroBondLinkage.portfolio_impact ?? {}).length > 0;
  const linkageBodyEmpty =
    macroBondLinkageQuery.isSuccess &&
    Boolean(linkageReportDate) &&
    macroBondLinkage.environment_score?.composite_score == null &&
    !hasPortfolioImpact &&
    macroBondLinkageWarnings.length === 0 &&
    (macroBondLinkage.top_correlations ?? []).length === 0;

  const env = useMemo(() => macroBondLinkage.environment_score ?? {}, [macroBondLinkage.environment_score]);
  const kpis = useMemo(() => resolveCrossAssetKpis(latestSeries), [latestSeries]);
  const headlineKpis = useMemo(() => kpis.slice(0, 4), [kpis]);
  const remainder = kpis.length % 4;
  const kpiPlaceholderCount = remainder !== 0 ? 4 - remainder : 0;
  const trendOption = useMemo(() => buildCrossAssetTrendOption(latestSeries), [latestSeries]);
  const trendSummary = useMemo(() => buildCrossAssetTrendSummary(kpis), [kpis]);
  const correlationMatrix = useMemo(() => buildCorrelationMatrix(kpis), [kpis]);
  const momentumRows = useMemo(() => buildMomentumScoreboard(kpis), [kpis]);
  const volAlert = useMemo(() => detectVolatilityClustering(kpis), [kpis]);
  const erpData = useMemo(() => computeEquityBondERP(kpis), [kpis]);
  const waterfallBars = useMemo(() => buildDriverWaterfall(env), [env]);
  const drivers = useMemo(() => buildDriverColumns(env), [env]);
  const envTags = useMemo(() => buildEnvironmentTags(env), [env]);
  const heatmapRows = useMemo(() => linkageHeatmapRows(macroBondLinkage.top_correlations ?? []), [macroBondLinkage.top_correlations]);
  const researchViewCards = useMemo(
    () =>
      buildResearchSummaryCards({
        researchViews: macroBondLinkage.research_views,
        env,
        topCorrelations: macroBondLinkage.top_correlations ?? [],
        linkageWarnings: macroBondLinkageWarnings,
        linkageUnavailable: macroBondLinkageUnavailable,
      }),
    [env, macroBondLinkage.research_views, macroBondLinkage.top_correlations, macroBondLinkageUnavailable, macroBondLinkageWarnings],
  );
  const transmissionAxisRows = useMemo(
    () =>
      buildTransmissionAxisRows({
        transmissionAxes: macroBondLinkage.transmission_axes,
        env,
        linkageUnavailable: macroBondLinkageUnavailable,
      }),
    [env, macroBondLinkage.transmission_axes, macroBondLinkageUnavailable],
  );
  const assetClassAnalysisRows = useMemo(
    () =>
      buildCrossAssetClassAnalysisRows({
        kpis,
        transmissionAxes: transmissionAxisRows,
        latestMeta,
        linkageMeta,
      }),
    [kpis, latestMeta, linkageMeta, transmissionAxisRows],
  );
  const equityEvidenceItems = useMemo(() => buildCrossAssetEquityEvidenceItems(kpis, latestMeta), [kpis, latestMeta]);
  const ncdProxyPayload = ncdFundingProxyQuery.data?.result ?? null;
  const livermoreStrategyPayload = livermoreStrategyQuery.data?.result ?? null;
  const livermoreSignalConfluencePayload = livermoreSignalConfluenceQuery.data?.result ?? null;
  const ncdProxyEvidence = useMemo(
    () =>
      buildCrossAssetNcdProxyEvidence({
        result: ncdProxyPayload,
        available: ncdFundingProxyQuery.isSuccess && !ncdFundingProxyQuery.isError && Boolean(ncdFundingProxyQuery.data),
      }),
    [ncdFundingProxyQuery.data, ncdFundingProxyQuery.isError, ncdFundingProxyQuery.isSuccess, ncdProxyPayload],
  );
  const candidateActions = useMemo(
    () =>
      buildCrossAssetCandidateActions({
        researchViews: macroBondLinkage.research_views,
        transmissionAxes: macroBondLinkage.transmission_axes,
        env,
        topCorrelations: macroBondLinkage.top_correlations ?? [],
        linkageWarnings: macroBondLinkageWarnings,
        ncdProxy: ncdProxyPayload,
        linkageUnavailable: macroBondLinkageUnavailable,
      }),
    [
      env,
      macroBondLinkage.research_views,
      macroBondLinkage.top_correlations,
      macroBondLinkage.transmission_axes,
      macroBondLinkageUnavailable,
      macroBondLinkageWarnings,
      ncdProxyPayload,
    ],
  );
  const eventItems = useMemo(
    () =>
      buildCrossAssetEventItems({
        events: researchCalendarQuery.data ?? [],
      }),
    [researchCalendarQuery.data],
  );
  const watchRows = useMemo(
    () =>
      buildCrossAssetWatchList({
        kpis,
        researchViews: macroBondLinkage.research_views,
        transmissionAxes: macroBondLinkage.transmission_axes,
        topCorrelations: macroBondLinkage.top_correlations ?? [],
        linkageWarnings: macroBondLinkageWarnings,
        linkageUnavailable: macroBondLinkageUnavailable,
      }),
    [
      kpis,
      macroBondLinkage.research_views,
      macroBondLinkage.top_correlations,
      macroBondLinkage.transmission_axes,
      macroBondLinkageUnavailable,
      macroBondLinkageWarnings,
    ],
  );
  const statusFlags = useMemo(() => {
    if (latestQuery.isLoading || (Boolean(linkageReportDate) && macroBondLinkageQuery.isLoading)) {
      return [];
    }
    return buildCrossAssetStatusFlags({
      latestMeta,
      linkageMeta,
      latestSeries,
      crossAssetDataDate,
      linkageReportDate,
      loadingFailures: [
        latestQuery.isError ? "choice_macro.latest" : "",
        macroBondLinkageQuery.isError ? "macro_bond_linkage.analysis" : "",
      ],
    });
  }, [
    crossAssetDataDate,
    latestMeta,
    latestQuery.isError,
    latestQuery.isLoading,
    latestSeries,
    linkageMeta,
    linkageReportDate,
    macroBondLinkageQuery.isError,
    macroBondLinkageQuery.isLoading,
  ]);

  const evalColor = {
    bull: t.color.semantic.profit,
    bear: t.color.semantic.loss,
    warning: t.color.warning[500],
  } as const;

  return (
    <section
      className="cross-asset-drivers-page"
      data-testid="cross-asset-drivers-page"
    >
      <div data-testid="cross-asset-page" className="cross-asset-drivers-page__shell">
        <PageDecisionHero
          testId="cross-asset-decision-hero"
          className="cross-asset-decision-hero"
          title="跨资产驱动"
          eyebrow="市场工作台"
          businessQuestion="外部变量怎样传导到债券？只保留判断、告警和候选动作，不替代正式执行与风控口径。"
          reportDateSlot={
            <span>
              数据日期 <strong style={tabularNumsStyle}>{crossAssetDataDate || linkageReportDate || "—"}</strong>
              {" · "}
              完整序列请转到 <Link to="/market-data">市场数据</Link>
            </span>
          }
          conclusion={
            <span>
              {macroBondLinkageQuery.isLoading || latestQuery.isLoading
                ? "正在加载联动分析…"
                : env.signal_description ?? "当前暂无可用摘要；请确认数据日期与联动分析是否已就绪。"}
            </span>
          }
          actions={
            <div className="cross-asset-decision-hero__actions">
              <span className="cross-asset-mode-badge">
                {client.mode === "real" ? "真实分析口径读链路" : "本地模拟合约回放"}
              </span>
              <Link to="/market-data" className="cross-asset-market-link">
                市场数据
              </Link>
            </div>
          }
        />

        <DataStatusStrip testId="cross-asset-data-status-strip" className="cross-asset-data-status-strip">
          <div className="cross-asset-data-status-strip__flags" data-testid="cross-asset-status-flags">
            {statusFlags.length === 0 ? (
              <span className="cross-asset-data-status-strip__empty">当前没有额外状态告警</span>
            ) : (
              statusFlags.map((flag) => (
                <span key={flag.id} className="cross-asset-data-status-strip__flag">
                  <StatusPill status={flag.tone} label={flag.label} />
                  <span>{flag.detail}</span>
                </span>
              ))
            )}
          </div>
          <div className="cross-asset-data-status-strip__meta">
            <span>宏观最新质量 {resultMetaQualityLabel(latestMeta?.quality_flag)}</span>
            <span>联动质量 {resultMetaQualityLabel(linkageMeta?.quality_flag)}</span>
            <span>宏观生成 {latestMeta?.generated_at ?? "待定"}</span>
            <span>联动生成 {linkageMeta?.generated_at ?? "待定"}</span>
          </div>
        </DataStatusStrip>

        <div className="cross-asset-drivers-page__flow">
          <div className="cross-asset-first-screen-grid" data-testid="cross-asset-first-screen-grid">
            <section className={`${crossAssetPanelClass} cross-asset-market-decision`}>
              <div className="cross-asset-panel-head">
                <h2 className="cross-asset-drivers-page__panel-title">市场判断</h2>
                <p className="cross-asset-panel-note">
                  先读体制与主导因素，再看右侧四个投研判断，避免被底层行情噪音牵走。
                </p>
              </div>
              <MarketRegimePanel kpis={kpis} />
              <p className="cross-asset-drivers-page__panel-prose">
                {macroBondLinkageQuery.isLoading || latestQuery.isLoading
                  ? "正在加载联动分析…"
                  : env.signal_description ?? "当前暂无可用摘要；请确认数据日期与联动分析是否已就绪。"}
              </p>
              <div className="cross-asset-drivers-page__chip-row">
                <StatusPill status="normal" label={`主导因素 · ${envTags.primary}`} />
                <StatusPill status="caution" label={`次要因素 · ${envTags.secondary}`} />
                <StatusPill status="warning" label={`风格 · ${envTags.style}`} />
              </div>
            </section>

            <ResearchViewsPanel rows={researchViewCards} />
            <HeadlineKpiDeck kpis={headlineKpis} />

            <section className={`${crossAssetPanelClass} cross-asset-correlation-panel`}>
              <div className="cross-asset-panel-head">
                <h2 className="cross-asset-drivers-page__panel-title">宏观 — 债市相关性（前列）</h2>
                <p className="cross-asset-panel-note">
                  使用联动分析中的滚动相关结果作参考，不替代个券估值分位或正式风险结论。
                </p>
              </div>
              <table className="cross-asset-drivers-page__heatmap">
                <thead>
                  <tr>
                    <th>指标</th>
                    <th>3月相关</th>
                    <th>6月相关</th>
                    <th>方向</th>
                  </tr>
                </thead>
                <tbody>
                  {heatmapRows.map((row) => (
                    <tr key={row.id}>
                      <td>{row.indicator}</td>
                      <td style={tabularNumsStyle}>{row.current}</td>
                      <td style={tabularNumsStyle}>{row.mid}</td>
                      <td style={{ color: evalColor[row.evalTone] }}>{row.eval}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          </div>

          <div className="cross-asset-drivers-page__lede cross-asset-drivers-page__lede--tight">
            <PageSectionLead
              eyebrow="环境上下文"
              title="完整指标带"
              description="首屏只展示 4 个关键 headline；这里保留全部跨资产头线条目，仍来自同一条宏观序列链路。"
            />
          </div>
          <div className="cross-asset-drivers-page__kpi-grid" data-testid="cross-asset-kpi-band">
            {kpis.map((kpi) => (
              <MiniKpiCard key={kpi.key} kpi={kpi} />
            ))}
            {remainder !== 0
              ? Array.from({ length: kpiPlaceholderCount }, (_, index) => (
                  <div
                    key={`kpi-placeholder-${index}`}
                    className="cross-asset-drivers-page__kpi-placeholder"
                    aria-hidden={true}
                  />
                ))
              : null}
          </div>

          <TransmissionAxesPanel rows={transmissionAxisRows} />
          <AssetClassAnalysisPanel rows={assetClassAnalysisRows} equityEvidenceItems={equityEvidenceItems} />

          <section className={`${crossAssetPanelClass} cross-asset-drivers-page__drivers`}>
            <h2 className="cross-asset-drivers-page__panel-title">驱动拆解</h2>
            <div className="cross-asset-drivers-page__drivers-grid">
              {drivers.map((col) => {
                const stanceStyle = driverStanceStyle(col.tone);
                return (
                  <div key={col.title} className="cross-asset-drivers-page__driver-cell">
                    <div className="cross-asset-drivers-page__driver-title">{col.title}</div>
                    <div
                      className="cross-asset-drivers-page__driver-stance"
                      style={{ background: stanceStyle.bg, color: stanceStyle.color }}
                    >
                      {col.stance}
                    </div>
                    <ul className="cross-asset-drivers-page__driver-list">
                      {col.bullets.map((bullet) => (
                        <li key={bullet}>{bullet}</li>
                      ))}
                    </ul>
                  </div>
                );
              })}
            </div>
          </section>
            <DriverWaterfallPanel bars={waterfallBars} env={env} />

            <div className="cross-asset-risk-snapshot-grid">
              <VolatilityClusteringPanel alert={volAlert} />
              <EquityBondERPPanel erp={erpData} />
            </div>

            <MarketCandidateActions rows={candidateActions} />

            <NcdProxyEvidencePanel evidence={ncdProxyEvidence} isLoading={ncdFundingProxyQuery.isLoading} />

            <div className="cross-asset-drivers-page__lede">
              <PageSectionLead
                eyebrow="观察项"
                title="走势、事件与观察"
                description="完成研究判断后，再查看价格走势、事件流和观察名单，避免把短噪音误当成主结论。"
              />
            </div>
            <div data-testid="cross-asset-trend-panel" className="cross-asset-trend-panel">
              <SectionCard title="跨资产走势（近 20 日，统一基准 = 100）" style={{ minWidth: 0 }}>
                <TrendGroupToggle active={trendGroup} onChange={setTrendGroup} />
                {trendSummary ? (
                  <div className={`cross-asset-trend-panel__summary cross-asset-trend-panel__summary--${trendSummary.tone}`} data-testid="cross-asset-trend-summary">
                    <span className="cross-asset-trend-panel__summary-dot" />
                    <span className="cross-asset-trend-panel__summary-text">{trendSummary.headline}</span>
                    <div className="cross-asset-trend-panel__summary-signals">
                      {trendSummary.signals.map((sig) => (
                        <span key={sig.label} className={`cross-asset-trend-panel__signal cross-asset-trend-panel__signal--${sig.tone}`} title={sig.description}>
                          {sig.label}
                        </span>
                      ))}
                    </div>
                  </div>
                ) : null}
                <p className="cross-asset-trend-panel__note">
                  各资产发布日与休市不同，在统一时间轴上先对缺失日沿用「上一有效观测」(LOCF)，再按窗口内首次观测 = 100
                  归一化；否则多市场下会出现大段空档与碎线。曲线在两次真实更新之间为水平持有，不代表日内波动。
                </p>
                {latestQuery.isLoading ? (
                  <div className="cross-asset-trend-panel__loading">
                    <div className="cross-asset-trend-panel__spinner" />
                    正在加载宏观序列…
                  </div>
                ) : trendOption ? (
                  <div className="cross-asset-trend-chart">
                    <ReactECharts
                      option={(() => {
                        const visibleLabels = trendGroupLabels(trendGroup, kpis);
                        if (!visibleLabels || !trendOption.legend) return trendOption;
                        const selected: Record<string, boolean> = {};
                        const series = trendOption.series as Array<{ name?: string }>;
                        for (const s of series) {
                          if (s.name) selected[s.name] = visibleLabels.has(s.name);
                        }
                        return {
                          ...trendOption,
                          legend: {
                            ...(typeof trendOption.legend === "object" ? trendOption.legend : {}),
                            selected,
                          },
                        };
                      })()}
                      style={{ height: 420, width: "100%" }}
                      notMerge
                      lazyUpdate
                    />
                  </div>
                ) : (
                  <div className="cross-asset-trend-panel__empty">
                    当前没有足够历史点，无法绘制跨资产走势。
                  </div>
                )}
              </SectionCard>
            </div>

            <div className="cross-asset-observation-support-grid" data-testid="cross-asset-observation-support-grid">
              <MomentumScoreboardPanel rows={momentumRows} />
              <CorrelationHeatmapPanel matrix={correlationMatrix} />
            </div>

            <div className="cross-asset-observation-secondary-grid" data-testid="cross-asset-observation-secondary-grid">
              <CrossAssetEventCalendar items={eventItems} />
              <WatchList rows={watchRows} />
            </div>

            <div className="cross-asset-drivers-page__lede cross-asset-drivers-page__lede--tight">
              <PageSectionLead
                eyebrow="附加观察"
                title="A股策略与跨资产观察"
                description="股票策略面板保留在下游复核区，作为补充观察，不打断跨资产到债券的主判断链路。"
              />
            </div>
            <LivermoreStrategyStatusPanel
              payload={livermoreStrategyPayload}
              isLoading={livermoreStrategyQuery.isLoading}
              isError={livermoreStrategyQuery.isError}
              asOfDate={livermoreAsOfDate}
              onManualSubmit={(positions, asOfDate) =>
                livermoreManualPositionMutation.mutateAsync({ asOfDate, positions })
              }
              manualSubmitPending={livermoreManualPositionMutation.isPending}
              manualSubmitError={livermoreManualSubmitError}
              manualResultRowCount={livermoreManualPositionMutation.data?.row_count ?? null}
            />
            <LivermoreSignalConfluencePanel
              payload={livermoreSignalConfluencePayload}
              isLoading={livermoreSignalConfluenceQuery.isLoading}
              isError={livermoreSignalConfluenceQuery.isError}
              asOfDate={livermoreStrategyResolvedAsOfDate}
            />

            <div className="cross-asset-drivers-page__lede">
              <PageSectionLead
                eyebrow="分析结果"
                title="宏观联动与输出"
                description="以下为联动评分与组合影响的分析口径，仅供决策参考，不替代正式风控与会计口径。"
              />
            </div>
            <AsyncSection
              title="宏观 - 债券联动（评分与组合影响）"
              isLoading={macroBondLinkageQuery.isLoading || latestQuery.isLoading}
              isError={macroBondLinkageQuery.isError || latestQuery.isError}
              isEmpty={linkageBodyEmpty}
              onRetry={() => {
                void latestQuery.refetch();
                void macroBondLinkageQuery.refetch();
                void researchCalendarQuery.refetch();
              }}
            >
              {!linkageReportDate ? (
                <p style={{ color: t.color.neutral[600], fontSize: t.fontSize[14] }}>
                  缺少可用交易日，当前无法计算宏观-债券联动分析。
                </p>
              ) : (
                <div style={{ display: "grid", gap: t.space[4] }}>
                  {macroBondLinkageWarnings.length > 0 ? (
                    <ul
                      data-testid="cross-asset-linkage-warning-list"
                      style={{
                        margin: 0,
                        paddingLeft: t.space[5],
                        color: t.color.neutral[600],
                        fontSize: t.fontSize[13],
                        lineHeight: t.lineHeight.relaxed,
                      }}
                    >
                      {macroBondLinkageWarnings.map((warning) => (
                        <li key={warning}>{warning}</li>
                      ))}
                    </ul>
                  ) : null}

                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns: "repeat(4, minmax(0, 1fr))",
                      gap: t.space[3],
                    }}
                  >
                    <div data-testid="cross-asset-linkage-composite-score">
                      <KpiCard
                        title="综合评分"
                        value={env.composite_score != null ? String(env.composite_score.toFixed(2)) : "不可用"}
                        detail={env.signal_description ?? "缺少环境评分数据。"}
                        valueVariant="text"
                        tone={toneFromSignedNumber(env.composite_score != null ? env.composite_score : null)}
                      />
                    </div>
                    <div data-testid="cross-asset-linkage-rate-direction">
                      <KpiCard
                        title="利率方向"
                        value={env.rate_direction ?? "不可用"}
                        detail={env.rate_direction_score != null ? `direction score ${env.rate_direction_score.toFixed(2)}` : "缺少方向评分。"}
                        valueVariant="text"
                        tone={toneFromSignedNumber(env.rate_direction_score != null ? env.rate_direction_score : null)}
                      />
                    </div>
                    <div data-testid="cross-asset-linkage-liquidity-score">
                      <KpiCard
                        title="流动性评分"
                        value={env.liquidity_score != null ? env.liquidity_score.toFixed(2) : "不可用"}
                        detail="正值偏松，负值偏紧。"
                        valueVariant="text"
                        tone={toneFromSignedNumber(env.liquidity_score != null ? env.liquidity_score : null)}
                      />
                    </div>
                    <div data-testid="cross-asset-linkage-growth-score">
                      <KpiCard
                        title="增长评分"
                        value={env.growth_score != null ? env.growth_score.toFixed(2) : "不可用"}
                        detail="宏观增长方向的简化分值。"
                        valueVariant="text"
                        tone={toneFromSignedNumber(env.growth_score != null ? env.growth_score : null)}
                      />
                    </div>
                  </div>

                  <section data-testid="cross-asset-linkage-portfolio-impact" className={crossAssetPanelClass}>
                    <h2 style={{ marginTop: 0, marginBottom: t.space[2], fontSize: t.fontSize[16], fontWeight: 600, color: t.color.neutral[900] }}>
                      组合影响估算
                    </h2>
                    <p style={{ marginTop: 0, color: t.color.neutral[600], fontSize: t.fontSize[13], lineHeight: t.lineHeight.relaxed }}>
                      以下数值属于分析口径估算，只作为环境敏感度提示，不代表正式损益。
                    </p>
                    {hasPortfolioImpact ? (
                      <div
                        style={{
                          display: "grid",
                          gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
                          gap: t.space[3],
                        }}
                      >
                        <div>
                          <div style={{ color: t.color.neutral[500], fontSize: t.fontSize[12] }}>利率变动</div>
                          <div style={tabularNumsStyle}>{formatSignedNumber(macroBondLinkage.portfolio_impact?.estimated_rate_change_bps, " bp")}</div>
                        </div>
                        <div>
                          <div style={{ color: t.color.neutral[500], fontSize: t.fontSize[12] }}>利差走阔</div>
                          <div style={tabularNumsStyle}>{formatSignedNumber(macroBondLinkage.portfolio_impact?.estimated_spread_widening_bps, " bp")}</div>
                        </div>
                        <div>
                          <div style={{ color: t.color.neutral[500], fontSize: t.fontSize[12] }}>合计估算</div>
                          <div style={tabularNumsStyle}>{formatSignedNumber(macroBondLinkage.portfolio_impact?.total_estimated_impact)}</div>
                        </div>
                      </div>
                    ) : (
                      <div style={{ color: t.color.neutral[500], fontSize: t.fontSize[14] }}>当前没有可用组合影响估算。</div>
                    )}
                  </section>
                </div>
              )}
            </AsyncSection>

            <div data-testid="cross-asset-page-output">
              <PageOutput
                envTags={envTags}
                signalPreview={env.signal_description ?? null}
                linkageWarnings={macroBondLinkageWarnings}
                topCorrelationSummary={
                  macroBondLinkage.top_correlations?.[0]
                    ? `${macroBondLinkage.top_correlations[0].series_name} -> ${macroBondLinkage.top_correlations[0].target_family}${macroBondLinkage.top_correlations[0].target_tenor ? ` ${macroBondLinkage.top_correlations[0].target_tenor}` : ""}`
                    : null
                }
              />
            </div>
        </div>
      </div>
    </section>
  );
}
