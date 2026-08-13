import { describe, expect, it } from "vitest";

import { formatResearchTitleDisplay } from "./researchTitleDisplay";

describe("formatResearchTitleDisplay", () => {
  it("strips the file extension and trailing date stamp and turns underscores into spaces", () => {
    expect(
      formatResearchTitleDisplay(
        "硕远咨询_2026年中国旅游产业链研究报告_20260715.pdf",
      ),
    ).toBe("硕远咨询 2026年中国旅游产业链研究报告");
    expect(
      formatResearchTitleDisplay("东吴证券_医药生物行业点评报告_20260715.PDF"),
    ).toBe("东吴证券 医药生物行业点评报告");
  });

  it("keeps a normal headline unchanged", () => {
    expect(
      formatResearchTitleDisplay("国债收益率曲线延续下行，资金面保持宽松"),
    ).toBe("国债收益率曲线延续下行，资金面保持宽松");
  });

  it("returns empty input unchanged", () => {
    expect(formatResearchTitleDisplay("")).toBe("");
    expect(formatResearchTitleDisplay("   ")).toBe("");
  });
});
