import type { PnlV1DetailRow } from "../../../api/contracts";
import type { RankingBarRow } from "./RankingBarsCard";

function parseYuan(value: string | number | null | undefined): number {
  if (value === null || value === undefined || value === "") {
    return 0;
  }
  const n = Number(String(value).replace(/,/g, ""));
  return Number.isFinite(n) ? n : 0;
}

type AggRow = {
  key: string;
  interest_income: number;
  fair_value_change: number;
  capital_gain: number;
  total_pnl: number;
  proportion?: number | null;
};

function aggBy(
  keyFn: (r: PnlV1DetailRow) => string,
  dataRows: PnlV1DetailRow[],
  baseTotal: number,
): RankingBarRow[] {
  const m = new Map<string, AggRow>();
  for (const r of dataRows) {
    const key = keyFn(r);
    const cur =
      m.get(key) ||
      ({
        key,
        interest_income: 0,
        fair_value_change: 0,
        capital_gain: 0,
        total_pnl: 0,
      } satisfies AggRow);
    cur.interest_income += parseYuan(r.interest_income);
    cur.fair_value_change += parseYuan(r.fair_value_change);
    cur.capital_gain += parseYuan(r.capital_gain);
    cur.total_pnl += parseYuan(r.total_pnl);
    m.set(key, cur);
  }
  return Array.from(m.values())
    .map((x) => ({
      ...x,
      proportion: baseTotal !== 0 ? x.total_pnl / baseTotal : null,
    }))
    .sort((a, b) => Math.abs(b.total_pnl) - Math.abs(a.total_pnl));
}

export function buildYieldAnalysisAggregates(rows: PnlV1DetailRow[]) {
  const totalPnl = rows.reduce((s, r) => s + parseYuan(r.total_pnl), 0);
  const nonstdRows = rows.filter((r) => r.source === "NonStd");
  const nonstdTotalPnl = nonstdRows.reduce((s, r) => s + parseYuan(r.total_pnl), 0);
  const fiRows = rows.filter((r) => r.source !== "NonStd");
  const fiTotalPnl = fiRows.reduce((s, r) => s + parseYuan(r.total_pnl), 0);

  return {
    by_portfolio: aggBy((r) => String(r.portfolio || "未分组"), rows, totalPnl),
    by_source: aggBy((r) => String(r.source || "Ledger"), rows, totalPnl),
    by_bond_name: aggBy(
      (r) => String(r.bond_name || r.asset_code || "未命名"),
      fiRows,
      fiTotalPnl || 1,
    ),
    by_asset_class_nonstd: aggBy((r) => String(r.asset_class || "未分类"), nonstdRows, nonstdTotalPnl || 1),
    by_asset_type: aggBy((r) => String(r.asset_type || "非标投资"), rows, totalPnl),
  };
}
