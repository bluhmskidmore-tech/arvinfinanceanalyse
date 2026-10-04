import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { createApiClient } from "../../../api/client";
import { renderWorkbenchApp } from "../../../test/renderWorkbenchApp";
import BalanceMovementAnalysisPage from "./BalanceMovementAnalysisPage";

vi.mock("../../../lib/echarts", () => ({
  default: () => <div data-testid="balance-movement-echarts-stub" />,
}));

describe("balance movement supplementary content", () => {
  it("constructs evidence on first expansion and retains it across later disclosure toggles", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const dates = await baseClient.getBalanceMovementDates();
    const detail = await baseClient.getBalanceMovementAnalysis({ reportDate: dates.result.report_dates[0] });
    const calibration = detail.result.zqtz_calibration_analysis!;
    const items = calibration.items;
    const constructCalibrationRows = vi.fn(() => items);
    Object.defineProperty(calibration, "items", { get: constructCalibrationRows });
    const readDetail = vi.fn(async () => detail);
    renderWorkbenchApp(["/balance-movement-analysis"], {
      client: { ...baseClient, getBalanceMovementAnalysis: readDetail },
      routes: [{ path: "/balance-movement-analysis", element: <BalanceMovementAnalysisPage /> }],
    });

    await screen.findByTestId("balance-movement-analysis-summary");
    const dataStates = screen.getByTestId("balance-movement-analysis-data-states");
    const disclosure = dataStates.querySelector<HTMLDetailsElement>("details.balance-movement-data-states__pass")!;
    const evidenceIds = [
      "balance-movement-analysis-controls",
      "balance-movement-analysis-governance",
      "balance-movement-analysis-supplementary-business-matrix",
      "balance-movement-analysis-structure-share-table",
      "balance-movement-analysis-zqtz-calibration",
      "balance-movement-analysis-anomaly-diagnostics",
    ];
    expect(disclosure.open).toBe(false);
    expect(constructCalibrationRows).not.toHaveBeenCalled();
    for (const testId of evidenceIds) expect(within(disclosure).queryByTestId(testId)).not.toBeInTheDocument();
    const detailReads = readDetail.mock.calls.length;

    const toggle = within(disclosure).getByText("契约通过条件");
    await userEvent.click(toggle);
    await waitFor(() => {
      for (const testId of evidenceIds) expect(within(disclosure).getByTestId(testId)).toBeInTheDocument();
    });
    expect(constructCalibrationRows).toHaveBeenCalled();
    const mountedEvidence = evidenceIds.map((testId) => within(disclosure).getByTestId(testId));

    await userEvent.click(toggle);
    expect(disclosure.open).toBe(false);
    await userEvent.click(toggle);
    for (let index = 0; index < evidenceIds.length; index += 1) {
      expect(within(disclosure).getByTestId(evidenceIds[index])).toBe(mountedEvidence[index]);
    }
    expect(readDetail).toHaveBeenCalledTimes(detailReads);
  });
});
