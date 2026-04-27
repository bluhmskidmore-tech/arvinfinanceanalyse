import { Alert } from "antd";

import type { ResultMeta } from "../../../api/contracts";

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
  const qualityLabel: Record<ResultMeta["quality_flag"], string> = {
    ok: "正常",
    warning: "预警",
    error: "错误",
    stale: "陈旧",
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
  const line = [
    `${lead}`,
    `质量=${qualityLabel[meta.quality_flag] ?? meta.quality_flag}`,
    `供应商状态=${vendorLabel[meta.vendor_status] ?? meta.vendor_status}`,
    `降级模式=${fallbackLabel}`,
    `供应商版本=${meta.vendor_version}`,
    `来源版本=${meta.source_version}`,
    `追踪编号=${meta.trace_id}`,
  ].join(" · ");
  return <Alert data-testid={testId} type="info" showIcon message={line} />;
}
