import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const FRONTEND_ROOT = process.cwd();
const PACKAGE_JSON_PATH = resolve(FRONTEND_ROOT, "package.json");
const VITE_CONFIG_PATH = resolve(FRONTEND_ROOT, "vite.config.ts");
const GLOBAL_CSS_PATH = resolve(FRONTEND_ROOT, "src/styles/global.css");
const TAILWIND_CSS_PATH = resolve(FRONTEND_ROOT, "src/styles/tailwind.css");

describe("Tailwind integration", () => {
  it("wires Tailwind v4 through Vite without enabling Preflight resets", () => {
    const packageJson = JSON.parse(readFileSync(PACKAGE_JSON_PATH, "utf8")) as {
      devDependencies?: Record<string, string>;
      dependencies?: Record<string, string>;
    };
    const viteConfig = readFileSync(VITE_CONFIG_PATH, "utf8");
    const globalCss = readFileSync(GLOBAL_CSS_PATH, "utf8");
    const tailwindCss = readFileSync(TAILWIND_CSS_PATH, "utf8");
    const normalizedTailwindCss = tailwindCss.replace(/^\uFEFF/, "").replace(/\r\n?/g, "\n");

    expect({
      ...packageJson.dependencies,
      ...packageJson.devDependencies,
    }).toMatchObject({
      "@tailwindcss/vite": expect.any(String),
      tailwindcss: expect.any(String),
    });
    expect(viteConfig).toContain('import tailwindcss from "@tailwindcss/vite";');
    expect(viteConfig).toContain("tailwindcss()");
    expect(globalCss).toContain('@import "./tailwind.css";');
    expect(globalCss).not.toContain('@import "tailwindcss/theme.css" layer(theme);');
    expect(globalCss).not.toContain('@import "tailwindcss/utilities.css" layer(utilities);');
    expect(globalCss).not.toContain("tailwindcss/preflight.css");
    expect(globalCss).not.toContain('@import "tailwindcss";');
    expect(
      normalizedTailwindCss.startsWith(
        '@layer theme, base, components, utilities;\n@import "tailwindcss/theme.css" layer(theme);\n@import "tailwindcss/utilities.css" layer(utilities);\n',
      ),
    ).toBe(true);
    expect(tailwindCss).toContain('@import "tailwindcss/theme.css" layer(theme);');
    expect(tailwindCss).toContain('@import "tailwindcss/utilities.css" layer(utilities);');
    expect(tailwindCss).not.toContain("tailwindcss/preflight.css");
    expect(tailwindCss).not.toContain('@import "tailwindcss";');
  });
});
