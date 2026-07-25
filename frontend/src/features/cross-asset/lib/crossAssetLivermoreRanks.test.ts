import { describe, expect, it } from "vitest";

import type {
  FactorScreenCandidatesPayload,
  LivermoreSectorRankPayload,
} from "../../../api/contracts";
import {
  buildLivermoreFactorCandidateRows,
  buildLivermoreSectorRankRows,
} from "./crossAssetLivermoreRanks";

function makeSectorRankPayload(itemCount: number): LivermoreSectorRankPayload {
  return {
    as_of_date: "2026-07-22",
    formula_version: "sector_rank_v1",
    is_provisional: true,
    formula_note: "暂定公式",
    sector_count: 31,
    excluded_constituent_count: 0,
    excluded_sector_count: 0,
    items: Array.from({ length: itemCount }, (_, index) => ({
      rank: index + 1,
      sector_code: `S${String(index + 1).padStart(3, "0")}`,
      sector_name: index === 0 ? "煤炭" : `行业${index + 1}`,
      score: 0.94 - index * 0.01,
      avg_pctchange: 2.94 - index * 0.1,
      avg_turn: 3.5,
      avg_amplitude: 4.2,
      constituent_count: 33,
      leader_constituents: [
        { rank: 1, stock_code: "600403.SH", stock_name: "大有能源", pctchange: 10.04, turn: 5.1, amplitude: 6.2 },
        { rank: 2, stock_code: "600121.SH", stock_name: "郑州煤电", pctchange: 7.07, turn: 4.3, amplitude: 5.5 },
        { rank: 3, stock_code: "000000.SZ", stock_name: "第三名不应出现", pctchange: 5.0, turn: 3.0, amplitude: 4.0 },
      ],
    })),
  };
}

function makeFactorCandidatesPayload(itemCount: number): FactorScreenCandidatesPayload {
  return {
    as_of_date: "2026-07-22",
    formula_version: "factor_screen_v1",
    market_state: "WARM",
    observation_only: true,
    input_stock_count: 5200,
    candidate_count: 30,
    coverage_note: "覆盖口径说明",
    items: Array.from({ length: itemCount }, (_, index) => ({
      rank: index + 1,
      stock_code: index === 0 ? "000651.SZ" : `00000${index}.SZ`,
      stock_name: index === 0 ? "格力电器" : `股票${index + 1}`,
      sector_code: "S01",
      sector_name: "家用电器",
      industry: "白色家电",
      score: 0.81 - index * 0.01,
      pe: 7.9,
      pb: 1.8,
      roe: 0.2,
      gross_margin: 0.3,
      three_month_return: 0.105,
      twelve_month_return: 0.25,
      dividend_yield: 0.04,
    })),
  };
}

describe("buildLivermoreSectorRankRows", () => {
  it("maps real payload fields and takes top 2 leader names", () => {
    const { rows, meta } = buildLivermoreSectorRankRows(makeSectorRankPayload(31));
    expect(rows).toHaveLength(12);
    expect(rows[0]).toEqual({
      rank: 1,
      sectorName: "煤炭",
      score: 0.94,
      avgPctChange: 2.94,
      constituentCount: 33,
      leaderNames: ["大有能源", "郑州煤电"],
    });
    expect(meta).toEqual({
      asOfDate: "2026-07-22",
      sectorCount: 31,
      isProvisional: true,
      formulaVersion: "sector_rank_v1",
    });
  });

  it("respects the limit parameter", () => {
    const { rows } = buildLivermoreSectorRankRows(makeSectorRankPayload(31), 5);
    expect(rows).toHaveLength(5);
    expect(rows[4].rank).toBe(5);
  });

  it("handles missing leaders and null numerics", () => {
    const payload = makeSectorRankPayload(1);
    payload.items[0].leader_constituents = undefined;
    payload.items[0].score = Number.NaN;
    payload.items[0].avg_pctchange = null as unknown as number;
    const { rows } = buildLivermoreSectorRankRows(payload);
    expect(rows[0].leaderNames).toEqual([]);
    expect(rows[0].score).toBeNull();
    expect(rows[0].avgPctChange).toBeNull();
  });

  it("returns empty rows with safe meta for empty input", () => {
    const { rows, meta } = buildLivermoreSectorRankRows(null);
    expect(rows).toEqual([]);
    expect(meta).toEqual({
      asOfDate: "—",
      sectorCount: 0,
      isProvisional: false,
      formulaVersion: "—",
    });
  });
});

describe("buildLivermoreFactorCandidateRows", () => {
  it("maps real payload fields and multiplies three_month_return by 100", () => {
    const { rows, meta } = buildLivermoreFactorCandidateRows(makeFactorCandidatesPayload(30));
    expect(rows).toHaveLength(10);
    expect(rows[0]).toEqual({
      rank: 1,
      stockCode: "000651.SZ",
      stockName: "格力电器",
      sectorName: "家用电器",
      score: 0.81,
      pe: 7.9,
      threeMonthReturnPct: 10.5,
    });
    expect(meta).toEqual({
      asOfDate: "2026-07-22",
      candidateCount: 30,
      inputStockCount: 5200,
      observationOnly: true,
    });
  });

  it("respects the limit parameter", () => {
    const { rows } = buildLivermoreFactorCandidateRows(makeFactorCandidatesPayload(30), 3);
    expect(rows).toHaveLength(3);
  });

  it("keeps threeMonthReturnPct null when the raw return is missing", () => {
    const payload = makeFactorCandidatesPayload(1);
    payload.items[0].three_month_return = null;
    const { rows } = buildLivermoreFactorCandidateRows(payload);
    expect(rows[0].threeMonthReturnPct).toBeNull();
  });

  it("passes observation_only through and defaults safely on empty input", () => {
    expect(buildLivermoreFactorCandidateRows(makeFactorCandidatesPayload(1)).meta.observationOnly).toBe(true);
    const { rows, meta } = buildLivermoreFactorCandidateRows(undefined);
    expect(rows).toEqual([]);
    expect(meta).toEqual({
      asOfDate: "—",
      candidateCount: 0,
      inputStockCount: 0,
      observationOnly: false,
    });
  });
});
