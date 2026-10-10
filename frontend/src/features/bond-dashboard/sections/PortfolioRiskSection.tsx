import type {
  BondDashboardHeadlinePayload,
  PortfolioComparisonPayload,
  RiskIndicatorsPayload,
  SpreadAnalysisPayload,
} from "../../../api/contracts";
import { SectionGrid, SectionHead } from "../../../components/layout";
import { PortfolioTable } from "../components/PortfolioTable";
import { RiskIndicatorsPanel } from "../components/RiskIndicatorsPanel";
import { SpreadTable } from "../components/SpreadTable";
import { bondSectionState, bondSectionStatusFromStates, type BondSectionDataState } from "../sectionStatus";
import "./BondDashboardTableSections.css";

type PortfolioRiskSectionProps = {
  portfolioData: PortfolioComparisonPayload | undefined;
  portfolioState: BondSectionDataState;
  headline: BondDashboardHeadlinePayload | undefined;
  spreadData: SpreadAnalysisPayload | undefined;
  spreadState: BondSectionDataState;
  riskData: RiskIndicatorsPayload | undefined;
  riskState: BondSectionDataState;
};

/**
 * 04 组合与风险：组合对比 + 利差分析 + 风险指标。
 *
 * 列宽用权重轨道而非等分：组合表现是 6 列宽表，在 DataTable 的不换行列头下
 * 需要 456px 内容宽，等分三列给不到（实测数据见本轮报告）。三档权重按三块的
 * 实测最小内容宽分配——组合表现 > 利差分析 > 风险指标列表，最后一块是弹性的
 * 标签/读数列表，压缩后只是标签折行，不会截断数值。
 */
const PORTFOLIO_RISK_COLS = { base: 1, lg: [1.2, 0.8], xl: [1.66, 1.2, 0.74] } as const;

export default function PortfolioRiskSection({
  portfolioData,
  portfolioState,
  headline,
  spreadData,
  spreadState,
  riskData,
  riskState,
}: PortfolioRiskSectionProps) {
  const isEmpty =
    (portfolioData?.items.length ?? 0) === 0 &&
    (spreadData?.items.length ?? 0) === 0 &&
    !riskData;

  return (
    <section className="bond-dashboard-section" id="bond-dashboard-section-portfolio-risk">
      {/* 分区头状态由三个数据块的读取结果推导。 */}
      <SectionHead
        title="组合与风险"
        state={bondSectionState(
          bondSectionStatusFromStates([portfolioState, spreadState, riskState], isEmpty),
        )}
      />
      <SectionGrid cols={PORTFOLIO_RISK_COLS} gap={12} align="stretch">
        <PortfolioTable data={portfolioData} headline={headline} state={portfolioState} />
        <SpreadTable data={spreadData} state={spreadState} />
        <RiskIndicatorsPanel data={riskData} state={riskState} />
      </SectionGrid>
    </section>
  );
}
