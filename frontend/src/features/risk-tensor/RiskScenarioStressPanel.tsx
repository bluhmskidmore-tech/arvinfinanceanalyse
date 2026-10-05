import type { ResultMeta, RiskScenarioStressPayload, RiskScenarioStressRow } from "../../api/contracts";
import { EM_DASH } from "../../utils/format";
import { countDisplay, displayStr, riskTensorRawOrNull, yuanAsWanWithUnit } from "./riskTensorDisplay";
import { scenarioStressTone } from "./riskTensorPageModel";
import { describeRiskTensorWarning, errorEvidenceMessage } from "./riskTensorPresentation";

const SCENARIO_SOURCE_LABELS: Record<string, string> = {
  regulatory_dv01: "监管口径 DV01",
  cs01: "CS01",
  "asset_cashflow_30d/liability_cashflow_30d/liquidity_gap_30d": "30 日现金流",
  fx_exposure: "汇率敞口",
};

function scenarioStressCategoryLabel(category: RiskScenarioStressRow["category"]) {
  if (category === "rate") return "利率";
  if (category === "credit") return "信用";
  if (category === "liquidity") return "流动性";
  if (category === "fx") return "汇率";
  return category;
}

function scenarioStressDataStatusLabel(
  status: RiskScenarioStressRow["data_status"],
  amountDisplayAllowed: boolean,
) {
  if (status !== "available") return "待接入";
  return amountDisplayAllowed ? "已估算" : "金额待核验";
}

function scenarioAmountGateReason(payload: RiskScenarioStressPayload) {
  const evidence = payload.evidence;
  if (!evidence) {
    return "后端未返回监管 DV01 覆盖证据。";
  }

  const reasons: string[] = [];
  if (evidence.date_status !== "verified") {
    reasons.push("风险日期尚未完成核验");
  }
  if (evidence.fallback_status !== "none") {
    reasons.push(evidence.fallback_date ? `风险来源使用回退数据 ${evidence.fallback_date}` : "风险来源存在回退");
  }
  if (evidence.coverage.status !== "complete") {
    const missingCount = evidence.coverage.missing_risk_position_count;
    reasons.push(
      `监管 DV01 覆盖${evidence.coverage.status === "incomplete" ? "不完整" : "状态待核验"}${
        typeof missingCount === "number" ? `，缺少风险输入 ${missingCount.toLocaleString("zh-CN")} 条` : ""
      }`,
    );
  }
  reasons.push(
    ...evidence.coverage.reasons
      .map((reason) => reason.trim().replace(/[。；]+$/u, ""))
      .filter(Boolean),
  );
  const reasonText = Array.from(new Set(reasons)).join("；");
  return reasonText ? `${reasonText}。` : "金额展示条件未通过。";
}

export function RiskScenarioStressPanel({
  payload,
  meta,
  isLoading,
  error,
  reportDate,
  onRetry,
  onMetaJump,
}: {
  payload?: RiskScenarioStressPayload;
  meta?: ResultMeta;
  isLoading: boolean;
  error: unknown;
  reportDate: string;
  onRetry: () => void;
  onMetaJump: () => void;
}) {
  const errorMessage = error ? errorEvidenceMessage(error) : "";
  const amountDisplayAllowed = payload?.evidence?.amount_display_allowed === true;
  const worstScenario = payload?.summary.worst_scenario_key
    ? payload.scenarios.find((row) => row.scenario_key === payload.summary.worst_scenario_key)
    : undefined;
  const worstImpactAvailable = riskTensorRawOrNull(payload?.summary.worst_estimated_impact) !== null;
  const comparisonMeasureVerified =
    Boolean(payload?.summary.comparison_measure) &&
    payload?.summary.comparison_measure === worstScenario?.measure;
  const showWorstImpact =
    amountDisplayAllowed && worstImpactAvailable && Boolean(worstScenario) && comparisonMeasureVerified;
  const worstEstimateTitle =
    payload?.summary.comparison_measure === "estimated_pnl_impact" ? "最不利损益估算" : "最不利可比估算";

  return (
    <section className="risk-tensor-scenario-stress" data-testid="risk-tensor-scenario-stress">
      <div className="risk-tensor-scenario-stress__header">
        <div>
          <span>情景压力</span>
          <h2>多情景压力测试</h2>
          <p>估算利率、信用、流动性和汇率变化的影响，仅供复核，不代表实际损益或限额判定。</p>
        </div>
        <strong title={meta?.basis ?? payload?.basis ?? "scenario"}>情景估算</strong>
      </div>

      {isLoading ? (
        <div className="risk-tensor-scenario-stress__empty">
          <span>正在读取压力测试</span>
          <p>正在准备 {reportDate || "所选报告日"} 的情景估算。</p>
        </div>
      ) : error ? (
        <div className="risk-tensor-scenario-stress__empty" data-testid="risk-tensor-scenario-stress-error">
          <span>压力测试暂不可用</span>
          <p>{errorMessage || "后端未返回压力测试结果。"}</p>
          <div className="risk-tensor-quality-detail__trace-actions">
            <button type="button" className="risk-tensor-quality-detail__trace-action" onClick={onRetry}>
              重试压力测试
            </button>
            <button type="button" className="risk-tensor-quality-detail__trace-action" onClick={onMetaJump}>
              定位元数据
            </button>
          </div>
        </div>
      ) : payload ? (
        <>
          <div className="risk-tensor-scenario-stress__summary">
            <div>
              <span>情景数量</span>
              <strong>{payload.summary.scenario_count}</strong>
              <p>{payload.summary.review_required_count} 个需要人工复核</p>
            </div>
            <div>
              <span>可估算情景</span>
              <strong>{payload.summary.available_count}</strong>
              <p>汇率等缺口会单独显示待接入</p>
            </div>
            <div data-testid="risk-tensor-scenario-worst-estimate">
              <span>{worstEstimateTitle}</span>
              <strong>
                {showWorstImpact ? yuanAsWanWithUnit(payload.summary.worst_estimated_impact) : "暂不展示"}
              </strong>
              <p>
                {amountDisplayAllowed
                  ? comparisonMeasureVerified
                    ? worstScenario?.label
                    : "后端未返回可比口径"
                  : "覆盖证据未通过，摘要金额已隐藏"}
              </p>
            </div>
          </div>

          {!amountDisplayAllowed ? (
            <div className="risk-tensor-scenario-stress__warning" data-testid="risk-tensor-scenario-amount-gate">
              情景金额暂不展示：{scenarioAmountGateReason(payload)}
            </div>
          ) : null}

          {payload.warnings.length > 0 ? (
            <div className="risk-tensor-scenario-stress__warning">{payload.warnings.map(describeRiskTensorWarning).join(" / ")}</div>
          ) : null}

          <div className="risk-tensor-scenario-stress__grid">
            {payload.scenarios.map((row) => (
              <article
                className="risk-tensor-scenario-stress__card"
                data-tone={amountDisplayAllowed ? scenarioStressTone(row) : "warning"}
                data-testid={`risk-scenario-stress-row-${row.scenario_key}`}
                key={row.scenario_key}
              >
                <div className="risk-tensor-scenario-stress__card-head">
                  <span>{scenarioStressCategoryLabel(row.category)}</span>
                  <strong>{scenarioStressDataStatusLabel(row.data_status, amountDisplayAllowed)}</strong>
                </div>
                <h3>{row.label}</h3>
                <div className="risk-tensor-scenario-stress__impact">
                  {row.data_status === "available"
                    ? amountDisplayAllowed
                      ? yuanAsWanWithUnit(row.estimated_impact)
                      : "暂不展示"
                    : displayStr(row.estimated_impact)}
                </div>
                <p>{row.interpretation}</p>
                <dl>
                  <div>
                    <dt>冲击</dt>
                    <dd>{displayStr(row.shock)}</dd>
                  </div>
                  <div>
                    <dt>计算依据</dt>
                    <dd title={row.source_field}>{SCENARIO_SOURCE_LABELS[row.source_field] ?? row.source_field}</dd>
                  </div>
                  {amountDisplayAllowed && row.baseline_value && row.stressed_value ? (
                    <div>
                      <dt>压力后</dt>
                      <dd>{yuanAsWanWithUnit(row.stressed_value)}</dd>
                    </div>
                  ) : null}
                </dl>
                {row.human_review_required ? <small>需人工复核</small> : null}
              </article>
            ))}
          </div>

          <details className="risk-tensor-disclosure" data-testid="risk-tensor-scenario-evidence">
            <summary>情景计算说明与来源</summary>
            <div className="risk-tensor-scenario-stress__footer">
            <span>scenario_set_id {payload.scenario_set_id}</span>
            <span>rule_version {payload.rule_version}</span>
            <span>source_trace_id {payload.source.trace_id ?? EM_DASH}</span>
            <span>amount_display_allowed {String(amountDisplayAllowed)}</span>
            {payload.evidence ? (
              <>
                <span>风险日期 {payload.evidence.actual_risk_date ?? EM_DASH}</span>
                <span>监管 DV01 覆盖状态 {payload.evidence.coverage.status}</span>
                <span>
                  持仓记录 {countDisplay(payload.evidence.coverage.total_position_count)}；纳入范围 {countDisplay(payload.evidence.coverage.included_position_count)}；
                  排除范围 {countDisplay(payload.evidence.coverage.excluded_position_count)}；缺少风险输入 {countDisplay(payload.evidence.coverage.missing_risk_position_count)}
                </span>
                {payload.evidence.coverage.reasons.map((reason, index) => <p key={`coverage-reason-${index}`}>{reason}</p>)}
              </>
            ) : <p>未返回监管 DV01 覆盖证据。</p>}
            {payload.scenarios.map((row) => <span key={row.scenario_key}>{row.label}：{row.source_field}；human_review_required={String(row.human_review_required)}</span>)}
            {payload.warnings.map((warning, index) => <p key={index}>{warning}</p>)}
            </div>
          </details>
        </>
      ) : (
        <div className="risk-tensor-scenario-stress__empty">
          <span>暂无压力测试结果</span>
          <p>风险数据就绪后可查看情景估算。</p>
        </div>
      )}
    </section>
  );
}
