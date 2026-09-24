import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PerformanceComparison } from "../features/bond-analytics/components/PerformanceComparison";
import { RiskTrendChart } from "../features/bond-analytics/components/RiskTrendChart";

describe("BondAnalytics evidence panels", () => {
  it.each([
    ["风险趋势（近12周）", <RiskTrendChart />],
    ["组合表现对比（年初至今）", <PerformanceComparison />],
  ])("renders %s with dark-workbench-compatible panel tokens", (heading, panel) => {
    const { container } = render(panel);

    const title = screen.getByRole("heading", { level: 2, name: heading });
    const root = container.firstElementChild as HTMLElement;

    expect(root.tagName).toBe("SECTION");
    expect(title.parentElement).toBe(root);
    expect(root.style.border).toBe("1px solid var(--ib-hairline)");
    expect(root.style.borderRadius).toBe("var(--dh-api-radius, 6px)");
    expect(root.style.background).toBe("var(--ib-surface)");
    expect(root.style.boxShadow).toBe("none");
    expect(root.getAttribute("style")).not.toMatch(/rgb\(|24px/);
  });
});
