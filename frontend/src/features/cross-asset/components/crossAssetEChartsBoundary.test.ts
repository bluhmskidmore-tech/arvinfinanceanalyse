import { render, screen } from "@testing-library/react";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { createElement, Suspense } from "react";
import { describe, expect, it, vi } from "vitest";

const PAGE_PATH = resolve(
  process.cwd(),
  "src/features/cross-asset/pages/CrossAssetDriversPage.tsx",
);
const YIELD_CURVE_PATH = resolve(
  process.cwd(),
  "src/features/cross-asset/components/YieldCurvePanel.tsx",
);
const ECHARTS_BOUNDARY_PATH = resolve(
  process.cwd(),
  "src/features/cross-asset/components/CrossAssetECharts.ts",
);

describe("cross-asset ECharts startup boundary", () => {
  it("keeps both chart leaves behind one preloaded dynamic import", () => {
    expect(existsSync(ECHARTS_BOUNDARY_PATH)).toBe(true);

    const pageSource = readFileSync(PAGE_PATH, "utf8");
    const yieldCurveSource = readFileSync(YIELD_CURVE_PATH, "utf8");
    const boundarySource = readFileSync(ECHARTS_BOUNDARY_PATH, "utf8");

    expect(pageSource).not.toContain('import ReactECharts from "../../../lib/echarts"');
    expect(yieldCurveSource).not.toContain('import ReactECharts from "../../../lib/echarts"');
    expect(boundarySource).toContain('import("../../../lib/echarts")');
    expect(boundarySource).toContain("lazy(loadCrossAssetECharts)");
    expect(boundarySource).toContain(".catch(() => undefined)");
    expect(pageSource).toContain("preloadCrossAssetECharts();");
    expect(pageSource).toContain("<Suspense");
    expect(yieldCurveSource).toContain("<Suspense");
  });

  it("preloads the real lazy renderer once and unmounts both leaves", async () => {
    const renderer = vi.fn(() =>
      createElement("div", { "data-testid": "cross-asset-loaded-renderer" }),
    );
    const loadRenderer = vi.fn(() => ({ default: renderer }));
    let view: ReturnType<typeof render> | undefined;

    vi.resetModules();
    vi.doMock("../../../lib/echarts", loadRenderer);
    try {
      const { LazyCrossAssetECharts, preloadCrossAssetECharts } = await import("./CrossAssetECharts");

      preloadCrossAssetECharts();
      await vi.dynamicImportSettled();
      expect(loadRenderer).toHaveBeenCalledTimes(1);
      expect(renderer).not.toHaveBeenCalled();
      preloadCrossAssetECharts();
      await vi.dynamicImportSettled();
      expect(loadRenderer).toHaveBeenCalledTimes(1);

      view = render(
        createElement(
          Suspense,
          { fallback: createElement("div", { "data-testid": "cross-asset-renderer-loading" }) },
          createElement(LazyCrossAssetECharts, { key: "yield", option: {} }),
          createElement(LazyCrossAssetECharts, { key: "trend", option: {} }),
        ),
      );
      expect(await screen.findAllByTestId("cross-asset-loaded-renderer")).toHaveLength(2);
      expect(screen.queryByTestId("cross-asset-renderer-loading")).not.toBeInTheDocument();
      expect(loadRenderer).toHaveBeenCalledTimes(1);

      view.unmount();
      expect(screen.queryAllByTestId("cross-asset-loaded-renderer")).toHaveLength(0);
    } finally {
      view?.unmount();
      vi.doUnmock("../../../lib/echarts");
      vi.resetModules();
    }
  });

});
