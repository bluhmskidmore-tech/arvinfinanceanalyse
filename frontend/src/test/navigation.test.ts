import { describe, expect, it } from "vitest";

import {
  primaryWorkbenchNavigation,
  workbenchNavigation,
} from "../mocks/navigation";

describe("workbench navigation mocks", () => {
  it("has unique keys and unique paths", () => {
    const keys = workbenchNavigation.map((s) => s.key);
    const paths = workbenchNavigation.map((s) => s.path);
    expect(new Set(keys).size).toBe(keys.length);
    expect(new Set(paths).size).toBe(paths.length);
  });

  it("includes a hidden agent entry", () => {
    const agent = workbenchNavigation.find((s) => s.key === "agent");
    expect(agent).toBeDefined();
    expect(agent?.navigationVisibility).toBe("hidden");
    expect(agent?.path).toBe("/agent");
  });

  it("excludes hidden entries from primaryWorkbenchNavigation", () => {
    expect(
      primaryWorkbenchNavigation.some((s) => s.navigationVisibility === "hidden"),
    ).toBe(false);
    expect(primaryWorkbenchNavigation.length).toBeLessThan(
      workbenchNavigation.length,
    );
  });

  it("includes dashboard at /", () => {
    const dash = workbenchNavigation.find((s) => s.key === "dashboard");
    expect(dash?.path).toBe("/");
  });

  it("has more total entries than visible primary entries", () => {
    expect(primaryWorkbenchNavigation.length).toBeLessThan(
      workbenchNavigation.length,
    );
  });
});
