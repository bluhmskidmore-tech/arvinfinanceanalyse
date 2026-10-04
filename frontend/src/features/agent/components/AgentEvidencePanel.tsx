import type { AgentSemanticContext } from "../../../api/contracts";
import { EM_DASH } from "../../../utils/format";

type AgentEvidencePanelProps = {
  tablesUsed: string[];
  filtersApplied: Record<string, unknown>;
  sqlExecuted?: string[];
  evidenceStrength?: string;
  evidenceRows: number;
  qualityFlag: string;
  semanticContext?: AgentSemanticContext | null;
  resultMeta?: Record<string, unknown>;
};

const qualityLabels: Record<string, string> = {
  ok: "正常",
  warning: "需留意",
  error: "异常",
  stale: "可能陈旧",
};

const evidenceStrengthLabels: Record<string, string> = {
  governed_moss: "MOSS 受治理证据",
  provider_runtime: "外部模型运行证据",
  local_fallback: "本地降级回答",
  mixed: "外部模型 + MOSS 上下文",
};

const semanticStatusLabels: Record<AgentSemanticContext["status"], string> = {
  resolved: "已识别",
  clarification_required: "需要澄清",
  unsupported: "暂不支持",
  unavailable: "语义信息不可用",
};

const resultCheckLabels: Record<AgentSemanticContext["result_check"], string> = {
  matched: "结果已核对",
  blocked: "结果未通过核对",
  not_applicable: "无需核对数值",
};

const referenceStatusLabels: Record<AgentSemanticContext["references"][number]["status"], string> = {
  approved: "已批准",
  gap: "定义存在缺口",
  candidate: "候选定义",
  deprecated: "已废弃",
};

const metricUnitLabels: Record<string, string> = {
  yuan: "元",
};

function formatEvidenceValue(value: unknown): string {
  if (value === null) return "空";
  if (Array.isArray(value)) return value.map(formatEvidenceValue).join(", ");
  if (typeof value === "object") return JSON.stringify(value);
  if (typeof value === "boolean") return value ? "是" : "否";
  return String(value);
}

function formatFilterSummary(filtersApplied: Record<string, unknown>) {
  const entries = Object.entries(filtersApplied);
  if (entries.length === 0) {
    return "未应用额外筛选";
  }
  return entries.map(([key, value]) => `${key}: ${formatEvidenceValue(value)}`).join("；");
}

function formatDistinctValues(values: Array<string | null | undefined>): string {
  const distinctValues = Array.from(
    new Set(values.map((value) => value?.trim()).filter((value): value is string => Boolean(value))),
  );
  return distinctValues.length > 0 ? distinctValues.join("、") : EM_DASH;
}

function formatMetricUnits(values: Array<string | null | undefined>): string {
  return formatDistinctValues(
    values.map((value) => {
      const normalizedValue = value?.trim();
      return normalizedValue ? (metricUnitLabels[normalizedValue] ?? normalizedValue) : normalizedValue;
    }),
  );
}

function getActualReportDate(resultMeta: Record<string, unknown> | undefined): string {
  for (const key of ["fallback_date", "resolved_report_date", "as_of_date"] as const) {
    const reportDate = resultMeta?.[key];
    if (typeof reportDate === "string" && reportDate.trim()) {
      return reportDate.trim();
    }
  }
  return EM_DASH;
}

function getFormalUseLabel(
  resultMeta: Record<string, unknown> | undefined,
  semanticContext: AgentSemanticContext,
): string {
  if (semanticContext.status === "unavailable") {
    return "不可正式使用（语义信息不可用）";
  }
  if (semanticContext.result_check === "blocked") {
    return "不可正式使用（结果未通过核对）";
  }
  if (
    resultMeta?.formal_use_allowed === true &&
    semanticContext.status === "resolved" &&
    semanticContext.result_check === "matched"
  ) {
    return "允许正式使用";
  }
  if (resultMeta?.formal_use_allowed === false) {
    return "不可正式使用";
  }
  if (semanticContext.result_check === "not_applicable") {
    return "正式使用不适用";
  }
  return "使用资格未声明";
}

export function AgentEvidencePanel({
  tablesUsed,
  filtersApplied,
  sqlExecuted = [],
  evidenceStrength,
  evidenceRows,
  qualityFlag,
  semanticContext,
  resultMeta,
}: AgentEvidencePanelProps) {
  const rawFilters = JSON.stringify(filtersApplied, null, 2);
  const semanticReferences = semanticContext?.references ?? [];

  return (
    <div className="agent-side-panel agent-side-panel--evidence">
      {semanticContext ? (
        <>
          <div className="agent-side-panel__title">指标口径</div>
          <div className="agent-side-panel__body agent-side-panel__body--rows">
            <div className="agent-side-panel__row">
              <span>指标</span>
              <strong>{formatDistinctValues(semanticReferences.map((reference) => reference.name))}</strong>
            </div>
            <div className="agent-side-panel__row">
              <span>单位</span>
              <strong>{formatMetricUnits(semanticReferences.map((reference) => reference.unit))}</strong>
            </div>
            <div className="agent-side-panel__row">
              <span>实际数据日</span>
              <strong>{getActualReportDate(resultMeta)}</strong>
            </div>
            <div className="agent-side-panel__row">
              <span>使用状态</span>
              <strong>{getFormalUseLabel(resultMeta, semanticContext)}</strong>
            </div>
          </div>
          <details className="agent-side-panel__details" data-testid="agent-evidence-semantic-context">
            <summary>查看指标口径详情 · {semanticReferences.length} 项</summary>
            <div className="agent-side-panel__body agent-side-panel__body--rows">
              <div className="agent-side-panel__row">
                <span>语义状态</span>
                <strong>{semanticStatusLabels[semanticContext.status]}</strong>
              </div>
              <div className="agent-side-panel__row">
                <span>结果核对</span>
                <strong>{resultCheckLabels[semanticContext.result_check]}</strong>
              </div>
              {semanticReferences.map((reference, index) => (
                <div key={reference.entity_id} className="agent-side-panel__body agent-side-panel__body--rows">
                  <div className="agent-side-panel__row">
                    <span>{semanticReferences.length > 1 ? `指标 ${index + 1}` : "指标名称"}</span>
                    <strong>{reference.name}</strong>
                  </div>
                  <div className="agent-side-panel__row">
                    <span>指标 ID</span>
                    <strong>{reference.entity_id}</strong>
                  </div>
                  <div className="agent-side-panel__row">
                    <span>定义状态</span>
                    <strong>{referenceStatusLabels[reference.status]}</strong>
                  </div>
                  <div className="agent-side-panel__row">
                    <span>声明单位</span>
                    <strong>{reference.unit?.trim() || EM_DASH}</strong>
                  </div>
                  <div className="agent-side-panel__row">
                    <span>定义</span>
                    <strong>{reference.business_definition}</strong>
                  </div>
                  <div className="agent-side-panel__row">
                    <span>口径</span>
                    <strong>{reference.basis?.trim() || EM_DASH}</strong>
                  </div>
                  <div className="agent-side-panel__row">
                    <span>时间语义</span>
                    <strong>{reference.time_semantics?.trim() || EM_DASH}</strong>
                  </div>
                  <div className="agent-side-panel__row">
                    <span>权威出处</span>
                    <strong>{formatDistinctValues(reference.authority)}</strong>
                  </div>
                </div>
              ))}
              <div className="agent-side-panel__row">
                <span>本体版本</span>
                <strong>{semanticContext.ontology_revision?.trim() || EM_DASH}</strong>
              </div>
              <div className="agent-side-panel__row">
                <span>绑定版本</span>
                <strong>{semanticContext.binding_revision?.trim() || EM_DASH}</strong>
              </div>
              <div className="agent-side-panel__row">
                <span>上游结果</span>
                <strong>{semanticContext.upstream_result_kind?.trim() || EM_DASH}</strong>
              </div>
              <div className="agent-side-panel__row">
                <span>上游 Trace</span>
                <strong>{semanticContext.upstream_trace_id?.trim() || EM_DASH}</strong>
              </div>
              {semanticContext.reason_code ? (
                <div className="agent-side-panel__row">
                  <span>状态原因</span>
                  <strong>{semanticContext.reason_code}</strong>
                </div>
              ) : null}
            </div>
          </details>
        </>
      ) : null}
      <div className="agent-side-panel__title">回答依据</div>
      <div className="agent-side-panel__body agent-side-panel__body--rows">
        <div className="agent-side-panel__row">
          <span>来源</span>
          <strong>{tablesUsed.length > 0 ? tablesUsed.join(", ") : "未返回来源表"}</strong>
        </div>
        <div className="agent-side-panel__row">
          <span>过滤</span>
          <strong>{formatFilterSummary(filtersApplied)}</strong>
        </div>
        <div className="agent-side-panel__row">
          <span>证据行数</span>
          <strong>{evidenceRows} 行</strong>
        </div>
        <div className="agent-side-panel__row">
          <span>证据级别</span>
          <strong>
            {evidenceStrength
              ? (evidenceStrengthLabels[evidenceStrength] ?? evidenceStrength)
              : "未声明"}
          </strong>
        </div>
        <div className="agent-side-panel__row">
          <span>质量</span>
          <strong>{qualityLabels[qualityFlag] ?? qualityFlag}</strong>
        </div>
      </div>
      <details className="agent-side-panel__details">
        <summary>查看筛选参数</summary>
        <pre>{rawFilters}</pre>
      </details>
      {sqlExecuted.length > 0 ? (
        <details className="agent-side-panel__details" data-testid="agent-evidence-sql">
          <summary>查看只读 SQL 披露 · {sqlExecuted.length} 条</summary>
          <div className="agent-side-panel__sql-list">
            {sqlExecuted.map((sql, index) => (
              <pre key={`sql-${index}`}>{sql}</pre>
            ))}
          </div>
        </details>
      ) : null}
    </div>
  );
}
