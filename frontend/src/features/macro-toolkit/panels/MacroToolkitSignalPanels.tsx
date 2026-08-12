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
    ? "已对齐"
    : `${statusLabel(strategy.runtime_output_status)} · ${runtimeOutputGaps.length}`;
  const runtimeOutputDetail = runtimeOutputGaps.length
    ? runtimeOutputGaps.join(" / ")
    : strategy.required_runtime_outputs.join(" / ");
  const runtimeGapText = runtimeOutputGaps.length
    ? runtimeOutputGaps.join(" / ")
    : runtimeOutputsCurrent
      ? "无缺口"
      : "新鲜度未确认";
  const readinessEntries = modelReadiness.length ? modelReadiness : deriveModelReadinessFromHasonStrategy(strategy);
  const blockedReadinessEntries = readinessEntries.filter((item) => !isArtifactBackedModelReadiness(item.readiness));
  const readinessHeadline = blockedReadinessEntries.length
    ? blockedReadinessEntries.map((item) => `${item.label} ${modelReadinessStatusLabel(item.readiness)}`).join(" / ")
    : "全部模型仅作观察，无待复核缺口";
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
            <span>模型就绪度 · 仅观察</span>
            <strong>{readinessHeadline}</strong>
            <small title={readinessDetail}>
              {blockedReadinessEntries.length
                ? `${blockedReadinessEntries.length} 个模型待复核 · 悬停查看产物明细`
                : "全部模型仅观察 · 悬停查看清单"}
            </small>
          </div>
        ) : null}
      </section>
    );
  }
  return (
    <section className="macro-toolkit-section macro-toolkit-hason-strategy" data-testid="macro-toolkit-hason-strategy">
      <div className="macro-toolkit-hason-strategy__head">
        <div>
          <span>Hason 宏观框架</span>
          <strong>{strategy.framework_name}</strong>
          <small>{strategy.boundary}</small>
        </div>
        <div className="macro-toolkit-tag-row">
          <Tag color={statusColor(strategy.status)}>{statusLabel(strategy.status)}</Tag>
          <Tag color="blue">{strategy.basis}</Tag>
          <Tag color={strategy.observation_only ? "gold" : "green"}>
            {strategy.observation_only ? "仅作观察" : "可执行"}
          </Tag>
          <Tag color={strategy.formal_use_allowed ? "green" : "default"}>
            {strategy.formal_metric_id ?? "无正式指标"}
          </Tag>
        </div>
      </div>

      <div className="macro-toolkit-hason-strategy__metrics">
        <MetricTile
          icon={<SafetyCertificateOutlined />}
          label="模块就绪"
          value={readinessText}
          detail={`模块覆盖 ${formatPercent(readiness.ratio)}`}
          tone="neutral"
        />
        <MetricTile
          icon={<ToolOutlined />}
          label="模块缺口"
          value={`缺失脚本 ${readiness.missing_script_count}`}
          detail={`部分就绪 ${readiness.partial_modules} · 缺失模块 ${readiness.missing_modules}`}
          tone="neutral"
        />
        <MetricTile
          icon={<DatabaseOutlined />}
          label="运行输出"
          value={runtimeOutputValue}
          detail={runtimeOutputDetail}
          tone="neutral"
        />
        <MetricTile
          icon={<ToolOutlined />}
          label="脚本追踪"
          value={tracedScripts.length}
          detail={tracedScriptPreview.map(formatHasonTraceScript).join(" / ") || "暂无可用脚本"}
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
        <span>运行输出 · {statusLabel(strategy.runtime_output_status)}</span>
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
          <span>模型就绪度 · 仅观察</span>
          <strong>{readinessHeadline}</strong>
          <small title={readinessDetail}>
            {blockedReadinessEntries.length
              ? `${blockedReadinessEntries.length} 个模型待复核 · 悬停查看产物明细`
              : "全部模型仅观察 · 悬停查看清单"}
          </small>
        </div>
      ) : null}
    </section>
  );
}

function formatHasonRuntimeOutput(item: MacroToolkitHasonStrategy["runtime_outputs"][number]) {
  return (
    `${item.name}: ${statusLabel(item.freshness_status)} ${hasonFreshnessBasisLabel(item.freshness_basis)}` +
    `${hasonContentDateText(item)}` +
    `${hasonInvalidDateText(item)}` +
    `${item.modified_date ? ` 文件 ${item.modified_date}` : ""}`
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
  merrill_clock: "美林时钟",
  crisis_score: "Crisis Score",
  bond_futures_basis: "国债期货基差 / IRR / 安全边际",
  bond_futures_four_factor: "国债期货四因子趋势",
  funding_conditions: "资金面 / 流动性",
  crowding: "拥挤度",
  dcc_garch: "DCC-GARCH",
  cta_trend: "CTA 趋势",
  final_signal: "最终信号聚合",
  risk_monitor: "风险监控",
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
  return item.latest_content_date ?? item.artifact_receipt?.data_asof ?? item.latest_modified_at ?? "日期待定";
}

function modelSignalEvidenceText(item: MacroToolkitModelReadiness) {
  const artifacts = item.artifact_receipt?.artifact_paths ?? [];
  if (artifacts.length) return `产物 ${artifacts.join(" / ")}`;
  if (item.missing_outputs.length) return `缺失 ${item.missing_outputs.join(" / ")}`;
  if (item.stale_outputs.length) return `陈旧 ${item.stale_outputs.join(" / ")}`;
  if (item.expected_outputs.length) return `预期 ${item.expected_outputs.join(" / ")}`;
  return item.evidence_level ?? "证据待定";
}

function modelSignalThresholdText(item: MacroToolkitModelReadiness) {
  const gaps = [
    item.degraded_reason ?? "",
    item.degraded_outputs?.length ? `降级 ${item.degraded_outputs.join(" / ")}` : "",
    item.missing_outputs.length ? `缺失产物 ${item.missing_outputs.length}` : "",
    item.stale_outputs.length ? `陈旧产物 ${item.stale_outputs.length}` : "",
  ].filter(Boolean);
  return gaps.join(" · ") || "当前产物满足阈值";
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
  return `产物支撑 ${backed}/${total} · 降级 ${degraded}`;
}

function modelSignalArtifactList(items: string[] | undefined, fallback = "无") {
  return items?.length ? items.join(" / ") : fallback;
}

function modelSignalReceiptRuntime(item: MacroToolkitModelReadiness) {
  return item.artifact_receipt?.runtime_endpoint ?? "运行端点待定";
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
          <span>模型证据</span>
          <strong>{MODEL_SIGNAL_MATRIX_LABELS[item.id] ?? item.label}</strong>
          <small>
            {item.script_name} · {modelReadinessStatusLabel(item.readiness)} · {modelSignalDateText(item)}
          </small>
        </div>
        <div className="macro-toolkit-model-signal-matrix__boundary">
          <Tag color={item.observation_only ? "gold" : "green"}>
            {item.observation_only ? "仅作观察" : "可执行"}
          </Tag>
          <Tag color={item.formal_use_allowed ? "green" : "default"}>
            {item.formal_use_allowed ? "正式口径" : "非正式口径"}
          </Tag>
        </div>
      </div>
      <div className="macro-toolkit-model-signal-detail__grid">
        <div>
          <span>预期产物</span>
          <strong>{modelSignalArtifactList(item.expected_outputs)}</strong>
        </div>
        <div>
          <span>现有产物</span>
          <strong>{modelSignalArtifactList(receipt?.artifact_paths)}</strong>
        </div>
        <div>
          <span>缺失产物</span>
          <strong>{modelSignalArtifactList(receipt?.missing_artifacts ?? item.missing_outputs)}</strong>
        </div>
        <div>
          <span>陈旧产物</span>
          <strong>{modelSignalArtifactList(item.stale_outputs)}</strong>
        </div>
        <div>
          <span>运行端点</span>
          <strong>{modelSignalReceiptRuntime(item)}</strong>
        </div>
        <div>
          <span>阈值说明</span>
          <strong>{modelSignalThresholdText(item)}</strong>
        </div>
      </div>
      {item.notes.length ? <p>{item.notes.join(" / ")}</p> : null}
      {showActions ? (
        <div className="macro-toolkit-model-signal-detail__acceptance">
          <div>
            <span>产物验收</span>
            <strong>{item.readiness === "artifact_backed" ? "当前产物已通过" : "需要运行模型链"}</strong>
            <small>
              {item.readiness === "artifact_backed"
                ? "后端就绪度已确认该模型有产物支撑。"
                : "先预检，再运行模型链，用最新回执对照预期产物。"}
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
              预检模型链
            </Button>
            <Button
              data-testid="macro-toolkit-model-signal-chain-run"
              icon={<PlayCircleOutlined />}
              loading={isRunningChain}
              disabled={isRunningChain}
              size="small"
              onClick={() => onRunChain(false, item.id)}
            >
              运行模型链
            </Button>
          </div>
        </div>
      ) : null}
      {runReceipt ? (
        <div className="macro-toolkit-model-signal-detail__receipt">
          <span>最近脚本运行回执</span>
          <strong>
            {runReceipt.script_name} · {runReceipt.status}
          </strong>
          <small>
            预期 {modelSignalArtifactList(runReceipt.expected_outputs)} · 产出{" "}
            {modelSignalArtifactList(runReceipt.produced_outputs)} · 缺失{" "}
            {modelSignalArtifactList(runReceipt.missing_outputs_after)} ·{" "}
            {isSharedScript ? "共享脚本回执 · " : ""}
            {runReceipt.degraded_reason ?? "无降级原因"}
          </small>
        </div>
      ) : null}
      {isLatestChainModel && chainRunError ? (
        <div className="macro-toolkit-model-signal-detail__receipt macro-toolkit-model-signal-detail__receipt--error">
          <span>最近运行问题</span>
          <strong>{chainRunError}</strong>
          <small>检查执行权限、脚本依赖和模型链运行回执。</small>
        </div>
      ) : null}
      <div className="macro-toolkit-model-signal-detail__links">
        <a href="#macro-toolkit-script-artifact-detail">查看脚本产物</a>
        <a href="#macro-toolkit-model-readiness-detail">查看就绪度摘要</a>
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
    ? `${readinessSummary.observation_only ? "仅作观察" : "可执行"} · ${
        readinessSummary.formal_use_allowed ? "允许正式使用" : "不入正式口径"
      }`
    : "边界待后端汇总 · 不入正式口径";

  return (
    <section className="macro-toolkit-section macro-toolkit-model-signal-matrix" data-testid="macro-toolkit-model-signal-matrix">
      <div className="macro-toolkit-model-signal-matrix__head">
        <div>
          <span>模型信号</span>
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
                {item.observation_only ? "仅作观察" : "可执行"}
              </Tag>
              <Tag color={item.formal_use_allowed ? "green" : "default"}>
                {item.formal_use_allowed ? "正式口径" : "非正式口径"}
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
    artifact_backed: "产物支撑",
    missing_output: "缺产物",
    stale: "陈旧",
    registered_only: "仅注册",
    degraded: "降级",
    unknown: "待确认",
  };
  return labels[readiness];
}

function formatModelReadinessDetail(item: MacroToolkitModelReadiness) {
  const gaps = [
    item.missing_outputs.length ? `缺失 ${item.missing_outputs.join(" / ")}` : "",
    item.stale_outputs.length ? `陈旧 ${item.stale_outputs.join(" / ")}` : "",
    item.latest_content_date ? `内容日期 ${item.latest_content_date}` : "",
  ].filter(Boolean);
  return `${item.label} (${item.script_name}) ${modelReadinessStatusLabel(item.readiness)}${
    item.observation_only ? " · 仅作观察" : ""
  }${gaps.length ? ` · ${gaps.join(" · ")}` : ""}`;
}

function hasonContentDateText(item: MacroToolkitHasonStrategy["runtime_outputs"][number]) {
  if (item.content_date_min && item.content_date_max && item.content_date_min !== item.content_date_max) {
    return ` 内容 ${item.content_date_min}..${item.content_date_max}`;
  }
  return item.content_date ? ` 内容 ${item.content_date}` : "";
}

function hasonInvalidDateText(item: MacroToolkitHasonStrategy["runtime_outputs"][number]) {
  return item.content_date_invalid_count > 0 ? ` ${item.content_date_invalid_count} 个无效日期` : "";
}

function hasonFreshnessBasisLabel(basis: string) {
  const labels: Record<string, string> = {
    csv_content: "CSV 内容日期",
    file_modified_date: "文件修改日期",
    missing: "文件缺失",
  };
  return labels[basis] ?? basis;
}

function hasonModuleStatusLabel(status: string) {
  const labels: Record<string, string> = {
    integrated: "脚本链完整",
    partial: "脚本链部分",
    missing: "脚本链缺失",
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
  return `${item.script}${moduleText}${item.available ? "" : ":缺失"}`;
}
