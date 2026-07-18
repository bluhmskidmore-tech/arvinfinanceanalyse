import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { createApiClient } from "../../../api/client";

const boundaryMock = vi.hoisted(() => ({ current: null as unknown }));

vi.mock("../pages/useDashboardSnapshotBoundary", () => ({
  useDashboardSnapshotBoundary: () => boundaryMock.current,
}));

vi.mock("./useMockHomeFirstScreenView", () => ({
  useMockHomeFirstScreenView: () => null,
}));

import { useDashboardHomeFirstScreenViewModel } from "./useDashboardHomeFirstScreenViewModel";

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
});
