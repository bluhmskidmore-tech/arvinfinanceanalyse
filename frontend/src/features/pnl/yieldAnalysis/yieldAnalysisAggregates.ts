import type { PnlV1DetailRow } from "../../../api/contracts";
import type { RankingBarRow } from "./RankingBarsCard";

function parseYuan(value: string | number | null | undefined): number | null {
  if (value === null || value === undefined || value === "") {
    return null;
  }
  const n = Number(String(value).replace(/,/g, ""));
  return Number.isFinite(n) ? n : null;
}

function addMoney(total: number, value: string | number | null | undefined): number {
  const parsed = parseYuan(value);
  if (parsed === null || Number.isNaN(total)) {
    return Number.NaN;
  }
  return total + parsed;
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
    cur.interest_income = addMoney(cur.interest_income, r.interest_income);
    cur.fair_value_change = addMoney(cur.fair_value_change, r.fair_value_change);
    cur.capital_gain = addMoney(cur.capital_gain, r.capital_gain);
    cur.total_pnl = addMoney(cur.total_pnl, r.total_pnl);
    m.set(key, cur);
  }
  return Array.from(m.values())
    .map((x) => ({
      ...x,
      proportion:
        Number.isFinite(baseTotal) && baseTotal !== 0 && Number.isFinite(x.total_pnl)
          ? x.total_pnl / baseTotal
          : null,
    }))
    .sort((a, b) => {
      const left = Number.isFinite(a.total_pnl) ? Math.abs(a.total_pnl) : -1;
      const right = Number.isFinite(b.total_pnl) ? Math.abs(b.total_pnl) : -1;
      return right - left;
    });
}

export function buildYieldAnalysisAggregates(rows: PnlV1DetailRow[]) {
  const totalPnl = rows.reduce((s, r) => addMoney(s, r.total_pnl), 0);
  const nonstdRows = rows.filter((r) => r.source === "NonStd");
  const nonstdTotalPnl = nonstdRows.reduce((s, r) => addMoney(s, r.total_pnl), 0);
  const fiRows = rows.filter((r) => r.source !== "NonStd");
  const fiTotalPnl = fiRows.reduce((s, r) => addMoney(s, r.total_pnl), 0);

  return {
    by_portfolio: aggBy((r) => String(r.portfolio || "未分组"), rows, totalPnl),
    by_source: aggBy((r) => String(r.source || "Ledger"), rows, totalPnl),
    by_bond_name: aggBy((r) => String(r.bond_name || r.asset_code || "未命名"), fiRows, fiTotalPnl),
    by_asset_class_nonstd: aggBy((r) => String(r.asset_class || "未分类"), nonstdRows, nonstdTotalPnl),
    by_asset_type: aggBy((r) => String(r.asset_type || "非标投资"), rows, totalPnl),
  };
}
