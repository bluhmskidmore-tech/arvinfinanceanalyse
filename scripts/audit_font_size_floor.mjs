#!/usr/bin/env node

/**
 * Font-size floor guardrail (DESIGN.md §3).
 *
 * Per-file no-growth audit over frontend/src:
 *  - CSS (including .module.css): count `font-size:` declarations whose value
 *    is a px literal below 11px; rem/em/var()/calc()/other non-px are a
 *    coverage gap (not judged)
 *  - TS/TSX inline: count `fontSize:` assignments whose value is a judged px
 *    below 11 (bare number, "Npx" / 'Npx', or fontSize[N] / alias[N] token
 *    index). Unrecognized expressions are a coverage gap (not judged).
 *
 * Policy (2026-08 sign-off): DESIGN.md §3 allows 11-12px for auxiliary text,
 * so the hard floor is 11px (10px and below are violations). Data rows should
 * still be >=12px, but that distinction is enforced in review, not here.
 *
 * Baseline lives in scripts/audit_font_size_floor.baseline.json
 * (namespaces `css` and `inline`). Tighten after paying down debt with:
 *   node scripts/audit_font_size_floor.mjs --ratchet
 * Baselines must only go down; this tool never raises them.
 */

import { readdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = path.resolve(import.meta.dirname, "..");
const baselineRelativePath = "scripts/audit_font_size_floor.baseline.json";
const baselinePath = path.join(repoRoot, baselineRelativePath);
const scanRoot = path.join(repoRoot, "frontend", "src");

const FLOOR_PX = 11;
const SKIP_DIR_NAMES = new Set(["node_modules", "dist", "build", "coverage", ".git"]);
const FONT_SIZE_DECL = /(?<![\w-])font-size\s*:\s*([^;}]+)/gi;
const DESIGN_SYSTEM_REPO_PATH = "frontend/src/theme/designSystem.ts";
const TYPE_ONLY_VALUE =
  /^(?:number|string|boolean|unknown|undefined|null|bigint|any|never|object|void)(?:\s*[|&]\s*(?:number|string|boolean|unknown|undefined|null|bigint|any|never|object|void|(?:['"][^'"]*['"])))*\s*$/;

function walkByExtension(dir, extensions, out = []) {
  for (const entry of readdirSync(dir)) {
    if (SKIP_DIR_NAMES.has(entry)) continue;
    const fullPath = path.join(dir, entry);
    const stats = statSync(fullPath);
    if (stats.isDirectory()) {
      walkByExtension(fullPath, extensions, out);
    } else if (extensions.some((ext) => fullPath.endsWith(ext))) {
      out.push(fullPath);
    }
  }
  return out;
}

function toRepoPath(fullPath) {
  return path.relative(repoRoot, fullPath).replace(/\\/g, "/");
}

function isSkippedInlinePath(repoPath) {
  if (repoPath.endsWith(".d.ts")) return true;
  if (repoPath === DESIGN_SYSTEM_REPO_PATH) return true;
  if (/(?:^|\/)test\//.test(repoPath)) return true;
  if (/\.test\.tsx?$/.test(repoPath)) return true;
  if (/\.spec\.tsx?$/.test(repoPath)) return true;
  return false;
}

function stripCssComments(text) {
  return text.replace(/\/\*[\s\S]*?\*\//g, " ");
}

function isIdentChar(ch) {
  return ch !== undefined && /[A-Za-z0-9_$]/.test(ch);
}

function skipWs(text, i) {
  while (i < text.length && /\s/.test(text[i])) i += 1;
  return i;
}

function readBalancedValue(text, start) {
  let i = skipWs(text, start);
  const begin = i;
  let paren = 0;
  let bracket = 0;
  let brace = 0;
  let quote = null;
  while (i < text.length) {
    const c = text[i];
    if (quote) {
      if (c === "\\") {
        i += 2;
        continue;
      }
      if (c === quote) quote = null;
      i += 1;
      continue;
    }
    if (c === "'" || c === '"' || c === "`") {
      quote = c;
      i += 1;
      continue;
    }
    if (c === "(") paren += 1;
    else if (c === ")" && paren > 0) paren -= 1;
    else if (c === "[") bracket += 1;
    else if (c === "]" && bracket > 0) bracket -= 1;
    else if (c === "{") brace += 1;
    else if (c === "}" && brace > 0) brace -= 1;
    else if (paren === 0 && bracket === 0 && brace === 0) {
      if (c === "}" || c === "," || c === ";" || c === ")") break;
    }
    i += 1;
  }
  return text.slice(begin, i).trim();
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

function stripTypeAssertions(value) {
  return value
    .replace(/\s+as\s+const\s*$/i, "")
    .replace(/\s+satisfies\s+[\w$.]+\s*$/i, "")
    .replace(/\s+as\s+[\w$.]+\s*$/i, "")
    .trim();
}

function emptyInlineMetrics() {
  return {
    belowFloor: 0,
    pxTotal: 0,
    unrecognized: 0,
    typeOnly: 0,
    assignments: 0,
    shapesBelow: { bare: 0, string: 0, token: 0 },
  };
}

function addShape(metrics, shape) {
  if (shape === "bare" || shape === "string" || shape === "token") {
    metrics.shapesBelow[shape] += 1;
  }
}

function extractInlinePx(rawValue) {
  const value = stripTypeAssertions(rawValue);
  if (!value) return { kind: "empty", items: [] };
  if (TYPE_ONLY_VALUE.test(value)) return { kind: "typeOnly", items: [] };

  const quoted = /^(['"])([\s\S]*)\1$/.exec(value);
  if (quoted) {
    const inner = quoted[2];
    const px = /^(\d+(?:\.\d+)?)px$/i.exec(inner);
    if (px) return { kind: "judged", items: [{ px: Number(px[1]), shape: "string" }] };
    return { kind: "unrecognized", items: [] };
  }

  if (value.startsWith("`")) return { kind: "unrecognized", items: [] };

  const bare = /^(\d+(?:\.\d+)?)$/.exec(value);
  if (bare) return { kind: "judged", items: [{ px: Number(bare[1]), shape: "bare" }] };

  const tokenItems = [];
  for (const match of value.matchAll(/\.?fontSize\s*\[\s*(\d+)\s*\]/g)) {
    tokenItems.push({ px: Number(match[1]), shape: "token" });
  }
  if (tokenItems.length > 0) return { kind: "judged", items: tokenItems };

  const alias = /^[\w$]+\s*\[\s*(\d+)\s*\]$/.exec(value);
  if (alias) return { kind: "judged", items: [{ px: Number(alias[1]), shape: "token" }] };

  const numericAtoms = [...value.matchAll(/(?<![\w.$])(\d+(?:\.\d+)?)(?![\w.$])/g)];
  const looksLikeExpr = /^[\w.$?:\s()|&!=<>+\-*/%]+$/.test(value);
  if (numericAtoms.length > 0 && looksLikeExpr && !value.includes("`")) {
    return {
      kind: "judged",
      items: numericAtoms.map((match) => ({ px: Number(match[1]), shape: "bare" })),
    };
  }

  return { kind: "unrecognized", items: [] };
}

function forEachInlineFontSizeAssignment(text, onValue) {
  let i = 0;
  let quote = null;
  while (i < text.length) {
    const c = text[i];
    const n = text[i + 1];
    if (quote) {
      if (c === "\\") {
        i += 2;
        continue;
      }
      if (c === quote) quote = null;
      i += 1;
      continue;
    }
    if (c === "/" && n === "/") {
      while (i < text.length && text[i] !== "\n") i += 1;
      continue;
    }
    if (c === "/" && n === "*") {
      i += 2;
      while (i + 1 < text.length && !(text[i] === "*" && text[i + 1] === "/")) i += 1;
      i = Math.min(i + 2, text.length);
      continue;
    }
    if (c === "'" || c === '"' || c === "`") {
      quote = c;
      i += 1;
      continue;
    }
    if (c === "f" && text.startsWith("fontSize", i)) {
      if (i > 0 && isIdentChar(text[i - 1])) {
        i += 1;
        continue;
      }
      const after = i + "fontSize".length;
      if (isIdentChar(text[after])) {
        i += 1;
        continue;
      }
      let j = skipWs(text, after);
      if (text[j] === "?") j = skipWs(text, j + 1);
      if (text[j] === ":") {
        onValue(readBalancedValue(text, j + 1));
        i = j + 1;
        continue;
      }
    }
    i += 1;
  }
}

function auditInlineText(text) {
  const metrics = emptyInlineMetrics();
  forEachInlineFontSizeAssignment(text, (rawValue) => {
    const extracted = extractInlinePx(rawValue);
    if (extracted.kind === "typeOnly" || extracted.kind === "empty") {
      metrics.typeOnly += 1;
      return;
    }
    metrics.assignments += 1;
    if (extracted.kind === "unrecognized") {
      metrics.unrecognized += 1;
      return;
    }
    for (const item of extracted.items) {
      metrics.pxTotal += 1;
      if (item.px < FLOOR_PX) {
        metrics.belowFloor += 1;
        addShape(metrics, item.shape);
      }
    }
  });
  return metrics;
}

function collectCss() {
  const files = walkByExtension(scanRoot, [".css"]);
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

function collectInline() {
  const files = walkByExtension(scanRoot, [".ts", ".tsx"]).filter(
    (fullPath) => !isSkippedInlinePath(toRepoPath(fullPath)),
  );
  const results = {};
  const coverage = {
    tsFiles: files.length,
    filesWithBelowFloor: 0,
    assignments: 0,
    pxTotal: 0,
    belowFloor: 0,
    unrecognized: 0,
    typeOnly: 0,
    shapesBelow: { bare: 0, string: 0, token: 0 },
  };
  for (const fullPath of files) {
    const metrics = auditInlineText(readFileSync(fullPath, "utf8"));
    coverage.assignments += metrics.assignments;
    coverage.pxTotal += metrics.pxTotal;
    coverage.belowFloor += metrics.belowFloor;
    coverage.unrecognized += metrics.unrecognized;
    coverage.typeOnly += metrics.typeOnly;
    coverage.shapesBelow.bare += metrics.shapesBelow.bare;
    coverage.shapesBelow.string += metrics.shapesBelow.string;
    coverage.shapesBelow.token += metrics.shapesBelow.token;
    if (metrics.belowFloor > 0) {
      coverage.filesWithBelowFloor += 1;
      results[toRepoPath(fullPath)] = { belowFloor: metrics.belowFloor };
    }
  }
  return { results, coverage };
}

function collect() {
  const css = collectCss();
  const inline = collectInline();
  return {
    cssResults: css.results,
    inlineResults: inline.results,
    coverage: { css: css.coverage, inline: inline.coverage },
  };
}

function sortedResults(results) {
  return Object.fromEntries(Object.entries(results).sort(([a], [b]) => a.localeCompare(b)));
}

function belowFloorOf(entry) {
  if (!entry || typeof entry !== "object") return 0;
  const value = entry.belowFloor;
  return Number.isInteger(value) && value >= 0 ? value : 0;
}

function isPlainObject(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function looksLikeFileMap(value) {
  if (!isPlainObject(value)) return false;
  const keys = Object.keys(value);
  if (keys.length === 0) return true;
  return keys.every((key) => key.includes("/") || key.endsWith(".css") || key.endsWith(".ts") || key.endsWith(".tsx"));
}

function normalizeBaseline(parsed) {
  if (isPlainObject(parsed.css) && (parsed.inline === undefined || isPlainObject(parsed.inline))) {
    return {
      css: parsed.css,
      inline: parsed.inline ?? {},
    };
  }
  if (looksLikeFileMap(parsed) && parsed.css === undefined && parsed.inline === undefined) {
    return { css: parsed, inline: {} };
  }
  throw new Error("baseline must be a JSON object keyed by file path, or { css, inline } namespaces");
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
    return normalizeBaseline(parsed);
  } catch (error) {
    console.error(`Invalid JSON in ${baselineRelativePath}: ${error.message}`);
    process.exit(1);
  }
}

function writeBaseline(cssResults, inlineResults) {
  writeFileSync(
    baselinePath,
    `${JSON.stringify({ css: sortedResults(cssResults), inline: sortedResults(inlineResults) }, null, 2)}\n`,
  );
}

function printCoverage(coverage) {
  const cssJudged = coverage.css.pxTotal + coverage.css.nonPx;
  const cssGapPct = cssJudged === 0 ? 0 : (coverage.css.nonPx / cssJudged) * 100;
  console.log(
    `- coverage: scanned ${coverage.css.cssFiles} css files; px declarations ${coverage.css.pxTotal}; ` +
      `non-px font-size ${coverage.css.nonPx} (${cssGapPct.toFixed(1)}% of font-size decls, not judged)`,
  );
  const inlineJudged = coverage.inline.assignments;
  const inlineGapPct = inlineJudged === 0 ? 0 : (coverage.inline.unrecognized / inlineJudged) * 100;
  console.log(
    `- coverage: scanned ${coverage.inline.tsFiles} ts/tsx files; judged px ${coverage.inline.pxTotal}; ` +
      `unrecognized fontSize ${coverage.inline.unrecognized} (${inlineGapPct.toFixed(1)}% of assignments, not judged); ` +
      `type-only skipped ${coverage.inline.typeOnly}`,
  );
  console.log(
    `- inline below-${FLOOR_PX}px by shape: bare ${coverage.inline.shapesBelow.bare}; ` +
      `string ${coverage.inline.shapesBelow.string}; token ${coverage.inline.shapesBelow.token}`,
  );
}

function compareNamespace(label, results, baselineMap) {
  const failures = [];
  const tightenHints = [];
  const allPaths = new Set([...Object.keys(results), ...Object.keys(baselineMap)]);
  for (const repoPath of [...allPaths].sort()) {
    const actual = belowFloorOf(results[repoPath]);
    const allowed = belowFloorOf(baselineMap[repoPath]);
    if (actual > allowed) {
      failures.push(
        `${repoPath} ${label} belowFloor: ${actual} > baseline ${allowed}. ` +
          `DESIGN.md §3: hard floor ${FLOOR_PX}px (auxiliary text may use 11-12px; below that is a violation).`,
      );
    } else if (actual < allowed) {
      tightenHints.push(`${repoPath}: ${allowed} -> ${actual}`);
    }
  }
  const baselineFiles = Object.keys(baselineMap).length;
  const currentFiles = Object.keys(results).length;
  const baselineSum = Object.values(baselineMap).reduce((sum, entry) => sum + belowFloorOf(entry), 0);
  const currentSum = Object.values(results).reduce((sum, entry) => sum + belowFloorOf(entry), 0);
  return { failures, tightenHints, baselineFiles, currentFiles, baselineSum, currentSum };
}

function ratchetNamespace(results, baselineMap) {
  const tightened = [];
  const blocked = [];
  const next = { ...baselineMap };

  for (const [repoPath, metrics] of Object.entries(results)) {
    const allowed = belowFloorOf(baselineMap[repoPath]);
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

  for (const repoPath of Object.keys(baselineMap)) {
    if (!results[repoPath]) {
      const allowed = belowFloorOf(baselineMap[repoPath]);
      delete next[repoPath];
      tightened.push(`${repoPath}: baseline ${allowed} -> 0`);
    }
  }

  return { next, tightened, blocked };
}

function runSelfTest() {
  const sample = [
    ".a { font-size: 10px; }",
    ".b { font-size: 12px; }",
    ".c { font-size: 10.5px !important; }",
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

  const inlineSample = [
    "const a = { fontSize: 10 };",
    "const b = { fontSize: 12 };",
    'const c = { fontSize: "11px" };',
    "const d = { fontSize: '10px' };",
    "const e = { fontSize: designTokens.fontSize[11] };",
    "const f = { fontSize: dt.fontSize[11] };",
    "const g = { fontSize: fs[11] };",
    "const h = { fontSize: t.fontSize[11] };",
    "const i = { fontSize: fontSize[10] };",
    "const jsx = <span style={{ fontSize: 9 }} />;",
    "// fontSize: 8",
    "/* fontSize: 8 */",
    "const commented = { /* fontSize: 8 */ color: 1 };",
    "type X = { fontSize: number };",
    "const gap = { fontSize: ibTokens.kicker.fontSize };",
    "const tpl = { fontSize: `${x}px` };",
    "const tern = { fontSize: isCompact ? 10 : 11 };",
    "const cellFontSize: 11;",
    "const titleFontSize = 11;",
    'const quoted = "fontSize: 8";',
    "const obj = { 11: 11 };",
    "const kicker = { fontSize: 11 as const };",
  ].join("\n");
  const inlineActual = auditInlineText(inlineSample);
  if (
    inlineActual.belowFloor !== 5 ||
    inlineActual.pxTotal !== 13 ||
    inlineActual.unrecognized !== 2 ||
    inlineActual.typeOnly !== 1 ||
    inlineActual.shapesBelow.bare !== 3 ||
    inlineActual.shapesBelow.string !== 1 ||
    inlineActual.shapesBelow.token !== 1
  ) {
    throw new Error(`inline fontSize counters mismatch: ${JSON.stringify(inlineActual)}`);
  }
  console.log("audit_font_size_floor self-test: ok");
}

function runRatchet() {
  const { cssResults, inlineResults, coverage } = collect();
  const baseline = loadBaseline();
  if (baseline === null) {
    writeBaseline(cssResults, inlineResults);
    console.log(
      `Baseline seeded: css ${Object.keys(cssResults).length} files ` +
        `(below-${FLOOR_PX}px=${coverage.css.belowFloor}); inline ${Object.keys(inlineResults).length} files ` +
        `(below-${FLOOR_PX}px=${coverage.inline.belowFloor}) -> ${baselineRelativePath}`,
    );
    printCoverage(coverage);
    return;
  }

  const cssRatchet = ratchetNamespace(cssResults, baseline.css);
  const inlineRatchet = ratchetNamespace(inlineResults, baseline.inline);
  const tightened = [
    ...cssRatchet.tightened.map((line) => `css ${line}`),
    ...inlineRatchet.tightened.map((line) => `inline ${line}`),
  ];
  const blocked = [
    ...cssRatchet.blocked.map((line) => `css ${line}`),
    ...inlineRatchet.blocked.map((line) => `inline ${line}`),
  ];

  if (tightened.length > 0) {
    writeBaseline(cssRatchet.next, inlineRatchet.next);
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
  const { cssResults, inlineResults, coverage } = collect();
  const baseline = loadBaseline();
  if (baseline === null) {
    console.error(
      `Missing ${baselineRelativePath}. ` +
        "Generate it with: node scripts/audit_font_size_floor.mjs --ratchet",
    );
    process.exit(1);
  }

  const cssCmp = compareNamespace("css", cssResults, baseline.css);
  const inlineCmp = compareNamespace("inline", inlineResults, baseline.inline);
  const failures = [...cssCmp.failures, ...inlineCmp.failures];
  const tightenHints = [
    ...cssCmp.tightenHints.map((line) => `css ${line}`),
    ...inlineCmp.tightenHints.map((line) => `inline ${line}`),
  ];

  if (failures.length > 0) {
    console.error("Font size floor audit failed. Existing debt may remain, but this change grows it.");
    for (const failure of failures) {
      console.error(`- ${failure}`);
    }
    process.exit(1);
  }

  console.log("Font size floor audit passed (no growth over baseline).");
  console.log(
    `- css totals: below-${FLOOR_PX}px ${cssCmp.currentSum}/${cssCmp.baselineSum} across ${cssCmp.currentFiles}/${cssCmp.baselineFiles} files`,
  );
  console.log(
    `- inline totals: below-${FLOOR_PX}px ${inlineCmp.currentSum}/${inlineCmp.baselineSum} across ${inlineCmp.currentFiles}/${inlineCmp.baselineFiles} files`,
  );
  printCoverage(coverage);
  if (tightenHints.length > 0) {
    console.log(`- can tighten: ${tightenHints.length} file(s); re-run with --ratchet`);
    for (const hint of tightenHints) {
      console.log(`  - ${hint}`);
    }
  }
}

function isMainModule() {
  const invoked = process.argv[1] && path.resolve(process.argv[1]);
  if (!invoked) return false;
  return path.normalize(invoked) === path.normalize(fileURLToPath(import.meta.url));
}

if (isMainModule()) {
  if (process.argv.includes("--self-test")) {
    runSelfTest();
    process.exit(0);
  }

  if (process.argv.includes("--ratchet")) {
    runRatchet();
    process.exit(0);
  }

  runAudit();
}

export { auditCssText, auditInlineText, collect };
