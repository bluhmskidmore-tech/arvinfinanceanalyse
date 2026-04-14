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
  BondAnalyticsInstitutionalCockpit: (props: { reportDate: string }) => (
    <div data-testid="mock-bond-institutional-cockpit" data-report-date={props.reportDate} />
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

vi.mock("../features/bond-analytics/components/BondAnalyticsHeadlineZone", () => ({
  BondAnalyticsHeadlineZone: (props: {
    headlineTile: { key: string; label: string } | null;
    headlineCtaLabel: string | null;
    promotedItems: { key: string }[];
    warningItems: { key: string }[];
    onOpenModuleDetail: (key: string) => void;
  }) => (
    <div
      data-testid="mock-bond-headline-zone"
      data-headline-key={props.headlineTile?.key ?? ""}
      data-headline-label={props.headlineTile?.label ?? ""}
      data-headline-cta={props.headlineCtaLabel ?? ""}
      data-promoted-count={String(props.promotedItems.length)}
      data-warning-count={String(props.warningItems.length)}
    >
      {props.headlineTile ? (
        <button
          type="button"
          data-testid={`mock-bond-headline-open-${props.headlineTile.key}`}
          onClick={() => props.onOpenModuleDetail(props.headlineTile!.key)}
        >
          headline drill
        </button>
      ) : null}
    </div>
  ),
}));

vi.mock("../features/bond-analytics/components/BondAnalyticsOverviewWatchlistCard", () => ({
  BondAnalyticsOverviewWatchlistCard: (props: { topAnomalies: string[] }) => (
    <div data-testid="mock-bond-watchlist-card" data-anomaly-count={String(props.topAnomalies.length)} />
  ),
}));

vi.mock("../features/bond-analytics/components/BondAnalyticsFuturePanel", () => ({
  BondAnalyticsFuturePanel: (props: { futureVisibilityItems: { key: string }[] }) => (
    <div data-testid="mock-bond-future-panel" data-future-count={String(props.futureVisibilityItems.length)} />
  ),
}));

vi.mock("../features/bond-analytics/components/BondAnalyticsDecisionRail", () => ({
  BondAnalyticsDecisionRail: () => <div data-testid="mock-bond-decision-rail" />,
}));

vi.mock("../features/bond-analytics/components/BondAnalyticsReadinessMatrix", () => ({
  BondAnalyticsReadinessMatrix: (props: { onOpenModuleDetail: (key: string) => void }) => (
    <button
      type="button"
      data-testid="mock-bond-readiness-matrix"
      onClick={() => props.onOpenModuleDetail("return-decomposition")}
    >
      readiness drill
    </button>
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
  it("composes cockpit shells, passes overview props to children, and wires drill plus refresh callbacks", async () => {
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
    expect(screen.getByTestId("bond-analysis-right-rail")).toBeInTheDocument();

    const market = screen.getByTestId("mock-bond-market-context-strip");
    expect(market).toHaveAttribute("data-report-date", "2026-03-31");
    expect(market).toHaveAttribute("data-lead-module", "Lead from overview model");
    expect(market).toHaveAttribute("data-truth-title", "Truth and provenance");

    const filter = screen.getByTestId("mock-bond-filter-action-strip");
    expect(filter).toHaveAttribute("data-report-date", "2026-03-31");
    expect(filter).toHaveAttribute("data-period-type", "MoM");

    const headline = screen.getByTestId("mock-bond-headline-zone");
    expect(headline).toHaveAttribute("data-headline-key", "action-attribution");
    expect(headline).toHaveAttribute("data-headline-label", "Headline Action Attribution");
    expect(headline).toHaveAttribute("data-headline-cta", "Open Headline Action Attribution");
    expect(headline).toHaveAttribute("data-promoted-count", "1");
    expect(headline).toHaveAttribute("data-warning-count", "1");

    expect(screen.getByTestId("mock-bond-watchlist-card")).toHaveAttribute("data-anomaly-count", "1");
    expect(screen.getByTestId("mock-bond-future-panel")).toHaveAttribute("data-future-count", "1");

    await user.click(screen.getByTestId("mock-filter-refresh"));
    expect(onRefreshAnalytics).toHaveBeenCalledTimes(1);

    await user.click(screen.getByTestId("mock-bond-headline-open-action-attribution"));
    expect(onOpenModuleDetail).toHaveBeenCalledWith("action-attribution");

    await user.click(screen.getByTestId("mock-bond-readiness-matrix"));
    expect(onOpenModuleDetail).toHaveBeenCalledWith("return-decomposition");
  });
});
