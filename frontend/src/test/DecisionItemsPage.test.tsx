import { useState, type ReactNode } from "react";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, useNavigate } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ApiClientProvider, createApiClient, type ApiClient } from "../api/client";
import type {
  BalanceAnalysisDecisionItemStatusRow,
  BalanceAnalysisDecisionItemsPayload,
  ResultMeta,
} from "../api/contracts";
import DecisionItemsPage from "../features/decision-items/pages/DecisionItemsPage";

const decisionItemsPageSourcePath = resolve(
  process.cwd(),
  "src/features/decision-items/pages/DecisionItemsPage.tsx",
);
const decisionItemsPageCssPath = resolve(
  process.cwd(),
  "src/features/decision-items/pages/DecisionItemsPage.css",
);

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

function decisionItemRow(
  overrides: Partial<BalanceAnalysisDecisionItemStatusRow>,
): BalanceAnalysisDecisionItemStatusRow {
  const decisionKey = overrides.decision_key ?? "row-1";
  return {
    decision_key: decisionKey,
    title: "Decision item",
    action_label: "Act",
    severity: "medium",
    reason: "reason",
    source_section: "section",
    rule_id: "rule_a",
    rule_version: "v1",
    latest_status: {
      decision_key: decisionKey,
      status: "pending",
      updated_at: null,
      updated_by: null,
      comment: null,
    },
    ...overrides,
  };
}

function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false },
    },
  });
}

function renderPage(
  client: ApiClient = createApiClient({ mode: "mock" }),
  initialEntries: string[] = ["/decision-items"],
  queryClient: QueryClient = createTestQueryClient(),
) {
  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <MemoryRouter initialEntries={initialEntries}>
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

function DecisionItemsNavigationProbe({ to }: { to: string }) {
  const navigate = useNavigate();

  return (
    <button type="button" onClick={() => navigate(to)}>
      navigate decision items
    </button>
  );
}

describe("DecisionItemsPage", () => {
  it("keeps page-level style debt from regressing", () => {
    const pageSource = readFileSync(decisionItemsPageSourcePath, "utf8");
    const cssSource = readFileSync(decisionItemsPageCssPath, "utf8");
    const pageAndCss = `${pageSource}\n${cssSource}`;
    const privateShadowDeclarations = (
      cssSource.match(/box-shadow:[^;]+;/gi) ?? []
    ).filter((declaration) => !/box-shadow:\s*(none|var\()/i.test(declaration));

    expect(pageSource).not.toContain("style=");
    expect(pageAndCss).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
    expect(pageSource).not.toMatch(/boxShadow|rgba\(/);
    expect(privateShadowDeclarations).toEqual([]);
    expect(cssSource).not.toMatch(/rgba\(/);
  });

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

  it("uses the report date from dashboard decision action links", async () => {
    const client = createApiClient({ mode: "mock" });
    vi.spyOn(client, "getBalanceAnalysisDates").mockResolvedValue({
      result_meta: testMeta,
      result: { report_dates: ["2026-03-31", "2026-04-30"] },
    });
    const itemsSpy = vi.spyOn(client, "getBalanceAnalysisDecisionItems");

    renderPage(
      client,
      ["/decision-items?source=dashboard-home&report_date=2026-03-31&action_id=risk-review-queue"],
    );

    await waitFor(() => {
      expect(itemsSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          reportDate: "2026-03-31",
          positionScope: "all",
          currencyBasis: "CNY",
        }),
      );
    });
  });

  it("focuses dashboard risk review queue links on pending items with high severity first", async () => {
    const client = createApiClient({ mode: "mock" });
    vi.spyOn(client, "getBalanceAnalysisDates").mockResolvedValue({
      result_meta: testMeta,
      result: { report_dates: ["2026-03-31"] },
    });
    vi.spyOn(client, "getBalanceAnalysisDecisionItems").mockResolvedValue({
      result_meta: testMeta,
      result: decisionItemsPayload({
        rows: [
          decisionItemRow({
            decision_key: "pending-low",
            title: "Low pending item",
            severity: "low",
          }),
          decisionItemRow({
            decision_key: "confirmed-high",
            title: "Confirmed high item",
            severity: "high",
            latest_status: {
              decision_key: "confirmed-high",
              status: "confirmed",
              updated_at: null,
              updated_by: null,
              comment: null,
            },
          }),
          decisionItemRow({
            decision_key: "pending-high",
            title: "High pending item",
            severity: "high",
          }),
        ],
      }),
    });

    renderPage(
      client,
      ["/decision-items?source=dashboard-home&report_date=2026-03-31&action_id=risk-review-queue"],
    );

    expect(await screen.findByTestId("decision-items-entry-context")).toHaveTextContent(
      "首页风险复核队列",
    );
    expect(await screen.findByTestId("decision-items-list")).toBeInTheDocument();

    expect(screen.getByTestId("decision-items-row-0")).toHaveTextContent("High pending item");
    expect(screen.getByTestId("decision-items-row-1")).toHaveTextContent("Low pending item");
    expect(screen.queryByText("Confirmed high item")).not.toBeInTheDocument();
  });

  it("keeps ordinary decision items entry unfiltered by dashboard risk queue defaults", async () => {
    const client = createApiClient({ mode: "mock" });
    vi.spyOn(client, "getBalanceAnalysisDates").mockResolvedValue({
      result_meta: testMeta,
      result: { report_dates: ["2026-03-31"] },
    });
    vi.spyOn(client, "getBalanceAnalysisDecisionItems").mockResolvedValue({
      result_meta: testMeta,
      result: decisionItemsPayload({
        rows: [
          decisionItemRow({
            decision_key: "pending-low",
            title: "Low pending item",
            severity: "low",
          }),
          decisionItemRow({
            decision_key: "confirmed-high",
            title: "Confirmed high item",
            severity: "high",
            latest_status: {
              decision_key: "confirmed-high",
              status: "confirmed",
              updated_at: null,
              updated_by: null,
              comment: null,
            },
          }),
        ],
      }),
    });

    renderPage(client, ["/decision-items?report_date=2026-03-31"]);

    expect(screen.queryByTestId("decision-items-entry-context")).not.toBeInTheDocument();
    expect(await screen.findByTestId("decision-items-list")).toBeInTheDocument();
    expect(screen.getByTestId("decision-items-row-0")).toHaveTextContent("Low pending item");
    expect(screen.getByTestId("decision-items-row-1")).toHaveTextContent("Confirmed high item");
  });

  it("updates the decision items report date when the query changes in place", async () => {
    const client = createApiClient({ mode: "mock" });
    vi.spyOn(client, "getBalanceAnalysisDates").mockResolvedValue({
      result_meta: testMeta,
      result: { report_dates: ["2026-03-31", "2026-04-30"] },
    });
    const itemsSpy = vi.spyOn(client, "getBalanceAnalysisDecisionItems");

    function WrappedPage() {
      return (
        <>
          <DecisionItemsNavigationProbe to="/decision-items?report_date=2026-04-30" />
          <DecisionItemsPage />
        </>
      );
    }

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
        <MemoryRouter initialEntries={["/decision-items?report_date=2026-03-31"]}>
          <QueryClientProvider client={queryClient}>
            <ApiClientProvider client={client}>{children}</ApiClientProvider>
          </QueryClientProvider>
        </MemoryRouter>
      );
    }

    render(
      <Wrapper>
        <WrappedPage />
      </Wrapper>,
    );

    await waitFor(() => {
      expect(itemsSpy).toHaveBeenCalledWith(
        expect.objectContaining({ reportDate: "2026-03-31" }),
      );
    });

    fireEvent.click(screen.getByRole("button", { name: "navigate decision items" }));

    await waitFor(() => {
      expect(itemsSpy).toHaveBeenCalledWith(
        expect.objectContaining({ reportDate: "2026-04-30" }),
      );
    });
  });

  it("returns to the latest report date when dashboard report date query is removed", async () => {
    const client = createApiClient({ mode: "mock" });
    vi.spyOn(client, "getBalanceAnalysisDates").mockResolvedValue({
      result_meta: testMeta,
      result: { report_dates: ["2026-03-31", "2026-04-30"] },
    });
    const itemsSpy = vi.spyOn(client, "getBalanceAnalysisDecisionItems");

    function WrappedPage() {
      return (
        <>
          <DecisionItemsNavigationProbe to="/decision-items" />
          <DecisionItemsPage />
        </>
      );
    }

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
        <MemoryRouter initialEntries={["/decision-items?report_date=2026-03-31"]}>
          <QueryClientProvider client={queryClient}>
            <ApiClientProvider client={client}>{children}</ApiClientProvider>
          </QueryClientProvider>
        </MemoryRouter>
      );
    }

    render(
      <Wrapper>
        <WrappedPage />
      </Wrapper>,
    );

    await waitFor(() => {
      expect(itemsSpy).toHaveBeenCalledWith(
        expect.objectContaining({ reportDate: "2026-03-31" }),
      );
    });

    fireEvent.click(screen.getByRole("button", { name: "navigate decision items" }));

    await waitFor(() => {
      expect(itemsSpy).toHaveBeenCalledWith(
        expect.objectContaining({ reportDate: "2026-04-30" }),
      );
    });
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

    fireEvent.click(await screen.findByTestId("decision-items-confirm-0"));

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

  it("shows successful writeback feedback and invalidates dashboard home snapshot cache", async () => {
    const client = createApiClient({ mode: "mock" });
    const queryClient = createTestQueryClient();
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");
    vi.spyOn(client, "getBalanceAnalysisDates").mockResolvedValue({
      result_meta: testMeta,
      result: { report_dates: ["2026-03-31"] },
    });
    vi.spyOn(client, "getBalanceAnalysisDecisionItems").mockResolvedValue({
      result_meta: testMeta,
      result: decisionItemsPayload({
        rows: [
          decisionItemRow({
            decision_key: "row-1",
            title: "Risk queue item",
            severity: "high",
          }),
        ],
      }),
    });

    renderPage(
      client,
      ["/decision-items?source=dashboard-home&report_date=2026-03-31&action_id=risk-review-queue"],
      queryClient,
    );

    await screen.findByTestId("decision-items-list");
    fireEvent.click(await screen.findByTestId("decision-items-confirm-0"));

    expect(await screen.findByTestId("decision-items-update-feedback")).toHaveTextContent(
      "已确认并回写",
    );
    await waitFor(() => {
      expect(invalidateSpy).toHaveBeenCalledWith(
        expect.objectContaining({ queryKey: ["home-snapshot"] }),
      );
    });
  });

  it("allows scoped non-admin users to write decision item status", async () => {
    const client = createApiClient({ mode: "mock" });
    vi.spyOn(client, "getBalanceAnalysisDates").mockResolvedValue({
      result_meta: testMeta,
      result: { report_dates: ["2026-03-31"] },
    });
    vi.spyOn(client, "getBalanceAnalysisCurrentUser").mockResolvedValue({
      user_id: "decision-owner",
      role: "reviewer",
      identity_source: "header",
      can_write_decision_status: true,
    });
    const updateSpy = vi.spyOn(client, "updateBalanceAnalysisDecisionStatus");
    vi.spyOn(client, "getBalanceAnalysisDecisionItems").mockResolvedValue({
      result_meta: testMeta,
      result: decisionItemsPayload({
        rows: [
          decisionItemRow({
            decision_key: "row-1",
            title: "Scoped writer item",
            severity: "high",
          }),
        ],
      }),
    });

    renderPage(
      client,
      ["/decision-items?source=dashboard-home&report_date=2026-03-31&action_id=risk-review-queue"],
    );

    await screen.findByTestId("decision-items-list");
    fireEvent.click(await screen.findByTestId("decision-items-confirm-0"));

    await waitFor(() => {
      expect(updateSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          decisionKey: "row-1",
          status: "confirmed",
        }),
      );
    });
  });

  it("stores current-user capability under a mode-scoped query key", async () => {
    const client = createApiClient({ mode: "mock" });
    const queryClient = createTestQueryClient();
    vi.spyOn(client, "getBalanceAnalysisDates").mockResolvedValue({
      result_meta: testMeta,
      result: { report_dates: ["2026-03-31"] },
    });
    vi.spyOn(client, "getBalanceAnalysisCurrentUser").mockResolvedValue({
      user_id: "decision-owner",
      role: "reviewer",
      identity_source: "header",
      can_write_decision_status: true,
    });
    vi.spyOn(client, "getBalanceAnalysisDecisionItems").mockResolvedValue({
      result_meta: testMeta,
      result: decisionItemsPayload({
        rows: [
          decisionItemRow({
            decision_key: "row-1",
            title: "Scoped writer item",
            severity: "high",
          }),
        ],
      }),
    });

    renderPage(client, ["/decision-items?report_date=2026-03-31"], queryClient);

    await waitFor(() => {
      expect(queryClient.getQueryState(["balance-analysis", "current-user", "mock"])).toBeDefined();
    });
    expect(queryClient.getQueryState(["balance-analysis", "current-user"])).toBeUndefined();
  });

  it("uses decision write capability instead of admin role for read-only state", async () => {
    const client = createApiClient({ mode: "mock" });
    vi.spyOn(client, "getBalanceAnalysisDates").mockResolvedValue({
      result_meta: testMeta,
      result: { report_dates: ["2026-03-31"] },
    });
    vi.spyOn(client, "getBalanceAnalysisCurrentUser").mockResolvedValue({
      user_id: "admin-without-scope",
      role: "admin",
      identity_source: "header",
      can_write_decision_status: false,
    });
    const updateSpy = vi.spyOn(client, "updateBalanceAnalysisDecisionStatus");
    vi.spyOn(client, "getBalanceAnalysisDecisionItems").mockResolvedValue({
      result_meta: testMeta,
      result: decisionItemsPayload({
        rows: [
          decisionItemRow({
            decision_key: "row-1",
            title: "Read only item",
            severity: "high",
          }),
        ],
      }),
    });

    renderPage(
      client,
      ["/decision-items?source=dashboard-home&report_date=2026-03-31&action_id=risk-review-queue"],
    );

    expect(await screen.findByTestId("decision-items-readonly-notice")).toHaveTextContent(
      "无治理事项回写权限",
    );
    expect(screen.queryByTestId("decision-items-confirm-0")).not.toBeInTheDocument();
    expect(screen.queryByTestId("decision-items-dismiss-0")).not.toBeInTheDocument();
    expect(updateSpy).not.toHaveBeenCalled();
  });

  it("shows permission unknown state when decision write capability cannot be evaluated", async () => {
    const client = createApiClient({ mode: "mock" });
    vi.spyOn(client, "getBalanceAnalysisDates").mockResolvedValue({
      result_meta: testMeta,
      result: { report_dates: ["2026-03-31"] },
    });
    vi.spyOn(client, "getBalanceAnalysisCurrentUser").mockResolvedValue({
      user_id: "admin-unknown-scope",
      role: "admin",
      identity_source: "header",
      can_write_decision_status: null,
    });
    vi.spyOn(client, "getBalanceAnalysisDecisionItems").mockResolvedValue({
      result_meta: testMeta,
      result: decisionItemsPayload({
        rows: [
          decisionItemRow({
            decision_key: "row-1",
            title: "Unknown permission item",
            severity: "high",
          }),
        ],
      }),
    });

    renderPage(
      client,
      ["/decision-items?source=dashboard-home&report_date=2026-03-31&action_id=risk-review-queue"],
    );

    expect(await screen.findByTestId("decision-items-permission-unknown")).toHaveTextContent(
      "权限状态暂不可用",
    );
    expect(screen.queryByTestId("decision-items-confirm-0")).not.toBeInTheDocument();
    expect(screen.queryByTestId("decision-items-dismiss-0")).not.toBeInTheDocument();
  });

  it("shows permission unknown state when current-user lookup fails", async () => {
    const client = createApiClient({ mode: "mock" });
    vi.spyOn(client, "getBalanceAnalysisDates").mockResolvedValue({
      result_meta: testMeta,
      result: { report_dates: ["2026-03-31"] },
    });
    vi.spyOn(client, "getBalanceAnalysisCurrentUser").mockRejectedValue(new Error("scope store unavailable"));
    vi.spyOn(client, "getBalanceAnalysisDecisionItems").mockResolvedValue({
      result_meta: testMeta,
      result: decisionItemsPayload({
        rows: [
          decisionItemRow({
            decision_key: "row-1",
            title: "Unknown permission item",
            severity: "high",
          }),
        ],
      }),
    });

    renderPage(
      client,
      ["/decision-items?source=dashboard-home&report_date=2026-03-31&action_id=risk-review-queue"],
    );

    expect(await screen.findByTestId("decision-items-permission-unknown")).toHaveTextContent(
      "权限状态暂不可用",
    );
    expect(screen.queryByTestId("decision-items-confirm-0")).not.toBeInTheDocument();
    expect(screen.queryByTestId("decision-items-dismiss-0")).not.toBeInTheDocument();
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
    fireEvent.click(await screen.findByTestId("decision-items-confirm-0"));

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
