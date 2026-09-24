import { LineChartOutlined } from "@ant-design/icons";
import { Alert, Button, Tag } from "antd";

import type { MacroToolkitCapabilityResult } from "../../../api/macroToolkitClient";
import { PageSectionLead } from "../../../components/page/PagePrimitives";
import { EM_DASH } from "../../../utils/format";
import { formatCrisisTopContributorSummary } from "../lib/crisisScoreDisplay";
import { isCrisisComponent, normalizeInputEvidence } from "../lib/macroToolkitCrisisSupport";
import {
  formatCapabilityEvidenceList,
  formatCapabilityMetricValue,
} from "../lib/macroToolkitDisplayFormat";
import { statusColor, statusLabel } from "../lib/macroToolkitPanelShared";
import { ScoreTrack } from "./MacroToolkitPrimitives";

/**
 * 01-ia 决策表 #6：这五张模型能力卡与模型链视图同源但数值口径冲突
 * （如 Crisis 0.31 vs 链上 -0.068、DCC 0.51 vs 0.2764），结果统一由模型链
 * 唯一呈现，功能结果区不再复读。
 */
const MODEL_CHAIN_CAPABILITY_KEYS = new Set([
  "merrill_clock_cn",
  "cta_trend_cn",
  "dcc_garch_cn",
  "risk_parity_cn",
  "crisis_score_cn",
]);
const MODEL_CHAIN_CAPABILITY_MODULES = new Set(["Merrill", "CTA", "DCC", "RP", "Crisis"]);

function isModelChainCapabilityResult(result: MacroToolkitCapabilityResult) {
  return (
    MODEL_CHAIN_CAPABILITY_KEYS.has(result.key) || MODEL_CHAIN_CAPABILITY_MODULES.has(result.legacy_module)
  );
}

/** #6 ②：M16 决策管家卡与 Hason 框架审计重复，整卡下线（观察页决策摘要组件不受影响）。 */
function isDecisionSummaryCapabilityResult(result: MacroToolkitCapabilityResult) {
  return result.key === "decision_summary" || result.legacy_module === "M16";
}

const INSUFFICIENT_DATA_MARK = "数据不足";

export function CapabilityResultCard({ result }: { result: MacroToolkitCapabilityResult }) {
  const metric = result.primary_metric;
  const inputEvidence = normalizeInputEvidence(result);
  const rawResult = result.result;
  const crisisComponents =
    result.key === "crisis_score_cn" && Array.isArray(rawResult.components)
      ? rawResult.components.filter(isCrisisComponent)
      : [];
  const componentSummary =
    result.key === "crisis_score_cn" ? formatCrisisTopContributorSummary(crisisComponents) : null;
  const headline = result.headline ?? "";
  const headlineHasInsufficiency = headline.includes(INSUFFICIENT_DATA_MARK);
  // #6 ③：headline 已声明「数据不足」时，结果行与证据行不再复读同一状态（M14 三连去重）。
  const resultText = metric ? formatMetricDisplay(metric) : result.score ?? EM_DASH;
  const suppressInsufficiencyRepeat =
    typeof resultText === "string" && headlineHasInsufficiency && resultText.includes(INSUFFICIENT_DATA_MARK);
  const resultLine = suppressInsufficiencyRepeat ? EM_DASH : resultText;
  // 主值英文枚举（如「联动风险 MEDIUM」）译中文；原值收 title。
  const resultLineDisplay = suppressInsufficiencyRepeat
    ? EM_DASH
    : metric
      ? formatMetricDisplayLocalized(metric)
      : resultLine;
  const evidencePool = result.evidence.length ? result.evidence : result.warnings;
  const evidence = headlineHasInsufficiency
    ? evidencePool.filter((item) => !item.includes(INSUFFICIENT_DATA_MARK))
    : evidencePool;
  // 证据行按 key=value 译中文键名 + 格式化值；原始 kv 串收进 title。
  const visibleEvidence = evidence.slice(0, 3);
  const evidenceRawText = visibleEvidence.join(" / ");
  const evidenceDisplayText = formatCapabilityEvidenceList(visibleEvidence).join(" / ");
  const resultLineTitle =
    typeof resultLine === "string" && resultLine !== EM_DASH && resultLine !== resultLineDisplay
      ? resultLine
      : undefined;
  return (
    <div
      className={`macro-toolkit-capability-result macro-toolkit-capability-result--${result.tone}`}
      title={result.legacy_module}
    >
      <div className="macro-toolkit-capability-result-head">
        <span>{result.label}</span>
        <Tag color={statusColor(result.status)}>{statusLabel(result.status)}</Tag>
      </div>
      <strong title={resultLineTitle}>{resultLineDisplay}</strong>
      <ScoreTrack score={result.score} />
      <p>{headline}</p>
      {componentSummary ? (
        <small className="macro-toolkit-crisis-component-summary" data-testid="macro-toolkit-crisis-capability-component-summary">
          {componentSummary}
        </small>
      ) : null}
      <small title={evidenceRawText || undefined}>{evidenceDisplayText || "暂无证据"}</small>
      {inputEvidence ? (
        <details className="macro-toolkit-input-evidence">
          <summary>
            {inputEvidence.missingInputs.length
              ? `输入证据（缺失 ${inputEvidence.missingInputs.length} 项）`
              : "输入证据"}
          </summary>
          {inputEvidence.missingInputs.length ? (
            <span>缺失输入：{inputEvidence.missingInputs.join(" / ")}</span>
          ) : null}
          {inputEvidence.sources.length ? <span>数据源：{inputEvidence.sources.join(" / ")}</span> : null}
          {inputEvidence.latestDates.length ? <span>最新值日期：{inputEvidence.latestDates.join(" / ")}</span> : null}
          {inputEvidence.inputs.length ? (
            <small>
              {inputEvidence.inputs
                .slice(0, 3)
                .map((item) => `${item.label || item.field}: ${item.series_id ?? "缺失"} ${item.latest_date ?? ""}`.trim())
                .join(" / ")}
            </small>
          ) : null}
        </details>
      ) : null}
    </div>
  );
}

function formatMetricDisplay(metric: NonNullable<MacroToolkitCapabilityResult["primary_metric"]>) {
  return `${metric.label} ${metric.value}${metric.unit}`;
}

function formatMetricDisplayLocalized(
  metric: NonNullable<MacroToolkitCapabilityResult["primary_metric"]>,
) {
  return `${metric.label} ${formatCapabilityMetricValue(metric.value)}${metric.unit}`;
}

export function MacroToolkitCapabilityResultsSection({
  capabilityResults,
  isCoreAnalysis,
  isLoadingFullAnalysis,
  loadFullAnalysis,
}: {
  capabilityResults: MacroToolkitCapabilityResult[];
  isCoreAnalysis: boolean;
  isLoadingFullAnalysis: boolean;
  loadFullAnalysis: () => Promise<unknown>;
}) {
  const visibleResults = capabilityResults.filter(
    (result) => !isModelChainCapabilityResult(result) && !isDecisionSummaryCapabilityResult(result),
  );
  return (
    <section className="macro-toolkit-section">
      <PageSectionLead
        eyebrow="结果"
        title="功能结果"
        description="已接入的宏观功能输出结果；缺口按数据降级提示展示。模型类结果统一见模型链视图。"
      />
      {visibleResults.length ? (
        <div className="macro-toolkit-capability-result-grid">
          {visibleResults.map((result) => (
            <CapabilityResultCard result={result} key={result.key} />
          ))}
        </div>
      ) : isCoreAnalysis ? (
        <Alert
          type="info"
          showIcon
          message="功能结果正在生成"
          description="打开完整分析后显示。"
          action={
            <Button
              aria-label="查看完整分析"
              size="small"
              icon={<LineChartOutlined />}
              loading={isLoadingFullAnalysis}
              onClick={() => void loadFullAnalysis()}
            >
              查看完整分析
            </Button>
          }
        />
      ) : (
        <div className="macro-toolkit-empty-output">暂无功能结果。</div>
      )}
    </section>
  );
}
