import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DashboardHomeAmbientCanvas } from "./DashboardHomeAmbientCanvas";
import { createMockHomeFirstScreenView } from "./dashboardHomeFirstScreenMockView";
import { DecisionRailSection } from "./sections/DecisionRailSection";
import { TerminalHomeFirstScreen } from "./TerminalHomeFirstScreen";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("dashboard home decision closure", () => {
  it("shows one ready high-priority action as the hero primary action", () => {
    const base = createMockHomeFirstScreenView();
    const view = {
      ...base,
      decisionRail: {
        ...base.decisionRail,
        actions: [
          {
            id: "blocked-action",
            title: "不可执行动作",
            priority: "high" as const,
            sourceLabel: "保留缺口",
            reason: "来源未接入",
            statusKind: "backend-gap" as const,
          },
          ...base.decisionRail.actions,
        ],
      },
    };

    render(
      <MemoryRouter>
        <TerminalHomeFirstScreen view={view} />
      </MemoryRouter>,
    );

    const primaryAction = screen.getByTestId("dashboard-home-primary-action");
    expect(primaryAction).toHaveTextContent("复核风险总览");
    expect(primaryAction).toHaveAttribute(
      "href",
      "/risk-overview?report_date=2026-04-30",
    );
    expect(screen.getAllByTestId("dashboard-home-primary-action")).toHaveLength(1);
  });

  it("keeps live announcements on a short status node instead of the whole first screen", () => {
    const { container } = render(
      <MemoryRouter>
        <TerminalHomeFirstScreen view={createMockHomeFirstScreenView()} />
      </MemoryRouter>,
    );

    const firstScreen = container.querySelector("section[aria-label='MOSS 组合经营日报首屏']");
    expect(firstScreen).not.toHaveAttribute("aria-live");
    expect(screen.getByTestId("dashboard-home-evidence-score")).toHaveAttribute(
      "role",
      "status",
    );
  });

  it("provides a compact source summary for narrow screens", () => {
    render(
      <MemoryRouter>
        <TerminalHomeFirstScreen view={createMockHomeFirstScreenView()} />
      </MemoryRouter>,
    );

    expect(
      screen.getByTestId("dashboard-home-source-mobile-summary"),
    ).toHaveTextContent(
      "3 项主链 · 2 项下方复核 · 1 项保留缺口",
    );
  });

  it("uses the governed stale state consistently in the hero and source gate", () => {
    const base = createMockHomeFirstScreenView();
    const view = {
      ...base,
      headerStatus: {
        ...base.headerStatus,
        dataStatusKind: "stale" as const,
        dataSyncPrefix: "部分数据 · 需复核",
      },
      reportDateContext: {
        ...base.reportDateContext,
        mode: "stale" as const,
        divergenceReason: "沿用上一版本数据",
      },
      terminalKpis: base.terminalKpis.map((kpi) => ({
        ...kpi,
        value: "1.00",
        state: "ready" as const,
      })),
    };

    render(
      <MemoryRouter>
        <TerminalHomeFirstScreen view={view} />
      </MemoryRouter>,
    );

    const evidence = screen.getByTestId("dashboard-home-evidence-score");
    expect(evidence).toHaveTextContent("证据需复核");
    expect(evidence).not.toHaveTextContent("主链来源核验通过");

    const sourceGate = screen.getByRole("region", { name: "来源核验" });
    expect(within(sourceGate).getAllByText("偏旧")).toHaveLength(3);
  });


  it("marks an incomplete product headline as partial instead of stale or passed", () => {
    const base = createMockHomeFirstScreenView();
    const view = {
      ...base,
      headerStatus: {
        ...base.headerStatus,
        dataStatusKind: "partial" as const,
        dataSyncPrefix: "产品分类经营摘要不完整，需复核",
      },
      terminalKpis: base.terminalKpis.map((kpi) => ({
        ...kpi,
        value: "1.00",
        state: "ready" as const,
      })),
      productCategoryHeadline: {
        state: "partial" as const,
        metrics: [
          {
            id: "annual_pnl",
            label: "年度损益",
            value: "—",
            detail: "产品分类快照未完整下发",
          },
        ],
      },
    };

    render(
      <MemoryRouter>
        <TerminalHomeFirstScreen view={view} />
      </MemoryRouter>,
    );

    expect(screen.getByTestId("dashboard-home-evidence-score")).toHaveTextContent(
      "证据需复核",
    );
    expect(screen.getByTestId("dashboard-home-report-identity")).toHaveTextContent(
      "不完整",
    );
    const sourceGate = screen.getByRole("region", { name: "来源核验" });
    const productRow = within(sourceGate).getByText("产品分类").closest("div");
    const snapshotRow = within(sourceGate).getByText("受管快照").closest("div");
    const overviewRow = within(sourceGate).getByText("经营指标").closest("div");
    expect(snapshotRow).toHaveTextContent("部分");
    expect(overviewRow).toHaveTextContent("通过");
    expect(overviewRow).not.toHaveTextContent("部分");
    expect(productRow).toHaveTextContent("不完整");
    expect(productRow).not.toHaveTextContent("偏旧");
  });
  it("surfaces an empty snapshot as no data across the hero and rail", () => {
    const base = createMockHomeFirstScreenView();
    const view = {
      ...base,
      reportDate: "—",
      reportDateContext: {
        ...base.reportDateContext,
        actualDataDate: "",
        dataAsOfDate: "",
        generatedAt: "",
        mode: "empty" as const,
        divergenceReason: "暂无可用数据日",
      },
      headerStatus: {
        ...base.headerStatus,
        dataStatusKind: "stale" as const,
        dataSyncPrefix: "暂无可用快照，需复核",
      },
      terminalKpis: [],
    };

    const { unmount } = render(
      <MemoryRouter>
        <TerminalHomeFirstScreen view={view} />
      </MemoryRouter>,
    );

    expect(screen.getByTestId("dashboard-home-report-identity")).toHaveTextContent(
      "暂无数据",
    );
    expect(screen.getByTestId("dashboard-home-evidence-score")).toHaveTextContent(
      "暂无证据",
    );
    const sourceGate = screen.getByRole("region", { name: "来源核验" });
    expect(within(sourceGate).getAllByText("暂无")).toHaveLength(5);

    unmount();
    render(
      <MemoryRouter>
        <DecisionRailSection
          decisionRail={view.decisionRail}
          reportDate={view.reportDate}
          dataSyncPrefix={view.headerStatus.dataSyncPrefix}
          dataStatusKind={view.headerStatus.dataStatusKind}
          snapshotMeta={null}
          reportDateContext={view.reportDateContext}
        />
      </MemoryRouter>,
    );
    expect(screen.getByTestId("dashboard-home-rail-data-status")).toHaveTextContent(
      "暂无可用快照",
    );
    expect(screen.getByTestId("dashboard-home-rail-updated-at")).toHaveTextContent("暂无");
  });

  it("shows honest owner and deadline gaps for every decision action", () => {
    const view = createMockHomeFirstScreenView();

    render(
      <MemoryRouter>
        <DecisionRailSection
          decisionRail={view.decisionRail}
          reportDate={view.reportDate}
          dataSyncPrefix={view.headerStatus.dataSyncPrefix}
          dataStatusKind={view.headerStatus.dataStatusKind}
          snapshotMeta={null}
          reportDateContext={view.reportDateContext}
        />
      </MemoryRouter>,
    );

    const actionRows = screen.getAllByTestId("dashboard-home-decision-action-row");
    expect(actionRows).toHaveLength(view.decisionRail.actions.length);
    actionRows.forEach((row) => {
      expect(within(row).getByText("负责人待接入")).toBeInTheDocument();
      expect(within(row).getByText("截止时间未维护")).toBeInTheDocument();
      expect(within(row).getByText(/优先级/)).toBeInTheDocument();
    });
  });

  it("keeps only the genuinely horizontal source evidence keyboard-scrollable", () => {
    const clientWidthSpy = vi
      .spyOn(HTMLElement.prototype, "clientWidth", "get")
      .mockReturnValue(200);
    const scrollWidthSpy = vi
      .spyOn(HTMLElement.prototype, "scrollWidth", "get")
      .mockReturnValue(500);
    render(
      <MemoryRouter>
        <TerminalHomeFirstScreen view={createMockHomeFirstScreenView()} />
      </MemoryRouter>,
    );

    const sourceStrip = screen.getByRole("region", {
      name: "来源核验明细，可用左右方向键横向浏览",
    });
    const sourceScrollBy = vi.fn();
    Object.defineProperty(sourceStrip, "scrollBy", {
      configurable: true,
      value: sourceScrollBy,
    });

    fireEvent.keyDown(sourceStrip, { key: "ArrowRight" });

    expect(sourceScrollBy).toHaveBeenCalledWith({ behavior: "smooth", left: 160 });
    expect(screen.getByTestId("dashboard-home-hero-kpi-strip")).not.toHaveAttribute("tabindex");
    expect(screen.getByTestId("dashboard-home-product-category-strip")).not.toHaveAttribute("tabindex");
    clientWidthSpy.mockRestore();
    scrollWidthSpy.mockRestore();
  });

  it("does not expose a keyboard scrolling affordance when source evidence fits", () => {
    const clientWidthSpy = vi
      .spyOn(HTMLElement.prototype, "clientWidth", "get")
      .mockReturnValue(500);
    const scrollWidthSpy = vi
      .spyOn(HTMLElement.prototype, "scrollWidth", "get")
      .mockReturnValue(500);
    render(
      <MemoryRouter>
        <TerminalHomeFirstScreen view={createMockHomeFirstScreenView()} />
      </MemoryRouter>,
    );

    const sourceDetail = screen.getByRole("region", { name: "来源核验明细" });
    expect(sourceDetail).not.toHaveAttribute("tabindex");
    expect(screen.queryByRole("region", {
      name: "来源核验明细，可用左右方向键横向浏览",
    })).not.toBeInTheDocument();
    clientWidthSpy.mockRestore();
    scrollWidthSpy.mockRestore();
  });

  it("does not request a canvas context after the ambient visual is disabled", () => {
    const getContext = vi
      .spyOn(HTMLCanvasElement.prototype, "getContext")
      .mockImplementation(() => null);

    render(<DashboardHomeAmbientCanvas />);

    expect(getContext).not.toHaveBeenCalled();
  });
});

describe("TerminalHomeFirstScreen fallback source semantics", () => {
  it("labels the product source as fallback instead of stale or passed", () => {
    const base = createMockHomeFirstScreenView();
    const view = {
      ...base,
      headerStatus: {
        ...base.headerStatus,
        dataStatusKind: "fallback" as const,
        dataSyncPrefix: "快照使用回退链路，需复核",
      },
    };

    render(
      <MemoryRouter>
        <TerminalHomeFirstScreen view={view} />
      </MemoryRouter>,
    );

    expect(screen.getByTestId("dashboard-home-product-category-headline")).toHaveTextContent(
      "回退快照",
    );
    const sourceRegion = screen.getByRole("region", { name: "来源核验" });
    const productRow = within(sourceRegion).getByText("产品分类").parentElement;
    expect(productRow).toHaveTextContent("回退");
    expect(productRow).not.toHaveTextContent("偏旧");
    expect(productRow).not.toHaveTextContent("通过");
  });
});
