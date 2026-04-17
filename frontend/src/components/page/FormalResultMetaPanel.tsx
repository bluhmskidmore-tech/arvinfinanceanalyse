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
    return value ? "true" : "false";
  }
  if (Array.isArray(value)) {
    return value.length > 0 ? value.map(formatValue).join(", ") : "—";
  }
  if (typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value);
}

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
  title = "Result Meta / Evidence",
  emptyText = "当前还没有可展示的 provenance envelope。",
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
                <div style={labelStyle}>Provenance</div>
                <div style={headingStyle}>{section.title}</div>
                <dl style={listStyle}>
                  <dt>basis</dt>
                  <dd style={{ margin: 0 }}>{formatValue(meta.basis)}</dd>
                  <dt>result_kind</dt>
                  <dd style={{ margin: 0 }}>{formatValue(meta.result_kind)}</dd>
                  <dt>formal_use_allowed</dt>
                  <dd style={{ margin: 0 }}>{formatValue(meta.formal_use_allowed)}</dd>
                  <dt>scenario_flag</dt>
                  <dd style={{ margin: 0 }}>{formatValue(meta.scenario_flag)}</dd>
                  <dt>quality_flag</dt>
                  <dd style={{ margin: 0 }}>{formatValue(meta.quality_flag)}</dd>
                  <dt>trace_id</dt>
                  <dd style={{ margin: 0 }}>{formatValue(meta.trace_id)}</dd>
                  <dt>source_version</dt>
                  <dd style={{ margin: 0 }}>{formatValue(meta.source_version)}</dd>
                  <dt>rule_version</dt>
                  <dd style={{ margin: 0 }}>{formatValue(meta.rule_version)}</dd>
                  <dt>cache_version</dt>
                  <dd style={{ margin: 0 }}>{formatValue(meta.cache_version)}</dd>
                  <dt>generated_at</dt>
                  <dd style={{ margin: 0 }}>{formatValue(meta.generated_at)}</dd>
                  {hasEvidence(meta) ? (
                    <>
                      <dt>tables_used</dt>
                      <dd style={{ margin: 0 }}>{formatValue(meta.tables_used)}</dd>
                      <dt>filters_applied</dt>
                      <dd style={{ margin: 0 }}>{formatValue(meta.filters_applied)}</dd>
                      <dt>evidence_rows</dt>
                      <dd style={{ margin: 0 }}>{formatValue(meta.evidence_rows)}</dd>
                      <dt>next_drill</dt>
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
