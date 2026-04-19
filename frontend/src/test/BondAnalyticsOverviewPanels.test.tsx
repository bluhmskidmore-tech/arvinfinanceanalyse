import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

vi.mock("../features/bond-analytics/components/BondAnalyticsMarketContextStrip", () => ({
  BondAnalyticsMarketContextStrip: (props: { reportDate: string; leadModuleLabel: string; truthStrip: { title: string } }) => (
    <div
      data-testid="mock-bond-market-context-strip"
      data-report-date={props.reportDate}
      data-lead-module={props.leadModuleLabel}
      data-truth-title={props.truthStrip.title}
    />
  ),
}));

vi.mock("../features/bond-analytics/components/BondAnalyticsInstitutionalCockpit", () => ({
  BondAnalyticsInstitutionalCockpit: (props: {
    reportDate: string;
    topAnomalies?: string[];
    actionAttribution?: { total_actions?: number } | null;
    onOpenModuleDetail: (key: string) => void;
  }) => (
    <div
      data-testid="mock-bond-institutional-cockpit"
      data-report-date={props.reportDate}
      data-anomaly-count={String(props.topAnomalies?.length ?? 0)}
      data-action-count={String(props.actionAttribution?.total_actions ?? 0)}
    >
      <button
        type="button"
        data-testid="mock-home-open-action"
        onClick={() => props.onOpenModuleDetail("action-attribution")}
      >
        open home action
      </button>
    </div>
  ),
}));

vi.mock("../features/bond-analytics/components/BondAnalyticsFilterActionStrip", () => ({
  BondAnalyticsFilterActionStrip: (props: {
    reportDate: string;
    periodType: string;
    onRefreshAnalytics?: () => void;
  }) => (
    <div
      data-testid="mock-bond-filter-action-strip"
      data-report-date={props.reportDate}
      data-period-type={props.periodType}
    >
      <button type="button" data-testid="mock-filter-refresh" onClick={() => props.onRefreshAnalytics?.()}>
        trigger refresh
      </button>
    </div>
  ),
}));

import { BondAnalyticsOverviewPanels } from "../features/bond-analytics/components/BondAnalyticsOverviewPanels";
import type { BondAnalyticsOverviewModel, BondAnalyticsReadinessItem } from "../features/bond-analytics/lib/bondAnalyticsOverviewModel";

function createReadinessItem(overrides: Partial<BondAnalyticsReadinessItem> = {}): BondAnalyticsReadinessItem {
  return {
    key: "return-decomposition",
    label: "收益拆解",
    description: "desc",
    detailHint: "hint",
    statusLabel: "placeholder-blocked",
    statusReason: "reason",
    promotionDestination: "readiness-only",
    warnings: [],
    ...overrides,
  };
}

function createOverviewModel(): BondAnalyticsOverviewModel {
  return {
    reportDate: "2026-03-31",
    periodType: "MoM",
    truthStrip: {
      title: "Truth and provenance",
      items: [
        { key: "basis", label: "Basis", value: "Formal", tone: "neutral" },
      ],
    },
    headlineTiles: [
      {
        key: "action-attribution",
        label: "Headline Action Attribution",
        value: "12",
        caption: "Caption",
        detail: "Detail",
      },
    ],
    readinessItems: [
      createReadinessItem({
        key: "action-attribution",
        label: "动作归因",
        promotionDestination: "headline",
        statusLabel: "eligible",
      }),
      createReadinessItem({ key: "return-decomposition" }),
    ],
    futureVisibilityItems: [
      {
        key: "portfolio-headlines",
        label: "Future",
        description: "Future body",
        statusLabel: "future-visible",
        statusReason: "Planning",
      },
    ],
    topAnomalies: ["overview anomaly"],
    activeModuleContext: {
      key: "action-attribution",
      label: "Lead from overview model",
      description: "Active description",
      statusLabel: "eligible",
      statusReason: "Ready",
    },
  };
}

describe("BondAnalyticsOverviewPanels", () => {
  it("composes the simplified homepage shells, passes overview props to children, and wires drill plus refresh callbacks", async () => {
    const user = userEvent.setup();
    const onOpenModuleDetail = vi.fn();
    const onRefreshAnalytics = vi.fn();
    const onReportDateChange = vi.fn();
    const onPeriodTypeChange = vi.fn();

    const overviewModel = createOverviewModel();

    render(
      <BondAnalyticsOverviewPanels
        dateOptions={[{ value: "2026-03-31", label: "2026-03-31" }]}
        reportDate="2026-03-31"
        onReportDateChange={onReportDateChange}
        periodType="MoM"
        onPeriodTypeChange={onPeriodTypeChange}
        assetClass="all"
        onAssetClassChange={vi.fn()}
        accountingClass="all"
        onAccountingClassChange={vi.fn()}
        scenarioSet="standard"
        onScenarioSetChange={vi.fn()}
        spreadScenarios="10,25,50"
        onSpreadScenariosChange={vi.fn()}
        actionAttributionResult={{ total_actions: 4 } as never}
        overviewModel={overviewModel}
        onOpenModuleDetail={onOpenModuleDetail}
        onRefreshAnalytics={onRefreshAnalytics}
        lastAnalyticsRefreshRunId="run-001"
      />,
    );

    expect(screen.getByTestId("bond-analysis-top-cockpit")).toBeInTheDocument();
    expect(screen.getByTestId("mock-bond-institutional-cockpit")).toHaveAttribute(
      "data-report-date",
      "2026-03-31",
    );
    expect(screen.getByTestId("mock-bond-institutional-cockpit")).toHaveAttribute(
      "data-anomaly-count",
      "1",
    );
    expect(screen.getByTestId("mock-bond-institutional-cockpit")).toHaveAttribute(
      "data-action-count",
      "4",
    );

    const market = screen.getByTestId("mock-bond-market-context-strip");
    expect(market).toHaveAttribute("data-report-date", "2026-03-31");
    expect(market).toHaveAttribute("data-lead-module", "Lead from overview model");
    expect(market).toHaveAttribute("data-truth-title", "Truth and provenance");

    const filter = screen.getByTestId("mock-bond-filter-action-strip");
    expect(filter).toHaveAttribute("data-report-date", "2026-03-31");
    expect(filter).toHaveAttribute("data-period-type", "MoM");

    await user.click(screen.getByTestId("mock-filter-refresh"));
    expect(onRefreshAnalytics).toHaveBeenCalledTimes(1);

    await user.click(screen.getByTestId("mock-home-open-action"));
    expect(onOpenModuleDetail).toHaveBeenCalledWith("action-attribution");
  });
});
