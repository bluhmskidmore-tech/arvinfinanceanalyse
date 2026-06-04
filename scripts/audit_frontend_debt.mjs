#!/usr/bin/env node

import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";

const repoRoot = path.resolve(import.meta.dirname, "..");

const baseline = {
  apiClientLines: 560,
  // Phase 4H moves PnL attribution endpoint implementations into pnlAttributionClient.ts.
  apiClientMockOccurrences: 55,
  dashboardStyleFiles: {},
  totalTsxStyleProps: 2166,
  totalStaticTsxStyleProps: 827,
  maxPageStyleProps: {
    "frontend/src/features/balance-analysis/pages/BalanceAnalysisPage.tsx": 13,
    "frontend/src/features/market-data/pages/MarketDataPage.tsx": 1,
    "frontend/src/features/workbench/pages/OperationsAnalysisPage.tsx": 0,
    "frontend/src/layouts/WorkbenchShell.tsx": 0,
    "frontend/src/features/bond-analytics/components/BondAnalyticsInstitutionalCockpit.tsx": 18,
    "frontend/src/features/cross-asset/pages/CrossAssetDriversPage.tsx": 14,
    "frontend/src/features/product-category-pnl/pages/ProductCategoryPnlPage.tsx": 4,
    "frontend/src/features/risk-overview/RiskOverviewPage.tsx": 0,
  },
  maxPageStaticStyleProps: {},
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

function splitTopLevel(input, delimiter) {
  const parts = [];
  let start = 0;
  let quote = null;
  let escaped = false;
  let parenDepth = 0;
  let bracketDepth = 0;
  let braceDepth = 0;

  for (let index = 0; index < input.length; index += 1) {
    const char = input[index];
    if (quote) {
      if (escaped) {
        escaped = false;
      } else if (char === "\\") {
        escaped = true;
      } else if (char === quote) {
        quote = null;
      }
      continue;
    }
    if (char === "\"" || char === "'" || char === "`") {
      quote = char;
      continue;
    }
    if (char === "(") parenDepth += 1;
    if (char === ")") parenDepth -= 1;
    if (char === "[") bracketDepth += 1;
    if (char === "]") bracketDepth -= 1;
    if (char === "{") braceDepth += 1;
    if (char === "}") braceDepth -= 1;
    if (
      char === delimiter &&
      parenDepth === 0 &&
      bracketDepth === 0 &&
      braceDepth === 0
    ) {
      parts.push(input.slice(start, index));
      start = index + 1;
    }
  }
  parts.push(input.slice(start));
  return parts;
}

function isStaticStyleValue(value) {
  const normalized = value.trim();
  return (
    /^-?\d+(?:\.\d+)?$/.test(normalized) ||
    /^"(?:\\.|[^"\\])*"$/.test(normalized) ||
    /^'(?:\\.|[^'\\])*'$/.test(normalized)
  );
}

function isStaticStyleObjectBody(body) {
  const entries = splitTopLevel(body, ",").map((entry) => entry.trim()).filter(Boolean);
  if (entries.length === 0) return false;
  return entries.every((entry) => {
    const [key, ...valueParts] = splitTopLevel(entry, ":");
    if (!key || valueParts.length === 0) return false;
    return isStaticStyleValue(valueParts.join(":"));
  });
}

function findStyleObjectBodies(text) {
  const bodies = [];
  const pattern = /style\s*=\s*\{\s*\{/g;
  let match;
  while ((match = pattern.exec(text))) {
    const objectStart = match.index + match[0].lastIndexOf("{");
    let quote = null;
    let escaped = false;
    let depth = 0;
    for (let index = objectStart; index < text.length; index += 1) {
      const char = text[index];
      if (quote) {
        if (escaped) {
          escaped = false;
        } else if (char === "\\") {
          escaped = true;
        } else if (char === quote) {
          quote = null;
        }
        continue;
      }
      if (char === "\"" || char === "'" || char === "`") {
        quote = char;
        continue;
      }
      if (char === "{") {
        depth += 1;
      } else if (char === "}") {
        depth -= 1;
        if (depth === 0) {
          bodies.push(text.slice(objectStart + 1, index));
          pattern.lastIndex = index + 1;
          break;
        }
      }
    }
  }
  return bodies;
}

function countTsxStyleDebt(text) {
  const totalStyleProps = countMatches(text, /style\s*=/g);
  const staticStyleProps = findStyleObjectBodies(text).filter(isStaticStyleObjectBody).length;
  return {
    totalStyleProps,
    staticStyleProps,
    dynamicStyleProps: totalStyleProps - staticStyleProps,
  };
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
  const tsxStyleSample = [
    '<div style={{ height: 420, width: "100%", opacity: 0.85 }} />',
    '<div style={{ color: toneColor }} />',
    '<div style={{ left: `${percentile}%`, background: markerColor }} />',
    '<div style={chartStyle} />',
    '<div style={{ "--accent": "#ffffff", marginTop: "4px" }} />',
  ].join("\n");
  const tsxStyleDebt = countTsxStyleDebt(tsxStyleSample);
  if (
    tsxStyleDebt.totalStyleProps !== 5 ||
    tsxStyleDebt.staticStyleProps !== 2 ||
    tsxStyleDebt.dynamicStyleProps !== 3
  ) {
    throw new Error(`tsx style debt counter mismatch: ${JSON.stringify(tsxStyleDebt)}`);
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
let totalStaticStyleProps = 0;
let totalDynamicStyleProps = 0;
const pageStyleCounts = new Map();
const pageStaticStyleCounts = new Map();

for (const filePath of tsxFiles) {
  const repoPath = toRepoPath(filePath);
  const styleDebt = countTsxStyleDebt(readFileSync(filePath, "utf8"));
  totalStyleProps += styleDebt.totalStyleProps;
  totalStaticStyleProps += styleDebt.staticStyleProps;
  totalDynamicStyleProps += styleDebt.dynamicStyleProps;
  if (styleDebt.totalStyleProps > 0) {
    pageStyleCounts.set(repoPath, styleDebt.totalStyleProps);
  }
  if (styleDebt.staticStyleProps > 0) {
    pageStaticStyleCounts.set(repoPath, styleDebt.staticStyleProps);
  }
}

assertNoGrowth(
  "frontend TSX style props",
  totalStyleProps,
  baseline.totalTsxStyleProps,
  "Reuse page primitives, tokens, or page-local style modules instead of adding repeated inline styles.",
);
assertNoGrowth(
  "frontend TSX literal static style props",
  totalStaticStyleProps,
  baseline.totalStaticTsxStyleProps,
  "Literal static inline style objects should move into CSS classes, page primitives, or style modules.",
);
notes.push(`frontend TSX dynamic style props: ${totalDynamicStyleProps}`);

for (const [repoPath, max] of Object.entries(baseline.maxPageStyleProps)) {
  const actual = pageStyleCounts.get(repoPath) ?? 0;
  assertNoGrowth(
    `${repoPath} style props`,
    actual,
    max,
    "Pay down or keep flat when touching this page.",
  );
}

for (const [repoPath, max] of Object.entries(baseline.maxPageStaticStyleProps)) {
  const actual = pageStaticStyleCounts.get(repoPath) ?? 0;
  assertNoGrowth(
    `${repoPath} literal static style props`,
    actual,
    max,
    "Literal static inline style objects should move into CSS classes, page primitives, or style modules.",
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
