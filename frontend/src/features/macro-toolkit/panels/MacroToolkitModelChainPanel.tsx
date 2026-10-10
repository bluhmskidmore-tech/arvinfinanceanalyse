import { useState } from "react";
import { Tag } from "antd";

import type {
  MacroToolkitBacktestContext,
  MacroToolkitModelChainArtifactSnapshot,
  MacroToolkitModelChainModel,
  MacroToolkitModelChainResults,
  MacroToolkitModelChainStep,
  MacroToolkitModelChainTrend,
  MacroToolkitModelReadiness,
  MacroToolkitSchedulerReceiptSummary,
} from "../../../api/macroToolkitClient";
import { EM_DASH } from "../../../utils/format";
import { statusLabel } from "../lib/macroToolkitPanelShared";
import {
  modelReadinessStatusColor,
  modelReadinessStatusLabel,
  modelSignalMatrixLabel,
  useModelChainEvidenceBridge,
} from "./macroToolkitModelEvidenceShared";
import { ModelSignalDetail } from "./MacroToolkitSignalPanels";

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

/** 调度状态词中文化（02-copy §三）；原始状态保留在 title（receipt.summary 已含链状态原文）。 */
function schedulerStatusLabel(status: string) {
  return status === "success" ? "成功" : statusLabel(status);
}

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

function formatModelAsOf(asOf: string | null | undefined): string {
  return asOf ?? "未知";
}

function formatModelGeneratedAt(generatedAt: string | null | undefined): string {
  return generatedAt ? formatReceiptTimestamp(generatedAt) : EM_DASH;
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
  if (receipt.read_status === "invalid") {
    return (
      <span
        className="macro-toolkit-model-chain__scheduler-badge macro-toolkit-model-chain__scheduler-badge--failed"
        data-testid={testId}
        title={receipt.summary}
      >
        {label} 回执不可读/损坏
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
      {label} {formatReceiptTimestamp(receipt.generated_at)} {schedulerStatusLabel(receipt.status)}
    </span>
  );
}

function ArtifactSnapshotBadge({ snapshot }: { snapshot: MacroToolkitModelChainArtifactSnapshot }) {
  const readStatus = snapshot.read_status ?? snapshot.status;
  const writerStatus = snapshot.writer_status ?? snapshot.snapshot_status;
  const isVerified =
    snapshot.mode === "snapshot" && readStatus === "ready" && writerStatus === "captured";
  const assurance =
    snapshot.mode === "live_unverified"
      ? "仅作未验证证据"
      : isVerified
        ? "已验证快照"
        : "不可正式使用";
  // 徽标只留业务结论（可否正式使用）；模式/读写状态的英文枚举与 run_id 是系统标识，
  // 连同告警原文一起收进 title，业务段头不再出现中英混排技术串。
  const details = [
    `模式 ${snapshot.mode}`,
    `读取 ${readStatus}`,
    `写入 ${writerStatus ?? "未知"}`,
    ...(snapshot.run_id ? [`run_id ${snapshot.run_id}`] : []),
    ...(snapshot.warnings.length ? [snapshot.warnings.join("；")] : []),
  ];
  return (
    <Tag
      color={isVerified ? "green" : snapshot.mode === "live_unverified" ? "gold" : "red"}
      data-testid="macro-toolkit-model-chain-artifact-snapshot"
      title={details.join(" · ")}
    >
      {assurance}
    </Tag>
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

const BACKTEST_GATE_REASON_LABEL: Record<
  MacroToolkitBacktestContext["pit_gate"]["reason_code"],
  string
> = {
  pit_metadata_unavailable: "PIT 元数据不可用",
  pit_evidence_unverified: "PIT 逐行证据未验证",
  backtest_manifest_missing: "回测运行清单缺失",
  backtest_manifest_invalid: "回测运行清单无效",
};

function BacktestContextSummary({ context }: { context: MacroToolkitBacktestContext }) {
  const { sample, asset_coverage: assetCoverage, pit_gate: pitGate } = context;
  return (
    <section
      className="macro-toolkit-model-chain__backtest-context"
      aria-label="回测准入与样本口径"
      data-testid="macro-toolkit-model-chain-backtest-context"
      title={context.warnings.join("；") || undefined}
    >
      <div className="macro-toolkit-model-chain__backtest-status">
        <strong>未准入</strong>
        <span>PIT 门禁阻断</span>
        <span>{context.formal_use_allowed ? "允许正式使用" : "禁止正式使用"}</span>
      </div>
      <dl className="macro-toolkit-model-chain__backtest-facts">
        <div>
          <dt>收益样本</dt>
          <dd>
            {sample.return_start_date || sample.return_end_date
              ? `${sample.return_start_date ?? EM_DASH} 至 ${sample.return_end_date ?? EM_DASH}`
              : EM_DASH}
            <span>
              {sample.return_trading_days == null
                ? EM_DASH
                : `${sample.return_trading_days} 个交易日`}
            </span>
          </dd>
        </div>
        <div>
          <dt>价格观测</dt>
          <dd>
            {sample.price_observation_days == null
              ? EM_DASH
              : `${sample.price_observation_days} 条`}
            <span>
              {sample.price_start_date || sample.price_end_date
                ? `${sample.price_start_date ?? EM_DASH} 至 ${sample.price_end_date ?? EM_DASH}`
                : EM_DASH}
            </span>
          </dd>
        </div>
        <div>
          <dt>资产覆盖</dt>
          <dd>
            {assetCoverage.used_asset_count ?? EM_DASH} /{" "}
            {assetCoverage.configured_asset_count ?? EM_DASH}
            <span>
              {sample.declared_window_years == null
                ? "目标上限未返回"
                : `目标上限 ${sample.declared_window_years} 年`} · 实际以收益样本为准
            </span>
          </dd>
        </div>
        <div className="macro-toolkit-model-chain__backtest-fact--wide">
          <dt>缺失资产</dt>
          <dd>
            {assetCoverage.missing_assets.length
              ? assetCoverage.missing_assets.join("、")
              : EM_DASH}
          </dd>
        </div>
        <div className="macro-toolkit-model-chain__backtest-fact--wide">
          <dt>门禁依据</dt>
          <dd>
            {BACKTEST_GATE_REASON_LABEL[pitGate.reason_code]}
            <span>
              完整度{" "}
              {pitGate.completeness_pct == null ? EM_DASH : `${pitGate.completeness_pct}%`}；规则{" "}
              {pitGate.decision_rule || EM_DASH}
            </span>
          </dd>
        </div>
      </dl>
    </section>
  );
}

function ModelChainModelCard({
  model,
  readiness,
  evidenceOpen,
  onToggleEvidence,
}: {
  model: MacroToolkitModelChainModel;
  readiness: MacroToolkitModelReadiness | null;
  evidenceOpen: boolean;
  onToggleEvidence: (() => void) | null;
}) {
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
        {readiness ? (
          <Tag color={modelReadinessStatusColor(readiness.readiness)}>
            {modelReadinessStatusLabel(readiness.readiness)}
          </Tag>
        ) : null}
        {/* 数据日是业务口径日期，留在卡面；生成时间是系统运行时间戳，
            连同原始 ISO 一起收进 title，腾出的横向空间让业务读数完整显示。 */}
        <small
          title={`数据日 ${formatModelAsOf(model.as_of)} · 生成时间 ${formatModelGeneratedAt(
            model.generated_at,
          )}${model.generated_at ? ` · ${model.generated_at}` : ""}`}
        >
          数据日 {formatModelAsOf(model.as_of)}
        </small>
      </div>
      <strong>{model.headline || EM_DASH}</strong>
      {model.id === "backtest" && model.backtest_context ? (
        <BacktestContextSummary context={model.backtest_context} />
      ) : null}
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
      {readiness && onToggleEvidence ? (
        <button
          type="button"
          className="macro-toolkit-model-chain__evidence-button"
          aria-expanded={evidenceOpen}
          aria-label={`查看 ${model.label} 模型证据`}
          onClick={onToggleEvidence}
        >
          证据
        </button>
      ) : null}
    </article>
  );
}

function ModelChainStepSection({
  step,
  readinessForModel,
  evidenceKey,
  onToggleEvidence,
}: {
  step: MacroToolkitModelChainStep;
  readinessForModel: (model: MacroToolkitModelChainModel) => MacroToolkitModelReadiness | null;
  evidenceKey: string | null;
  onToggleEvidence: (readinessId: string) => void;
}) {
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
        {step.models.map((model) => {
          const readiness = readinessForModel(model);
          return (
            <ModelChainModelCard
              key={model.id}
              model={model}
              readiness={readiness}
              evidenceOpen={readiness != null && evidenceKey === readiness.id}
              onToggleEvidence={readiness ? () => onToggleEvidence(readiness.id) : null}
            />
          );
        })}
      </div>
    </section>
  );
}

export function MacroToolkitModelChainPanel({
  results,
}: {
  results: MacroToolkitModelChainResults;
}) {
  const [cardsExpanded, setCardsExpanded] = useState(false);
  const [evidenceKey, setEvidenceKey] = useState<string | null>(null);
  // 就绪度角标与证据抽屉的数据来自模型信号摘要（同页兄弟区块）发布的证据桥；
  // 面板单测或桥未发布时退回纯链视图。
  const bridge = useModelChainEvidenceBridge();
  if (!results.steps.length) {
    return null;
  }
  const readinessById = new Map<string, MacroToolkitModelReadiness>();
  const readinessByScript = new Map<string, MacroToolkitModelReadiness>();
  for (const entry of bridge?.entries ?? []) {
    if (!readinessById.has(entry.id)) readinessById.set(entry.id, entry);
    if (!readinessByScript.has(entry.script_name)) readinessByScript.set(entry.script_name, entry);
  }
  const readinessForModel = (model: MacroToolkitModelChainModel) =>
    readinessById.get(model.id) ?? readinessByScript.get(model.script_name) ?? null;
  const matchedReadinessIds = new Set<string>();
  for (const step of results.steps) {
    for (const model of step.models) {
      const readiness = readinessForModel(model);
      if (readiness) matchedReadinessIds.add(readiness.id);
    }
  }
  const offChainEntries = (bridge?.entries ?? []).filter((entry) => !matchedReadinessIds.has(entry.id));
  const scriptCounts = (bridge?.entries ?? []).reduce<Record<string, number>>((counts, entry) => {
    counts[entry.script_name] = (counts[entry.script_name] ?? 0) + 1;
    return counts;
  }, {});
  const selectedReadiness = evidenceKey
    ? (bridge?.entries ?? []).find((entry) => entry.id === evidenceKey) ?? null
    : null;
  const toggleEvidence = (readinessId: string) =>
    setEvidenceKey((current) => (current === readinessId ? null : readinessId));
  return (
    <section
      className={`macro-toolkit-section macro-toolkit-model-chain${
        cardsExpanded ? "" : " macro-toolkit-model-chain--cards-collapsed"
      }`}
      aria-label="模型链结果决策链视图"
      data-testid="macro-toolkit-model-chain"
    >
      <div className="macro-toolkit-model-chain__head">
        <div>
          <span>模型链</span>
          <strong>模型链结果 · 决策链视图</strong>
          <small>数据日 {results.as_of_date ?? EM_DASH}</small>
        </div>
        <div className="macro-toolkit-model-chain__head-side">
          {/* H：口径披露降为 11px 元信息文字，模块头只保留产物快照一枚徽标。 */}
          <span className="macro-toolkit-model-chain__scope-note">仅观察 · 不入正式口径</span>
          {results.artifact_snapshot ? (
            <ArtifactSnapshotBadge snapshot={results.artifact_snapshot} />
          ) : null}
          <button
            type="button"
            className="macro-toolkit-model-chain__wall-toggle"
            aria-expanded={cardsExpanded}
            onClick={() => setCardsExpanded((current) => !current)}
          >
            {cardsExpanded ? "收起全部模型卡" : "展开全部模型卡"}
          </button>
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
        <ModelChainStepSection
          key={step.key}
          step={step}
          readinessForModel={readinessForModel}
          evidenceKey={evidenceKey}
          onToggleEvidence={toggleEvidence}
        />
      ))}
      {offChainEntries.length ? (
        <div className="macro-toolkit-model-chain__offchain">
          <span>链外模型证据</span>
          {offChainEntries.map((entry) => (
            <button
              key={entry.id}
              type="button"
              className="macro-toolkit-model-chain__evidence-button"
              aria-expanded={evidenceKey === entry.id}
              aria-label={`查看 ${modelSignalMatrixLabel(entry)} 模型证据`}
              onClick={() => toggleEvidence(entry.id)}
            >
              {modelSignalMatrixLabel(entry)}
            </button>
          ))}
        </div>
      ) : null}
      {selectedReadiness ? (
        <ModelSignalDetail
          item={selectedReadiness}
          chainRunResult={bridge?.chainRunResult ?? null}
          isSharedScript={(scriptCounts[selectedReadiness.script_name] ?? 0) > 1}
          showActions={bridge?.showAcceptance ?? false}
        />
      ) : null}
    </section>
  );
}
