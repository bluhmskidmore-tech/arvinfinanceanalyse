import { describe, expect, it } from "vitest";

import {
  findWorkbenchSectionByPath,
  primaryWorkbenchNavigationGroups,
  primaryWorkbenchNavigation,
  resolveWorkbenchPathAlias,
  secondaryWorkbenchNavigation,
  workbenchNavigation,
  workbenchPathAliases,
} from "../mocks/navigation";

describe("workbench navigation mocks", () => {
  it("has unique keys and unique paths", () => {
    const keys = workbenchNavigation.map((s) => s.key);
    const paths = workbenchNavigation.map((s) => s.path);
    expect(new Set(keys).size).toBe(keys.length);
    expect(new Set(paths).size).toBe(paths.length);
  });

  it("includes an agent entry outside the live primary navigation", () => {
    const agent = workbenchNavigation.find((s) => s.key === "agent");
    expect(agent).toBeDefined();
    expect(agent?.readiness).toBe("placeholder");
    expect(agent?.readinessLabel).toBe("智能体试用");
    expect(agent?.path).toBe("/agent");
    expect(primaryWorkbenchNavigation.some((s) => s.key === "agent")).toBe(false);
    expect(secondaryWorkbenchNavigation.some((s) => s.key === "agent")).toBe(true);
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

  it("marks operations-analysis as a temporary exception within the primary workbench", () => {
    const section = workbenchNavigation.find((s) => s.key === "operations-analysis");
    expect(section?.path).toBe("/operations-analysis");
    expect(section?.readiness).toBe("live");
    expect(section?.readinessLabel).toBe("临时开放");
    expect(primaryWorkbenchNavigation.some((s) => s.key === "operations-analysis")).toBe(true);
  });

  it("marks the wave-1 temporary-exception routes explicitly in navigation metadata", () => {
    const temporaryExceptionKeys = [
      "operations-analysis",
      "bond-analysis",
      "cross-asset",
      "decision-items",
      "team-performance",
      "market-data",
      "platform-config",
      "bond-dashboard",
      "positions",
      "average-balance",
      "ledger-pnl",
      "concentration-monitor",
      "cashflow-projection",
      "kpi-performance",
      "news-events",
      "product-category-pnl",
    ];

    for (const key of temporaryExceptionKeys) {
      const section = workbenchNavigation.find((item) => item.key === key);
      expect(section?.readiness).toBe("live");
      expect(section?.readinessLabel).toBe("临时开放");
      expect(section?.governanceStatus).toBe("temporary-exception");
    }
  });

  it("keeps risk-overview in the live primary navigation", () => {
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

  it("keeps liability-analytics in the live primary navigation", () => {
    const liab = workbenchNavigation.find((s) => s.key === "liability-analytics");
    expect(liab?.path).toBe("/liability-analytics");
    expect(liab?.readiness).toBe("live");
    expect(liab?.readinessLabel).toBe("已开放");
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

  it("keeps cube-query outside the live primary navigation", () => {
    const cube = workbenchNavigation.find((s) => s.key === "cube-query");
    expect(cube?.path).toBe("/cube-query");
    expect(cube?.readiness).toBe("placeholder");
    expect(primaryWorkbenchNavigation.some((s) => s.key === "cube-query")).toBe(false);
    expect(secondaryWorkbenchNavigation.some((s) => s.key === "cube-query")).toBe(true);
  });

  it("promotes decision-items into the live primary navigation as a temporary exception", () => {
    const section = workbenchNavigation.find((s) => s.key === "decision-items");
    expect(section?.readiness).toBe("live");
    expect(section?.readinessLabel).toBe("临时开放");
    expect(section?.governanceStatus).toBe("temporary-exception");
    expect(primaryWorkbenchNavigation.some((s) => s.key === "decision-items")).toBe(true);
    expect(secondaryWorkbenchNavigation.some((s) => s.key === "decision-items")).toBe(false);
  });

  it("keeps reports-center outside the live primary navigation", () => {
    const section = workbenchNavigation.find((s) => s.key === "reports-center");
    expect(section?.readiness).toBe("placeholder");
    expect(primaryWorkbenchNavigation.some((s) => s.key === "reports-center")).toBe(false);
    expect(secondaryWorkbenchNavigation.some((s) => s.key === "reports-center")).toBe(true);
  });

  it("resolves V1 bookmark path aliases for nav grouping", () => {
    expect(resolveWorkbenchPathAlias("/market")).toBe("/market-data");
    expect(resolveWorkbenchPathAlias("/assets")).toBe("/bond-dashboard");
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

  it("promotes average-balance into the live primary navigation", () => {
    const adb = workbenchNavigation.find((s) => s.key === "average-balance");
    expect(adb?.path).toBe("/average-balance");
    expect(adb?.readiness).toBe("live");
    expect(adb?.label).toBe("日均分析");
    expect(primaryWorkbenchNavigation.some((s) => s.key === "average-balance")).toBe(true);
    expect(secondaryWorkbenchNavigation.some((s) => s.key === "average-balance")).toBe(false);
  });

  it("promotes ledger-pnl into the live primary navigation", () => {
    const ledger = workbenchNavigation.find((s) => s.key === "ledger-pnl");
    expect(ledger?.path).toBe("/ledger-pnl");
    expect(ledger?.readiness).toBe("live");
    expect(primaryWorkbenchNavigation.some((s) => s.key === "ledger-pnl")).toBe(true);
    expect(secondaryWorkbenchNavigation.some((s) => s.key === "ledger-pnl")).toBe(false);
  });

  it("tracks reserved modules outside the live primary navigation", () => {
    expect(
      secondaryWorkbenchNavigation.every((s) => s.readiness !== "live"),
    ).toBe(true);
    expect(primaryWorkbenchNavigation.length + secondaryWorkbenchNavigation.length).toBe(
      workbenchNavigation.filter((s) => s.navigationVisibility !== "hidden").length,
    );
    expect(secondaryWorkbenchNavigation.length).toBeGreaterThan(0);
  });

  it("groups live entries into a smaller set of primary workspaces", () => {
    expect(primaryWorkbenchNavigationGroups.length).toBeLessThan(
      primaryWorkbenchNavigation.length,
    );
    expect(
      primaryWorkbenchNavigationGroups.every((group) => group.sections.length > 0),
    ).toBe(true);

    const groupedSectionKeys = primaryWorkbenchNavigationGroups.flatMap((group) =>
      group.sections.map((section) => section.key),
    );
    expect(new Set(groupedSectionKeys).size).toBe(primaryWorkbenchNavigation.length);
    expect(groupedSectionKeys.sort()).toEqual(
      primaryWorkbenchNavigation.map((section) => section.key).sort(),
    );
  });

  it("keeps every workspace default path inside its own grouped sections", () => {
    for (const group of primaryWorkbenchNavigationGroups) {
      expect(group.sections.some((section) => section.path === group.defaultPath)).toBe(
        true,
      );
    }
  });

  it("resolves MOSS-V1-style paths to the canonical V3 workbench routes", () => {
    expect(resolveWorkbenchPathAlias("/adb")).toBe("/average-balance");
    expect(resolveWorkbenchPathAlias("/macro-analysis")).toBe("/market-data");
    expect(resolveWorkbenchPathAlias("/pnl-by-business")).toBe("/ledger-pnl");
    expect(resolveWorkbenchPathAlias("/liabilities")).toBe("/liability-analytics");
    expect(resolveWorkbenchPathAlias("/bonds")).toBe("/bond-dashboard");
    expect(resolveWorkbenchPathAlias("/bond-analytics-advanced")).toBe("/bond-analysis");
    expect(resolveWorkbenchPathAlias("/average-balance")).toBe("/average-balance");
  });

  it("maps aliased paths to the same section as their canonical target", () => {
    const adb = workbenchNavigation.find((s) => s.key === "average-balance");
    expect(adb).toBeDefined();
    expect(findWorkbenchSectionByPath("/adb", workbenchNavigation).key).toBe("average-balance");
    expect(findWorkbenchSectionByPath("/average-balance", workbenchNavigation).key).toBe(
      "average-balance",
    );
  });

  it("keeps every workbenchPathAliases value as a real navigation path", () => {
    const paths = new Set(workbenchNavigation.map((s) => s.path));
    for (const target of Object.values(workbenchPathAliases)) {
      expect(paths.has(target)).toBe(true);
    }
  });
});
