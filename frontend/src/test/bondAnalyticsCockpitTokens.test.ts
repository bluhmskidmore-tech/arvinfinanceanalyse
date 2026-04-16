import { describe, expect, it } from "vitest";

import {
  BORDER,
  PERIOD_OPTIONS,
  SHADOW,
  panelStyle,
  promotionLabel,
  readinessSurface,
  readinessTagColor,
  toneColor,
} from "../features/bond-analytics/components/bondAnalyticsCockpitTokens";

describe("bondAnalyticsCockpitTokens", () => {
  it("orders PERIOD_OPTIONS as MoM, YTD, TTM", () => {
    expect(PERIOD_OPTIONS.map((o) => o.value)).toEqual(["MoM", "YTD", "TTM"]);
  });

  it("panelStyle passes background and fixed border, radius, shadow", () => {
    const bg = "#fafafa";
    const style = panelStyle(bg);
    expect(style.borderRadius).toBe(24);
    expect(style.borderColor).toBe(BORDER);
    expect(style.boxShadow).toBe(SHADOW);
    expect(style.background).toBe(bg);
  });

  it("toneColor covers success, warning, danger, and default neutral", () => {
    expect(toneColor("success").color).toBe("#25724d");
    expect(toneColor("warning").color).toBe("#9f5b0b");
    expect(toneColor("danger").color).toBe("#a9342f");
    expect(toneColor("neutral").color).toBe("#48627d");
  });

  it("readinessTagColor maps status labels to ant tag colors", () => {
    expect(readinessTagColor("eligible")).toBe("success");
    expect(readinessTagColor("request-error")).toBe("error");
    expect(readinessTagColor("placeholder-blocked")).toBe("warning");
    expect(readinessTagColor("warning")).toBe("warning");
    expect(readinessTagColor("unknown-status")).toBe("default");
  });

  it("readinessSurface maps status labels to surface tokens", () => {
    expect(readinessSurface("eligible").accent).toBe("#2f8f63");
    expect(readinessSurface("request-error").accent).toBe("#b42318");
    expect(readinessSurface("placeholder-blocked").accent).toBe("#b86a16");
    expect(readinessSurface("warning").text).toBe("#815014");
    expect(readinessSurface("default").borderColor).toBe("#dde6f0");
  });

  it("promotionLabel maps destinations to stable English labels", () => {
    expect(promotionLabel("headline")).toBe("Headline eligible");
    expect(promotionLabel("main-rail")).toBe("Main rail eligible");
    expect(promotionLabel("readiness-only")).toBe("Readiness / drill only");
  });
});
