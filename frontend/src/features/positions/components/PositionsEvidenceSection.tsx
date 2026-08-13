import type { ResultMeta } from "../../../api/contracts";
import { FormalResultMetaPanel } from "../../../components/page/FormalResultMetaPanel";
import type { PositionsTabKey } from "../model/positionsPageModel";
import "./PositionsEvidenceSection.css";

/**
 * 证据与口径分区：当前 tab 的列表信封（分析口径）与聚合信封（正式口径）。
 * result_meta 原样透出，date_basis / tables_used / filters_applied /
 * evidence_rows 由 FormalResultMetaPanel 自动渲染；面板视觉在
 * PositionsEvidenceSection.css 内以 positions 作用域收敛，不改共享组件本体。
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
  const aggregateTitle = tab === "bonds" ? "授信主体聚合（正式口径）" : "资产负债结构（正式口径）";

  return (
    <div className="positions-evidence">
      <p className="positions-evidence__note" data-testid="positions-evidence-note">
        列表为分析口径（candidate），聚合为正式口径；证据字段来自后端信封原样透出。
      </p>
      <FormalResultMetaPanel
        testId="positions-evidence-panel"
        sections={[
          { key: "list", title: listTitle, meta: listMeta },
          { key: "aggregate", title: aggregateTitle, meta: aggregateMeta },
        ]}
      />
    </div>
  );
}
