import { describe, expect, it } from "vitest";

import type {
  CounterpartyStatsResponse,
  InterbankCounterpartySplitResponse,
  RateCoverage,
  RatingStatsResponse,
  ResultMeta,
} from "../../../api/contracts";
import { EM_DASH } from "../../../pageModel";
import {
  buildPositionsBondsKpiBand,
  buildPositionsCaliberItems,
  buildPositionsFirstScreenStatus,
  buildPositionsInterbankKpiBand,
  buildPositionsPrimaryListTableState,
  compactVersion,
  formatCoverageSummary,
  metaSummary,
  normalizePositionsPrimaryListEnvelope,
  rateCoveragePolicyLabel,
  topRatingItem,
  type PositionsPrimaryListEnvelope,
  type PositionsPrimaryListMeta,
} from "./positionsPageModel";

type FirstScreenInput = Parameters<typeof buildPositionsFirstScreenStatus>[0];
type TableStateInput = Parameters<typeof buildPositionsPrimaryListTableState>[0];

function listMeta(overrides: Partial<PositionsPrimaryListMeta> = {}): PositionsPrimaryListMeta {
  return {
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    requested_report_date: "2026-04-30",
    resolved_report_date: "2026-04-30",
    as_of_date: "2026-04-30",
    fallback_date: null,
    ...overrides,
  };
}

function validRawEnvelope() {
  return {
    result_meta: {
      // 额外字段模拟真实 ResultMeta；归一化只保留白名单内 7 个字段。
      trace_id: "tr_test",
      quality_flag: "ok",
      vendor_status: "ok",
      fallback_mode: "none",
      requested_report_date: "2026-04-30",
      resolved_report_date: "2026-04-29",
      as_of_date: "2026-04-28",
      fallback_date: null,
    },
    result: { items: [{ bond_code: "B1" }], total: 5, page: 1, page_size: 20 },
  };
}

function withResult(overrides: Record<string, unknown>) {
  const base = validRawEnvelope();
  return { ...base, result: { ...base.result, ...overrides } };
}

function withMeta(overrides: Record<string, unknown>) {
  const base = validRawEnvelope();
  return { ...base, result_meta: { ...base.result_meta, ...overrides } };
}

function envelopeOf(items: unknown[], total: number): PositionsPrimaryListEnvelope<unknown> {
  return {
    result_meta: listMeta(),
    result: { items, total, page: 1, page_size: 20 },
  };
}

function tableInput(overrides: Partial<TableStateInput> = {}): TableStateInput {
  return {
    reportDate: "2026-04-30",
    datesLoading: false,
    datesError: false,
    listLoading: false,
    listSuccess: true,
    listError: false,
    envelope: envelopeOf([{ id: 1 }], 5),
    ...overrides,
  };
}

function statusInput(overrides: Partial<FirstScreenInput> = {}): FirstScreenInput {
  return {
    tab: "bonds",
    datesError: false,
    datesEmpty: false,
    listError: false,
    listTableState: "ready",
    meta: listMeta(),
    ...overrides,
  };
}

function bondsStats(overrides: Partial<CounterpartyStatsResponse> = {}): CounterpartyStatsResponse {
  return {
    start_date: "2026-04-01",
    end_date: "2026-04-30",
    num_days: 30,
    items: [],
    total_amount: "60000000000",
    total_avg_daily: "200000000.00",
    total_weighted_rate: "0.02550000",
    total_weighted_coupon_rate: "0.03000000",
    total_customers: 12,
    cr10_ratio: "87.65",
    ...overrides,
  };
}

function interbankSplit(
  overrides: Partial<InterbankCounterpartySplitResponse> = {},
): InterbankCounterpartySplitResponse {
  return {
    start_date: "2026-04-01",
    end_date: "2026-04-30",
    num_days: 31,
    asset_total_amount: "9000000000",
    asset_total_avg_daily: "300000000",
    asset_total_weighted_rate: "0.02100000",
    asset_customer_count: 8,
    liability_total_amount: "0",
    liability_total_avg_daily: "0",
    liability_total_weighted_rate: null,
    liability_customer_count: 5,
    asset_items: [],
    liability_items: [],
    ...overrides,
  };
}

function coverage(overrides: Partial<RateCoverage> = {}): RateCoverage {
  return {
    policy: "exclude_missing_rate_from_denominator",
    covered_amount: "1000000000",
    missing_amount: "0",
    missing_count: 0,
    coverage_ratio: "100.00",
    ...overrides,
  };
}

function resultMeta(overrides: Partial<ResultMeta> = {}): ResultMeta {
  return {
    trace_id: "tr_test",
    basis: "formal",
    result_kind: "positions.test",
    formal_use_allowed: true,
    source_version: "sv_test",
    vendor_version: "vv_none",
    rule_version: "rv_test",
    cache_version: "cv_test",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-01-02T00:00:00Z",
    ...overrides,
  };
}

function ratingItem(rating: string, percentage: string): RatingStatsResponse["items"][number] {
  return {
    rating,
    total_amount: "0",
    avg_daily_balance: "0",
    weighted_rate: null,
    bond_count: 1,
    percentage,
  };
}

describe("normalizePositionsPrimaryListEnvelope", () => {
  it("accepts a valid envelope and keeps only the whitelisted meta fields", () => {
    expect(normalizePositionsPrimaryListEnvelope(validRawEnvelope())).toEqual({
      result_meta: {
        quality_flag: "ok",
        vendor_status: "ok",
        fallback_mode: "none",
        requested_report_date: "2026-04-30",
        resolved_report_date: "2026-04-29",
        as_of_date: "2026-04-28",
        fallback_date: null,
      },
      result: { items: [{ bond_code: "B1" }], total: 5, page: 1, page_size: 20 },
    });
  });

  it.each<[string, unknown]>([
    ["value is not a record", null],
    ["result is missing", { result_meta: validRawEnvelope().result_meta }],
    ["result_meta is missing", { result: validRawEnvelope().result }],
    ["items is not an array", withResult({ items: "invalid" })],
    ["total is negative", withResult({ total: -1 })],
    ["total is NaN", withResult({ total: Number.NaN })],
    ["total is not an integer", withResult({ total: 1.5 })],
    ["page is below 1", withResult({ page: 0 })],
    ["page_size is below 1", withResult({ page_size: 0 })],
    ["quality_flag is invalid", withMeta({ quality_flag: "unknown" })],
    ["vendor_status is invalid", withMeta({ vendor_status: "unknown" })],
    ["fallback_mode is invalid", withMeta({ fallback_mode: "partial" })],
    ["requested_report_date is not a string", withMeta({ requested_report_date: 20260430 })],
    ["as_of_date is not a string", withMeta({ as_of_date: 20260428 })],
  ])("fails closed to null when %s", (_label, raw) => {
    expect(normalizePositionsPrimaryListEnvelope(raw)).toBeNull();
  });
});

describe("buildPositionsPrimaryListTableState", () => {
  it("stays loading while report dates are unresolved", () => {
    expect(
      buildPositionsPrimaryListTableState(tableInput({ reportDate: "", datesLoading: true })),
    ).toBe("loading");
  });

  it("reports error when report dates failed and none is selected", () => {
    expect(
      buildPositionsPrimaryListTableState(tableInput({ reportDate: "", datesError: true })),
    ).toBe("error");
  });

  it("blocks when no report date resolved without a dates error", () => {
    expect(buildPositionsPrimaryListTableState(tableInput({ reportDate: "" }))).toBe("blocked");
  });

  it("reports error when the list query failed", () => {
    expect(buildPositionsPrimaryListTableState(tableInput({ listError: true }))).toBe("error");
  });

  it("reports loading while the list query is pending", () => {
    expect(buildPositionsPrimaryListTableState(tableInput({ listLoading: true }))).toBe("loading");
  });

  it("reports loading before the list query has succeeded", () => {
    expect(buildPositionsPrimaryListTableState(tableInput({ listSuccess: false }))).toBe("loading");
  });

  it("reports error for a null (fail-closed) envelope", () => {
    expect(buildPositionsPrimaryListTableState(tableInput({ envelope: null }))).toBe("error");
  });

  it("reports empty only for total=0 with no rows", () => {
    expect(buildPositionsPrimaryListTableState(tableInput({ envelope: envelopeOf([], 0) }))).toBe(
      "empty",
    );
  });

  it("blocks when total is positive but the current page has no rows", () => {
    expect(buildPositionsPrimaryListTableState(tableInput({ envelope: envelopeOf([], 5) }))).toBe(
      "blocked",
    );
  });

  it("is ready when rows are present", () => {
    expect(buildPositionsPrimaryListTableState(tableInput())).toBe("ready");
  });
});

describe("buildPositionsFirstScreenStatus", () => {
  it("returns null when everything is clean", () => {
    expect(buildPositionsFirstScreenStatus(statusInput())).toBeNull();
  });

  it("returns null when meta is undefined and no other signal fires", () => {
    expect(buildPositionsFirstScreenStatus(statusInput({ meta: undefined }))).toBeNull();
  });

  it("prioritizes the dates error over every other signal", () => {
    expect(
      buildPositionsFirstScreenStatus(
        statusInput({
          datesError: true,
          datesEmpty: true,
          listError: true,
          listTableState: "error",
          meta: listMeta({ quality_flag: "error", fallback_mode: "latest_snapshot" }),
        }),
      ),
    ).toEqual({
      type: "error",
      message: "可用报告日加载失败",
      description: "当前无法确定持仓报告日，请稍后重试。",
    });
  });

  it("prioritizes the list query failure over envelope/quality/empty signals", () => {
    expect(
      buildPositionsFirstScreenStatus(
        statusInput({
          datesEmpty: true,
          listError: true,
          listTableState: "error",
          meta: listMeta({ quality_flag: "error" }),
        }),
      ),
    ).toEqual({
      type: "error",
      message: "债券持仓加载失败",
      description: "持仓请求未成功，请稍后重试。",
    });
  });

  it("labels the interbank list when that tab is active", () => {
    expect(
      buildPositionsFirstScreenStatus(statusInput({ tab: "interbank", listError: true })),
    ).toEqual({
      type: "error",
      message: "同业持仓加载失败",
      description: "持仓请求未成功，请稍后重试。",
    });
  });

  it("reports an incomplete envelope before quality/empty signals", () => {
    expect(
      buildPositionsFirstScreenStatus(
        statusInput({
          datesEmpty: true,
          listTableState: "error",
          meta: listMeta({ quality_flag: "error" }),
        }),
      ),
    ).toEqual({
      type: "error",
      message: "债券持仓响应不完整",
      description: "当前返回内容缺少必要的数据或状态信息，请稍后重试。",
    });
  });

  it.each<[string, Partial<PositionsPrimaryListMeta>]>([
    ["quality error", { quality_flag: "error" }],
    ["vendor unavailable", { vendor_status: "vendor_unavailable" }],
  ])("reports unavailable data for %s before the empty states", (_label, overrides) => {
    expect(
      buildPositionsFirstScreenStatus(
        statusInput({ datesEmpty: true, meta: listMeta(overrides) }),
      ),
    ).toEqual({
      type: "error",
      message: "债券持仓数据当前不可用",
      description: "当前返回结果未达到可用状态，请稍后重试。",
    });
  });

  it("reports missing report dates before the empty list state", () => {
    expect(
      buildPositionsFirstScreenStatus(statusInput({ datesEmpty: true, listTableState: "empty" })),
    ).toEqual({
      type: "info",
      message: "暂无可用报告日",
      description: "当前无法查询持仓数据。",
    });
  });

  it("reports the empty list before fallback details", () => {
    expect(
      buildPositionsFirstScreenStatus(
        statusInput({
          listTableState: "empty",
          meta: listMeta({ fallback_mode: "latest_snapshot" }),
        }),
      ),
    ).toEqual({
      type: "info",
      message: "当前报告日暂无债券持仓数据",
      description: "可调整报告日或筛选条件后重试。",
    });
  });

  it("describes a latest-snapshot fallback with every known date", () => {
    expect(
      buildPositionsFirstScreenStatus(
        statusInput({
          meta: listMeta({
            fallback_mode: "latest_snapshot",
            requested_report_date: "2026-04-30",
            resolved_report_date: "2026-04-29",
            as_of_date: "2026-04-28",
            fallback_date: "2026-04-27",
          }),
        }),
      ),
    ).toEqual({
      type: "warning",
      message: "债券持仓已回退到最近可用快照",
      description: "请求日期 2026-04-30，解析日期 2026-04-29，有效日期 2026-04-28，回退日期 2026-04-27。",
    });
  });

  it.each<[string, Partial<PositionsPrimaryListMeta>]>([
    ["quality stale", { quality_flag: "stale" }],
    ["vendor stale", { vendor_status: "vendor_stale" }],
  ])("merges %s into the fallback message", (_label, overrides) => {
    expect(
      buildPositionsFirstScreenStatus(
        statusInput({ meta: listMeta({ fallback_mode: "latest_snapshot", ...overrides }) }),
      ),
    ).toEqual({
      type: "warning",
      message: "债券持仓已回退至最近可用快照，且该快照可能偏旧",
      description: "请求日期 2026-04-30，解析日期 2026-04-30，有效日期 2026-04-30。",
    });
  });

  it("falls back to the generic snapshot description when no dates are present", () => {
    expect(
      buildPositionsFirstScreenStatus(
        statusInput({
          meta: listMeta({
            fallback_mode: "latest_snapshot",
            requested_report_date: null,
            resolved_report_date: null,
            as_of_date: null,
            fallback_date: null,
          }),
        }),
      ),
    ).toEqual({
      type: "warning",
      message: "债券持仓已回退到最近可用快照",
      description: "当前使用最近可用快照，请确认数据日期后使用。",
    });
  });

  it.each<[string, Partial<PositionsPrimaryListMeta>]>([
    ["quality stale", { quality_flag: "stale" }],
    ["vendor stale", { vendor_status: "vendor_stale" }],
  ])("warns about stale data with the effective date for %s", (_label, overrides) => {
    expect(
      buildPositionsFirstScreenStatus(
        statusInput({ meta: listMeta({ ...overrides, as_of_date: "2026-04-27" }) }),
      ),
    ).toEqual({
      type: "warning",
      message: "债券持仓数据可能偏旧",
      description: "有效日期 2026-04-27，请确认后使用。",
    });
  });

  it("resolves the stale effective date via as_of → resolved → fallback order", () => {
    expect(
      buildPositionsFirstScreenStatus(
        statusInput({
          meta: listMeta({
            quality_flag: "stale",
            as_of_date: null,
            resolved_report_date: "2026-04-26",
            fallback_date: "2026-04-20",
          }),
        }),
      )?.description,
    ).toBe("有效日期 2026-04-26，请确认后使用。");

    expect(
      buildPositionsFirstScreenStatus(
        statusInput({
          meta: listMeta({
            quality_flag: "stale",
            as_of_date: null,
            resolved_report_date: null,
            fallback_date: "2026-04-20",
          }),
        }),
      )?.description,
    ).toBe("有效日期 2026-04-20，请确认后使用。");
  });

  it("uses the generic stale description when no dates exist", () => {
    expect(
      buildPositionsFirstScreenStatus(
        statusInput({
          meta: listMeta({
            quality_flag: "stale",
            requested_report_date: null,
            resolved_report_date: null,
            as_of_date: null,
            fallback_date: null,
          }),
        }),
      ),
    ).toEqual({
      type: "warning",
      message: "债券持仓数据可能偏旧",
      description: "当前数据可能滞后，请确认日期后使用。",
    });
  });
});

describe("buildPositionsBondsKpiBand", () => {
  it("formats the six business readouts from full stats", () => {
    expect(buildPositionsBondsKpiBand({ stats: bondsStats(), loading: false })).toEqual([
      { key: "avg-daily", label: "日均合计", value: "2.00 亿元", note: "分母 30 天" },
      { key: "range-total", label: "区间累计", value: "600.00 亿元" },
      { key: "weighted-rate", label: "加权收益率", value: "2.55%" },
      { key: "coupon-rate", label: "加权付息率", value: "3.00%" },
      { key: "customers", label: "客户数", value: "12 户" },
      { key: "cr10", label: "CR10 集中度", value: "87.65" },
    ]);
  });

  it("never sets a tone on any cell", () => {
    const band = buildPositionsBondsKpiBand({ stats: bondsStats(), loading: false });
    expect(band.every((cell) => cell.tone === undefined)).toBe(true);
  });

  it("dashes null/undefined rates and CR10 without touching amounts", () => {
    const band = buildPositionsBondsKpiBand({
      stats: bondsStats({
        total_weighted_rate: null,
        total_weighted_coupon_rate: undefined,
        cr10_ratio: null,
      }),
      loading: false,
    });
    expect(band[2].value).toBe(EM_DASH);
    expect(band[3].value).toBe(EM_DASH);
    expect(band[5].value).toBe(EM_DASH);
    expect(band[0].value).toBe("2.00 亿元");
  });

  it("keeps '0' amounts as a true zero instead of EM_DASH", () => {
    const band = buildPositionsBondsKpiBand({
      stats: bondsStats({ total_avg_daily: "0", total_amount: "0" }),
      loading: false,
    });
    expect(band[0].value).toBe("0.00 亿元");
    expect(band[1].value).toBe("0.00 亿元");
  });

  it("omits the denominator note when num_days is missing", () => {
    const band = buildPositionsBondsKpiBand({
      stats: bondsStats({ num_days: null as unknown as number }),
      loading: false,
    });
    expect(band[0].note).toBeUndefined();
  });

  it("shows loading placeholders while the query is pending", () => {
    const expected = [
      { key: "avg-daily", label: "日均合计", value: EM_DASH, status: "loading" },
      { key: "range-total", label: "区间累计", value: EM_DASH, status: "loading" },
      { key: "weighted-rate", label: "加权收益率", value: EM_DASH, status: "loading" },
      { key: "coupon-rate", label: "加权付息率", value: EM_DASH, status: "loading" },
      { key: "customers", label: "客户数", value: EM_DASH, status: "loading" },
      { key: "cr10", label: "CR10 集中度", value: EM_DASH, status: "loading" },
    ];
    expect(buildPositionsBondsKpiBand({ stats: undefined, loading: true })).toEqual(expected);
    // loading 优先于已有数据（如 keepPreviousData 场景）
    expect(buildPositionsBondsKpiBand({ stats: bondsStats(), loading: true })).toEqual(expected);
  });

  it("dashes all values without a status when stats are absent and not loading", () => {
    const band = buildPositionsBondsKpiBand({ stats: undefined, loading: false });
    expect(band).toEqual([
      { key: "avg-daily", label: "日均合计", value: EM_DASH },
      { key: "range-total", label: "区间累计", value: EM_DASH },
      { key: "weighted-rate", label: "加权收益率", value: EM_DASH },
      { key: "coupon-rate", label: "加权付息率", value: EM_DASH },
      { key: "customers", label: "客户数", value: EM_DASH },
      { key: "cr10", label: "CR10 集中度", value: EM_DASH },
    ]);
    expect(band.every((cell) => cell.status === undefined)).toBe(true);
  });
});

describe("buildPositionsInterbankKpiBand", () => {
  it("formats the six asset/liability readouts from a full split", () => {
    expect(buildPositionsInterbankKpiBand({ split: interbankSplit(), loading: false })).toEqual([
      { key: "asset-avg", label: "资产端日均", value: "3.00 亿元", note: "分母 31 天" },
      { key: "asset-rate", label: "资产端加权利率", value: "2.10%" },
      { key: "asset-customers", label: "资产端户数", value: "8 户" },
      { key: "liability-avg", label: "负债端日均", value: "0.00 亿元" },
      { key: "liability-rate", label: "负债端加权利率", value: EM_DASH },
      { key: "liability-customers", label: "负债端户数", value: "5 户" },
    ]);
  });

  it("never sets a tone on any cell", () => {
    const band = buildPositionsInterbankKpiBand({ split: interbankSplit(), loading: false });
    expect(band.every((cell) => cell.tone === undefined)).toBe(true);
  });

  it("shows loading placeholders while the query is pending", () => {
    const expected = [
      { key: "asset-avg", label: "资产端日均", value: EM_DASH, status: "loading" },
      { key: "asset-rate", label: "资产端加权利率", value: EM_DASH, status: "loading" },
      { key: "asset-customers", label: "资产端户数", value: EM_DASH, status: "loading" },
      { key: "liability-avg", label: "负债端日均", value: EM_DASH, status: "loading" },
      { key: "liability-rate", label: "负债端加权利率", value: EM_DASH, status: "loading" },
      { key: "liability-customers", label: "负债端户数", value: EM_DASH, status: "loading" },
    ];
    expect(buildPositionsInterbankKpiBand({ split: undefined, loading: true })).toEqual(expected);
    expect(buildPositionsInterbankKpiBand({ split: interbankSplit(), loading: true })).toEqual(
      expected,
    );
  });

  it("dashes all values without a status when the split is absent and not loading", () => {
    const band = buildPositionsInterbankKpiBand({ split: undefined, loading: false });
    expect(band.map((cell) => cell.value)).toEqual([
      EM_DASH,
      EM_DASH,
      EM_DASH,
      EM_DASH,
      EM_DASH,
      EM_DASH,
    ]);
    expect(band.every((cell) => cell.status === undefined)).toBe(true);
  });
});

describe("buildPositionsCaliberItems", () => {
  it("emits the fixed-order caliber items for the bonds tab", () => {
    expect(
      buildPositionsCaliberItems({
        tab: "bonds",
        reportDate: "2026-04-30",
        startDate: "2026-04-01",
        endDate: "2026-04-30",
        scopeLabel: "Gov",
        peerFilterLabel: "未输入客户",
      }),
    ).toEqual([
      "报表日：2026-04-30",
      "区间：2026-04-01 ~ 2026-04-30",
      "数据来源：ZQTZ + TYWL",
      "日均分母=有数据 report_date 数",
      "当前：债券持仓",
      "Gov",
      "未输入客户",
    ]);
  });

  it("emits the interbank branch and dashes unresolved dates", () => {
    expect(
      buildPositionsCaliberItems({
        tab: "interbank",
        reportDate: "",
        startDate: null,
        endDate: null,
        scopeLabel: "全部产品类型",
        peerFilterLabel: "全部方向 / 未输入对手方",
      }),
    ).toEqual([
      `报表日：${EM_DASH}`,
      `区间：${EM_DASH} ~ ${EM_DASH}`,
      "数据来源：ZQTZ + TYWL",
      "日均分母=有数据 report_date 数",
      "当前：同业持仓",
      "全部产品类型",
      "全部方向 / 未输入对手方",
    ]);
  });
});

describe("formatCoverageSummary", () => {
  it("returns EM_DASH for missing coverage", () => {
    expect(formatCoverageSummary(null)).toBe(EM_DASH);
    expect(formatCoverageSummary(undefined)).toBe(EM_DASH);
  });

  it("shows only the ratio when nothing is missing", () => {
    expect(formatCoverageSummary(coverage({ coverage_ratio: "98.50" }))).toBe("98.50%");
  });

  it("appends missing count and amount when rates are missing", () => {
    expect(
      formatCoverageSummary(
        coverage({ missing_count: 2, missing_amount: "150000000", coverage_ratio: "97.00" }),
      ),
    ).toBe("97.00%，缺 2 笔 / 1.50 亿元");
  });
});

describe("rateCoveragePolicyLabel", () => {
  it("maps the known exclusion policy to its Chinese label", () => {
    expect(rateCoveragePolicyLabel("exclude_missing_rate_from_denominator")).toBe(
      "缺失利率剔除分母",
    );
  });

  it("passes through unknown policies and dashes missing ones", () => {
    expect(rateCoveragePolicyLabel("some_other_policy")).toBe("some_other_policy");
    expect(rateCoveragePolicyLabel(null)).toBe(EM_DASH);
    expect(rateCoveragePolicyLabel("")).toBe(EM_DASH);
  });
});

describe("compactVersion / metaSummary", () => {
  it("truncates versions longer than 18 characters", () => {
    expect(compactVersion("sv_20260101_abcdefgh")).toBe("sv_20260101_abc…");
    expect(compactVersion("short")).toBe("short");
    expect(compactVersion(null)).toBe(EM_DASH);
  });

  it("summarizes quality flag and compacted versions", () => {
    expect(metaSummary(resultMeta())).toBe("ok / sv_test / rv_test");
    expect(
      metaSummary(resultMeta({ source_version: "sv_20260101_abcdefgh" })),
    ).toBe("ok / sv_20260101_abc… / rv_test");
    expect(metaSummary(null)).toBe(EM_DASH);
    expect(metaSummary(undefined)).toBe(EM_DASH);
  });
});

describe("topRatingItem", () => {
  it("returns null for missing or empty items", () => {
    expect(topRatingItem(undefined)).toBeNull();
    expect(topRatingItem([])).toBeNull();
  });

  it("picks the item with the highest numeric percentage", () => {
    const items: RatingStatsResponse["items"] = [
      ratingItem("AA+", "12.5"),
      ratingItem("AAA", "30.1"),
      ratingItem("AA", "7.2"),
    ];
    // "7.2" 字典序大于 "30.1"；数值比较必须选 30.1。
    expect(topRatingItem(items)).toBe(items[1]);
  });
});
