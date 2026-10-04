import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type {
  DashboardHomeFirstScreenHydration,
  HomeSupplementalApiState,
} from "../features/workbench/dashboard-home/dashboardHomeFirstScreenTypes";
import { createMockHomeFirstScreenView } from "../features/workbench/dashboard-home/dashboardHomeFirstScreenMockView";
import { DeferredTerminalHomeContent } from "../features/workbench/dashboard-home/DeferredTerminalHomeContent";
import type { DashboardHomeSnapshotBoundary } from "../features/workbench/dashboard-home/useDashboardHomeFirstScreenViewModel";
import { useDashboardHomeSupplementalHydration } from "../features/workbench/dashboard-home/useDashboardHomeSupplementalHydration";

vi.mock("../features/workbench/dashboard-home/useDashboardHomeSupplementalHydration", () => ({
  useDashboardHomeSupplementalHydration: vi.fn(),
}));

vi.mock("../features/workbench/dashboard-home/DeferredTerminalHomeBody", () => ({
  DeferredTerminalHomeBody: ({
    supplementalState,
    updatedAt,
  }: {
    supplementalState?: HomeSupplementalApiState;
    updatedAt?: string;
  }) => (
    <div data-testid="supplemental-body-state">
      {supplementalState?.label} {updatedAt}
    </div>
  ),
}));

const mockedUseDashboardHomeSupplementalHydration = vi.mocked(
  useDashboardHomeSupplementalHydration,
);

function createHydration(
  overrides: Partial<DashboardHomeFirstScreenHydration> = {},
): DashboardHomeFirstScreenHydration {
  return {
    reportDate: "2026-04-30",
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

function createSupplementalResult(
  overrides: Partial<ReturnType<typeof useDashboardHomeSupplementalHydration>> = {},
): ReturnType<typeof useDashboardHomeSupplementalHydration> {
  return {
    firstScreenHydration: createHydration(),
    supplementalState: { kind: "loading", label: "补充查询读取中" },
    updatedAt: "2026-04-30 16:00",
    ...overrides,
  };
}

describe("DeferredTerminalHomeContent", () => {
  beforeEach(() => {
    mockedUseDashboardHomeSupplementalHydration.mockReset();
  });

  it("shows the below-fold evidence index before deferred sections render", () => {
    mockedUseDashboardHomeSupplementalHydration.mockReturnValue(createSupplementalResult());

    render(
      <DeferredTerminalHomeContent
        snapshotBoundary={{} as DashboardHomeSnapshotBoundary}
        firstScreenView={createMockHomeFirstScreenView()}
        userReachedDeferredContent={false}
      />,
    );

    const index = screen.getByTestId("dashboard-home-deferred-index");
    expect(index).toHaveTextContent("证据索引");
    expect(index).toHaveTextContent("下半屏模块按来源延迟展开");
    expect(index).toHaveTextContent("持仓账本");
    expect(index).toHaveTextContent("凭证链路");
  });

  it("enables hydration on the first requested render without cascading state updates", async () => {
    mockedUseDashboardHomeSupplementalHydration.mockReturnValue(createSupplementalResult());
    render(
      <DeferredTerminalHomeContent
        snapshotBoundary={{} as DashboardHomeSnapshotBoundary}
        firstScreenView={createMockHomeFirstScreenView()}
        userReachedDeferredContent
      />,
    );

    expect(mockedUseDashboardHomeSupplementalHydration.mock.calls[0]?.[1]).toEqual({ enabled: true });
    expect(await screen.findByTestId("supplemental-body-state")).toBeInTheDocument();
    expect(mockedUseDashboardHomeSupplementalHydration).toHaveBeenCalledTimes(1);
  });

  it("emits equivalent first-screen hydration only once across rerenders", async () => {
    const onFirstScreenHydrated = vi.fn();
    const snapshotBoundary = {} as DashboardHomeSnapshotBoundary;
    mockedUseDashboardHomeSupplementalHydration
      .mockReturnValueOnce(createSupplementalResult())
      .mockReturnValueOnce(createSupplementalResult());

    const { rerender } = render(
      <DeferredTerminalHomeContent
        snapshotBoundary={snapshotBoundary}
        firstScreenView={createMockHomeFirstScreenView()}
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
        firstScreenView={createMockHomeFirstScreenView()}
        userReachedDeferredContent={false}
        onFirstScreenHydrated={onFirstScreenHydrated}
      />,
    );

    await waitFor(() => {
      expect(mockedUseDashboardHomeSupplementalHydration).toHaveBeenCalledTimes(2);
    });
    expect(onFirstScreenHydrated).toHaveBeenCalledTimes(1);
  });

  it("emits risk label corrections even when the displayed value is unchanged", async () => {
    const onFirstScreenHydrated = vi.fn();
    const props = {
      snapshotBoundary: {} as DashboardHomeSnapshotBoundary,
      firstScreenView: createMockHomeFirstScreenView(),
      userReachedDeferredContent: false,
      onFirstScreenHydrated,
    };
    mockedUseDashboardHomeSupplementalHydration.mockReturnValue(createSupplementalResult());
    const { rerender } = render(<DeferredTerminalHomeContent {...props} />);
    const correctedHydration = createHydration({
      keyRiskStrip: createHydration().keyRiskStrip.map((item) => ({
        ...item,
        label: "修正久期",
      })),
    });
    mockedUseDashboardHomeSupplementalHydration.mockReturnValue(
      createSupplementalResult({ firstScreenHydration: correctedHydration }),
    );

    rerender(<DeferredTerminalHomeContent {...props} />);

    await waitFor(() => expect(onFirstScreenHydrated).toHaveBeenCalledTimes(2));
    expect(onFirstScreenHydrated).toHaveBeenLastCalledWith(correctedHydration);
  });

  it.each(["state", "updatedAt"] as const)(
    "updates the body when only %s changes without re-emitting first-screen hydration",
    async (changedField) => {
      const onFirstScreenHydrated = vi.fn();
      const props = {
        snapshotBoundary: {} as DashboardHomeSnapshotBoundary,
        firstScreenView: createMockHomeFirstScreenView(),
        userReachedDeferredContent: true,
        onFirstScreenHydrated,
      };
      mockedUseDashboardHomeSupplementalHydration.mockReturnValue(createSupplementalResult());
      const { rerender } = render(<DeferredTerminalHomeContent {...props} />);
      expect(await screen.findByTestId("supplemental-body-state")).toHaveTextContent(
        "补充查询读取中 2026-04-30 16:00",
      );
      const updatedResult = createSupplementalResult(
        changedField === "state"
          ? { supplementalState: { kind: "error", label: "补充查询失败" } }
          : { updatedAt: "2026-04-30 16:05" },
      );
      mockedUseDashboardHomeSupplementalHydration.mockReturnValue(updatedResult);

      rerender(<DeferredTerminalHomeContent {...props} />);

      expect(screen.getByTestId("supplemental-body-state")).toHaveTextContent(
        `${updatedResult.supplementalState.label} ${updatedResult.updatedAt}`,
      );
      expect(onFirstScreenHydrated).toHaveBeenCalledTimes(1);
      expect(onFirstScreenHydrated).toHaveBeenCalledWith(createHydration());
    },
  );
});
