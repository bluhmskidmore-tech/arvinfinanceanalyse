import type { ResultMeta } from "../../api/contracts";
import { shellTokens as t } from "../../theme/tokens";

type FormalResultMetaSection = {
  key: string;
  title: string;
  meta: ResultMeta | null | undefined;
};

type FormalResultMetaPanelProps = {
  testId?: string;
  title?: string;
  emptyText?: string;
  sections: FormalResultMetaSection[];
};

const panelStyle = {
  marginTop: 24,
  padding: 16,
  borderRadius: 16,
  border: `1px solid ${t.colorBorderSoft}`,
  background: t.colorBgSurface,
} as const;

const panelTitleStyle = {
  color: t.colorTextPrimary,
  fontSize: 14,
  fontWeight: 600,
} as const;

const panelSubtitleStyle = {
  marginTop: 6,
  color: t.colorTextMuted,
  fontSize: 12,
  lineHeight: 1.6,
} as const;

const sectionGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
  gap: 12,
  marginTop: 16,
} as const;

const cardStyle = {
  borderRadius: 14,
  border: `1px solid ${t.colorBorderSoft}`,
  background: "#f7f9fc",
  padding: 14,
} as const;

const labelStyle = {
  color: t.colorTextMuted,
  fontSize: 11,
  fontWeight: 700,
  letterSpacing: "0.06em",
  textTransform: "uppercase",
} as const;

const headingStyle = {
  marginTop: 8,
  color: t.colorTextPrimary,
  fontSize: 14,
  fontWeight: 600,
} as const;

const listStyle = {
  margin: "12px 0 0",
  display: "grid",
  gridTemplateColumns: "minmax(120px, 150px) minmax(0, 1fr)",
  gap: "8px 12px",
  color: t.colorTextSecondary,
  fontSize: 13,
  lineHeight: 1.6,
} as const;

function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "—";
  }
  if (typeof value === "boolean") {
    return value ? "是" : "否";
  }
  if (Array.isArray(value)) {
    return value.length > 0 ? value.map(formatValue).join(", ") : "—";
  }
  if (typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value);
}

function formatMetaField(key: string, value: unknown): string {
  if (key === "basis") {
    if (value === "formal") return "正式口径";
    if (value === "analytical") return "分析口径";
  }
  if (key === "quality_flag") {
    const labels: Record<string, string> = {
      ok: "正常",
      warning: "预警",
      error: "错误",
      stale: "陈旧",
    };
    if (typeof value === "string" && labels[value]) return labels[value];
  }
  if (key === "vendor_status") {
    const labels: Record<string, string> = {
      ok: "正常",
      vendor_stale: "供应商陈旧",
      vendor_unavailable: "供应商不可用",
    };
    if (typeof value === "string" && labels[value]) return labels[value];
  }
  if (key === "fallback_mode") {
    if (value === "none") return "未降级";
    if (value === "latest_snapshot") return "最新快照降级";
  }
  return formatValue(value);
}

const metaLabelMap: Record<string, string> = {
  basis: "口径",
  result_kind: "结果类型",
  formal_use_allowed: "正式可用",
  scenario_flag: "情景标记",
  quality_flag: "质量标记",
  vendor_status: "供应商状态",
  fallback_mode: "降级模式",
  trace_id: "追踪编号",
  source_version: "来源版本",
  vendor_version: "供应商版本",
  rule_version: "规则版本",
  cache_version: "缓存版本",
  generated_at: "生成时间",
  tables_used: "使用表",
  filters_applied: "应用筛选",
  evidence_rows: "证据行数",
  next_drill: "下钻建议",
};

function hasEvidence(meta: ResultMeta) {
  return (
    (meta.tables_used?.length ?? 0) > 0 ||
    Object.keys(meta.filters_applied ?? {}).length > 0 ||
    typeof meta.evidence_rows === "number" ||
    (meta.next_drill?.length ?? 0) > 0
  );
}

export function FormalResultMetaPanel({
  testId,
  title = "结果元信息 / 证据",
  emptyText = "当前还没有可展示的溯源信封。",
  sections,
}: FormalResultMetaPanelProps) {
  const visibleSections = sections.filter((section) => section.meta);

  return (
    <section data-testid={testId} style={panelStyle}>
      <div style={panelTitleStyle}>{title}</div>
      <div style={panelSubtitleStyle}>
        展示当前读链路返回的口径、版本、质量与可选证据字段；页面不在前端补算正式指标。
      </div>

      {visibleSections.length === 0 ? (
        <div style={{ marginTop: 14, color: t.colorTextMuted, fontSize: 13 }}>{emptyText}</div>
      ) : (
        <div style={sectionGridStyle}>
          {visibleSections.map((section) => {
            const meta = section.meta!;
            return (
              <article
                key={section.key}
                data-testid={`${testId}-${section.key}`}
                style={cardStyle}
              >
                <div style={labelStyle}>溯源</div>
                <div style={headingStyle}>{section.title}</div>
                <dl style={listStyle}>
                  <dt>{metaLabelMap.basis}</dt>
                  <dd style={{ margin: 0 }}>{formatMetaField("basis", meta.basis)}</dd>
                  <dt>{metaLabelMap.result_kind}</dt>
                  <dd style={{ margin: 0 }}>{formatValue(meta.result_kind)}</dd>
                  <dt>{metaLabelMap.formal_use_allowed}</dt>
                  <dd style={{ margin: 0 }}>{formatValue(meta.formal_use_allowed)}</dd>
                  <dt>{metaLabelMap.scenario_flag}</dt>
                  <dd style={{ margin: 0 }}>{formatValue(meta.scenario_flag)}</dd>
                  <dt>{metaLabelMap.quality_flag}</dt>
                  <dd style={{ margin: 0 }}>{formatMetaField("quality_flag", meta.quality_flag)}</dd>
                  <dt>{metaLabelMap.vendor_status}</dt>
                  <dd style={{ margin: 0 }}>{formatMetaField("vendor_status", meta.vendor_status)}</dd>
                  <dt>{metaLabelMap.fallback_mode}</dt>
                  <dd style={{ margin: 0 }}>{formatMetaField("fallback_mode", meta.fallback_mode)}</dd>
                  <dt>{metaLabelMap.trace_id}</dt>
                  <dd style={{ margin: 0 }}>{formatValue(meta.trace_id)}</dd>
                  <dt>{metaLabelMap.source_version}</dt>
                  <dd style={{ margin: 0 }}>{formatValue(meta.source_version)}</dd>
                  <dt>{metaLabelMap.vendor_version}</dt>
                  <dd style={{ margin: 0 }}>{formatValue(meta.vendor_version)}</dd>
                  <dt>{metaLabelMap.rule_version}</dt>
                  <dd style={{ margin: 0 }}>{formatValue(meta.rule_version)}</dd>
                  <dt>{metaLabelMap.cache_version}</dt>
                  <dd style={{ margin: 0 }}>{formatValue(meta.cache_version)}</dd>
                  <dt>{metaLabelMap.generated_at}</dt>
                  <dd style={{ margin: 0 }}>{formatValue(meta.generated_at)}</dd>
                  {hasEvidence(meta) ? (
                    <>
                      <dt>{metaLabelMap.tables_used}</dt>
                      <dd style={{ margin: 0 }}>{formatValue(meta.tables_used)}</dd>
                      <dt>{metaLabelMap.filters_applied}</dt>
                      <dd style={{ margin: 0 }}>{formatValue(meta.filters_applied)}</dd>
                      <dt>{metaLabelMap.evidence_rows}</dt>
                      <dd style={{ margin: 0 }}>{formatValue(meta.evidence_rows)}</dd>
                      <dt>{metaLabelMap.next_drill}</dt>
                      <dd style={{ margin: 0 }}>{formatValue(meta.next_drill)}</dd>
                    </>
                  ) : null}
                </dl>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
