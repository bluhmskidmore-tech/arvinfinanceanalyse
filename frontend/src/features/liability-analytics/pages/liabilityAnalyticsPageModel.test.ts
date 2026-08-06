import { describe, expect, it } from "vitest";

import type { ResultMeta } from "../../../api/contracts";
import { buildLiabilityAnalyticsPageReadModel } from "./liabilityAnalyticsPageModel";

function meta(overrides: Partial<ResultMeta> = {}): ResultMeta {
  return {
    trace_id: "tr_liability",
    basis: "formal",
    result_kind: "liability.test",
    formal_use_allowed: true,
    source_version: "sv_liability",
    vendor_version: "vv_none",
    rule_version: "rv_liability",
    cache_version: "cv_liability",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-04-19T00:00:00Z",
    ...overrides,
  };
}

describe("buildLiabilityAnalyticsPageReadModel", () => {
  it("surfaces mode and visible evidence metadata when all core reads expose result metadata", () => {
    const model = buildLiabilityAnalyticsPageReadModel({
      mode: "real",
      activeTab: "daily",
      requestedReportDate: "2025-12-31",
      resolvedReportDate: "2025-12-31",
      selectedYear: 2026,
      selectedMonthLabel: null,
      yieldKpi: null,
      liabilityTotalYi: 12.34,
      firstYearPressureYi: 5.67,
      topCounterpartyShare: "30.00%",
      warningCount: 1,
      alertCount: 2,
      resultMetas: [
        { key: "knowledge", title: "业务资料", required: false, meta: meta({ result_kind: "liability.page_knowledge" }) },
        { key: "counterparty", title: "对手方集中度", required: true, meta: meta({ result_kind: "liability.counterparty" }) },
      ],
      syntheticSections: [],
    });

    expect(model.statusBadges.map((badge) => badge.label)).toContain("真实链路");
    expect(model.kpis).toHaveLength(6);
    expect(model.kpis.find((kpi) => kpi.key === "warnings")?.value).toBe("3条");
    expect(model.evidenceCards).toHaveLength(2);
    expect(model.evidenceCards[0]?.resultKind).toBe("liability.page_knowledge");
    expect(model.statusBadges.map((badge) => badge.key)).not.toContain("meta-gap");
    expect(model.stateSurfaces.map((surface) => surface.key)).not.toContain("missing-meta");
  });

  it("fails closed to an explicit metadata gap when a core read does not expose result metadata", () => {
    const model = buildLiabilityAnalyticsPageReadModel({
      mode: "real",
      activeTab: "daily",
      requestedReportDate: "2025-12-31",
      resolvedReportDate: "2025-12-31",
      selectedYear: 2026,
      selectedMonthLabel: null,
      yieldKpi: null,
      liabilityTotalYi: 12.34,
      firstYearPressureYi: 5.67,
      topCounterpartyShare: "30.00%",
      warningCount: 0,
      alertCount: 0,
      resultMetas: [
        { key: "risk-buckets", title: "负债期限结构", required: true, meta: null },
        { key: "yield-metrics", title: "负债收益指标", required: true, meta: meta({ result_kind: "liability.yield_metrics" }) },
      ],
      syntheticSections: [],
    });

    expect(model.statusBadges.map((badge) => badge.key)).toContain("meta-gap");
    expect(model.stateSurfaces.map((surface) => surface.key)).toContain("missing-meta");
    expect(model.evidenceCards[0]?.resultKind).toBe("结果元数据未透出");
    expect(model.evidenceCards[0]?.title).toBe("负债期限结构");
  });

  it("does not mark optional reads as a core metadata gap when their metadata is absent", () => {
    const model = buildLiabilityAnalyticsPageReadModel({
      mode: "real",
      activeTab: "daily",
      requestedReportDate: "2025-12-31",
      resolvedReportDate: "2025-12-31",
      selectedYear: 2026,
      selectedMonthLabel: null,
      yieldKpi: null,
      liabilityTotalYi: 12.34,
      firstYearPressureYi: 5.67,
      topCounterpartyShare: "30.00%",
      warningCount: 0,
      alertCount: 0,
      resultMetas: [
        { key: "risk-buckets", title: "负债期限结构", required: true, meta: meta({ result_kind: "liability.risk_buckets" }) },
        { key: "yield-metrics", title: "负债收益指标", required: true, meta: meta({ result_kind: "liability.yield_metrics" }) },
        { key: "counterparty", title: "对手方集中度", required: true, meta: meta({ result_kind: "liability.counterparty" }) },
        { key: "knowledge", title: "业务资料", required: false, meta: null },
      ],
      syntheticSections: [],
    });

    expect(model.statusBadges.map((badge) => badge.key)).not.toContain("meta-gap");
    expect(model.stateSurfaces.map((surface) => surface.key)).not.toContain("missing-meta");
    expect(model.evidenceCards.map((card) => card.title)).not.toContain("业务资料");
  });

  it("marks mock mode, fallback, stale vendor, and date mismatch", () => {
    const model = buildLiabilityAnalyticsPageReadModel({
      mode: "mock",
      activeTab: "daily",
      requestedReportDate: "2025-12-30",
      resolvedReportDate: "2025-12-31",
      selectedYear: 2026,
      selectedMonthLabel: null,
      yieldKpi: null,
      liabilityTotalYi: null,
      firstYearPressureYi: null,
      topCounterpartyShare: "—",
      warningCount: 0,
      alertCount: 0,
      resultMetas: [
        {
          key: "warnings",
          title: "预警",
          required: false,
          meta: meta({
            fallback_mode: "latest_snapshot",
            vendor_status: "vendor_stale",
            as_of_date: "2025-12-31",
          }),
        },
      ],
      syntheticSections: [{ key: "calendar", title: "关键日历", detail: "接口预留" }],
    });

    expect(model.modeBadge.tone).toBe("mock");
    expect(model.statusBadges.map((badge) => badge.key)).toEqual(
      expect.arrayContaining(["mode", "date", "fallback", "stale"]),
    );
    expect(model.stateSurfaces.map((surface) => surface.key)).toEqual(
      expect.arrayContaining(["mock", "date-mismatch", "fallback", "stale", "synthetic-sections"]),
    );
    expect(model.evidenceCards[0]?.fallbackLabel).toBe("latest_snapshot");
  });

  it("builds monthly readout without daily KPI assumptions", () => {
    const model = buildLiabilityAnalyticsPageReadModel({
      mode: "real",
      activeTab: "monthly",
      requestedReportDate: "",
      resolvedReportDate: "",
      selectedYear: 2026,
      selectedMonthLabel: "2026-04",
      yieldKpi: null,
      liabilityTotalYi: null,
      firstYearPressureYi: null,
      topCounterpartyShare: "—",
      warningCount: 0,
      alertCount: 0,
      resultMetas: [
        { key: "liabilities-monthly", title: "负债月度日均", required: true, meta: meta({ result_kind: "liability_analytics.monthly" }) },
        { key: "adb-monthly", title: "ADB 月度日均", required: true, meta: meta({ result_kind: "adb.monthly" }) },
      ],
      syntheticSections: [],
    });

    expect(model.reportLine).toBe("2026 年 · 2026-04（月度日均）");
    expect(model.evidenceCards.map((card) => card.title)).toEqual(["负债月度日均", "ADB 月度日均"]);
    expect(model.kpis).toEqual([
      { key: "year", label: "统计年份", value: "2026", detail: "月度日均口径" },
      { key: "month", label: "当前月份", value: "2026-04", detail: "按月选择" },
    ]);
  });
});
