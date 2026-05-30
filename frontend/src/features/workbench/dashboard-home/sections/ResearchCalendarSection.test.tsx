import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ResearchCalendarSection } from "./ResearchCalendarSection";

describe("ResearchCalendarSection", () => {
  it("renders empty-state message", () => {
    render(
      <ResearchCalendarSection
        calendar={{
          items: [],
          status: "empty",
          windowLabel: "2026-04-23 至 2026-05-14",
          message: "当前窗口暂无供给/招标事件。",
        }}
      />,
    );

    expect(screen.getByTestId("dashboard-home-research-calendar")).toBeInTheDocument();
    expect(screen.getByTestId("dashboard-home-research-calendar-message")).toHaveTextContent(
      "当前窗口暂无供给/招标事件。",
    );
  });
});
