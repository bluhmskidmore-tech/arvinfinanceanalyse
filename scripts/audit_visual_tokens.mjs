#!/usr/bin/env node

/**
 * Visual token guardrail (DESIGN.md).
 *
 * Per-file no-growth audit over frontend/src for:
 *  - bare hex color literals (should go through --ib-* / --dh-api-* / designTokens)
 *  - forbidden colors (AI purple family; disallowed by DESIGN.md §4)
 *  - CSS border-radius values outside the Shape Lock allowlist (2px / 6px / 999px)
 *  - "--" missing-value literals in TSX (canonical placeholder is the em dash "—")
 *
 * Baseline lives in scripts/audit_visual_tokens.baseline.json.
 * Regenerate after paying down debt with:  node scripts/audit_visual_tokens.mjs --update-baseline
 * Baselines must only go down; do not raise them without explicit justification.
 *
 * Baseline reconciliations (justified raises, not new violations):
 *  - 2026-08-13 frontend/src/test/theme.test.ts hex 14 -> 15: all 15 hexes are theme test
 *    fixtures (14 shell-token `toBe("#...")` assertions plus the Nocturne scope-parity needle
 *    `"--nct-bg: #161826"`). Pre-existing drift surfaced once the audit stopped early-exiting;
 *    the file is unchanged relative to HEAD.
 *  - 2026-08-13 frontend/src/test/theme.test.ts hex 15 -> 17: commit 04d9613e (antd cssinjs
 *    tokens switched to Nocturne with derivation guardrails) added two more hex assertion
 *    fixtures to the theme test; legitimate test samples, not UI literals.
 *  - 2026-08-13 frontend/src/theme/designSystem.ts hex -> 217: the token authority file is the
 *    sanctioned home for hex literals (Nocturne dark-theme tokens added here); 217 is the exact
 *    count under the ticket-guarded HEX_PATTERN (4 comment anchor references like `锚点 #1850a1）`
 *    are prose, no longer counted).
 *  - 2026-08-13 frontend/src/components/page/PagePrimitives.module.css hex 0 -> 20: inline-style
 *    extraction from PagePrimitives.tsx made previously invisible shellTokens constant references
 *    visible as CSS literals. All 20 values verified identical to theme/tokens.ts shellTokens /
 *    designTokens (see the file's header comment for the mapping); no new colors introduced.
 *  - 2026-08-13 dashboard-home debt move reconciliation: dashboardHomeShell.module.css hex
 *    84 -> 38 and dashboardHomeOptionTwo.module.css hex 0 -> 20. The 皮肤统一阶段1 MOVE
 *    migration (commits 60b112db/1c561ed2) copied 20 legacy hex declarations verbatim from the
 *    shell module into optionTwo (declaration-value fidelity contract, see optionTwo header
 *    comments) without reconciling either per-file entry. Net -26 hex; no new colors introduced.
 *  - 2026-08-14 Shape Lock allowlist realigned to DESIGN.md §2.2/§5 (8px in, 6px out):
 *    `--dh-api-radius` = 8px is the canonical Nocturne radius (tokens.css Nocturne scope);
 *    6px only survives as the steel-blue `.theme-dh-api` compat fallback and hand-written 6px
 *    is drift. offRadius baselines reconciled surgically (only offRadius fields; no full
 *    regenerate, so parallel in-flight edits are not absorbed): 10 files raised for newly
 *    counted literal 6px (+48: StockAnalysisPage 2->27, BondAnalyticsViewContent 1->9,
 *    dashboardHomeOptionTwoDeferred 0->6, dashboardHome 3->4, workbenchShell 2->3,
 *    StockAnalysisPretradeChecklist 0->2, CalendarList / DataQualityBanner /
 *    BondAnalyticsDetailPrimitives / StockAnalysisDataHealthCard 0->1), 3 files ratcheted
 *    down for now-allowed literal 8px (AgentWorkbenchPage 25->17, MarketDataPage 26->8,
 *    AgentPanel 1->0). Existing 6px literals are pre-existing drift made visible, not new
 *    violations; they stay counted so the ratchet drives them to `var(--dh-api-radius)`.
 */

import { readdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import path from "node:path";

const repoRoot = path.resolve(import.meta.dirname, "..");
const baselinePath = path.join(repoRoot, "scripts", "audit_visual_tokens.baseline.json");
const scanRoot = path.join(repoRoot, "frontend", "src");

/**
 * Bare hex color literal.
 * Guards against ticket-reference false positives in comments (e.g. `01#17a：`, `#17a/#17d。`):
 *  - lookbehind: a real color literal is never directly preceded by an ASCII alphanumeric
 *    (ticket ids like `01#17a` are);
 *  - lookahead: a real color literal is never directly followed by CJK text or CJK/full-width
 *    punctuation (`#17a工单`, `#17d。`, `#17a：` are prose, not colors).
 */
const HEX_PATTERN =
  /(?<![0-9a-zA-Z])#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\b(?![\u3000-\u303f\u4e00-\u9fff\uff00-\uffef])/g;

/** AI purple family — forbidden by DESIGN.md §4 ("AI 紫/霓虹渐变"). */
const FORBIDDEN_HEXES = [
  "#7c3aed",
  "#8b5cf6",
  "#a855f7",
  "#9333ea",
  "#6d28d9",
  "#531dab",
  "#722ed1",
  "#eb2f96",
];

/**
 * Shape Lock (DESIGN.md §2.2/§5): 2px IB light, 8px canonical Nocturne dark
 * terminal (`--dh-api-radius`, tokens.css Nocturne scope), 999px pills only.
 * 6px is the steel-blue `.theme-dh-api` compat fallback — hand-written 6px is
 * drift (compat pages must reference `var(--dh-api-radius)`), so it counts as
 * debt since 2026-08-14.
 */
const RADIUS_ALLOWLIST = new Set(["0", "2px", "8px", "999px", "50%", "inherit"]);

function walkFiles(dir, out = []) {
  for (const entry of readdirSync(dir)) {
    const fullPath = path.join(dir, entry);
    const stats = statSync(fullPath);
    if (stats.isDirectory()) {
      walkFiles(fullPath, out);
    } else if (/\.(css|tsx|ts)$/.test(fullPath) && !/\.d\.ts$/.test(fullPath)) {
      out.push(fullPath);
    }
  }
  return out;
}

function toRepoPath(fullPath) {
  return path.relative(repoRoot, fullPath).replace(/\\/g, "/");
}

function countMatches(text, pattern) {
  return [...text.matchAll(pattern)].length;
}

function countForbidden(text) {
  const lower = text.toLowerCase();
  let count = 0;
  for (const hex of FORBIDDEN_HEXES) {
    let index = lower.indexOf(hex);
    while (index !== -1) {
      count += 1;
      index = lower.indexOf(hex, index + hex.length);
    }
  }
  return count;
}

function countOffRadius(cssText) {
  let count = 0;
  for (const match of cssText.matchAll(/border-radius\s*:\s*([^;}]+)[;}]/g)) {
    // var(...) values (including their fallbacks) resolve through tokens; skip them.
    // !important is a modifier, not a radius value.
    const withoutVars = match[1]
      .replace(/var\([^)]*\)/g, " ")
      .replace(/!important/g, " ")
      .trim();
    if (withoutVars === "") continue;
    for (const value of withoutVars.split(/\s+/)) {
      if (!RADIUS_ALLOWLIST.has(value.toLowerCase())) {
        count += 1;
      }
    }
  }
  return count;
}

function countDoubleDashPlaceholders(tsxText) {
  // "--" string literals used as display placeholders (should be "—").
  return countMatches(tsxText, /(["'`])--\1/g);
}

function auditFile(fullPath) {
  const text = readFileSync(fullPath, "utf8");
  const isCss = fullPath.endsWith(".css");
  const isTsx = fullPath.endsWith(".tsx");
  return {
    hex: countMatches(text, HEX_PATTERN),
    forbidden: countForbidden(text),
    offRadius: isCss ? countOffRadius(text) : 0,
    doubleDash: isTsx ? countDoubleDashPlaceholders(text) : 0,
  };
}

function collect() {
  const results = {};
  for (const fullPath of walkFiles(scanRoot)) {
    const metrics = auditFile(fullPath);
    if (metrics.hex || metrics.forbidden || metrics.offRadius || metrics.doubleDash) {
      results[toRepoPath(fullPath)] = metrics;
    }
  }
  return results;
}

function totals(results) {
  const sum = { hex: 0, forbidden: 0, offRadius: 0, doubleDash: 0 };
  for (const metrics of Object.values(results)) {
    sum.hex += metrics.hex;
    sum.forbidden += metrics.forbidden;
    sum.offRadius += metrics.offRadius;
    sum.doubleDash += metrics.doubleDash;
  }
  return sum;
}

function runSelfTest() {
  const cssSample = [
    ".a { color: #fff; border-radius: 12px; }",
    ".b { border-radius: 2px; background: #7C3AED; }",
    ".c { border-radius: var(--ib-radius, 2px) 999px; }",
  ].join("\n");
  const hex = countMatches(cssSample, HEX_PATTERN);
  const forbidden = countForbidden(cssSample);
  const offRadius = countOffRadius(cssSample);
  if (hex !== 2 || forbidden !== 1 || offRadius !== 1) {
    throw new Error(`css counters mismatch: hex=${hex} forbidden=${forbidden} offRadius=${offRadius}`);
  }
  const tsxSample = 'const x = value ?? "--"; const y = `--`; const ok = "—";';
  if (countDoubleDashPlaceholders(tsxSample) !== 2) {
    throw new Error("double-dash counter mismatch");
  }
  // Ticket references in comments must not count as hex colors; real literals must.
  const ticketSample = [
    "// 01#17a：工单编号并非颜色。",
    "// 01#17a/#17d：连续工单编号也不是颜色。",
    'const label = "#17a工单";',
    ".d { color: #17a; }",
    'const accent = "#17ab";',
  ].join("\n");
  const ticketHex = countMatches(ticketSample, HEX_PATTERN);
  if (ticketHex !== 2) {
    throw new Error(`hex ticket-reference guard mismatch: hex=${ticketHex} (expected 2)`);
  }
  console.log("audit_visual_tokens self-test: ok");
}

if (process.argv.includes("--self-test")) {
  runSelfTest();
  process.exit(0);
}

const current = collect();

if (process.argv.includes("--update-baseline")) {
  const sorted = Object.fromEntries(
    Object.entries(current).sort(([a], [b]) => a.localeCompare(b)),
  );
  writeFileSync(baselinePath, `${JSON.stringify(sorted, null, 2)}\n`);
  const sum = totals(current);
  console.log(
    `Baseline updated: ${Object.keys(current).length} files ` +
      `(hex=${sum.hex}, forbidden=${sum.forbidden}, offRadius=${sum.offRadius}, doubleDash=${sum.doubleDash})`,
  );
  process.exit(0);
}

let baseline;
try {
  baseline = JSON.parse(readFileSync(baselinePath, "utf8"));
} catch {
  console.error(
    "Missing scripts/audit_visual_tokens.baseline.json. " +
      "Generate it with: node scripts/audit_visual_tokens.mjs --update-baseline",
  );
  process.exit(1);
}

const failures = [];
const metricHints = {
  hex: "Use --ib-* / --dh-api-* / designTokens instead of new bare hex colors.",
  forbidden: "AI purple family is forbidden (DESIGN.md §4); use IB accent or info scale.",
  offRadius: "Shape Lock (DESIGN.md §2.2/§5): only 2px (IB), 8px (canonical Nocturne), 999px (pills).",
  doubleDash: 'Use the canonical em dash "—" for missing values (DESIGN.md §6).',
};

for (const [repoPath, metrics] of Object.entries(current)) {
  const base = baseline[repoPath] ?? { hex: 0, forbidden: 0, offRadius: 0, doubleDash: 0 };
  for (const key of Object.keys(metricHints)) {
    const allowed = base[key] ?? 0;
    if (metrics[key] > allowed) {
      failures.push(`${repoPath} ${key}: ${metrics[key]} > baseline ${allowed}. ${metricHints[key]}`);
    }
  }
}

const currentSum = totals(current);
const baselineSum = totals(baseline);

if (failures.length > 0) {
  console.error("Visual token audit failed. Existing debt may remain, but this change grows it.");
  for (const failure of failures) {
    console.error(`- ${failure}`);
  }
  process.exit(1);
}

console.log("Visual token audit passed (no growth over baseline).");
console.log(
  `- totals: hex ${currentSum.hex}/${baselineSum.hex}, forbidden ${currentSum.forbidden}/${baselineSum.forbidden}, ` +
    `off-radius ${currentSum.offRadius}/${baselineSum.offRadius}, "--" placeholders ${currentSum.doubleDash}/${baselineSum.doubleDash}`,
);
