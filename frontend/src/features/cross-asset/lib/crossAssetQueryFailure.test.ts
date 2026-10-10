import { describe, expect, it } from "vitest";

import {
  classifyCrossAssetQueryFailure,
  linkageUnavailableEvidence,
  linkageUnavailableSummary,
} from "./crossAssetQueryFailure";

describe("crossAssetQueryFailure", () => {
  it("classifies backend permission denials as permission failures", () => {
    expect(
      classifyCrossAssetQueryFailure(
        new Error("User is not allowed to read macro_bond_linkage."),
      ),
    ).toBe("permission");
    expect(classifyCrossAssetQueryFailure(new Error("Request failed: /api/x (403)"))).toBe(
      "permission",
    );
  });

  it("maps permission failures to user-facing linkage copy", () => {
    expect(linkageUnavailableSummary("permission")).toBe("联动分析权限受限，四维判断待开通。");
    expect(linkageUnavailableEvidence("permission")).toBe("macro_bond_linkage.read 权限不足");
  });
});
