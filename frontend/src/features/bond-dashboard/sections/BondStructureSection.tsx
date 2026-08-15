import type { AssetStructurePayload, YieldDistributionPayload } from "../../../api/contracts";
import { AssetStructurePie, type AssetGroupBy } from "../components/AssetStructurePie";
import BondDashboardSectionLead, {
  type BondDashboardSectionState,
} from "../components/BondDashboardSectionLead";
import { CreditRatingBlocks } from "../components/CreditRatingBlocks";
import { YieldDistributionBar } from "../components/YieldDistributionBar";
import "./BondDashboardChartSections.css";

type BondStructureSectionProps = {
  assetData: AssetStructurePayload | undefined;
  assetLoading: boolean;
  groupBy: AssetGroupBy;
  onGroupByChange: (groupBy: AssetGroupBy) => void;
  ratingData: AssetStructurePayload | undefined;
  ratingLoading: boolean;
  yieldData: YieldDistributionPayload | undefined;
  tenorData: AssetStructurePayload | undefined;
  yieldLoading: boolean;
  tenorLoading: boolean;
};

/** 分区头状态位：loading/empty 露一句话，正常返回 null（错误在 01 区 notice 披露）。 */
function sectionLeadState(loading: boolean, isEmpty: boolean): BondDashboardSectionState {
  if (loading) return { label: "读取中", tone: "loading" };
  if (isEmpty) return { label: "暂无数据", tone: "empty" };
  return null;
}

/** 02 资产结构：券种/评级/期限占比 + 收益率分布（lg 三面板等高网格）。 */
export default function BondStructureSection({
  assetData,
  assetLoading,
  groupBy,
  onGroupByChange,
  ratingData,
  ratingLoading,
  yieldData,
  tenorData,
  yieldLoading,
  tenorLoading,
}: BondStructureSectionProps) {
  const loading = assetLoading || ratingLoading || yieldLoading || tenorLoading;
  const isEmpty =
    (assetData?.items.length ?? 0) === 0 &&
    (ratingData?.items.length ?? 0) === 0 &&
    (yieldData?.items.length ?? 0) === 0 &&
    (tenorData?.items.length ?? 0) === 0;

  return (
    <section className="bond-dashboard-section" id="bond-dashboard-section-structure">
      <BondDashboardSectionLead title="资产结构" state={sectionLeadState(loading, isEmpty)} />
      <div className="bond-dashboard-page__grid bond-dashboard-page__grid--3 bond-dashboard-charts__grid-equal">
        <AssetStructurePie
          data={assetData}
          loading={assetLoading}
          groupBy={groupBy}
          onGroupByChange={onGroupByChange}
        />
        <YieldDistributionBar
          yieldData={yieldData}
          tenorData={tenorData}
          loadingYield={yieldLoading}
          loadingTenor={tenorLoading}
        />
        <CreditRatingBlocks data={ratingData} loading={ratingLoading} />
      </div>
    </section>
  );
}
