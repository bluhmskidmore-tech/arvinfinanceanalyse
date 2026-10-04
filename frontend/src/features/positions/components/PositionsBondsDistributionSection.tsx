import { SectionGrid } from "../../../components/layout";
import IndustryDistributionCard from "./IndustryDistributionCard";
import RatingDistributionCard from "./RatingDistributionCard";
import "./PositionsBondsSections.css";

/**
 * 04 评级与行业分布：两张分布卡（标准面板语言 + Nocturne 深色图表）。
 * 双列在 1024 以下折单列；不等高 start 对齐由 SectionGrid 默认保证（§11.2）。
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
    <SectionGrid cols={{ base: 1, md: 1, lg: 2 }} gap={12}>
      <RatingDistributionCard startDate={startDate} endDate={endDate} subType={subType} />
      <IndustryDistributionCard startDate={startDate} endDate={endDate} subType={subType} />
    </SectionGrid>
  );
}
