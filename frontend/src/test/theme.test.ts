import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import { stockAnalysisPageCssVars } from "../features/stock-analysis/lib/stockAnalysisTokens";
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

  it("defines homepage-aligned cockpit rail tokens for WorkbenchShell aside", () => {
    expect(shellTokens.railBg).toMatch(/^#[0-9a-f]{6}$/i);
    expect(shellTokens.railBg).toBe(designTokens.color.cockpit.navy950);
    expect(shellTokens.railBorder).toMatch(/^rgba\(/i);
    expect(shellTokens.railNavActiveBg).toBe("rgba(24, 80, 161, 0.24)");
    expect(shellTokens.railBrandText).toBe(designTokens.color.cockpit.blue50);
  });

  it("maps the shell to the homepage blue-gray design token palette via stable aliases", () => {
    expect(shellTokens.colorBgApp).toBe(designTokens.color.neutral[50]);
    expect(shellTokens.colorBgSurface).toBe("#ffffff");
    expect(shellTokens.colorBgCanvas).toBe("#ffffff");
    expect(shellTokens.colorTextPrimary).toBe(designTokens.color.neutral[900]);
    expect(shellTokens.colorTextSecondary).toBe(designTokens.color.neutral[600]);
    expect(shellTokens.colorTextMuted).toBe(designTokens.color.neutral[500]);
    expect(shellTokens.colorAccent).toBe(designTokens.color.primary[600]);
    expect(shellTokens.colorSuccess).toBe(designTokens.color.success[500]);
    expect(shellTokens.colorWarning).toBe(designTokens.color.warning[500]);
    expect(shellTokens.colorDanger).toBe(designTokens.color.danger[500]);
    expect(shellTokens.colorInfo).toBe(designTokens.color.info[500]);
    expect(shellTokens.colorBgMuted).toBe(designTokens.color.neutral[100]);
    expect(shellTokens.appBackdrop).toContain(designTokens.color.neutral[50]);
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

describe("stockAnalysisPageCssVars", () => {
  it("keeps warning surfaces on the design-system warning palette", () => {
    const vars = stockAnalysisPageCssVars as Record<string, string | number | undefined>;

    expect(vars["--sa-warning-fg"]).toBe(designTokens.color.warning[800]);
    expect(vars["--sa-warning-soft-bg"]).toBe(designTokens.color.warning[50]);
    expect(vars["--sa-warning-border"]).toBe(designTokens.color.warning[200]);
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
    expect(mossVars.get("moss-color-surface-base")).toBe("var(--moss-color-neutral-50)");
    expect(mossVars.get("moss-color-card-bg")).toBe("#ffffff");
    expect(mossVars.get("moss-color-link")).toBe("var(--moss-color-info-500)");
    expect(mossVars.get("moss-color-primary-rgb")).toBe("24, 80, 161");
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
    expect(mossVars.get("moss-color-card-bg")).toBe("#ffffff");
    expect(mossVars.get("moss-color-border-default")).toContain("var(--moss-color-neutral-200)");
    expect(mossVars.get("moss-color-text-primary")).toBe("var(--moss-color-neutral-900)");
    expect(mossVars.get("moss-color-text-secondary")).toBe("var(--moss-color-neutral-600)");
    expect(mossVars.get("moss-color-text-muted")).toBe("var(--moss-color-neutral-500)");
    expect(normalizeHex(mossVars.get("moss-color-warm-porcelain") ?? "")).toBe(
      normalizeHex(designTokens.color.warm.porcelain),
    );
  });

  it("points shell rail css aliases to the homepage navy rail contract", () => {
    expect(normalizeHex(mossVars.get("moss-shell-rail-bg") ?? "")).toBe(
      normalizeHex(designTokens.color.cockpit.navy950),
    );
    expect(mossVars.get("moss-shell-rail-text")).toBe("rgba(234, 242, 251, 0.82)");
    expect(mossVars.get("moss-shell-rail-active-bg")).toBe("rgba(24, 80, 161, 0.24)");
    expect(mossVars.get("moss-shell-rail-active-border")).toBe("rgba(96, 165, 250, 0.36)");
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
      ':where([data-testid="bond-analysis-overview"]).dashboard-home-shell',
    );
    expect(globalCss).toContain(
      ':where([data-testid="bond-analysis-overview"]) .dashboard-home-toolbar',
    );
    expect(globalCss).not.toMatch(/(^|[,{]\s*)\.dashboard-home-toolbar\b/m);
    expect(globalCss).not.toMatch(/(^|[,{]\s*)\.dashboard-action-ledger\b/m);
    expect(globalCss).not.toMatch(/\.workbench-shell-grid--cockpit\s+\.dashboard-home-shell\b/m);
    expect(globalCss).not.toContain("fixed-income-dashboard-page");
  });
});
