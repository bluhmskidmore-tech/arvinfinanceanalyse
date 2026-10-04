// Sector rank rows, sector views and sector heavyweight preview for the stock-analysis page model.
import type { LivermoreSectorRankSeriesPoint, LivermoreStrategyPayload } from "../../../api/contracts";
import type { StockDetailSource } from "./stockAnalysisDetailSelection";
import type {
  StockSectorHeavyweightPreviewSummary,
  StockSectorHeavyweightStockPreview,
  StockSectorOverviewState,
  StockSectorRow,
  StockSectorViewKind,
  StockSectorViewRow,
} from "./stockAnalysisPageModel.types";
import { formatNumber, formatPercent, formatRatioAsPercent } from "./stockAnalysisPageModel.format";
import { finiteNumber, sectorHeavyweightSourceLabel } from "./stockAnalysisPageModel.shared";
import { buildCandidateReviewQueue } from "./stockAnalysisPageModel.candidates";

function numericFromDisplay(formatted: string): number | null {
  const n = Number.parseFloat(formatted);
  return Number.isFinite(n) ? n : null;
}

function metricValueForView(row: StockSectorRow, view: StockSectorViewKind): number | null {
  switch (view) {
    case "score":
      return row.scoreValue;
    case "pctchange":
      return row.pctChangeValue;
    case "turnover":
      return row.turnoverValue;
    case "amplitude":
      return row.amplitudeValue;
    default:
      return row.scoreValue;
  }
}

function sectorHeavyweightDetailSource(source: string): StockDetailSource {
  const sources: Record<string, StockDetailSource> = {
    theme_breakout: "theme_breakout",
    livermore: "livermore",
    fresh_trend_watchlist: "fresh_trend_watchlist",
    factor_screen: "factor_screen",
    hybrid_fusion: "hybrid_fusion",
    mean_reversion: "mean_reversion",
    review_queue: "review_queue",
    sector_constituent: "sector_constituent",
  };
  return sources[source] ?? "source_unconfirmed";
}

export function buildSectorHeavyweightPreview(
  payload: LivermoreStrategyPayload,
  options?: { sectorLimit?: number; stocksPerSector?: number },
): StockSectorHeavyweightPreviewSummary {
  const sectorLimit = options?.sectorLimit ?? 8;
  const stocksPerSector = options?.stocksPerSector ?? 3;
  const sectorRows = buildSectorRows(payload).slice(0, sectorLimit);
  if (sectorRows.length === 0) {
    return {
      rows: [],
      sectorLimit,
      sectorsWithSamples: 0,
      totalSampleCount: 0,
      uncoveredSectorCount: 0,
    };
  }

  // Display-only fill order when backend leader_constituents is short.
  // Uses discrete source priority + backend rank only — no invented composite score.
  const SOURCE_FILL_PRIORITY: Record<string, number> = {
    theme_breakout: 80,
    review_queue: 70,
    livermore: 50,
    hybrid_fusion: 40,
    fresh_trend_watchlist: 30,
    factor_screen: 20,
    mean_reversion: 10,
  };

  type PoolEntry = {
    stockCode: string;
    stockName: string;
    sectorCode: string;
    sectorName: string;
    pctChangeValue: number | null;
    turnValue: number | null;
    closeStrengthValue: number | null;
    factorScoreValue: number | null;
    /** Higher = prefer when filling preview slots (source tier, then better backend rank). */
    fillOrder: number;
    source: string;
  };

  const pool = new Map<string, PoolEntry>();

  function upsert(entry: PoolEntry) {
    const key = `${entry.sectorCode}:${entry.stockCode}`;
    const existing = pool.get(key);
    if (!existing || entry.fillOrder > existing.fillOrder) {
      pool.set(key, entry);
    }
  }

  function fillOrderFor(source: string, rank: number | null | undefined): number {
    const tier = SOURCE_FILL_PRIORITY[source] ?? 0;
    const backendRank = rank != null && Number.isFinite(rank) ? rank : 9999;
    return tier * 10_000 - backendRank;
  }

  for (const item of payload.theme_breakout?.items ?? []) {
    for (const stock of item.items) {
      const pctChangeValue = finiteNumber(stock.pctchange);
      const turnValue = finiteNumber(stock.turn);
      upsert({
        stockCode: stock.stock_code,
        stockName: stock.stock_name,
        sectorCode: stock.sector_code,
        sectorName: stock.sector_name,
        pctChangeValue,
        turnValue,
        closeStrengthValue: finiteNumber(stock.close_strength),
        factorScoreValue: null,
        fillOrder: fillOrderFor(
          "theme_breakout",
          stock.strong || stock.closed_up_limit ? 1 : 50,
        ),
        source: "theme_breakout",
      });
    }
  }

  for (const stock of payload.stock_candidates?.items ?? []) {
    const turnValue = finiteNumber(stock.abnormal_turnover);
    const closeStrengthValue = finiteNumber(stock.close_strength);
    upsert({
      stockCode: stock.stock_code,
      stockName: stock.stock_name,
      sectorCode: stock.sector_code,
      sectorName: stock.sector_name,
      pctChangeValue: null,
      turnValue,
      closeStrengthValue,
      factorScoreValue: null,
      fillOrder: fillOrderFor("livermore", stock.rank),
      source: "livermore",
    });
  }

  for (const stock of payload.fresh_trend_watchlist?.items ?? []) {
    const pctChangeValue = finiteNumber(stock.pctchange);
    const turnValue = finiteNumber(stock.turn);
    const closeToMa20Value = finiteNumber(stock.close_to_ma20);
    const scoreValue = finiteNumber(stock.score);
    upsert({
      stockCode: stock.stock_code,
      stockName: stock.stock_name,
      sectorCode: stock.sector_code,
      sectorName: stock.sector_name,
      pctChangeValue,
      turnValue,
      closeStrengthValue: closeToMa20Value,
      factorScoreValue: scoreValue,
      fillOrder: fillOrderFor("fresh_trend_watchlist", stock.rank),
      source: "fresh_trend_watchlist",
    });
  }

  for (const stock of payload.hybrid_fusion_candidates?.items ?? []) {
    upsert({
      stockCode: stock.stock_code,
      stockName: stock.stock_name,
      sectorCode: stock.sector_code,
      sectorName: stock.sector_name,
      pctChangeValue: null,
      turnValue: null,
      closeStrengthValue: null,
      factorScoreValue: null,
      fillOrder: fillOrderFor("hybrid_fusion", stock.rank),
      source: "hybrid_fusion",
    });
  }

  for (const stock of payload.factor_screen_candidates?.items ?? []) {
    const factorScoreValue = finiteNumber(stock.score);
    upsert({
      stockCode: stock.stock_code,
      stockName: stock.stock_name,
      sectorCode: stock.sector_code,
      sectorName: stock.sector_name,
      pctChangeValue: null,
      turnValue: null,
      closeStrengthValue: null,
      factorScoreValue,
      fillOrder: fillOrderFor("factor_screen", stock.rank),
      source: "factor_screen",
    });
  }

  for (const stock of payload.mean_reversion_candidates?.items ?? []) {
    upsert({
      stockCode: stock.stock_code,
      stockName: stock.stock_name,
      sectorCode: stock.sector_code,
      sectorName: stock.sector_name,
      pctChangeValue: null,
      turnValue: null,
      closeStrengthValue: null,
      factorScoreValue: finiteNumber(stock.score),
      fillOrder: fillOrderFor("mean_reversion", stock.rank),
      source: "mean_reversion",
    });
  }

  for (const card of buildCandidateReviewQueue(payload)) {
    upsert({
      stockCode: card.stockCode,
      stockName: card.stockName,
      sectorCode: card.sectorCode,
      sectorName: card.sectorName,
      pctChangeValue: null,
      turnValue: null,
      closeStrengthValue: null,
      factorScoreValue: null,
      fillOrder: fillOrderFor("review_queue", card.rank),
      source: "review_queue",
    });
  }

  const leaderBySector = new Map(
    (payload.sector_rank?.items ?? []).map((item) => [item.sector_code, item.leader_constituents ?? []]),
  );

  function mapPoolEntryToPreview(entry: PoolEntry): StockSectorHeavyweightStockPreview {
    return {
      stockCode: entry.stockCode,
      stockName: entry.stockName,
      pctChange: entry.pctChangeValue != null ? formatPercent(entry.pctChangeValue) : "待补",
      turn: entry.turnValue != null ? formatNumber(entry.turnValue, 2) : "待补",
      closeStrength:
        entry.closeStrengthValue != null ? formatRatioAsPercent(entry.closeStrengthValue, 0) : "待补",
      sourceLabel: sectorHeavyweightSourceLabel(entry.source),
      detailSource: sectorHeavyweightDetailSource(entry.source),
      detailLabel:
        entry.source === "factor_screen" && entry.factorScoreValue != null
          ? `因子分 ${formatNumber(entry.factorScoreValue, 4)}`
          : entry.source === "mean_reversion" && entry.factorScoreValue != null
            ? `超跌分 ${formatNumber(entry.factorScoreValue, 2)}`
            : undefined,
    };
  }

  const rows = sectorRows.map((sector) => {
    const backendLeaders = leaderBySector.get(sector.sectorCode) ?? [];
    const usedCodes = new Set<string>();
    const stocks: StockSectorHeavyweightStockPreview[] = backendLeaders
      .slice(0, stocksPerSector)
      .map((leader) => {
        usedCodes.add(leader.stock_code);
        return {
          stockCode: leader.stock_code,
          stockName: leader.stock_name,
          pctChange: formatPercent(leader.pctchange),
          turn: formatNumber(leader.turn, 2),
          closeStrength: "待补",
          sourceLabel: sectorHeavyweightSourceLabel("sector_constituent"),
          detailSource: sectorHeavyweightDetailSource("sector_constituent"),
          auxiliaryLabel: `振幅 ${formatPercent(leader.amplitude)}`,
        };
      });

    if (stocks.length < stocksPerSector) {
      const supplemental = [...pool.values()]
        .filter((entry) => entry.sectorCode === sector.sectorCode && !usedCodes.has(entry.stockCode))
        .sort((left, right) => right.fillOrder - left.fillOrder)
        .slice(0, stocksPerSector - stocks.length)
        .map(mapPoolEntryToPreview);
      stocks.push(...supplemental);
    }

    return {
      sectorCode: sector.sectorCode,
      sectorName: sector.sectorName,
      sectorRank: sector.rank,
      sectorPctChange: sector.pctChange,
      sectorScore: sector.score,
      stocks,
      emptyReason:
        stocks.length === 0
          ? "板块成分与策略/题材观察池均未命中（请检查 sector_rank 供数）"
          : undefined,
    };
  });

  const sectorsWithSamples = rows.filter((row) => row.stocks.length > 0).length;
  const totalSampleCount = rows.reduce((count, row) => count + row.stocks.length, 0);

  return {
    rows,
    sectorLimit,
    sectorsWithSamples,
    totalSampleCount,
    uncoveredSectorCount: rows.length - sectorsWithSamples,
  };
}

export function buildSectorRows(payload: LivermoreStrategyPayload): StockSectorRow[] {
  const items = [...(payload.sector_rank?.items ?? [])].sort((left, right) => left.rank - right.rank);
  const n = items.length;
  const scores = items
    .map((i) => i.score)
    .filter((s): s is number => s != null && Number.isFinite(s));
  const maxScore = scores.length ? Math.max(...scores) : 0;
  const pctAbs = items
    .map((i) => (i.avg_pctchange != null && Number.isFinite(i.avg_pctchange) ? Math.abs(i.avg_pctchange) : 0))
    .filter(Boolean);
  const maxPctAbs = pctAbs.length ? Math.max(...pctAbs) : 0;

  return items.map((item) => {
    const scoreNum = item.score;
    const scoreVal = scoreNum != null && Number.isFinite(scoreNum) ? scoreNum : null;
    const scoreNormalized =
      maxScore > 0 && scoreVal != null ? Math.min(1, Math.max(0, scoreVal / maxScore)) : 0;

    const pctRaw = item.avg_pctchange;
    const pctVal = pctRaw != null && Number.isFinite(pctRaw) ? pctRaw : null;

    let pctBar = 0;
    if (pctVal != null) {
      if (maxPctAbs > 0) {
        pctBar = (Math.abs(pctVal) / maxPctAbs) * 100;
      } else if (pctVal !== 0) {
        pctBar = 50;
      }
    }

    return {
      rank: item.rank,
      sectorCode: item.sector_code,
      sectorName: item.sector_name,
      score: formatNumber(scoreVal, 3),
      pctChange: formatPercent(pctVal ?? undefined),
      turnover: formatNumber(item.avg_turn, 2),
      amplitude: formatPercent(item.avg_amplitude),
      constituentCount: item.constituent_count,
      scoreValue: scoreVal,
      pctChangeValue: pctVal,
      turnoverValue: item.avg_turn != null && Number.isFinite(item.avg_turn) ? item.avg_turn : null,
      amplitudeValue:
        item.avg_amplitude != null && Number.isFinite(item.avg_amplitude) ? item.avg_amplitude : null,
      scoreNormalized,
      pctChangeBar: pctBar,
      isTop: n > 0 && item.rank <= 5,
      isBottom: n > 0 && item.rank >= n - 4,
    };
  });
}

export function buildSectorRowsFromSectorSeries(
  rows: LivermoreSectorRankSeriesPoint[],
): StockSectorRow[] {
  const items = [...rows].sort((left, right) => {
    const leftRank = finiteNumber(left.rank) ?? 9999;
    const rightRank = finiteNumber(right.rank) ?? 9999;
    if (leftRank !== rightRank) return leftRank - rightRank;
    return left.sector_code.localeCompare(right.sector_code);
  });
  const n = items.length;
  const scores = items
    .map((item) => finiteNumber(item.score))
    .filter((score): score is number => score != null);
  const maxScore = scores.length ? Math.max(...scores) : 0;
  const pctAbs = items
    .map((item) => finiteNumber(item.avg_pctchange))
    .filter((value): value is number => value != null)
    .map((value) => Math.abs(value))
    .filter(Boolean);
  const maxPctAbs = pctAbs.length ? Math.max(...pctAbs) : 0;

  return items.map((item, index) => {
    const rank = finiteNumber(item.rank) ?? index + 1;
    const scoreVal = finiteNumber(item.score);
    const pctVal = finiteNumber(item.avg_pctchange);
    const turnoverVal = finiteNumber(item.avg_turn);
    const amplitudeVal = finiteNumber(item.avg_amplitude);
    const constituentCount = finiteNumber(item.constituent_count) ?? 0;
    const scoreNormalized =
      maxScore > 0 && scoreVal != null ? Math.min(1, Math.max(0, scoreVal / maxScore)) : 0;

    let pctBar = 0;
    if (pctVal != null) {
      if (maxPctAbs > 0) {
        pctBar = (Math.abs(pctVal) / maxPctAbs) * 100;
      } else if (pctVal !== 0) {
        pctBar = 50;
      }
    }

    return {
      rank,
      sectorCode: item.sector_code,
      sectorName: item.sector_name,
      score: formatNumber(scoreVal, 3),
      pctChange: formatPercent(pctVal),
      turnover: formatNumber(turnoverVal, 2),
      amplitude: formatPercent(amplitudeVal),
      constituentCount,
      scoreValue: scoreVal,
      pctChangeValue: pctVal,
      turnoverValue: turnoverVal,
      amplitudeValue: amplitudeVal,
      scoreNormalized,
      pctChangeBar: pctBar,
      isTop: n > 0 && rank <= 5,
      isBottom: n > 0 && rank >= n - 4,
    };
  });
}

export function buildStockSectorOverviewState<TRow extends StockSectorRow>(
  rows: TRow[],
): StockSectorOverviewState<TRow> {
  return {
    leaderRow: rows[0] ?? null,
    tailRow: rows.length > 0 ? rows[rows.length - 1] : null,
    coverageCount: rows.reduce((sum, row) => sum + row.constituentCount, 0),
    topBars: rows.slice(0, 5),
    bottomBars: rows.slice(Math.max(rows.length - 5, 0)),
  };
}

export function buildSectorViewRows(
  rows: StockSectorRow[],
  view: StockSectorViewKind,
): StockSectorViewRow[] {
  const sorted = [...rows].sort((a, b) => {
    const av = metricValueForView(a, view);
    const bv = metricValueForView(b, view);
    if (av == null && bv == null) return a.rank - b.rank;
    if (av == null) return 1;
    if (bv == null) return -1;
    if (bv !== av) return bv - av;
    return a.rank - b.rank;
  });
  const values = sorted
    .map((r) => metricValueForView(r, view))
    .filter((v): v is number => v != null && Number.isFinite(v));
  let maxMag = values.length ? Math.max(...values.map((v) => Math.abs(v))) : 0;
  if (!(maxMag > 0)) maxMag = 1;
  return sorted.map((row) => {
    const v = metricValueForView(row, view);
    let metricBarNormalized = 0;
    if (v != null && Number.isFinite(v)) {
      metricBarNormalized = Math.min(1, Math.max(0, Math.abs(v) / maxMag));
    }
    return {
      ...row,
      metricBarNormalized,
    };
  });
}

export function buildSectorTableSortComparator(
  key: keyof StockSectorRow | "code" | "name" | "pctchange",
  order: "ascend" | "descend",
) {
  return (a: StockSectorRow, b: StockSectorRow) => {
    const sign = order === "ascend" ? 1 : -1;
    const num = (
      ai: StockSectorRow,
      bi: StockSectorRow,
      pick: (r: StockSectorRow) => number | null | undefined,
    ) => {
      const av = pick(ai);
      const bv = pick(bi);
      if ((av == null || !Number.isFinite(av)) && (bv == null || !Number.isFinite(bv))) return 0;
      if (av == null || !Number.isFinite(av)) return 1;
      if (bv == null || !Number.isFinite(bv)) return -1;
      if (av === bv) return 0;
      return av > bv ? sign : -sign;
    };

    switch (key) {
      case "rank":
        return num(a, b, (r) => r.rank);
      case "sectorCode":
        return sign * a.sectorCode.localeCompare(b.sectorCode, "zh-Hans-CN");
      case "sectorName":
      case "name":
        return sign * a.sectorName.localeCompare(b.sectorName, "zh-Hans-CN");
      case "score":
        return num(a, b, (r) => r.scoreValue ?? numericFromDisplay(r.score));
      case "pctChange":
      case "pctchange":
        return num(a, b, (r) => r.pctChangeValue ?? Number.NaN);
      case "turnover":
        return num(a, b, (r) => r.turnoverValue ?? numericFromDisplay(r.turnover));
      case "amplitude":
        return num(a, b, (r) => r.amplitudeValue ?? Number.NaN);
      case "constituentCount":
        return num(a, b, (r) => r.constituentCount);
      default:
        return a.rank - b.rank;
    }
  };
}
