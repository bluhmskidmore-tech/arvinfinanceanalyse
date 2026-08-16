import { Link } from "react-router-dom";

import { EM_DASH } from "../../../pageModel";
import type { MacroObservationCrisisEvidenceView } from "../model/macroObservationPageModel";
import MacroObservationCrisisChart from "./MacroObservationCrisisChart";
import "./MacroObservationModelCrisis.css";

/**
 * 04 危机分证据：左读数栈（score 大字 + regime 徽标 + headline +
 * percentile / components / recommendation 读数行）+ 右 ECharts 历史折线。
 * analytical only：修复与刷新动作留在宏观工具页，本区只放链接细注。
 */

/** 历史折线至少 2 点才画；不足时占位说明，禁止用演示数据冒充。 */
const CRISIS_CHART_MIN_POINTS = 2;

export default function MacroObservationCrisisSection({
  crisis,
}: {
  crisis: MacroObservationCrisisEvidenceView;
}) {
  const isReady = crisis.state === "ready";
  const history = isReady ? crisis.history : [];
  const hasChart = history.length >= CRISIS_CHART_MIN_POINTS;
  const placeholderNote = isReady
    ? "暂无历史序列"
    : crisis.state === "empty"
      ? "暂无历史序列"
      : "历史序列待完整分析确认";

  return (
    <div className="macro-observation-crisis-layout">
      <div className="macro-observation-crisis-readout" aria-label="危机分读数">
        {isReady ? (
          <>
            {/* 危机分读数已在 01 KPI 与 02 信号带出现；本区大字徽标按 §6 去重删除，
                headline 原句保留作为证据上下文。 */}
            <p className="macro-observation-crisis-headline">{crisis.headline}</p>
            <dl className="macro-observation-view__meta-list">
              <dt>历史分位</dt>
              <dd>{crisis.percentileText}</dd>
              <dt>组件</dt>
              <dd>
                可用 {crisis.availableComponentCount}/{crisis.componentCount}
                {crisis.coverageNote ? (
                  <small className="macro-observation-crisis-coverage-note">{crisis.coverageNote}</small>
                ) : null}
              </dd>
              <dt>模型建议</dt>
              <dd title={crisis.recommendation}>{crisis.recommendation}</dd>
            </dl>
          </>
        ) : (
          <p className="macro-observation-crisis-empty">
            {crisis.state === "empty" ? crisis.note : `危机分证据${crisis.note}。`}
          </p>
        )}
        <p className="macro-observation-crisis-link-note">
          数据修复与刷新请前往
          <Link className="macro-observation-view__toolkit-link" to="/macro-toolkit">
            宏观工具页
          </Link>
          。
        </p>
      </div>

      <div className="macro-observation-crisis-chart-panel">
        <div className="macro-observation-view__panel-head">
          <h3 className="macro-observation-view__panel-title">危机分历史</h3>
          <span className="macro-observation-view__panel-hint">
            {hasChart ? `${history.length} 点` : EM_DASH}
          </span>
        </div>
        <div
          className="macro-observation-crisis-chart"
          data-testid="macro-observation-crisis-chart"
        >
          {hasChart ? (
            <MacroObservationCrisisChart history={history} />
          ) : (
            <p className="macro-observation-crisis-placeholder">{placeholderNote}</p>
          )}
        </div>
      </div>
    </div>
  );
}
