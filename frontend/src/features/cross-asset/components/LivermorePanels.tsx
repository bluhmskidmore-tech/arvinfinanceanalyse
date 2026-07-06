import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import type {
  LivermoreManualPositionInput,
  LivermoreSignalConfluencePayload,
  LivermoreStrategyPayload,
} from "../../../api/contracts";
import { riskExitBlockedDetail } from "../../stock-analysis/lib/stockAnalysisPageCopy";
import { crossAssetPanelClass } from "./shared";
import { formatLivermoreReadinessSummary } from "../lib/crossAssetLivermoreCopy";

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
  if (message === "Adversarial risk gate is blocking new entry observations; candidate entries stay observe_only.") {
    return "风控对抗门控阻止新增入场观察，候选项保持仅观察。";
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
          <input value={draft.stockCode} onChange={(event) => updateDraft("stockCode", event.target.value)} placeholder="000001.SZ" />
        </label>
        <label>
          <span>股票名称</span>
          <input value={draft.stockName} onChange={(event) => updateDraft("stockName", event.target.value)} placeholder="平安银行" />
        </label>
        <label>
          <span>入场成本</span>
          <input inputMode="decimal" value={draft.entryCost} onChange={(event) => updateDraft("entryCost", event.target.value)} placeholder="10.50" />
        </label>
        <label>
          <span>持有天数</span>
          <input inputMode="numeric" value={draft.barsSinceEntry} onChange={(event) => updateDraft("barsSinceEntry", event.target.value)} placeholder="6" />
        </label>
        <label>
          <span>持仓数量</span>
          <input inputMode="decimal" value={draft.positionQuantity} onChange={(event) => updateDraft("positionQuantity", event.target.value)} placeholder="10000" />
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

export function LivermoreStrategyStatusPanel({
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
  const riskLabel = riskClosed ? `${payload?.risk_exit?.signal_count ?? 0}/${payload?.risk_exit?.position_count ?? 0}` : "缺持仓快照";
  const localizedRiskReason = riskReason ? riskExitBlockedDetail(riskReason, "risk_exit") : "";
  const riskDetail = riskClosed
    ? `退出信号 ${payload?.risk_exit?.signal_count ?? 0} 条，覆盖持仓 ${payload?.risk_exit?.position_count ?? 0} 条。`
    : riskReason
      ? `持仓快照输入未闭合：${localizedRiskReason}`
      : formatLivermoreReadinessSummary(riskReadiness?.summary, "risk_exit") ||
        "缺少持仓快照输入，风险退出规则无法闭环。";
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
            Livermore A股防守趋势策略当前只做分析读链路，先看输入是否足够支撑输出。
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
                {formatLivermoreExposure(payload.market_gate.exposure)} ·{" "}
                {formatLivermoreReadinessSummary(gateReadiness?.summary, gateReadiness?.key) || "门控状态待定"}
              </small>
            </div>
            <div className="cross-asset-livermore__metric">
              <span className="cross-asset-livermore__label">个股候选</span>
              <strong className="cross-asset-livermore__value">{candidateCount}</strong>
              <small className="cross-asset-livermore__detail">
                {payload.supported_outputs.includes("stock_candidates") ? "候选筛选已就绪" : "候选筛选未开放"} ·{" "}
                {formatLivermoreReadinessSummary(candidatesReadiness?.summary, candidatesReadiness?.key) || "候选状态待定"}
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

export function LivermoreSignalConfluencePanel({
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
    positionSizeHint: formatLivermoreExposure(parseOptionalNumeric(item?.position_size_hint) ?? strategyPositionSizeHint),
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
    <section data-testid="cross-asset-livermore-confluence" className={`${crossAssetPanelClass} cross-asset-livermore-confluence`}>
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
                    {codeLabel ? <span className="cross-asset-livermore-confluence__diagnostic-code">{codeLabel}</span> : null}
                    <span>{item.message}</span>
                  </li>
                );
              })}
            </ul>
          ) : null}

          {!hasObservations ? <div className="cross-asset-livermore-confluence__empty">暂无可观察点位</div> : null}

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
                    <article key={`${item.stockCode}-${item.triggerPrice}`} className="cross-asset-livermore-confluence__item">
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
                    <article key={`${item.stockCode}-${item.exitWatchPrice}`} className="cross-asset-livermore-confluence__item">
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
