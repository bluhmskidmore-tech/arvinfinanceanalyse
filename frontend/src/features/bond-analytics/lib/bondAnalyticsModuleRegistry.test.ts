import { describe, expect, it } from "vitest";

import {
  BOND_ANALYTICS_CURRENT_MODULES,
  BOND_ANALYTICS_FUTURE_MODULES,
  getBondAnalyticsModuleDefinition,
} from "./bondAnalyticsModuleRegistry";

describe("bondAnalyticsModuleRegistry", () => {
  it("keeps current and future module keys unique", () => {
    const currentKeys = BOND_ANALYTICS_CURRENT_MODULES.map((m) => m.key);
    const futureKeys = BOND_ANALYTICS_FUTURE_MODULES.map((m) => m.key);

    expect(new Set(currentKeys).size).toBe(currentKeys.length);
    expect(new Set(futureKeys).size).toBe(futureKeys.length);
  });

  it("requires non-empty label, description, and detailHint for each current module", () => {
    for (const module of BOND_ANALYTICS_CURRENT_MODULES) {
      expect(module.label.trim().length, `label for ${module.key}`).toBeGreaterThan(0);
      expect(module.description.trim().length, `description for ${module.key}`).toBeGreaterThan(0);
      expect(module.detailHint.trim().length, `detailHint for ${module.key}`).toBeGreaterThan(0);
    }
  });

  it("returns the exact module definition for a known key", () => {
    const target = BOND_ANALYTICS_CURRENT_MODULES.find((m) => m.key === "action-attribution");
    expect(target).toBeDefined();
    expect(getBondAnalyticsModuleDefinition("action-attribution")).toEqual(target);
  });

  it("falls back to the first current module for an unknown key", () => {
    const fallback = BOND_ANALYTICS_CURRENT_MODULES[0];
    expect(
      getBondAnalyticsModuleDefinition("not-a-real-key" as never),
    ).toEqual(fallback);
  });
});
