import { useEffect, useMemo, useState } from "react";
import {
  InfoCircleOutlined,
  PlayCircleOutlined,
  SafetyCertificateOutlined,
  ToolOutlined,
  DatabaseOutlined,
} from "@ant-design/icons";
import { Alert, Button, Tag } from "antd";
import type {
  MacroToolkitHasonStrategy,
  MacroToolkitModelReadiness,
  MacroToolkitReadinessSummary,
  MacroToolkitScriptChainRun,
} from "../../../api/macroToolkitClient";
import { MetricTile } from "../lib/MacroToolkitStatusPrimitives";
import { hasonFrameworkDisplayName } from "../lib/macroToolkitDisplayFormat";
import {
  formatPercent,
  statusColor,
  statusLabel,
} from "../lib/macroToolkitPanelShared";
import {
  isArtifactBackedModelReadiness,
  modelReadinessStatusLabel,
  modelSignalMatrixLabel,
  publishModelChainEvidenceBridge,
} from "./macroToolkitModelEvidenceShared";

export function HasonMacroStrategyPanel({
  strategy,
}: {
  strategy: MacroToolkitHasonStrategy;
}) {
  const [auditExpanded, setAuditExpanded] = useState(false);
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
  const tracedScripts = strategy.source_trace;
  const tracedScriptPreview = tracedScripts.slice(0, 5);
  return (
    <section
      className={`macro-toolkit-section macro-toolkit-hason-strategy${
        auditExpanded ? "" : " macro-toolkit-hason-strategy--audit-collapsed"
      }`}
      data-testid="macro-toolkit-hason-strategy"
    >
      <div className="macro-toolkit-hason-strategy__head">
        <div>
          <span>Hason 宏观框架</span>
          <strong title={strategy.framework_name}>
            {hasonFrameworkDisplayName(strategy.framework_name)}
          </strong>
          {/* 三段元信息分行呈现，单行 `·` 不超配额（DESIGN §7）。 */}
          <small>模块就绪 {readinessText} · 缺失脚本 {readiness.missing_script_count}</small>
          <small>
            运行输出{" "}
            {runtimeOutputsCurrent
              ? "已对齐"
              : `${statusLabel(strategy.runtime_output_status)}${runtimeOutputGaps.length ? ` ${runtimeOutputGaps.length}` : ""}`}
          </small>
        </div>
        <div className="macro-toolkit-tag-row">
          <Tag color={statusColor(strategy.status)}>{statusLabel(strategy.status)}</Tag>
          <Tag color={strategy.observation_only ? "gold" : "green"}>
            {strategy.observation_only ? "仅作观察" : "可执行"}
          </Tag>
          <button
            type="button"
            className="macro-toolkit-hason-strategy__audit-toggle"
            aria-expanded={auditExpanded}
            onClick={() => setAuditExpanded((current) => !current)}
          >
            {auditExpanded ? "收起框架审计" : "框架审计"}
          </button>
        </div>
      </div>

      <div className="macro-toolkit-hason-strategy__audit-body">
        <small>框架口径 {strategy.basis} · {strategy.formal_metric_id ?? "无正式指标"}</small>
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
              {module.evidence.length ? <small>覆盖能力：{module.evidence.join(" / ")}</small> : null}
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
      </div>
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

function modelSignalMatrixOrder(item: MacroToolkitModelReadiness) {
  const index = MODEL_SIGNAL_MATRIX_ORDER.indexOf(item.id as (typeof MODEL_SIGNAL_MATRIX_ORDER)[number]);
  return index === -1 ? MODEL_SIGNAL_MATRIX_ORDER.length : index;
}

function modelSignalDateText(item: MacroToolkitModelReadiness) {
  return item.latest_content_date ?? item.artifact_receipt?.data_asof ?? item.latest_modified_at ?? "日期待定";
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

export function ModelSignalDetail({
  item,
  chainRunResult,
  isSharedScript,
  showActions,
}: {
  item: MacroToolkitModelReadiness;
  chainRunResult: MacroToolkitScriptChainRun | null;
  isSharedScript: boolean;
  showActions: boolean;
}) {
  const receipt = item.artifact_receipt;
  const runReceipt = modelSignalRunReceipt(item, chainRunResult);
  return (
    <aside className="macro-toolkit-model-signal-detail" data-testid="macro-toolkit-model-signal-detail">
      <div className="macro-toolkit-model-signal-detail__head">
        <div>
          <span>模型证据</span>
          <strong>{modelSignalMatrixLabel(item)}</strong>
          <small title={item.script_name}>
            {modelReadinessStatusLabel(item.readiness)} · {modelSignalDateText(item)}
          </small>
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
                : "先预检，再从模型链工具条运行模型链，用最新回执对照预期产物。"}
            </small>
          </div>
        </div>
      ) : null}
      {runReceipt ? (
        <div className="macro-toolkit-model-signal-detail__receipt">
          <span>最近脚本运行回执</span>
          <strong title={`${runReceipt.script_name}${isSharedScript ? " · 共享脚本回执" : ""}`}>
            {statusLabel(runReceipt.status)}
          </strong>
          <small>预期 {modelSignalArtifactList(runReceipt.expected_outputs)}</small>
          <small>产出 {modelSignalArtifactList(runReceipt.produced_outputs)}</small>
          <small>
            缺失 {modelSignalArtifactList(runReceipt.missing_outputs_after)} ·{" "}
            {runReceipt.degraded_reason ?? "无降级原因"}
          </small>
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
  isRunningChain,
  onRunChain,
}: {
  modelReadiness: MacroToolkitModelReadiness[];
  readinessSummary?: MacroToolkitReadinessSummary;
  chainRunResult: MacroToolkitScriptChainRun | null;
  chainRunError: string | null;
  chainRunModelId: string | null;
  isRunningChain: boolean;
  onRunChain: (dryRun: boolean, modelId?: string) => void;
}) {
  const rows = useMemo(
    () =>
      [...modelReadiness].sort((left, right) => {
        const byOrder = modelSignalMatrixOrder(left) - modelSignalMatrixOrder(right);
        return byOrder || left.label.localeCompare(right.label);
      }),
    [modelReadiness],
  );
  useEffect(() => {
    if (!rows.length) return undefined;
    publishModelChainEvidenceBridge({ entries: rows, chainRunResult, showAcceptance: true });
    return () => publishModelChainEvidenceBridge(null);
  }, [rows, chainRunResult]);
  if (!rows.length) {
    return null;
  }
  const boundaryText = readinessSummary
    ? `${readinessSummary.observation_only ? "仅作观察" : "可执行"} · ${
        readinessSummary.formal_use_allowed ? "允许正式使用" : "不入正式口径"
      }`
    : "边界待后端汇总 · 不入正式口径";

  const blockedEntries = rows.filter((item) => !isArtifactBackedModelReadiness(item.readiness));
  const readinessDetail = blockedEntries.length
    ? blockedEntries.map(formatModelReadinessDetail).join(" / ")
    : rows.map((item) => `${item.label} ${modelReadinessStatusLabel(item.readiness)}`).join(" / ");
  return (
    <section
      className="macro-toolkit-section macro-toolkit-model-signal-matrix"
      data-testid="macro-toolkit-model-signal-matrix"
    >
      <div className="macro-toolkit-model-signal-matrix__head">
        <div>
          <span>模型信号</span>
          <strong>模型就绪度摘要</strong>
          <small>{modelSignalSummaryText(rows, readinessSummary)}</small>
          <small>{boundaryText}</small>
        </div>
        <div className="macro-toolkit-model-signal-matrix__toolbar">
          <a href="#macro-toolkit-script-artifact-detail">查看脚本产物证据</a>
          <Button
            data-testid="macro-toolkit-model-signal-chain-preflight"
            icon={<InfoCircleOutlined />}
            loading={isRunningChain}
            disabled={isRunningChain}
            size="small"
            onClick={() => onRunChain(true)}
          >
            预检模型链
          </Button>
          <Button
            data-testid="macro-toolkit-model-signal-chain-run"
            icon={<PlayCircleOutlined />}
            loading={isRunningChain}
            disabled={isRunningChain}
            size="small"
            onClick={() => onRunChain(false)}
          >
            运行模型链
          </Button>
        </div>
      </div>
      <div
        id="macro-toolkit-model-readiness-detail"
        className="macro-toolkit-model-signal-matrix__readiness"
        data-testid="macro-toolkit-model-readiness-detail"
      >
        <span>模型就绪度 · 仅观察</span>
        {/* 段落式「/」串摘要改为模型名 + 状态徽标胶囊列表（06 区模型卡同语言）。 */}
        {blockedEntries.length ? (
          <ul className="macro-toolkit-model-readiness-pills" aria-label="待复核模型清单">
            {blockedEntries.map((item) => (
              <li key={item.id} title={formatModelReadinessDetail(item)}>
                {modelSignalMatrixLabel(item)}{" "}
                <em data-readiness={item.readiness}>{modelReadinessStatusLabel(item.readiness)}</em>
              </li>
            ))}
          </ul>
        ) : (
          <strong>全部模型仅作观察，无待复核缺口</strong>
        )}
        <small title={readinessDetail}>
          {blockedEntries.length ? `${blockedEntries.length} 个模型待复核` : "全部模型仅观察"}
        </small>
      </div>
      {chainRunError ? (
        <Alert type="error" showIcon message="模型链运行失败" description={chainRunError} />
      ) : null}
    </section>
  );
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
