import { readFileSync } from "node:fs";
import { resolve } from "node:path";

describe("WorkbenchShell theme guard", () => {
  it("keeps inactive group subnav pills on the homepage blue-gray palette", () => {
    const source = readFileSync(
      resolve(process.cwd(), "src/layouts/WorkbenchShell.tsx"),
      "utf8",
    );

    expect(source).not.toContain("rgba(255, 253, 248");
    expect(source).not.toMatch(/moss-color-warm-|designTokens\.color\.warm/);
    expect(source).toContain("shellTokens.colorBgSurface");
  });
});
