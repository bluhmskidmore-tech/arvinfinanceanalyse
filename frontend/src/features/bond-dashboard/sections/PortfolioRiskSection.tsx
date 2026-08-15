import type {
  BondDashboardHeadlinePayload,
  PortfolioComparisonPayload,
  RiskIndicatorsPayload,
  SpreadAnalysisPayload,
} from "../../../api/contracts";
import BondDashboardSectionLead, {
  type BondDashboardSectionState,
} from "../components/BondDashboardSectionLead";
import { PortfolioTable } from "../components/PortfolioTable";
import { RiskIndicatorsPanel } from "../components/RiskIndicatorsPanel";
import { SpreadTable } from "../components/SpreadTable";
import "./BondDashboardTableSections.css";

type PortfolioRiskSectionProps = {
  portfolioData: PortfolioComparisonPayload | undefined;
  portfolioLoading: boolean;
  headline: BondDashboardHeadlinePayload | undefined;
  spreadData: SpreadAnalysisPayload | undefined;
  spreadLoading: boolean;
  riskData: RiskIndicatorsPayload | undefined;
  riskLoading: boolean;
};

/** 分区头状态位：loading/empty 露一句话，正常返回 null（错误在 01 区 notice 披露）。 */
function sectionLeadState(loading: boolean, isEmpty: boolean): BondDashboardSectionState {
  if (loading) return { label: "读取中", tone: "loading" };
  if (isEmpty) return { label: "暂无数据", tone: "empty" };
  return null;
}

/** 04 组合与风险：组合对比 + 利差分析 + 风险指标（lg 三列等高，md 以下单列）。 */
export default function PortfolioRiskSection({
  portfolioData,
  portfolioLoading,
  headline,
  spreadData,
  spreadLoading,
  riskData,
  riskLoading,
}: PortfolioRiskSectionProps) {
  const loading = portfolioLoading || spreadLoading || riskLoading;
  const isEmpty =
    (portfolioData?.items.length ?? 0) === 0 &&
    (spreadData?.items.length ?? 0) === 0 &&
    !riskData;

  return (
    <section className="bond-dashboard-section" id="bond-dashboard-section-portfolio-risk">
      <BondDashboardSectionLead title="组合与风险" state={sectionLeadState(loading, isEmpty)} />
      <div className="bond-dashboard-page__grid bond-dashboard-page__grid--3 bond-dashboard-table-grid--fill">
        <PortfolioTable data={portfolioData} headline={headline} loading={portfolioLoading} />
        <SpreadTable data={spreadData} loading={spreadLoading} />
        <RiskIndicatorsPanel data={riskData} loading={riskLoading} />
      </div>
    </section>
  );
}
