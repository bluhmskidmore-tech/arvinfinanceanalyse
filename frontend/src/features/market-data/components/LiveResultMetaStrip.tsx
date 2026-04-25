import { Alert } from "antd";

import type { ResultMeta } from "../../../api/contracts";

type LiveResultMetaStripProps = {
  meta: ResultMeta | undefined;
  testId: string;
  /** 前缀文案，例如「宏观 latest 读面」 */
  lead: string;
};

/** 紧贴主读面展示 quality / vendor / fallback，对应 contracts.ResultMeta（无额外 inline style=）。 */
export function LiveResultMetaStrip({ meta, testId, lead }: LiveResultMetaStripProps) {
  if (!meta) {
    return null;
  }
  const line = [
    `${lead}`,
    `quality=${meta.quality_flag}`,
    `vendor_status=${meta.vendor_status}`,
    `fallback_mode=${meta.fallback_mode}`,
    `vendor_version=${meta.vendor_version}`,
    `source_version=${meta.source_version}`,
    `trace_id=${meta.trace_id}`,
  ].join(" · ");
  return <Alert data-testid={testId} type="info" showIcon message={line} />;
}
