import type { ResultMeta } from "../../api/contracts";
import { designTokens as dt } from "../../theme/designSystem";
import { shellTokens as t } from "../../theme/tokens";
import "./FormalResultMetaPanel.css";

type FormalResultMetaSection = {
  key: string;
  title: string;
  meta: ResultMeta | null | undefined;
  vendor_status?: ResultMeta["vendor_status"];
  fallback_mode?: ResultMeta["fallback_mode"];
};

type FormalResultMetaPanelProps = {
  testId?: string;
  title?: string;
  emptyText?: string;
  sections: FormalResultMetaSection[];
};

const missingAsOfDateLabel = "未提供";

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

function formatAsOfDate(value: ResultMeta["as_of_date"]): string {
  if (value === null || value === undefined || value === "") {
    return missingAsOfDateLabel;
  }
  return formatValue(value);
}

function formatMetaField(key: string, value: unknown): string {
  if (key === "basis") {
    if (value === "formal") return "正式口径";
    if (value === "analytical") return "分析口径";
    if (value === "scenario") return "情景口径";
    if (value === "ledger") return "台账口径";
  }
  if (key === "quality_flag") {
    const labels: Record<string, string> = {
      ok: "正常",
      warning: "预警",
      error: "错误",
      stale: "陈旧",
      missing: "缺失",
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
  requested_report_date: "请求报告日",
  resolved_report_date: "解析报告日",
  trace_id: "追踪编号",
  source_version: "来源版本",
  vendor_version: "供应商版本",
  rule_version: "规则版本",
  cache_version: "缓存版本",
  as_of_date: "数据截至日",
  date_basis: "日期基准",
  fallback_date: "降级日期",
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

/**
 * 徽章色经 CSS 变量出口（回退值 = 原浅色字面量，浅色页面零变化），
 * 深色页面可在自身 scope 内重定义 --formal-meta-badge-* 完成换肤。
 */
const badgeToneFallbacks = {
  ok: {
    bg: t.colorBgSuccessSoft,
    ink: dt.color.success[700],
    line: dt.color.success[200],
  },
  warn: {
    bg: t.colorBgWarningSoft,
    ink: t.colorTextWarning,
    line: t.colorBorderWarning,
  },
  danger: {
    bg: t.colorBgDangerSoft,
    ink: dt.color.danger[700],
    line: dt.color.danger[200],
  },
} as const;

function toneStyle(tone: keyof typeof badgeToneFallbacks) {
  const fallback = badgeToneFallbacks[tone];
  return {
    background: `var(--formal-meta-badge-${tone}-bg, ${fallback.bg})`,
    color: `var(--formal-meta-badge-${tone}-ink, ${fallback.ink})`,
    borderColor: `var(--formal-meta-badge-${tone}-line, ${fallback.line})`,
  };
}

function badgeTone(
  kind: "vendor_status" | "fallback_mode",
  value: string | undefined,
) {
  if (kind === "vendor_status") {
    if (value === "vendor_stale") {
      return toneStyle("warn");
    }
    if (value === "vendor_unavailable") {
      return toneStyle("danger");
    }
  }
  if (kind === "fallback_mode" && value === "latest_snapshot") {
    return toneStyle("warn");
  }
  return toneStyle("ok");
}

function buildBadges(section: FormalResultMetaSection) {
  const meta = section.meta;
  const vendorStatus = section.vendor_status ?? meta?.vendor_status;
  const fallbackMode = section.fallback_mode ?? meta?.fallback_mode;

  return [
    {
      key: "vendor_status",
      value: vendorStatus,
      label: formatMetaField("vendor_status", vendorStatus),
      title: `供应商状态：${formatMetaField("vendor_status", vendorStatus)}`,
    },
    {
      key: "fallback_mode",
      value: fallbackMode,
      label: formatMetaField("fallback_mode", fallbackMode),
      title: `降级模式：${formatMetaField("fallback_mode", fallbackMode)}`,
    },
  ].filter((badge) => typeof badge.value === "string");
}

export function FormalResultMetaPanel({
  testId,
  title = "结果元信息 / 证据",
  emptyText = "当前还没有可展示的溯源信封。",
  sections,
}: FormalResultMetaPanelProps) {
  const visibleSections = sections.filter((section) => section.meta);

  return (
    <section data-testid={testId} className="formal-result-meta-panel">
      <div className="formal-result-meta-panel__title">{title}</div>
      <div className="formal-result-meta-panel__subtitle">
        展示当前读链路返回的口径、版本、质量与可选证据字段；页面不在前端补算正式指标。
      </div>

      {visibleSections.length === 0 ? (
        <div className="formal-result-meta-panel__empty">{emptyText}</div>
      ) : (
        <div className="formal-result-meta-panel__grid">
          {visibleSections.map((section) => {
            const meta = section.meta!;
            const vendorStatus = section.vendor_status ?? meta.vendor_status;
            const fallbackMode = section.fallback_mode ?? meta.fallback_mode;
            const badges = buildBadges(section);

            return (
              <article
                key={section.key}
                data-testid={`${testId}-${section.key}`}
                className="formal-result-meta-panel__card"
              >
                <div className="formal-result-meta-panel__label">溯源</div>
                <div className="formal-result-meta-panel__card-header">
                  <div className="formal-result-meta-panel__heading">{section.title}</div>
                  {badges.length > 0 ? (
                    <div className="formal-result-meta-panel__badge-row">
                      {badges.map((badge) => {
                        const tone = badgeTone(
                          badge.key as "vendor_status" | "fallback_mode",
                          badge.value,
                        );
                        return (
                          <span
                            key={badge.key}
                            title={badge.title}
                            className="formal-result-meta-panel__badge"
                            style={tone}
                          >
                            {badge.label}
                          </span>
                        );
                      })}
                    </div>
                  ) : null}
                </div>
                <dl className="formal-result-meta-panel__list">
                  <dt>{metaLabelMap.basis}</dt>
                  <dd className="formal-result-meta-panel__value">{formatMetaField("basis", meta.basis)}</dd>
                  <dt>{metaLabelMap.result_kind}</dt>
                  <dd className="formal-result-meta-panel__value">{formatValue(meta.result_kind)}</dd>
                  <dt>{metaLabelMap.formal_use_allowed}</dt>
                  <dd className="formal-result-meta-panel__value">{formatValue(meta.formal_use_allowed)}</dd>
                  <dt>{metaLabelMap.scenario_flag}</dt>
                  <dd className="formal-result-meta-panel__value">{formatValue(meta.scenario_flag)}</dd>
                  <dt>{metaLabelMap.quality_flag}</dt>
                  <dd className="formal-result-meta-panel__value">
                    {formatMetaField("quality_flag", meta.quality_flag)}
                  </dd>
                  <dt>{metaLabelMap.vendor_status}</dt>
                  <dd className="formal-result-meta-panel__value">
                    {formatMetaField("vendor_status", vendorStatus)}
                  </dd>
                  <dt>{metaLabelMap.fallback_mode}</dt>
                  <dd className="formal-result-meta-panel__value">
                    {formatMetaField("fallback_mode", fallbackMode)}
                  </dd>
                  <dt>{metaLabelMap.trace_id}</dt>
                  <dd className="formal-result-meta-panel__value">{formatValue(meta.trace_id)}</dd>
                  <dt>{metaLabelMap.source_version}</dt>
                  <dd className="formal-result-meta-panel__value">{formatValue(meta.source_version)}</dd>
                  <dt>{metaLabelMap.vendor_version}</dt>
                  <dd className="formal-result-meta-panel__value">{formatValue(meta.vendor_version)}</dd>
                  <dt>{metaLabelMap.rule_version}</dt>
                  <dd className="formal-result-meta-panel__value">{formatValue(meta.rule_version)}</dd>
                  <dt>{metaLabelMap.cache_version}</dt>
                  <dd className="formal-result-meta-panel__value">{formatValue(meta.cache_version)}</dd>
                  <dt>{metaLabelMap.requested_report_date}</dt>
                  <dd className="formal-result-meta-panel__value">{formatValue(meta.requested_report_date)}</dd>
                  <dt>{metaLabelMap.resolved_report_date}</dt>
                  <dd className="formal-result-meta-panel__value">{formatValue(meta.resolved_report_date)}</dd>
                  <dt>{metaLabelMap.as_of_date}</dt>
                  <dd className="formal-result-meta-panel__value">{formatAsOfDate(meta.as_of_date)}</dd>
                  <dt>{metaLabelMap.date_basis}</dt>
                  <dd className="formal-result-meta-panel__value">{formatValue(meta.date_basis)}</dd>
                  <dt>{metaLabelMap.fallback_date}</dt>
                  <dd className="formal-result-meta-panel__value">{formatValue(meta.fallback_date)}</dd>
                  <dt>{metaLabelMap.generated_at}</dt>
                  <dd className="formal-result-meta-panel__value">{formatValue(meta.generated_at)}</dd>
                  {hasEvidence(meta) ? (
                    <>
                      <dt>{metaLabelMap.tables_used}</dt>
                      <dd className="formal-result-meta-panel__value">{formatValue(meta.tables_used)}</dd>
                      <dt>{metaLabelMap.filters_applied}</dt>
                      <dd className="formal-result-meta-panel__value">{formatValue(meta.filters_applied)}</dd>
                      <dt>{metaLabelMap.evidence_rows}</dt>
                      <dd className="formal-result-meta-panel__value">{formatValue(meta.evidence_rows)}</dd>
                      <dt>{metaLabelMap.next_drill}</dt>
                      <dd className="formal-result-meta-panel__value">{formatValue(meta.next_drill)}</dd>
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
