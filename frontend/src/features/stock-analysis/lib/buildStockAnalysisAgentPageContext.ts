import type { AgentPageContext } from "../../../api/contracts";
import type { StockDetailSource } from "./stockAnalysisDetailSelection";
import type { StockSectorViewKind } from "./stockAnalysisPageModel";

export const STOCK_ANALYSIS_AGENT_CONTEXT_NOTE = "stock-analysis workbench observation context";

export type BuildStockAnalysisAgentPageContextInput = {
  /** 当前快照日：取自策略返回的实际 as_of_date。 */
  asOfDate?: string | null;
  /** 用户请求的日期；仅用于说明 fallback，不作为实际数据日。 */
  requestedAsOfDate?: string | null;
  sectorFilterSectorCode: string | null;
  sectorFilterLabel?: string | null;
  sectorView: StockSectorViewKind;
  detailSelection: {
    code: string;
    name?: string;
    reviewRank?: number;
    sectorCode?: string;
    sectorName?: string;
    source?: StockDetailSource;
    livermoreRank?: number | null;
    meanReversionRank?: number | null;
    factorScreenRank?: number | null;
    hybridFusionRank?: number | null;
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
  if (
    input.requestedAsOfDate != null &&
    String(input.requestedAsOfDate).trim() !== "" &&
    input.requestedAsOfDate !== input.asOfDate
  ) {
    current_filters.requested_as_of_date = input.requestedAsOfDate;
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
    if (input.detailSelection.hybridFusionRank != null) {
      row.hybrid_fusion_rank = input.detailSelection.hybridFusionRank;
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
