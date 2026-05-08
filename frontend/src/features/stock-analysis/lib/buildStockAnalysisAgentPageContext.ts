import type { AgentPageContext } from "../../../api/contracts";
import type { StockSectorViewKind } from "./stockAnalysisPageModel";

export const STOCK_ANALYSIS_AGENT_CONTEXT_NOTE = "stock-analysis workbench observation context";

export type BuildStockAnalysisAgentPageContextInput = {
  /** 当前快照日：取自日期覆盖或策略返回的 as_of_date */
  asOfDate?: string | null;
  sectorFilterSectorCode: string | null;
  sectorView: StockSectorViewKind;
  detailSelection: { code: string; name?: string } | null;
};

export function buildStockAnalysisAgentPageContext(
  input: BuildStockAnalysisAgentPageContextInput,
): AgentPageContext {
  const current_filters: Record<string, unknown> = {
    sector_filter: input.sectorFilterSectorCode ?? null,
    sector_view: input.sectorView,
  };
  if (input.asOfDate != null && String(input.asOfDate).trim() !== "") {
    current_filters.as_of_date = input.asOfDate;
  }

  const selected_rows: Array<Record<string, unknown>> = [];
  if (input.detailSelection) {
    const row: Record<string, unknown> = { stock_code: input.detailSelection.code };
    if (input.detailSelection.name != null && String(input.detailSelection.name).trim() !== "") {
      row.stock_name = input.detailSelection.name;
    }
    selected_rows.push(row);
  }

  return {
    page_id: "stock-analysis",
    current_filters,
    selected_rows,
    context_note: STOCK_ANALYSIS_AGENT_CONTEXT_NOTE,
  };
}
