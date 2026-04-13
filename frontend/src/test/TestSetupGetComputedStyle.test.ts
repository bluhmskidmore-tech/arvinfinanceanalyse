import { describe, expect, it } from "vitest";

describe("test setup getComputedStyle patch", () => {
  it("does not throw when pseudo element is requested", () => {
    expect(() => window.getComputedStyle(document.body, "::before")).not.toThrow();
  });
});
