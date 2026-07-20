import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";

import { describe, expect, it } from "vitest";

import { stockAnalysisPageCssVars } from "../features/stock-analysis/lib/stockAnalysisTokens";
import { designTokens, ibTokens } from "../theme/designSystem";
import { shellTokens } from "../theme/tokens";
import { workbenchTheme } from "../theme/theme";

const GLOBAL_CSS_PATH = resolve(process.cwd(), "src/styles/global.css");
const WORKBENCH_INSTITUTIONAL_CONSOLE_CSS_PATH = resolve(
  process.cwd(),
  "src/styles/workbenchInstitutionalConsole.css",
);
const WORKBENCH_DEFERRED_CHROME_CSS_PATH = resolve(
  process.cwd(),
  "src/styles/workbenchDeferredChrome.css",
);
const AG_GRID_INSTITUTIONAL_CSS_PATH = resolve(
  process.cwd(),
  "src/styles/agGridInstitutional.css",
);

function readCssWithLocalImports(filePath: string, seen = new Set<string>()): string {
  if (seen.has(filePath)) {
    throw new Error(`Circular CSS import detected for ${filePath}`);
  }
  seen.add(filePath);

  return readFileSync(filePath, "utf8").replace(
    /^@import "\.\/([^"]+)";\r?\n?/gm,
    (_match, importPath: string) =>
      readCssWithLocalImports(resolve(dirname(filePath), importPath), seen),
  );
}

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

/** Extract --ib-* declarations; values trimmed, internal whitespace collapsed for comparison. */
function parseIbCssVars(css: string): Map<string, string> {
  const map = new Map<string, string>();
  const cleaned = stripCssComments(css);
  const re = /--(ib-[a-z0-9-]+)\s*:\s*([\s\S]*?);/g;
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

describe("ibTokens", () => {
  const globalCss = readCssWithLocalImports(GLOBAL_CSS_PATH);
  const ibVars = parseIbCssVars(globalCss);

  it("exposes core IB light restyle variables aligned with ibTokens", () => {
    expect(normalizeHex(ibVars.get("ib-paper") ?? "")).toBe(normalizeHex(ibTokens.color.paper));
    expect(normalizeHex(ibVars.get("ib-ink") ?? "")).toBe(normalizeHex(ibTokens.color.ink));
    expect(normalizeHex(ibVars.get("ib-accent") ?? "")).toBe(normalizeHex(ibTokens.color.accent));
    expect(normalizeHex(ibVars.get("ib-hairline") ?? "")).toBe(normalizeHex(ibTokens.color.hairline));
    expect(normalizeHex(ibVars.get("ib-gold") ?? "")).toBe(normalizeHex(ibTokens.color.gold));
    expect(normalizeHex(ibVars.get("ib-rail-bg") ?? "")).toBe(normalizeHex(ibTokens.color.railBg));
    expect(ibVars.get("ib-radius")).toBe(`${ibTokens.radius}px`);
    expect(ibVars.get("ib-shadow")).toBe(ibTokens.shadow);
  });
});

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
    expect(shellTokens.railBg).toBe("#10161f");
    expect(shellTokens.railBorder).toMatch(/^#/i);
    expect(shellTokens.railNavActiveBg).toBe("#1a2230");
    expect(shellTokens.railBrandText).toBe("#f5f6f8");
  });

  it("maps the shell to the IB light restyle palette via stable aliases", () => {
    expect(shellTokens.colorBgApp).toBe("#f4f3f0");
    expect(shellTokens.colorBgSurface).toBe("#ffffff");
    expect(shellTokens.colorBgCanvas).toBe("#ffffff");
    expect(shellTokens.colorTextPrimary).toBe("#16191d");
    expect(shellTokens.colorTextSecondary).toBe("#5c6370");
    expect(shellTokens.colorTextMuted).toBe("#8a8f98");
    expect(shellTokens.colorAccent).toBe("#14366b");
    expect(shellTokens.colorSuccess).toBe("#1f7a4d");
    expect(shellTokens.colorWarning).toBe(designTokens.color.warning[500]);
    expect(shellTokens.colorDanger).toBe("#b42318");
    expect(shellTokens.colorInfo).toBe(designTokens.color.info[500]);
    expect(shellTokens.colorBgMuted).toBe("#f7f6f3");
    expect(shellTokens.appBackdrop).toBe("#f4f3f0");
  });

  it("defines placeholder readiness badge colors for shell badges", () => {
    expect(shellTokens.readinessBadgePlaceholderBg).toBe("transparent");
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
    expect(token?.borderRadius).toBe(2);
  });

  it("defines Card and Layout overrides from shellTokens", () => {
    const { components } = workbenchTheme;
    expect(components?.Card?.borderRadiusLG).toBe(2);
    expect(components?.Card?.boxShadow).toBe("none");
    expect(components?.Layout?.bodyBg).toBe(shellTokens.colorBgApp);
    expect(components?.Layout?.siderBg).toBe(shellTokens.railBg);
  });

  it("keeps table chrome on institutional density and row tokens", () => {
    const { components } = workbenchTheme;
    expect(components?.Table?.headerBg).toBe(shellTokens.colorBgMuted);
    expect(components?.Table?.headerColor).toBe(designTokens.color.institutional.textMuted);
    expect(components?.Table?.rowHoverBg).toBe(designTokens.color.institutional.rowHover);
  });
});

describe("stockAnalysisPageCssVars", () => {
  it("maps warning surfaces to the Decision Desk amber palette", () => {
    const vars = stockAnalysisPageCssVars as Record<string, string | number | undefined>;

    expect(vars["--sa-warning-fg"]).toBe("var(--dh-api-amber)");
    expect(vars["--sa-warning-soft-bg"]).toBe("var(--dh-api-amber-soft)");
    expect(vars["--sa-warning-border"]).toBe("var(--dh-api-line)");
  });
});

describe("globalCss design token bridge (:root)", () => {
  const globalCss = readCssWithLocalImports(GLOBAL_CSS_PATH);
  const workbenchInstitutionalConsoleCss = readFileSync(
    WORKBENCH_INSTITUTIONAL_CONSOLE_CSS_PATH,
    "utf8",
  );
  const workbenchDeferredChromeCss = readFileSync(WORKBENCH_DEFERRED_CHROME_CSS_PATH, "utf8");
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
    expect(mossVars.get("moss-color-surface-base")).toBe("var(--moss-institutional-bg)");
    expect(mossVars.get("moss-color-card-bg")).toBe(
      "var(--moss-institutional-surface-raised)",
    );
    expect(mossVars.get("moss-color-link")).toBe("var(--moss-color-info-500)");
    expect(mossVars.get("moss-color-primary-rgb")).toBe("20, 54, 107");
  });

  it("exposes institutional console aliases for the investment-bank shell pass", () => {
    expect(mossVars.get("moss-institutional-bg")).toBe("var(--ib-paper)");
    expect(mossVars.get("moss-institutional-surface")).toBe("var(--ib-surface)");
    expect(mossVars.get("moss-institutional-border")).toBe("var(--ib-hairline)");
    expect(mossVars.get("moss-institutional-row-stripe")).toBe("var(--ib-surface-muted)");
    expect(mossVars.get("moss-institutional-row-hover")).toBe("var(--ib-surface-muted)");
    expect(mossVars.get("moss-institutional-focus-ring")).toBe(
      "rgba(20, 54, 107, 0.28)",
    );
    expect(mossVars.get("moss-institutional-rail-bg")).toBe("var(--ib-rail-bg)");
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
    expect(mossVars.get("moss-color-surface-base")).toBe("var(--moss-institutional-bg)");
    expect(mossVars.get("moss-color-card-bg")).toBe(
      "var(--moss-institutional-surface-raised)",
    );
    expect(mossVars.get("moss-color-border-default")).toBe("var(--moss-institutional-border)");
    expect(mossVars.get("moss-color-text-primary")).toBe("var(--moss-color-neutral-900)");
    expect(mossVars.get("moss-color-text-secondary")).toBe("var(--moss-color-neutral-600)");
    expect(mossVars.get("moss-color-text-muted")).toBe("var(--moss-color-neutral-500)");
    expect(normalizeHex(mossVars.get("moss-color-warm-porcelain") ?? "")).toBe(
      normalizeHex(designTokens.color.warm.porcelain),
    );
  });

  it("points shell rail css aliases to the IB light rail contract", () => {
    expect(mossVars.get("moss-shell-rail-bg")).toBe("var(--ib-rail-bg)");
    expect(mossVars.get("moss-institutional-rail-bg")).toBe("var(--ib-rail-bg)");
    expect(mossVars.get("moss-shell-rail-text")).toBe("var(--ib-rail-text)");
    expect(mossVars.get("moss-shell-rail-active-bg")).toBe("var(--ib-rail-active-bg)");
    expect(mossVars.get("moss-shell-rail-active-border")).toBe("var(--ib-rail-active-bar)");
  });

  it("keeps Page V2 and cockpit shell class hooks in the eager global stylesheet", () => {
    expect(globalCss).toContain(".moss-page-v2-shell");
    expect(globalCss).toContain(".moss-page-v2-surface");
    expect(globalCss).toContain(".moss-page-v2-decision-hero");
    expect(globalCss).toContain(".moss-page-v2-data-status");
    expect(globalCss).toContain(".moss-page-v2-kpi-band");
    expect(globalCss).toContain(".moss-page-v2-evidence-panel");
    expect(globalCss).toContain(".moss-page-v2-state-surface");
    expect(globalCss).toContain(".workbench-shell-grid--cockpit");
    expect(globalCss).not.toContain(".workbench-shell-grid--institutional-console");
    expect(globalCss).not.toContain("ag-theme-alpine");
    expect(globalCss).toContain(".dashboard-home-shell");
  });

  it("keeps institutional console skin in the deferred stylesheet", () => {
    expect(workbenchInstitutionalConsoleCss).toContain(
      ".workbench-shell-grid--institutional-console",
    );
    expect(workbenchInstitutionalConsoleCss).toContain(
      ".workbench-shell-grid--institutional-console :where(.ant-table-wrapper)",
    );
    expect(workbenchInstitutionalConsoleCss).not.toContain("ag-theme-alpine");
  });

  it("keeps the shared shell wired to load institutional console skin only for scoped routes", () => {
    const shellSource = readFileSync(
      resolve(process.cwd(), "src/layouts/WorkbenchShell.tsx"),
      "utf8",
    );
    const scopedRouteSources = [
      "src/features/cross-asset/pages/CrossAssetDriversPage.tsx",
      "src/features/ledger-pnl/pages/LedgerPnlPage.tsx",
      "src/features/product-category-pnl/pages/ProductCategoryPnlPage.tsx",
      "src/features/pnl-attribution/components/PnlAttributionView.tsx",
    ].map((filePath) => readFileSync(resolve(process.cwd(), filePath), "utf8"));

    expect(shellSource).toContain("institutionalConsoleShellSectionKeys");
    expect(shellSource).toContain("useInstitutionalConsoleCss");
    expect(shellSource).toContain('import("../styles/workbenchInstitutionalConsole.css")');
    expect(shellSource).toContain('import("../styles/workbenchDeferredChrome.css")');
    expect(shellSource).toContain('currentSection.key !== "dashboard"');
    expect(shellSource).not.toContain('currentSection.key !== "dashboard";\n  useInstitutionalConsoleCss');
    expect(shellSource).not.toContain("requestIdleCallback");
    expect(shellSource).not.toContain("cancelIdleCallback");
    for (const routeSource of scopedRouteSources) {
      expect(routeSource).not.toContain("workbenchInstitutionalConsole.css");
      expect(routeSource).not.toContain("workbenchDeferredChrome.css");
    }
  });

  it("keeps non-home workbench chrome out of the eager global stylesheet", () => {
    const deferredSelectors = [
      ".workbench-terminal-bar {",
      ".workbench-terminal-bar-split {",
      ".workbench-workspace-hero {",
      ".portfolio-workbench-light-hint {",
      ".workbench-shell-status-summary {",
      ".workbench-shell-status-meta {",
      ".portfolio-workbench-board {",
      ".workbench-section-subnav {",
      ".workbench-notice {",
      ".portfolio-workbench-lead {",
      ".portfolio-workbench-flow {",
    ];

    for (const selector of deferredSelectors) {
      expect(globalCss).not.toContain(selector);
      expect(workbenchDeferredChromeCss).toContain(selector);
    }
    expect(globalCss).toContain(".workbench-shell-grid--cockpit");
    expect(globalCss).toContain(".dashboard-home-shell");
  });

  it("keeps AG Grid theme aliases out of the eager global stylesheet", () => {
    const agGridCss = readFileSync(AG_GRID_INSTITUTIONAL_CSS_PATH, "utf8");

    expect(agGridCss).toContain(
      ".workbench-shell-grid--institutional-console :where(.ag-theme-alpine, .ag-theme-quartz)",
    );
    expect(agGridCss).toContain("--ag-background-color");
    expect(globalCss).not.toContain("ag-theme-alpine");
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
