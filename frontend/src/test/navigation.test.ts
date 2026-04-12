import { describe, expect, it } from "vitest";

import {
  primaryWorkbenchNavigation,
  secondaryWorkbenchNavigation,
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
    expect(primaryWorkbenchNavigation.every((s) => s.readiness === "live")).toBe(
      true,
    );
  });

  it("includes dashboard at /", () => {
    const dash = workbenchNavigation.find((s) => s.key === "dashboard");
    expect(dash?.path).toBe("/");
  });

  it("promotes risk-overview into the live primary navigation", () => {
    const riskOverview = workbenchNavigation.find((s) => s.key === "risk-overview");
    expect(riskOverview?.readiness).toBe("live");
    expect(primaryWorkbenchNavigation.some((s) => s.key === "risk-overview")).toBe(true);
    expect(secondaryWorkbenchNavigation.some((s) => s.key === "risk-overview")).toBe(false);
  });

  it("tracks reserved modules outside the live primary navigation", () => {
    expect(secondaryWorkbenchNavigation.length).toBeGreaterThan(0);
    expect(
      secondaryWorkbenchNavigation.every((s) => s.readiness !== "live"),
    ).toBe(true);
    expect(primaryWorkbenchNavigation.length + secondaryWorkbenchNavigation.length).toBe(
      workbenchNavigation.filter((s) => s.navigationVisibility !== "hidden").length,
    );
  });
});
