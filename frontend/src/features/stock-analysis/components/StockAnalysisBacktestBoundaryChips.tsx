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
      className="mb-2 flex flex-wrap items-center gap-1.5"
      role="status"
      aria-label={`${label}边界`}
      data-testid={testId}
    >
      <span className="inline-flex items-center gap-1.5 rounded-md border border-primary-100 bg-primary-50 px-2 py-1 text-[11px] font-bold text-primary-700">
        <LineChartOutlined aria-hidden="true" /> 代理口径
      </span>
      <span className="inline-flex items-center gap-1.5 rounded-md border border-warning-200 bg-warning-50 px-2 py-1 text-[11px] font-bold text-warning-700">
        <DatabaseOutlined aria-hidden="true" /> 缺口 {missing.length}
      </span>
      {missing.slice(0, 3).map((input) => {
        const labelText = cycleInputLabel(input);
        return (
          <span
            key={input}
            className="inline-flex max-w-36 items-center truncate rounded-md border border-neutral-200 bg-white px-2 py-1 text-[11px] font-semibold text-neutral-600"
            title={labelText}
          >
            {compactStockText(labelText, 10)}
          </span>
        );
      })}
      {missing.length > 3 ? (
        <span className="inline-flex items-center rounded-md border border-neutral-200 bg-white px-2 py-1 text-[11px] font-semibold text-neutral-600">
          +{missing.length - 3}
        </span>
      ) : null}
    </div>
  );
}
