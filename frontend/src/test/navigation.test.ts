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

  it("promotes bond-dashboard into the live primary navigation", () => {
    const dash = workbenchNavigation.find((s) => s.key === "bond-dashboard");
    expect(dash?.path).toBe("/bond-dashboard");
    expect(dash?.readiness).toBe("live");
    expect(primaryWorkbenchNavigation.some((s) => s.key === "bond-dashboard")).toBe(true);
    expect(secondaryWorkbenchNavigation.some((s) => s.key === "bond-dashboard")).toBe(false);
  });

  it("promotes bond-analysis into the live primary navigation", () => {
    const bondAnalysis = workbenchNavigation.find((s) => s.key === "bond-analysis");
    expect(bondAnalysis?.readiness).toBe("live");
    expect(primaryWorkbenchNavigation.some((s) => s.key === "bond-analysis")).toBe(true);
    expect(secondaryWorkbenchNavigation.some((s) => s.key === "bond-analysis")).toBe(false);
  });

  it("promotes cross-asset into the live primary navigation", () => {
    const cross = workbenchNavigation.find((s) => s.key === "cross-asset");
    expect(cross?.path).toBe("/cross-asset");
    expect(cross?.readiness).toBe("live");
    expect(primaryWorkbenchNavigation.some((s) => s.key === "cross-asset")).toBe(true);
    expect(secondaryWorkbenchNavigation.some((s) => s.key === "cross-asset")).toBe(false);
  });

  it("promotes positions into the live primary navigation", () => {
    const positions = workbenchNavigation.find((s) => s.key === "positions");
    expect(positions?.readiness).toBe("live");
    expect(primaryWorkbenchNavigation.some((s) => s.key === "positions")).toBe(true);
    expect(secondaryWorkbenchNavigation.some((s) => s.key === "positions")).toBe(false);
  });

  it("promotes liability-analytics into the live primary navigation", () => {
    const liab = workbenchNavigation.find((s) => s.key === "liability-analytics");
    expect(liab?.path).toBe("/liability-analytics");
    expect(liab?.readiness).toBe("live");
    expect(primaryWorkbenchNavigation.some((s) => s.key === "liability-analytics")).toBe(true);
    expect(secondaryWorkbenchNavigation.some((s) => s.key === "liability-analytics")).toBe(false);
  });

  it("promotes cashflow-projection into the live primary navigation", () => {
    const cf = workbenchNavigation.find((s) => s.key === "cashflow-projection");
    expect(cf?.path).toBe("/cashflow-projection");
    expect(cf?.readiness).toBe("live");
    expect(primaryWorkbenchNavigation.some((s) => s.key === "cashflow-projection")).toBe(true);
    expect(secondaryWorkbenchNavigation.some((s) => s.key === "cashflow-projection")).toBe(false);
  });

  it("promotes kpi-performance into the live primary navigation", () => {
    const kpi = workbenchNavigation.find((s) => s.key === "kpi-performance");
    expect(kpi?.path).toBe("/kpi");
    expect(kpi?.readiness).toBe("live");
    expect(primaryWorkbenchNavigation.some((s) => s.key === "kpi-performance")).toBe(true);
    expect(secondaryWorkbenchNavigation.some((s) => s.key === "kpi-performance")).toBe(false);
  });

  it("promotes team-performance into the live primary navigation", () => {
    const team = workbenchNavigation.find((s) => s.key === "team-performance");
    expect(team?.path).toBe("/team-performance");
    expect(team?.readiness).toBe("live");
    expect(primaryWorkbenchNavigation.some((s) => s.key === "team-performance")).toBe(true);
    expect(secondaryWorkbenchNavigation.some((s) => s.key === "team-performance")).toBe(false);
  });

  it("promotes cube-query into the live primary navigation", () => {
    const cube = workbenchNavigation.find((s) => s.key === "cube-query");
    expect(cube?.path).toBe("/cube-query");
    expect(cube?.readiness).toBe("live");
    expect(primaryWorkbenchNavigation.some((s) => s.key === "cube-query")).toBe(true);
    expect(secondaryWorkbenchNavigation.some((s) => s.key === "cube-query")).toBe(false);
  });

  it("promotes pnl-attribution into the live primary navigation", () => {
    const pnlAttr = workbenchNavigation.find((s) => s.key === "pnl-attribution");
    expect(pnlAttr?.path).toBe("/pnl-attribution");
    expect(pnlAttr?.readiness).toBe("live");
    expect(primaryWorkbenchNavigation.some((s) => s.key === "pnl-attribution")).toBe(true);
    expect(secondaryWorkbenchNavigation.some((s) => s.key === "pnl-attribution")).toBe(false);
  });

  it("promotes platform-config into the live primary navigation", () => {
    const platform = workbenchNavigation.find((s) => s.key === "platform-config");
    expect(platform?.path).toBe("/platform-config");
    expect(platform?.readiness).toBe("live");
    expect(primaryWorkbenchNavigation.some((s) => s.key === "platform-config")).toBe(true);
    expect(secondaryWorkbenchNavigation.some((s) => s.key === "platform-config")).toBe(false);
  });

  it("tracks reserved modules outside the live primary navigation", () => {
    expect(
      secondaryWorkbenchNavigation.every((s) => s.readiness !== "live"),
    ).toBe(true);
    expect(primaryWorkbenchNavigation.length + secondaryWorkbenchNavigation.length).toBe(
      workbenchNavigation.filter((s) => s.navigationVisibility !== "hidden").length,
    );
    expect(secondaryWorkbenchNavigation.length).toBe(0);
  });
});
