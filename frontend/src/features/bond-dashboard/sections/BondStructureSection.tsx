import type { AssetStructurePayload, YieldDistributionPayload } from "../../../api/contracts";
import { SectionGrid, SectionHead } from "../../../components/layout";
import { AssetStructurePie, type AssetGroupBy } from "../components/AssetStructurePie";
import { CreditRatingBlocks } from "../components/CreditRatingBlocks";
import { YieldDistributionBar } from "../components/YieldDistributionBar";
import { bondSectionState, bondSectionStatusFromStates, type BondSectionDataState } from "../sectionStatus";
import "./BondDashboardChartSections.css";

type BondStructureSectionProps = {
  assetData: AssetStructurePayload | undefined;
  assetState: BondSectionDataState;
  groupBy: AssetGroupBy;
  onGroupByChange: (groupBy: AssetGroupBy) => void;
  ratingData: AssetStructurePayload | undefined;
  ratingState: BondSectionDataState;
  yieldData: YieldDistributionPayload | undefined;
  tenorData: AssetStructurePayload | undefined;
  yieldState: BondSectionDataState;
  tenorState: BondSectionDataState;
};

/** 02 资产结构：券种/评级/期限占比 + 收益率分布（lg 三面板等高网格）。 */
export default function BondStructureSection({
  assetData,
  assetState,
  groupBy,
  onGroupByChange,
  ratingData,
  ratingState,
  yieldData,
  tenorData,
  yieldState,
  tenorState,
}: BondStructureSectionProps) {
  const isEmpty =
    (assetData?.items.length ?? 0) === 0 &&
    (ratingData?.items.length ?? 0) === 0 &&
    (yieldData?.items.length ?? 0) === 0 &&
    (tenorData?.items.length ?? 0) === 0;

  return (
    <section className="bond-dashboard-section" id="bond-dashboard-section-structure">
      {/* 分区头状态由四个数据块的读取结果推导，块里红了分区头不会还写着暂无数据。 */}
      <SectionHead
        title="资产结构"
        state={bondSectionState(
          bondSectionStatusFromStates([assetState, ratingState, yieldState, tenorState], isEmpty),
        )}
      />
      {/* 三面板刻意等高：短面板靠卡片背景补齐，不留裸空白断层（DESIGN.md §5）。 */}
      <SectionGrid cols={{ base: 1, lg: 3 }} gap={12} align="stretch">
        <AssetStructurePie
          data={assetData}
          state={assetState}
          groupBy={groupBy}
          onGroupByChange={onGroupByChange}
        />
        <YieldDistributionBar
          yieldData={yieldData}
          tenorData={tenorData}
          yieldState={yieldState}
          tenorState={tenorState}
        />
        <CreditRatingBlocks data={ratingData} state={ratingState} />
      </SectionGrid>
    </section>
  );
}
