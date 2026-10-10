import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const referencePanelsSource = readFileSync(
  resolve(process.cwd(), "src/features/cross-asset/components/ReferencePanels.tsx"),
  "utf8",
);

describe("cross-asset lightweight icon boundary", () => {
  it("keeps the route independent from the Ant Design icon runtime", () => {
    expect(referencePanelsSource).not.toContain("@ant-design/icons");
    expect(referencePanelsSource).toContain('import { LightIcon } from "../../../components/LightIcon"');
  });
});
