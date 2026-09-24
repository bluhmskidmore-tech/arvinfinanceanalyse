import { EvidencePanel, PageStateSurface } from "../../../components/page/PagePrimitives";
import styles from "./AssetStructurePie.module.css";

/** 独立饼图占位：组合资产结构请使用驾驶舱「债券资产结构」或 KRD 明细中的真实占比图。 */
export function AssetStructurePie() {
  return (
    <EvidencePanel heading="债券资产结构">
      <PageStateSurface
        variant="definition-pending"
        description="本卡片未接独立接口；请在概览驾驶舱「债券资产结构」或「曲线风险」明细查看按资产类的真实权重与市值。"
      >
        <p className={styles.footnote}>已移除静态示意切片，避免与真实持仓口径混淆。</p>
      </PageStateSurface>
    </EvidencePanel>
  );
}

export default AssetStructurePie;
