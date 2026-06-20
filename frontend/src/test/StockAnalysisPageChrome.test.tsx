import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import {
  DECISION_GRID_ICONS,
  FIRST_SCREEN_ICONS,
  SA_CARD_TITLE,
  SA_FIRST_CARD,
  SA_FIRST_HERO,
  SA_SECTION_DESC,
  SA_SECTION_EYEBROW,
  SA_SECTION_HEAD,
  SA_SHELL_LAYOUT,
  SA_SHELL_PAGE,
  SECTION_HEAD_ICONS,
} from "../features/stock-analysis/lib/stockAnalysisPageChrome";

describe("stockAnalysisPageChrome", () => {
  it("exports dashboard-home shell class names", () => {
    expect(SA_SHELL_PAGE.length).toBeGreaterThan(0);
    expect(SA_SHELL_LAYOUT.length).toBeGreaterThan(0);
    expect(SA_FIRST_CARD).toContain("stock-analysis-page__dh-panel");
    expect(SA_FIRST_CARD).toContain("stock-analysis-page__dh-card");
    expect(SA_FIRST_HERO).toContain("stock-analysis-page__dh-hero");
    expect(SA_CARD_TITLE).toBe("m-0");
    expect(SA_SECTION_HEAD).toContain("stock-analysis-page__dh-section-head");
    expect(SA_SECTION_DESC).toContain("stock-analysis-page__dh-section-desc");
    expect(SA_SECTION_EYEBROW).toContain("stock-analysis-page__dh-section-eyebrow");
  });

  it("exports the expected icon sets for first-screen, decision, and section headings", () => {
    expect(FIRST_SCREEN_ICONS).toHaveLength(4);
    expect(DECISION_GRID_ICONS).toHaveLength(4);
    expect(SECTION_HEAD_ICONS).toHaveLength(3);

    const { container } = render(<>{FIRST_SCREEN_ICONS[0]}</>);
    expect(container.querySelector(".anticon-bar-chart")).toBeInTheDocument();
  });
});
