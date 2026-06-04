import { readFileSync } from "node:fs";
import { resolve } from "node:path";

describe("WorkbenchShell theme guard", () => {
  it("keeps inactive group subnav pills on the homepage blue-gray palette", () => {
    const shellSource = readFileSync(
      resolve(process.cwd(), "src/layouts/WorkbenchShell.tsx"),
      "utf8",
    );
    const globalCss = readFileSync(resolve(process.cwd(), "src/styles/global.css"), "utf8");
    const heroRule = globalCss.match(/\.workbench-workspace-hero\s*\{[^}]+\}/)?.[0] ?? "";

    expect(shellSource).not.toContain("rgba(255, 253, 248");
    expect(shellSource).not.toMatch(/moss-color-warm-|designTokens\.color\.warm/);
    expect(heroRule).not.toContain("rgba(255, 253, 248");
    expect(heroRule).not.toMatch(/moss-color-warm-|designTokens\.color\.warm/);
    expect(heroRule).toContain("var(--moss-color-card-bg)");
  });
});
