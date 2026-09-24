import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

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
});
