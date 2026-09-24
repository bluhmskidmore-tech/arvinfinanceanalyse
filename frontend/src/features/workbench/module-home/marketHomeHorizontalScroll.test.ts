import { describe, expect, it, vi } from "vitest";

import { handleHorizontalScrollKeyboard } from "./marketHomeHorizontalScroll";

function keyboardEvent(key: string, element: HTMLElement) {
  return {
    key,
    currentTarget: element,
    preventDefault: vi.fn(),
  } as unknown as Parameters<typeof handleHorizontalScrollKeyboard>[0];
}

describe("handleHorizontalScrollKeyboard", () => {
  it("scrolls right and left when arrow keys are pressed", () => {
    const element = document.createElement("div");
    const scrollBy = vi.fn();
    element.scrollBy = scrollBy;

    handleHorizontalScrollKeyboard(keyboardEvent("ArrowRight", element));
    handleHorizontalScrollKeyboard(keyboardEvent("ArrowLeft", element), 80);

    expect(scrollBy).toHaveBeenNthCalledWith(1, { left: 120, behavior: "smooth" });
    expect(scrollBy).toHaveBeenNthCalledWith(2, { left: -80, behavior: "smooth" });
  });

  it("ignores unrelated keys", () => {
    const element = document.createElement("div");
    const scrollBy = vi.fn();
    element.scrollBy = scrollBy;

    handleHorizontalScrollKeyboard(keyboardEvent("Enter", element));

    expect(scrollBy).not.toHaveBeenCalled();
  });
});
