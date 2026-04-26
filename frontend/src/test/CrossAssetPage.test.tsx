import { useState, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
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
    const latestPayload = await client.getChoiceMacroLatest();
    const baseCsi300 = latestPayload.result.series.find((point) => point.series_id === "CA.CSI300")!;
    vi.spyOn(client, "getChoiceMacroLatest").mockResolvedValue({
      ...latestPayload,
      result_meta: {
        ...latestPayload.result_meta,
        vendor_status: "vendor_unavailable",
      },
      result: {
        ...latestPayload.result,
        series: [
          ...latestPayload.result.series,
          {
            ...baseCsi300,
            series_id: "CA.CSI300_PE",
            series_name: "沪深300市盈率",
            value_numeric: 14.58,
            unit: "x",
            latest_change: 0.16,
          },
          {
            ...baseCsi300,
            series_id: "CA.MEGA_CAP_WEIGHT",
            series_name: "沪深300前十大权重",
            trade_date: "2026-04-01",
            value_numeric: 23.5367,
            unit: "%",
            latest_change: 0.2,
          },
          {
            ...baseCsi300,
            series_id: "CA.MEGA_CAP_TOP5_WEIGHT",
            series_name: "沪深300前五大权重",
            trade_date: "2026-04-01",
            value_numeric: 15.532,
            unit: "%",
            latest_change: 0.1,
          },
        ],
      },
    });
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
            status: "ready",
            stance: "conflicted",
            summary: "CSI300 equity-bond spread is 5.10ppt with CSI300 move -0.35%.",
            impacted_views: ["duration", "credit"],
            required_series_ids: ["tushare.index.000300.SH.daily", "tushare.index.000300.SH.dailybasic"],
            warnings: [],
          },
          {
            axis_key: "mega_cap_equities",
            status: "ready",
            stance: "neutral",
            summary: "CSI300 top10 weight concentration is 23.54% (top5 15.53%).",
            impacted_views: ["credit", "instrument"],
            required_series_ids: ["tushare.index.000300.SH.weight"],
            warnings: [],
          },
        ],
      },
    });

    renderPage(client);

    expect(await screen.findByTestId("cross-asset-drivers-page")).toBeInTheDocument();
    expect(await screen.findByTestId("cross-asset-ncd-proxy")).toBeInTheDocument();
    expect(screen.getByTestId("cross-asset-ncd-proxy-warning")).toBeInTheDocument();
    await waitFor(() => {
      const warning = screen.getByTestId("cross-asset-ncd-proxy-warning");
      expect(warning).toHaveTextContent(/not actual NCD issuance matrix/i);
      expect(warning).toHaveTextContent(/landed|quote medians unavailable/i);
    });
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
    expect(screen.getByTestId("cross-asset-transmission-axis-global_rates")).toHaveTextContent("已就绪");
    expect(screen.getByTestId("cross-asset-transmission-axis-global_rates")).toHaveTextContent("偏紧");
    expect(screen.getByTestId("cross-asset-transmission-axis-equity_bond_spread")).toHaveTextContent(
      "CSI300 equity-bond spread",
    );
    expect(screen.getByTestId("cross-asset-transmission-axis-mega_cap_equities")).toHaveTextContent("23.54%");
    expect(screen.getByTestId("cross-asset-asset-class-analysis")).toBeInTheDocument();
    expect(screen.getByTestId("cross-asset-asset-analysis-stock")).toHaveTextContent("股票分析");
    expect(screen.getByTestId("cross-asset-asset-analysis-commodities")).toHaveTextContent("大宗商品");
    expect(screen.getByTestId("cross-asset-asset-analysis-options")).toHaveTextContent("期权");
    expect(screen.getByTestId("cross-asset-asset-analysis-options")).toHaveTextContent("\u5f85\u63a5\u5165");
    expect(screen.getByTestId("cross-asset-asset-class-analysis")).toHaveTextContent("\u8de8\u8d44\u4ea7\u7ed3\u8bba");
    expect(screen.getByTestId("cross-asset-asset-class-analysis")).toHaveTextContent("\u5f85\u63a5\u5165\u6e05\u5355");
    expect(screen.getByTestId("cross-asset-asset-class-analysis")).toHaveTextContent("Choice");
    expect(screen.getByTestId("cross-asset-asset-class-analysis")).toHaveTextContent("Tushare");
    expect(screen.getByTestId("cross-asset-status-flags")).toHaveTextContent("source_blocked");
    const stockBroadIndex = screen.getByTestId("cross-asset-asset-analysis-stock-broad_index");
    expect(stockBroadIndex).toBeInTheDocument();
    expect(stockBroadIndex).toHaveTextContent("source_blocked");
    expect(stockBroadIndex).not.toHaveTextContent("EMM01843735");
    expect(stockBroadIndex.querySelector(".cross-asset-class-analysis__line-source")?.getAttribute("title")).toContain(
      "EMM01843735",
    );
    expect(screen.getByTestId("cross-asset-asset-analysis-stock-valuation_spread")).toHaveTextContent("14.58");
    expect(screen.getByTestId("cross-asset-asset-analysis-stock-mega_cap_weight")).toBeInTheDocument();
    expect(screen.getByTestId("cross-asset-asset-analysis-stock-mega_cap_weight")).toHaveTextContent("23.54%");
    expect(screen.getByTestId("cross-asset-asset-analysis-stock-mega_cap_weight")).toHaveTextContent("15.53%");
    const equityEvidence = screen.getByTestId("cross-asset-equity-evidence");
    expect(equityEvidence).toHaveTextContent("EMM01843735");
    expect(equityEvidence).toHaveTextContent("CA.CSI300_PE");
    expect(equityEvidence).toHaveTextContent("CA.MEGA_CAP_WEIGHT");
    expect(equityEvidence).toHaveTextContent("CA.MEGA_CAP_TOP5_WEIGHT");
    expect(equityEvidence).toHaveTextContent("index");
    expect(equityEvidence).toHaveTextContent("x");
    expect(equityEvidence).toHaveTextContent("%");
    const commoditiesEnergy = screen.getByTestId("cross-asset-asset-analysis-commodities-energy");
    expect(commoditiesEnergy).toBeInTheDocument();
    expect(commoditiesEnergy).not.toHaveTextContent("CA.BRENT");
    expect(commoditiesEnergy.querySelector(".cross-asset-class-analysis__line-source")?.getAttribute("title")).toContain(
      "CA.BRENT",
    );
    const commoditiesFerrous = screen.getByTestId("cross-asset-asset-analysis-commodities-ferrous");
    expect(commoditiesFerrous).toBeInTheDocument();
    expect(commoditiesFerrous).not.toHaveTextContent("CA.STEEL");
    expect(commoditiesFerrous.querySelector(".cross-asset-class-analysis__line-source")?.getAttribute("title")).toContain(
      "CA.STEEL",
    );
    expect(screen.getByTestId("cross-asset-asset-analysis-commodities-nonferrous")).toBeInTheDocument();
    expect(screen.getByTestId("cross-asset-asset-analysis-options-equity_options")).toBeInTheDocument();
    expect(screen.getByTestId("cross-asset-asset-analysis-options-equity_options")).toHaveTextContent("Choice");
    expect(screen.getByTestId("cross-asset-asset-analysis-options-commodity_options")).toBeInTheDocument();
    expect(screen.getByTestId("cross-asset-asset-analysis-options-rates_bond_options")).toBeInTheDocument();
    expect(screen.getByTestId("cross-asset-asset-analysis-options")).not.toHaveTextContent("Evidence:");
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
