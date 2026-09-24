import { describe, expect, it } from "vitest";

import { buildHomeResearchCalendarModel } from "./buildHomeResearchCalendarModel";

describe("buildHomeResearchCalendarModel", () => {
  it("builds research calendar states", () => {
    const empty = buildHomeResearchCalendarModel({
      events: [],
      isLoading: false,
      isError: false,
      startDate: "2026-04-23",
      endDate: "2026-05-14",
    });
    const ready = buildHomeResearchCalendarModel({
      events: [
        { id: "high", date: "2026-04-24", title: "high", kind: "supply", severity: "high" },
        { id: "low", date: "2026-04-25", title: "low", kind: "auction", severity: "low" },
        { id: "mid", date: "2026-04-26", title: "mid", kind: "supply", severity: "medium" },
      ],
      isLoading: false,
      isError: false,
      startDate: "2026-04-23",
      endDate: "2026-05-14",
    });

    expect(empty.status).toBe("empty");
    expect(ready.status).toBe("ready");
    expect(ready.items.map((item) => item.id)).toEqual(["high", "mid"]);
  });
});
