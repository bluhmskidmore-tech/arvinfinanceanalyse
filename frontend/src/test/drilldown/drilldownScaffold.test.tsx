import { beforeEach, describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { DrilldownRenderHarness } from "./DrilldownRenderHarness";
import {
  createNeutralDrilldownFixture,
  resetNeutralDrilldownFixtureSeq,
} from "./drilldownNeutralFixtures";

describe("drilldown 测试支架（中性）", () => {
  beforeEach(() => {
    resetNeutralDrilldownFixtureSeq();
  });

  it("DrilldownRenderHarness 能挂载子节点", () => {
    render(
      <DrilldownRenderHarness>
        <span>harness-child</span>
      </DrilldownRenderHarness>,
    );

    expect(screen.getByTestId("drilldown-render-harness")).toBeInTheDocument();
    expect(screen.getByText("harness-child")).toBeInTheDocument();
  });

  it("中性 fixture 仅保证测试内可区分，不声明领域形状", () => {
    const a = createNeutralDrilldownFixture("a");
    const b = createNeutralDrilldownFixture("b");

    expect(a.seq).not.toBe(b.seq);
    expect(a.label).toBe("a");
    expect(b.label).toBe("b");
  });
});