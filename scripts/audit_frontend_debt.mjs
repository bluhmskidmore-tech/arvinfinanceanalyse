#!/usr/bin/env node

import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";

const repoRoot = path.resolve(import.meta.dirname, "..");

const baseline = {
  apiClientLines: 1207,
  // Phase 4H moves PnL attribution endpoint implementations into pnlAttributionClient.ts.
  apiClientMockOccurrences: 136,
  dashboardStyleFiles: {},
  totalTsxStyleProps: 3308,
  maxPageStyleProps: {
    "frontend/src/features/balance-analysis/pages/BalanceAnalysisPage.tsx": 203,
    "frontend/src/features/market-data/pages/MarketDataPage.tsx": 130,
    "frontend/src/features/workbench/pages/OperationsAnalysisPage.tsx": 91,
    "frontend/src/layouts/WorkbenchShell.tsx": 123,
    "frontend/src/features/bond-analytics/components/BondAnalyticsInstitutionalCockpit.tsx": 104,
    "frontend/src/features/cross-asset/pages/CrossAssetDriversPage.tsx": 103,
    "frontend/src/features/product-category-pnl/pages/ProductCategoryPnlPage.tsx": 88,
    "frontend/src/features/risk-overview/RiskOverviewPage.tsx": 81,
  },
};

function readText(relativePath) {
  return readFileSync(path.join(repoRoot, relativePath), "utf8");
}

function countLines(text) {
  if (text.length === 0) return 0;
  return text.endsWith("\n") ? text.split(/\r?\n/).length - 1 : text.split(/\r?\n/).length;
}

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

function countDashboardStyleDebt(text) {
  return {
    hardcodedHexes: countMatches(text, /#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\b/g),
    gradients: countMatches(text, /\b(?:repeating-)?(?:linear|radial)-gradient\(/g),
    repeatingGradients: countMatches(text, /\brepeating-(?:linear|radial)-gradient\(/g),
    important: countMatches(text, /!important\b/g),
  };
}

function runSelfTest() {
  if (!baseline.dashboardStyleFiles) {
    throw new Error("dashboard style debt baselines are required");
  }
  const sample = [
    ".demo {",
    "  color: #ffffff;",
    "  border-color: #d9e3ef;",
    "  background: linear-gradient(180deg, #ffffff, transparent);",
    "  mask-image: repeating-linear-gradient(90deg, transparent 0 1px, #000 1px 2px);",
    "  padding: 0 !important;",
    "}",
  ].join("\n");
  const actual = countDashboardStyleDebt(sample);
  if (
    actual.hardcodedHexes !== 4 ||
    actual.gradients !== 2 ||
    actual.repeatingGradients !== 1 ||
    actual.important !== 1
  ) {
    throw new Error(`dashboard style debt counter mismatch: ${JSON.stringify(actual)}`);
  }
  console.log("audit_frontend_debt self-test: ok");
}

if (process.argv.includes("--self-test")) {
  runSelfTest();
  process.exit(0);
}

const failures = [];
const notes = [];

function assertNoGrowth(label, actual, max, hint) {
  if (actual > max) {
    failures.push(`${label}: ${actual} > baseline ${max}. ${hint}`);
  } else {
    notes.push(`${label}: ${actual}/${max}`);
  }
}

const apiClient = readText("frontend/src/api/client.ts");

assertNoGrowth(
  "api/client.ts lines",
  countLines(apiClient),
  baseline.apiClientLines,
  "Move endpoint implementation into a domain client instead of growing the monolith.",
);
assertNoGrowth(
  "api/client.ts mock occurrences",
  countMatches(apiClient, /mock/gi),
  baseline.apiClientMockOccurrences,
  "Move mock payloads out of api/client.ts or reduce existing mock coupling.",
);

for (const [repoPath, limits] of Object.entries(baseline.dashboardStyleFiles)) {
  const filename = path.basename(repoPath);
  const debt = countDashboardStyleDebt(readText(repoPath));
  assertNoGrowth(
    `${filename} hard-coded hex occurrences`,
    debt.hardcodedHexes,
    limits.hardcodedHexes,
    "Tokenize repeated homepage colors before growing the cockpit style layer.",
  );
  assertNoGrowth(
    `${filename} gradient occurrences`,
    debt.gradients,
    limits.gradients,
    "Reuse existing cockpit/home surfaces instead of adding new gradient treatments.",
  );
  assertNoGrowth(
    `${filename} repeating gradient occurrences`,
    debt.repeatingGradients,
    limits.repeatingGradients,
    "Avoid adding repeating gradient treatments; replace decorative patterns with governed surfaces first.",
  );
  assertNoGrowth(
    `${filename} !important occurrences`,
    debt.important,
    limits.important,
    "Move ownership-conflicting overrides into the correct homepage layer before adding more !important rules.",
  );
}

const tsxFiles = walkFiles(
  path.join(repoRoot, "frontend/src"),
  (filePath) => filePath.endsWith(".tsx"),
);

let totalStyleProps = 0;
const pageStyleCounts = new Map();

for (const filePath of tsxFiles) {
  const repoPath = toRepoPath(filePath);
  const styleProps = countMatches(readFileSync(filePath, "utf8"), /style\s*=/g);
  totalStyleProps += styleProps;
  if (styleProps > 0) {
    pageStyleCounts.set(repoPath, styleProps);
  }
}

assertNoGrowth(
  "frontend TSX style props",
  totalStyleProps,
  baseline.totalTsxStyleProps,
  "Reuse page primitives, tokens, or page-local style modules instead of adding repeated inline styles.",
);

for (const [repoPath, max] of Object.entries(baseline.maxPageStyleProps)) {
  const actual = pageStyleCounts.get(repoPath) ?? 0;
  assertNoGrowth(
    `${repoPath} style props`,
    actual,
    max,
    "Pay down or keep flat when touching this page.",
  );
}

if (failures.length > 0) {
  console.error("Frontend debt audit failed. Current debt may remain, but this change grows it.");
  for (const failure of failures) {
    console.error(`- ${failure}`);
  }
  console.error("\nPassing checks:");
  for (const note of notes) {
    console.error(`- ${note}`);
  }
  process.exit(1);
}

console.log("Frontend debt audit passed (no growth over baseline).");
for (const note of notes) {
  console.log(`- ${note}`);
}
