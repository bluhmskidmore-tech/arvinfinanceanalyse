import type { ResultMeta } from "../../../api/contracts";
import "./LiveResultMetaStrip.css";

type LiveResultMetaStripProps = {
  meta: ResultMeta | undefined;
  testId: string;
  /** 前缀文案，例如「宏观 latest 读面」 */
  lead: string;
};

function qualityTone(quality: ResultMeta["quality_flag"]): "ok" | "warn" | "error" | "neutral" {
  if (quality === "warning" || quality === "stale") {
    return "warn";
  }
  if (quality === "error" || quality === "missing") {
    return "error";
  }
  if (quality === "ok") {
    return "ok";
  }
  return "neutral";
}

/** 紧贴主读面展示质量 / 供应商 / 降级，对应 contracts.ResultMeta（无额外 inline style=）。 */
export function LiveResultMetaStrip({ meta, testId, lead }: LiveResultMetaStripProps) {
  if (!meta) {
    return null;
  }
  const basisLabel: Record<ResultMeta["basis"], string> = {
    formal: "正式口径",
    analytical: "分析口径",
    scenario: "情景口径",
    ledger: "台账口径",
    mock: "模拟口径",
  };
  const qualityLabel: Record<ResultMeta["quality_flag"], string> = {
    ok: "正常",
    warning: "预警",
    error: "错误",
    stale: "陈旧",
    missing: "缺失",
  };
  const vendorLabel: Record<ResultMeta["vendor_status"], string> = {
    ok: "正常",
    vendor_stale: "供应商陈旧",
    vendor_unavailable: "供应商不可用",
  };
  const fallbackLabel =
    meta.fallback_mode === "none"
      ? "未降级"
      : meta.fallback_mode === "latest_snapshot"
        ? "最新快照降级"
        : meta.fallback_mode;
  const displayValue = (value: string | null | undefined, emptyLabel = "未提供") =>
    value == null || value === "" ? emptyLabel : value;
  const reportDate = meta.resolved_report_date || meta.requested_report_date;
  const formalUseAllowedLabel = meta.formal_use_allowed ? "是" : "否";
  const summaryItems = [
    { label: `口径=${basisLabel[meta.basis] ?? meta.basis}`, tone: "neutral" as const },
    { label: `正式可用=${formalUseAllowedLabel}`, tone: meta.formal_use_allowed ? ("ok" as const) : ("warn" as const) },
    { label: `质量=${qualityLabel[meta.quality_flag] ?? meta.quality_flag}`, tone: qualityTone(meta.quality_flag) },
    { label: `供应商=${vendorLabel[meta.vendor_status] ?? meta.vendor_status}`, tone: "neutral" as const },
    { label: `降级=${fallbackLabel}`, tone: meta.fallback_mode === "none" ? ("ok" as const) : ("warn" as const) },
    { label: `报告日=${displayValue(reportDate)}`, tone: "neutral" as const },
    { label: `截至=${displayValue(meta.as_of_date)}`, tone: "neutral" as const },
  ];
  const versionDetailItems = [
    { label: `供应商版本=${meta.vendor_version}` },
    { label: `来源版本=${meta.source_version}` },
    { label: `追踪编号=${meta.trace_id}` },
  ];

  return (
    <div className="live-result-meta-strip" data-testid={testId} role="status" aria-live="polite">
      <div className="live-result-meta-strip__head">
        <span className="live-result-meta-strip__lead">{lead}</span>
      </div>
      <div className="live-result-meta-strip__body">
        <div className="live-result-meta-strip__items live-result-meta-strip__items--summary">
          {summaryItems.map((item) => (
            <span className="live-result-meta-strip__pill" data-tone={item.tone} key={item.label}>
              {item.label}
            </span>
          ))}
        </div>
        <details className="live-result-meta-strip__version-details">
          <summary>来源版本明细</summary>
          <span className="live-result-meta-strip__items live-result-meta-strip__items--version">
            {versionDetailItems.map((item) => (
              <span
                className="live-result-meta-strip__item live-result-meta-strip__item--long"
                key={item.label}
                title={item.label}
              >
                {item.label}
              </span>
            ))}
          </span>
        </details>
      </div>
    </div>
  );
}
