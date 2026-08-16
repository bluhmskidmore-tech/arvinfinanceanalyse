#!/usr/bin/env node

import { readdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import path from "node:path";

const repoRoot = path.resolve(import.meta.dirname, "..");

// Debt baselines live in scripts/debt-baselines.json (namespace "frontend").
// Policy (see the _policy field there): baselines only ratchet DOWN; any
// increase requires tech-lead sign-off recorded in the PR. Baseline history
// predating the JSON extraction is preserved in the git log of this file.
const baselineRelativePath = "scripts/debt-baselines.json";
const baselinePath = path.join(repoRoot, baselineRelativePath);

// Mirrored by tests/test_development_hygiene_guards.py. The self-test fails
// when scripts/debt-baselines.json silently drops one of these
// protectedMonolithFiles entries, so removing a guarded monolith from the
// baseline file is as loud as raising its limit.
const requiredProtectedMonolithFiles = [
  "scripts/mcp/moss_project_mcp.py",
  "tests/test_project_mcp_servers.py",
  "frontend/src/api/contracts.ts",
  "frontend/src/features/macro-toolkit/pages/MacroToolkitPage.tsx",
  "frontend/src/features/product-category-pnl/pages/ProductCategoryPnlPage.tsx",
  "frontend/src/features/product-category-pnl/pages/productCategoryPnlPageModel.ts",
  "backend/app/services/pnl_service.py",
];

function fail(message) {
  console.error(message);
  process.exit(1);
}

function isCounterValue(value) {
  return Number.isInteger(value) && value >= 0;
}

function loadBaselineDocument() {
  let raw;
  try {
    raw = readFileSync(baselinePath, "utf8");
  } catch (error) {
    fail(`Cannot read ${baselineRelativePath}: ${error.message}`);
  }
  let document;
  try {
    document = JSON.parse(raw);
  } catch (error) {
    fail(`Invalid JSON in ${baselineRelativePath}: ${error.message}`);
  }
  if (typeof document._policy !== "string" || document._policy.trim() === "") {
    fail(`${baselineRelativePath} must declare a non-empty _policy field (ratchet-only baselines).`);
  }
  const frontend = document.frontend;
  if (!frontend || typeof frontend !== "object") {
    fail(`${baselineRelativePath} must contain a "frontend" namespace object.`);
  }
  for (const key of [
    "apiClientLines",
    "apiClientMockOccurrences",
    "totalTsxStyleProps",
    "totalStaticTsxStyleProps",
    "featuresEmDashLiterals",
    "featuresSemanticProfitLossRefs",
    "featuresEchartsForReactImportFiles",
  ]) {
    if (!isCounterValue(frontend[key])) {
      fail(`${baselineRelativePath}: frontend.${key} must be a non-negative integer.`);
    }
  }
  for (const key of ["dashboardStyleFiles", "maxPageStyleProps", "maxPageStaticStyleProps", "protectedMonolithFiles"]) {
    if (!frontend[key] || typeof frontend[key] !== "object") {
      fail(`${baselineRelativePath}: frontend.${key} must be an object.`);
    }
  }
  return document;
}

const baselineDocument = loadBaselineDocument();
const baseline = baselineDocument.frontend;

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

// ---- frontend/src/features debt counters (2026-08-13 登记) ----------------
// 口径（三项共用同一文件集）：frontend/src/features 下的 .ts/.tsx 文件，
// 排除文件名含 ".test." 的测试文件。
// - featuresEmDashLiterals: 独立字符串字面量 "—" / '—' / `—`（整个字面量恰为
//   一个 U+2014）的出现次数。长文案内部的破折号属于合法文案，不计入；目标是
//   驱动缺省值占位改为 import EM_DASH（src/utils/format.ts / src/pageModel）。
// - featuresSemanticProfitLossRefs: `semantic.profit` / `semantic.loss` 引用
//   次数（含 designTokens.color.semantic.* 等任何点访问）。深色路由禁止直灌
//   浅色语义色，应走 TONE_COLOR / TONE_CSS_VAR 入口；本计数是收敛代理指标。
// - featuresEchartsForReactImportFiles: 文件内出现 "echarts-for-react" 模块
//   说明符（静态或动态 import）的文件数，即绕过 BaseChart 直连
//   echarts-for-react 的代理指标；按文件计数而非出现次数。

const FEATURES_EM_DASH_LITERAL_PATTERN = /(["'`])\u2014\1/g;
const FEATURES_SEMANTIC_PROFIT_LOSS_PATTERN = /\bsemantic\.(?:profit|loss)\b/g;
const FEATURES_ECHARTS_FOR_REACT_PATTERN = /["']echarts-for-react["']/;

function isFeaturesCountedFile(filePath) {
  return (
    (filePath.endsWith(".ts") || filePath.endsWith(".tsx")) &&
    !path.basename(filePath).includes(".test.")
  );
}

function collectFeaturesDebt() {
  const files = walkFiles(path.join(repoRoot, "frontend/src/features"), isFeaturesCountedFile);
  let emDashLiterals = 0;
  let semanticProfitLossRefs = 0;
  let echartsForReactImportFiles = 0;
  for (const filePath of files) {
    const text = readFileSync(filePath, "utf8");
    emDashLiterals += countMatches(text, FEATURES_EM_DASH_LITERAL_PATTERN);
    semanticProfitLossRefs += countMatches(text, FEATURES_SEMANTIC_PROFIT_LOSS_PATTERN);
    if (FEATURES_ECHARTS_FOR_REACT_PATTERN.test(text)) {
      echartsForReactImportFiles += 1;
    }
  }
  return { emDashLiterals, semanticProfitLossRefs, echartsForReactImportFiles };
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
  if (countLines("first\nsecond\n") !== 2) {
    throw new Error("line counter must ignore the trailing newline");
  }
  const featuresSample = [
    'const a = value ?? "\u2014";',
    "const b = ready ? fmt(x) : '\u2014';",
    "const c = `\u2014`;",
    'const copy = "\u8de8\u671f\u5bf9\u6bd4\u2014\u2014\u957f\u6587\u6848\u4e2d\u7684\u7834\u6298\u53f7\u4e0d\u8ba1\u5165";',
    "const up = designTokens.color.semantic.profit;",
    "const down = theme.semantic.loss;",
    "const label = semanticProfit; // \u975e\u70b9\u8bbf\u95ee\u4e0d\u8ba1\u5165",
  ].join("\n");
  const emDashLiteralCount = countMatches(featuresSample, FEATURES_EM_DASH_LITERAL_PATTERN);
  if (emDashLiteralCount !== 3) {
    throw new Error(`features em-dash literal counter mismatch: ${emDashLiteralCount}`);
  }
  const semanticRefCount = countMatches(featuresSample, FEATURES_SEMANTIC_PROFIT_LOSS_PATTERN);
  if (semanticRefCount !== 2) {
    throw new Error(`features semantic.profit/loss counter mismatch: ${semanticRefCount}`);
  }
  if (
    !FEATURES_ECHARTS_FOR_REACT_PATTERN.test('import ReactECharts from "echarts-for-react";') ||
    !FEATURES_ECHARTS_FOR_REACT_PATTERN.test("const mod = await import('echarts-for-react');") ||
    FEATURES_ECHARTS_FOR_REACT_PATTERN.test('import { BaseChart } from "../components/BaseChart";')
  ) {
    throw new Error("features echarts-for-react import detector mismatch");
  }
  for (const repoPath of requiredProtectedMonolithFiles) {
    if (!baseline.protectedMonolithFiles[repoPath]) {
      throw new Error(
        `${baselineRelativePath} lost the protected monolith baseline for ${repoPath}; ` +
          "removing an entry requires tech-lead sign-off and updating requiredProtectedMonolithFiles.",
      );
    }
  }
  for (const [repoPath, policy] of Object.entries(baseline.protectedMonolithFiles)) {
    if (!Number.isInteger(policy.maxLines) || policy.maxLines <= 0) {
      throw new Error(`invalid protected monolith maxLines for ${repoPath}`);
    }
    if (typeof policy.routeHint !== "string" || policy.routeHint.trim() === "") {
      throw new Error(`missing protected monolith routeHint for ${repoPath}`);
    }
  }
  console.log("audit_frontend_debt self-test: ok");
}

// Measures every governed counter and pairs it with its baseline plus a
// ratchet setter so the default audit and --ratchet share one measurement pass.
function collectMeasurements() {
  const measurements = [];

  const apiClient = readText("frontend/src/api/client.ts");
  measurements.push({
    kind: "limit",
    label: "api/client.ts lines",
    actual: countLines(apiClient),
    max: baseline.apiClientLines,
    hint: "Move endpoint implementation into a domain client instead of growing the monolith.",
    ratchet: (value) => {
      baseline.apiClientLines = value;
    },
  });
  measurements.push({
    kind: "limit",
    label: "api/client.ts mock occurrences",
    actual: countMatches(apiClient, /mock/gi),
    max: baseline.apiClientMockOccurrences,
    hint: "Move mock payloads out of api/client.ts or reduce existing mock coupling.",
    ratchet: (value) => {
      baseline.apiClientMockOccurrences = value;
    },
  });

  for (const [repoPath, policy] of Object.entries(baseline.protectedMonolithFiles)) {
    measurements.push({
      kind: "limit",
      label: `${repoPath} lines`,
      actual: countLines(readText(repoPath)),
      max: policy.maxLines,
      hint: policy.routeHint,
      ratchet: (value) => {
        policy.maxLines = value;
      },
    });
  }

  for (const [repoPath, limits] of Object.entries(baseline.dashboardStyleFiles)) {
    const filename = path.basename(repoPath);
    const debt = countDashboardStyleDebt(readText(repoPath));
    const dashboardChecks = [
      ["hardcodedHexes", `${filename} hard-coded hex occurrences`, "Tokenize repeated homepage colors before growing the cockpit style layer."],
      ["gradients", `${filename} gradient occurrences`, "Reuse existing cockpit/home surfaces instead of adding new gradient treatments."],
      ["repeatingGradients", `${filename} repeating gradient occurrences`, "Avoid adding repeating gradient treatments; replace decorative patterns with governed surfaces first."],
      ["important", `${filename} !important occurrences`, "Move ownership-conflicting overrides into the correct homepage layer before adding more !important rules."],
    ];
    for (const [metric, label, hint] of dashboardChecks) {
      measurements.push({
        kind: "limit",
        label,
        actual: debt[metric],
        max: limits[metric],
        hint,
        ratchet: (value) => {
          limits[metric] = value;
        },
      });
    }
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

  measurements.push({
    kind: "limit",
    label: "frontend TSX style props",
    actual: totalStyleProps,
    max: baseline.totalTsxStyleProps,
    hint: "Reuse page primitives, tokens, or page-local style modules instead of adding repeated inline styles.",
    ratchet: (value) => {
      baseline.totalTsxStyleProps = value;
    },
  });
  measurements.push({
    kind: "limit",
    label: "frontend TSX literal static style props",
    actual: totalStaticStyleProps,
    max: baseline.totalStaticTsxStyleProps,
    hint: "Literal static inline style objects should move into CSS classes, page primitives, or style modules.",
    ratchet: (value) => {
      baseline.totalStaticTsxStyleProps = value;
    },
  });
  measurements.push({
    kind: "info",
    label: "frontend TSX dynamic style props",
    actual: totalDynamicStyleProps,
  });

  const featuresDebt = collectFeaturesDebt();
  measurements.push({
    kind: "limit",
    label: "features em-dash string literals",
    actual: featuresDebt.emDashLiterals,
    max: baseline.featuresEmDashLiterals,
    hint: "Import EM_DASH from src/utils/format or src/pageModel instead of the string literal \"\u2014\".",
    ratchet: (value) => {
      baseline.featuresEmDashLiterals = value;
    },
  });
  measurements.push({
    kind: "limit",
    label: "features semantic.profit/loss references",
    actual: featuresDebt.semanticProfitLossRefs,
    max: baseline.featuresSemanticProfitLossRefs,
    hint: "Use TONE_COLOR / TONE_CSS_VAR from src/utils/tone.ts instead of referencing semantic.profit/loss directly.",
    ratchet: (value) => {
      baseline.featuresSemanticProfitLossRefs = value;
    },
  });
  measurements.push({
    kind: "limit",
    label: "features direct echarts-for-react import files",
    actual: featuresDebt.echartsForReactImportFiles,
    max: baseline.featuresEchartsForReactImportFiles,
    hint: "Render charts through the shared BaseChart wrapper instead of importing echarts-for-react directly.",
    ratchet: (value) => {
      baseline.featuresEchartsForReactImportFiles = value;
    },
  });

  for (const [repoPath, max] of Object.entries(baseline.maxPageStyleProps)) {
    measurements.push({
      kind: "limit",
      label: `${repoPath} style props`,
      actual: pageStyleCounts.get(repoPath) ?? 0,
      max,
      hint: "Pay down or keep flat when touching this page.",
      ratchet: (value) => {
        baseline.maxPageStyleProps[repoPath] = value;
      },
    });
  }

  for (const [repoPath, max] of Object.entries(baseline.maxPageStaticStyleProps)) {
    measurements.push({
      kind: "limit",
      label: `${repoPath} literal static style props`,
      actual: pageStaticStyleCounts.get(repoPath) ?? 0,
      max,
      hint: "Literal static inline style objects should move into CSS classes, page primitives, or style modules.",
      ratchet: (value) => {
        baseline.maxPageStaticStyleProps[repoPath] = value;
      },
    });
  }

  return measurements;
}

function runAudit() {
  const failures = [];
  const notes = [];

  for (const measurement of collectMeasurements()) {
    if (measurement.kind === "info") {
      notes.push(`${measurement.label}: ${measurement.actual}`);
      continue;
    }
    if (measurement.actual > measurement.max) {
      failures.push(`${measurement.label}: ${measurement.actual} > baseline ${measurement.max}. ${measurement.hint}`);
    } else {
      notes.push(`${measurement.label}: ${measurement.actual}/${measurement.max}`);
    }
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
}

function runRatchet() {
  const tightened = [];
  const blocked = [];

  for (const measurement of collectMeasurements()) {
    if (measurement.kind !== "limit") continue;
    if (measurement.actual < measurement.max) {
      measurement.ratchet(measurement.actual);
      tightened.push(`${measurement.label}: baseline ${measurement.max} -> ${measurement.actual}`);
    } else if (measurement.actual > measurement.max) {
      blocked.push(
        `${measurement.label}: actual ${measurement.actual} > baseline ${measurement.max}; ` +
          `--ratchet never raises a baseline. Reduce the debt, or obtain tech-lead sign-off and edit ${baselineRelativePath} manually.`,
      );
    }
  }

  if (tightened.length > 0) {
    writeFileSync(baselinePath, `${JSON.stringify(baselineDocument, null, 2)}\n`, "utf8");
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

  if (blocked.length > 0) {
    console.error(`\nRefused to raise ${blocked.length} baseline(s):`);
    for (const line of blocked) {
      console.error(`- ${line}`);
    }
    process.exit(1);
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
