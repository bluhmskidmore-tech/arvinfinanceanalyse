import { LineChartOutlined } from "@ant-design/icons";
import { Alert, Button, Tag } from "antd";

import type { MacroToolkitCapabilityResult } from "../../../api/macroToolkitClient";
import { PageSectionLead } from "../../../components/page/PagePrimitives";
import { formatCrisisTopContributorSummary } from "../lib/crisisScoreDisplay";
import { isCrisisComponent, normalizeInputEvidence } from "../lib/macroToolkitCrisisSupport";
import { statusColor, statusLabel } from "../lib/macroToolkitPanelShared";
import { ScoreTrack } from "./MacroToolkitPrimitives";

export function CapabilityResultCard({ result }: { result: MacroToolkitCapabilityResult }) {
  const metric = result.primary_metric;
  const evidence = result.evidence.length ? result.evidence : result.warnings;
  const inputEvidence = normalizeInputEvidence(result);
  const rawResult = result.result;
  const crisisComponents =
    result.key === "crisis_score_cn" && Array.isArray(rawResult.components)
      ? rawResult.components.filter(isCrisisComponent)
      : [];
  const componentSummary =
    result.key === "crisis_score_cn" ? formatCrisisTopContributorSummary(crisisComponents) : null;
  return (
    <div
      className={`macro-toolkit-capability-result macro-toolkit-capability-result--${result.tone}`}
    >
      <div className="macro-toolkit-capability-result-head">
        <span>
          {result.legacy_module} · {result.label}
        </span>
        <Tag color={statusColor(result.status)}>{statusLabel(result.status)}</Tag>
      </div>
      <strong>{metric ? formatMetricDisplay(metric) : result.score ?? statusLabel(result.status)}</strong>
      <ScoreTrack score={result.score} />
      <p>{result.headline}</p>
      {componentSummary ? (
        <small className="macro-toolkit-crisis-component-summary" data-testid="macro-toolkit-crisis-capability-component-summary">
          {componentSummary}
        </small>
      ) : null}
      <small>{evidence.slice(0, 3).join(" / ") || "暂无证据"}</small>
      {inputEvidence ? (
        <div className="macro-toolkit-input-evidence">
          {inputEvidence.missingInputs.length ? (
            <span>缺失输入：{inputEvidence.missingInputs.join(" / ")}</span>
          ) : null}
          {inputEvidence.sources.length ? <span>数据源：{inputEvidence.sources.join(" / ")}</span> : null}
          {inputEvidence.latestDates.length ? <span>最新日期：{inputEvidence.latestDates.join(" / ")}</span> : null}
          {inputEvidence.inputs.length ? (
            <small>
              {inputEvidence.inputs
                .slice(0, 3)
                .map((item) => `${item.label || item.field}: ${item.series_id ?? "缺失"} ${item.latest_date ?? ""}`.trim())
                .join(" / ")}
            </small>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function formatMetricDisplay(metric: NonNullable<MacroToolkitCapabilityResult["primary_metric"]>) {
  return `${metric.label} ${metric.value}${metric.unit}`;
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
  return (
    <section className="macro-toolkit-section">
      <PageSectionLead
        eyebrow="结果"
        title="功能结果"
        description="M7-M16 已按现有宏观纯函数和正式事实表输出结果，缺口只保留为数据降级提示。"
      />
      {capabilityResults.length ? (
        <div className="macro-toolkit-capability-result-grid">
          {capabilityResults.map((result) => (
            <CapabilityResultCard result={result} key={result.key} />
          ))}
        </div>
      ) : isCoreAnalysis ? (
        <Alert
          type="info"
          showIcon
          message="M7-M16 功能结果正在生成"
          description="核心信号已先返回；市场踩踏风险和功能结果需打开完整分析后显示。"
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
        <div className="macro-toolkit-empty-output">暂无 M7-M16 功能结果。</div>
      )}
    </section>
  );
}
