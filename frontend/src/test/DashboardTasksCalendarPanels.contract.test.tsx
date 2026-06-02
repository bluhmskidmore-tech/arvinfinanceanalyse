import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DashboardTasksCalendarPanels } from "../features/workbench/dashboard/DashboardOverviewSections";

describe("DashboardTasksCalendarPanels supply/auction contract", () => {
  it("maps calendar badge severity from payload severity instead of row order", () => {
    render(
      <DashboardTasksCalendarPanels
        calendarItems={[
          {
            id: "calendar-low-first",
            title: "净融资观察",
            time: "2026-03-31",
            kind: "supply",
            severity: "low",
          },
          {
            id: "calendar-high-second",
            title: "政策债招标",
            time: "2026-04-01",
            kind: "macro",
            severity: "high",
          },
        ]}
      />,
    );

    const panel = screen.getByTestId("dashboard-tasks-calendar");
    const lowRow = within(panel).getByText("净融资观察").closest("article");
    const highRow = within(panel).getByText("政策债招标").closest("article");

    expect(lowRow).toHaveTextContent("低");
    expect(lowRow).not.toHaveTextContent("高");
    expect(highRow).toHaveTextContent("高");
    expect(highRow).not.toHaveTextContent("低");
  });
});
