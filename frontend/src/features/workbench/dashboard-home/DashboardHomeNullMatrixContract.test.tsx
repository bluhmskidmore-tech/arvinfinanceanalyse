import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { createApiClient } from "../../../api/client";
import type { Numeric } from "../../../api/contracts";
import { DashboardHomeOptionTwoOverview } from "./DashboardHomeOptionTwoOverview";
import { adaptHomeSnapshotForFirstScreen } from "./dashboardHomeSnapshotAdapter";

const boundaryMock = vi.hoisted(() => ({ current: null as unknown }));

vi.mock("../pages/useDashboardSnapshotBoundary", () => ({
  useDashboardSnapshotBoundary: () => boundaryMock.current,
}));
vi.mock("./useMockHomeFirstScreenView", () => ({
  useMockHomeFirstScreenView: () => null,
}));

import { useDashboardHomeFirstScreenViewModel } from "./useDashboardHomeFirstScreenViewModel";

function FirstScreenOverview() {
  const { view } = useDashboardHomeFirstScreenViewModel();
  return <DashboardHomeOptionTwoOverview view={view} />;
}

function aumValue(raw: number | null | undefined): Numeric {
  const common = {
    display: "0.00 亿",
    unit: "yuan" as const,
    precision: 2,
    sign_aware: false,
  };
  if (raw === undefined) {
    // Exercise a malformed wire value whose required raw field was omitted.
    return common as Numeric;
  }
  return { ...common, raw };
}

describe("dashboard home governed AUM null matrix", () => {
  it.each([
    { caseName: "null raw with misleading zero display", raw: null, state: "empty", value: "—" },
    { caseName: "real zero raw", raw: 0, state: "ready", value: "0.00亿" },
    { caseName: "missing raw with misleading zero display", raw: undefined, state: "empty", value: "—" },
  ])("renders $caseName from snapshot through the first screen", async ({ raw, state, value }) => {
    const mockClient = createApiClient({ mode: "mock" });
    const base = await mockClient.getHomeSnapshot();
    const aum = base.result.overview.metrics.find((metric) => metric.id === "aum");
    if (!aum) throw new Error("Home snapshot fixture is missing the governed AUM metric");

    const snapshot = {
      ...base,
      result_meta: {
        ...base.result_meta,
        basis: "analytical" as const,
        formal_use_allowed: false,
      },
      result: {
        ...base.result,
        overview: {
          ...base.result.overview,
          metrics: [{ ...aum, value: aumValue(raw), delta: aumValue(null) }],
        },
      },
    };
    const adapterOutput = adaptHomeSnapshotForFirstScreen({
      snapshot,
      isLoading: false,
      isError: false,
    });
    expect(adapterOutput.overview.vm?.metrics[0]?.value.raw).toBe(raw);

    boundaryMock.current = {
      dataClient: { ...mockClient, mode: "real" },
      adapterOutput,
      snapshotResult: snapshot.result,
      snapshotMeta: snapshot.result_meta,
      reportDateDataWarning: null,
      snapshotQuery: { isError: false, isFetching: false, error: null },
      refreshSnapshot: vi.fn(),
    };

    render(
      <MemoryRouter>
        <FirstScreenOverview />
      </MemoryRouter>,
    );

    const card = screen.getByTestId("dashboard-home-kpi-aum");
    expect(card).toHaveAttribute("data-state", state);
    expect(card.querySelector("strong")).toHaveTextContent(value);
    if (raw == null) {
      expect(card.querySelector("strong")).not.toHaveTextContent("0.00");
    }
  });
});
