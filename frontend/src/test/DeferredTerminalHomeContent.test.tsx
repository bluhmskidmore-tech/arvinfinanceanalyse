import { render, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { DashboardHomeFirstScreenHydration } from "../features/workbench/dashboard-home/dashboardHomeFirstScreenTypes";
import { DeferredTerminalHomeContent } from "../features/workbench/dashboard-home/DeferredTerminalHomeContent";
import type { DashboardHomeSnapshotBoundary } from "../features/workbench/dashboard-home/useDashboardHomeFirstScreenViewModel";
import { useDashboardHomeSupplementalHydration } from "../features/workbench/dashboard-home/useDashboardHomeSupplementalHydration";

vi.mock("../features/workbench/dashboard-home/useDashboardHomeSupplementalHydration", () => ({
  useDashboardHomeSupplementalHydration: vi.fn(),
}));

const mockedUseDashboardHomeSupplementalHydration = vi.mocked(
  useDashboardHomeSupplementalHydration,
);

function createHydration(
  overrides: Partial<DashboardHomeFirstScreenHydration> = {},
): DashboardHomeFirstScreenHydration {
  return {
    reportDate: "2026-04-30",
    headerStatus: {
      dataStatusKind: "ok",
      dataUpdatedAt: "2026-04-30 16:00",
      marketStatus: "open",
      valuationLabel: "ok",
      valuationTone: "ok",
      riskReviewCount: 0,
      showRiskReview: false,
      dataSyncPrefix: "formal",
    },
    decisionRail: {
      conclusion: "position risk is controlled",
      maxDragLabel: "duration",
      maxDragValue: "4.20",
      maxContributionLabel: "carry",
      maxContributionValue: "1.20",
      keyRisk: "no new risk",
      suggestions: ["monitor"],
      pendingSummary: "none",
      reportDate: "2026-04-30",
      dataUpdatedAt: "2026-04-30 16:00",
      dataSyncPrefix: "formal",
    },
    terminalKpis: [
      {
        id: "nav",
        label: "nav",
        value: "100.00",
        unit: "yi",
        delta: "+0.10%",
        deltaTone: "up",
        sparkline: [99.9, 100],
        state: "ready",
      },
    ],
    keyRiskStrip: [
      {
        id: "duration",
        label: "duration",
        value: "4.20",
        delta: "0.00",
        deltaTone: "flat",
      },
    ],
    ...overrides,
  };
}

describe("DeferredTerminalHomeContent", () => {
  beforeEach(() => {
    mockedUseDashboardHomeSupplementalHydration.mockReset();
  });

  it("emits equivalent first-screen hydration only once across rerenders", async () => {
    const onFirstScreenHydrated = vi.fn();
    const snapshotBoundary = {} as DashboardHomeSnapshotBoundary;
    mockedUseDashboardHomeSupplementalHydration
      .mockReturnValueOnce(createHydration())
      .mockReturnValueOnce(createHydration());

    const { rerender } = render(
      <DeferredTerminalHomeContent
        snapshotBoundary={snapshotBoundary}
        userReachedDeferredContent={false}
        onFirstScreenHydrated={onFirstScreenHydrated}
      />,
    );

    await waitFor(() => {
      expect(onFirstScreenHydrated).toHaveBeenCalledTimes(1);
    });

    rerender(
      <DeferredTerminalHomeContent
        snapshotBoundary={snapshotBoundary}
        userReachedDeferredContent={false}
        onFirstScreenHydrated={onFirstScreenHydrated}
      />,
    );

    await waitFor(() => {
      expect(mockedUseDashboardHomeSupplementalHydration).toHaveBeenCalledTimes(2);
    });
    expect(onFirstScreenHydrated).toHaveBeenCalledTimes(1);
  });
});
