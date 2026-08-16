import type { IndustryDistPayload, MaturityStructurePayload } from "../../../api/contracts";
import BondDashboardSectionLead, {
  type BondDashboardSectionState,
} from "../components/BondDashboardSectionLead";
import { IndustryTable } from "../components/IndustryTable";
import { MaturityStructureChart } from "../components/MaturityStructureChart";
import "./BondDashboardChartSections.css";

type MaturityIndustrySectionProps = {
  maturityData: MaturityStructurePayload | undefined;
  maturityLoading: boolean;
  industryData: IndustryDistPayload | undefined;
  industryLoading: boolean;
};

/** 分区头状态位：loading/empty 露一句话，正常返回 null（错误在 01 区 notice 披露）。 */
function sectionLeadState(loading: boolean, isEmpty: boolean): BondDashboardSectionState {
  if (loading) return { label: "读取中", tone: "loading" };
  if (isEmpty) return { label: "暂无数据", tone: "empty" };
  return null;
}

/** 03 期限与行业：期限结构 + 行业分布（lg 两列，不等高网格保持 start 对齐）。 */
export default function MaturityIndustrySection({
  maturityData,
  maturityLoading,
  industryData,
  industryLoading,
}: MaturityIndustrySectionProps) {
  const loading = maturityLoading || industryLoading;
  const isEmpty =
    (maturityData?.items.length ?? 0) === 0 && (industryData?.items.length ?? 0) === 0;

  return (
    <section className="bond-dashboard-section" id="bond-dashboard-section-maturity-industry">
      <BondDashboardSectionLead title="期限与行业" state={sectionLeadState(loading, isEmpty)} />
      <div className="bond-dashboard-page__grid bond-dashboard-page__grid--2">
        <MaturityStructureChart data={maturityData} loading={maturityLoading} />
        <IndustryTable data={industryData} loading={industryLoading} />
      </div>
    </section>
  );
}
