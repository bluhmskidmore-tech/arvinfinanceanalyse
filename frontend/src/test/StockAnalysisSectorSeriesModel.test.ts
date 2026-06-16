import { describe, expect, it } from "vitest";

import type { LivermoreSectorRankSeriesPoint } from "../api/contracts";
import {
  buildSectorSeriesTrendLines,
  formatSectorSeriesCumPctChange,
  formatSectorSeriesScore,
  latestSectorSeriesTableRows,
  localizeSectorSeriesUnsupportedNotes,
  sectorRankUnavailable,
} from "../features/stock-analysis/lib/stockAnalysisSectorSeriesModel";

const basePoint: LivermoreSectorRankSeriesPoint = {
  trade_date: "2026-04-29",
  sector_code: "BK001",
  sector_name: "半导体",
  score: 0.82,
  rank: 2,
  avg_pctchange: 1.2,
  avg_turn: 3.4,
  avg_amplitude: 5.6,
  constituent_count: 24,
  cum_pctchange_window: 2.3,
};

describe("stockAnalysisSectorSeriesModel", () => {
  it("marks sector rank unavailable when formula or items are missing", () => {
    expect(sectorRankUnavailable(null)).toBe(true);
    expect(sectorRankUnavailable({ sector_rank: { formula_version: "", items: [basePoint] } })).toBe(true);
    expect(sectorRankUnavailable({ sector_rank: { formula_version: "   ", items: [basePoint] } })).toBe(true);
    expect(sectorRankUnavailable({ sector_rank: { formula_version: "v1", items: [] } })).toBe(true);
    expect(sectorRankUnavailable({ sector_rank: { formula_version: "v1", items: [basePoint] } })).toBe(false);
  });

  it("keeps the latest row per sector and sorts unavailable ranks to the bottom", () => {
    const rows = latestSectorSeriesTableRows([
      {
        ...basePoint,
        trade_date: "2026-04-28",
        sector_code: "BK001",
        sector_name: "半导体旧",
        rank: 1,
      },
      {
        ...basePoint,
        sector_code: "BK002",
        sector_name: "新能源",
        rank: null,
      },
      {
        ...basePoint,
        trade_date: "2026-04-30",
        sector_code: "BK001",
        sector_name: "半导体新",
        rank: 3,
      },
      {
        ...basePoint,
        sector_code: "BK003",
        sector_name: "银行",
        rank: 1,
      },
    ]);

    expect(rows.map((row) => `${row.sector_code}:${row.sector_name}:${row.rank ?? "NA"}`)).toEqual([
      "BK003:银行:1",
      "BK001:半导体新:3",
      "BK002:新能源:NA",
    ]);
  });

  it("builds top sector trend lines ordered by latest rank", () => {
    const lines = buildSectorSeriesTrendLines(
      [
        { ...basePoint, trade_date: "2026-04-28", sector_code: "BK001", score: 0.7, rank: 2 },
        { ...basePoint, trade_date: "2026-04-29", sector_code: "BK001", score: 0.82, rank: 1 },
        { ...basePoint, trade_date: "2026-04-28", sector_code: "BK002", sector_name: "新能源", score: 0.5, rank: 3 },
        { ...basePoint, trade_date: "2026-04-29", sector_code: "BK002", sector_name: "新能源", score: 0.55, rank: 2 },
      ],
      2,
    );

    expect(lines).toHaveLength(2);
    expect(lines[0]).toMatchObject({
      sectorCode: "BK001",
      sectorName: "半导体",
      dates: ["2026-04-28", "2026-04-29"],
      scores: [0.7, 0.82],
    });
    expect(lines[1].sectorCode).toBe("BK002");
  });

  it("localizes unsupported notes and formats series metrics", () => {
    expect(
      localizeSectorSeriesUnsupportedNotes([
        "momentum_persistence: needs metric definition review (P1)",
        "sector_money_flow: needs vendor approval & new schema (P1)",
      ]),
    ).toEqual(["动量持续度：口径待评审（P1）", "板块资金流向：待 vendor 审批与新 schema（P1）"]);
    expect(formatSectorSeriesScore(0.8123)).toBe("0.8123");
    expect(formatSectorSeriesCumPctChange(2.35)).toBe("+2.35%");
    expect(formatSectorSeriesCumPctChange(null)).toBe("-");
  });
});
