import {
  DatabaseOutlined,
  LineChartOutlined,
} from "@ant-design/icons";
import { StockAnalysisInlineChip as Chip } from "./StockAnalysisStatusPrimitives";

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
      className="flex flex-wrap gap-2 items-center text-sm mb-4"
      role="status"
      aria-label={`${label}边界`}
      data-testid={testId}
    >
      <Chip color="primary" variant="flat" startContent={<LineChartOutlined aria-hidden="true" />}>
        代理口径
      </Chip>
      <Chip color="warning" variant="flat" startContent={<DatabaseOutlined aria-hidden="true" />}>
        缺口 {missing.length}
      </Chip>
      {missing.slice(0, 3).map((input) => {
        const labelText = cycleInputLabel(input);
        return (
          <Chip
            key={input}
            variant="bordered"
            title={labelText}
            className="truncate max-w-[150px]"
          >
            {compactStockText(labelText, 10)}
          </Chip>
        );
      })}
      {missing.length > 3 ? (
        <Chip variant="bordered">+{missing.length - 3}</Chip>
      ) : null}
    </div>
  );
}
