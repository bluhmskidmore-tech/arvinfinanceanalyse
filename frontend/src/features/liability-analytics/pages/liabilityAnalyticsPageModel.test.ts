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
  it("surfaces mode, evidence meta, and compatibility meta gaps", () => {
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
      resultMetas: [{ key: "knowledge", title: "业务资料", meta: meta({ result_kind: "liability.page_knowledge" }) }],
      unwrappedEvidenceLabels: ["risk-buckets", "yield-metrics"],
      syntheticSections: [],
    });

    expect(model.statusBadges.map((badge) => badge.label)).toContain("真实链路");
    expect(model.statusBadges.map((badge) => badge.label)).toContain("2 个兼容端点缺少可见 meta");
    expect(model.kpis).toHaveLength(6);
    expect(model.kpis.find((kpi) => kpi.key === "warnings")?.value).toBe("3条");
    expect(model.evidenceCards).toHaveLength(3);
    expect(model.evidenceCards[0]?.resultKind).toBe("liability.page_knowledge");
    expect(model.stateSurfaces.map((surface) => surface.key)).toContain("missing-meta");
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
          meta: meta({
            fallback_mode: "latest_snapshot",
            vendor_status: "vendor_stale",
            as_of_date: "2025-12-31",
          }),
        },
      ],
      unwrappedEvidenceLabels: [],
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
      resultMetas: [],
      unwrappedEvidenceLabels: ["liabilities monthly"],
      syntheticSections: [],
    });

    expect(model.reportLine).toBe("2026 年 · 2026-04 · 月度日均");
    expect(model.kpis).toEqual([
      { key: "year", label: "统计年份", value: "2026", detail: "月度日均口径" },
      { key: "month", label: "当前月份", value: "2026-04", detail: "按月选择" },
    ]);
  });
});
