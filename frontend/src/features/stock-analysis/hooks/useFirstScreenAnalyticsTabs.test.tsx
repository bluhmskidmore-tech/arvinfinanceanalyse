import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { useFirstScreenAnalyticsTabs } from "./useFirstScreenAnalyticsTabs";

describe("useFirstScreenAnalyticsTabs", () => {
  it("starts on consensus without requesting deferred analytics", () => {
    const { result } = renderHook(() => useFirstScreenAnalyticsTabs());

    expect(result.current.firstScreenAnalyticsTab).toBe("consensus");
    expect(result.current.firstScreenAnalyticsRequested).toBe(false);
  });

  it("marks deferred analytics requested when priority or optimization is opened", () => {
    const { result } = renderHook(() => useFirstScreenAnalyticsTabs());

    act(() => {
      result.current.handleFirstScreenAnalyticsTabChange("priority");
    });
    expect(result.current.firstScreenAnalyticsTab).toBe("priority");
    expect(result.current.firstScreenAnalyticsRequested).toBe(true);

    act(() => {
      result.current.handleFirstScreenAnalyticsTabChange("consensus");
    });
    expect(result.current.firstScreenAnalyticsTab).toBe("consensus");
    expect(result.current.firstScreenAnalyticsRequested).toBe(true);

    act(() => {
      result.current.handleFirstScreenAnalyticsTabChange("optimization");
    });
    expect(result.current.firstScreenAnalyticsTab).toBe("optimization");
    expect(result.current.firstScreenAnalyticsRequested).toBe(true);
  });
});
