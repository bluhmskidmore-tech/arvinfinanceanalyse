import type { AgentPageContext } from "../../../api/contracts";
import type { StockSectorViewKind } from "./stockAnalysisPageModel";

export const STOCK_ANALYSIS_AGENT_CONTEXT_NOTE = "stock-analysis workbench observation context";

export type BuildStockAnalysisAgentPageContextInput = {
  /** 当前快照日：取自日期覆盖或策略返回的 as_of_date */
  asOfDate?: string | null;
  sectorFilterSectorCode: string | null;
  sectorFilterLabel?: string | null;
  sectorView: StockSectorViewKind;
  detailSelection: {
    code: string;
    name?: string;
    reviewRank?: number;
    sectorCode?: string;
    sectorName?: string;
    source?: "review_queue" | "risk_exit" | "mean_reversion" | "factor_screen" | "consensus";
    livermoreRank?: number | null;
    meanReversionRank?: number | null;
    factorScreenRank?: number | null;
  } | null;
};

export function buildStockAnalysisAgentPageContext(
  input: BuildStockAnalysisAgentPageContextInput,
): AgentPageContext {
  const current_filters: Record<string, unknown> = {
    sector_filter: input.sectorFilterSectorCode ?? null,
    sector_filter_label: input.sectorFilterLabel ?? null,
    sector_view: input.sectorView,
    current_view: input.detailSelection
      ? "stock_detail"
      : input.sectorFilterSectorCode
        ? "review_queue_filtered"
        : "decision",
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
    if (input.detailSelection.reviewRank != null) {
      row.review_rank = input.detailSelection.reviewRank;
    }
    if (input.detailSelection.sectorCode != null && String(input.detailSelection.sectorCode).trim() !== "") {
      row.sector_code = input.detailSelection.sectorCode;
    }
    if (input.detailSelection.sectorName != null && String(input.detailSelection.sectorName).trim() !== "") {
      row.sector_name = input.detailSelection.sectorName;
    }
    if (input.detailSelection.source != null) {
      row.source = input.detailSelection.source;
    }
    if (input.detailSelection.livermoreRank != null) {
      row.livermore_rank = input.detailSelection.livermoreRank;
    }
    if (input.detailSelection.meanReversionRank != null) {
      row.mean_reversion_rank = input.detailSelection.meanReversionRank;
    }
    if (input.detailSelection.factorScreenRank != null) {
      row.factor_screen_rank = input.detailSelection.factorScreenRank;
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
