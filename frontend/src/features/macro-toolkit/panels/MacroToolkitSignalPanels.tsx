import { useState } from "react";
import {
  InfoCircleOutlined,
  PlayCircleOutlined,
  SafetyCertificateOutlined,
  ToolOutlined,
  DatabaseOutlined,
} from "@ant-design/icons";
import { Button, Tag } from "antd";
import type {
  MacroToolkitHasonStrategy,
  MacroToolkitModelReadiness,
  MacroToolkitReadinessSummary,
  MacroToolkitScriptChainRun,
} from "../../../api/macroToolkitClient";
import {
  MetricTile,
  formatPercent,
  observationStatusLabel,
  statusColor,
  statusLabel,
} from "../lib/macroToolkitPanelShared";

export function HasonMacroStrategyPanel({
  strategy,
  modelReadiness = [],
  variant = "detail",
}: {
  strategy: MacroToolkitHasonStrategy;
  modelReadiness?: MacroToolkitModelReadiness[];
  variant?: "detail" | "observation";
}) {
  const readiness = strategy.readiness;
  const readinessText = `${readiness.ready_modules}/${readiness.total_modules}`;
  const runtimeOutputsCurrent = strategy.runtime_output_status === "current";
  const runtimeOutputGaps = strategy.runtime_output_gaps;
  const runtimeOutputValue = runtimeOutputsCurrent
    ? "current"
    : `${strategy.runtime_output_status} · ${runtimeOutputGaps.length}`;
  const runtimeOutputDetail = runtimeOutputGaps.length
    ? runtimeOutputGaps.join(" / ")
    : strategy.required_runtime_outputs.join(" / ");
  const runtimeGapText = runtimeOutputGaps.length
    ? runtimeOutputGaps.join(" / ")
    : runtimeOutputsCurrent
      ? "none"
      : "freshness not confirmed";
  const readinessEntries = modelReadiness.length ? modelReadiness : deriveModelReadinessFromHasonStrategy(strategy);
  const blockedReadinessEntries = readinessEntries.filter((item) => !isArtifactBackedModelReadiness(item.readiness));
  const readinessHeadline = blockedReadinessEntries.length
    ? blockedReadinessEntries.map((item) => `${item.label} ${modelReadinessStatusLabel(item.readiness)}`).join(" / ")
    : "all observed models remain observation-only";
  const readinessDetail = blockedReadinessEntries.length
    ? blockedReadinessEntries.map(formatModelReadinessDetail).join(" / ")
    : readinessEntries.map((item) => `${item.label} ${modelReadinessStatusLabel(item.readiness)}`).join(" / ");
  const tracedScripts = strategy.source_trace;
  const tracedScriptPreview = tracedScripts.slice(0, 5);
  if (variant === "observation") {
    return (
      <section
        className="macro-toolkit-section macro-toolkit-hason-strategy macro-toolkit-hason-strategy--observation"
        data-testid="macro-toolkit-hason-strategy"
      >
        <div className="macro-toolkit-hason-strategy__head">
          <div>
            <span>Hason 观察框架</span>
            <strong>宏观对冲观察框架</strong>
            <small>只展示投研观察边界，完整模块和脚本审计留在工具页。</small>
          </div>
          <div className="macro-toolkit-tag-row">
            <Tag color={statusColor(strategy.status)}>{observationStatusLabel(strategy.status)}</Tag>
            <Tag color="gold">仅作观察</Tag>
            <Tag color={strategy.formal_use_allowed ? "green" : "default"}>
              {strategy.formal_use_allowed ? "正式可用" : "非正式信号"}
            </Tag>
          </div>
        </div>

        <div className="macro-toolkit-hason-strategy__metrics">
          <MetricTile
            icon={<SafetyCertificateOutlined />}
            label="观察覆盖"
            value={readinessText}
            detail={`${formatPercent(readiness.ratio)} 覆盖，缺口需人工复核。`}
            tone="neutral"
            detailMaxLength={40}
          />
          <MetricTile
            icon={<ToolOutlined />}
            label="缺口复核"
            value={readiness.missing_script_count + readiness.missing_modules}
            detail={`${readiness.partial_modules} 个部分就绪，${readiness.missing_modules} 个模块待补齐。`}
            tone={readiness.missing_script_count || readiness.missing_modules ? "missing" : "neutral"}
            detailMaxLength={40}
          />
          <MetricTile
            icon={<DatabaseOutlined />}
            label="运行证据"
            value={runtimeOutputsCurrent ? "已对齐" : observationStatusLabel(strategy.runtime_output_status)}
            detail={runtimeOutputGaps.length ? `${runtimeOutputGaps.length} 项输出待复核。` : "运行输出未发现待复核项。"}
            tone={runtimeOutputsCurrent ? "neutral" : "missing"}
            detailMaxLength={40}
          />
        </div>
        {readinessEntries.length ? (
          <div
            id="macro-toolkit-model-readiness-detail"
            className="macro-toolkit-hason-runtime"
            data-testid="macro-toolkit-model-readiness-detail"
          >
            <span>model readiness / observation-only</span>
            <strong>{readinessHeadline}</strong>
            <small>{readinessDetail}</small>
          </div>
        ) : null}
      </section>
    );
  }
  return (
    <section className="macro-toolkit-section macro-toolkit-hason-strategy" data-testid="macro-toolkit-hason-strategy">
      <div className="macro-toolkit-hason-strategy__head">
        <div>
          <span>Hason macro strategy</span>
          <strong>{strategy.framework_name}</strong>
          <small>{strategy.boundary}</small>
        </div>
        <div className="macro-toolkit-tag-row">
          <Tag color={statusColor(strategy.status)}>{statusLabel(strategy.status)}</Tag>
          <Tag color="blue">{strategy.basis}</Tag>
          <Tag color={strategy.observation_only ? "gold" : "green"}>
            {strategy.observation_only ? "observation-only" : "actionable"}
          </Tag>
          <Tag color={strategy.formal_use_allowed ? "green" : "default"}>
            {strategy.formal_metric_id ?? "no formal MTR"}
          </Tag>
        </div>
      </div>

      <div className="macro-toolkit-hason-strategy__metrics">
        <MetricTile
          icon={<SafetyCertificateOutlined />}
          label="Readiness"
          value={readinessText}
          detail={`${formatPercent(readiness.ratio)} module coverage`}
          tone="neutral"
        />
        <MetricTile
          icon={<ToolOutlined />}
          label="Module gaps"
          value={`${readiness.missing_script_count} missing script`}
          detail={`${readiness.partial_modules} partial / ${readiness.missing_modules} missing module`}
          tone="neutral"
        />
        <MetricTile
          icon={<DatabaseOutlined />}
          label="Runtime outputs"
          value={runtimeOutputValue}
          detail={runtimeOutputDetail}
          tone="neutral"
        />
        <MetricTile
          icon={<ToolOutlined />}
          label="Script trace"
          value={tracedScripts.length}
          detail={tracedScriptPreview.map(formatHasonTraceScript).join(" / ") || "no script available"}
          tone="neutral"
          testId="macro-toolkit-hason-script-trace"
        />
      </div>

      <div className="macro-toolkit-hason-module-grid">
        {strategy.modules.map((module) => (
          <div
            className="macro-toolkit-hason-module"
            data-testid={`macro-toolkit-hason-module-${module.key}`}
            key={module.key}
          >
            <div className="macro-toolkit-capability-result-head">
              <span>{module.key}</span>
              <Tag color={hasonModuleStatusColor(module.status)}>{hasonModuleStatusLabel(module.status)}</Tag>
            </div>
            <strong>{module.label}</strong>
            <small>可用脚本：{module.available_scripts.join(" / ") || "无"}</small>
            {module.missing_scripts.length ? (
              <small className="macro-toolkit-hason-module__missing">
                缺失脚本：{module.missing_scripts.join(" / ")}
              </small>
            ) : null}
            <div className="macro-toolkit-tag-row">
              {module.evidence.map((item) => (
                <Tag color="blue" key={`${module.key}-${item}`}>
                  {item}
                </Tag>
              ))}
            </div>
          </div>
        ))}
      </div>

      <div className="macro-toolkit-hason-runtime" data-testid="macro-toolkit-hason-runtime-gaps">
        <span>runtime outputs · {strategy.runtime_output_status}</span>
        <strong>{runtimeGapText}</strong>
        {strategy.runtime_outputs.length ? (
          <small>
            {strategy.runtime_outputs.map(formatHasonRuntimeOutput).join(" / ")}
          </small>
        ) : null}
      </div>
      {readinessEntries.length ? (
        <div
          id="macro-toolkit-model-readiness-detail"
          className="macro-toolkit-hason-runtime"
          data-testid="macro-toolkit-model-readiness-detail"
        >
          <span>model readiness / observation-only</span>
          <strong>{readinessHeadline}</strong>
          <small>{readinessDetail}</small>
        </div>
      ) : null}
    </section>
  );
}

function formatHasonRuntimeOutput(item: MacroToolkitHasonStrategy["runtime_outputs"][number]) {
  return (
    `${item.name}: ${item.freshness_status} ${hasonFreshnessBasisLabel(item.freshness_basis)}` +
    `${hasonContentDateText(item)}` +
    `${hasonInvalidDateText(item)}` +
    `${item.modified_date ? ` file ${item.modified_date}` : ""}`
  );
}

const MODEL_SIGNAL_MATRIX_ORDER = [
  "merrill_clock",
  "crisis_score",
  "bond_futures_four_factor",
  "funding_conditions",
  "crowding",
  "dcc_garch",
  "cta_trend",
  "bond_futures_basis",
  "final_signal",
  "risk_monitor",
] as const;

const MODEL_SIGNAL_MATRIX_LABELS: Record<string, string> = {
  merrill_clock: "Merrill Clock",
  crisis_score: "Crisis Score",
  bond_futures_basis: "Bond Futures Basis / IRR / Safety Margin",
  bond_futures_four_factor: "Bond Futures Four-Factor Trend",
  funding_conditions: "Funding Conditions / Flow",
  crowding: "Crowding",
  dcc_garch: "DCC-GARCH",
  cta_trend: "CTA Trend",
  final_signal: "Final Signal Aggregator",
  risk_monitor: "Risk Monitor",
};

function modelSignalMatrixOrder(item: MacroToolkitModelReadiness) {
  const index = MODEL_SIGNAL_MATRIX_ORDER.indexOf(item.id as (typeof MODEL_SIGNAL_MATRIX_ORDER)[number]);
  return index === -1 ? MODEL_SIGNAL_MATRIX_ORDER.length : index;
}

function modelReadinessStatusColor(readiness: MacroToolkitModelReadiness["readiness"]) {
  if (readiness === "artifact_backed") return "green";
  if (readiness === "stale" || readiness === "degraded" || readiness === "registered_only") return "gold";
  if (readiness === "missing_output") return "red";
  return "default";
}

function modelSignalDateText(item: MacroToolkitModelReadiness) {
  return item.latest_content_date ?? item.artifact_receipt?.data_asof ?? item.latest_modified_at ?? "date pending";
}

function modelSignalEvidenceText(item: MacroToolkitModelReadiness) {
  const artifacts = item.artifact_receipt?.artifact_paths ?? [];
  if (artifacts.length) return `artifacts ${artifacts.join(" / ")}`;
  if (item.missing_outputs.length) return `missing ${item.missing_outputs.join(" / ")}`;
  if (item.stale_outputs.length) return `stale ${item.stale_outputs.join(" / ")}`;
  if (item.expected_outputs.length) return `expected ${item.expected_outputs.join(" / ")}`;
  return item.evidence_level ?? "evidence pending";
}

function modelSignalThresholdText(item: MacroToolkitModelReadiness) {
  const gaps = [
    item.degraded_reason ?? "",
    item.degraded_outputs?.length ? `degraded ${item.degraded_outputs.join(" / ")}` : "",
    item.missing_outputs.length ? `missing output ${item.missing_outputs.length}` : "",
    item.stale_outputs.length ? `stale output ${item.stale_outputs.length}` : "",
  ].filter(Boolean);
  return gaps.join(" · ") || "threshold clear by current artifacts";
}

function modelSignalSummaryText(
  readinessEntries: MacroToolkitModelReadiness[],
  readinessSummary?: MacroToolkitReadinessSummary,
) {
  const total = readinessSummary?.total_count ?? readinessEntries.length;
  const backed =
    readinessSummary?.artifact_backed_count ??
    readinessEntries.filter((item) => item.readiness === "artifact_backed").length;
  const degraded =
    readinessSummary?.degraded_count ??
    readinessEntries.filter((item) => item.readiness !== "artifact_backed").length;
  return `artifact-backed ${backed}/${total} · degraded ${degraded}`;
}

function modelSignalArtifactList(items: string[] | undefined, fallback = "none") {
  return items?.length ? items.join(" / ") : fallback;
}

function modelSignalReceiptRuntime(item: MacroToolkitModelReadiness) {
  return item.artifact_receipt?.runtime_endpoint ?? "runtime endpoint pending";
}

function modelSignalRunReceipt(
  item: MacroToolkitModelReadiness,
  chainRunResult: MacroToolkitScriptChainRun | null,
) {
  return chainRunResult?.receipts.find((receipt) => receipt.script_name === item.script_name) ?? null;
}

function ModelSignalDetail({
  item,
  chainRunResult,
  chainRunError,
  chainRunModelId,
  isSharedScript,
  isRunningChain,
  showActions,
  onRunChain,
}: {
  item: MacroToolkitModelReadiness;
  chainRunResult: MacroToolkitScriptChainRun | null;
  chainRunError: string | null;
  chainRunModelId: string | null;
  isSharedScript: boolean;
  isRunningChain: boolean;
  showActions: boolean;
  onRunChain: (dryRun: boolean, modelId?: string) => void;
}) {
  const receipt = item.artifact_receipt;
  const isLatestChainModel = chainRunModelId === item.id;
  const runReceipt = isLatestChainModel ? modelSignalRunReceipt(item, chainRunResult) : null;
  return (
    <aside className="macro-toolkit-model-signal-detail" data-testid="macro-toolkit-model-signal-detail">
      <div className="macro-toolkit-model-signal-detail__head">
        <div>
          <span>model evidence</span>
          <strong>{MODEL_SIGNAL_MATRIX_LABELS[item.id] ?? item.label}</strong>
          <small>
            {item.script_name} 路 {modelReadinessStatusLabel(item.readiness)} 路 {modelSignalDateText(item)}
          </small>
        </div>
        <div className="macro-toolkit-model-signal-matrix__boundary">
          <Tag color={item.observation_only ? "gold" : "green"}>
            {item.observation_only ? "observation-only" : "actionable"}
          </Tag>
          <Tag color={item.formal_use_allowed ? "green" : "default"}>
            {item.formal_use_allowed ? "formal" : "non-formal"}
          </Tag>
        </div>
      </div>
      <div className="macro-toolkit-model-signal-detail__grid">
        <div>
          <span>Expected outputs</span>
          <strong>{modelSignalArtifactList(item.expected_outputs)}</strong>
        </div>
        <div>
          <span>Present artifacts</span>
          <strong>{modelSignalArtifactList(receipt?.artifact_paths)}</strong>
        </div>
        <div>
          <span>Missing artifacts</span>
          <strong>{modelSignalArtifactList(receipt?.missing_artifacts ?? item.missing_outputs)}</strong>
        </div>
        <div>
          <span>Stale artifacts</span>
          <strong>{modelSignalArtifactList(item.stale_outputs)}</strong>
        </div>
        <div>
          <span>Runtime endpoint</span>
          <strong>{modelSignalReceiptRuntime(item)}</strong>
        </div>
        <div>
          <span>Threshold note</span>
          <strong>{modelSignalThresholdText(item)}</strong>
        </div>
      </div>
      {item.notes.length ? <p>{item.notes.join(" / ")}</p> : null}
      {showActions ? (
        <div className="macro-toolkit-model-signal-detail__acceptance">
          <div>
            <span>Artifact-backed acceptance</span>
            <strong>{item.readiness === "artifact_backed" ? "current artifacts accepted" : "run-chain required"}</strong>
            <small>
              {item.readiness === "artifact_backed"
                ? "Current backend readiness marks this model artifact-backed."
                : "Run preflight first, then run the model chain and compare latest receipt with expected outputs."}
            </small>
          </div>
          <div className="macro-toolkit-model-signal-detail__actions">
            <Button
              data-testid="macro-toolkit-model-signal-chain-preflight"
              icon={<InfoCircleOutlined />}
              loading={isRunningChain}
              disabled={isRunningChain}
              size="small"
              onClick={() => onRunChain(true, item.id)}
            >
              Preflight chain
            </Button>
            <Button
              data-testid="macro-toolkit-model-signal-chain-run"
              icon={<PlayCircleOutlined />}
              loading={isRunningChain}
              disabled={isRunningChain}
              size="small"
              onClick={() => onRunChain(false, item.id)}
            >
              Run chain
            </Button>
          </div>
        </div>
      ) : null}
      {runReceipt ? (
        <div className="macro-toolkit-model-signal-detail__receipt">
          <span>Latest script run receipt</span>
          <strong>
            {runReceipt.script_name} · {runReceipt.status}
          </strong>
          <small>
            expected {modelSignalArtifactList(runReceipt.expected_outputs)} · produced{" "}
            {modelSignalArtifactList(runReceipt.produced_outputs)} · missing{" "}
            {modelSignalArtifactList(runReceipt.missing_outputs_after)} ·{" "}
            {isSharedScript ? "shared script receipt 路 " : ""}
            {runReceipt.degraded_reason ?? "no degraded reason"}
          </small>
        </div>
      ) : null}
      {isLatestChainModel && chainRunError ? (
        <div className="macro-toolkit-model-signal-detail__receipt macro-toolkit-model-signal-detail__receipt--error">
          <span>Latest run issue</span>
          <strong>{chainRunError}</strong>
          <small>Check execute permission, script dependencies, and run-chain receipt.</small>
        </div>
      ) : null}
      <div className="macro-toolkit-model-signal-detail__links">
        <a href="#macro-toolkit-script-artifact-detail">查看脚本产物</a>
        <a href="#macro-toolkit-model-readiness-detail">查看 readiness 摘要</a>
      </div>
    </aside>
  );
}

export function ModelSignalMatrix({
  modelReadiness,
  readinessSummary,
  chainRunResult,
  chainRunError,
  chainRunModelId,
  isRunningChain,
  showActions,
  onRunChain,
}: {
  modelReadiness: MacroToolkitModelReadiness[];
  readinessSummary?: MacroToolkitReadinessSummary;
  chainRunResult: MacroToolkitScriptChainRun | null;
  chainRunError: string | null;
  chainRunModelId: string | null;
  isRunningChain: boolean;
  showActions: boolean;
  onRunChain: (dryRun: boolean, modelId?: string) => void;
}) {
  const [selectedModelId, setSelectedModelId] = useState<string | null>(null);
  if (!modelReadiness.length) {
    return null;
  }
  const rows = [...modelReadiness].sort((left, right) => {
    const byOrder = modelSignalMatrixOrder(left) - modelSignalMatrixOrder(right);
    return byOrder || left.label.localeCompare(right.label);
  });
  const selectedModel = rows.find((item) => item.id === selectedModelId) ?? null;
  const scriptCounts = rows.reduce<Record<string, number>>((counts, item) => {
    counts[item.script_name] = (counts[item.script_name] ?? 0) + 1;
    return counts;
  }, {});
  const boundaryText = readinessSummary
    ? `${readinessSummary.observation_only ? "observation-only" : "actionable"} · ${
        readinessSummary.formal_use_allowed ? "formal use allowed" : "formal use blocked"
      }`
    : "boundary pending backend summary · formal use blocked";

  return (
    <section className="macro-toolkit-section macro-toolkit-model-signal-matrix" data-testid="macro-toolkit-model-signal-matrix">
      <div className="macro-toolkit-model-signal-matrix__head">
        <div>
          <span>model signals</span>
          <strong>模型信号矩阵</strong>
          <small>
            {modelSignalSummaryText(rows, readinessSummary)} · {boundaryText}
          </small>
        </div>
        <a href="#macro-toolkit-script-artifact-detail">查看脚本产物证据</a>
      </div>
      <div className="macro-toolkit-model-signal-matrix__grid">
        {rows.map((item) => (
          <article className="macro-toolkit-model-signal-matrix__row" key={`${item.id}-${item.script_name}`}>
            <div className="macro-toolkit-model-signal-matrix__title">
              <span>{MODEL_SIGNAL_MATRIX_LABELS[item.id] ?? item.label}</span>
              <Tag color={modelReadinessStatusColor(item.readiness)}>{modelReadinessStatusLabel(item.readiness)}</Tag>
            </div>
            <strong>{modelSignalDateText(item)}</strong>
            <small>{modelSignalThresholdText(item)}</small>
            <div className="macro-toolkit-model-signal-matrix__evidence">
              <span>{item.script_name}</span>
              <em>{modelSignalEvidenceText(item)}</em>
            </div>
            <div className="macro-toolkit-model-signal-matrix__boundary">
              <Tag color={item.observation_only ? "gold" : "green"}>
                {item.observation_only ? "observation-only" : "actionable"}
              </Tag>
              <Tag color={item.formal_use_allowed ? "green" : "default"}>
                {item.formal_use_allowed ? "formal" : "non-formal"}
              </Tag>
            </div>
            <button
              className="macro-toolkit-model-signal-matrix__detail-button"
              type="button"
              aria-label={`查看 ${MODEL_SIGNAL_MATRIX_LABELS[item.id] ?? item.label} 模型证据`}
              aria-expanded={selectedModelId === item.id}
              onClick={() => setSelectedModelId((current) => (current === item.id ? null : item.id))}
            >
              证据
            </button>
          </article>
        ))}
      </div>
      {selectedModel ? (
        <ModelSignalDetail
          item={selectedModel}
          chainRunResult={chainRunResult}
          chainRunError={chainRunError}
          chainRunModelId={chainRunModelId}
          isSharedScript={(scriptCounts[selectedModel.script_name] ?? 0) > 1}
          isRunningChain={isRunningChain}
          showActions={showActions}
          onRunChain={onRunChain}
        />
      ) : null}
    </section>
  );
}

export function deriveModelReadinessFromHasonStrategy(strategy: MacroToolkitHasonStrategy): MacroToolkitModelReadiness[] {
  return strategy.source_trace.map((item) => ({
    id: item.script,
    label: item.script,
    script_name: item.script,
    expected_outputs: strategy.required_runtime_outputs,
    readiness: !item.available
      ? "registered_only"
      : strategy.missing_runtime_outputs.length
        ? "missing_output"
        : strategy.stale_runtime_outputs.length
          ? "stale"
          : "unknown",
    observation_only: strategy.observation_only,
    formal_use_allowed: strategy.formal_use_allowed,
    latest_modified_at: null,
    latest_content_date: null,
    missing_outputs: strategy.missing_runtime_outputs,
    stale_outputs: strategy.stale_runtime_outputs,
    notes: [],
  }));
}

function isArtifactBackedModelReadiness(readiness: MacroToolkitModelReadiness["readiness"]) {
  return readiness === "artifact_backed";
}

function modelReadinessStatusLabel(readiness: MacroToolkitModelReadiness["readiness"]) {
  const labels: Record<MacroToolkitModelReadiness["readiness"], string> = {
    artifact_backed: "artifact-backed",
    missing_output: "missing output",
    stale: "stale",
    registered_only: "registered only",
    degraded: "degraded",
    unknown: "unknown",
  };
  return labels[readiness];
}

function formatModelReadinessDetail(item: MacroToolkitModelReadiness) {
  const gaps = [
    item.missing_outputs.length ? `missing ${item.missing_outputs.join(" / ")}` : "",
    item.stale_outputs.length ? `stale ${item.stale_outputs.join(" / ")}` : "",
    item.latest_content_date ? `content ${item.latest_content_date}` : "",
  ].filter(Boolean);
  return `${item.label} (${item.script_name}) ${modelReadinessStatusLabel(item.readiness)}${
    item.observation_only ? " · observation-only" : ""
  }${gaps.length ? ` · ${gaps.join(" · ")}` : ""}`;
}

function hasonContentDateText(item: MacroToolkitHasonStrategy["runtime_outputs"][number]) {
  if (item.content_date_min && item.content_date_max && item.content_date_min !== item.content_date_max) {
    return ` content ${item.content_date_min}..${item.content_date_max}`;
  }
  return item.content_date ? ` content ${item.content_date}` : "";
}

function hasonInvalidDateText(item: MacroToolkitHasonStrategy["runtime_outputs"][number]) {
  return item.content_date_invalid_count > 0 ? ` ${item.content_date_invalid_count} invalid date` : "";
}

function hasonFreshnessBasisLabel(basis: string) {
  const labels: Record<string, string> = {
    csv_content: "CSV content date",
    file_modified_date: "file modified date",
    missing: "file missing",
  };
  return labels[basis] ?? basis;
}

function hasonModuleStatusLabel(status: string) {
  const labels: Record<string, string> = {
    integrated: "script-chain complete",
    partial: "script-chain partial",
    missing: "script-chain missing",
  };
  return labels[status] ?? status;
}

function hasonModuleStatusColor(status: string) {
  if (status === "integrated") return "default";
  return statusColor(status);
}

function formatHasonTraceScript(item: MacroToolkitHasonStrategy["source_trace"][number]) {
  const modules = Array.isArray(item.modules) ? item.modules : [];
  const moduleText = modules.length ? `[${modules.join("+")}]` : "";
  return `${item.script}${moduleText}${item.available ? "" : ":missing"}`;
}
