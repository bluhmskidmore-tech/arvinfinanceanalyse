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
  // deferred（core 首发）→ 待完整分析；ready 但序列不足 → 暂无历史序列。
  const placeholderNote = isReady ? "暂无历史序列" : "历史序列待完整分析确认";
  const availableComponentCount = isReady
    ? crisis.componentCount - crisis.componentMissingCount
    : 0;

  return (
    <div className="macro-observation-crisis-layout">
      <div className="macro-observation-crisis-readout" aria-label="危机分读数">
        {isReady ? (
          <>
            <div className="macro-observation-crisis-score-row">
              <span className="macro-observation-crisis-score">{crisis.scoreText}</span>
              <span className="macro-observation-crisis-regime">{crisis.regime}</span>
            </div>
            <p className="macro-observation-crisis-headline">{crisis.headline}</p>
            <dl className="macro-observation-view__meta-list">
              <dt>历史分位</dt>
              <dd>{crisis.percentileText}</dd>
              <dt>组件</dt>
              <dd>
                可用 {availableComponentCount}/{crisis.componentCount}
              </dd>
              <dt>模型建议</dt>
              <dd title={crisis.recommendation}>{crisis.recommendation}</dd>
            </dl>
          </>
        ) : (
          <p className="macro-observation-crisis-empty">危机分证据{crisis.note}。</p>
        )}
        <p className="macro-observation-crisis-link-note">
          数据修复与刷新请前往
          <a className="macro-observation-view__toolkit-link" href="/macro-toolkit">
            宏观工具页
          </a>
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
