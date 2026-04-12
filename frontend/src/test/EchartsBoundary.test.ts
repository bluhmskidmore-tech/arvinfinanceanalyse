import { readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const TEST_DIR = dirname(fileURLToPath(import.meta.url));
const SRC_DIR = join(TEST_DIR, "..");
const SHARED_ECHARTS_MODULE = "lib/echarts.tsx";

function walkFiles(dir: string): string[] {
  const entries = readdirSync(dir, { withFileTypes: true });
  const files: string[] = [];
  for (const entry of entries) {
    const fullPath = join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...walkFiles(fullPath));
      continue;
    }
    if (!/\.(ts|tsx)$/.test(entry.name)) {
      continue;
    }
    files.push(fullPath);
  }
  return files;
}

function srcRelativePath(path: string) {
  return relative(SRC_DIR, path).replace(/\\/g, "/");
}

describe("shared echarts boundary", () => {
  it("keeps runtime echarts imports isolated to the shared wrapper", () => {
    const offenders = walkFiles(SRC_DIR)
      .filter((path) => !path.includes(`${TEST_DIR}\\`))
      .filter((path) => srcRelativePath(path) !== SHARED_ECHARTS_MODULE)
      .filter((path) => {
        const source = readFileSync(path, "utf8");
        return (
          source.includes('"echarts-for-react"') ||
          source.includes('"echarts-for-react/lib/core"') ||
          source.includes('"echarts/core"') ||
          source.includes('"echarts/charts"') ||
          source.includes('"echarts/components"') ||
          source.includes('"echarts/renderers"')
        );
      })
      .map(srcRelativePath);

    expect(offenders).toEqual([]);
  });

  it("keeps shared echarts registrations centralized in the wrapper", () => {
    const source = readFileSync(join(SRC_DIR, SHARED_ECHARTS_MODULE), "utf8");

    expect(source).toContain("echarts.use([");
    expect(source).toContain("BarChart");
    expect(source).toContain("PieChart");
    expect(source).toContain("CanvasRenderer");
  });
});
