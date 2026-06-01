import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiClientProvider, createApiClient } from "../api/client";
import type { ResultMeta } from "../api/contracts";
import CustomerDetailModal from "../features/positions/components/CustomerDetailModal";

vi.mock("../lib/echarts", () => ({
  __esModule: true,
  default: () => <div data-testid="customer-detail-echarts-stub" />,
}));

function resultMeta(resultKind: string): ResultMeta {
  return {
    trace_id: "tr_positions_customer",
    basis: "formal",
    result_kind: resultKind,
    formal_use_allowed: true,
    source_version: "sv",
    vendor_version: "vv",
    rule_version: "rv",
    cache_version: "cv",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-04-12T00:00:00Z",
  };
}

function renderModal(client: ReturnType<typeof createApiClient>) {
  return render(
    <QueryClientProvider
      client={
        new QueryClient({
          defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } },
        })
      }
    >
      <ApiClientProvider client={client}>
        <CustomerDetailModal
          open
          customerName="客户A"
          reportDate="2026-03-31"
          onClose={vi.fn()}
        />
      </ApiClientProvider>
    </QueryClientProvider>,
  );
}

describe("CustomerDetailModal", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders customer holding market values in yi yuan", async () => {
    const client = {
      ...createApiClient({ mode: "mock" }),
      getPositionsCustomerDetails: vi.fn(async () => ({
        result_meta: resultMeta("positions.customer.details"),
        result: {
          customer_name: "客户A",
          report_date: "2026-03-31",
          total_market_value: "200000000",
          bond_count: 1,
          items: [
            {
              bond_code: "BOND-1",
              sub_type: "信用债",
              asset_class: "credit",
              market_value: "100000000",
              yield_rate: "0.025",
              maturity_date: "2027-03-31",
              rating: "AAA",
              industry: "金融",
            },
          ],
        },
      })),
      getPositionsCustomerTrend: vi.fn(async () => ({
        result_meta: resultMeta("positions.customer.trend"),
        result: {
          customer_name: "客户A",
          start_date: "2026-03-01",
          end_date: "2026-03-31",
          days: 30,
          items: [],
        },
      })),
    };

    renderModal(client);

    expect(await screen.findByText("BOND-1")).toBeInTheDocument();
    expect(screen.getByText("2.00 亿元")).toBeInTheDocument();
    expect(screen.getByText("1.00 亿元")).toBeInTheDocument();
  });
});
