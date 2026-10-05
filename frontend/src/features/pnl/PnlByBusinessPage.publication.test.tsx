import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ApiClientProvider, createApiClient, type ApiClient } from "../../api/client";
import type {
  PnlByBusinessPrecomputeStatus,
} from "../../api/contracts";
import PnlByBusinessPage, {
  resolveApprovedPnlByBusinessInsightsEnvelope,
} from "./PnlByBusinessPage";

type PnlByBusinessInsightsEnvelope = Awaited<
  ReturnType<ApiClient["getPnlByBusinessInsights"]>
>;

vi.mock("./pnlByBusinessInsightsModel", () => ({
  buildPnlByBusinessInsightsLeadershipModel: ({ envelope }: {
    envelope?: PnlByBusinessInsightsEnvelope;
  }) => ({
    approvedAmount: envelope?.result.concentration.hhi_pct
      ? `${envelope.result.concentration.hhi_pct}%`
      : "masked",
  }),
}));

vi.mock("./PnlByBusinessInsightsLeadershipPanel", () => ({
  PnlByBusinessInsightsLeadershipPanel: ({ model }: {
    model: { approvedAmount: string };
  }) => (
    <div data-testid="pnl-by-business-insights-leadership-panel">
      {model.approvedAmount}
    </div>
  ),
}));

const REPORT_DATES = ["2026-06-30", "2026-05-31"];

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((nextResolve, nextReject) => {
    resolve = nextResolve;
    reject = nextReject;
  });
  return { promise, resolve, reject };
}

async function baseStatus(
  base: ApiClient,
  overrides: Partial<PnlByBusinessPrecomputeStatus>,
): Promise<PnlByBusinessPrecomputeStatus> {
  return {
    ...(await base.getPnlByBusinessPrecomputeStatus(2026, REPORT_DATES[0])),
    ...overrides,
  };
}

async function publishedPayload(
  base: ApiClient,
  reportDate: string,
  generation: string,
): Promise<PnlByBusinessInsightsEnvelope> {
  const envelope = await base.getPnlByBusinessInsights(2026, reportDate);
  return {
    ...envelope,
    result_meta: {
      ...envelope.result_meta,
      requested_report_date: reportDate,
      resolved_report_date: reportDate,
    },
    result: {
      ...envelope.result,
      generation,
      concentration: {
        ...envelope.result.concentration,
        hhi_pct: "98.76",
      },
    },
  };
}

function buildClient(
  status: ApiClient["getPnlByBusinessPrecomputeStatus"],
  insights: ApiClient["getPnlByBusinessInsights"],
): ApiClient {
  const base = createApiClient({ mode: "mock" });
  return {
    ...base,
    getFormalPnlDates: vi.fn(async (options) => {
      const envelope = await base.getFormalPnlDates(options);
      return {
        ...envelope,
        result: {
          ...envelope.result,
          report_dates: REPORT_DATES,
          formal_fi_report_dates: REPORT_DATES,
        },
      };
    }),
    getPnlByBusinessPrecomputeStatus: status,
    getPnlByBusinessInsights: insights,
    getPnlByBusinessYtd: vi.fn(async (year, asOfDate) => {
      const envelope = await base.getPnlByBusinessYtd(year, asOfDate);
      return {
        ...envelope,
        result: {
          ...envelope.result,
          total_pnl: "100.00",
          summary: {
            ...envelope.result.summary,
            total_pnl: "100.00",
            assets_count: 1,
          },
          items: [{
            row_key: "mock-business",
            business_key: "mock-business",
            business_type: "Mock 业务",
            sort_order: 1,
            interest_income: "100.00",
            fair_value_change: "0.00",
            capital_gain: "0.00",
            manual_adjustment: "0.00",
            total_pnl: "100.00",
            avg_balance: "1000.00",
            current_balance: "1000.00",
            annualized_yield_pct: "10.00",
            balance_yield_pct: "10.00",
            ftp_rate_pct: "1.75",
            ftp_cost: "17.50",
            ftp_net_pnl: "82.50",
            ftp_net_annualized_yield_pct: "8.25",
            proportion: "100.00",
            assets_count: 1,
          }],
        },
      };
    }),
  };
}

function renderPage(client: ApiClient) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const rendered = render(
    <QueryClientProvider client={queryClient}>
      <ApiClientProvider client={client}>
        <MemoryRouter>
          <PnlByBusinessPage />
        </MemoryRouter>
      </ApiClientProvider>
    </QueryClientProvider>,
  );
  return { ...rendered, queryClient };
}

async function openYtdView() {
  await waitFor(() => {
    expect(screen.getByLabelText("pnl-by-business-report-date")).toHaveValue(REPORT_DATES[0]);
  });
  fireEvent.change(screen.getByLabelText("pnl-by-business-view-mode"), {
    target: { value: "ytd" },
  });
}

describe("PnlByBusinessPage published insights boundary", () => {
  it("keeps the explicit legacy status shape on the unpinned request", async () => {
    const base = createApiClient({ mode: "mock" });
    const status = vi.fn(async () => baseStatus(base, { readiness: undefined, generation: null }));
    const insights = vi.fn((year, reportDate) => base.getPnlByBusinessInsights(year, reportDate));
    renderPage(buildClient(status, insights));

    await openYtdView();

    await waitFor(() => expect(insights).toHaveBeenCalledTimes(1));
    expect(insights).toHaveBeenCalledWith(
      2026,
      REPORT_DATES[0],
      { signal: expect.any(AbortSignal) },
    );
  });

  it("pins a ready published generation to the selected report date", async () => {
    const base = createApiClient({ mode: "mock" });
    const status = vi.fn(async () => baseStatus(base, {
      readiness: "ready",
      generation: "generation-a",
      worker_stalled: false,
    }));
    const insights = vi.fn(async (_year, reportDate) =>
      publishedPayload(base, reportDate, "generation-a"));
    renderPage(buildClient(status, insights));

    await openYtdView();

    await waitFor(() => expect(insights).toHaveBeenCalledTimes(1));
    expect(insights).toHaveBeenCalledWith(
      2026,
      REPORT_DATES[0],
      { signal: expect.any(AbortSignal), generation: "generation-a" },
    );
  });

  it.each([
    [{ readiness: "stale", generation: "generation-old" }, "not ready"],
    [{ readiness: "ready", generation: null }, "missing generation"],
  ] as const)("does not read an uncovered publication when it is %s", async (overrides, _label) => {
    const base = createApiClient({ mode: "mock" });
    const status = vi.fn(async () => baseStatus(base, {
      ...overrides,
      worker_stalled: false,
    }));
    const insights = vi.fn((year, reportDate) => base.getPnlByBusinessInsights(year, reportDate));
    renderPage(buildClient(status, insights));

    await openYtdView();

    await waitFor(() => expect(status).toHaveBeenCalled());
    expect(insights).not.toHaveBeenCalled();
  });

  it("masks retained insights when the current status refresh fails", async () => {
    const base = createApiClient({ mode: "mock" });
    let failStatus = false;
    const status = vi.fn(async () => {
      if (failStatus) {
        throw new Error("publication status unavailable");
      }
      return baseStatus(base, {
        readiness: "ready",
        generation: "generation-a",
        worker_stalled: false,
      });
    });
    const insights = vi.fn(async (_year, reportDate) =>
      publishedPayload(base, reportDate, "generation-a"));
    const { queryClient } = renderPage(buildClient(status, insights));
    await openYtdView();
    await waitFor(() => expect(insights).toHaveBeenCalledTimes(1));
    const publishedPanel = await screen.findByTestId("pnl-by-business-insights-leadership-panel");
    await waitFor(() => expect(publishedPanel).toHaveTextContent("98.76%"));

    failStatus = true;
    await act(async () => {
      await queryClient.refetchQueries({
        queryKey: ["pnl-by-business", "precompute-status", "mock", 2026, REPORT_DATES[0]],
      });
    });

    await waitFor(() => {
      expect(queryClient.getQueryState([
        "pnl-by-business",
        "precompute-status",
        "mock",
        2026,
        REPORT_DATES[0],
      ])?.status).toBe("error");
    });
    expect(screen.getByTestId("pnl-by-business-insights-leadership-panel")).toHaveTextContent(
      "masked",
    );
    expect(screen.getByTestId("pnl-by-business-insights-leadership-panel")).not.toHaveTextContent(
      "98.76%",
    );
    expect(insights).toHaveBeenCalledTimes(1);
    expect(resolveApprovedPnlByBusinessInsightsEnvelope({
      envelope: await publishedPayload(base, REPORT_DATES[0], "generation-a"),
      insightsQuerySucceeded: true,
      legacyReadAllowed: false,
      precomputeStatusQuerySucceeded: false,
      publishedGeneration: "generation-a",
      publishedReadAllowed: true,
      selectedReportDate: REPORT_DATES[0],
      usesReadinessProtocol: true,
    })).toBeUndefined();
  });

  it("does not reveal a late response from the prior date or generation", async () => {
    const base = createApiClient({ mode: "mock" });
    const oldResponse = deferred<PnlByBusinessInsightsEnvelope>();
    const nextResponse = deferred<PnlByBusinessInsightsEnvelope>();
    const status = vi.fn(async (_year, reportDate) => baseStatus(base, {
      readiness: "ready",
      generation: reportDate === REPORT_DATES[0] ? "generation-a" : "generation-b",
      worker_stalled: false,
    }));
    const insights = vi.fn((_year, reportDate) =>
      reportDate === REPORT_DATES[0] ? oldResponse.promise : nextResponse.promise);
    const { queryClient } = renderPage(buildClient(status, insights));
    await openYtdView();
    await waitFor(() => expect(insights).toHaveBeenCalledTimes(1));

    fireEvent.change(screen.getByLabelText("pnl-by-business-report-date"), {
      target: { value: REPORT_DATES[1] },
    });
    await waitFor(() => expect(insights).toHaveBeenCalledTimes(2));
    oldResponse.resolve(await publishedPayload(base, REPORT_DATES[0], "generation-a"));

    await waitFor(() => {
      expect(queryClient.getQueryState([
        "pnl-by-business",
        "insights",
        "mock",
        2026,
        REPORT_DATES[1],
        "generation-b",
      ])?.status).toBe("pending");
    });
    expect(screen.getByTestId("pnl-by-business-insights-leadership-panel")).toHaveTextContent(
      "masked",
    );
    nextResponse.resolve(await publishedPayload(base, REPORT_DATES[1], "generation-b"));
    await waitFor(() => {
      expect(queryClient.getQueryState([
        "pnl-by-business",
        "insights",
        "mock",
        2026,
        REPORT_DATES[1],
        "generation-b",
      ])?.status).toBe("success");
    });
    expect(screen.getByTestId("pnl-by-business-insights-leadership-panel")).toHaveTextContent(
      "98.76%",
    );
  });

  it("does not retry a failed pinned read without its generation", async () => {
    const base = createApiClient({ mode: "mock" });
    const status = vi.fn(async () => baseStatus(base, {
      readiness: "ready",
      generation: "generation-revoked",
      worker_stalled: false,
    }));
    const insights = vi.fn(async () => {
      throw new Error("409 published generation revoked");
    });
    const client = buildClient(status, insights);
    const ytdResponse = deferred<Awaited<ReturnType<ApiClient["getPnlByBusinessYtd"]>>>();
    const readYtd = client.getPnlByBusinessYtd;
    client.getPnlByBusinessYtd = vi.fn(() => ytdResponse.promise);
    const { queryClient } = renderPage(client);
    await openYtdView();

    await waitFor(() => expect(insights).toHaveBeenCalledTimes(1));
    expect(insights).toHaveBeenCalledWith(
      2026,
      REPORT_DATES[0],
      { signal: expect.any(AbortSignal), generation: "generation-revoked" },
    );
    await waitFor(() => {
      expect(queryClient.getQueryState([
        "pnl-by-business",
        "insights",
        "mock",
        2026,
        REPORT_DATES[0],
        "generation-revoked",
      ])?.status).toBe("error");
    });
    expect(queryClient.getQueryState([
      "pnl-by-business", "ytd", "mock", 2026, REPORT_DATES[0],
    ])?.status).toBe("pending");
    expect(screen.queryByTestId("pnl-by-business-insights-leadership-panel")).not.toBeInTheDocument();
    // Insights can fail before the YTD payload allows the panel to mount.
    ytdResponse.resolve(await readYtd(2026, REPORT_DATES[0]));
    const panel = await screen.findByTestId("pnl-by-business-insights-leadership-panel");
    expect(panel).toHaveTextContent(
      "masked",
    );
    expect(insights).toHaveBeenCalledTimes(1);
  });

  it("keeps a deferred rebuild receipt and status reread on the submitted report date", async () => {
    const base = createApiClient({ mode: "mock" });
    const pendingRebuild = deferred<PnlByBusinessPrecomputeStatus>();
    let nextDateReads = 0;
    const status = vi.fn(async (_year: number, reportDate?: string) => {
      if (reportDate === REPORT_DATES[1] && ++nextDateReads > 1) {
        return new Promise<PnlByBusinessPrecomputeStatus>(() => {});
      }
      return baseStatus(base, {
        readiness: undefined,
        report_date: reportDate,
        status: "completed",
      });
    });
    const insights = vi.fn((year: number, reportDate: string) =>
      base.getPnlByBusinessInsights(year, reportDate));
    const client = {
      ...buildClient(status, insights),
      rebuildPnlByBusinessPrecompute: vi.fn(() => pendingRebuild.promise),
    };
    const { queryClient } = renderPage(client);
    const submittedKey = [
      "pnl-by-business",
      "precompute-status",
      "mock",
      2026,
      REPORT_DATES[0],
    ];
    const nextDateKey = [
      "pnl-by-business",
      "precompute-status",
      "mock",
      2026,
      REPORT_DATES[1],
    ];

    await waitFor(() => {
      expect(screen.getByLabelText("pnl-by-business-report-date")).toHaveValue(REPORT_DATES[0]);
      expect(status).toHaveBeenCalledWith(2026, REPORT_DATES[0]);
    });
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "重新生成预计算" })).toBeEnabled();
    });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "重新生成预计算" }));
    });
    await waitFor(() => {
      expect(client.rebuildPnlByBusinessPrecompute).toHaveBeenCalledWith(2026, REPORT_DATES[0]);
    });

    fireEvent.change(screen.getByLabelText("pnl-by-business-report-date"), {
      target: { value: REPORT_DATES[1] },
    });
    await waitFor(() => {
      expect(queryClient.getQueryData(nextDateKey)).toMatchObject({
        report_date: REPORT_DATES[1],
        status: "completed",
      });
    });

    const queuedStatus = await baseStatus(base, {
      readiness: undefined,
      status: "queued",
      run_id: "review-run-june",
      report_date: REPORT_DATES[0],
    });
    await act(async () => {
      pendingRebuild.resolve(queuedStatus);
    });

    await waitFor(() => {
      expect(queryClient.getQueryData(submittedKey)).toMatchObject({
        report_date: REPORT_DATES[0],
      });
      expect(status.mock.calls.filter(([, reportDate]) => reportDate === REPORT_DATES[0])).toHaveLength(2);
    });
    expect(status.mock.calls.filter(([, reportDate]) => reportDate === REPORT_DATES[1])).toHaveLength(1);
    expect(queryClient.getQueryData(nextDateKey)).toMatchObject({
      report_date: REPORT_DATES[1],
      status: "completed",
    });
  });

  it("rejects date and generation mismatches before any consumer receives the envelope", async () => {
    const base = createApiClient({ mode: "mock" });
    const envelope = await publishedPayload(base, REPORT_DATES[0], "generation-a");

    expect(resolveApprovedPnlByBusinessInsightsEnvelope({
      envelope,
      insightsQuerySucceeded: true,
      legacyReadAllowed: false,
      precomputeStatusQuerySucceeded: true,
      publishedGeneration: "generation-b",
      publishedReadAllowed: true,
      selectedReportDate: REPORT_DATES[0],
      usesReadinessProtocol: true,
    })).toBeUndefined();
    expect(resolveApprovedPnlByBusinessInsightsEnvelope({
      envelope,
      insightsQuerySucceeded: true,
      legacyReadAllowed: false,
      precomputeStatusQuerySucceeded: true,
      publishedGeneration: "generation-a",
      publishedReadAllowed: true,
      selectedReportDate: REPORT_DATES[1],
      usesReadinessProtocol: true,
    })).toBeUndefined();
  });
});
