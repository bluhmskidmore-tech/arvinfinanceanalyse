#!/usr/bin/env node

/**
 * Font-size floor guardrail (DESIGN.md §3).
 *
 * Per-file no-growth audit over frontend/src CSS (including .module.css):
 *  - count `font-size:` declarations whose value is a px literal below 12px
 *  - report rem/em/var()/calc()/other non-px values as a coverage gap (not judged)
 *
 * Baseline lives in scripts/audit_font_size_floor.baseline.json.
 * Tighten after paying down debt with:  node scripts/audit_font_size_floor.mjs --ratchet
 * Baselines must only go down; this tool never raises them.
 */

import { readdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import path from "node:path";

const repoRoot = path.resolve(import.meta.dirname, "..");
const baselineRelativePath = "scripts/audit_font_size_floor.baseline.json";
const baselinePath = path.join(repoRoot, baselineRelativePath);
const scanRoot = path.join(repoRoot, "frontend", "src");

const FLOOR_PX = 12;
const SKIP_DIR_NAMES = new Set(["node_modules", "dist", "build", "coverage", ".git"]);
const FONT_SIZE_DECL = /(?<![\w-])font-size\s*:\s*([^;}]+)/gi;

function walkCssFiles(dir, out = []) {
  for (const entry of readdirSync(dir)) {
    if (SKIP_DIR_NAMES.has(entry)) continue;
    const fullPath = path.join(dir, entry);
    const stats = statSync(fullPath);
    if (stats.isDirectory()) {
      walkCssFiles(fullPath, out);
    } else if (fullPath.endsWith(".css")) {
      out.push(fullPath);
    }
  }
  return out;
}

function toRepoPath(fullPath) {
  return path.relative(repoRoot, fullPath).replace(/\\/g, "/");
}

function stripCssComments(text) {
  return text.replace(/\/\*[\s\S]*?\*\//g, " ");
}

function classifyFontSizeValue(raw) {
  const value = raw.replace(/!important/gi, "").trim();
  if (!value) return "empty";
  const pxMatch = /^(\d+(?:\.\d+)?)px$/i.exec(value);
  if (pxMatch) {
    return Number(pxMatch[1]) < FLOOR_PX ? "belowFloor" : "pxOk";
  }
  return "nonPx";
}

function auditCssText(text) {
  const stripped = stripCssComments(text);
  let belowFloor = 0;
  let pxTotal = 0;
  let nonPx = 0;
  for (const match of stripped.matchAll(FONT_SIZE_DECL)) {
    const kind = classifyFontSizeValue(match[1]);
    if (kind === "belowFloor") {
      belowFloor += 1;
      pxTotal += 1;
    } else if (kind === "pxOk") {
      pxTotal += 1;
    } else if (kind === "nonPx") {
      nonPx += 1;
    }
  }
  return { belowFloor, pxTotal, nonPx };
}

function collect() {
  const files = walkCssFiles(scanRoot);
  const results = {};
  const coverage = { cssFiles: files.length, pxTotal: 0, belowFloor: 0, nonPx: 0 };
  for (const fullPath of files) {
    const metrics = auditCssText(readFileSync(fullPath, "utf8"));
    coverage.pxTotal += metrics.pxTotal;
    coverage.belowFloor += metrics.belowFloor;
    coverage.nonPx += metrics.nonPx;
    if (metrics.belowFloor > 0) {
      results[toRepoPath(fullPath)] = { belowFloor: metrics.belowFloor };
    }
  }
  return { results, coverage };
}

function sortedResults(results) {
  return Object.fromEntries(Object.entries(results).sort(([a], [b]) => a.localeCompare(b)));
}

function belowFloorOf(entry) {
  if (!entry || typeof entry !== "object") return 0;
  const value = entry.belowFloor;
  return Number.isInteger(value) && value >= 0 ? value : 0;
}

function loadBaseline() {
  let raw;
  try {
    raw = readFileSync(baselinePath, "utf8");
  } catch {
    return null;
  }
  try {
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      throw new Error("baseline must be a JSON object keyed by file path");
    }
    return parsed;
  } catch (error) {
    console.error(`Invalid JSON in ${baselineRelativePath}: ${error.message}`);
    process.exit(1);
  }
}

function writeBaseline(results) {
  writeFileSync(baselinePath, `${JSON.stringify(sortedResults(results), null, 2)}\n`);
}

function printCoverage(coverage) {
  const judged = coverage.pxTotal + coverage.nonPx;
  const gapPct = judged === 0 ? 0 : (coverage.nonPx / judged) * 100;
  console.log(
    `- coverage: scanned ${coverage.cssFiles} css files; px declarations ${coverage.pxTotal}; ` +
      `non-px font-size ${coverage.nonPx} (${gapPct.toFixed(1)}% of font-size decls, not judged)`,
  );
}

function runSelfTest() {
  const sample = [
    ".a { font-size: 10px; }",
    ".b { font-size: 12px; }",
    ".c { font-size: 11.5px !important; }",
    ".d { font-size: 0.75rem; }",
    ".e { font-size: var(--x); }",
    ".f { font-size: calc(1em + 2px); }",
    ".g { --ib-kicker-font-size: 11px; }",
    ".h { font-size: clamp(10px, 2vw, 14px); }",
    "/* font-size: 8px; */",
  ].join("\n");
  const actual = auditCssText(sample);
  if (actual.belowFloor !== 2 || actual.pxTotal !== 3 || actual.nonPx !== 4) {
    throw new Error(`font-size counters mismatch: ${JSON.stringify(actual)}`);
  }
  console.log("audit_font_size_floor self-test: ok");
}

function runRatchet() {
  const { results, coverage } = collect();
  const baseline = loadBaseline();
  if (baseline === null) {
    writeBaseline(results);
    console.log(
      `Baseline seeded: ${Object.keys(results).length} files ` +
        `(below-12px=${coverage.belowFloor}) -> ${baselineRelativePath}`,
    );
    printCoverage(coverage);
    return;
  }

  const tightened = [];
  const blocked = [];
  const next = { ...baseline };

  for (const [repoPath, metrics] of Object.entries(results)) {
    const allowed = belowFloorOf(baseline[repoPath]);
    if (metrics.belowFloor > allowed) {
      blocked.push(
        `${repoPath}: actual ${metrics.belowFloor} > baseline ${allowed}; ` +
          `--ratchet never raises a baseline. Reduce the debt, or obtain tech-lead sign-off and edit ${baselineRelativePath} manually.`,
      );
    } else if (metrics.belowFloor < allowed) {
      next[repoPath] = { belowFloor: metrics.belowFloor };
      tightened.push(`${repoPath}: baseline ${allowed} -> ${metrics.belowFloor}`);
    }
  }

  for (const repoPath of Object.keys(baseline)) {
    if (!results[repoPath]) {
      const allowed = belowFloorOf(baseline[repoPath]);
      delete next[repoPath];
      tightened.push(`${repoPath}: baseline ${allowed} -> 0`);
    }
  }

  if (tightened.length > 0) {
    writeBaseline(next);
  }

  const banner = "!".repeat(78);
  console.log(banner);
  console.log("RATCHET MODE: 基线变更需技术负责人签核 (baseline changes require tech-lead sign-off).");
  console.log("Policy: baselines only ratchet DOWN; this tool never raises a baseline.");
  console.log(banner);

  if (tightened.length === 0) {
    console.log(`No baseline lowered; ${baselineRelativePath} left unchanged.`);
  } else {
    console.log(`Tightened ${tightened.length} baseline(s) in ${baselineRelativePath}:`);
    for (const line of tightened) {
      console.log(`- ${line}`);
    }
    console.log("Review the diff and record tech-lead sign-off in the PR before committing.");
  }
  printCoverage(coverage);

  if (blocked.length > 0) {
    console.error(`\nRefused to raise ${blocked.length} baseline(s):`);
    for (const line of blocked) {
      console.error(`- ${line}`);
    }
    process.exit(1);
  }
}

function runAudit() {
  const { results, coverage } = collect();
  const baseline = loadBaseline();
  if (baseline === null) {
    console.error(
      `Missing ${baselineRelativePath}. ` +
        "Generate it with: node scripts/audit_font_size_floor.mjs --ratchet",
    );
    process.exit(1);
  }

  const failures = [];
  const tightenHints = [];
  const allPaths = new Set([...Object.keys(results), ...Object.keys(baseline)]);
  for (const repoPath of [...allPaths].sort()) {
    const actual = belowFloorOf(results[repoPath]);
    const allowed = belowFloorOf(baseline[repoPath]);
    if (actual > allowed) {
      failures.push(
        `${repoPath} belowFloor: ${actual} > baseline ${allowed}. ` +
          "DESIGN.md §3: data-row minimum 12px.",
      );
    } else if (actual < allowed) {
      tightenHints.push(`${repoPath}: ${allowed} -> ${actual}`);
    }
  }

  const baselineFiles = Object.keys(baseline).length;
  const currentFiles = Object.keys(results).length;
  const baselineSum = Object.values(baseline).reduce((sum, entry) => sum + belowFloorOf(entry), 0);

  if (failures.length > 0) {
    console.error("Font size floor audit failed. Existing debt may remain, but this change grows it.");
    for (const failure of failures) {
      console.error(`- ${failure}`);
    }
    process.exit(1);
  }

  console.log("Font size floor audit passed (no growth over baseline).");
  console.log(
    `- totals: below-12px ${coverage.belowFloor}/${baselineSum} across ${currentFiles}/${baselineFiles} files`,
  );
  printCoverage(coverage);
  if (tightenHints.length > 0) {
    console.log(`- can tighten: ${tightenHints.length} file(s); re-run with --ratchet`);
    for (const hint of tightenHints) {
      console.log(`  - ${hint}`);
    }
  }
}

if (process.argv.includes("--self-test")) {
  runSelfTest();
  process.exit(0);
}

if (process.argv.includes("--ratchet")) {
  runRatchet();
  process.exit(0);
}

runAudit();
