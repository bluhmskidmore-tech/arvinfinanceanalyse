import { useState } from "react";
import { Tag } from "antd";

import type {
  MacroToolkitModelChainModel,
  MacroToolkitModelChainResults,
  MacroToolkitModelChainStep,
} from "../../../api/macroToolkitClient";
import { EM_DASH } from "../../../utils/format";

const NUMERIC_CELL_PATTERN = /^-?\d[\d,]*(?:\.\d+)?%?$/;

function isNumericColumn(model: MacroToolkitModelChainModel, columnIndex: number) {
  if (columnIndex === 0) {
    return false;
  }
  const values = model.rows
    .map((row) => row[columnIndex] ?? "")
    .filter((value) => value !== "");
  return values.length > 0 && values.every((value) => NUMERIC_CELL_PATTERN.test(value));
}

function ModelChainTable({ model }: { model: MacroToolkitModelChainModel }) {
  const numericColumns = model.columns.map((_, columnIndex) => isNumericColumn(model, columnIndex));
  return (
    <table className="macro-toolkit-model-chain__table">
      <thead>
        <tr>
          {model.columns.map((column, columnIndex) => (
            <th
              key={column}
              className={numericColumns[columnIndex] ? "macro-toolkit-model-chain__cell--numeric" : undefined}
            >
              {column}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {model.rows.map((row, rowIndex) => (
          <tr key={`${model.id}-${rowIndex}`}>
            {model.columns.map((column, columnIndex) => (
              <td
                key={column}
                className={numericColumns[columnIndex] ? "macro-toolkit-model-chain__cell--numeric" : undefined}
              >
                {row[columnIndex] ? row[columnIndex] : EM_DASH}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function ModelChainModelCard({ model }: { model: MacroToolkitModelChainModel }) {
  const [expanded, setExpanded] = useState(false);
  const isMissing = model.artifact_status === "missing";
  const tableId = `macro-toolkit-model-chain-table-${model.id}`;
  return (
    <article
      className="macro-toolkit-model-chain__model"
      data-testid={`macro-toolkit-model-chain-model-${model.id}`}
    >
      <div className="macro-toolkit-model-chain__model-head">
        <span title={`${model.script_name} · ${model.artifact}`}>{model.label}</span>
        <small>{model.as_of ?? EM_DASH}</small>
      </div>
      <strong>{model.headline || EM_DASH}</strong>
      {isMissing ? (
        <div className="macro-toolkit-model-chain__missing">产物缺失</div>
      ) : (
        <>
          <button
            type="button"
            className="macro-toolkit-model-chain__toggle"
            aria-expanded={expanded}
            aria-controls={tableId}
            aria-label={`${expanded ? "收起" : "展开"} ${model.label} 明细`}
            onClick={() => setExpanded((current) => !current)}
          >
            {expanded ? "收起明细" : "展开明细"}
          </button>
          {expanded ? (
            <div className="macro-toolkit-model-chain__table-wrap" id={tableId}>
              <ModelChainTable model={model} />
            </div>
          ) : null}
        </>
      )}
    </article>
  );
}

function ModelChainStepSection({ step }: { step: MacroToolkitModelChainStep }) {
  return (
    <section
      className="macro-toolkit-model-chain__step"
      aria-label={`第 ${step.step_no} 步 ${step.label}`}
      data-testid={`macro-toolkit-model-chain-step-${step.key}`}
    >
      <div className="macro-toolkit-model-chain__step-head">
        <span>第 {step.step_no} 步</span>
        <strong>{step.label}</strong>
        <small>{step.models.length} 个模型</small>
      </div>
      <div className="macro-toolkit-model-chain__step-models">
        {step.models.map((model) => (
          <ModelChainModelCard key={model.id} model={model} />
        ))}
      </div>
    </section>
  );
}

export function MacroToolkitModelChainPanel({
  results,
}: {
  results: MacroToolkitModelChainResults;
}) {
  if (!results.steps.length) {
    return null;
  }
  return (
    <section
      className="macro-toolkit-section macro-toolkit-model-chain"
      aria-label="模型链结果决策链视图"
      data-testid="macro-toolkit-model-chain"
    >
      <div className="macro-toolkit-model-chain__head">
        <div>
          <span>模型链</span>
          <strong>模型链结果 · 决策链视图</strong>
          <small>数据日 {results.as_of_date ?? EM_DASH} · 按决策链七步分组展示模型最新结果</small>
        </div>
        <Tag color="gold">仅观察 · 不入正式口径</Tag>
      </div>
      {results.steps.map((step) => (
        <ModelChainStepSection key={step.key} step={step} />
      ))}
    </section>
  );
}
