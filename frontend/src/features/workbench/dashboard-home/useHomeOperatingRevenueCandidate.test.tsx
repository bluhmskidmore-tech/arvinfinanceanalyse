import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { createApiClient } from "../../../api/client";
import type { ApiClient } from "../../../api/clientContext";
import type { LedgerPnlCandidateFinancialIndicatorsEnvelope } from "../../../api/contracts";
import {
  toCandidateReportMonth,
  useHomeOperatingRevenueCandidate,
} from "./useHomeOperatingRevenueCandidate";

const METRIC_ID = "income.operating.mother_bank";

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

function createSettledWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return {
    queryClient,
    wrapper: ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    ),
  };
}

async function baseEnvelope(): Promise<LedgerPnlCandidateFinancialIndicatorsEnvelope> {
  return createApiClient({
    mode: "mock",
  }).getLedgerPnlCandidateFinancialIndicators("202606");
}

function clientReturning(
  envelope: LedgerPnlCandidateFinancialIndicatorsEnvelope,
  overrides: Partial<ApiClient> = {},
): ApiClient {
  return {
    ...createApiClient({ mode: "mock" }),
    mode: "real" as const,
    getLedgerPnlCandidateFinancialIndicators: vi.fn(async () => envelope),
    ...overrides,
  };
}

function withMetric(
  envelope: LedgerPnlCandidateFinancialIndicatorsEnvelope,
  metric: Partial<
    LedgerPnlCandidateFinancialIndicatorsEnvelope["result"]["metrics"][number]
  >,
): LedgerPnlCandidateFinancialIndicatorsEnvelope {
  return {
    ...envelope,
    result: {
      ...envelope.result,
      calculation_status: "warning",
      report_month: "202607",
      metrics: [
        {
          metric_id: METRIC_ID,
          name: "母公司营业收入（可自动口径）",
          category: "营业收入",
          basis: "cumulative",
          unit: "亿元",
          value: "90.5633166815",
          status: "warning",
          reasons: [],
          lineage: [],
          ...metric,
        },
      ],
    },
  };
}

describe("toCandidateReportMonth", () => {
  it("maps a snapshot report date onto the candidate report month", () => {
    expect(toCandidateReportMonth("2026-07-31")).toBe("202607");
    expect(toCandidateReportMonth(" 2026-01-31 ")).toBe("202601");
  });

  it("returns null for anything that is not a full date", () => {
    for (const value of ["", "2026-07", "202607", null, undefined]) {
      expect(toCandidateReportMonth(value)).toBeNull();
    }
  });
});

describe("useHomeOperatingRevenueCandidate", () => {
  it("returns the candidate value at display precision with its report month", async () => {
    const client = clientReturning(withMetric(await baseEnvelope(), {}));

    const { result } = renderHook(
      () =>
        useHomeOperatingRevenueCandidate(client, "2026-07-31", {
          enabled: true,
        }),
      { wrapper },
    );

    await waitFor(() =>
      expect(result.current).toEqual({
        display: "90.56 亿",
        status: "warning",
        reportMonth: "202607",
      }),
    );
    expect(
      client.getLedgerPnlCandidateFinancialIndicators,
    ).toHaveBeenCalledWith("202607", {
      includeLineage: false,
      metricId: METRIC_ID,
    });
  });

  it("withholds the value when the backend blocks the calculation", async () => {
    const envelope = withMetric(await baseEnvelope(), {});
    const client = clientReturning({
      ...envelope,
      result: { ...envelope.result, calculation_status: "error" },
    });

    const { result } = renderHook(
      () =>
        useHomeOperatingRevenueCandidate(client, "2026-07-31", {
          enabled: true,
        }),
      { wrapper },
    );

    await waitFor(() =>
      expect(
        client.getLedgerPnlCandidateFinancialIndicators,
      ).toHaveBeenCalled(),
    );
    expect(result.current).toBeNull();
  });

  it("withholds the value when the metric itself errored or has no number", async () => {
    for (const metric of [{ status: "error" as const }, { value: null }, { value: "" }, { value: "   " }]) {
      const client = clientReturning(withMetric(await baseEnvelope(), metric));
      const settled = createSettledWrapper();
      const { result } = renderHook(
        () =>
          useHomeOperatingRevenueCandidate(client, "2026-07-31", {
            enabled: true,
          }),
        { wrapper: settled.wrapper },
      );

      await waitFor(() =>
        expect(settled.queryClient.getQueryCache().getAll()[0]?.state.status).toBe("success"),
      );
      expect(result.current).toBeNull();
    }
  });

  it("preserves a supplied zero after the query has completed", async () => {
    const client = clientReturning(withMetric(await baseEnvelope(), { value: "0" }));
    const { result } = renderHook(
      () => useHomeOperatingRevenueCandidate(client, "2026-07-31", { enabled: true }),
      { wrapper },
    );
    await waitFor(() => expect(result.current?.display).toBe("0.00 亿"));
  });

  it("withholds a completed response for another report month", async () => {
    const envelope = withMetric(await baseEnvelope(), {});
    const client = clientReturning({
      ...envelope,
      result: { ...envelope.result, report_month: "202606" },
    });
    const settled = createSettledWrapper();
    const { result } = renderHook(
      () => useHomeOperatingRevenueCandidate(client, "2026-07-31", { enabled: true }),
      { wrapper: settled.wrapper },
    );
    await waitFor(() =>
      expect(settled.queryClient.getQueryCache().getAll()[0]?.state.status).toBe("success"),
    );
    expect(result.current).toBeNull();
  });

  it("keeps a late previous-month response out of the current month and clears disabled values", async () => {
    const envelope = withMetric(await baseEnvelope(), {});
    let resolveJuly!: (value: LedgerPnlCandidateFinancialIndicatorsEnvelope) => void;
    let resolveAugust!: (value: LedgerPnlCandidateFinancialIndicatorsEnvelope) => void;
    const july = new Promise<LedgerPnlCandidateFinancialIndicatorsEnvelope>((resolve) => { resolveJuly = resolve; });
    const august = new Promise<LedgerPnlCandidateFinancialIndicatorsEnvelope>((resolve) => { resolveAugust = resolve; });
    const client = clientReturning(envelope, {
      getLedgerPnlCandidateFinancialIndicators: vi.fn((month) => month === "202607" ? july : august),
    });
    const settled = createSettledWrapper();
    const { result, rerender } = renderHook(
      ({ reportDate, enabled }) => useHomeOperatingRevenueCandidate(client, reportDate, { enabled }),
      { wrapper: settled.wrapper, initialProps: { reportDate: "2026-07-31", enabled: true } },
    );
    rerender({ reportDate: "2026-08-31", enabled: true });
    expect(result.current).toBeNull();
    await act(async () => resolveAugust({
      ...envelope,
      result: { ...envelope.result, report_month: "202608", metrics: [{ ...envelope.result.metrics[0]!, value: "12" }] },
    }));
    await waitFor(() => expect(result.current?.display).toBe("12.00 亿"));
    await act(async () => resolveJuly(envelope));
    expect(result.current?.reportMonth).toBe("202608");
    expect(result.current?.display).toBe("12.00 亿");
    rerender({ reportDate: "2026-08-31", enabled: false });
    expect(result.current).toBeNull();
  });

  it("withholds retained candidate data after a same-month refetch fails", async () => {
    const envelope = withMetric(await baseEnvelope(), {});
    const getLedgerPnlCandidateFinancialIndicators = vi.fn()
      .mockResolvedValueOnce(envelope)
      .mockRejectedValueOnce(new Error("candidate refresh unavailable"))
      .mockResolvedValueOnce(withMetric(envelope, { value: "0" }));
    const client = clientReturning(envelope, { getLedgerPnlCandidateFinancialIndicators });
    const settled = createSettledWrapper();
    const { result } = renderHook(
      () => useHomeOperatingRevenueCandidate(client, "2026-07-31", { enabled: true }),
      { wrapper: settled.wrapper },
    );
    await waitFor(() => expect(result.current?.display).toBe("90.56 亿"));

    await act(async () => {
      await settled.queryClient.refetchQueries({ queryKey: ["ledger-pnl", "candidate-financial-indicators"] });
    });
    await waitFor(() =>
      expect(settled.queryClient.getQueryCache().getAll()[0]?.state.status).toBe("error"),
    );
    expect(getLedgerPnlCandidateFinancialIndicators).toHaveBeenCalledTimes(2);
    expect(settled.queryClient.getQueryCache().getAll()[0]?.state.data).toEqual(envelope);
    expect(result.current).toBeNull();

    await act(async () => {
      await settled.queryClient.refetchQueries({ queryKey: ["ledger-pnl", "candidate-financial-indicators"] });
    });
    await waitFor(() => expect(result.current?.display).toBe("0.00 亿"));
    expect(getLedgerPnlCandidateFinancialIndicators).toHaveBeenCalledTimes(3);
  });

  it("never requests the candidate engine in mock mode or while disabled", async () => {
    const envelope = withMetric(await baseEnvelope(), {});
    const mockModeClient = clientReturning(envelope, { mode: "mock" as const });
    const disabledClient = clientReturning(envelope);

    renderHook(
      () =>
        useHomeOperatingRevenueCandidate(mockModeClient, "2026-07-31", {
          enabled: true,
        }),
      { wrapper },
    );
    renderHook(
      () =>
        useHomeOperatingRevenueCandidate(disabledClient, "2026-07-31", {
          enabled: false,
        }),
      { wrapper },
    );

    await Promise.resolve();
    expect(
      mockModeClient.getLedgerPnlCandidateFinancialIndicators,
    ).not.toHaveBeenCalled();
    expect(
      disabledClient.getLedgerPnlCandidateFinancialIndicators,
    ).not.toHaveBeenCalled();
  });
});
