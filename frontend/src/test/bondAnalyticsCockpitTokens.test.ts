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
import { designTokens } from "../theme/designSystem";

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
    expect(toneColor("success").color).toBe(designTokens.color.success[800]);
    expect(toneColor("warning").color).toBe(designTokens.color.warning[800]);
    expect(toneColor("danger").color).toBe(designTokens.color.danger[800]);
    expect(toneColor("neutral").color).toBe(designTokens.color.neutral[700]);
  });

  it("readinessTagColor maps status labels to ant tag colors", () => {
    expect(readinessTagColor("eligible")).toBe("success");
    expect(readinessTagColor("request-error")).toBe("error");
    expect(readinessTagColor("placeholder-blocked")).toBe("warning");
    expect(readinessTagColor("warning")).toBe("warning");
    expect(readinessTagColor("unknown-status")).toBe("default");
  });

  it("readinessSurface maps status labels to surface tokens", () => {
    expect(readinessSurface("eligible").accent).toBe(designTokens.color.success[500]);
    expect(readinessSurface("request-error").accent).toBe(designTokens.color.danger[600]);
    expect(readinessSurface("placeholder-blocked").accent).toBe(designTokens.color.warning[600]);
    expect(readinessSurface("warning").text).toBe(designTokens.color.warning[800]);
    expect(readinessSurface("default").borderColor).toBe(designTokens.color.neutral[200]);
  });

  it("promotionLabel maps destinations to stable Chinese labels", () => {
    expect(promotionLabel("headline")).toBe("可进入头条");
    expect(promotionLabel("main-rail")).toBe("可进入主栏");
    expect(promotionLabel("readiness-only")).toBe("仅就绪/下钻");
  });
});
