import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { CalendarList } from "../components/CalendarList";

describe("CalendarList", () => {
  it("renders calendar event details and source links", () => {
    const { container } = render(
      <CalendarList
        items={[
          {
            date: "2026-06-10",
            event: "Policy bond auction",
            issuerLabel: "CDB",
            amount: "120 bn",
            level: "high",
            note: "Watch liquidity impact",
            sourceUrl: "https://example.test/calendar",
            sourceLabel: "Exchange notice",
          },
        ]}
      />,
    );

    expect(screen.getByText("2026-06-10")).toBeInTheDocument();
    expect(screen.getByText("Policy bond auction")).toBeInTheDocument();
    expect(screen.getByText("CDB")).toBeInTheDocument();
    expect(screen.getByText("120 bn")).toBeInTheDocument();
    expect(screen.getByText("Watch liquidity impact")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Exchange notice/ })).toHaveAttribute(
      "href",
      "https://example.test/calendar",
    );
    expect(container.querySelector(".calendar-list")).toBeInTheDocument();
    expect(container.querySelector(".calendar-list__issuer")).toHaveTextContent("CDB");
    expect(container.querySelector("[style]")).not.toBeInTheDocument();
  });
});
