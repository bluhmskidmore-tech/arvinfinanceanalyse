import { render, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiClientProvider, createApiClient } from "../api/client";
import { AssetStructurePie } from "../features/bond-dashboard/components/AssetStructurePie";
import { BOND_SECTION_READY } from "../features/bond-dashboard/sectionStatus";
import IndustryDistributionCard from "../features/positions/components/IndustryDistributionCard";
import { formatRawAsNumeric } from "../utils/format";
import { portfolioCrossPageEnvelope } from "./portfolioCrossPageGoldenSample";

const chart = vi.hoisted(() => ({ option: null as unknown }));
vi.mock("../lib/echarts", () => ({
  default: ({ option }: { option: unknown }) => { chart.option = option; return null; },
}));

function tooltip(params: unknown): HTMLElement {
  const option = chart.option as { tooltip: { formatter: (value: unknown) => string | HTMLElement } };
  const content = option.tooltip.formatter(params);
  const host = document.createElement("div");
  if (typeof content === "string") host.innerHTML = content;
  else host.append(content);
  return host;
}

beforeEach(() => { chart.option = null; });

describe("chart tooltip source text", () => {
  const attack = '<img src=x onerror="window.auditProof=1"> & <svg onload="window.auditProof=2">';

  it("renders the industry name literally without creating source HTML nodes", async () => {
    const client = createApiClient({ mode: "mock" });
    vi.spyOn(client, "getPositionsStatsIndustry").mockResolvedValue(portfolioCrossPageEnvelope("positions.industry", {
      start_date: "2026-08-01", end_date: "2026-08-31", num_days: 31,
      total_amount: "100", total_avg_daily: "100",
      items: [{ industry: attack, total_amount: "100", avg_daily_balance: "100", weighted_rate: null, bond_count: 1, percentage: "12.5" }],
    }));
    render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <ApiClientProvider client={client}><IndustryDistributionCard startDate="2026-08-01" endDate="2026-08-31" /></ApiClientProvider>
    </QueryClientProvider>);
    await waitFor(() => expect(chart.option).not.toBeNull());
    const host = tooltip([{ dataIndex: 0, value: 12.5 }]);
    expect(host.querySelector("img,svg,script")).toBeNull();
    expect(host.textContent).toBe(`${attack}占比：12.50%`);
  });

  it("renders the asset category literally while retaining backend percentage and amounts", () => {
    const yuan = formatRawAsNumeric({ raw: 100000000, unit: "yuan", sign_aware: false });
    const percentage = formatRawAsNumeric({ raw: 0.125, unit: "ratio", sign_aware: false });
    render(<AssetStructurePie state={BOND_SECTION_READY} groupBy="portfolio_name" onGroupByChange={() => undefined}
      data={{ report_date: "2026-08-31", group_by: "portfolio_name", total_market_value: yuan,
        items: [{ category: attack, total_market_value: yuan, bond_count: 1, percentage }] }} />);
    const option = chart.option as { series: Array<{ data: Array<Record<string, unknown>> }> };
    const datum = option.series[0].data[0];
    const host = tooltip({ ...datum, data: datum, percent: 100 });
    expect(host.querySelector("img,svg,script")).toBeNull();
    expect(host.textContent).toBe(`${attack}12.50%1.00 亿1 只`);
  });
});
