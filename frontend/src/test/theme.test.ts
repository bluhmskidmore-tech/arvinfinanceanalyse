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

  it("defines cockpit rail tokens for WorkbenchShell aside", () => {
    expect(shellTokens.railBg).toMatch(/^#[0-9a-f]{6}$/i);
    expect(shellTokens.railBg).toBe(designTokens.color.warm.rail);
    expect(shellTokens.railBorder).toMatch(/^rgba\(/i);
    expect(shellTokens.railNavActiveBg).toMatch(/^rgba\(/i);
    expect(shellTokens.railBrandText).toBe(designTokens.color.warm.ink);
  });

  it("maps the shell to the shared design token palette via stable aliases", () => {
    expect(shellTokens.colorBgApp).toBe(designTokens.color.warm.porcelain);
    expect(shellTokens.colorBgSurface).toBe(designTokens.color.warm.paper);
    expect(shellTokens.colorTextPrimary).toBe(designTokens.color.warm.charcoal);
    expect(shellTokens.colorAccent).toBe(designTokens.color.warm.terracotta);
    expect(shellTokens.colorSuccess).toBe(designTokens.color.warm.sage);
    expect(shellTokens.colorDanger).toBe(designTokens.color.warm.burgundy);
    expect(shellTokens.colorInfo).toBe(designTokens.color.warm.slateBlue);
    expect(shellTokens.colorBgMuted).toBe("#f0e7db");
    expect(shellTokens.appBackdrop).toContain(designTokens.color.warm.porcelain);
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
    expect(token?.colorBgBase).toBe(shellTokens.colorBgApp);
    expect(token?.colorBgContainer).toBe(shellTokens.colorBgSurface);
    expect(token?.colorFillAlter).toBe(shellTokens.colorBgMuted);
    expect(token?.borderRadius).toBe(shellTokens.radiusCard);
  });

  it("defines Card and Layout overrides from shellTokens", () => {
    const { components } = workbenchTheme;
    expect(components?.Card?.borderRadiusLG).toBe(shellTokens.radiusCard);
    expect(components?.Layout?.bodyBg).toBe(shellTokens.colorBgApp);
    expect(components?.Layout?.siderBg).toBe(shellTokens.railBg);
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
    expect(normalizeHex(mossVars.get("moss-color-warm-porcelain") ?? "")).toBe(
      normalizeHex(designTokens.color.warm.porcelain),
    );
    expect(normalizeHex(mossVars.get("moss-color-warm-charcoal") ?? "")).toBe(
      normalizeHex(designTokens.color.warm.charcoal),
    );
    expect(mossVars.get("moss-space-4")).toBe(`${designTokens.space[4]}px`);
    expect(mossVars.get("moss-radius-md")).toBe(`${designTokens.radius.md}px`);
    expect(mossVars.get("moss-shadow-card")).toBe(shellTokens.shadowCard);
    expect(mossVars.get("moss-shadow-panel")).toBe(shellTokens.shadowPanel);
  });

  it("exposes shared semantic helpers used by the cockpit shell", () => {
    expect(mossVars.get("moss-color-surface-base")).toBe("var(--moss-color-warm-porcelain)");
    expect(mossVars.get("moss-color-card-bg")).toBe("var(--moss-color-warm-paper)");
    expect(mossVars.get("moss-color-link")).toBe("var(--moss-color-warm-slate-blue)");
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
    expect(mossVars.get("moss-color-surface-base")).toBe("var(--moss-color-warm-porcelain)");
    expect(mossVars.get("moss-color-card-bg")).toBe("var(--moss-color-warm-paper)");
    expect(mossVars.get("moss-color-border-default")).toContain("var(--moss-color-warm-stone)");
    expect(mossVars.get("moss-color-text-primary")).toBe("var(--moss-color-warm-charcoal)");
    expect(normalizeHex(mossVars.get("moss-color-warm-porcelain") ?? "")).toBe(
      normalizeHex(designTokens.color.warm.porcelain),
    );
  });

  it("points shell rail css aliases to the light warm rail contract", () => {
    expect(mossVars.get("moss-shell-rail-bg")).toBe("var(--moss-color-warm-rail)");
    expect(mossVars.get("moss-shell-rail-text")).toBe("rgba(47, 40, 36, 0.76)");
    expect(mossVars.get("moss-shell-rail-active-bg")).toBe("rgba(184, 92, 56, 0.12)");
    expect(mossVars.get("moss-shell-rail-active-border")).toBe("rgba(184, 92, 56, 0.24)");
  });

  it("keeps Page V2 and cockpit shell class hooks in the global stylesheet", () => {
    expect(globalCss).toContain(".moss-page-v2-shell");
    expect(globalCss).toContain(".moss-page-v2-surface");
    expect(globalCss).toContain(".moss-page-v2-decision-hero");
    expect(globalCss).toContain(".moss-page-v2-data-status");
    expect(globalCss).toContain(".moss-page-v2-kpi-band");
    expect(globalCss).toContain(".moss-page-v2-evidence-panel");
    expect(globalCss).toContain(".moss-page-v2-state-surface");
    expect(globalCss).toContain(".workbench-shell-grid--cockpit");
    expect(globalCss).toContain(".dashboard-home-shell");
  });

  it("keeps dashboard-home compatibility styles rooted to known page owners", () => {
    expect(globalCss).toContain(
      ':where([data-testid="fixed-income-dashboard-page"], [data-testid="bond-analysis-overview"]).dashboard-home-shell',
    );
    expect(globalCss).toContain(
      ':where([data-testid="fixed-income-dashboard-page"], [data-testid="bond-analysis-overview"]) .dashboard-home-toolbar',
    );
    expect(globalCss).toContain(
      '[data-testid="fixed-income-dashboard-page"] .dashboard-action-ledger',
    );
    expect(globalCss).not.toMatch(/(^|[,{]\s*)\.dashboard-home-toolbar\b/m);
    expect(globalCss).not.toMatch(/(^|[,{]\s*)\.dashboard-action-ledger\b/m);
    expect(globalCss).not.toMatch(/\.workbench-shell-grid--cockpit\s+\.dashboard-home-shell\b/m);
  });
});
