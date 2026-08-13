import type { ResultMeta } from "../../../api/contracts";
import { FormalResultMetaPanel } from "../../../components/page/FormalResultMetaPanel";
import type { PositionsTabKey } from "../model/positionsPageModel";

/**
 * 05/04' 证据与口径：当前 tab 的列表信封（分析口径）与聚合信封（正式口径）
 * 原样透出 result_meta；本区只做溯源展示，细节打磨归角色 8。
 */
export default function PositionsEvidenceSection({
  tab,
  listMeta,
  aggregateMeta,
}: {
  tab: PositionsTabKey;
  listMeta: ResultMeta | null | undefined;
  aggregateMeta: ResultMeta | null | undefined;
}) {
  const listTitle = tab === "bonds" ? "债券持仓明细（分析口径）" : "同业持仓明细（分析口径）";
  const aggregateTitle =
    tab === "bonds" ? "授信主体区间聚合（正式口径）" : "同业资产负债聚合（正式口径）";

  return (
    <FormalResultMetaPanel
      testId="positions-evidence-panel"
      sections={[
        { key: "list", title: listTitle, meta: listMeta },
        { key: "aggregate", title: aggregateTitle, meta: aggregateMeta },
      ]}
    />
  );
}
