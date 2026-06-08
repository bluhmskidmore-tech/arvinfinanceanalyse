import { Alert } from "antd";

import type { ResultMeta } from "../../../api/contracts";
import "./LiveResultMetaStrip.css";

type LiveResultMetaStripProps = {
  meta: ResultMeta | undefined;
  testId: string;
  /** 前缀文案，例如「宏观 latest 读面」 */
  lead: string;
};

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
  const items = [
    { label: `口径=${basisLabel[meta.basis] ?? meta.basis}` },
    { label: `正式可用=${formalUseAllowedLabel}` },
    { label: `质量=${qualityLabel[meta.quality_flag] ?? meta.quality_flag}` },
    { label: `供应商状态=${vendorLabel[meta.vendor_status] ?? meta.vendor_status}` },
    { label: `降级模式=${fallbackLabel}` },
    { label: `报告日=${displayValue(reportDate)}` },
    { label: `数据截至=${displayValue(meta.as_of_date)}` },
    { label: `降级日期=${displayValue(meta.fallback_date)}` },
    { label: `生成时间=${meta.generated_at}` },
    { label: `供应商版本=${meta.vendor_version}`, long: true },
    { label: `来源版本=${meta.source_version}`, long: true },
    { label: `追踪编号=${meta.trace_id}`, long: true },
  ];
  return (
    <Alert
      className="live-result-meta-strip"
      data-testid={testId}
      type="info"
      showIcon
      message={lead}
      description={
        <span className="live-result-meta-strip__items">
          {items.map((item) => (
            <span
              className={[
                "live-result-meta-strip__item",
                item.long ? "live-result-meta-strip__item--long" : "",
              ]
                .filter(Boolean)
                .join(" ")}
              key={item.label}
              title={item.long ? item.label : undefined}
            >
              {item.label}
            </span>
          ))}
        </span>
      }
    />
  );
}
