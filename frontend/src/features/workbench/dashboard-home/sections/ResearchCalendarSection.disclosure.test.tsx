import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { buildHomeMacroBriefingModel } from "../adapters/buildHomeMacroBriefingModel";
import { ResearchCalendarSection } from "./ResearchCalendarSection";

describe("ResearchCalendarSection history disclosure", () => {
  it("keeps every history row in a collapsed disclosure by default", () => {
    const macroBriefing = buildHomeMacroBriefingModel({
      todayIsoDate: "2026-07-16",
      newsEvents: [],
      fallbackNewsEvents: [],
      newsLoading: false,
      newsError: false,
      supplyCalendar: {
        items: [],
        status: "empty",
        windowLabel: "2026-07-16 to 2026-08-30",
        message: null,
      },
    });

    render(<ResearchCalendarSection macroBriefing={macroBriefing} />);

    const disclosure = screen.getByTestId("dashboard-home-release-history-disclosure");
    expect(disclosure).not.toHaveAttribute("open");
    const trigger = within(disclosure).getByRole("button");
    expect(within(trigger).getByText(`共 ${macroBriefing.releaseHistoryItems.length} 项`)).toBeInTheDocument();
    expect(within(disclosure).getByText("ISM Manufacturing PMI")).toBeInTheDocument();
    expect(screen.getAllByTestId("dashboard-home-release-history-row")).toHaveLength(
      macroBriefing.releaseHistoryItems.length,
    );

    fireEvent.click(trigger);
    expect(disclosure).toHaveAttribute("open");
  });

  it("keeps history status available when no release rows exist", () => {
    const macroBriefing = buildHomeMacroBriefingModel({
      todayIsoDate: "2026-07-16",
      newsEvents: [],
      fallbackNewsEvents: [],
      newsLoading: false,
      newsError: false,
      supplyCalendar: {
        items: [],
        status: "empty",
        windowLabel: "2026-07-16 to 2026-08-30",
        message: null,
      },
    });

    render(
      <ResearchCalendarSection
        macroBriefing={{
          ...macroBriefing,
          releaseItems: [],
          releaseHistoryItems: [],
          releaseHistoryMessage: "History data failed to load.",
        }}
      />,
    );

    const disclosure = screen.getByTestId("dashboard-home-release-history-disclosure");
    expect(disclosure).not.toHaveAttribute("open");
    fireEvent.click(within(disclosure).getByRole("button"));
    expect(disclosure).toHaveAttribute("open");
    expect(within(disclosure).getByText("History data failed to load.")).toBeInTheDocument();
  });
});
