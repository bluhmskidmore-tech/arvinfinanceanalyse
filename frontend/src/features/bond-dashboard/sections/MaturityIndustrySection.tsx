import type { IndustryDistPayload, MaturityStructurePayload } from "../../../api/contracts";
import { SectionGrid, SectionHead } from "../../../components/layout";
import { IndustryTable } from "../components/IndustryTable";
import { MaturityStructureChart } from "../components/MaturityStructureChart";
import { bondSectionState, bondSectionStatusFromStates, type BondSectionDataState } from "../sectionStatus";
import "./BondDashboardChartSections.css";

type MaturityIndustrySectionProps = {
  maturityData: MaturityStructurePayload | undefined;
  maturityState: BondSectionDataState;
  industryData: IndustryDistPayload | undefined;
  industryState: BondSectionDataState;
};

/** 03 期限与行业：期限结构 + 行业分布（lg 两列，不等高网格保持 start 对齐）。 */
export default function MaturityIndustrySection({
  maturityData,
  maturityState,
  industryData,
  industryState,
}: MaturityIndustrySectionProps) {
  const isEmpty =
    (maturityData?.items.length ?? 0) === 0 && (industryData?.items.length ?? 0) === 0;

  return (
    <section className="bond-dashboard-section" id="bond-dashboard-section-maturity-industry">
      {/* 分区头状态由两个数据块的读取结果推导。 */}
      <SectionHead
        title="期限与行业"
        state={bondSectionState(bondSectionStatusFromStates([maturityState, industryState], isEmpty))}
      />
      <SectionGrid cols={{ base: 1, lg: 2 }} gap={12}>
        <MaturityStructureChart data={maturityData} state={maturityState} />
        <IndustryTable data={industryData} state={industryState} />
      </SectionGrid>
    </section>
  );
}
