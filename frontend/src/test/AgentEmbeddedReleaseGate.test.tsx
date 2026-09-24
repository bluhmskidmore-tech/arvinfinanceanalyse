import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiClientProvider } from "../api/clientContext";
import { AgentPanel } from "../features/agent/AgentPanel";
import { BondAnalyticsAgentDrawer } from "../features/bond-analytics/components/BondAnalyticsAgentDrawer";
import { StockAnalysisWorkbenchActions } from "../features/stock-analysis/components/StockAnalysisWorkbenchActions";
import { DashboardHomeAgentDrawer } from "../features/workbench/dashboard-home/DashboardHomeAgentDrawer";
import { RiskOverviewAgentDrawer } from "../features/workbench/module-home/RiskOverviewAgentDrawer";

describe("embedded Agent release gate", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("hides all four page entry surfaces and keeps AgentPanel unable to submit", () => {
    render(
      <ApiClientProvider>
        <StockAnalysisWorkbenchActions
          pickerDisplay={null}
          queueSearchText=""
          dataStatusLabel="ok"
          dataStatusTone="positive"
          gateStatusLabel="ok"
          gateStatusTone="positive"
          loopStatusLabel="ok"
          loopStatusTone="positive"
          formalUseAllowed
          routeLabel="test"
          agentDrawerOpen={false}
          onAsOfOverrideChange={() => undefined}
          onQueueSearchTextChange={() => undefined}
          onOpenAgentDrawer={() => undefined}
          onRefresh={() => undefined}
        />
        <DashboardHomeAgentDrawer
          open
          reportDate="2026-01-01"
          currentFilters={{}}
          onClose={() => undefined}
        />
        <RiskOverviewAgentDrawer
          open
          reportDate="2026-01-01"
          currentFilters={{}}
          onClose={() => undefined}
        />
        <BondAnalyticsAgentDrawer
          open
          reportDate="2026-01-01"
          currentFilters={{}}
          onClose={() => undefined}
        />
        <AgentPanel pageId="test" />
      </ApiClientProvider>,
    );

    expect(screen.queryByTestId("stock-analysis-agent-open")).not.toBeInTheDocument();
    expect(screen.queryByTestId("dashboard-home-agent-drawer")).not.toBeInTheDocument();
    expect(screen.queryByTestId("risk-overview-agent-drawer")).not.toBeInTheDocument();
    expect(screen.queryByTestId("bond-analysis-agent-drawer")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("向 Agent 提问")).not.toBeInTheDocument();
    expect(screen.queryByTestId("agent-panel-submit")).not.toBeInTheDocument();
  });

  it("opens all four page entry surfaces only with the explicit development opt-in", () => {
    vi.stubEnv("VITE_MOSS_AGENT_FRONTEND_ENABLED", "true");

    render(
      <ApiClientProvider>
        <StockAnalysisWorkbenchActions
          pickerDisplay={null}
          queueSearchText=""
          dataStatusLabel="ok"
          dataStatusTone="positive"
          gateStatusLabel="ok"
          gateStatusTone="positive"
          loopStatusLabel="ok"
          loopStatusTone="positive"
          formalUseAllowed
          routeLabel="test"
          agentDrawerOpen={false}
          onAsOfOverrideChange={() => undefined}
          onQueueSearchTextChange={() => undefined}
          onOpenAgentDrawer={() => undefined}
          onRefresh={() => undefined}
        />
        <DashboardHomeAgentDrawer
          open
          reportDate="2026-01-01"
          currentFilters={{}}
          onClose={() => undefined}
        />
        <RiskOverviewAgentDrawer
          open
          reportDate="2026-01-01"
          currentFilters={{}}
          onClose={() => undefined}
        />
        <BondAnalyticsAgentDrawer
          open
          reportDate="2026-01-01"
          currentFilters={{}}
          onClose={() => undefined}
        />
      </ApiClientProvider>,
    );

    expect(screen.getByTestId("stock-analysis-agent-open")).toBeInTheDocument();
    expect(screen.getByTestId("dashboard-home-agent-drawer")).toBeInTheDocument();
    expect(screen.getByTestId("risk-overview-agent-drawer")).toBeInTheDocument();
    expect(screen.getByTestId("bond-analysis-agent-drawer")).toBeInTheDocument();
  });
});
