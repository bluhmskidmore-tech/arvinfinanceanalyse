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

  it("drops a leading dash left over from source concatenation", () => {
    expect(
      formatResearchTitleDisplay(
        "— 英国财政大臣里夫斯：英国将在2027年初发行首个数字主权债券。",
      ),
    ).toBe("英国财政大臣里夫斯：英国将在2027年初发行首个数字主权债券。");
    expect(formatResearchTitleDisplay("· 央行开展逆回购操作")).toBe(
      "央行开展逆回购操作",
    );
  });

  it("keeps an inline dash inside the headline", () => {
    expect(formatResearchTitleDisplay("中美利差—走阔至历史高位")).toBe(
      "中美利差—走阔至历史高位",
    );
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

  it("strips a title prefix duplicated by the source column", () => {
    expect(
      formatResearchTitleDisplay("东吴证券_医药生物行业点评报告_20260715.PDF", [
        "东吴证券",
      ]),
    ).toBe("医药生物行业点评报告");
    expect(
      formatResearchTitleDisplay("华鑫证券：公司动态研究报告", ["华鑫证券"]),
    ).toBe("公司动态研究报告");
  });

  it("keeps the title intact when the source does not prefix it or would empty it", () => {
    expect(
      formatResearchTitleDisplay("国债收益率曲线延续下行", ["东吴证券"]),
    ).toBe("国债收益率曲线延续下行");
    // 标题只剩来源名时不剥离，避免清空可见标题。
    expect(formatResearchTitleDisplay("东吴证券", ["东吴证券"])).toBe(
      "东吴证券",
    );
    // 来源是标题词的前缀子串（无边界分隔）时不误剥。
    expect(
      formatResearchTitleDisplay("东吴证券研究所季度展望", ["东吴证券"]),
    ).toBe("东吴证券研究所季度展望");
  });
});
