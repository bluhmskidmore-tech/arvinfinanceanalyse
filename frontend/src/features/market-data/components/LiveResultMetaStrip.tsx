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

/**
 * 行内来源/口径元信息条（DESIGN.md §6）：正文只保留口径 / 正式可用 / 质量 / 报告日，
 * 供应商与降级仅在异常时占正文；版本、追踪编号等证据细节收进 title。
 */
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
    { label: `报告日=${displayValue(reportDate)}`, tone: "neutral" as const },
    ...(meta.vendor_status !== "ok"
      ? [{ label: `供应商=${vendorLabel[meta.vendor_status] ?? meta.vendor_status}`, tone: "warn" as const }]
      : []),
    ...(meta.fallback_mode !== "none" ? [{ label: `降级=${fallbackLabel}`, tone: "warn" as const }] : []),
  ];
  const detailTitle = [
    `供应商=${vendorLabel[meta.vendor_status] ?? meta.vendor_status}`,
    `降级=${fallbackLabel}`,
    `截至=${displayValue(meta.as_of_date)}`,
    `供应商版本=${meta.vendor_version}`,
    `来源版本=${meta.source_version}`,
    `追踪编号=${meta.trace_id}`,
  ].join("；");

  return (
    <p
      className="live-result-meta-strip"
      data-testid={testId}
      role="status"
      aria-live="polite"
      title={detailTitle}
    >
      <span className="live-result-meta-strip__lead">{lead}</span>
      {summaryItems.map((item) => (
        <span className="live-result-meta-strip__item" data-tone={item.tone} key={item.label}>
          {item.label}
        </span>
      ))}
    </p>
  );
}
