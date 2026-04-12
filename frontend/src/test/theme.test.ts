import { describe, expect, it } from "vitest";

import { shellTokens } from "../theme/tokens";
import { workbenchTheme } from "../theme/theme";

describe("shellTokens", () => {
  it("defines core semantic colors used by the shell", () => {
    expect(shellTokens.colorAccent).toMatch(/^#/);
    expect(shellTokens.colorSuccess).toMatch(/^#/);
    expect(shellTokens.colorDanger).toMatch(/^#/);
    expect(shellTokens.colorTextPrimary).toMatch(/^#/);
    expect(shellTokens.colorBorder).toMatch(/^#/);
    expect(shellTokens.colorBgApp).toMatch(/^#/);
  });
});

describe("workbenchTheme", () => {
  it("maps token fields to shellTokens", () => {
    const { token } = workbenchTheme;
    expect(token).toBeDefined();
    expect(token?.colorPrimary).toBe(shellTokens.colorAccent);
    expect(token?.colorSuccess).toBe(shellTokens.colorSuccess);
    expect(token?.colorWarning).toBe(shellTokens.colorWarning);
    expect(token?.colorError).toBe(shellTokens.colorDanger);
    expect(token?.colorText).toBe(shellTokens.colorTextPrimary);
    expect(token?.colorTextSecondary).toBe(shellTokens.colorTextSecondary);
    expect(token?.colorBorder).toBe(shellTokens.colorBorder);
    expect(token?.colorBgBase).toBe(shellTokens.colorBgSurface);
    expect(token?.colorBgContainer).toBe(shellTokens.colorBgSurface);
    expect(token?.colorFillAlter).toBe(shellTokens.colorBgMuted);
    expect(token?.borderRadius).toBe(shellTokens.radiusCard);
  });

  it("defines Card and Layout overrides from shellTokens", () => {
    const { components } = workbenchTheme;
    expect(components?.Card?.borderRadiusLG).toBe(shellTokens.radiusCard);
    expect(components?.Layout?.bodyBg).toBe(shellTokens.colorBgApp);
    expect(components?.Layout?.siderBg).toBe(shellTokens.colorBgSurface);
  });
});
