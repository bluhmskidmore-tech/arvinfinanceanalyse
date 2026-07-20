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
 */

import { readdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import path from "node:path";

const repoRoot = path.resolve(import.meta.dirname, "..");
const baselinePath = path.join(repoRoot, "scripts", "audit_visual_tokens.baseline.json");
const scanRoot = path.join(repoRoot, "frontend", "src");

const HEX_PATTERN = /#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\b/g;

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

/** Shape Lock (DESIGN.md §5): 2px IB light, 6px dark terminal, 999px pills only. */
const RADIUS_ALLOWLIST = new Set(["0", "2px", "6px", "999px", "50%", "inherit"]);

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
  offRadius: "Shape Lock (DESIGN.md §5): only 2px (IB), 6px (dark terminal), 999px (pills).",
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
