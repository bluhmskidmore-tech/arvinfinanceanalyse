import IndustryDistributionCard from "./IndustryDistributionCard";
import RatingDistributionCard from "./RatingDistributionCard";

/**
 * 04 评级与行业分布：包裹现有两张分布卡（卡片内部实现不改），
 * 双列 grid align-items:start 防不等高 stretch 留白。
 */
export default function PositionsBondsDistributionSection({
  startDate,
  endDate,
  subType,
}: {
  startDate: string | null;
  endDate: string | null;
  subType: string | null;
}) {
  return (
    <div className="positions-view__dist-grid">
      <RatingDistributionCard startDate={startDate} endDate={endDate} subType={subType} />
      <IndustryDistributionCard startDate={startDate} endDate={endDate} subType={subType} />
    </div>
  );
}
