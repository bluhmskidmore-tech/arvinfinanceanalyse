import { act, cleanup, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { createApiClient, type ApiClient } from "../../../api/client";
import { renderWorkbenchApp } from "../../../test/renderWorkbenchApp";
import RiskOverviewPage from "./RiskOverviewPage";

const REPORT_DATE = "2026-06-30";
const NEXT_REPORT_DATE = "2026-07-31";
const BOND_DATES = [
  NEXT_REPORT_DATE, REPORT_DATE, "2026-05-31", "2026-04-30", "2026-03-31",
  "2026-02-28", "2026-01-31", "2025-07-31", "2025-06-30",
];

function deferred() {
  let resolve!: () => void;
  let reject!: (error: Error) => void;
  const promise = new Promise<void>((accept, fail) => {
    resolve = accept;
    reject = fail;
  });
  return { promise, resolve, reject };
}

function currentGates() {
  return { tensor: deferred(), cashflow: deferred(), oci: deferred(), tpl: deferred() };
}

async function createControlledClient() {
  const base = createApiClient({ mode: "mock" });
  const [riskDates, bondDates] = await Promise.all([
    base.getRiskTensorDates(), base.getBondAnalyticsDates(),
  ]);
  const state = {
    reportDate: REPORT_DATE,
    bondDates: BOND_DATES,
    current: currentGates(),
    dates: undefined as ReturnType<typeof deferred> | undefined,
    auxiliary: undefined as ReturnType<typeof deferred> | undefined,
  };
  const client: ApiClient = {
    ...base,
    getRiskTensorDates: vi.fn(async () => {
      await state.dates?.promise;
      return { ...riskDates, result: { ...riskDates.result, report_dates: [state.reportDate] } };
    }),
    getBondAnalyticsDates: vi.fn(async () => ({
      ...bondDates, result: { ...bondDates.result, report_dates: state.bondDates },
    })),
    getRiskTensor: vi.fn(async (reportDate: string) => {
      await state.current.tensor.promise;
      return base.getRiskTensor(reportDate);
    }),
    getCashflowProjection: vi.fn(async (reportDate: string) => {
      await state.current.cashflow.promise;
      return base.getCashflowProjection(reportDate);
    }),
    getBondAnalyticsDv01Risk: vi.fn(async (
      reportDate: string,
      options?: Parameters<ApiClient["getBondAnalyticsDv01Risk"]>[1],
    ) => {
      if (reportDate === state.reportDate) {
        await (options?.accountingClass === "OCI" ? state.current.oci : state.current.tpl).promise;
      } else {
        await state.auxiliary?.promise;
      }
      const envelope = await base.getBondAnalyticsDv01Risk(reportDate, options);
      return { ...envelope, result: { ...envelope.result, position_count: 1 } };
    }),
    getRiskTensorHistory: vi.fn(async (...args: Parameters<ApiClient["getRiskTensorHistory"]>) => {
      await state.auxiliary?.promise;
      return base.getRiskTensorHistory(...args);
    }),
    getBondAnalyticsYieldCurveTermStructure: vi.fn(async (
      ...args: Parameters<ApiClient["getBondAnalyticsYieldCurveTermStructure"]>
    ) => {
      await state.auxiliary?.promise;
      return base.getBondAnalyticsYieldCurveTermStructure(...args);
    }),
  };
  return { client, state };
}

function renderRisk(client: ApiClient) {
  return renderWorkbenchApp(["/risk-overview"], {
    client,
    routes: [{ path: "/risk-overview", element: <RiskOverviewPage /> }],
  });
}

async function expectCurrentReads(client: ApiClient, reportDate = REPORT_DATE) {
  await waitFor(() => {
    expect(client.getRiskTensor).toHaveBeenCalledWith(reportDate);
    expect(client.getCashflowProjection).toHaveBeenCalledWith(reportDate);
    expect(client.getBondAnalyticsDv01Risk).toHaveBeenCalledWith(reportDate, expect.objectContaining({ accountingClass: "OCI" }));
    expect(client.getBondAnalyticsDv01Risk).toHaveBeenCalledWith(reportDate, expect.objectContaining({ accountingClass: "TPL" }));
  });
}

function expectAuxiliaryWaiting(client: ApiClient) {
  expect(client.getRiskTensorHistory).not.toHaveBeenCalled();
  expect(client.getBondAnalyticsYieldCurveTermStructure).not.toHaveBeenCalled();
  expect(client.getBondAnalyticsDv01Risk).toHaveBeenCalledTimes(2);
  expect(screen.getByTestId("risk-overview-bond-comparison-status")).toHaveAttribute("data-state", "loading");
  expect(screen.getByTestId("risk-overview-curve-panel")).toHaveTextContent("读取中");
}

async function settleCurrent(gates: ReturnType<typeof currentGates>, failTpl = false) {
  await act(async () => {
    gates.tensor.resolve();
    gates.cashflow.resolve();
    gates.oci.resolve();
    if (failTpl) gates.tpl.reject(new Error("synthetic current TPL failure"));
    else gates.tpl.resolve();
  });
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("risk overview current request priority", () => {
  it.each([false, true])("waits for all current reads before auxiliary reads when TPL failure is %s", async (failTpl) => {
    const { client, state } = await createControlledClient();
    state.auxiliary = deferred();
    renderRisk(client);
    await expectCurrentReads(client);
    expectAuxiliaryWaiting(client);

    await act(async () => {
      state.current.tensor.resolve();
      state.current.cashflow.resolve();
      state.current.oci.resolve();
    });
    await screen.findByTestId("risk-overview-sparkcap");
    expectAuxiliaryWaiting(client);
    expect(screen.getByTestId("risk-overview-sparkcap")).toHaveTextContent("读取中");
    await waitFor(() => {
      expect(screen.getByTestId("risk-overview-bond-oci-total-dv01-mom"))
        .toHaveAttribute("data-state", "loading");
    });
    expect(screen.getByTestId("risk-overview-bond-oci-total-dv01-mom")).toHaveTextContent("读取中");
    expect(screen.getByTestId("risk-overview-bond-oci")).not.toHaveTextContent("基期不可用");

    await settleCurrent(state.current, failTpl);
    await waitFor(() => {
      expect(client.getRiskTensorHistory).toHaveBeenCalledTimes(1);
      expect(client.getBondAnalyticsYieldCurveTermStructure).toHaveBeenCalledTimes(1);
      expect(client.getBondAnalyticsDv01Risk).toHaveBeenCalledTimes(14);
    });
    expect(screen.getByTestId("risk-overview-bond-comparison-status")).toHaveAttribute("data-state", "loading");
    await act(async () => state.auxiliary?.resolve());
    await waitFor(() => expect(screen.getByRole("button", { name: "刷新" })).toBeEnabled());
  });

  it.each([REPORT_DATE, NEXT_REPORT_DATE])("rechecks dates and prioritizes current reads during refresh for %s", async (nextDate) => {
    const { client, state } = await createControlledClient();
    renderRisk(client);
    await expectCurrentReads(client);
    await settleCurrent(state.current);
    await waitFor(() => expect(screen.getByRole("button", { name: "刷新" })).toBeEnabled());
    const reads = [client.getRiskTensor, client.getCashflowProjection, client.getBondAnalyticsDv01Risk,
      client.getRiskTensorHistory, client.getBondAnalyticsYieldCurveTermStructure];
    reads.forEach((read) => vi.mocked(read).mockClear());
    state.current = currentGates();
    state.dates = deferred();
    state.reportDate = nextDate;

    await userEvent.click(screen.getByRole("button", { name: "刷新" }));
    reads.forEach((read) => expect(read).not.toHaveBeenCalled());
    await act(async () => state.dates?.resolve());
    await expectCurrentReads(client, nextDate);
    expect(client.getRiskTensorHistory).not.toHaveBeenCalled();
    expect(client.getBondAnalyticsYieldCurveTermStructure).not.toHaveBeenCalled();
    expect(client.getBondAnalyticsDv01Risk).toHaveBeenCalledTimes(2);
    expect(vi.mocked(client.getRiskTensor).mock.calls.every(([date]) => date === nextDate)).toBe(true);
    expect(vi.mocked(client.getCashflowProjection).mock.calls.every(([date]) => date === nextDate)).toBe(true);

    await settleCurrent(state.current);
    await waitFor(() => {
      expect(client.getRiskTensorHistory).toHaveBeenCalledTimes(1);
      expect(client.getRiskTensorHistory).toHaveBeenCalledWith(nextDate, 24);
      expect(client.getBondAnalyticsYieldCurveTermStructure).toHaveBeenCalledTimes(1);
      expect(screen.getByRole("button", { name: "刷新" })).toBeEnabled();
    });
    if (nextDate === REPORT_DATE) expect(client.getBondAnalyticsDv01Risk).toHaveBeenCalledTimes(14);
    expect(within(screen.getByTestId("risk-overview-bond-evidence")).getByTestId("risk-overview-bond-comparison-status"))
      .not.toHaveAttribute("data-state", "loading");
  });

  it("keeps newly available historical dates behind current reads during refresh", async () => {
    const { client, state } = await createControlledClient();
    state.bondDates = BOND_DATES.filter((date) => date !== "2026-01-31");
    renderRisk(client);
    await expectCurrentReads(client);
    await settleCurrent(state.current);
    await waitFor(() => expect(screen.getByRole("button", { name: "刷新" })).toBeEnabled());
    vi.mocked(client.getBondAnalyticsDv01Risk).mockClear();
    state.current = currentGates();
    state.bondDates = BOND_DATES;

    await userEvent.click(screen.getByRole("button", { name: "刷新" }));
    await waitFor(() => expect(client.getBondAnalyticsDv01Risk).toHaveBeenCalledTimes(2));
    expect(vi.mocked(client.getBondAnalyticsDv01Risk).mock.calls.map(([date]) => date))
      .toEqual([REPORT_DATE, REPORT_DATE]);
    await settleCurrent(state.current);
    await waitFor(() => {
      expect(client.getBondAnalyticsDv01Risk).toHaveBeenCalledWith("2026-01-31", expect.objectContaining({ accountingClass: "OCI" }));
      expect(client.getBondAnalyticsDv01Risk).toHaveBeenCalledWith("2026-01-31", expect.objectContaining({ accountingClass: "TPL" }));
      expect(screen.getByRole("button", { name: "刷新" })).toBeEnabled();
    });
  });
});
