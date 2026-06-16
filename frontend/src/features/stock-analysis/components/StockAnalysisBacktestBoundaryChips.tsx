import {
  DatabaseOutlined,
  LineChartOutlined,
} from "@ant-design/icons";

import { compactStockText } from "../lib/stockAnalysisPageCopy";
import { cycleInputLabel } from "../lib/stockAnalysisPageLabels";

export function BacktestBoundaryChips({
  label,
  missingInputs,
  testId,
}: {
  label: string;
  missingInputs: readonly string[];
  testId?: string;
}) {
  const missing = missingInputs.filter((item) => item.trim().length > 0);

  return (
    <div
      className="stock-analysis-page__boundary-chip-bar"
      role="status"
      aria-label={`${label}边界`}
      data-testid={testId}
    >
      <span className="stock-analysis-page__boundary-chip stock-analysis-page__boundary-chip--accent">
        <LineChartOutlined aria-hidden="true" /> 代理口径
      </span>
      <span className="stock-analysis-page__boundary-chip stock-analysis-page__boundary-chip--warn">
        <DatabaseOutlined aria-hidden="true" /> 缺口 {missing.length}
      </span>
      {missing.slice(0, 3).map((input) => {
        const labelText = cycleInputLabel(input);
        return (
          <span
            key={input}
            className="stock-analysis-page__boundary-chip stock-analysis-page__boundary-chip--truncate"
            title={labelText}
          >
            {compactStockText(labelText, 10)}
          </span>
        );
      })}
      {missing.length > 3 ? (
        <span className="stock-analysis-page__boundary-chip">+{missing.length - 3}</span>
      ) : null}
    </div>
  );
}
