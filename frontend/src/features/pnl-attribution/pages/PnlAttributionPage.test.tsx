import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, useNavigate } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import PnlAttributionPage from "./PnlAttributionPage";

vi.mock("../components/PnlAttributionView", () => ({
  PnlAttributionView: ({
    reportDate,
    homeCampisiWindow,
    homeCampisiError,
  }: {
    reportDate?: string;
    homeCampisiWindow?: { startDate: string; endDate: string };
    homeCampisiError?: string;
  }) => (
    <div data-testid="pnl-attribution-view">
      {reportDate ?? "no report date"} | {homeCampisiWindow?.startDate ?? "no start"} | {homeCampisiWindow?.endDate ?? "no end"} | {homeCampisiError ?? "no error"}
    </div>
  ),
}));

function renderAt(url: string) {
  return render(
    <MemoryRouter initialEntries={[url]}>
      <PnlAttributionPage />
    </MemoryRouter>,
  );
}

describe("PnlAttributionPage", () => {
  it("honors report_date from the URL", () => {
    renderAt("/pnl-attribution?report_date=2026-04-30");
    expect(screen.getByTestId("pnl-attribution-view")).toHaveTextContent("2026-04-30 | no start | no end | no error");
  });

  it("passes only a valid home Campisi window through to the view", () => {
    renderAt("/pnl-attribution?source=dashboard-home&report_date=2026-08-31&campisi_start_date=2026-08-01&campisi_end_date=2026-08-31");
    expect(screen.getByTestId("pnl-attribution-view")).toHaveTextContent("2026-08-31 | 2026-08-01 | 2026-08-31 | no error");
  });

  it.each([
    "campisi_start_date=2026-08-32&campisi_end_date=2026-08-31",
    "campisi_start_date=2026-09-01&campisi_end_date=2026-08-31",
    "campisi_start_date=2026-08-01&campisi_end_date=2026-08-30",
  ])("does not pass an invalid home window: %s", (windowQuery) => {
    renderAt(`/pnl-attribution?source=dashboard-home&report_date=2026-08-31&${windowQuery}`);
    expect(screen.getByTestId("pnl-attribution-view")).toHaveTextContent("2026-08-31 | no start | no end | 首页 Campisi 链接日期无效");
  });

  it("keeps ordinary links on the default path even if they contain Campisi dates", () => {
    renderAt("/pnl-attribution?report_date=2026-08-31&campisi_start_date=2026-08-01&campisi_end_date=2026-08-31");
    expect(screen.getByTestId("pnl-attribution-view")).toHaveTextContent("2026-08-31 | no start | no end | no error");
  });

  it("rejects a home link with a missing interval boundary", () => {
    renderAt("/pnl-attribution?source=dashboard-home&report_date=2026-08-31&campisi_end_date=2026-08-31");
    expect(screen.getByTestId("pnl-attribution-view")).toHaveTextContent("2026-08-31 | no start | no end | 首页 Campisi 链接日期无效");
  });

  it("drops the old home window when the report date changes in the same route", () => {
    function NavigationHarness() {
      const navigate = useNavigate();
      return (
        <>
          <button type="button" onClick={() => navigate("/pnl-attribution?source=dashboard-home&report_date=2026-09-30&campisi_start_date=2026-08-01&campisi_end_date=2026-08-31")}>Switch report date</button>
          <button type="button" onClick={() => navigate("/pnl-attribution?report_date=2026-09-30")}>Default entry</button>
          <PnlAttributionPage />
        </>
      );
    }
    render(
      <MemoryRouter initialEntries={["/pnl-attribution?source=dashboard-home&report_date=2026-08-31&campisi_start_date=2026-08-01&campisi_end_date=2026-08-31"]}>
        <NavigationHarness />
      </MemoryRouter>,
    );
    expect(screen.getByTestId("pnl-attribution-view")).toHaveTextContent("2026-08-31 | 2026-08-01 | 2026-08-31 | no error");
    fireEvent.click(screen.getByRole("button", { name: "Switch report date" }));
    expect(screen.getByTestId("pnl-attribution-view")).toHaveTextContent("2026-09-30 | no start | no end | 首页 Campisi 链接日期无效");
    fireEvent.click(screen.getByRole("button", { name: "Default entry" }));
    expect(screen.getByTestId("pnl-attribution-view")).toHaveTextContent("2026-09-30 | no start | no end | no error");
  });
});
