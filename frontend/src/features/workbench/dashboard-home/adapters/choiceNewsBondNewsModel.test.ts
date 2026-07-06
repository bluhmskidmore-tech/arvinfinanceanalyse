import { describe, expect, it } from "vitest";

import type { ChoiceNewsEventsPayload } from "../../../../api/contracts";
import { buildHomeBondNewsModel } from "./buildHomeBondNewsModel";

describe("ChoiceNews bond news model", () => {
  it("uses ChoiceNews payload as_of_date in the existing data date label", () => {
    const payload: ChoiceNewsEventsPayload = {
      total_rows: 0,
      limit: 10,
      offset: 0,
      as_of_date: "2026-05-08",
      excluded_future_rows: 2,
      events: [],
    };

    const model = buildHomeBondNewsModel({
      todayIsoDate: "2026-05-08",
      events: [],
      choiceNewsPayloads: [payload],
    });

    expect(model.asOfLabel).toBe("数据日期 2026-05-08 · 已剔除未来 2 条");
  });
});
