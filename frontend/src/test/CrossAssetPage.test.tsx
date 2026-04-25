import { useState, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";

vi.mock("../lib/echarts", () => ({
  default: () => <div data-testid="cross-asset-echarts-stub" />,
}));

import { ApiClientProvider, createApiClient, type ApiClient } from "../api/client";
import CrossAssetPage from "../features/cross-asset/pages/CrossAssetPage";

function renderPage(client: ApiClient = createApiClient({ mode: "mock" })) {
  function Wrapper({ children }: { children: ReactNode }) {
    const [queryClient] = useState(
      () =>
        new QueryClient({
          defaultOptions: {
            queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false },
          },
        }),
    );

    return (
      <MemoryRouter>
        <QueryClientProvider client={queryClient}>
          <ApiClientProvider client={client}>{children}</ApiClientProvider>
        </QueryClientProvider>
      </MemoryRouter>
    );
  }

  return render(
    <Wrapper>
      <CrossAssetPage />
    </Wrapper>,
  );
}

describe("CrossAssetPage", () => {
  it("renders first-screen investment research judgments from backend additive fields", async () => {
    const client = createApiClient({ mode: "mock" });
    const linkagePayload = await client.getMacroBondLinkageAnalysis({ reportDate: "2026-04-10" });

    vi.spyOn(client, "getMacroBondLinkageAnalysis").mockResolvedValue({
      ...linkagePayload,
      result: {
        ...linkagePayload.result,
        research_views: [
          {
            key: "duration",
            status: "ready",
            stance: "bullish",
            confidence: "high",
            summary: "Duration view favors adding exposure.",
            affected_targets: ["rates", "ncd", "high_grade_credit"],
            evidence: ["Liquidity remains supportive."],
          },
          {
            key: "curve",
            status: "ready",
            stance: "barbell",
            confidence: "medium",
            summary: "Curve view prefers front-end carry with selective extension.",
            affected_targets: ["rates", "ncd"],
            evidence: ["Funding stays loose."],
          },
          {
            key: "credit",
            status: "ready",
            stance: "selective",
            confidence: "medium",
            summary: "Credit view stays focused on high grade.",
            affected_targets: ["high_grade_credit"],
            evidence: ["Spread beta remains controlled."],
          },
          {
            key: "instrument",
            status: "ready",
            stance: "barbell",
            confidence: "medium",
            summary: "Instrument view prefers rates plus high-grade credit.",
            affected_targets: ["rates", "ncd", "high_grade_credit"],
            evidence: ["Cross-asset evidence is mixed but constructive."],
          },
        ],
        transmission_axes: [
          {
            axis_key: "global_rates",
            status: "ready",
            stance: "restrictive",
            summary: "Global rates cap aggressive long-end chasing.",
            impacted_views: ["duration", "curve"],
            required_series_ids: ["UST10Y"],
            warnings: [],
          },
          {
            axis_key: "equity_bond_spread",
            status: "pending_signal",
            stance: "neutral",
            summary: "Awaiting governed equity-bond spread proxy.",
            impacted_views: ["duration", "credit"],
            required_series_ids: ["CA.CSI300"],
            warnings: ["missing governed proxy series"],
          },
        ],
      },
    });

    renderPage(client);

    expect(await screen.findByTestId("cross-asset-drivers-page")).toBeInTheDocument();
    expect(await screen.findByTestId("cross-asset-ncd-proxy")).toBeInTheDocument();
    expect(screen.getByTestId("cross-asset-ncd-proxy-warning")).toBeInTheDocument();
    expect(await screen.findByText("Duration view favors adding exposure.")).toBeInTheDocument();
    expect(screen.getByTestId("cross-asset-research-views")).toBeInTheDocument();
    expect(screen.getByTestId("cross-asset-transmission-axes")).toBeInTheDocument();
    expect(screen.getByTestId("cross-asset-research-card-duration")).toHaveTextContent(
      "Duration view favors adding exposure.",
    );
    expect(screen.getByTestId("cross-asset-research-card-instrument")).toHaveTextContent(
      "Instrument view prefers rates plus high-grade credit.",
    );
    expect(screen.getByTestId("cross-asset-transmission-axis-global_rates")).toHaveTextContent(
      "Global rates cap aggressive long-end chasing.",
    );
    expect(screen.getByTestId("cross-asset-transmission-axis-equity_bond_spread")).toHaveTextContent(
      "Awaiting governed equity-bond spread proxy.",
    );
  });

  it("surfaces the data-driven cockpit sections and provenance flags", async () => {
    const client = {
      ...createApiClient({ mode: "mock" }),
      getResearchCalendarEvents: vi.fn(async () => [
        {
          id: "rc_supply_001",
          date: "2026-04-10",
          title: "国债供给窗口",
          kind: "supply" as const,
          severity: "medium" as const,
          amount_label: "净融资 180 亿元",
          note: "供给节奏",
        },
      ]),
    };

    renderPage(client);

    expect(await screen.findByTestId("cross-asset-drivers-page")).toBeInTheDocument();
    expect(screen.getByTestId("cross-asset-candidate-actions")).toBeInTheDocument();
    expect(screen.getByTestId("cross-asset-event-calendar")).toBeInTheDocument();
    expect(screen.getByTestId("cross-asset-watch-list")).toBeInTheDocument();
    expect(screen.getByTestId("cross-asset-page-output")).toBeInTheDocument();
    expect(await screen.findByText("国债供给窗口")).toBeInTheDocument();
    expect(screen.getByTestId("cross-asset-event-calendar")).not.toHaveTextContent("analytical only");
    expect((await screen.findAllByText("analytical only")).length).toBeGreaterThan(0);
  });

  it("surfaces a first-screen loading failure when the latest macro chain fails", async () => {
    const client = {
      ...createApiClient({ mode: "mock" }),
      getChoiceMacroLatest: vi.fn(async () => {
        throw new Error("choice latest failed");
      }),
    };

    renderPage(client);

    expect(await screen.findByTestId("cross-asset-drivers-page")).toBeInTheDocument();
    const firstScreenFlags = await screen.findByTestId("cross-asset-status-flags");
    expect(firstScreenFlags).toHaveTextContent("loading failure");
    expect(firstScreenFlags).toHaveTextContent("choice_macro.latest");
  });
});
