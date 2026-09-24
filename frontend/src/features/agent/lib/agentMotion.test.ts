import { afterEach, describe, expect, it, vi } from "vitest";

import { getAgentScrollBehavior } from "./agentMotion";

describe("getAgentScrollBehavior", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("uses an immediate scroll when reduced motion is preferred", () => {
    const matchMedia = vi.fn().mockReturnValue({ matches: true });
    vi.stubGlobal("matchMedia", matchMedia);

    expect(getAgentScrollBehavior()).toBe("auto");
    expect(matchMedia).toHaveBeenCalledWith("(prefers-reduced-motion: reduce)");
  });

  it("keeps smooth scrolling when reduced motion is not preferred", () => {
    vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({ matches: false }));

    expect(getAgentScrollBehavior()).toBe("smooth");
  });

  it("keeps smooth scrolling when matchMedia is unavailable", () => {
    vi.stubGlobal("matchMedia", undefined);

    expect(getAgentScrollBehavior()).toBe("smooth");
  });
});
