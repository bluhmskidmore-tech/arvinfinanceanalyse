import { describe, expect, it } from "vitest";

import type {
  BondDashboardHeadlinePayload,
  BondPortfolioHeadlinesPayload,
  Numeric,
  ResultMeta,
  VerdictPayload,
} from "../../../api/contracts";
import type { HomeSnapshotOverviewMetricVM } from "./dashboardHomeSnapshotAdapter";
import {
  mapToHomeFirstScreenView,
  mapToHomeFirstScreenHydration,
  VERDICT_REASON_SEPARATOR,
} from "./dashboardHomeFirstScreenView";

const meta: ResultMeta = {
  trace_id: "trace-1",
  basis: "analytical",
  result_kind: "home_snapshot",
  formal_use_allowed: false,
  source_version: "v1",
  vendor_version: "v1",
  rule_version: "v1",
  cache_version: "v1",
  quality_flag: "ok",
  vendor_status: "ok",
  fallback_mode: "none",
  scenario_flag: false,
  generated_at: "2026-07-31T16:00:00",
};

const metrics: HomeSnapshotOverviewMetricVM[] = [
  {
    id: "aum",
    label: "总资产规模",
    caliberLabel: "本币资产口径",
    value: { raw: 370_538_010_245.46, unit: "yuan", display: "3,705.38 亿", precision: 2, sign_aware: false },
    delta: { raw: -0.0386, unit: "pct", display: "-3.86%", precision: 2, sign_aware: true },
    tone: "positive",
    detail: "",
    history: null,
  },
  {
    id: "yield",
    label: "年度损益（不扣FTP）",
    caliberLabel: "FI + 非标桥接",
    value: { raw: 4_856_069_979.5, unit: "yuan", display: "+48.56 亿", precision: 2, sign_aware: true },
    delta: { raw: 0.144, unit: "pct", display: "+14.40%", precision: 2, sign_aware: true },
    tone: "positive",
    detail: "",
    history: null,
  },
];

const templateVerdict: VerdictPayload = {
  conclusion: "首屏整体偏多，可基于规模与收益做方向性判断",
  tone: "positive",
  reasons: [
    {
      label: "总资产规模",
      value: "3,705.38 亿",
      detail: "来自治理资产快照，在 2026-07-31 的本币资产口径市值合计。",
      tone: "positive",
    },
  ],
  suggestions: [],
};

function build(verdict: VerdictPayload | null, kpis = metrics) {
  return mapToHomeFirstScreenView({
    reportDate: "2026-07-31",
    useMockFallback: false,
    verdict,
    metrics: kpis,
    attribution: null,
    bondHeadline: null,
    portfolio: null,
    snapshotMeta: meta,
    alertCount: 0,
    snapshotUnavailable: false,
    snapshotStale: false,
    snapshotLoading: false,
    productCategoryHeadline: { state: "ready", metrics: [] },
  });
}

describe("mapToHomeFirstScreenView decision summary", () => {
  it("replaces a templated verdict with a verifiable KPI fact sentence and adds no direction words", () => {
    const view = build(templateVerdict);

    expect(view.decisionRail.conclusion).toBe(
      "总资产规模（本币资产口径） 3,705.38 亿，年度损益（不扣FTP） +48.56 亿。",
    );
    expect(view.decisionRail.conclusion).not.toMatch(/趋势判断|待复核|偏多|偏空|方向性判断/);
  });

  it("does not fabricate a reading when the templated verdict has no KPI behind it", () => {
    const view = build(templateVerdict, []);

    expect(view.decisionRail.conclusion).toBe("当前报告日暂无经营读数");
  });

  it("passes a substantive backend conclusion through unchanged", () => {
    const view = build({
      ...templateVerdict,
      conclusion: "组合收益主要受利率上行拖累，信用利差收窄对冲了部分回撤。",
    });

    expect(view.decisionRail.conclusion).toBe(
      "组合收益主要受利率上行拖累，信用利差收窄对冲了部分回撤。",
    );
  });

  it("keeps the first reason as label · value · lineage when it does not repeat the conclusion", () => {
    const view = build({
      ...templateVerdict,
      conclusion: "组合收益主要受利率上行拖累，信用利差收窄对冲了部分回撤。",
    });

    expect(view.decisionRail.keyRisk).toBe(
      ["总资产规模", "3,705.38 亿", "来自治理资产快照，在 2026-07-31 的本币资产口径市值合计。"].join(
        VERDICT_REASON_SEPARATOR,
      ),
    );
  });
});

describe("first-screen supplemental risk display", () => {
  const numeric = (raw: number | null, unit: Numeric["unit"] = "ratio"): Numeric => ({
    raw, unit, display: raw == null ? "--" : String(raw), precision: 2, sign_aware: false,
  });
  const headline: BondDashboardHeadlinePayload = {
    report_date: "2026-07-31",
    prev_report_date: null,
    prev_kpis: null,
    kpis: {
      total_market_value: numeric(null, "yuan"),
      unrealized_pnl: numeric(null, "yuan"),
      weighted_ytm: numeric(null),
      weighted_duration: numeric(4.23),
      weighted_coupon: numeric(null),
      credit_spread_median: numeric(null, "bp"),
      total_dv01: numeric(120_000, "dv01"),
      bond_count: 0,
    },
  };
  const portfolio: BondPortfolioHeadlinesPayload = {
    report_date: "2026-07-31",
    total_market_value: numeric(null, "yuan"),
    weighted_ytm: numeric(null),
    weighted_duration: numeric(3.5),
    weighted_coupon: numeric(null),
    total_dv01: numeric(90_000, "dv01"),
    bond_count: 0,
    credit_weight: numeric(0.62),
    issuer_hhi: numeric(null),
    issuer_top5_weight: numeric(0.31),
    by_asset_class: [],
    warnings: [],
    computed_at: "2026-07-31T20:59:00",
  };
  const input = {
    reportDate: " 2026-07-31 ",
    bondHeadline: headline,
    portfolio,
    snapshotMeta: meta,
    snapshotUnavailable: false,
    snapshotLoading: false,
  };
  const values = (hydration: ReturnType<typeof mapToHomeFirstScreenHydration>) =>
    hydration.firstScreenHydration.keyRiskStrip.map(({ id, value }) => [id, value]);

  it("keeps headline precedence, risk units, and snapshot update time", () => {
    const hydration = mapToHomeFirstScreenHydration(input);

    expect(hydration.firstScreenHydration.reportDate).toBe("2026-07-31");
    expect(values(hydration)).toEqual([
      ["risk-dv01", "12.00 万"],
      ["risk-duration", "4.23"],
      ["risk-credit", "62.00%"],
      ["risk-top5", "31.00%"],
    ]);
    expect(hydration.updatedAt).toBe("16:00");
  });

  it("rejects each wrong-date source independently and retains same-date fallback", () => {
    expect(values(mapToHomeFirstScreenHydration({
      ...input, bondHeadline: { ...headline, report_date: "2026-07-30" },
    }))).toEqual([
      ["risk-dv01", "9.00 万"], ["risk-duration", "3.5"],
      ["risk-credit", "62.00%"], ["risk-top5", "31.00%"],
    ]);
    expect(values(mapToHomeFirstScreenHydration({
      ...input, portfolio: { ...portfolio, report_date: "2026-07-30" },
    }))).toEqual([["risk-dv01", "12.00 万"], ["risk-duration", "4.23"]]);
  });

  it("preserves zero values while suppressing null numeric payloads with display text", () => {
    const hydration = mapToHomeFirstScreenHydration({
      ...input,
      bondHeadline: null,
      portfolio: {
        ...portfolio,
        total_dv01: numeric(0, "dv01"),
        weighted_duration: { ...numeric(null), display: "5.99" },
        credit_weight: numeric(0),
        issuer_top5_weight: numeric(null),
      },
    });
    expect(values(hydration)).toEqual([["risk-dv01", "0.00 万"], ["risk-credit", "0.00%"]]);
  });

  it.each(["", "2026-07-30"])("does not hydrate unmatched report date %j", (reportDate) => {
    const hydration = mapToHomeFirstScreenHydration({ ...input, reportDate });
    expect(hydration.firstScreenHydration.reportDate).toBe(reportDate || "—");
    expect(hydration.firstScreenHydration.keyRiskStrip).toEqual([]);
  });

  it.each([
    { snapshotUnavailable: true, snapshotLoading: false },
    { snapshotUnavailable: false, snapshotLoading: true },
  ])("shows no update time when snapshot is unavailable: %j", (state) => {
    expect(mapToHomeFirstScreenHydration({ ...input, ...state }).updatedAt).toBe("—");
  });

  it("keeps the snapshot time when supplements are absent and never substitutes computed_at", () => {
    expect(mapToHomeFirstScreenHydration({
      ...input, bondHeadline: null, portfolio: null,
    })).toEqual({
      firstScreenHydration: { reportDate: "2026-07-31", keyRiskStrip: [] },
      updatedAt: "16:00",
    });
    expect(mapToHomeFirstScreenHydration({ ...input, snapshotMeta: null }).updatedAt).toBe("—");
  });

  it("keeps stale and vendor metadata semantics shared with the full first-screen view", () => {
    const snapshotMeta: ResultMeta = { ...meta, vendor_status: "vendor_stale", fallback_mode: "latest_snapshot" };
    const hydration = mapToHomeFirstScreenHydration({ ...input, snapshotMeta });
    const view = mapToHomeFirstScreenView({
      ...input, snapshotMeta, useMockFallback: false, snapshotStale: true,
      metrics, attribution: null, verdict: templateVerdict, alertCount: 0,
    });

    expect(view.headerStatus.dataStatusKind).toBe("stale");
    expect(view.headerStatus.dataUpdatedAt).toBe("16:00");
    expect(hydration.updatedAt).toBe(view.headerStatus.dataUpdatedAt);
    expect(hydration.firstScreenHydration.keyRiskStrip).toEqual(view.keyRiskStrip);
  });
});

describe("mapToHomeFirstScreenView reason line dedupe", () => {
  const nimReason = {
    label: "净息差",
    value: "+0.92%",
    detail: "来自受治理负债分析收益指标，在 2026-07-31 的 NIM 读面。",
    tone: "positive" as const,
  };
  const yieldReason = {
    label: "年度损益（不扣FTP）",
    value: "+48.56 亿",
    detail: "来自 fact_formal_pnl_fi 截至 2026-07-31 的年度累计。",
    tone: "positive" as const,
  };

  it("skips reasons whose label and value already appear in the fact headline and takes the next one", () => {
    const view = build({
      ...templateVerdict,
      reasons: [templateVerdict.reasons[0]!, yieldReason, nimReason],
    });

    expect(view.decisionRail.conclusion).toContain("3,705.38 亿");
    expect(view.decisionRail.conclusion).toContain("+48.56 亿");
    expect(view.decisionRail.keyRisk).toBe(
      ["净息差", "+0.92%", nimReason.detail].join(VERDICT_REASON_SEPARATOR),
    );
    expect(view.decisionRail.keyRisk).not.toContain("3,705.38");
  });

  it("falls back to the first informative suggestion when every reason repeats the headline", () => {
    const view = build({
      ...templateVerdict,
      reasons: [templateVerdict.reasons[0]!, yieldReason],
      suggestions: [
        { text: "进入对应专题页继续下钻原因链条", link: null },
        { text: "关注信用利差与久期暴露", link: "/bond-analysis" },
      ],
    });

    expect(view.decisionRail.keyRisk).toBe("关注信用利差与久期暴露");
  });

  it("returns the gap marker instead of filler copy when nothing is left to show", () => {
    const view = build({
      ...templateVerdict,
      reasons: [templateVerdict.reasons[0]!],
      suggestions: [{ text: "进入对应专题页继续下钻原因链条", link: null }],
    });

    expect(view.decisionRail.keyRisk).toBe("—");
  });

  it("matches on label plus value, so a same-named reason with a different value is kept", () => {
    const view = build({
      ...templateVerdict,
      reasons: [{ ...templateVerdict.reasons[0]!, value: "3,690.00 亿" }],
    });

    expect(view.decisionRail.keyRisk).toBe(
      ["总资产规模", "3,690.00 亿", templateVerdict.reasons[0]!.detail].join(
        VERDICT_REASON_SEPARATOR,
      ),
    );
  });
});
