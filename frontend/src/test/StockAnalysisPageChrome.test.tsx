import { describe, expect, it } from "vitest";

import {
  SA_CARD_TITLE,
  SA_FIRST_CARD,
  SA_PILL,
  SA_SECTION_DESC,
  SA_SECTION_EYEBROW,
  SA_SECTION_HEAD,
  SA_SHELL_NUM,
  SA_SHELL_PAGE,
} from "../features/stock-analysis/lib/stockAnalysisPageChrome";

describe("stockAnalysisPageChrome", () => {
  it("exports the shell classes consumed by the page and its components", () => {
    expect(SA_SHELL_PAGE.length).toBeGreaterThan(0);
    expect(SA_SHELL_NUM.length).toBeGreaterThan(0);
    expect(SA_FIRST_CARD).toContain("stock-analysis-page__dh-panel");
    expect(SA_FIRST_CARD).toContain("stock-analysis-page__dh-card");
    expect(SA_CARD_TITLE).toBe("m-0");
    expect(SA_SECTION_HEAD).toContain("stock-analysis-page__dh-section-head");
    expect(SA_SECTION_DESC).toContain("stock-analysis-page__dh-section-desc");
    expect(SA_SECTION_EYEBROW).toContain("stock-analysis-page__dh-section-eyebrow");
    expect(SA_PILL).toContain("stock-analysis-page__dh-pill");
  });
});
