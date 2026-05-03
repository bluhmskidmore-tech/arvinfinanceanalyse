import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import { designTokens } from "../theme/designSystem";
import { shellTokens } from "../theme/tokens";
import { workbenchTheme } from "../theme/theme";

const GLOBAL_CSS_PATH = resolve(process.cwd(), "src/styles/global.css");

function stripCssComments(source: string): string {
  return source.replace(/\/\*[\s\S]*?\*\//g, "");
}

/** Extract --moss-* declarations; values trimmed, internal whitespace collapsed for comparison. */
function parseMossCssVars(css: string): Map<string, string> {
  const map = new Map<string, string>();
  const cleaned = stripCssComments(css);
  const re = /--(moss-[a-z0-9-]+)\s*:\s*([\s\S]*?);/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(cleaned)) !== null) {
    const key = m[1];
    const raw = m[2].replace(/\s+/g, " ").trim();
    map.set(key, raw);
  }
  return map;
}

function normalizeHex(value: string): string {
  return value.trim().toLowerCase();
}

describe("shellTokens", () => {
  it("defines core semantic colors used by the shell", () => {
    expect(shellTokens.colorAccent).toMatch(/^#/);
    expect(shellTokens.colorSuccess).toMatch(/^#/);
    expect(shellTokens.colorDanger).toMatch(/^#/);
    expect(shellTokens.colorTextPrimary).toMatch(/^#/);
    expect(shellTokens.colorBorder).toMatch(/^#/);
    expect(shellTokens.colorBgApp).toMatch(/^#/);
  });

  it("defines dark workbench rail tokens for WorkbenchShell aside", () => {
    expect(shellTokens.railBg).toMatch(/^#[0-9a-f]{6}$/i);
    expect(shellTokens.railBg.toLowerCase()).toBe("#121d2a");
    expect(shellTokens.railBorder).toMatch(/^rgba\(/i);
    expect(shellTokens.railNavActiveBg).toMatch(/^rgba\(/i);
  });

  it("defines placeholder readiness badge colors for shell badges", () => {
    expect(shellTokens.readinessBadgePlaceholderBg).toMatch(/^#/);
    expect(shellTokens.readinessBadgePlaceholderFg).toMatch(/^#/);
    expect(shellTokens.readinessBadgePlaceholderBorder).toMatch(/^#/);
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

describe("globalCss design token bridge (:root)", () => {
  const globalCss = readFileSync(GLOBAL_CSS_PATH, "utf8");
  const mossVars = parseMossCssVars(globalCss);

  it("exposes primitives aligned with designTokens (sample)", () => {
    expect(normalizeHex(mossVars.get("moss-color-primary-600") ?? "")).toBe(
      normalizeHex(designTokens.color.primary[600]),
    );
    expect(normalizeHex(mossVars.get("moss-color-success-500") ?? "")).toBe(
      normalizeHex(designTokens.color.success[500]),
    );
    expect(normalizeHex(mossVars.get("moss-color-neutral-900") ?? "")).toBe(
      normalizeHex(designTokens.color.neutral[900]),
    );
    expect(mossVars.get("moss-space-4")).toBe(`${designTokens.space[4]}px`);
    expect(mossVars.get("moss-radius-md")).toBe(`${designTokens.radius.md}px`);
    expect(mossVars.get("moss-shadow-card")).toBe(designTokens.shadow.card);
    expect(mossVars.get("moss-shadow-panel")).toBe(designTokens.shadow.panel);
  });

  it("maps monospace stack to designTokens.fontFamily.tabular", () => {
    const cssMono = mossVars.get("moss-font-mono") ?? "";
    const tokenMono = designTokens.fontFamily.tabular.replace(/\s+/g, " ").trim();
    expect(cssMono.replace(/\s+/g, " ").trim()).toBe(tokenMono);
  });

  it("exposes motion duration and easing from designTokens.motion", () => {
    expect(mossVars.get("moss-motion-duration-fast")).toBe(`${designTokens.motion.durationFast}ms`);
    expect(mossVars.get("moss-motion-duration-base")).toBe(`${designTokens.motion.durationBase}ms`);
    expect(mossVars.get("moss-motion-ease-out")).toBe(String(designTokens.motion.easeOut));
  });

  it("exposes semantic surface / card / border / text helpers", () => {
    expect(mossVars.get("moss-color-surface-base")).toBe("var(--moss-color-neutral-50)");
    expect(mossVars.get("moss-color-card-bg")).toBe("var(--moss-color-neutral-50)");
    expect(mossVars.get("moss-color-border-default")).toBe("var(--moss-color-neutral-300)");
    expect(mossVars.get("moss-color-text-primary")).toBe("var(--moss-color-neutral-900)");
    expect(normalizeHex(mossVars.get("moss-color-neutral-50") ?? "")).toBe(
      normalizeHex(designTokens.color.neutral[50]),
    );
  });
});
