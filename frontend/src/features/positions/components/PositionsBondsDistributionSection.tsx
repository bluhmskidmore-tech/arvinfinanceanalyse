import IndustryDistributionCard from "./IndustryDistributionCard";
import RatingDistributionCard from "./RatingDistributionCard";
import "./PositionsBondsSections.css";

/**
 * 04 评级与行业分布：两张分布卡（标准面板语言 + Nocturne 深色图表），
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
