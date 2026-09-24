import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import type { ApiEnvelope, ChoiceMacroLatestPayload } from "../../../api/contracts";
import {
  buildMarketDataTerminalModel,
  buildTerminalTickerItems,
} from "./marketDataTerminalModel";

const goldenPath = resolve(
  dirname(fileURLToPath(import.meta.url)),
  "../../../../../tests/golden_samples/GS-MKT-RATES-FRAGMENT-A/response.json",
);

const goldenEnvelope = JSON.parse(readFileSync(goldenPath, "utf8")) as ApiEnvelope<ChoiceMacroLatestPayload>;

describe("GS-MKT-RATES-FRAGMENT-A frontend tie-out", () => {
  it("maps formal rates fragment to terminal tape without recomputing values", () => {
    const model = buildMarketDataTerminalModel({ ratesEnvelope: goldenEnvelope });
    const items = buildTerminalTickerItems(model);
    const byKey = Object.fromEntries(items.map((item) => [item.key, item]));

    expect(goldenEnvelope.result_meta.basis).toBe("formal");
    expect(goldenEnvelope.result_meta.formal_use_allowed).toBe(true);
    expect(byKey.cgb10y?.value).toBe("1.71%");
    expect(byKey.cgb5y?.value).toBe("1.58%");
    expect(byKey.cdb10y?.value).toBe("2.18%");
    expect(byKey.cdb5y?.value).toBe("2.05%");
    expect(byKey.dr007?.value).toBe("1.83%");
    expect(byKey.cgb10y?.delta).toMatch(/^-/);
  });
});
