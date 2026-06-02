import { useState, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ApiClientProvider, createApiClient, type ApiClient } from "../api/client";
import type { BalanceAnalysisDecisionItemsPayload, ResultMeta } from "../api/contracts";
import DecisionItemsPage from "../features/decision-items/pages/DecisionItemsPage";

const testMeta: ResultMeta = {
  trace_id: "tr_decision_items_test",
  basis: "formal",
  result_kind: "balance-analysis.decision-items",
  formal_use_allowed: true,
  source_version: "sv_test",
  vendor_version: "vv_test",
  rule_version: "rv_test",
  cache_version: "cv_test",
  quality_flag: "ok",
  vendor_status: "ok",
  fallback_mode: "none",
  scenario_flag: false,
  generated_at: "2026-04-24T00:00:00Z",
};

function decisionItemsPayload(overrides: Partial<BalanceAnalysisDecisionItemsPayload>): BalanceAnalysisDecisionItemsPayload {
  return {
    report_date: "2026-03-31",
    position_scope: "all",
    currency_basis: "native",
    columns: [{ key: "title", label: "Title" }],
    rows: [],
    ...overrides,
  };
}

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
      <DecisionItemsPage />
    </Wrapper>,
  );
}

function openAntSelectByTestId(testId: string) {
  const root = screen.getByTestId(testId);
  const selector = root.querySelector(".ant-select-selector");
  if (!selector) {
    throw new Error(`ant select shell not found for ${testId}`);
  }
  fireEvent.mouseDown(selector);
}

describe("DecisionItemsPage", () => {
  it("defaults to the latest available report date and loads decision items for it", async () => {
    const client = createApiClient({ mode: "mock" });
    vi.spyOn(client, "getBalanceAnalysisDates").mockResolvedValue({
      result_meta: testMeta,
      result: { report_dates: ["2026-01-01", "2026-03-31"] },
    });
    const itemsSpy = vi.spyOn(client, "getBalanceAnalysisDecisionItems");

    renderPage(client);

    await waitFor(() => {
      expect(itemsSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          reportDate: "2026-03-31",
          positionScope: "all",
          currencyBasis: "CNY",
        }),
      );
    });
    expect(await screen.findByTestId("decision-items-page")).toBeInTheDocument();
  });

  it("refetches decision items when position scope changes", async () => {
    const client = createApiClient({ mode: "mock" });
    vi.spyOn(client, "getBalanceAnalysisDates").mockResolvedValue({
      result_meta: testMeta,
      result: { report_dates: ["2026-03-31"] },
    });
    const itemsSpy = vi.spyOn(client, "getBalanceAnalysisDecisionItems");

    renderPage(client);

    await waitFor(() => expect(itemsSpy).toHaveBeenCalledTimes(1));
    expect(itemsSpy.mock.calls[0]![0].positionScope).toBe("all");

    openAntSelectByTestId("decision-items-position-scope");
    const assetOption = (await screen.findAllByText("资产")).at(-1);
    if (!assetOption) {
      throw new Error("资产 option not found");
    }
    fireEvent.click(assetOption);

    await waitFor(() => {
      expect(itemsSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          reportDate: "2026-03-31",
          positionScope: "asset",
        }),
      );
    });
  });

  it("refetches decision items when currency basis changes", async () => {
    const client = createApiClient({ mode: "mock" });
    vi.spyOn(client, "getBalanceAnalysisDates").mockResolvedValue({
      result_meta: testMeta,
      result: { report_dates: ["2026-03-31"] },
    });
    const itemsSpy = vi.spyOn(client, "getBalanceAnalysisDecisionItems");

    renderPage(client);

    await waitFor(() => expect(itemsSpy).toHaveBeenCalledTimes(1));
    expect(itemsSpy.mock.calls[0]![0].currencyBasis).toBe("CNY");

    openAntSelectByTestId("decision-items-currency-basis");
    const nativeOption = (await screen.findAllByText(/native/i)).at(-1);
    if (!nativeOption) {
      throw new Error("native option not found");
    }
    fireEvent.click(nativeOption);

    await waitFor(() => {
      expect(itemsSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          reportDate: "2026-03-31",
          currencyBasis: "CNY",
        }),
      );
    });
  });

  it("filters rows by status selection", async () => {
    const client = createApiClient({ mode: "mock" });
    vi.spyOn(client, "getBalanceAnalysisDates").mockResolvedValue({
      result_meta: testMeta,
      result: { report_dates: ["2026-03-31"] },
    });
    vi.spyOn(client, "getBalanceAnalysisDecisionItems").mockResolvedValue({
      result_meta: testMeta,
      result: decisionItemsPayload({
        rows: [
          {
            decision_key: "row-pending",
            title: "Pending row",
            action_label: "Act",
            severity: "low",
            reason: "r1",
            source_section: "s1",
            rule_id: "rule_a",
            rule_version: "v1",
            latest_status: {
              decision_key: "row-pending",
              status: "pending",
              updated_at: null,
              updated_by: null,
              comment: null,
            },
          },
          {
            decision_key: "row-done",
            title: "Done row",
            action_label: "Act",
            severity: "low",
            reason: "r2",
            source_section: "s2",
            rule_id: "rule_b",
            rule_version: "v1",
            latest_status: {
              decision_key: "row-done",
              status: "confirmed",
              updated_at: null,
              updated_by: null,
              comment: null,
            },
          },
        ],
      }),
    });

    renderPage(client);

    expect(await screen.findByTestId("decision-items-list")).toBeInTheDocument();
    expect(screen.getByTestId("decision-items-row-0")).toHaveTextContent("Pending row");
    expect(screen.getByTestId("decision-items-row-1")).toHaveTextContent("Done row");

    openAntSelectByTestId("decision-items-status-filter");
    const pendingOption = (await screen.findAllByText("待处理")).at(-1);
    if (!pendingOption) {
      throw new Error("待处理 option not found");
    }
    fireEvent.click(pendingOption);

    await waitFor(() => {
      expect(screen.queryByTestId("decision-items-row-1")).not.toBeInTheDocument();
    });
    expect(screen.getByTestId("decision-items-row-0")).toHaveTextContent("Pending row");
  });

  it("calls update API on confirm with scope, basis, decision key, status and comment then refetches", async () => {
    const client = createApiClient({ mode: "mock" });
    vi.spyOn(client, "getBalanceAnalysisDates").mockResolvedValue({
      result_meta: testMeta,
      result: { report_dates: ["2026-03-31"] },
    });
    vi.spyOn(client, "getBalanceAnalysisDecisionItems").mockResolvedValue({
      result_meta: testMeta,
      result: decisionItemsPayload({
        rows: [
          {
            decision_key: "row-1",
            title: "T1",
            action_label: "Act",
            severity: "high",
            reason: "r",
            source_section: "sec",
            rule_id: "rid",
            rule_version: "v1",
            latest_status: {
              decision_key: "row-1",
              status: "pending",
              updated_at: null,
              updated_by: null,
              comment: null,
            },
          },
        ],
      }),
    });
    const updateSpy = vi.spyOn(client, "updateBalanceAnalysisDecisionStatus");
    const itemsSpy = vi.spyOn(client, "getBalanceAnalysisDecisionItems");

    renderPage(client);

    await screen.findByTestId("decision-items-list");
    fireEvent.click(screen.getByTestId("decision-items-row-0"));

    const detail = await screen.findByTestId("decision-items-detail");
    const textarea = within(detail).getByRole("textbox");
    fireEvent.change(textarea, { target: { value: "复核备注" } });

    fireEvent.click(screen.getByTestId("decision-items-confirm-0"));

    await waitFor(() => {
      expect(updateSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          reportDate: "2026-03-31",
          positionScope: "all",
          currencyBasis: "CNY",
          decisionKey: "row-1",
          status: "confirmed",
          comment: "复核备注",
        }),
      );
    });

    await waitFor(() => expect(itemsSpy.mock.calls.length).toBeGreaterThanOrEqual(2));
  });

  it("surfaces update failures in the error region", async () => {
    const client = createApiClient({ mode: "mock" });
    vi.spyOn(client, "getBalanceAnalysisDates").mockResolvedValue({
      result_meta: testMeta,
      result: { report_dates: ["2026-03-31"] },
    });
    vi.spyOn(client, "getBalanceAnalysisDecisionItems").mockResolvedValue({
      result_meta: testMeta,
      result: decisionItemsPayload({
        rows: [
          {
            decision_key: "row-1",
            title: "T1",
            action_label: "Act",
            severity: "high",
            reason: "r",
            source_section: "sec",
            rule_id: "rid",
            rule_version: "v1",
            latest_status: {
              decision_key: "row-1",
              status: "pending",
              updated_at: null,
              updated_by: null,
              comment: null,
            },
          },
        ],
      }),
    });
    vi.spyOn(client, "updateBalanceAnalysisDecisionStatus").mockRejectedValue(new Error("write blocked"));

    renderPage(client);

    await screen.findByTestId("decision-items-list");
    fireEvent.click(screen.getByTestId("decision-items-confirm-0"));

    expect(await screen.findByTestId("decision-items-error")).toHaveTextContent(/write blocked/);
  });

  it("shows an empty state when the payload has no rows", async () => {
    const client = createApiClient({ mode: "mock" });
    vi.spyOn(client, "getBalanceAnalysisDates").mockResolvedValue({
      result_meta: testMeta,
      result: { report_dates: ["2026-03-31"] },
    });
    vi.spyOn(client, "getBalanceAnalysisDecisionItems").mockResolvedValue({
      result_meta: testMeta,
      result: decisionItemsPayload({ rows: [] }),
    });

    renderPage(client);

    expect(await screen.findByText("本报告日未返回决策事项。")).toBeInTheDocument();
  });

  it("surfaces contract warnings for incomplete rows", async () => {
    const client = createApiClient({ mode: "mock" });
    vi.spyOn(client, "getBalanceAnalysisDates").mockResolvedValue({
      result_meta: testMeta,
      result: { report_dates: ["2026-03-31"] },
    });
    vi.spyOn(client, "getBalanceAnalysisDecisionItems").mockResolvedValue({
      result_meta: testMeta,
      result: decisionItemsPayload({
        rows: [
          {
            decision_key: "bad-row",
            title: "",
            action_label: "Act",
            severity: "high",
            reason: "r",
            source_section: "sec",
            rule_id: "rid",
            rule_version: "v1",
            latest_status: {
              decision_key: "bad-row",
              status: "pending",
              updated_at: null,
              updated_by: null,
              comment: null,
            },
          },
        ],
      }),
    });

    renderPage(client);

    const warn = await screen.findByTestId("decision-items-contract-warning");
    expect(warn).toHaveTextContent(/missing or empty title/i);
  });
});
