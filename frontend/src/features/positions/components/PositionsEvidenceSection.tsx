import type { ResultMeta } from "../../../api/contracts";
import { FormalResultMetaPanel } from "../../../components/page/FormalResultMetaPanel";
import type { PositionsTabKey } from "../model/positionsPageModel";
import "./PositionsEvidenceSection.css";

/**
 * 证据与口径分区：当前 tab 的列表信封与聚合信封（B11 起快照全部端点
 * 统一为分析口径 analytical，formal_use_allowed=false）。
 * result_meta 原样透出，date_basis / tables_used / filters_applied /
 * evidence_rows 由 FormalResultMetaPanel 自动渲染；面板视觉在
 * PositionsEvidenceSection.css 内以 positions 作用域收敛，不改共享组件本体。
 */
export default function PositionsEvidenceSection({
  tab,
  listMeta,
  aggregateMeta,
  caliberItems,
  open,
  onOpenChange,
}: {
  tab: PositionsTabKey;
  listMeta: ResultMeta | null | undefined;
  aggregateMeta: ResultMeta | null | undefined;
  caliberItems: string[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const listTitle = tab === "bonds" ? "债券持仓明细（分析口径）" : "同业持仓明细（分析口径）";
  const aggregateTitle = tab === "bonds" ? "授信主体聚合（分析口径）" : "资产负债结构（分析口径）";

  return (
    <details
      className="positions-evidence"
      open={open}
      onToggle={(event) => onOpenChange(event.currentTarget.open)}
    >
      <summary className="positions-evidence__summary">数据与口径说明</summary>
      <div data-testid="positions-data-status" className="positions-view__caliber">
        {caliberItems.filter((item) => !item.startsWith("数据来源：")).map((item) => (
          <span key={item} className="positions-view__caliber-item">
            {item}
          </span>
        ))}
      </div>
      <p className="positions-evidence__note" data-testid="positions-evidence-note">
        明细与区间统计仅供分析参考，尚未获准作为正式业务依据。
      </p>
      <details className="positions-evidence__diagnostics">
        <summary className="positions-evidence__summary">技术诊断</summary>
        <p className="positions-evidence__note">
          {caliberItems.filter((item) => item.startsWith("数据来源：")).join("；")}
        </p>
        <p data-testid="positions-list-candidate-boundary" className="positions-evidence__note">
          GAP-POS-LIST 尚未关闭；MTR-POS-001、MTR-POS-002 仍为 candidate，pending_confirmation=true，bound_sample_id=GS-POSITIONS-BONDS-LIST-A / GS-POSITIONS-INTERBANK-LIST-A（capture-ready，待业主审批）。
        </p>
      </details>
      <FormalResultMetaPanel
        testId="positions-evidence-panel"
        sections={[
          { key: "list", title: listTitle, meta: listMeta },
          { key: "aggregate", title: aggregateTitle, meta: aggregateMeta },
        ]}
      />
    </details>
  );
}
