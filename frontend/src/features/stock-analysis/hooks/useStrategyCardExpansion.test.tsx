import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { useStrategyCardExpansion } from "./useStrategyCardExpansion";

describe("useStrategyCardExpansion", () => {
  it("toggles a strategy card id on and off", () => {
    const { result } = renderHook(() => useStrategyCardExpansion());

    expect(result.current.isStrategyCardExpanded("cycle-rotation")).toBe(false);

    act(() => {
      result.current.toggleStrategyCard("cycle-rotation");
    });
    expect(result.current.isStrategyCardExpanded("cycle-rotation")).toBe(true);

    act(() => {
      result.current.toggleStrategyCard("cycle-rotation");
    });
    expect(result.current.isStrategyCardExpanded("cycle-rotation")).toBe(false);
  });

  it("keeps different strategy card ids independent", () => {
    const { result } = renderHook(() => useStrategyCardExpansion());

    act(() => {
      result.current.toggleStrategyCard("cycle-rotation");
      result.current.toggleStrategyCard("theme-breakout");
    });

    expect(result.current.isStrategyCardExpanded("cycle-rotation")).toBe(true);
    expect(result.current.isStrategyCardExpanded("theme-breakout")).toBe(true);
    expect(result.current.isStrategyCardExpanded("market-priority")).toBe(false);
  });
});
