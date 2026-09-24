import { describe, expect, it } from "vitest";

import type {
  ApiEnvelope,
  BondDashboardBundlePayload,
  BondDashboardHeadlinePayload,
  ResultMeta,
  RiskIndicatorsPayload,
} from "../../../api/contracts";
import { EM_DASH } from "../../../pageModel";
import { formatRawAsNumeric } from "../../../utils/format";
import { BOND_DASHBOARD_PAGE_BUNDLE_SECTIONS } from "../bondDashboardBundleModel";
import {
  buildBondDashboardCaliberItems,
  buildBondDashboardKpiBand,
  buildBondDashboardScreenNotices,
  buildBondDashboardSectionStatusItems,
  buildDashboardConclusion,
  businessTypeMetricNumber,
  describeFirstScreenMetaFallback,
} from "./bondDashboardPageModel";

const yuan = (raw: number | null) => formatRawAsNumeric({ raw, unit: "yuan", sign_aware: false });
const pct = (raw: number | null) => formatRawAsNumeric({ raw, unit: "pct", sign_aware: false });
const ratio = (raw: number | null) => formatRawAsNumeric({ raw, unit: "ratio", sign_aware: false });
const dv01 = (raw: number | null) => formatRawAsNumeric({ raw, unit: "dv01", sign_aware: false });
const years = (raw: number | null) => formatRawAsNumeric({ raw, unit: "years", sign_aware: false });

function resultMeta(overrides: Partial<ResultMeta> = {}): ResultMeta {
  return {
    trace_id: "tr_test",
    basis: "formal",
    result_kind: "bond_dashboard.headline_kpis",
    formal_use_allowed: true,
    source_version: "sv",
    vendor_version: "vv",
    rule_version: "rv",
    cache_version: "cv",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-04-30T00:00:00Z",
    ...overrides,
  };
}

function prevKpisFixture(): NonNullable<BondDashboardHeadlinePayload["prev_kpis"]> {
  return {
    total_market_value: yuan(1_000_000_000),
    unrealized_pnl: yuan(50_000_000),
    weighted_ytm: pct(0.024),
    weighted_duration: years(4),
    weighted_coupon: pct(0.03),
    credit_spread_median: pct(null),
    total_dv01: dv01(1_200_000),
    bond_count: 120,
  };
}

function headlineFixture(
  overrides: Partial<BondDashboardHeadlinePayload> = {},
): BondDashboardHeadlinePayload {
  return {
    report_date: "2026-04-30",
    prev_report_date: "2026-03-31",
    kpis: {
      total_market_value: yuan(1_250_000_000),
      unrealized_pnl: yuan(50_100_000),
      weighted_ytm: pct(0.025),
      weighted_duration: years(3.5),
      weighted_coupon: pct(0.03),
      credit_spread_median: pct(0.005),
      total_dv01: dv01(1_234_000),
      bond_count: 128,
    },
    prev_kpis: prevKpisFixture(),
    ...overrides,
  };
}

function riskFixture(overrides: Partial<RiskIndicatorsPayload> = {}): RiskIndicatorsPayload {
  return {
    report_date: "2026-04-30",
    total_market_value: yuan(1_250_000_000),
    total_dv01: dv01(1_234_000),
    weighted_duration: years(3.5),
    credit_ratio: ratio(0.62),
    weighted_convexity: ratio(0.8),
    total_spread_dv01: dv01(600_000),
    reinvestment_ratio_1y: ratio(0.2),
    ...overrides,
  };
}

function bundleEnvelope(
  result: Partial<BondDashboardBundlePayload> = {},
): ApiEnvelope<BondDashboardBundlePayload> {
  return {
    result_meta: resultMeta({ result_kind: "bond_dashboard.bundle" }),
    result: {
      report_date: "2026-04-30",
      requested_sections: [...BOND_DASHBOARD_PAGE_BUNDLE_SECTIONS],
      sections: {},
      ...result,
    },
  };
}

const KPI_KEY_ORDER = [
  "total_market_value",
  "unrealized_pnl",
  "weighted_ytm",
  "weighted_duration",
  "weighted_coupon",
  "credit_spread_median",
  "total_dv01",
  "bond_count",
];

describe("describeFirstScreenMetaFallback", () => {
  it("healthy meta 返回 null", () => {
    const meta = resultMeta({
      requested_report_date: "2026-04-30",
      resolved_report_date: "2026-04-30",
    });
    expect(describeFirstScreenMetaFallback("首屏指标", meta, "2026-04-30")).toBeNull();
  });

  it("meta 未提供时返回 null", () => {
    expect(describeFirstScreenMetaFallback("首屏指标", undefined, "2026-04-30")).toBeNull();
  });

  it("quality 非 ok 且 resolved 与请求日一致时补实际数据日期", () => {
    const meta = resultMeta({
      quality_flag: "warning",
      requested_report_date: "2026-04-30",
      resolved_report_date: "2026-04-30",
    });
    expect(describeFirstScreenMetaFallback("首屏指标", meta, "2026-04-30")).toBe(
      "首屏指标：供数质量 warning；实际数据日期 2026-04-30",
    );
  });

  it("请求日回退与 fallback_date 组合文案按固定顺序拼接", () => {
    const meta = resultMeta({
      requested_report_date: "2026-04-30",
      resolved_report_date: "2026-04-29",
      fallback_date: "2026-04-29",
    });
    expect(describeFirstScreenMetaFallback("首屏指标", meta, null)).toBe(
      "首屏指标：请求日 2026-04-30 回退至 2026-04-29；回退日期 2026-04-29",
    );
  });

  it("仅 fallback_date 降级时输出回退日期并补实际数据日期", () => {
    const meta = resultMeta({
      requested_report_date: "2026-04-30",
      resolved_report_date: "2026-04-30",
      fallback_date: "2026-04-28",
    });
    expect(describeFirstScreenMetaFallback("首屏指标", meta, "2026-04-30")).toBe(
      "首屏指标：回退日期 2026-04-28；实际数据日期 2026-04-30",
    );
  });

  it("meta 无请求日时回落到页面请求日判定日期回退", () => {
    const meta = resultMeta({ resolved_report_date: "2026-04-29" });
    expect(describeFirstScreenMetaFallback("风险指标", meta, "2026-04-30")).toBe(
      "风险指标：请求日 2026-04-30 回退至 2026-04-29",
    );
  });
});

describe("buildDashboardConclusion", () => {
  it("完整数据输出规模/久期/信用结论", () => {
    expect(buildDashboardConclusion(headlineFixture(), riskFixture())).toEqual({
      title: "当前结论",
      body: "组合规模约 12.50 亿元，久期约 3.50 年，信用仓位偏高。",
      detail: "当前信用占比 62.0%，总市值处于已投放状态。",
    });
  });

  it("total_market_value 为 null 时不形成投放状态结论", () => {
    const base = headlineFixture();
    const headline: BondDashboardHeadlinePayload = {
      ...base,
      kpis: { ...base.kpis, total_market_value: yuan(null) },
    };
    const conclusion = buildDashboardConclusion(headline, riskFixture());
    expect(conclusion.body).toContain(`组合规模约 ${EM_DASH}`);
    expect(conclusion.detail).toContain("不形成投放状态结论");
    expect(conclusion.detail).not.toContain("尚未形成有效持仓");
  });

  it("total_market_value 为 0 时给出尚未形成有效持仓", () => {
    const base = headlineFixture();
    const headline: BondDashboardHeadlinePayload = {
      ...base,
      kpis: { ...base.kpis, total_market_value: yuan(0) },
    };
    const conclusion = buildDashboardConclusion(headline, riskFixture());
    expect(conclusion.detail).toContain("总市值尚未形成有效持仓");
  });

  it("credit_ratio 为 null 时信用仓位与占比均为 EM_DASH", () => {
    const conclusion = buildDashboardConclusion(
      headlineFixture(),
      riskFixture({ credit_ratio: ratio(null) }),
    );
    expect(conclusion.body).toContain(`信用仓位 ${EM_DASH}`);
    expect(conclusion.detail).toContain(`当前信用占比 ${EM_DASH}`);
  });

  it("creditRatio 按 0.5/0.3 阈值分三档", () => {
    const bodyFor = (raw: number) =>
      buildDashboardConclusion(headlineFixture(), riskFixture({ credit_ratio: ratio(raw) })).body;
    expect(bodyFor(0.5)).toContain("信用仓位偏高");
    expect(bodyFor(0.3)).toContain("信用仓位适中");
    expect(bodyFor(0.2)).toContain("利率债占比更高");
  });

  it("headline 或 risk 缺失时输出待载入分支", () => {
    const pending = {
      title: "当前结论",
      body: "债券驾驶舱结论待载入，先确认报告日与正式读链路状态。",
      detail: "首屏结论会基于持仓规模、久期和信用占比同步更新。",
    };
    expect(buildDashboardConclusion(undefined, riskFixture())).toEqual(pending);
    expect(buildDashboardConclusion(headlineFixture(), undefined)).toEqual(pending);
  });
});

describe("buildBondDashboardKpiBand", () => {
  it("完整 headline 输出 8 格且顺序/数值/环比正确", () => {
    const band = buildBondDashboardKpiBand({ headline: headlineFixture(), loading: false });
    expect(band.loading).toBe(false);
    expect(band.cells.map((cell) => cell.key)).toEqual(KPI_KEY_ORDER);
    expect(band.cells.map((cell) => cell.label)).toEqual([
      "债券持仓规模",
      "未实现损益",
      "加权到期收益率",
      "加权久期",
      "加权票息率",
      "信用债收益率中位数",
      "DV01合计",
      "持仓只数",
    ]);

    const byKey = new Map(band.cells.map((cell) => [cell.key, cell]));
    expect(byKey.get("total_market_value")).toMatchObject({
      value: "12.50",
      unit: "亿",
      mom: "+25.00%",
      momTone: "up",
      note: "环比基准 2026-03-31",
    });
    // amountYi 的 "+0.00 亿"（微小正差）按现网行为判 up。
    expect(byKey.get("unrealized_pnl")).toMatchObject({
      value: "0.50",
      unit: "亿",
      mom: "+0.00 亿",
      momTone: "up",
    });
    expect(byKey.get("weighted_ytm")).toMatchObject({
      value: "2.50",
      unit: "%",
      mom: "+10.0bp",
      momTone: "up",
    });
    expect(byKey.get("weighted_duration")).toMatchObject({
      value: "3.50",
      unit: "年",
      mom: "-12.50%",
      momTone: "down",
    });
    expect(byKey.get("weighted_coupon")).toMatchObject({
      value: "3.00",
      unit: "%",
      mom: "0.0bp",
      momTone: "flat",
    });
    expect(byKey.get("credit_spread_median")).toMatchObject({
      value: "0.50",
      unit: "%",
      mom: null,
      momTone: "none",
    });
    expect(byKey.get("total_dv01")).toMatchObject({
      value: "123.40",
      unit: "万元/bp",
      mom: "+2.83%",
      momTone: "up",
    });
    expect(byKey.get("bond_count")).toMatchObject({
      value: "128",
      unit: "只",
      mom: "+8 只",
      momTone: "up",
    });
  });

  it("仅规模格携带环比基准披露", () => {
    const { cells } = buildBondDashboardKpiBand({ headline: headlineFixture(), loading: false });
    expect(cells[0].note).toBe("环比基准 2026-03-31");
    expect(cells.slice(1).every((cell) => cell.note === undefined)).toBe(true);
  });

  it("bond_count 环比按整数差给出三态", () => {
    const withPrevCount = (bondCount: number): BondDashboardHeadlinePayload => ({
      ...headlineFixture(),
      prev_kpis: { ...prevKpisFixture(), bond_count: bondCount },
    });
    const cellFor = (bondCount: number) =>
      buildBondDashboardKpiBand({ headline: withPrevCount(bondCount), loading: false }).cells[7];
    expect(cellFor(120)).toMatchObject({ mom: "+8 只", momTone: "up" });
    expect(cellFor(130)).toMatchObject({ mom: "-2 只", momTone: "down" });
    expect(cellFor(128)).toMatchObject({ mom: "0 只", momTone: "flat" });
  });

  it("prev_kpis 为 null 时环比全部为 null 且无披露", () => {
    const headline: BondDashboardHeadlinePayload = {
      ...headlineFixture(),
      prev_report_date: null,
      prev_kpis: null,
    };
    const { cells } = buildBondDashboardKpiBand({ headline, loading: false });
    expect(cells.every((cell) => cell.mom === null && cell.momTone === "none")).toBe(true);
    expect(cells[0].note).toBeUndefined();
    expect(cells[0].value).toBe("12.50");
    expect(cells[7].value).toBe("128");
    expect(cells[7].unit).toBe("只");
  });

  it("KPI 缺失时 value 为 EM_DASH 且 unit 置 null", () => {
    const base = headlineFixture();
    const headline: BondDashboardHeadlinePayload = {
      ...base,
      kpis: { ...base.kpis, total_market_value: yuan(null) },
    };
    const { cells } = buildBondDashboardKpiBand({ headline, loading: false });
    expect(cells[0].value).toBe(EM_DASH);
    expect(cells[0].unit).toBeNull();
    expect(cells[0].mom).toBeNull();
    expect(cells[0].momTone).toBe("none");
    expect(cells[0].note).toBe("环比基准 2026-03-31");
  });

  it("headline 未载入时输出 8 个占位格并透传 loading", () => {
    const band = buildBondDashboardKpiBand({ headline: undefined, loading: true });
    expect(band.loading).toBe(true);
    expect(band.cells.map((cell) => cell.key)).toEqual(KPI_KEY_ORDER);
    for (const cell of band.cells) {
      expect(cell.value).toBe(EM_DASH);
      expect(cell.unit).toBeNull();
      expect(cell.mom).toBeNull();
      expect(cell.momTone).toBe("none");
      expect(cell.note).toBeUndefined();
    }
  });
});

describe("buildBondDashboardCaliberItems", () => {
  it("bond_analytics_facts 输出口径差异原文", () => {
    expect(
      buildBondDashboardCaliberItems({
        reportDate: "2026-04-30",
        prevReportDate: "2026-03-31",
        dataSource: "bond_analytics_facts",
      }),
    ).toEqual([
      "报告日：2026-04-30",
      "环比基准：2026-03-31",
      "数据来源：债券分析事实表（与余额分析页可能存在口径差异）",
    ]);
  });

  it("其他非空 dataSource 输出通用来源条目", () => {
    expect(
      buildBondDashboardCaliberItems({
        reportDate: "2026-04-30",
        prevReportDate: "2026-03-31",
        dataSource: "balance_ledger",
      }),
    ).toEqual(["报告日：2026-04-30", "环比基准：2026-03-31", "数据来源：balance_ledger"]);
  });

  it("dataSource 未提供时省略来源条目且空日期显示 EM_DASH", () => {
    expect(
      buildBondDashboardCaliberItems({ reportDate: "", prevReportDate: null, dataSource: undefined }),
    ).toEqual([`报告日：${EM_DASH}`, `环比基准：${EM_DASH}`]);
  });
});

describe("buildBondDashboardScreenNotices", () => {
  it("全部正常时返回空数组", () => {
    expect(
      buildBondDashboardScreenNotices({
        datesError: false,
        datesEmpty: false,
        bundleError: false,
        fallbackNotices: [],
      }),
    ).toEqual([]);
  });

  it("datesError 输出报告日加载失败", () => {
    expect(
      buildBondDashboardScreenNotices({
        datesError: true,
        datesEmpty: false,
        bundleError: false,
        fallbackNotices: [],
      }),
    ).toEqual([
      {
        key: "dates-error",
        kind: "error",
        title: "报告日加载失败",
        description: "当前无法获取债券驾驶舱可用报告日，请稍后重试。",
      },
    ]);
  });

  it("datesEmpty 输出暂无可用报告日", () => {
    expect(
      buildBondDashboardScreenNotices({
        datesError: false,
        datesEmpty: true,
        bundleError: false,
        fallbackNotices: [],
      }),
    ).toEqual([
      {
        key: "dates-empty",
        kind: "info",
        title: "暂无可用报告日",
        description: "债券驾驶舱当前没有可读的正式报告日，因此首屏模块不展示业务结论。",
      },
    ]);
  });

  it("bundleError 输出聚合数据加载失败", () => {
    expect(
      buildBondDashboardScreenNotices({
        datesError: false,
        datesEmpty: false,
        bundleError: true,
        fallbackNotices: [],
      }),
    ).toEqual([
      {
        key: "bundle-error",
        kind: "error",
        title: "债券总览数据加载失败",
        description: "当前无法获取债券总览聚合数据，请稍后重试。",
      },
    ]);
  });

  it("fallbackNotices 非空时输出 stale 且按句号拼接", () => {
    expect(
      buildBondDashboardScreenNotices({
        datesError: false,
        datesEmpty: false,
        bundleError: false,
        fallbackNotices: ["首屏指标：供数质量 warning", "风险指标：回退日期 2026-04-28"],
      }),
    ).toEqual([
      {
        key: "stale",
        kind: "warning",
        title: "首屏数据为回退/降级口径",
        description:
          "首屏指标：供数质量 warning。风险指标：回退日期 2026-04-28。下方 KPI 与结论基于上述回退数据，请以实际数据日期为准。",
      },
    ]);
  });

  it("组合触发时顺序固定 dates-error → dates-empty → bundle-error → stale", () => {
    const notices = buildBondDashboardScreenNotices({
      datesError: true,
      datesEmpty: true,
      bundleError: true,
      fallbackNotices: ["首屏指标：供数质量 warning"],
    });
    expect(notices.map((notice) => notice.key)).toEqual([
      "dates-error",
      "dates-empty",
      "bundle-error",
      "stale",
    ]);
  });
});

describe("buildBondDashboardSectionStatusItems", () => {
  it("bundle 未提供时返回空数组", () => {
    expect(buildBondDashboardSectionStatusItems(undefined)).toEqual([]);
  });

  it("无 section_statuses 且无 failed_sections 时返回空数组", () => {
    expect(buildBondDashboardSectionStatusItems(bundleEnvelope())).toEqual([]);
  });

  it("按页面分区顺序映射状态与中文名", () => {
    const bundle = bundleEnvelope({
      section_statuses: {
        "risk-indicators": { status: "ok", message: null, duration_ms: 12 },
        "headline-kpis": { status: "ok", message: null, duration_ms: 34 },
        "business-type-metrics": { status: "error", message: "boom", duration_ms: 5 },
      },
    });
    const items = buildBondDashboardSectionStatusItems(bundle);
    expect(items).toEqual([
      { section: "headline-kpis", label: "首屏指标", status: "ok", message: null, durationMs: 34 },
      { section: "risk-indicators", label: "风险指标", status: "ok", message: null, durationMs: 12 },
      {
        section: "business-type-metrics",
        label: "业务类型指标",
        status: "error",
        message: "boom",
        durationMs: 5,
      },
    ]);
  });

  it("failed_sections 缺失 status 的分区补 error 条目", () => {
    const bundle = bundleEnvelope({
      section_statuses: { "headline-kpis": { status: "ok", message: null, duration_ms: 8 } },
      failed_sections: ["spread-analysis"],
    });
    expect(buildBondDashboardSectionStatusItems(bundle)).toEqual([
      { section: "headline-kpis", label: "首屏指标", status: "ok", message: null, durationMs: 8 },
      { section: "spread-analysis", label: "利差分析", status: "error", message: null, durationMs: null },
    ]);
  });

  it("failed_sections 与 section_statuses 重叠时不重复且保留原 message", () => {
    const bundle = bundleEnvelope({
      section_statuses: {
        "yield-distribution": { status: "error", message: "上游超时", duration_ms: 30 },
      },
      failed_sections: ["yield-distribution"],
    });
    expect(buildBondDashboardSectionStatusItems(bundle)).toEqual([
      {
        section: "yield-distribution",
        label: "收益率分布",
        status: "error",
        message: "上游超时",
        durationMs: 30,
      },
    ]);
  });

  it("未知 section id 原样透出并附在既定顺序之后", () => {
    const bundle = bundleEnvelope({
      section_statuses: {
        "top-holdings": { status: "ok", message: null, duration_ms: 3 },
        "headline-kpis": { status: "ok", message: null, duration_ms: 6 },
      },
    });
    const items = buildBondDashboardSectionStatusItems(bundle);
    expect(items.map((item) => item.section)).toEqual(["headline-kpis", "top-holdings"]);
    expect(items[1]).toEqual({
      section: "top-holdings",
      label: "top-holdings",
      status: "ok",
      message: null,
      durationMs: 3,
    });
  });
});

describe("businessTypeMetricNumber", () => {
  it("null/undefined/空串/空白串归一为 null", () => {
    expect(businessTypeMetricNumber(null)).toBeNull();
    expect(businessTypeMetricNumber(undefined)).toBeNull();
    expect(businessTypeMetricNumber("")).toBeNull();
    expect(businessTypeMetricNumber("   ")).toBeNull();
  });

  it("后端的 \"0.00000000\" 保留为真实零", () => {
    expect(businessTypeMetricNumber("0.00000000")).toBe(0);
  });

  it("非数字串返回 null", () => {
    expect(businessTypeMetricNumber("abc")).toBeNull();
    expect(businessTypeMetricNumber("1,234")).toBeNull();
  });

  it("数字串与数字正常解析", () => {
    expect(businessTypeMetricNumber("12.5")).toBe(12.5);
    expect(businessTypeMetricNumber("-4.2")).toBe(-4.2);
    expect(businessTypeMetricNumber(3)).toBe(3);
  });
});
