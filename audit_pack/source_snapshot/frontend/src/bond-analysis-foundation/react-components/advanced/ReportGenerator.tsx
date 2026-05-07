import { useState, type FormEvent } from "react";

import type { Portfolio } from "../../data-structures/PortfolioModel";

export interface ReportRequest {
  template: "daily" | "strategy" | "risk";
  includeCharts: boolean;
  includeHoldings: boolean;
}

export interface ReportGeneratorProps {
  portfolio?: Portfolio;
  onGenerate?: (request: ReportRequest) => void;
}

export function ReportGenerator({ portfolio, onGenerate }: ReportGeneratorProps) {
  const [template, setTemplate] = useState<ReportRequest["template"]>("daily");
  const [includeCharts, setIncludeCharts] = useState(true);
  const [includeHoldings, setIncludeHoldings] = useState(true);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onGenerate?.({
      template,
      includeCharts,
      includeHoldings,
    });
  }

  return (
    <form onSubmit={handleSubmit} style={{ display: "grid", gap: 16 }}>
      <div>
        <h2 style={{ margin: 0 }}>报告生成</h2>
        <p style={{ margin: "6px 0 0", color: "#475467" }}>
          {portfolio ? `面向 ${portfolio.portfolioName} 生成报告` : "先选择组合再生成报告。"}
        </p>
      </div>
      <label>
        模板
        <select value={template} onChange={(event) => setTemplate(event.target.value as ReportRequest["template"])}>
          <option value="daily">日报</option>
          <option value="strategy">策略会纪要</option>
          <option value="risk">风险专报</option>
        </select>
      </label>
      <label>
        <input
          type="checkbox"
          checked={includeCharts}
          onChange={(event) => setIncludeCharts(event.target.checked)}
        />
        包含图表
      </label>
      <label>
        <input
          type="checkbox"
          checked={includeHoldings}
          onChange={(event) => setIncludeHoldings(event.target.checked)}
        />
        包含持仓明细
      </label>
      <button type="submit">生成报告</button>
    </form>
  );
}
