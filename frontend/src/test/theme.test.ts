import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";

import { describe, expect, it } from "vitest";

import { workbenchNavigation } from "../app/navigation";
import { stockAnalysisPageCssVars } from "../features/stock-analysis/lib/stockAnalysisTokens";
import {
  COCKPIT_SHELL_SECTION_KEYS,
  SECTION_SUBNAV_EXCLUDED_SECTION_KEYS,
  TERMINAL_BAR_EXCLUDED_SECTION_KEYS,
} from "../layouts/workbenchShellSections";
import { designTokens, ibTokens, nocturneTokens } from "../theme/designSystem";
import { NOCTURNE_THEME_SCOPES } from "../theme/themeScopes";
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
 * selectorMarker 用于 body 声明相同的两组规则（rail-mark 与 page-v2
 * 背景压制同为 `background: var(--nct-surface) !important`）按选择器区分。
 */
function nocturneScopeSet(css: string, bodyMarker: string, selectorMarker?: string): string[] {
  const cleaned = stripCssComments(css);
  const scopes = new Set<string>();
  const ruleRe = /([^{}]+)\{([^{}]*)\}/g;
  let rule: RegExpExecArray | null;
  while ((rule = ruleRe.exec(cleaned)) !== null) {
    if (!rule[2].includes(bodyMarker)) continue;
    if (selectorMarker && !rule[1].includes(selectorMarker)) continue;
    const scopeRe = /data-moss-theme-scope="([a-z0-9-]+)"/g;
    let scope: RegExpExecArray | null;
    while ((scope = scopeRe.exec(rule[1])) !== null) {
      scopes.add(scope[1]);
    }
  }
  return [...scopes].sort();
}

/** 选择器列表按顶层逗号拆条（:has(...) / :is(...) 括号内的逗号不拆）。 */
function splitTopLevelSelectors(selectorList: string): string[] {
  const legs: string[] = [];
  let depth = 0;
  let current = "";
  for (const char of selectorList) {
    if (char === "," && depth === 0) {
      legs.push(current);
      current = "";
      continue;
    }
    if (char === "(") depth += 1;
    else if (char === ")") depth -= 1;
    current += char;
  }
  legs.push(current);
  return legs;
}

/**
 * 成对子列表分列提取：与 nocturneScopeSet 同样按 bodyMarker 命中规则，
 * 但只统计 legFilter 命中的顶层 selector 腿。nocturneScopeSet 对整条规则
 * 并集提取，对「同一规则里的成对列表只往一半加/删 scope」不敏感；分列后
 * 断言两半各自等于并集即可锁死（tokens.css「纯属性列表 + :has 列表」双写
 * 与延迟分册终端条阴影组双 selector 都属此类结构）。
 */
function nocturneScopeSetForLegs(
  css: string,
  bodyMarker: string,
  legFilter: (leg: string) => boolean,
): string[] {
  const cleaned = stripCssComments(css);
  const scopes = new Set<string>();
  const ruleRe = /([^{}]+)\{([^{}]*)\}/g;
  let rule: RegExpExecArray | null;
  while ((rule = ruleRe.exec(cleaned)) !== null) {
    if (!rule[2].includes(bodyMarker)) continue;
    for (const leg of splitTopLevelSelectors(rule[1])) {
      if (!legFilter(leg)) continue;
      const scopeRe = /data-moss-theme-scope="([a-z0-9-]+)"/g;
      let scope: RegExpExecArray | null;
      while ((scope = scopeRe.exec(leg)) !== null) {
        scopes.add(scope[1]);
      }
    }
  }
  return [...scopes].sort();
}

/**
 * section key → Nocturne scope 名映射：登记「key 与 scope 名不一致」的页面
 * （dashboard 首页 scope 为 dashboard-home；kpi-performance 为 kpi；
 * performance-home / reports-center 共用 ModuleWorkbenchHome 的
 * module-workbench-home 单 scope；macro-observation 与 macro-toolkit
 * 共用同一页面组件与 scope）。
 */
const NOCTURNE_SECTION_SCOPE_ALIASES: Record<string, string> = {
  dashboard: "dashboard-home",
  "kpi-performance": "kpi",
  "performance-home": "module-workbench-home",
  "reports-center": "module-workbench-home",
  "macro-observation": "macro-toolkit",
};

/** 未接入 Nocturne 的 section（占位/隐藏路由）白名单，新增时须显式登记。 */
const NON_NOCTURNE_SECTION_KEYS = new Set(["source-preview"]);

/**
 * 从 section key 推导 Nocturne scope 期望列表（治理横幅推导范式推广到
 * 全部铬件清单）：别名解析后落在 palette 内 → 参与推导；否则该 section
 * 必须命中 NON_NOCTURNE_SECTION_KEYS 白名单，缺席直接抛错——防止将来
 * 「key 与 scope 名不一致且未登记别名」的页面被静默丢弃（旧
 * palette.includes 过滤的口子）。
 */
function deriveNocturneScopes(sectionKeys: readonly string[], palette: string[]): string[] {
  const scopes = new Set<string>();
  for (const sectionKey of sectionKeys) {
    const scope = NOCTURNE_SECTION_SCOPE_ALIASES[sectionKey] ?? sectionKey;
    if (palette.includes(scope)) {
      scopes.add(scope);
      continue;
    }
    if (!NON_NOCTURNE_SECTION_KEYS.has(sectionKey)) {
      throw new Error(
        `workbenchNavigation section "${sectionKey}"（解析 scope "${scope}"）不在 Nocturne palette，` +
          "也未登记 NOCTURNE_SECTION_SCOPE_ALIASES / NON_NOCTURNE_SECTION_KEYS；" +
          "请显式登记后再更新断言，禁止静默丢弃。",
      );
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

/** 色值字面量比较归一化：小写 + 空白收敛（排版差异不报警，值差异照报）。 */
function normalizeColorLiteral(value: string): string {
  return value.replace(/\s+/g, " ").trim().toLowerCase();
}

/**
 * tokens.css Nocturne 主色板块提取：全 src 仅此一个规则声明 --nct-*（其余
 * 出现处均为 var(--nct-…) 引用）。出现第二个声明块＝引入第二套 Nocturne
 * 数值源，直接抛错要求并回主色板块，防止分叉后互锁断言只盯其中一份。
 */
function nocturnePaletteDeclarations(css: string): string {
  const cleaned = stripCssComments(css);
  const bodies: string[] = [];
  const ruleRe = /([^{}]+)\{([^{}]*)\}/g;
  let rule: RegExpExecArray | null;
  while ((rule = ruleRe.exec(cleaned)) !== null) {
    if (/--nct-[a-z0-9-]+\s*:/.test(rule[2])) bodies.push(rule[2]);
  }
  if (bodies.length !== 1) {
    throw new Error(
      `tokens.css 应恰有 1 个 --nct-* 声明块，实际 ${bodies.length} 个；` +
        "新增声明块会成为第二套 Nocturne 数值源，请并回主色板块或更新互锁断言。",
    );
  }
  return bodies[0];
}

/** 提取单个规则体内的全部自定义属性声明（键不含 --，值空白收敛）。 */
function parseCssVarDeclarations(ruleBody: string): Map<string, string> {
  const map = new Map<string, string>();
  const re = /--([a-z0-9-]+)\s*:\s*([\s\S]*?);/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(ruleBody)) !== null) {
    map.set(m[1], m[2].replace(/\s+/g, " ").trim());
  }
  return map;
}

/**
 * `color-mix(in srgb, <基色> N%, transparent)` → `rgba(r, g, b, N/100)`。
 * 取舍：soft 槽位 CSS 侧写 color-mix（基色引 var(--nct-*)，改基色自动联动），
 * JS 侧是 canvas/antd 可直接消费的 rgba 字面量，字符串无法直接对比。srgb
 * 下与 transparent 的预乘插值恰等价于「基色 + alpha=N/100」，故解析基色
 * （var 引用按同块声明解析一层）改写成 rgba 再比较——仍是值级互锁，而非
 * 退化成只比透明度或跳过 soft 槽位。
 */
function nocturneColorMixToRgba(expression: string, blockVars: Map<string, string>): string {
  const match = expression.match(
    /^color-mix\(in srgb, (#[0-9a-f]{6}|var\(--[a-z0-9-]+\)) (\d+(?:\.\d+)?)%, transparent\)$/i,
  );
  if (!match) {
    throw new Error(`无法归一化的 color-mix 表达式：${expression}`);
  }
  let base = match[1];
  if (base.toLowerCase().startsWith("var(")) {
    const resolved = blockVars.get(base.slice("var(--".length, -1));
    if (!resolved) {
      throw new Error(`color-mix 基色变量未在 Nocturne 块内声明：${base}`);
    }
    base = resolved;
  }
  const hex = /^#([0-9a-f]{6})$/i.exec(base)?.[1];
  if (!hex) {
    throw new Error(`color-mix 基色解析后不是 6 位 hex，无法归一化：${base}`);
  }
  const channel = (offset: number) => parseInt(hex.slice(offset, offset + 2), 16);
  return `rgba(${channel(0)}, ${channel(2)}, ${channel(4)}, ${Number(match[2]) / 100})`;
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

/**
 * Nocturne 双源互锁槽位映射（hex 槽位）：tokens.css Nocturne 块变量名
 * （不含 --）→ nocturneTokens.color 键。两份数值手工同步：CSS 侧供页面
 * 样式经 --dh-api-* 语义链消费，JS 侧供 antd cssinjs 与 canvas 图表等
 * 读不到 CSS 变量的消费方。命名易混处：--nct-ring（实线边框）→ line，
 * 而 --nct-line（弱分隔）→ lineSoft（登记在 color-mix 槽位表）；
 * --nct-warn 是 JS amber 与 gold 双别名的共同源（tokens.css 侧
 * --dh-api-amber / --dh-api-gold 亦同引 --nct-warn）。
 */
const NOCTURNE_HEX_SLOTS: ReadonlyArray<
  readonly [cssVar: string, jsKey: keyof typeof nocturneTokens.color]
> = [
  ["nct-bg", "bg"],
  ["nct-rail", "rail"],
  ["nct-surface", "panel"],
  ["nct-well", "panel2"],
  ["nct-raised", "panel3"],
  ["nct-ring", "line"],
  ["nct-ink", "ink"],
  ["nct-soft", "inkSoft"],
  ["nct-muted", "inkMuted"],
  ["nct-accent", "blue"],
  ["nct-accent-300", "accent300"],
  ["nct-accent-400", "accent400"],
  ["nct-up", "green"],
  ["nct-warn", "amber"],
  ["nct-warn", "gold"],
  ["nct-down", "red"],
];

/**
 * Nocturne 双源互锁槽位映射（color-mix 槽位）：CSS 侧是 color-mix 表达式
 * （soft 四件套挂在同块 --dh-api-*-soft 别名上、基色引 var(--nct-*)；
 * --nct-line 直接基于 hex 字面量），JS 侧是 rgba 字面量；经
 * nocturneColorMixToRgba 归一化成 rgba 后做值级对比（取舍见该函数注释）。
 */
const NOCTURNE_COLOR_MIX_SLOTS: ReadonlyArray<
  readonly [cssVar: string, jsKey: keyof typeof nocturneTokens.color]
> = [
  ["nct-line", "lineSoft"],
  ["dh-api-blue-soft", "blueSoft"],
  ["dh-api-green-soft", "greenSoft"],
  ["dh-api-amber-soft", "amberSoft"],
  ["dh-api-red-soft", "redSoft"],
];

/**
 * JS/CSS 双源数值互锁：nocturneTokens（designSystem.ts）与 tokens.css
 * Nocturne scope 块是手工同步的两份色值。只改 CSS 侧时 antd cssinjs 与
 * canvas 图表（JS 消费方）静默漂移，只改 JS 侧时页面样式（CSS 消费方）
 * 静默漂移——此组断言按上方槽位映射逐一值级对拍。
 */
describe("nocturneTokens ↔ tokens.css Nocturne scope parity", () => {
  const nocturneCssVars = parseCssVarDeclarations(
    nocturnePaletteDeclarations(readFileSync(TOKENS_CSS_PATH, "utf8")),
  );
  const driftHint =
    "改了一侧色值未同步另一侧：CSS 侧改动需同步 designSystem.ts nocturneTokens，" +
    "JS 侧改动需同步 tokens.css Nocturne scope 块。";

  it("keeps every hex slot in value parity", () => {
    for (const [cssVar, jsKey] of NOCTURNE_HEX_SLOTS) {
      const cssValue = nocturneCssVars.get(cssVar);
      const jsValue = nocturneTokens.color[jsKey];
      expect(cssValue, `tokens.css Nocturne 块缺少 --${cssVar} 声明；${driftHint}`).toBeDefined();
      expect(
        normalizeColorLiteral(cssValue ?? ""),
        `Nocturne 双源漂移：tokens.css --${cssVar}="${cssValue}" ≠ ` +
          `nocturneTokens.color.${jsKey}="${jsValue}"；${driftHint}`,
      ).toBe(normalizeColorLiteral(jsValue));
    }
  });

  it("keeps soft quad and line-soft color-mix slots equivalent to the JS rgba literals", () => {
    for (const [cssVar, jsKey] of NOCTURNE_COLOR_MIX_SLOTS) {
      const cssValue = nocturneCssVars.get(cssVar);
      const jsValue = nocturneTokens.color[jsKey];
      expect(cssValue, `tokens.css Nocturne 块缺少 --${cssVar} 声明；${driftHint}`).toBeDefined();
      const normalized = nocturneColorMixToRgba(cssValue ?? "", nocturneCssVars);
      expect(
        normalizeColorLiteral(normalized),
        `Nocturne 双源漂移：tokens.css --${cssVar}="${cssValue}"（归一化 "${normalized}"）≠ ` +
          `nocturneTokens.color.${jsKey}="${jsValue}"；${driftHint}`,
      ).toBe(normalizeColorLiteral(jsValue));
    }
  });

  it("keeps --dh-api-radius in parity with nocturneTokens.radius", () => {
    expect(
      nocturneCssVars.get("dh-api-radius"),
      `Nocturne 双源漂移：tokens.css --dh-api-radius="${nocturneCssVars.get("dh-api-radius")}" ≠ ` +
        `nocturneTokens.radius=${nocturneTokens.radius}（期望 "${nocturneTokens.radius}px"）；${driftHint}`,
    ).toBe(`${nocturneTokens.radius}px`);
  });

  it("registers every slot on both sides of the interlock map", () => {
    const coveredCssVars = new Set(
      [...NOCTURNE_HEX_SLOTS, ...NOCTURNE_COLOR_MIX_SLOTS].map(([cssVar]) => cssVar),
    );
    const unmappedCssVars = [...nocturneCssVars.keys()].filter(
      (name) => name.startsWith("nct-") && !coveredCssVars.has(name),
    );
    expect(
      unmappedCssVars,
      "tokens.css Nocturne 块出现未登记进互锁映射表的 --nct-* 槽位；" +
        "请同步扩展 nocturneTokens 与 NOCTURNE_*_SLOTS 映射。",
    ).toEqual([]);

    const coveredJsKeys = new Set<keyof typeof nocturneTokens.color>(
      [...NOCTURNE_HEX_SLOTS, ...NOCTURNE_COLOR_MIX_SLOTS].map(([, jsKey]) => jsKey),
    );
    const unmappedJsKeys = (
      Object.keys(nocturneTokens.color) as Array<keyof typeof nocturneTokens.color>
    ).filter((key) => !coveredJsKeys.has(key));
    expect(
      unmappedJsKeys,
      "nocturneTokens.color 出现未登记进互锁映射表的槽位；" +
        "请同步扩展 tokens.css Nocturne 块与 NOCTURNE_*_SLOTS 映射。",
    ).toEqual([]);
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
  it("maps token fields to the Nocturne palette", () => {
    const { token } = workbenchTheme;
    expect(workbenchTheme.algorithm).toBeDefined();
    expect(token).toBeDefined();
    expect(token?.colorPrimary).toBe(nocturneTokens.color.blue);
    expect(token?.colorSuccess).toBe(nocturneTokens.color.green);
    expect(token?.colorWarning).toBe(nocturneTokens.color.amber);
    expect(token?.colorError).toBe(nocturneTokens.color.red);
    expect(token?.colorText).toBe(nocturneTokens.color.ink);
    expect(token?.colorTextSecondary).toBe(nocturneTokens.color.inkSoft);
    expect(token?.colorBorder).toBe(nocturneTokens.color.line);
    expect(token?.colorBgBase).toBe(nocturneTokens.color.bg);
    expect(token?.colorBgContainer).toBe(nocturneTokens.color.panel);
    // colorBgElevated / colorFillAlter 取 panel2（--nct-well），与页内压制层同源。
    expect(token?.colorBgElevated).toBe(nocturneTokens.color.panel2);
    expect(token?.colorFillAlter).toBe(nocturneTokens.color.panel2);
    expect(token?.borderRadius).toBe(nocturneTokens.radius);
  });

  it("defines Card and Layout overrides from the Nocturne tokens", () => {
    const { components } = workbenchTheme;
    expect(components?.Card?.borderRadiusLG).toBe(nocturneTokens.radius);
    expect(components?.Card?.boxShadow).toBe("none");
    expect(components?.Layout?.bodyBg).toBe(nocturneTokens.color.bg);
    expect(components?.Layout?.siderBg).toBe(nocturneTokens.color.rail);
  });

  it("keeps table chrome on the Nocturne density and row tokens", () => {
    const { components } = workbenchTheme;
    expect(components?.Table?.headerBg).toBe(nocturneTokens.color.panel3);
    expect(components?.Table?.headerColor).toBe(nocturneTokens.color.inkSoft);
    // accent 8% 行悬停，对齐 --moss-institutional-row-hover 的 mix 惯例。
    expect(components?.Table?.rowHoverBg).toBe("rgba(145, 132, 217, 0.08)");
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
    const railMarkOverride = nocturneScopeSet(
      shellCss,
      "background: var(--nct-surface) !important",
      ".workbench-shell-rail-mark",
    );
    const pageV2Override = nocturneScopeSet(
      shellCss,
      "background: var(--nct-surface) !important",
      ".moss-page-v2-",
    );
    const conclusionOverride = nocturneScopeSet(
      shellCss,
      "border-left-color: var(--nct-accent) !important",
      ".moss-page-v2-decision-hero__conclusion",
    );
    const cockpitHoverOverride = nocturneScopeSet(
      shellCss,
      "color-mix(in srgb, var(--nct-accent) 9%, transparent) !important",
    );
    const cockpitActiveOverride = nocturneScopeSet(
      shellCss,
      "box-shadow: inset 2px 0 0 var(--nct-accent) !important",
    );
    const terminalOverride = nocturneScopeSet(
      workbenchDeferredChromeCss,
      "background: var(--nct-rail) !important",
    );
    const boundaryOverride = nocturneScopeSet(
      tokensCss,
      "background: var(--nct-bg, var(--dh-api-bg))",
    );
    // 延迟分册的铬件收敛列表（workbenchDeferredChrome.css）：
    // 终端条铬件四组（阴影 / chip+pill / utility navlink / 行情条）。
    const terminalChromeShadow = nocturneScopeSet(
      workbenchDeferredChromeCss,
      "box-shadow: none !important",
    );
    const terminalChromeChipPill = nocturneScopeSet(
      workbenchDeferredChromeCss,
      "background: var(--dh-api-panel-2)",
    );
    const terminalChromeNavlink = nocturneScopeSet(
      workbenchDeferredChromeCss,
      "border-bottom-color: var(--dh-api-blue)",
    );
    const terminalChromeTicker = nocturneScopeSet(
      workbenchDeferredChromeCss,
      "border-top-color: var(--dh-api-line-soft)",
    );
    // 组内子导航三组（分隔线 / 链接描边 / active 链接）。
    const subnavOverride = nocturneScopeSet(
      workbenchDeferredChromeCss,
      "border-bottom-color: var(--dh-api-line-soft)",
    );
    const subnavLinkOverride = nocturneScopeSet(
      workbenchDeferredChromeCss,
      "border-color: var(--dh-api-line-soft)",
      ".workbench-section-subnav__link",
    );
    const subnavActiveOverride = nocturneScopeSet(
      workbenchDeferredChromeCss,
      "color-mix(in srgb, var(--dh-api-blue) 14%, transparent)",
    );
    // 治理横幅四块（selectorMarker 排除 /agent 的 gated 就绪横幅同款声明）。
    const governanceSelectorMarker = '[data-notice-tone="governance"]';
    const governanceBannerOverride = nocturneScopeSet(
      workbenchDeferredChromeCss,
      "background: var(--dh-api-amber-soft)",
      governanceSelectorMarker,
    );
    const governanceTitleOverride = nocturneScopeSet(
      workbenchDeferredChromeCss,
      "color: var(--dh-api-amber)",
      governanceSelectorMarker,
    );
    const governanceBodyOverride = nocturneScopeSet(
      workbenchDeferredChromeCss,
      "line-height: 1.5",
      ".workbench-notice__body",
    );
    const governanceHintOverride = nocturneScopeSet(
      workbenchDeferredChromeCss,
      "color: var(--dh-api-muted)",
      governanceSelectorMarker,
    );

    // 渲染分支推导期望（WorkbenchShell 导出常量 + workbenchNavigation +
    // 共享别名表）：终端条/子导航/cockpit 不再互为相对 parity，而是各自
    // 对齐渲染分支的推导值——tokens.css 某块自身多写/漏写 scope 时同样红。
    const navigationSectionKeys = workbenchNavigation.map((section) => section.key);
    const terminalExpected = deriveNocturneScopes(
      navigationSectionKeys.filter(
        (key) => !TERMINAL_BAR_EXCLUDED_SECTION_KEYS.includes(key),
      ),
      palette,
    );
    const subnavExpected = deriveNocturneScopes(
      navigationSectionKeys.filter(
        (key) => !SECTION_SUBNAV_EXCLUDED_SECTION_KEYS.includes(key),
      ),
      palette,
    );
    const cockpitExpected = deriveNocturneScopes(COCKPIT_SHELL_SECTION_KEYS, palette);
    // 推导锚点：market-data 渲染终端条但抑制子导航；宏观工具相反；
    // dashboard / performance-home / reports-center 走别名解析入 cockpit。
    expect(terminalExpected).toContain("market-data");
    expect(terminalExpected).not.toContain("macro-toolkit");
    expect(subnavExpected).toContain("macro-toolkit");
    expect(subnavExpected).not.toContain("market-data");
    expect(cockpitExpected).toContain("dashboard-home");
    expect(cockpitExpected).toContain("module-workbench-home");

    // 主色板块（tokens.css）是唯一权威列表；收口层 grid/rail 必须同一份。
    expect(palette.length).toBeGreaterThanOrEqual(10);
    expect(gridOverride).toEqual(palette);
    expect(railOverride).toEqual(palette);
    // themeScope 字面量联合（PageV2Shell / MarketWorkbenchFrame 类型收窄
    // 的 union 来源）与主色板块同构全量。
    expect([...NOCTURNE_THEME_SCOPES].sort()).toEqual(palette);
    // ThemedRouteBoundary 兜底底色块与主色板块同构全量
    // （无 boundary 的路由 :has() 不命中即零效果）。
    expect(boundaryOverride).toEqual(palette);
    // rail-mark：dashboard-home / portfolio-home 保持 cockpit 透明制度不入列表；
    // market-overview / risk-overview 虽也走 cockpit 壳，rail-mark 保留兜底行
    // （market-overview 由页内更高特异性块接管）。
    expect(railMarkOverride).toEqual(
      palette.filter((scope) => scope !== "dashboard-home" && scope !== "portfolio-home"),
    );
    // page-v2 面板压制（背景 + 结论左边线）与 grid/rail 同构全量列表。
    expect(pageV2Override).toEqual(palette);
    expect(conclusionOverride).toEqual(palette);
    // cockpit 壳 rail hover/active＝useCockpitShellFrame 渲染分支推导
    // （终层兜底）；dashboard-home / market-overview 由页内更高特异性块
    // 等值接管，其余 scope 由终层直接生效。
    expect(cockpitHoverOverride).toEqual(cockpitExpected);
    expect(cockpitActiveOverride).toEqual(cockpitExpected);
    // 首页 cockpit 壳不渲染主列纸面。
    expect(paper).toEqual(palette.filter((scope) => scope !== "dashboard-home"));
    // 渲染终端条的 scope＝showShellTerminalBar 渲染分支推导；tokens.css
    // 终端条块与延迟分册收敛列表（含铬件四组：阴影 / chip+pill /
    // utility navlink / 行情条）都必须等于这一份推导值。
    expect(terminalVars).toEqual(terminalExpected);
    expect(terminalOverride).toEqual(terminalExpected);
    expect(terminalChromeShadow).toEqual(terminalExpected);
    expect(terminalChromeChipPill).toEqual(terminalExpected);
    expect(terminalChromeNavlink).toEqual(terminalExpected);
    expect(terminalChromeTicker).toEqual(terminalExpected);
    // 子导航三组＝组内子导航渲染分支推导（market-data 抑制子导航、
    // 宏观工具抑制终端条但保留子导航，差异都由排除表常量表达）。
    expect(subnavOverride).toEqual(subnavExpected);
    expect(subnavLinkOverride).toEqual(subnavExpected);
    expect(subnavActiveOverride).toEqual(subnavExpected);
    // 治理横幅四块＝navigation.ts 中 governanceStatus="temporary-exception"
    // 的 section 走共享别名表推导（kpi-performance → kpi），外加
    // liability-analytics 历史零效果行（该 section 已无治理横幅）。
    const governanceExpected = [
      ...new Set([
        ...deriveNocturneScopes(
          workbenchNavigation
            .filter((section) => section.governanceStatus === "temporary-exception")
            .map((section) => section.key),
          palette,
        ),
        "liability-analytics",
      ]),
    ].sort();
    expect(governanceExpected).toContain("decision-items");
    expect(governanceBannerOverride).toEqual(governanceExpected);
    expect(governanceTitleOverride).toEqual(governanceExpected);
    expect(governanceBodyOverride).toEqual(governanceExpected);
    expect(governanceHintOverride).toEqual(governanceExpected);

    // 成对子列表一致性（分列提取）：tokens.css 三块「纯属性列表 + :has
    // 列表」双写与延迟分册终端条阴影组「基础腿 + --desktop-aligned 腿」
    // 双 selector，整条并集提取对「只往一半加/删 scope」不敏感；分列后
    // 断言每一半各自等于对应权威列表。
    const isHasLeg = (leg: string) => leg.includes(":has(");
    const isPlainLeg = (leg: string) => !leg.includes(":has(");
    const isDesktopAlignedLeg = (leg: string) => leg.includes("--desktop-aligned");
    expect(nocturneScopeSetForLegs(tokensCss, "--nct-bg: #161826", isPlainLeg)).toEqual(
      palette,
    );
    expect(nocturneScopeSetForLegs(tokensCss, "--nct-bg: #161826", isHasLeg)).toEqual(
      palette,
    );
    expect(
      nocturneScopeSetForLegs(tokensCss, "--moss-shell-paper-bg: var(--nct-bg)", isPlainLeg),
    ).toEqual(paper);
    expect(
      nocturneScopeSetForLegs(tokensCss, "--moss-shell-paper-bg: var(--nct-bg)", isHasLeg),
    ).toEqual(paper);
    expect(
      nocturneScopeSetForLegs(
        tokensCss,
        "--moss-shell-terminal-bg: var(--nct-rail)",
        isPlainLeg,
      ),
    ).toEqual(terminalExpected);
    expect(
      nocturneScopeSetForLegs(
        tokensCss,
        "--moss-shell-terminal-bg: var(--nct-rail)",
        isHasLeg,
      ),
    ).toEqual(terminalExpected);
    expect(
      nocturneScopeSetForLegs(
        workbenchDeferredChromeCss,
        "box-shadow: none !important",
        (leg) => !isDesktopAlignedLeg(leg),
      ),
    ).toEqual(terminalExpected);
    expect(
      nocturneScopeSetForLegs(
        workbenchDeferredChromeCss,
        "box-shadow: none !important",
        isDesktopAlignedLeg,
      ),
    ).toEqual(terminalExpected);
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
