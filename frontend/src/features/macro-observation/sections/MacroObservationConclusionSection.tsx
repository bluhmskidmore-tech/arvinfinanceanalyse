import type { MacroToolkitCapabilityResult } from "../../../api/macroToolkitClient";
import { statusLabel } from "../../macro-toolkit/lib/macroToolkitPanelShared";
import MacroObservationKpiBand from "../components/MacroObservationKpiBand";
import type {
  MacroObservationConclusionView,
  MacroObservationKpiItem,
} from "../model/macroObservationPageModel";
import "./MacroObservationConclusionSignal.css";

/**
 * 01 当日观察结论：KPI 单框横带（骨架组件） + 左右双栏
 * （结论主读数 3fr / 决策摘要卡 2fr，1280 以下折单栏）。
 * 数据一律来自模型层视图对象，组件只编排与着色（data-tone / data-status → CSS）。
 */
export default function MacroObservationConclusionSection({
  kpiItems,
  conclusion,
  decisionResult,
  isCoreAnalysis,
  analysisBasis,
}: {
  kpiItems: MacroObservationKpiItem[];
  conclusion: MacroObservationConclusionView;
  /** decision_summary 能力结果原始行（模型层暂无专用视图，最小透传）。 */
  decisionResult: MacroToolkitCapabilityResult | null;
  isCoreAnalysis: boolean;
  /** 分析信封 basis；"mock" 时必须露出模拟口径旗标（对齐旧页行为）。 */
  analysisBasis: string | null;
}) {
  return (
    <div className="macro-observation-view__conclusion-stack">
      <MacroObservationKpiBand testId="macro-observation-kpi-band" items={kpiItems} />

      <div className="macro-observation-conclusion-grid">
        <div className="macro-observation-conclusion-main" aria-label="观察结论正文">
          <strong className="macro-observation-conclusion-stance" data-tone={conclusion.tone}>
            {conclusion.stance}
          </strong>
          <p className="macro-observation-conclusion-summary" title={conclusion.summary}>
            {conclusion.summary}
          </p>
          <p className="macro-observation-conclusion-action">
            <span className="macro-observation-conclusion-action-label">建议动作</span>
            <span className="macro-observation-conclusion-action-text">
              {conclusion.recommendedAction}
            </span>
          </p>
          {conclusion.warningNote ? (
            <p
              className="macro-observation-conclusion-warning-note"
              data-testid="macro-observation-conclusion-warning-note"
            >
              {conclusion.warningNote}，全文见证据与口径分区。
            </p>
          ) : null}
        </div>

        <div
          className="macro-observation-conclusion-decision"
          data-testid="macro-observation-decision-summary"
          aria-label="宏观决策摘要"
        >
          {analysisBasis === "mock" ? (
            <p
              className="macro-observation-conclusion-decision-mock-flag"
              data-testid="macro-observation-decision-mock-flag"
            >
              <strong>模拟口径</strong>
              当前决策摘要由前端模拟数据生成，仅用于界面演示，不代表宏观分析结论。
            </p>
          ) : null}
          {decisionResult ? (
            <>
              <div
                className="macro-observation-conclusion-decision-head"
                title={decisionResult.legacy_module}
              >
                <span className="macro-observation-conclusion-decision-title">宏观决策摘要</span>
                {/* 后端 result.data_status 与能力行 status 同源同值，走 TS 契约字段。 */}
                <span
                  className="macro-observation-conclusion-decision-badge"
                  data-status={decisionResult.status}
                >
                  {statusLabel(decisionResult.status)}
                </span>
              </div>
              {decisionResult.primary_metric ? (
                <p className="macro-observation-conclusion-decision-metric">
                  <span className="macro-observation-conclusion-decision-metric-label">
                    {decisionResult.primary_metric.label}
                  </span>{" "}
                  <strong className="macro-observation-conclusion-decision-metric-value">
                    {decisionResult.primary_metric.value}
                    <small>{decisionResult.primary_metric.unit}</small>
                  </strong>
                </p>
              ) : null}
              <p className="macro-observation-conclusion-decision-headline">
                {decisionResult.headline}
              </p>
              {decisionResult.warnings.length ? (
                <small className="macro-observation-conclusion-decision-warning">
                  {decisionResult.warnings.join(" / ")}
                </small>
              ) : null}
            </>
          ) : (
            <p className="macro-observation-conclusion-decision-empty">
              {isCoreAnalysis
                ? "核心分析已先返回；决策摘要需打开完整分析后确认。"
                : "后端未返回决策摘要结果，本页不推导宏观结论。"}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
