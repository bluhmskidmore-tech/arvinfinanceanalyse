import { describe, expect, it } from "vitest";

import type { Numeric, ResultMeta, ResearchCalendarEvent, VerdictPayload } from "../../../api/contracts";
import type { DashboardOverviewMetricVM } from "../../executive-dashboard/adapters/executiveDashboardAdapter";
import {
  buildDashboardHomeAlerts,
  buildDashboardHomeFocusItems,
  buildDashboardHomeHeroMetrics,
  buildDashboardHomeJudgment,
  buildDashboardHomeKpiRibbon,
  buildDashboardHomeModel,
  buildDashboardHomeSnapshotPartialNote,
  collectDashboardAttentionItems,
  resolveDashboardHomeEffectiveReportDate,
} from "./dashboardHomeModel";

function numeric(partial: Partial<Numeric> = {}): Numeric {
  return {
    raw: 0,
    unit: "yuan",
    display: "0.00",
    precision: 2,
    sign_aware: false,
    ...partial,
  };
}

function overviewMetric(partial: Partial<DashboardOverviewMetricVM>): DashboardOverviewMetricVM {
  return {
    id: partial.id ?? "metric-1",
    label: partial.label ?? "Overview metric",
    caliberLabel: partial.caliberLabel ?? null,
    value: partial.value ?? numeric({ display: "1.00" }),
    delta: partial.delta ?? numeric({ display: "-1.00" }),
    tone: partial.tone ?? "neutral",
    detail: partial.detail ?? "Detail text",
    history: partial.history ?? null,
    ...partial,
  };
}

function resultMeta(overrides: Partial<ResultMeta> = {}): ResultMeta {
  return {
    trace_id: "trace-id",
    basis: "formal",
    result_kind: "k",
    formal_use_allowed: true,
    source_version: "sv",
    vendor_version: "vv",
    rule_version: "rv",
    cache_version: "cv",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function calendarEvent(overrides: Partial<ResearchCalendarEvent> = {}): ResearchCalendarEvent {
  return {
    id: overrides.id ?? "event-1",
    date: overrides.date ?? "2026-01-01",
    kind: overrides.kind ?? "macro",
    title: overrides.title ?? "Calendar event",
    severity: overrides.severity ?? "high",
    ...overrides,
  };
}

describe("dashboardHomeModel helpers", () => {
  it("resolves effective report date with snapshot date taking precedence over requested date", () => {
    expect(
      resolveDashboardHomeEffectiveReportDate({
        snapshotReportDate: "2026-02-01",
        requestedReportDate: "2026-01-01",
      }),
    ).toBe("2026-02-01");

    expect(
      resolveDashboardHomeEffectiveReportDate({
        requestedReportDate: "2026-01-01",
      }),
    ).toBe("2026-01-01");

    expect(resolveDashboardHomeEffectiveReportDate({})).toBe("");
  });

  it("preserves zero display values and only falls back delta when missing", () => {
    const hero = buildDashboardHomeHeroMetrics({
      metrics: [
        overviewMetric({
          id: "m-0",
          value: numeric({ display: "0.00" }),
          delta: numeric({ display: "" }),
          tone: "negative",
        }),
      ],
    });

    expect(hero).toHaveLength(1);
    expect(hero[0]).toBeDefined();
    expect(hero[0]!.value).toBe("0.00");
    expect(hero[0]!.delta).toBe("N/A");
  });

  it("collects attention items only when meta is degraded", () => {
    const healthy = collectDashboardAttentionItems({
      overviewMeta: resultMeta(),
      attributionMeta: resultMeta(),
    });
    const degraded = collectDashboardAttentionItems({
      overviewMeta: resultMeta({
        quality_flag: "stale",
        fallback_mode: "latest_snapshot",
        vendor_status: "vendor_stale",
      }),
      attributionMeta: resultMeta({ quality_flag: "ok", fallback_mode: "none", vendor_status: "ok" }),
    });

    expect(healthy).toEqual([]);
    expect(degraded).toHaveLength(1);
    expect(degraded[0]).toContain("overview");
  });

  it("builds snapshot partial note from mode or missing domains", () => {
    expect(
      buildDashboardHomeSnapshotPartialNote({
        snapshotMode: "partial",
      }),
    ).toBe("快照覆盖不完整");
    expect(
      buildDashboardHomeSnapshotPartialNote({
        domainsMissing: ["Macro", "Auction"],
      }),
    ).toBe("快照含缺域：Macro, Auction");
  });

  it("builds warning-level KPI ribbon for partial data and mock source", () => {
    const pills = buildDashboardHomeKpiRibbon({
      effectiveReportDate: "2026-01-01",
      snapshotMode: "strict",
      snapshotLoading: false,
      snapshotPartialNote: "Partial snapshot: missing Macro",
      attentionCount: 2,
      isMockMode: true,
    });

    expect(pills).toHaveLength(4);
    expect(pills[0]?.value).toBe("2026-01-01");
    expect(pills[1]?.value).toBe("含缺域");
    expect(pills[1]?.tone).toBe("warning");
    expect(pills[2]?.tone).toBe("warning");
    expect(pills[3]?.value).toBe("模拟");
    expect(pills[3]?.tone).toBe("warning");
  });

  it("switches judgment into warning mode when attention or partial snapshot exists", () => {
    const escalated = buildDashboardHomeJudgment({
      baseVerdict: null,
      isMockMode: true,
      hasAttention: false,
      hasSnapshotPartial: false,
    });
    const normal = buildDashboardHomeJudgment({
      baseVerdict: {
        conclusion: "All systems healthy",
        tone: "positive",
        reasons: [],
        suggestions: [],
      } as VerdictPayload,
      isMockMode: false,
      hasAttention: false,
      hasSnapshotPartial: false,
    });

    expect(escalated.tone).toBe("warning");
    expect(escalated.conclusion).toContain("数据状态");
    expect(normal.tone).toBe("positive");
    expect(normal.conclusion).toBe("All systems healthy");
  });

  it("limits alerts by max alert count and metric alert cap without inventing values", () => {
    const alerts = buildDashboardHomeAlerts({
      metrics: [
        overviewMetric({ id: "warning", tone: "warning", value: numeric({ display: "1" }), detail: "m1" }),
        overviewMetric({ id: "negative", tone: "negative", value: numeric({ display: "-2" }), detail: "m2" }),
      ],
      isMockMode: false,
      attentionItems: ["attn-1", "attn-2", "attn-3"],
      snapshotPartialNote: null,
      maxAlerts: 4,
      metricAlertLimit: 1,
    });

    expect(alerts).toHaveLength(4);
    expect(alerts[0]).toMatchObject({ id: "attention-0", severity: "high" });
    expect(alerts[1]).toMatchObject({ id: "attention-1", severity: "high" });
    expect(alerts[2]).toMatchObject({ id: "attention-2", severity: "high" });
    expect(alerts[3]).toMatchObject({ id: "metric-warning", severity: "medium" });
  });

  it("maps alerts and calendar items into focus with item caps", () => {
    const focus = buildDashboardHomeFocusItems({
      alerts: [
        { id: "a1", title: "A", detail: "A", severity: "medium" },
        { id: "a2", title: "B", detail: "B", severity: "low" },
        { id: "a3", title: "C", detail: "C", severity: "high" },
      ],
      calendarEvents: [
        calendarEvent({ id: "e1", date: "2026-01-02", severity: "high", title: "Early", kind: "macro" }),
        calendarEvent({ id: "e2", date: "2026-01-01", severity: "medium", title: "First", kind: "auction" }),
        calendarEvent({ id: "e3", date: "2026-01-03", severity: "low", title: "Late", kind: "auction" }),
      ],
      calendarIsLoading: false,
      calendarIsError: false,
      focusTaskLimit: 2,
      calendarLimit: 2,
    });

    expect(focus.tasks).toHaveLength(2);
    expect(focus.calendarItems.map((item) => item.id)).toEqual(["e2", "e1"]);
    expect(focus.calendarState.status).toBe("ready");
    expect(focus.calendarState.message).toBeNull();
  });
});

describe("buildDashboardHomeModel", () => {
  it("composes a compact cockpit model with null/empty inputs and no synthetic business values", () => {
    const output = buildDashboardHomeModel({
      metrics: null,
      baseVerdict: null,
      isSnapshotLoading: true,
      calendarEvents: [],
      calendarIsLoading: false,
      calendarIsError: false,
      isMockMode: false,
    });

    expect(output.effectiveReportDate).toBe("");
    expect(output.attentionItems).toEqual([]);
    expect(output.snapshotPartialNote).toBeNull();
    expect(output.heroMetrics).toEqual([]);
    expect(output.alerts).toEqual([]);
    expect(output.focus.tasks).toEqual([]);
    expect(output.focus.calendarItems).toEqual([]);
    expect(output.focus.calendarState.status).toBe("no-data");
    expect(output.judgment.tone).toBe("neutral");
  });

  it("classifies first-screen, supplemental, and reserved dashboard sections", () => {
    const output = buildDashboardHomeModel({
      metrics: [overviewMetric({ id: "aum", label: "资产规模" })],
      baseVerdict: null,
      overviewMeta: resultMeta(),
      attributionMeta: resultMeta(),
      requestedReportDate: "",
      snapshotReportDate: "2026-04-08",
      snapshotMode: "strict",
      snapshotDomainsMissing: [],
      coreMetricsReportDate: "2026-04-07",
      dailyChangesReportDate: "2026-04-08",
      isSnapshotLoading: false,
      calendarEvents: [],
      calendarIsLoading: false,
      calendarIsError: false,
      isMockMode: false,
    });

    expect(output.meta.reportDate).toBe("2026-04-08");
    expect(output.sections).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          id: "judgment",
          status: "landed",
          firstScreenAllowed: true,
        }),
        expect.objectContaining({
          id: "overview_metrics",
          status: "landed",
          firstScreenAllowed: true,
        }),
        expect.objectContaining({
          id: "core_metrics",
          status: "blocked",
          firstScreenAllowed: false,
        }),
        expect.objectContaining({
          id: "daily_changes",
          status: "supplemental",
          firstScreenAllowed: false,
        }),
        expect.objectContaining({
          id: "risk_overview",
          status: "reserved",
          firstScreenAllowed: false,
        }),
        expect.objectContaining({
          id: "market_context",
          status: "supplemental",
          firstScreenAllowed: false,
        }),
      ]),
    );
    expect(output.hiddenOrReservedSections.map((section) => section.id)).toEqual(
      expect.arrayContaining(["core_metrics", "market_context", "risk_overview"]),
    );
  });
});
