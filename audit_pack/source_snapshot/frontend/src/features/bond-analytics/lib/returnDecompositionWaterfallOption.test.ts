import { describe, expect, it } from "vitest";

import {
  RETURN_DECOMPOSITION_WATERFALL_CATEGORY_COUNT,
  RETURN_DECOMPOSITION_WATERFALL_CATEGORIES,
} from "./returnDecompositionWaterfallOption";

describe("returnDecompositionWaterfallOption", () => {
  it("exports a fixed category list length for tooltip and xAxis", () => {
    expect(RETURN_DECOMPOSITION_WATERFALL_CATEGORIES.length).toBe(RETURN_DECOMPOSITION_WATERFALL_CATEGORY_COUNT);
    expect(RETURN_DECOMPOSITION_WATERFALL_CATEGORY_COUNT).toBe(8);
  });
});
