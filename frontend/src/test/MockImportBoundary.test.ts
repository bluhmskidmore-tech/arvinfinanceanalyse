import { ESLint } from "eslint";
import { describe, expect, it } from "vitest";

const eslint = new ESLint({ overrideConfigFile: "eslint.config.js" });

async function boundaryErrors(source: string, filePath: string) {
  const [result] = await eslint.lintText(source, { filePath });
  return result.messages.filter(({ ruleId }) =>
    ruleId === "no-restricted-imports" || ruleId === "no-restricted-syntax",
  );
}

describe("mock runtime import boundary", () => {
  it.each([
    'import { sample } from "../../mocks/ordinaryData"; sample();',
    'export { sample } from "../../mocks/ordinaryData";',
    'void import("../../mocks/ordinaryData");',
  ])("rejects a page payload import regardless of its file name (%s)", async (source) => {
    expect(await boundaryErrors(source, "src/features/workbench/samplePage.ts")).toHaveLength(1);
  });

  it.each([
    "src/test/sample.test.ts",
    "src/features/workbench/sample.test.ts",
    "src/mocks/ordinaryData.ts",
    "src/api/clientContext.ts",
  ])("allows the registered mock entry point %s", async (filePath) => {
    expect(await boundaryErrors('void import("../mocks/ordinaryData");', filePath)).toEqual([]);
  });

  it("allows erased type imports without making payloads reachable", async () => {
    expect(await boundaryErrors(
      'import type { Sample } from "../../mocks/ordinaryData"; export type { Sample };',
      "src/features/workbench/samplePage.ts",
    )).toEqual([]);
  });
});
