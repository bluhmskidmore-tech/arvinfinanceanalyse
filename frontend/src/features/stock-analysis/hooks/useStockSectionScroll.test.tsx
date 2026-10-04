import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useStockSectionScroll } from "./useStockSectionScroll";

function mountSection(id: string, { insideClosedDetails = false } = {}) {
  const section = document.createElement("section");
  section.id = id;
  section.scrollIntoView = vi.fn();
  if (insideClosedDetails) {
    const details = document.createElement("details");
    details.append(section);
    document.body.append(details);
    return { section, details };
  }
  document.body.append(section);
  return { section, details: null };
}

describe("useStockSectionScroll", () => {
  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("opens enclosing disclosures and scrolls when the target is already mounted", () => {
    const { section, details } = mountSection("stock-analysis-validation-evidence", {
      insideClosedDetails: true,
    });
    const onRequestDeepResearch = vi.fn();
    const { result } = renderHook(() => useStockSectionScroll({ onRequestDeepResearch }));

    act(() => {
      result.current.scrollToStockSection("stock-analysis-validation-evidence");
    });

    expect(details?.open).toBe(true);
    expect(section.scrollIntoView).toHaveBeenCalledWith({ behavior: "smooth", block: "start" });
    expect(onRequestDeepResearch).not.toHaveBeenCalled();
  });

  it("requests the lazy zone and scrolls once the target appears in the DOM", async () => {
    const onRequestDeepResearch = vi.fn();
    const { result } = renderHook(() => useStockSectionScroll({ onRequestDeepResearch }));

    act(() => {
      result.current.scrollToStockSection("stock-analysis-deep-research");
    });
    expect(onRequestDeepResearch).toHaveBeenCalledTimes(1);

    const { section } = mountSection("stock-analysis-deep-research");

    await waitFor(() => {
      expect(section.scrollIntoView).toHaveBeenCalledWith({ behavior: "smooth", block: "start" });
    });
  });

  it("also resolves targets by data-testid", () => {
    const section = document.createElement("section");
    section.dataset.testid = "stock-analysis-review-queue";
    section.scrollIntoView = vi.fn();
    document.body.append(section);
    const onRequestDeepResearch = vi.fn();
    const { result } = renderHook(() => useStockSectionScroll({ onRequestDeepResearch }));

    act(() => {
      result.current.scrollToStockSection("stock-analysis-review-queue");
    });

    expect(section.scrollIntoView).toHaveBeenCalledTimes(1);
    expect(onRequestDeepResearch).not.toHaveBeenCalled();
  });
});
