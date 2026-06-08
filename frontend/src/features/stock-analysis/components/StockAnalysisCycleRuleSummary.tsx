import type { LivermoreCycleRotationFramework } from "../../../api/contracts";
import {
  cycleCadenceLabel,
  cycleRuleSummary,
} from "../lib/stockAnalysisPageLabels";

type CycleRuleSummaryFramework = Pick<
  LivermoreCycleRotationFramework,
  "layers" | "observation_only" | "rebalance_cadence"
>;

export function StockAnalysisCycleRuleSummary({
  framework,
}: {
  framework: CycleRuleSummaryFramework;
}) {
  return (
    <div className="stock-analysis-page__cycle-formulas" data-testid="stock-analysis-cycle-rule-summary">
      <strong>轮动规则</strong>
      <span>{cycleRuleSummary(framework.layers)}</span>
      {framework.observation_only ? <small>只读观察，不生成交易指令</small> : null}
      <small>{cycleCadenceLabel(framework.rebalance_cadence)}</small>
    </div>
  );
}
