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
    <div className="flex flex-col gap-1 p-3 bg-default-100/50 rounded-lg text-sm text-default-700" data-testid="stock-analysis-cycle-rule-summary">
      <strong className="text-foreground">轮动规则</strong>
      <span>{cycleRuleSummary(framework.layers)}</span>
      {framework.observation_only && <small className="text-warning">只读观察，不生成交易指令</small>}
      <small className="text-default-500">{cycleCadenceLabel(framework.rebalance_cadence)}</small>
    </div>
  );
}
