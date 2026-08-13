import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";

import { describe, expect, it } from "vitest";

import { stockAnalysisPageCssVars } from "../features/stock-analysis/lib/stockAnalysisTokens";
import { designTokens, dhApiTokens, ibTokens } from "../theme/designSystem";
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
const TOKENS_CSS_PATH = resolve(process.cwd(), "src/styles/tokens.css");
const WORKBENCH_SHELL_CSS_PATH = resolve(process.cwd(), "src/styles/workbenchShell.css");

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

/**
 * Nocturne 外壳收口的 scope 列表提取：收集 body 含指定声明片段的规则里
 * 出现的全部 data-moss-theme-scope 值（去重排序）。嵌套在 @media 里的
 * 规则同样能被逐条抓到（正则不跨花括号，外层壳被跳过）。
 */
function nocturneScopeSet(css: string, bodyMarker: string): string[] {
  const cleaned = stripCssComments(css);
  const scopes = new Set<string>();
  const ruleRe = /([^{}]+)\{([^{}]*)\}/g;
  let rule: RegExpExecArray | null;
  while ((rule = ruleRe.exec(cleaned)) !== null) {
    if (!rule[2].includes(bodyMarker)) continue;
    const scopeRe = /data-moss-theme-scope="([a-z0-9-]+)"/g;
    let scope: RegExpExecArray | null;
    while ((scope = scopeRe.exec(rule[1])) !== null) {
      scopes.add(scope[1]);
    }
  }
  return [...scopes].sort();
}

function extractRootCssBlock(css: string): string {
  const cleaned = stripCssComments(css);
  const match = cleaned.match(/:root\s*\{([\s\S]*?)\n\}/);
  return match?.[1] ?? cleaned;
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
  const globalCss = extractRootCssBlock(readCssWithLocalImports(GLOBAL_CSS_PATH));
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
  it("maps token fields to the route-scoped dark terminal palette", () => {
    const { token } = workbenchTheme;
    expect(workbenchTheme.algorithm).toBeDefined();
    expect(token).toBeDefined();
    expect(token?.colorPrimary).toBe(dhApiTokens.color.blue);
    expect(token?.colorSuccess).toBe(dhApiTokens.color.green);
    expect(token?.colorWarning).toBe(dhApiTokens.color.amber);
    expect(token?.colorError).toBe(dhApiTokens.color.red);
    expect(token?.colorText).toBe(dhApiTokens.color.ink);
    expect(token?.colorTextSecondary).toBe(dhApiTokens.color.inkSoft);
    expect(token?.colorBorder).toBe(dhApiTokens.color.line);
    expect(token?.colorBgBase).toBe(dhApiTokens.color.bg);
    expect(token?.colorBgContainer).toBe(dhApiTokens.color.panel);
    expect(token?.colorFillAlter).toBe(dhApiTokens.color.panel2);
    expect(token?.borderRadius).toBe(2);
  });

  it("defines Card and Layout overrides from the dark route tokens", () => {
    const { components } = workbenchTheme;
    expect(components?.Card?.borderRadiusLG).toBe(2);
    expect(components?.Card?.boxShadow).toBe("none");
    expect(components?.Layout?.bodyBg).toBe(dhApiTokens.color.bg);
    expect(components?.Layout?.siderBg).toBe(dhApiTokens.color.rail);
  });

  it("keeps table chrome on the dark route density and row tokens", () => {
    const { components } = workbenchTheme;
    expect(components?.Table?.headerBg).toBe(dhApiTokens.color.panel3);
    expect(components?.Table?.headerColor).toBe(dhApiTokens.color.inkSoft);
    expect(components?.Table?.rowHoverBg).toBe("rgba(114, 167, 220, 0.08)");
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
  const fullGlobalCss = readCssWithLocalImports(GLOBAL_CSS_PATH);
  const globalCss = extractRootCssBlock(fullGlobalCss);
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
    expect(fullGlobalCss).toContain(".moss-page-v2-shell");
    expect(fullGlobalCss).toContain(".moss-page-v2-surface");
    expect(fullGlobalCss).toContain(".moss-page-v2-decision-hero");
    expect(fullGlobalCss).toContain(".moss-page-v2-data-status");
    expect(fullGlobalCss).toContain(".moss-page-v2-kpi-band");
    expect(fullGlobalCss).toContain(".moss-page-v2-evidence-panel");
    expect(fullGlobalCss).toContain(".moss-page-v2-state-surface");
    expect(fullGlobalCss).toContain(".workbench-shell-grid--cockpit");
    expect(fullGlobalCss).not.toContain(".workbench-shell-grid--institutional-console");
    expect(fullGlobalCss).not.toContain("ag-theme-alpine");
    expect(fullGlobalCss).toContain(".dashboard-home-shell");
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
      expect(fullGlobalCss).not.toContain(selector);
      expect(workbenchDeferredChromeCss).toContain(selector);
    }
    expect(fullGlobalCss).toContain(".workbench-shell-grid--cockpit");
    expect(fullGlobalCss).toContain(".dashboard-home-shell");
  });

  it("keeps Nocturne shell override scope lists in parity across tokens/shell/deferred chrome", () => {
    const tokensCss = readFileSync(TOKENS_CSS_PATH, "utf8");
    const shellCss = readFileSync(WORKBENCH_SHELL_CSS_PATH, "utf8");

    const palette = nocturneScopeSet(tokensCss, "--nct-bg: #161826");
    const paper = nocturneScopeSet(tokensCss, "--moss-shell-paper-bg: var(--nct-bg)");
    const terminalVars = nocturneScopeSet(tokensCss, "--moss-shell-terminal-bg: var(--nct-rail)");
    const gridOverride = nocturneScopeSet(shellCss, "background: var(--nct-bg) !important");
    const railOverride = nocturneScopeSet(shellCss, "background: var(--nct-rail) !important");
    const railMarkOverride = nocturneScopeSet(shellCss, "background: var(--nct-surface) !important");
    const terminalOverride = nocturneScopeSet(
      workbenchDeferredChromeCss,
      "background: var(--nct-rail) !important",
    );

    // 主色板块（tokens.css）是唯一权威列表；收口层 grid/rail 必须同一份。
    expect(palette.length).toBeGreaterThanOrEqual(10);
    expect(gridOverride).toEqual(palette);
    expect(railOverride).toEqual(palette);
    // cockpit 壳（dashboard-home / portfolio-home）的 rail-mark 保持透明制度，不入收口列表。
    expect(railMarkOverride).toEqual(
      palette.filter((scope) => scope !== "dashboard-home" && scope !== "portfolio-home"),
    );
    // 首页 cockpit 壳不渲染主列纸面。
    expect(paper).toEqual(palette.filter((scope) => scope !== "dashboard-home"));
    // 渲染终端条的 scope：tokens.css 终端条块与延迟分册必须同一份列表。
    expect(terminalVars.length).toBeGreaterThan(0);
    expect(terminalOverride).toEqual(terminalVars);
  });

  it("keeps AG Grid theme aliases out of the eager global stylesheet", () => {
    const agGridCss = readFileSync(AG_GRID_INSTITUTIONAL_CSS_PATH, "utf8");

    expect(agGridCss).toContain(
      ".workbench-shell-grid--institutional-console :where(.ag-theme-alpine, .ag-theme-quartz)",
    );
    expect(agGridCss).toContain("--ag-background-color");
    expect(fullGlobalCss).not.toContain("ag-theme-alpine");
  });

  it("scopes a dark token remap to ThemedRouteBoundary owners", () => {
    expect(fullGlobalCss).toContain(".themed-route-boundary.theme-dh-api");
    expect(fullGlobalCss).toContain("--ib-paper: var(--dh-api-bg);");
    expect(fullGlobalCss).toContain("--moss-color-text-primary: var(--dh-api-ink);");
  });

  it("gives shell owners a dark AG Grid variable bridge for themed routes", () => {
    const agGridCss = readFileSync(AG_GRID_INSTITUTIONAL_CSS_PATH, "utf8");

    expect(agGridCss).toContain('.theme-dh-api :where(.ag-theme-alpine, .ag-theme-quartz)');
    expect(agGridCss).toContain("--ag-header-background-color: var(--dh-api-panel-3);");
    expect(agGridCss).toContain("--ag-foreground-color: var(--dh-api-ink);");
  });

  it("keeps dashboard-home compatibility styles rooted to known page owners", () => {
    expect(fullGlobalCss).toContain(
      ':where([data-testid="bond-analysis-overview"]).dashboard-home-shell',
    );
    expect(fullGlobalCss).toContain(
      ':where([data-testid="bond-analysis-overview"]) .dashboard-home-toolbar',
    );
    expect(fullGlobalCss).not.toMatch(/(^|[,{]\s*)\.dashboard-home-toolbar\b/m);
    expect(fullGlobalCss).not.toMatch(/(^|[,{]\s*)\.dashboard-action-ledger\b/m);
    expect(fullGlobalCss).not.toMatch(/\.workbench-shell-grid--cockpit\s+\.dashboard-home-shell\b/m);
    expect(fullGlobalCss).not.toContain("fixed-income-dashboard-page");
  });
});
