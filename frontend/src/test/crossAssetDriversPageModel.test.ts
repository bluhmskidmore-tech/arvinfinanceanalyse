import { describe, expect, it } from "vitest";

import type {
  ChoiceMacroLatestPoint,
  ChoiceNewsEvent,
  MacroBondResearchView,
  MacroBondTransmissionAxis,
  MacroBondLinkageTopCorrelation,
  ResultMeta,
} from "../api/contracts";
import { resolveCrossAssetKpis } from "../features/cross-asset/lib/crossAssetKpiModel";
import {
  buildCrossAssetCandidateActions,
  buildCrossAssetDriversViewModel,
  buildCrossAssetEquityEvidenceItems,
  buildCrossAssetEventItems,
  buildCrossAssetNcdProxyEvidence,
  buildCrossAssetClassAnalysisRows,
  buildResearchSummaryCards,
  buildCrossAssetStatusFlags,
  buildTransmissionAxisRows,
  buildCrossAssetWatchList,
} from "../features/cross-asset/lib/crossAssetDriversPageModel";

function makeResultMeta(overrides: Partial<ResultMeta> = {}): ResultMeta {
  return {
    trace_id: "tr_cross_asset_test",
    basis: "analytical",
    result_kind: "macro.choice.latest",
    formal_use_allowed: false,
    source_version: "sv_cross_asset_test",
    vendor_version: "vv_cross_asset_test",
    rule_version: "rv_cross_asset_test",
    cache_version: "cv_cross_asset_test",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-04-10T09:00:00Z",
    ...overrides,
  };
}

function makePoint(
  series_id: string,
  series_name: string,
  value_numeric: number,
  overrides: Partial<ChoiceMacroLatestPoint> = {},
): ChoiceMacroLatestPoint {
  return {
    series_id,
    series_name,
    trade_date: "2026-04-10",
    value_numeric,
    frequency: "daily",
    unit: "%",
    source_version: "sv_choice_macro_test",
    vendor_version: "vv_choice_macro_test",
    refresh_tier: "stable",
    fetch_mode: "date_slice",
    fetch_granularity: "batch",
    policy_note: "cross-asset headline lane",
    quality_flag: "ok",
    latest_change: 0.01,
    recent_points: [
      {
        trade_date: "2026-04-09",
        value_numeric: value_numeric - 0.01,
        source_version: "sv_choice_macro_prev",
        vendor_version: "vv_choice_macro_prev",
        quality_flag: "ok",
      },
      {
        trade_date: "2026-04-10",
        value_numeric,
        source_version: "sv_choice_macro_test",
        vendor_version: "vv_choice_macro_test",
        quality_flag: "ok",
      },
    ],
    ...overrides,
  };
}

describe("crossAssetDriversPageModel", () => {
  it("surfaces analytical-only, fallback, stale, and no-data flags from result meta and series tiers", () => {
    const flags = buildCrossAssetStatusFlags({
      latestMeta: makeResultMeta({
        quality_flag: "stale",
        vendor_status: "vendor_stale",
        fallback_mode: "latest_snapshot",
      }),
      linkageMeta: makeResultMeta({
        result_kind: "macro_bond_linkage.analysis",
        quality_flag: "warning",
      }),
      latestSeries: [],
      crossAssetDataDate: "",
      linkageReportDate: "",
    });

    expect(flags.map((flag) => flag.id)).toEqual(
      expect.arrayContaining(["analytical-only", "stale", "fallback", "no-data"]),
    );
    const stale = flags.find((f) => f.id === "stale");
    const fallback = flags.find((f) => f.id === "fallback");
    expect(stale?.label).toBe("stale");
    expect(stale?.tone).toBe("warning");
    expect(fallback?.label).toBe("fallback");
    expect(fallback?.detail).toContain("Fallback");
  });

  it("marks the cross-asset chain as dual-source when Choice and Tushare supplements coexist", () => {
    const flags = buildCrossAssetStatusFlags({
      latestMeta: makeResultMeta(),
      latestSeries: [
        makePoint("EMM01843735", "Choice financial condition", -1.54),
        makePoint("CA.CSI300", "CSI300", 4769.37),
      ],
      crossAssetDataDate: "2026-04-24",
      linkageReportDate: "2026-04-24",
    });

    expect(flags.find((flag) => flag.id === "dual-source")?.label).toBe("dual source ready");
  });

  it("keeps source_blocked visible when Choice is unavailable but retained Choice rows still exist", () => {
    const flags = buildCrossAssetStatusFlags({
      latestMeta: makeResultMeta({ vendor_status: "vendor_unavailable" }),
      latestSeries: [
        makePoint("EMM01843735", "Choice financial condition", -1.54),
        makePoint("CA.CSI300", "CSI300", 4769.37),
      ],
      crossAssetDataDate: "2026-04-24",
      linkageReportDate: "2026-04-24",
    });

    expect(flags.find((flag) => flag.id === "source-blocked")?.label).toBe("source_blocked");
    expect(flags.find((flag) => flag.id === "dual-source")?.label).toBe("dual source ready");
  });

  it("puts failed module ids on the loading-failure flag label for header-only pill visibility", () => {
    const flags = buildCrossAssetStatusFlags({
      latestSeries: [],
      crossAssetDataDate: "",
      linkageReportDate: "",
      loadingFailures: ["choice_macro.latest", "macro_bond_linkage.analysis"],
    });
    const loadFail = flags.find((f) => f.id === "loading-failure");
    expect(loadFail?.label).toBe(
      "loading failure · choice_macro.latest, macro_bond_linkage.analysis",
    );
    expect(loadFail?.label).toContain("choice_macro.latest");
  });

  it("builds candidate actions from current environment scores and top-correlation evidence", () => {
    const rows = buildCrossAssetCandidateActions({
      env: {
        liquidity_score: 0.31,
        rate_direction_score: 0.42,
        growth_score: -0.18,
        inflation_score: 0.08,
      },
      topCorrelations: [
        {
          series_id: "EMM00166466",
          series_name: "10Y treasury yield",
          target_family: "credit_spread",
          target_tenor: "5Y",
          target_yield: "credit_spread_5Y",
          correlation_3m: -0.41,
          correlation_6m: -0.58,
          correlation_1y: -0.63,
          lead_lag_days: -4,
          direction: "negative",
        },
      ],
      linkageWarnings: [],
    });

    expect(rows).not.toHaveLength(0);
    expect(rows[0].evidence).toContain("liquidity_score");
    expect(rows.some((row) => row.evidence.includes("credit_spread"))).toBe(true);
  });

  it("marks heuristic fallback research views as pending_signal when backend omits them", () => {
    const rows = buildResearchSummaryCards({
      researchViews: undefined,
      env: { liquidity_score: 0.1, rate_direction_score: -0.05 },
      topCorrelations: [],
      linkageWarnings: [],
    });
    expect(rows).toHaveLength(4);
    expect(rows.every((row) => row.status === "pending_signal")).toBe(true);
    expect(rows.every((row) => row.source === "fallback")).toBe(true);
  });

  it("prefers backend research views over local heuristic fallback", () => {
    const rows = buildResearchSummaryCards({
      researchViews: [
        {
          key: "duration",
          status: "ready",
          stance: "bullish",
          confidence: "high",
          summary: "Backend duration view favors adding duration on easing liquidity.",
          affected_targets: ["rates", "ncd", "high_grade_credit"],
          evidence: ["Liquidity remains supportive."],
        } satisfies MacroBondResearchView,
      ],
      env: {
        rate_direction_score: 0.44,
        liquidity_score: -0.2,
      },
      topCorrelations: [],
      linkageWarnings: [],
    });

    expect(rows[0].key).toBe("duration");
    expect(rows[0].summary).toContain("Backend duration view");
    expect(rows[0].source).toBe("backend");
    expect(rows[1].source).toBe("fallback");
    expect(rows[1].status).toBe("pending_signal");
  });

  it("fills missing research view slots with pending_signal fallback cards", () => {
    const rows = buildResearchSummaryCards({
      researchViews: [
        {
          key: "duration",
          status: "ready",
          stance: "bullish",
          confidence: "high",
          summary: "Backend duration only.",
          affected_targets: ["rates"],
          evidence: ["evidence"],
        } satisfies MacroBondResearchView,
      ],
      env: {},
      topCorrelations: [],
      linkageWarnings: [],
    });
    const instrument = rows.find((r) => r.key === "instrument");
    expect(instrument?.source).toBe("fallback");
    expect(instrument?.status).toBe("pending_signal");
    expect(instrument?.summary).toContain("Fallback read");
  });

  it("surfaces governed transmission axes and pending-signal placeholders in page order", () => {
    const rows = buildTransmissionAxisRows({
      transmissionAxes: [
        {
          axis_key: "global_rates",
          status: "ready",
          stance: "restrictive",
          summary: "US rates remain a constraint on long-end duration.",
          impacted_views: ["duration", "curve"],
          required_series_ids: ["UST10Y"],
          warnings: [],
        } satisfies MacroBondTransmissionAxis,
      ],
      env: {
        liquidity_score: 0.28,
        inflation_score: 0.11,
      },
    });

    expect(rows.map((row) => row.axisKey)).toEqual([
      "global_rates",
      "liquidity",
      "equity_bond_spread",
      "commodities_inflation",
      "mega_cap_equities",
    ]);
    expect(rows[0].source).toBe("backend");
    expect(rows[0].status).toBe("ready");
    expect(rows[1].source).toBe("fallback");
    expect(rows[1].status).toBe("pending_signal");
    expect(rows[1].warnings.some((w) => w.includes("Heuristic"))).toBe(true);
    expect(rows[2].status).toBe("pending_signal");
    expect(rows[2].warnings.some((w) => w.toLowerCase().includes("governed"))).toBe(true);
    expect(rows[3].status).toBe("pending_signal");
    expect(rows[4].status).toBe("pending_signal");
  });

  it("keeps transmission axis order stable when backend omits axes (all pending_signal visible)", () => {
    const rows = buildTransmissionAxisRows({
      transmissionAxes: undefined,
      env: { rate_direction_score: 0.2, liquidity_score: 0.1, inflation_score: 0 },
    });
    expect(rows.map((r) => r.axisKey)).toEqual([
      "global_rates",
      "liquidity",
      "equity_bond_spread",
      "commodities_inflation",
      "mega_cap_equities",
    ]);
    expect(rows.every((r) => r.status === "pending_signal")).toBe(true);
    expect(rows.every((r) => r.source === "fallback")).toBe(true);
  });

  it("builds asset-class analysis rows with direction, source, and pending data labels", () => {
    const vendor = (vendor_name: string) => ({ vendor_name }) as Partial<ChoiceMacroLatestPoint>;
    const kpis = resolveCrossAssetKpis([
      makePoint("EMM01843735", "CSI 300", 3924.5, { unit: "index", latest_change: 1.8 }),
      makePoint("CA.CSI300_PE", "CSI300 PE", 14.58, { unit: "x", latest_change: 0.16, ...vendor("tushare") }),
      makePoint("CA.MEGA_CAP_WEIGHT", "CSI300 Top10 weight", 23.5367, {
        unit: "%",
        latest_change: 0.2,
        ...vendor("tushare"),
      }),
      makePoint("CA.MEGA_CAP_TOP5_WEIGHT", "CSI300 Top5 weight", 15.532, {
        unit: "%",
        latest_change: 0.1,
        ...vendor("tushare"),
      }),
      makePoint("CA.BRENT", "Brent spot price", 82.3, { unit: "USD/bbl", latest_change: 4.8, ...vendor("fred") }),
      makePoint("CA.STEEL", "Steel spot price", 8500, {
        unit: "CNY/t",
        latest_change: 3.2,
        ...vendor("public_spot_price_qh"),
      }),
    ]);
    const axes = buildTransmissionAxisRows({
      transmissionAxes: [
        {
          axis_key: "equity_bond_spread",
          status: "ready",
          stance: "risk_on",
          summary: "Equity-bond spread narrows as equity risk appetite improves.",
          impacted_views: ["duration", "credit"],
          required_series_ids: ["CA.CSI300"],
          warnings: [],
        } satisfies MacroBondTransmissionAxis,
        {
          axis_key: "mega_cap_equities",
          status: "ready",
          stance: "neutral",
          summary: "CSI300 top10 weight concentration is 23.54% (top5 15.53%).",
          impacted_views: ["credit", "instrument"],
          required_series_ids: ["tushare.index.000300.SH.weight"],
          warnings: [],
        } satisfies MacroBondTransmissionAxis,
      ],
      env: {},
    });

    const rows = buildCrossAssetClassAnalysisRows({ kpis, transmissionAxes: axes });

    expect(rows.map((row) => row.key)).toEqual(["stock", "commodities", "options"]);
    expect(rows[0].status).toBe("ready");
    expect(rows[0].lines.map((line) => line.key)).toEqual(["broad_index", "valuation_spread", "mega_cap_weight"]);
    expect(rows[0].lines[0].direction.length).toBeGreaterThan(0);
    expect(rows[0].lines[0].dataLabel).toContain("2026-04-10");
    expect(rows[0].lines[0].sourceLabel).toContain("Choice");
    expect(rows[0].lines[0].sourceLabel).toContain("EMM01843735");
    expect(rows[0].lines[1].dataLabel).toContain("14.58");
    expect(rows[0].lines[1].dataLabel).toContain("股债利差轴 ready");
    expect(rows[0].lines[2].dataLabel).toContain("23.54%");
    expect(rows[0].lines[2].dataLabel).toContain("15.53%");
    expect(rows[0].lines[2].sourceLabel).toContain("Tushare: CA.MEGA_CAP_WEIGHT");
    expect(rows[0].lines[2].sourceLabel).toContain("tushare.index.000300.SH.weight");
    expect(rows[0].lines[0].explanation).toContain("金融条件指数");
    expect(rows[1].status).toBe("ready");
    expect(rows[1].lines.map((line) => line.key)).toEqual(["energy", "ferrous", "nonferrous"]);
    expect(rows[1].lines[0].sourceLabel).toContain("公共补充源(fred): CA.BRENT");
    expect(rows[1].lines[0].sourceLabel).toContain("公共补充源");
    expect(rows[1].lines[0].sourceLabel).toContain("CA.BRENT");
    expect(rows[1].lines[1].sourceLabel).toContain("公共补充源");
    expect(rows[1].lines[1].sourceLabel).toContain("CA.STEEL");
    expect(rows[1].lines[0].explanation).toContain("布油");
    expect(rows[1].lines[1].explanation).toContain("钢");
    expect(rows[1].lines[2].status).toBe("pending_signal");
    expect(rows[1].lines[2].dataLabel).toContain("铜/铝");
    expect(rows[1].lines[2].dataLabel).toContain("公共补充");
    expect(rows[2].status).toBe("pending_signal");
    expect(rows[2].lines.map((line) => line.key)).toEqual(["equity_options", "commodity_options", "rates_bond_options"]);
    expect(rows[2].lines.every((line) => line.status === "pending_signal")).toBe(true);
    expect(rows[2].lines.every((line) => line.stateLabel === "pending_definition")).toBe(true);
    expect(rows[2].lines.every((line) => line.dataLabel.includes("Choice"))).toBe(true);
    expect(rows[2].lines.every((line) => line.dataLabel.includes("治理源"))).toBe(true);
    expect(rows[2].lines[0].explanation).toContain("No governed equity-options input");
  });

  it("builds stock index and mega-cap evidence items with unit, date, and source trace", () => {
    const vendor = (vendor_name: string) => ({ vendor_name }) as Partial<ChoiceMacroLatestPoint>;
    const kpis = resolveCrossAssetKpis([
      makePoint("EMM01843735", "CSI 300", 3924.5, { unit: "index", latest_change: 1.8 }),
      makePoint("CA.CSI300_PE", "CSI300 PE", 14.58, { unit: "x", latest_change: 0.16, ...vendor("tushare") }),
      makePoint("CA.MEGA_CAP_WEIGHT", "CSI300 Top10 weight", 23.5367, {
        unit: "%",
        latest_change: 0.2,
        ...vendor("tushare"),
      }),
      makePoint("CA.MEGA_CAP_TOP5_WEIGHT", "CSI300 Top5 weight", 15.532, {
        unit: "%",
        latest_change: 0.1,
        ...vendor("tushare"),
      }),
    ]);

    const items = buildCrossAssetEquityEvidenceItems(kpis);

    expect(items.map((item) => item.key)).toEqual([
      "broad_index",
      "csi300_pe",
      "mega_cap_weight",
      "mega_cap_top5_weight",
    ]);
    expect(items[0]).toMatchObject({
      sourceLabel: "Choice接入码: EMM01843735",
      unitLabel: "index",
      tradeDate: "2026-04-10",
    });
    expect(items[1].sourceLabel).toBe("Tushare: CA.CSI300_PE");
    expect(items[1].unitLabel).toBe("x");
    expect(items[2].valueLabel).toBe("23.54%");
    expect(items[2].unitLabel).toBe("%");
    expect(items[3].sourceLabel).toBe("Tushare: CA.MEGA_CAP_TOP5_WEIGHT");
  });

  it("marks equity evidence item quality from selected data and source availability", () => {
    const vendor = (vendor_name: string) => ({ vendor_name }) as Partial<ChoiceMacroLatestPoint>;
    const kpis = resolveCrossAssetKpis([
      makePoint("EMM01843735", "CSI 300", 3924.5, {
        unit: "index",
        quality_flag: "stale",
      }),
      makePoint("CA.CSI300_PE", "CSI300 PE", 14.58, {
        unit: "x",
        refresh_tier: "fallback",
        ...vendor("tushare"),
      }),
    ]);

    const items = buildCrossAssetEquityEvidenceItems(kpis);
    const sourceBlockedItems = buildCrossAssetEquityEvidenceItems(
      kpis,
      makeResultMeta({ vendor_status: "vendor_unavailable" }),
    );

    expect(items.find((item) => item.key === "broad_index")?.status).toBe("stale");
    expect(items.find((item) => item.key === "csi300_pe")?.status).toBe("fallback");
    expect(items.find((item) => item.key === "mega_cap_weight")?.status).toBe("missing_dependency");
    expect(sourceBlockedItems.find((item) => item.key === "broad_index")?.status).toBe("source_blocked");
  });

  it("marks retained Choice-backed card lines as source_blocked when vendor status is unavailable", () => {
    const kpis = resolveCrossAssetKpis([
      makePoint("EMM01843735", "Choice financial condition", -1.54, {
        latest_change: -0.01,
      }),
    ]);

    const rows = buildCrossAssetClassAnalysisRows({
      kpis,
      transmissionAxes: [],
      latestMeta: makeResultMeta({ vendor_status: "vendor_unavailable" }),
    });

    expect(rows[0].lines.find((line) => line.key === "broad_index")?.stateLabel).toBe("source_blocked");
  });

  it("maps research calendar events into event calendar rows", () => {
    const items = buildCrossAssetEventItems({
      events: [
        {
          id: "cal-1",
          date: "2026-04-24",
          title: "附息国债发行",
          kind: "supply",
          severity: "high",
          amount_label: "180 亿元",
          note: "7Y · scheduled",
        },
      ],
    });
    expect(items).toHaveLength(1);
    expect(items[0].event).toContain("附息");
    expect(items[0].amount).toBe("180 亿元");
    expect(items[0].level).toBe("high");
    expect(items[0].note).toContain("7Y");
  });

  it("converts recent news events and linkage warnings into data-driven event rows", () => {
    const items = buildCrossAssetEventItems({
      reportDate: "2026-04-10",
      linkageWarnings: ["fact_choice_macro_daily 数据点不足（少于 30 个交易日）"],
      newsEvents: [
        {
          event_key: "ce_mock_001",
          received_at: "2026-04-10T09:01:00Z",
          group_id: "news_cmd1",
          content_type: "sectornews",
          serial_id: 1001,
          request_id: 501,
          error_code: 0,
          error_msg: "",
          topic_code: "S888010007API",
          item_index: 0,
          payload_text: "Macro data release calendar updated for CPI and industrial production.",
          payload_json: null,
        } satisfies ChoiceNewsEvent,
      ],
    });

    expect(items).toHaveLength(2);
    expect(items[0].event).toContain("数据点不足");
    expect(items[1].event).toContain("Macro data release");
  });

  it("builds the watch list from resolved KPI rows instead of static placeholders", () => {
    const kpis = resolveCrossAssetKpis([
      makePoint("E1000180", "中债国债到期收益率:10年", 1.94),
      makePoint("E1003238", "美国国债收益率:10年", 4.1),
      makePoint("EM1", "中美10Y利差", -210, {
        unit: "bp",
        latest_change: -3,
        recent_points: [
          {
            trade_date: "2026-04-09",
            value_numeric: -207,
            source_version: "sv_choice_macro_prev",
            vendor_version: "vv_choice_macro_prev",
            quality_flag: "ok",
          },
          {
            trade_date: "2026-04-10",
            value_numeric: -210,
            source_version: "sv_choice_macro_test",
            vendor_version: "vv_choice_macro_test",
            quality_flag: "ok",
          },
        ],
      }),
      makePoint("CA.DR007", "DR007", 1.82),
      makePoint("EMM01843735", "金融条件指数", 3924.5, { unit: "index", latest_change: 1.8 }),
      makePoint("CA.BRENT", "Brent spot price", 82.3, { unit: "USD/bbl", latest_change: 4.8 }),
      makePoint("CA.STEEL", "螺纹钢现货价格", 8500, { unit: "CNY/t", latest_change: 3.2 }),
      makePoint("EMM00058124", "中间价:美元兑人民币", 7.14, { unit: "CNY/USD", latest_change: 0.0064 }),
    ]);

    const rows = buildCrossAssetWatchList({
      kpis,
      topCorrelations: [
        {
          series_id: "EMM00166466",
          series_name: "10Y treasury yield",
          target_family: "treasury",
          target_tenor: "10Y",
          target_yield: "treasury_10Y",
          correlation_3m: 0.32,
          correlation_6m: 0.47,
          correlation_1y: 0.51,
          lead_lag_days: 2,
          direction: "positive",
        } satisfies MacroBondLinkageTopCorrelation,
      ],
      linkageWarnings: [],
    });

    expect(rows).not.toHaveLength(0);
    expect(rows[0].current).not.toContain("分位");
    expect(rows[0].signalText.length).toBeGreaterThan(0);
  });
  it("surfaces NCD proxy-only metadata in evidence and candidate actions", () => {
    const evidence = buildCrossAssetNcdProxyEvidence({
      available: true,
      result: {
        as_of_date: "2026-04-23",
        proxy_label: "Tushare Shibor funding proxy",
        is_actual_ncd_matrix: false,
        rows: [
          {
            row_key: "shibor_fixing",
            label: "Shibor fixing",
            "1M": 1.405,
            "3M": 1.4275,
            "6M": 1.4505,
            "9M": 1.464,
            "1Y": 1.478,
            quote_count: null,
          },
        ],
        warnings: [
          "Proxy only; not actual NCD issuance matrix.",
          "Using landed external warehouse Shibor; quote medians unavailable.",
        ],
      },
    });
    expect(evidence.isActualNcdMatrix).toBe(false);
    expect(evidence.proxyWarning).toMatch(/not actual NCD issuance matrix/i);
    expect(evidence.proxyWarning).toMatch(/warehouse|landed|quote medians unavailable/i);
    expect(evidence.rowCaptions[0]).toContain("Shibor fixing");
    expect(evidence.rowCaptions[0]).toContain("9M 1.464");
    expect(evidence.rowCaptions.some((line) => /Quote median/i.test(line))).toBe(false);

    const actions = buildCrossAssetCandidateActions({
      env: {},
      topCorrelations: [],
      linkageWarnings: [],
      ncdProxy: {
        as_of_date: "2026-04-23",
        proxy_label: "Test proxy",
        is_actual_ncd_matrix: false,
        rows: [],
        warnings: [
          "Proxy only; not actual NCD issuance matrix.",
          "Using landed external warehouse Shibor; quote medians unavailable.",
        ],
      },
    });
    expect(actions[0].action).toContain("NCD");
    expect(actions[0].reason).toMatch(/not actual NCD issuance matrix/i);
    expect(actions[0].reason).toMatch(/quote medians unavailable/i);
    expect(actions[0].action).not.toMatch(/真实|actual\s+NCD\s+issuance\s+matrix/i);
  });

  it("buildCrossAssetDriversViewModel aggregates cards, axes, calendar, NCD evidence, and flags", () => {
    const kpis = resolveCrossAssetKpis([makePoint("E1000180", "CN 10Y", 1.94)]);
    const vm = buildCrossAssetDriversViewModel({
      researchViews: [
        {
          key: "duration",
          status: "ready",
          stance: "bullish",
          confidence: "high",
          summary: "Synthesized.",
          affected_targets: ["rates"],
          evidence: ["e"],
        } satisfies MacroBondResearchView,
      ],
      transmissionAxes: [
        {
          axis_key: "global_rates",
          status: "ready",
          stance: "neutral",
          summary: "Axis ok.",
          impacted_views: ["duration"],
          required_series_ids: [],
          warnings: [],
        } satisfies MacroBondTransmissionAxis,
      ],
      env: {},
      topCorrelations: [],
      linkageWarnings: [],
      kpis,
      latestMeta: makeResultMeta({ quality_flag: "stale", fallback_mode: "latest_snapshot" }),
      linkageMeta: undefined,
      latestSeries: [makePoint("E1000180", "CN 10Y", 1.94)],
      crossAssetDataDate: "2026-04-10",
      linkageReportDate: "2026-04-10",
      calendarEvents: [
        {
          id: "e1",
          date: "2026-04-11",
          title: "Auction",
          kind: "auction",
          severity: "medium",
          amount_label: "50 亿元",
        },
      ],
      ncdProxy: null,
      ncdProxyAvailable: false,
    });

    expect(vm.researchCards[0].source).toBe("backend");
    expect(vm.transmissionAxes[0].source).toBe("backend");
    expect(vm.assetClassAnalysisRows.map((row) => row.key)).toEqual(["stock", "commodities", "options"]);
    expect(vm.assetClassAnalysisRows.find((row) => row.key === "options")?.status).toBe("pending_signal");
    expect(vm.eventCalendarRows[0].event).toContain("Auction");
    expect(vm.ncdProxyEvidence.sourceMeta).toBe("unavailable");
    expect(vm.statusFlags.map((f) => f.id)).toEqual(
      expect.arrayContaining(["analytical-only", "stale", "fallback"]),
    );
  });

  it("derives candidate actions and watch items from research views plus provenance", () => {
    const researchViews: MacroBondResearchView[] = [
      {
        key: "duration",
        status: "ready",
        stance: "bullish",
        confidence: "high",
        summary: "Duration view turns constructive as liquidity stays easy.",
        affected_targets: ["rates", "ncd"],
        evidence: ["DR007 remains contained."],
      },
      {
        key: "instrument",
        status: "ready",
        stance: "barbell",
        confidence: "medium",
        summary: "Prefer rates and high-grade credit over lower-quality carry.",
        affected_targets: ["rates", "high_grade_credit"],
        evidence: ["Credit beta should stay selective."],
      },
    ];
    const transmissionAxes: MacroBondTransmissionAxis[] = [
      {
        axis_key: "global_rates",
        status: "ready",
        stance: "restrictive",
        summary: "Global rates cap aggressive long-end chasing.",
        impacted_views: ["duration", "curve"],
        required_series_ids: ["UST10Y"],
        warnings: [],
      },
    ];
    const kpis = resolveCrossAssetKpis([
      makePoint("E1000180", "CN 10Y", 1.94),
      makePoint("CA.DR007", "DR007", 1.82),
      makePoint("EMM00058124", "USD/CNY", 7.14, { unit: "CNY/USD", latest_change: 0.0064 }),
      makePoint("CA.BRENT", "Brent spot price", 82.3, { unit: "USD/bbl", latest_change: 4.8 }),
    ]);

    const actions = buildCrossAssetCandidateActions({
      researchViews,
      transmissionAxes,
      env: {},
      topCorrelations: [],
      linkageWarnings: ["analytical only"],
    });
    const watchRows = buildCrossAssetWatchList({
      kpis,
      researchViews,
      transmissionAxes,
      topCorrelations: [],
      linkageWarnings: ["analytical only"],
    });

    expect(actions[0].reason.toLowerCase()).toContain("duration");
    expect(actions.some((row) => row.evidence.includes("global_rates"))).toBe(true);
    expect(watchRows[0].note).toContain("duration");
    expect(watchRows[0].signalText).toContain("全球利率");
  });
});
