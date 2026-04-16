import { SectionCard } from "../../../components/SectionCard";
import { SummaryBlock } from "../../../components/SummaryBlock";
import { BORDER, panelStyle } from "./bondAnalyticsCockpitTokens";

const SUMMARY_CONTENT = "当前组合呈现'久期偏高、信用以高等级为主、浮盈较厚'的特征...";

export function PortfolioSummaryNarrative() {
  return (
    <SectionCard
      title="组合摘要"
      style={{ ...panelStyle("#ffffff"), border: `1px solid ${BORDER}` }}
    >
      <SummaryBlock
        title=""
        content={SUMMARY_CONTENT}
        tags={[
          { label: "久期:偏高", color: "blue" },
          { label: "信用:以高等级为主", color: "cyan" },
          { label: "策略:票息>波段", color: "geekblue" },
        ]}
      />
    </SectionCard>
  );
}

export default PortfolioSummaryNarrative;
