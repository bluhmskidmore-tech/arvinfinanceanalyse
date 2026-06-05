import type { Portfolio } from "../../data-structures/PortfolioModel";
import { HistoricalPerformance, type PerformanceSeries } from "../charts/HistoricalPerformance";
import { RiskMatrix, type RiskMatrixBubble } from "../charts/RiskMatrix";

export interface RiskAnalysisProps {
  portfolio?: Portfolio;
  matrixItems?: RiskMatrixBubble[];
  performanceSeries?: PerformanceSeries[];
  stressNotes?: string[];
}

export function RiskAnalysis({
  portfolio,
  matrixItems = [],
  performanceSeries = [],
  stressNotes = [],
}: RiskAnalysisProps) {
  return (
    <section style={{ display: "grid", gap: 24 }}>
      <div>
        <h2 style={{ margin: 0 }}>风险分析</h2>
        <p style={{ margin: "6px 0 0", color: "#475467" }}>
          {portfolio ? `${portfolio.portfolioName} 的风险暴露与情景损益。` : "请先选择投资组合。"}
        </p>
      </div>
      <RiskMatrix items={matrixItems} />
      <HistoricalPerformance series={performanceSeries} />
      {stressNotes.length ? (
        <div style={{ borderRadius: 18, border: "1px solid #d0d5dd", background: "#fff", padding: 16 }}>
          <strong>风险提示</strong>
          <ul style={{ marginBottom: 0 }}>
            {stressNotes.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
