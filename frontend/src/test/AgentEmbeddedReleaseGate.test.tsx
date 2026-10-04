import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiClientProvider } from "../api/clientContext";
import { AgentPanel } from "../features/agent/AgentPanel";
import { BondAnalyticsAgentDrawer } from "../features/bond-analytics/components/BondAnalyticsAgentDrawer";
import { PnlAttributionAgentDrawer } from "../features/pnl-attribution/components/PnlAttributionAgentDrawer";
import { StockAnalysisWorkbenchActions } from "../features/stock-analysis/components/StockAnalysisWorkbenchActions";
import { DashboardHomeAgentDrawer } from "../features/workbench/dashboard-home/DashboardHomeAgentDrawer";
import { RiskOverviewAgentDrawer } from "../features/workbench/module-home/RiskOverviewAgentDrawer";

describe("embedded Agent release gate", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("hides all five page entry surfaces and keeps AgentPanel unable to submit", () => {
    render(
      <MemoryRouter>
      <ApiClientProvider>
        <StockAnalysisWorkbenchActions
          pickerDisplay={null}
          queueSearchText=""
          gateStatusLabel="ok"
          loopStatusLabel="ok"
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
        <PnlAttributionAgentDrawer
          open
          reportDate="2026-03-31"
          currentFilters={{}}
          onClose={() => undefined}
        />
        <AgentPanel pageId="test" />
      </ApiClientProvider>
      </MemoryRouter>,
    );

    expect(screen.queryByTestId("stock-analysis-agent-open")).not.toBeInTheDocument();
    expect(screen.queryByTestId("dashboard-home-agent-drawer")).not.toBeInTheDocument();
    expect(screen.queryByTestId("risk-overview-agent-drawer")).not.toBeInTheDocument();
    expect(screen.queryByTestId("bond-analysis-agent-drawer")).not.toBeInTheDocument();
    expect(screen.queryByTestId("pnl-attribution-agent-open")).not.toBeInTheDocument();
    expect(screen.queryByTestId("pnl-attribution-agent-drawer")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("向 Agent 提问")).not.toBeInTheDocument();
    expect(screen.queryByTestId("agent-panel-submit")).not.toBeInTheDocument();
  });

  it.each([true, false])("opens all five page entry surfaces with the release flag when DEV=%s", (dev) => {
    vi.stubEnv("DEV", dev);
    vi.stubEnv("VITE_MOSS_AGENT_FRONTEND_ENABLED", "true");

    render(
      <MemoryRouter>
      <ApiClientProvider>
        <StockAnalysisWorkbenchActions
          pickerDisplay={null}
          queueSearchText=""
          gateStatusLabel="ok"
          loopStatusLabel="ok"
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
        <PnlAttributionAgentDrawer
          open
          reportDate="2026-03-31"
          currentFilters={{}}
          onClose={() => undefined}
        />
      </ApiClientProvider>
      </MemoryRouter>,
    );

    expect(screen.getByTestId("stock-analysis-agent-open")).toBeInTheDocument();
    expect(screen.getByTestId("dashboard-home-agent-drawer")).toBeInTheDocument();
    expect(screen.getByTestId("risk-overview-agent-drawer")).toBeInTheDocument();
    expect(screen.getByTestId("bond-analysis-agent-drawer")).toBeInTheDocument();
    expect(screen.getByTestId("pnl-attribution-agent-drawer")).toBeInTheDocument();
  });

  it("prefills the pnl review workflow without automatically submitting it", async () => {
    vi.stubEnv("VITE_MOSS_AGENT_FRONTEND_ENABLED", "true");
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    render(
      <ApiClientProvider>
        <PnlAttributionAgentDrawer
          open
          reportDate="2026-03-31"
          currentFilters={{ active_tab: "product-category", compare: "mom" }}
          onClose={() => undefined}
        />
      </ApiClientProvider>,
    );

    expect(screen.getByTestId("pnl-attribution-agent-drawer")).toBeInTheDocument();
    expect(await screen.findByLabelText("向 Agent 提问")).toHaveValue("/pnl-review");
    expect(screen.getByText("只读")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
