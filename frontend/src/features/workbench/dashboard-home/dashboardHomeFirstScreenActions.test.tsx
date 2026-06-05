import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import type { VerdictPayload } from "../../../api/contracts";
import { DecisionRailSection } from "./sections/DecisionRailSection";
import { TerminalHomeFirstScreen } from "./TerminalHomeFirstScreen";
import { mapToHomeFirstScreenView } from "./dashboardHomeFirstScreenView";
import type { DashboardHomeFirstScreenView } from "./dashboardHomeFirstScreenTypes";

type DecisionActionForTest = {
  id: string;
  title: string;
  to?: string;
  sourceLabel: string;
  reason: string;
  statusKind: string;
};

const verdict: VerdictPayload = {
  conclusion: "review portfolio duration",
  tone: "warning",
  reasons: [{ label: "duration", value: "4.20", detail: "duration moved higher", tone: "warning" }],
  suggestions: [{ text: "review duration", link: "/risk-tensor" }],
};

function decisionActions(view: DashboardHomeFirstScreenView): readonly DecisionActionForTest[] {
  return ((view.decisionRail as { actions?: readonly DecisionActionForTest[] }).actions ?? []);
}

function firstScreenView(
  overrides: Partial<DashboardHomeFirstScreenView> = {},
): DashboardHomeFirstScreenView {
  return {
    reportDate: "2026-04-30",
    useMockFallback: false,
    headerStatus: {
      dataStatusKind: "ok",
      dataUpdatedAt: "16:00",
      marketStatus: "closed",
      valuationLabel: "ok",
      valuationTone: "ok",
      riskReviewCount: 0,
      showRiskReview: false,
      dataSyncPrefix: "formal",
    },
    decisionRail: {
      conclusion: "review portfolio duration",
      maxDragLabel: "rates",
      maxDragValue: "-1.00",
      maxContributionLabel: "carry",
      maxContributionValue: "+0.20",
      keyRisk: "duration",
      suggestions: ["review duration"],
      pendingSummary: "1 item",
      reportDate: "2026-04-30",
      dataUpdatedAt: "16:00",
      dataSyncPrefix: "formal",
      actions: [
        {
          id: "risk-overview",
          title: "Review risk workbench",
          priority: "high",
          sourceLabel: "risk",
          reason: "2 risk items require review",
          to: "/risk-overview?report_date=2026-04-30",
          statusKind: "ready",
        },
      ],
    } as unknown as DashboardHomeFirstScreenView["decisionRail"],
    terminalKpis: [
      {
        id: "aum",
        label: "AUM",
        value: "100.00",
        delta: "flat",
        deltaTone: "flat",
        sparkline: [100, 100],
        state: "ready",
      },
    ],
    keyRiskStrip: [
      {
        id: "duration",
        label: "Duration",
        value: "4.20",
        delta: "0.10",
        deltaTone: "warn",
      },
    ],
    ...overrides,
  };
}

describe("dashboard home first-screen actions", () => {
  it("preserves backend suggestion links and adds the risk workbench action", () => {
    const view = mapToHomeFirstScreenView({
      reportDate: "2026-04-30",
      useMockFallback: false,
      verdict,
      metrics: [],
      attribution: null,
      bondHeadline: null,
      portfolio: null,
      snapshotMeta: null,
      alertCount: 2,
      snapshotUnavailable: false,
      snapshotStale: false,
    });

    expect(decisionActions(view)).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          title: "review duration",
          to: "/risk-tensor?report_date=2026-04-30",
          sourceLabel: "risk-tensor",
          statusKind: "ready",
        }),
        expect.objectContaining({
          id: "risk-overview",
          to: "/risk-overview?report_date=2026-04-30",
          sourceLabel: "risk",
        }),
      ]),
    );
  });

  it("does not fabricate clickable action links when the home snapshot is unavailable", () => {
    const view = mapToHomeFirstScreenView({
      reportDate: "2026-04-30",
      useMockFallback: false,
      verdict: null,
      metrics: [],
      attribution: null,
      bondHeadline: null,
      portfolio: null,
      snapshotMeta: null,
      alertCount: 0,
      snapshotUnavailable: true,
      snapshotStale: false,
    });

    const actions = decisionActions(view);
    expect(actions).toHaveLength(1);
    expect(actions[0]).toEqual(
      expect.objectContaining({
        id: "snapshot-unavailable",
        to: undefined,
        statusKind: "backend-gap",
      }),
    );
  });

  it("uses a non-clickable empty action when there is no backend drilldown work", () => {
    const view = mapToHomeFirstScreenView({
      reportDate: "2026-04-30",
      useMockFallback: false,
      verdict: null,
      metrics: [],
      attribution: null,
      bondHeadline: null,
      portfolio: null,
      snapshotMeta: null,
      alertCount: 0,
      snapshotUnavailable: false,
      snapshotStale: false,
    });

    const actions = decisionActions(view);
    expect(actions).toHaveLength(1);
    expect(actions[0]).toEqual(
      expect.objectContaining({
        id: "no-action",
        to: undefined,
        statusKind: "empty",
      }),
    );
  });

  it("ignores backend suggestion links outside the known workbench drilldowns", () => {
    const view = mapToHomeFirstScreenView({
      reportDate: "2026-04-30",
      useMockFallback: false,
      verdict: {
        ...verdict,
        suggestions: [{ text: "open unknown page", link: "/not-a-workbench-route" }],
      },
      metrics: [],
      attribution: null,
      bondHeadline: null,
      portfolio: null,
      snapshotMeta: null,
      alertCount: 0,
      snapshotUnavailable: false,
      snapshotStale: false,
    });

    expect(decisionActions(view)).toEqual([
      expect.objectContaining({
        id: "no-action",
        to: undefined,
        statusKind: "empty",
      }),
    ]);
  });

  it("renders decision actions as drilldown links", () => {
    const view = firstScreenView();

    render(
      <MemoryRouter>
        <DecisionRailSection
          decisionRail={view.decisionRail}
          reportDate={view.reportDate}
          dataSyncPrefix={view.headerStatus.dataSyncPrefix}
          dataStatusKind={view.headerStatus.dataStatusKind}
        />
      </MemoryRouter>,
    );

    expect(screen.getByTestId("dashboard-home-decision-action-risk-overview")).toHaveAttribute(
      "href",
      "/risk-overview?report_date=2026-04-30",
    );
  });

  it("routes the first-screen risk strip to the real risk overview page", () => {
    render(
      <MemoryRouter>
        <TerminalHomeFirstScreen view={firstScreenView()} />
      </MemoryRouter>,
    );

    const marketPanel = screen.getByTestId("dashboard-home-market");
    expect(within(marketPanel).getByRole("link")).toHaveAttribute("href", "/risk-overview");
  });
});
