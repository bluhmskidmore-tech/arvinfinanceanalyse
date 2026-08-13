import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const moduleHomePageSource = readFileSync(
  resolve(process.cwd(), "src/features/workbench/module-home/ModuleWorkbenchHomePage.tsx"),
  "utf8",
);
const moduleHomeCss = readFileSync(
  resolve(process.cwd(), "src/features/workbench/module-home/moduleWorkbenchHome.module.css"),
  "utf8",
);
const macroToolkitPageSource = readFileSync(
  resolve(process.cwd(), "src/features/macro-toolkit/pages/MacroToolkitPage.tsx"),
  "utf8",
);
const macroToolkitCss = readFileSync(
  resolve(process.cwd(), "src/features/macro-toolkit/pages/MacroToolkitPage.css"),
  "utf8",
);

/**
 * 仅守卫 module-home 与 macro-toolkit 两个页面族对 dh-api 变量的引用。
 * 37-scope Nocturne / AntD 契约由 theme.test.ts 覆盖，本文件不代表全站路由契约。
 */
describe("module-home and macro-toolkit dh-api variable reference guards", () => {
  it("pins module workbench home routes to dh-api page tokens", () => {
    expect(moduleHomePageSource).toContain("theme-dh-api");
    expect(moduleHomeCss).toContain("--mh-page-bg: var(--dh-api-bg);");
    expect(moduleHomeCss).toContain("--mh-card: var(--dh-api-panel);");
    expect(moduleHomeCss).not.toContain("--mh-page-bg: var(--ib-paper);");
  });

  it("pins macro toolkit routes to dh-api page tokens", () => {
    expect(macroToolkitPageSource).toContain("theme-dh-api");
    expect(macroToolkitCss).toContain("--dh-bg: var(--dh-api-bg);");
    expect(macroToolkitCss).toContain("--dh-card: var(--dh-api-panel);");
    expect(macroToolkitCss).toContain("color-scheme: dark;");
    expect(macroToolkitCss).toContain("background: var(--macro-toolkit-card-soft);");
  });
});
