import { localizeStockBackendText } from "../../stock-analysis/lib/stockAnalysisPageModel";

const LIVERMORE_READINESS_SUMMARY_ZH: Record<string, string> = {
  "Trend-only market gate is available; breadth and limit-up quality remain missing.":
    "趋势门控可用；市场宽度与涨停质量仍缺数。",
  "Trend-only market gate is available.": "趋势门控可用。",
  "Sector ranking is available from landed Choice sector inputs.":
    "板块排序已可由 Choice 板块输入支撑。",
  "Sector membership and sector-strength inputs are not landed yet.":
    "板块归属与板块强弱输入尚未落地。",
  "Stock pivot candidate screening is available for landed Choice stock inputs.":
    "个股候选筛选已可由 Choice 个股输入支撑。",
  "Stock pivot output is blocked until sector rank and stock-universe inputs land.":
    "板块排序与股票池输入未落地，个股候选暂不可用。",
  "Risk and exit output is available from landed position snapshots and close history.":
    "风险退出可由落地持仓快照与收盘价历史支撑。",
  "Risk and exit output is blocked until position and entry-cost inputs land.":
    "持仓与入场成本输入未落地，风险退出暂不可用。",
  "Risk and exit output is blocked because the position snapshot has no ACTIVE rows.":
    "持仓快照无有效持仓，风险退出暂不可用。",
  "Position snapshot is missing.": "持仓快照缺失。",
};

export function formatLivermoreReadinessSummary(
  summary: string | null | undefined,
  key?: string | null,
): string {
  const normalized = summary?.trim();
  if (!normalized) {
    return "";
  }
  return LIVERMORE_READINESS_SUMMARY_ZH[normalized] ?? localizeStockBackendText(normalized, key);
}
