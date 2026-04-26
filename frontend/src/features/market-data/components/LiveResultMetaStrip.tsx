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
  const line = [
    `${lead}`,
    `质量=${meta.quality_flag}`,
    `供应商状态=${meta.vendor_status}`,
    `降级模式=${meta.fallback_mode}`,
    `供应商版本=${meta.vendor_version}`,
    `来源版本=${meta.source_version}`,
    `追踪编号=${meta.trace_id}`,
  ].join(" · ");
  return <Alert data-testid={testId} type="info" showIcon message={line} />;
}
