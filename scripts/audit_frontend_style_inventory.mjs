#!/usr/bin/env node
/**
 * Full frontend style inventory report.
 *
 * This is intentionally read-only: it maps current visual/layout debt so pages
 * can be migrated one at a time without changing business metric behavior.
 */

import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";

const repoRoot = path.resolve(import.meta.dirname, "..");
const frontendSrc = path.join(repoRoot, "frontend/src");

const PAGE_RE = /(?:Page|View)\.tsx$/;
const SOURCE_RE = /\.(tsx?|css|module\.css)$/i;
const HEX_RE = /#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\b/g;
const STYLE_PROP_RE = /\bstyle\s*=/g;
const GRADIENT_RE = /\b(?:linear|radial)-gradient\(/g;
const CSS_VAR_DEF_RE = /^\s*(--moss-[\w-]+)\s*:/gm;

const PRIMITIVES = [
  "PageDecisionHero",
  "DataStatusStrip",
  "PageFilterTray",
  "KpiBand",
  "AnalysisGrid",
  "EvidencePanel",
  "PageStateSurface",
];

const TOP_N = 12;

function walkFiles(dir, predicate, out = []) {
  for (const entry of readdirSync(dir)) {
    const fullPath = path.join(dir, entry);
    const stats = statSync(fullPath);
    if (stats.isDirectory()) {
      walkFiles(fullPath, predicate, out);
    } else if (predicate(fullPath)) {
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

function extractCssVarDuplicates(text) {
  const counts = new Map();
  for (const match of text.matchAll(CSS_VAR_DEF_RE)) {
    counts.set(match[1], (counts.get(match[1]) ?? 0) + 1);
  }
  return [...counts.entries()]
    .filter(([, count]) => count > 1)
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
}

function analyzeSourceFile(fullPath) {
  const text = readFileSync(fullPath, "utf8");
  const repoPath = toRepoPath(fullPath);
  const primitiveHits = Object.fromEntries(
    PRIMITIVES.map((name) => [name, new RegExp(`\\b${name}\\b`).test(text)]),
  );

  return {
    repoPath,
    isPage: PAGE_RE.test(path.basename(fullPath)),
    primitiveHits,
    hardcodedHexes: countMatches(text, HEX_RE),
    styleProps: countMatches(text, STYLE_PROP_RE),
    gradients: countMatches(text, GRADIENT_RE),
    duplicateCssVars: repoPath.endsWith(".css") ? extractCssVarDuplicates(text) : [],
  };
}

function sortByMetric(rows, key) {
  return rows
    .filter((row) => row[key] > 0)
    .sort((a, b) => b[key] - a[key] || a.repoPath.localeCompare(b.repoPath))
    .slice(0, TOP_N);
}

function fmtCheck(value) {
  return value ? "Y" : "-";
}

function pagePrimitiveRow(row) {
  return [
    row.repoPath,
    ...PRIMITIVES.map((name) => fmtCheck(row.primitiveHits[name])),
    row.styleProps,
    row.hardcodedHexes,
  ].join(" | ");
}

function metricRows(title, rows, key) {
  if (rows.length === 0) return [`## ${title}`, "", "No hotspots found.", ""].join("\n");

  return [
    `## ${title}`,
    "",
    "| File | Count |",
    "| --- | ---: |",
    ...rows.map((row) => `| ${row.repoPath} | ${row[key]} |`),
    "",
  ].join("\n");
}

function duplicateRows(rows) {
  const duplicates = rows.flatMap((row) =>
    row.duplicateCssVars.map(([name, count]) => ({ repoPath: row.repoPath, name, count })),
  );
  if (duplicates.length === 0) {
    return ["## Duplicate CSS Token Definitions", "", "No duplicate --moss-* definitions found.", ""].join("\n");
  }

  return [
    "## Duplicate CSS Token Definitions",
    "",
    "| File | Token | Count |",
    "| --- | --- | ---: |",
    ...duplicates
      .sort((a, b) => b.count - a.count || a.name.localeCompare(b.name))
      .slice(0, TOP_N)
      .map((item) => `| ${item.repoPath} | \`${item.name}\` | ${item.count} |`),
    "",
  ].join("\n");
}

function buildReport(rows) {
  const pages = rows.filter((row) => row.isPage).sort((a, b) => a.repoPath.localeCompare(b.repoPath));
  const pagePrimitiveHeader = [
    "## Page V2 Primitive Adoption",
    "",
    `| Page | ${PRIMITIVES.join(" | ")} | style= | #hex |`,
    `| --- | ${PRIMITIVES.map(() => ":---:").join(" | ")} | ---: | ---: |`,
    ...pages.map(pagePrimitiveRow).map((row) => `| ${row} |`),
    "",
  ].join("\n");

  const totals = rows.reduce(
    (acc, row) => {
      acc.files += 1;
      acc.pages += row.isPage ? 1 : 0;
      acc.styleProps += row.styleProps;
      acc.hardcodedHexes += row.hardcodedHexes;
      acc.gradients += row.gradients;
      return acc;
    },
    { files: 0, pages: 0, styleProps: 0, hardcodedHexes: 0, gradients: 0 },
  );

  return [
    "# Frontend Style Inventory",
    "",
    "Read-only report for gradual page-level layout, typography, and color governance.",
    "",
    "## Totals",
    "",
    `- Scanned files: ${totals.files}`,
    `- Candidate page/view files: ${totals.pages}`,
    `- TSX style props: ${totals.styleProps}`,
    `- Hard-coded hex occurrences: ${totals.hardcodedHexes}`,
    `- Gradient occurrences: ${totals.gradients}`,
    "",
    pagePrimitiveHeader,
    metricRows("Inline Style Hotspots", sortByMetric(rows, "styleProps"), "styleProps"),
    metricRows("Hard-Coded Hex Hotspots", sortByMetric(rows, "hardcodedHexes"), "hardcodedHexes"),
    metricRows("Gradient Hotspots", sortByMetric(rows, "gradients"), "gradients"),
    duplicateRows(rows),
  ].join("\n");
}

function runInventory() {
  const files = walkFiles(frontendSrc, (filePath) => SOURCE_RE.test(filePath));
  return buildReport(files.map(analyzeSourceFile));
}

function runSelfTest() {
  const fixtureRows = [
    {
      repoPath: "frontend/src/features/demo/DemoPage.tsx",
      isPage: true,
      primitiveHits: {
        PageDecisionHero: true,
        DataStatusStrip: false,
        PageFilterTray: false,
        KpiBand: true,
        AnalysisGrid: false,
        EvidencePanel: false,
        PageStateSurface: true,
      },
      hardcodedHexes: 2,
      styleProps: 3,
      gradients: 1,
      duplicateCssVars: [],
    },
    {
      repoPath: "frontend/src/styles/demo.css",
      isPage: false,
      primitiveHits: Object.fromEntries(PRIMITIVES.map((name) => [name, false])),
      hardcodedHexes: 1,
      styleProps: 0,
      gradients: 0,
      duplicateCssVars: [["--moss-color-primary-600", 2]],
    },
  ];
  const report = buildReport(fixtureRows);
  const required = [
    "# Frontend Style Inventory",
    "Page V2 Primitive Adoption",
    "frontend/src/features/demo/DemoPage.tsx",
    "Inline Style Hotspots",
    "Duplicate CSS Token Definitions",
    "--moss-color-primary-600",
  ];
  for (const needle of required) {
    if (!report.includes(needle)) {
      console.error(`self-test failed: missing ${needle}`);
      process.exit(2);
    }
  }
  console.log("audit_frontend_style_inventory self-test: ok");
}

if (process.argv.includes("--self-test")) {
  runSelfTest();
} else {
  console.log(runInventory());
}
