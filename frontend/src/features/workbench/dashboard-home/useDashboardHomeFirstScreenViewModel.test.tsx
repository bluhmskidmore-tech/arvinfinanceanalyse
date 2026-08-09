import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { createApiClient } from "../../../api/client";
import type { Numeric, ResultMeta } from "../../../api/contracts";

const boundaryMock = vi.hoisted(() => ({ current: null as unknown }));

vi.mock("../pages/useDashboardSnapshotBoundary", () => ({
  useDashboardSnapshotBoundary: () => boundaryMock.current,
}));

vi.mock("./useMockHomeFirstScreenView", () => ({
  useMockHomeFirstScreenView: () => null,
}));

import { useDashboardHomeFirstScreenViewModel } from "./useDashboardHomeFirstScreenViewModel";

function numeric(
  raw: number | null,
  display: string,
  unit: Numeric["unit"] = "yuan",
  signAware = true,
  precision = 2,
): Numeric {
  return {
    raw,
    unit,
    display,
    precision,
    sign_aware: signAware,
  };
}

function homeSnapshotMeta(overrides: Partial<ResultMeta> = {}): ResultMeta {
  return {
    trace_id: "trace-home",
    basis: "formal",
    result_kind: "home.snapshot",
    formal_use_allowed: true,
    source_version: "sv_home_snapshot_test",
    vendor_version: "vv_none",
    rule_version: "rv_home_snapshot_test",
    cache_version: "cv_home_snapshot_test",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-04-30T16:00:00Z",
    filters_applied: {},
    ...overrides,
  };
}

describe("useDashboardHomeFirstScreenViewModel report date", () => {
  beforeEach(() => {
    boundaryMock.current = {
      dataClient: { ...createApiClient({ mode: "mock" }), mode: "real" },
      isLiveDataFallback: false,
      adapterOutput: {
        overview: { vm: null, state: { kind: "empty" }, meta: null },
        attribution: { vm: null, state: { kind: "empty" }, meta: null },
        verdict: null,
        domainsEffectiveDate: {},
        domainsMissing: [],
        productCategoryHeadline: { state: "empty", metrics: [] },
        datesDiverged: false,
      },
      snapshotResult: undefined,
      snapshotMeta: null,
      initialEffectiveReportDate: "",
      reportDateDataWarning: null,
      snapshotQuery: {
        isError: false,
        isFetching: false,
      },
      refreshSnapshot: vi.fn(),
    };
  });

  it("keeps an empty snapshot empty instead of backfilling today or the requested date", () => {
    const { result } = renderHook(() => useDashboardHomeFirstScreenViewModel());

    expect(result.current.effectiveReportDate).toBe("");
    expect(result.current.view.reportDate).toBe("—");
    expect(result.current.view.reportDateContext.mode).toBe("empty");
    expect(result.current.view.headerStatus.dataStatusKind).not.toBe("ok");

    act(() => {
      result.current.setReportDate("2026-04-18");
    });

    expect(result.current.effectiveReportDate).toBe("");
    expect(result.current.view.reportDateContext.actualDataDate).toBe("");
    expect(result.current.view.reportDateContext.mode).toBe("empty");
    expect(result.current.view.headerStatus.formalUseAllowed).toBeNull();
    expect(result.current.view.headerStatus.governanceFeedAvailable).toBe(false);
  });

  it("keeps analytical usage separate from an otherwise healthy data-quality state", () => {
    boundaryMock.current = {
      ...(boundaryMock.current as Record<string, unknown>),
      adapterOutput: {
        ...(boundaryMock.current as { adapterOutput: Record<string, unknown> }).adapterOutput,
        productCategoryHeadline: { state: "ready", metrics: [] },
      },
      snapshotResult: {
        report_date: "2026-06-30",
        mode: "strict",
        domains_missing: [],
      },
      snapshotMeta: {
        basis: "analytical",
        formal_use_allowed: false,
        fallback_mode: "none",
        vendor_status: "ok",
        quality_flag: "ok",
        generated_at: "2026-08-01T14:23:24Z",
      },
    };

    const { result } = renderHook(() => useDashboardHomeFirstScreenViewModel());

    expect(result.current.view.headerStatus.dataStatusKind).toBe("ok");
    expect(result.current.view.headerStatus.formalUseAllowed).toBe(false);
    expect(result.current.view.headerStatus.governanceFeedAvailable).toBe(false);
    expect(result.current.view.headerStatus.dataSyncPrefix).toBe("分析快照已更新");
    expect(result.current.view.headerStatus.dataSyncPrefix).not.toContain("正式数据");
  });

  it("keeps missing data domains in data quality instead of inventing risk actions", () => {
    boundaryMock.current = {
      ...(boundaryMock.current as Record<string, unknown>),
      adapterOutput: {
        ...(boundaryMock.current as { adapterOutput: Record<string, unknown> }).adapterOutput,
        domainsMissing: ["alerts", "contribution"],
        productCategoryHeadline: { state: "empty", metrics: [] },
      },
      snapshotResult: {
        report_date: "2026-04-30",
        mode: "partial",
        domains_missing: ["alerts", "contribution"],
      },
      snapshotMeta: {
        fallback_mode: "none",
        vendor_status: "ok",
        quality_flag: "ok",
        generated_at: "2026-04-30T16:00:00Z",
      },
    };

    const { result } = renderHook(() => useDashboardHomeFirstScreenViewModel());

    expect(result.current.view.headerStatus.dataStatusKind).toBe("partial");
    expect(result.current.view.headerStatus.showRiskReview).toBe(false);
    expect(result.current.view.headerStatus.riskReviewCount).toBe(0);
    expect(
      result.current.view.decisionRail.actions.some((action) =>
        action.to?.startsWith("/decision-items"),
      ),
    ).toBe(false);
  });

  it("suppresses trusted AUM delta text when only prior lineage is missing", () => {
    boundaryMock.current = {
      ...(boundaryMock.current as Record<string, unknown>),
      adapterOutput: {
        ...(boundaryMock.current as { adapterOutput: Record<string, unknown> }).adapterOutput,
        overview: {
          vm: {
            title: "经营总览",
            metrics: [
              {
                id: "aum",
                label: "总资产规模",
                caliberLabel: "本币资产口径",
                value: numeric(10_000_000_000, "100.00 亿", "yuan", false),
                delta: numeric(null, "无环比", "pct"),
                tone: "positive" as const,
                detail: "当前值可信，上一期缺少治理血缘。",
                history: [9_000_000_000, 10_000_000_000],
              },
            ],
          },
          state: { kind: "ok" },
          meta: homeSnapshotMeta(),
        },
        productCategoryHeadline: { state: "ready", metrics: [] },
      },
      snapshotResult: {
        report_date: "2026-04-30",
        mode: "strict",
        domains_missing: [],
      },
      snapshotMeta: homeSnapshotMeta(),
    };

    const { result } = renderHook(() => useDashboardHomeFirstScreenViewModel());
    const aumKpi = result.current.view.terminalKpis.find((metric) => metric.id === "aum");

    expect(result.current.view.headerStatus.dataStatusKind).toBe("ok");
    expect(aumKpi?.delta).toBe("—");
    expect(aumKpi?.delta).not.toContain("+11.11%");
  });

  it("keeps current-lineage gaps in review state on the first screen", () => {
    boundaryMock.current = {
      ...(boundaryMock.current as Record<string, unknown>),
      adapterOutput: {
        ...(boundaryMock.current as { adapterOutput: Record<string, unknown> }).adapterOutput,
        overview: {
          vm: {
            title: "经营总览",
            metrics: [
              {
                id: "aum",
                label: "总资产规模",
                caliberLabel: "本币资产口径",
                value: numeric(10_000_000_000, "100.00 亿", "yuan", false),
                delta: numeric(0.1111, "+11.11%", "pct"),
                tone: "warning" as const,
                detail: "当前值缺少治理血缘，需复核。",
                history: [9_000_000_000, 10_000_000_000],
              },
            ],
          },
          state: { kind: "ok" },
          meta: homeSnapshotMeta({
            quality_flag: "warning",
            vendor_status: "vendor_unavailable",
          }),
        },
        productCategoryHeadline: { state: "ready", metrics: [] },
      },
      snapshotResult: {
        report_date: "2026-04-30",
        mode: "strict",
        domains_missing: [],
      },
      snapshotMeta: homeSnapshotMeta({
        quality_flag: "warning",
        vendor_status: "vendor_unavailable",
      }),
    };

    const { result } = renderHook(() => useDashboardHomeFirstScreenViewModel());

    expect(result.current.view.headerStatus.dataStatusKind).toBe("partial");
    expect(result.current.view.headerStatus.marketStatus).toBe("来源需复核");
    expect(result.current.view.headerStatus.dataSyncPrefix).toContain("需复核");
  });
});
