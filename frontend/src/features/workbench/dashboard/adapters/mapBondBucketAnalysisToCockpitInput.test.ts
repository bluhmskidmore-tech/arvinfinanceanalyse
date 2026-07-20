import { describe, expect, it, vi } from "vitest";

import type {
  ApiEnvelope,
  BondPortfolioHeadlinesPayload,
  Numeric,
  PnlByBusinessAnalysisPayload,
  PnlByBusinessAnalysisRow,
  ResultMeta,
} from "../../../../api/contracts";
import { buildDashboardCockpitModel } from "../dashboardCockpitModel";
import { getBondBucketYield } from "../services/dashboardApi";
import { mapBondBucketAnalysisToCockpitInput } from "./mapBondBucketAnalysisToCockpitInput";

function numeric(display: string, raw = 1): Numeric {
  return {
    raw,
    unit: "ratio",
    display,
    precision: 2,
    sign_aware: false,
  };
}

function analysisRow(
  overrides: Partial<PnlByBusinessAnalysisRow> &
    Pick<PnlByBusinessAnalysisRow, "dimension_key" | "dimension_label" | "annualized_yield_pct">,
): PnlByBusinessAnalysisRow {
  return {
    interest_income: "0",
    fair_value_change: "0",
    capital_gain: "0",
    manual_adjustment: "0",
    total_pnl: "0",
    avg_balance: "1000",
    current_balance: "1000",
    ftp_rate_pct: "1.6",
    ftp_cost: "0",
    ftp_net_pnl: "0",
    ftp_net_annualized_yield_pct: "0",
    asset_count: 1,
    ...overrides,
  };
}

function bondBucketPayload(
  overrides: Partial<PnlByBusinessAnalysisPayload> = {},
): PnlByBusinessAnalysisPayload {
  return {
    year: 2026,
    as_of_date: "2026-04-30",
    business_key: null,
    dimension: "bond_bucket",
    period_start_date: "2026-01-01",
    period_end_date: "2026-04-30",
    source_tables: ["fact_formal_pnl_fi"],
    rows: [
      analysisRow({
        dimension_key: "credit_bond",
        dimension_label: "信用债",
        annualized_yield_pct: "98.500000",
      }),
      analysisRow({
        dimension_key: "rate_bond",
        dimension_label: "利率债",
        annualized_yield_pct: "117.741935",
      }),
      analysisRow({
        dimension_key: "financial_bond",
        dimension_label: "金融债",
        annualized_yield_pct: "73.000000",
      }),
      analysisRow({
        dimension_key: "other_bond",
        dimension_label: "其它债券",
        annualized_yield_pct: "36.500000",
        avg_balance: "2000",
      }),
    ],
    merged_bucket_rows: [
      analysisRow({
        dimension_key: "other_merged",
        dimension_label: "其他",
        // Distinct from the old frontend weighted recompute (58.40).
        annualized_yield_pct: "43.800000",
        avg_balance: "3000",
      }),
    ],
    ...overrides,
  };
}

function portfolioWithOther(): BondPortfolioHeadlinesPayload {
  return {
    report_date: "2026-04-30",
    total_market_value: numeric("3,438.23 亿"),
    weighted_ytm: numeric("2.57%"),
    weighted_duration: numeric("4.14"),
    weighted_coupon: numeric("2.07%"),
    total_dv01: numeric("106,155,944", 106_155_944.31),
    bond_count: 1740,
    credit_weight: numeric("29.25%"),
    issuer_hhi: numeric("5.09%"),
    issuer_top5_weight: numeric("41.35%"),
    by_asset_class: [
      {
        asset_class: "credit",
        market_value: numeric("1,005.70 亿"),
        duration: numeric("2.40"),
        dv01: numeric("23,572,093", 23_572_092.66),
        weight: numeric("29.25%"),
      },
      {
        asset_class: "rate",
        market_value: numeric("1,344.90 亿"),
        duration: numeric("5.63"),
        dv01: numeric("73,667,216", 73_667_216.08),
        weight: numeric("39.12%"),
      },
      {
        asset_class: "other",
        market_value: numeric("100.00 亿"),
        duration: numeric("1.20"),
        dv01: numeric("1,000,000", 1_000_000),
        weight: numeric("2.91%"),
      },
    ],
    warnings: [],
    computed_at: "2026-05-10T00:00:00Z",
  };
}

describe("mapBondBucketAnalysisToCockpitInput", () => {
  it("passes merged_bucket_rows through as bondBucketMergedRows", () => {
    const payload = bondBucketPayload();
    const mapped = mapBondBucketAnalysisToCockpitInput(payload);

    expect(mapped.bondBucketRows).toBe(payload.rows);
    expect(mapped.bondBucketMergedRows).toBe(payload.merged_bucket_rows);
    expect(mapped.bondBucketMergedRows?.[0]).toMatchObject({
      dimension_key: "other_merged",
      annualized_yield_pct: "43.800000",
    });
  });

  it("returns null merged rows when the backend field is absent", () => {
    const { merged_bucket_rows: _omit, ...withoutMerged } = bondBucketPayload();
    void _omit;
    const mapped = mapBondBucketAnalysisToCockpitInput(withoutMerged);

    expect(mapped.bondBucketRows).toHaveLength(4);
    expect(mapped.bondBucketMergedRows).toBeNull();
  });

  it("wires getBondBucketYield payload into cockpit other-bucket ytm without local recompute", async () => {
    const payload = bondBucketPayload();
    const envelope = {
      result_meta: {
        result_kind: "pnl.by_business_analysis",
        basis: "analytical",
        formal_use_allowed: false,
      } as ResultMeta,
      result: payload,
    } satisfies ApiEnvelope<PnlByBusinessAnalysisPayload>;
    const getPnlByBusinessAnalysis = vi.fn(async () => envelope);
    const client = { getPnlByBusinessAnalysis } as unknown as Parameters<
      typeof getBondBucketYield
    >[0];

    const response = await getBondBucketYield(client, "2026-04-30", 2026);
    const mapped = mapBondBucketAnalysisToCockpitInput(response.result);

    const model = buildDashboardCockpitModel({
      reportDate: "2026-04-30",
      snapshotMode: "strict",
      isMockMode: false,
      portfolio: portfolioWithOther(),
      ...mapped,
      marketPoints: [],
      calendarItems: [],
    });

    expect(getPnlByBusinessAnalysis).toHaveBeenCalledWith({
      year: 2026,
      asOfDate: "2026-04-30",
      dimension: "bond_bucket",
    });
    // Backend merged annualized yield (43.80%), not local weighted 58.40%.
    expect(model.accountRows.find((row) => row.id === "account-other")).toMatchObject({
      ytm: "43.80%",
    });
  });
});
