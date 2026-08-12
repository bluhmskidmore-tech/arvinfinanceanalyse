import { useState } from "react";
import { Tag } from "antd";

import type {
  MacroToolkitModelChainModel,
  MacroToolkitModelChainResults,
  MacroToolkitModelChainStep,
  MacroToolkitModelChainTrend,
  MacroToolkitSchedulerReceiptSummary,
} from "../../../api/macroToolkitClient";
import { EM_DASH } from "../../../utils/format";

const NUMERIC_CELL_PATTERN = /^-?\d[\d,]*(?:\.\d+)?%?$/;

const TREND_CHART_WIDTH = 260;
const TREND_CHART_HEIGHT = 56;
const TREND_CHART_PADDING = 4;
const TREND_LINE_COLOR_COUNT = 4;

function buildTrendPolylinePoints(
  points: [string, number][],
  min: number,
  span: number,
): string {
  const innerWidth = TREND_CHART_WIDTH - TREND_CHART_PADDING * 2;
  const innerHeight = TREND_CHART_HEIGHT - TREND_CHART_PADDING * 2;
  const step = innerWidth / (points.length - 1);
  return points
    .map(([, value], index) => {
      const x = TREND_CHART_PADDING + index * step;
      const y = TREND_CHART_PADDING + innerHeight * (1 - (value - min) / span);
      return `${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");
}

function ModelChainTrendChart({
  modelId,
  trend,
}: {
  modelId: string;
  trend: MacroToolkitModelChainTrend;
}) {
  const series = trend.series.filter((line) => line.points.length >= 2);
  if (!series.length) {
    return null;
  }
  const values = series.flatMap((line) => line.points.map(([, value]) => value));
  const min = Math.min(...values);
  const span = Math.max(...values) - min || 1;
  return (
    <figure className="macro-toolkit-model-chain__trend">
      <svg
        className="macro-toolkit-model-chain__trend-chart"
        viewBox={`0 0 ${TREND_CHART_WIDTH} ${TREND_CHART_HEIGHT}`}
        width={TREND_CHART_WIDTH}
        height={TREND_CHART_HEIGHT}
        role="img"
        aria-label={`${trend.label} · ${series.length} 条序列`}
        data-testid={`macro-toolkit-model-chain-trend-${modelId}`}
      >
        {series.map((line, lineIndex) => {
          const firstDate = line.points[0]![0];
          const lastDate = line.points[line.points.length - 1]![0];
          return (
            <polyline
              key={line.name}
              className={`macro-toolkit-model-chain__trend-line macro-toolkit-model-chain__trend-line--${lineIndex % TREND_LINE_COLOR_COUNT}`}
              points={buildTrendPolylinePoints(line.points, min, span)}
              fill="none"
            >
              <title>{`${line.name} · ${firstDate} ~ ${lastDate}`}</title>
            </polyline>
          );
        })}
      </svg>
      <figcaption className="macro-toolkit-model-chain__trend-label">{trend.label}</figcaption>
    </figure>
  );
}

const SCHEDULER_HEALTHY_STATUSES = new Set(["completed", "degraded", "success"]);

/** ISO 时间 → 本地时区 "MM-dd HH:mm"（回执 generated_at 为 UTC，直接截取会误导本地运维判断）。 */
function formatReceiptTimestamp(generatedAt: string): string {
  const parsed = new Date(generatedAt);
  if (Number.isNaN(parsed.getTime())) {
    const day = generatedAt.slice(5, 10);
    const time = generatedAt.slice(11, 16);
    return time ? `${day} ${time}` : day;
  }
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${pad(parsed.getMonth() + 1)}-${pad(parsed.getDate())} ${pad(parsed.getHours())}:${pad(parsed.getMinutes())}`;
}

function SchedulerBadge({
  kind,
  label,
  receipt,
}: {
  kind: "daily_chain" | "freshness";
  label: string;
  receipt: MacroToolkitSchedulerReceiptSummary | null;
}) {
  const testId = `macro-toolkit-model-chain-scheduler-${kind}`;
  if (!receipt) {
    return (
      <span
        className="macro-toolkit-model-chain__scheduler-badge macro-toolkit-model-chain__scheduler-badge--idle"
        data-testid={testId}
      >
        {label} 未运行
      </span>
    );
  }
  const healthy = receipt.exit_code === 0 || SCHEDULER_HEALTHY_STATUSES.has(receipt.status);
  const toneClass = healthy
    ? "macro-toolkit-model-chain__scheduler-badge--ok"
    : "macro-toolkit-model-chain__scheduler-badge--failed";
  return (
    <span
      className={`macro-toolkit-model-chain__scheduler-badge ${toneClass}`}
      data-testid={testId}
      title={receipt.summary}
    >
      {label} {formatReceiptTimestamp(receipt.generated_at)} {receipt.status}
    </span>
  );
}

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
      {model.trend ? <ModelChainTrendChart modelId={model.id} trend={model.trend} /> : null}
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
        <div className="macro-toolkit-model-chain__head-side">
          <Tag color="gold">仅观察 · 不入正式口径</Tag>
          {results.scheduler ? (
            <div
              className="macro-toolkit-model-chain__scheduler"
              data-testid="macro-toolkit-model-chain-scheduler"
              aria-label="调度健康状态"
            >
              <SchedulerBadge
                kind="daily_chain"
                label="自动重算"
                receipt={results.scheduler.daily_chain}
              />
              <SchedulerBadge
                kind="freshness"
                label="数据刷新"
                receipt={results.scheduler.freshness}
              />
            </div>
          ) : null}
        </div>
      </div>
      {results.steps.map((step) => (
        <ModelChainStepSection key={step.key} step={step} />
      ))}
    </section>
  );
}
