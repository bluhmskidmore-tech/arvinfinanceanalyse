import { describe, expect, it } from "vitest";

import {
  PERIOD_OPTIONS,
  SHADOW,
  panelStyle,
  promotionLabel,
  readinessStatusLabel,
  readinessSurface,
  readinessTagColor,
  toneColor,
} from "../features/bond-analytics/components/bondAnalyticsCockpitTokens";
import { dhApiTokens } from "../theme/designSystem";

describe("bondAnalyticsCockpitTokens", () => {
  it("orders PERIOD_OPTIONS as MoM, YTD, TTM", () => {
    expect(PERIOD_OPTIONS.map((o) => o.value)).toEqual(["MoM", "YTD", "TTM"]);
  });

  it("panelStyle passes background, no border stroke, radius, shadow", () => {
    const bg = "#fafafa";
    const style = panelStyle(bg);
    expect(style.borderRadius).toBe(dhApiTokens.radius);
    expect(style.border).toBe("none");
    expect(style.boxShadow).toBe(SHADOW);
    expect(style.background).toBe(bg);
  });

  it("toneColor covers success, warning, danger, and default neutral", () => {
    // Nocturne 换肤（2026-08-13）：tone 面走 --dh-api-* 语义链（DOM style 消费）。
    expect(toneColor("success").color).toBe("var(--dh-api-green)");
    expect(toneColor("warning").color).toBe("var(--dh-api-amber)");
    expect(toneColor("danger").color).toBe("var(--dh-api-red)");
    expect(toneColor("neutral").color).toBe("var(--dh-api-soft)");
    expect(toneColor("neutral").background).toBe("var(--dh-api-panel-2)");
    expect(toneColor("success").background).toBe(
      "color-mix(in srgb, var(--dh-api-green) 12%, var(--dh-api-panel))",
    );
  });

  it("readinessTagColor maps status labels to ant tag colors", () => {
    expect(readinessTagColor("eligible")).toBe("success");
    expect(readinessTagColor("request-error")).toBe("error");
    expect(readinessTagColor("placeholder-blocked")).toBe("warning");
    expect(readinessTagColor("warning")).toBe("warning");
    expect(readinessTagColor("unknown-status")).toBe("default");
  });

  it("readinessStatusLabel keeps request errors as controlled user-facing copy", () => {
    expect(readinessStatusLabel("request-error")).toBe("暂不可用");
  });

  it("readinessSurface maps status labels to surface tokens", () => {
    // Nocturne 换肤（2026-08-13）：就绪面与 toneColor 同走 --dh-api-* 语义链。
    expect(readinessSurface("eligible").accent).toBe("var(--dh-api-green)");
    expect(readinessSurface("request-error").accent).toBe("var(--dh-api-red)");
    expect(readinessSurface("placeholder-blocked").accent).toBe("var(--dh-api-amber)");
    expect(readinessSurface("warning").text).toBe("var(--dh-api-amber)");
    expect(readinessSurface("default").borderColor).toBe("var(--dh-api-line-soft)");
  });

  it("promotionLabel maps destinations to stable Chinese labels", () => {
    expect(promotionLabel("headline")).toBe("可进入头条");
    expect(promotionLabel("main-rail")).toBe("可进入主栏");
    expect(promotionLabel("readiness-only")).toBe("仅就绪/下钻");
  });
});
