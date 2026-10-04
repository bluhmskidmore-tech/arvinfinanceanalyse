#!/usr/bin/env node
/**
 * DESIGN §3 / §10.2, approved aesthetic plan A5: CSS debt must only decrease.
 * Reuses PostCSS already shipped with Vite; no new dependency or command family.
 * Runs from style:audit and debt:audit. --ratchet only removes existing debt.
 *
 * Scope: every frontend/src CSS file, including shared and shell styles. Only
 * tokens.css is exempt from rawColor/fontScale (the canonical CSS token source).
 * Existing home font sizes are retained in the baseline under DESIGN §3/§9.2;
 * this does not permit new off-scale declarations. TS/TSX remains covered by
 * the existing visual-token/font-floor guards and the browser compliance audit.
 *
 * Each identity includes file, selector/at-rule context, property and violating
 * value. Removing old debt cannot fund a different violation with the same count.
 * Pure token font references require the browser audit to check resolved sizes.
 */
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { existsSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = path.resolve(import.meta.dirname, "..");
const frontendRequire = createRequire(path.join(repoRoot, "frontend/package.json"));
const postcss = frontendRequire("postcss");
const baselinePath = path.join(repoRoot, "scripts/audit_frontend_style_architecture.baseline.json");
const metrics = ["rawColor", "fontScale", "important", "pageHas"];
const fontSizes = new Set([11, 12, 13, 14, 20, 24]);
const tokenSource = "frontend/src/styles/tokens.css";
const namedColors = new Set(("aliceblue antiquewhite aqua aquamarine azure beige bisque black blanchedalmond blue blueviolet brown burlywood cadetblue chartreuse chocolate coral cornflowerblue cornsilk crimson cyan darkblue darkcyan darkgoldenrod darkgray darkgreen darkgrey darkkhaki darkmagenta darkolivegreen darkorange darkorchid darkred darksalmon darkseagreen darkslateblue darkslategray darkslategrey darkturquoise darkviolet deeppink deepskyblue dimgray dimgrey dodgerblue firebrick floralwhite forestgreen fuchsia gainsboro ghostwhite gold goldenrod gray green greenyellow grey honeydew hotpink indianred indigo ivory khaki lavender lavenderblush lawngreen lemonchiffon lightblue lightcoral lightcyan lightgoldenrodyellow lightgray lightgreen lightgrey lightpink lightsalmon lightseagreen lightskyblue lightslategray lightslategrey lightsteelblue lightyellow lime limegreen linen magenta maroon mediumaquamarine mediumblue mediumorchid mediumpurple mediumseagreen mediumslateblue mediumspringgreen mediumturquoise mediumvioletred midnightblue mintcream mistyrose moccasin navajowhite navy oldlace olive olivedrab orange orangered orchid palegoldenrod palegreen paleturquoise palevioletred papayawhip peachpuff peru pink plum powderblue purple rebeccapurple red rosybrown royalblue saddlebrown salmon sandybrown seagreen seashell sienna silver skyblue slateblue slategray slategrey snow springgreen steelblue tan teal thistle tomato turquoise violet wheat white whitesmoke yellow yellowgreen").split(" "));
const normalize = (value) => value.replace(/\s+/g, " ").trim();
const fingerprint = (value) => createHash("sha256").update(value).digest("hex").slice(0, 24);

function context(node) {
  const parts = [];
  for (let parent = node; parent && parent.type !== "root"; parent = parent.parent) {
    if (parent.type === "rule") parts.unshift(normalize(parent.selector));
    if (parent.type === "atrule") parts.unshift(`@${parent.name} ${normalize(parent.params)}`.trim());
  }
  return parts.join(" | ");
}

function selectorScope(node, detail) {
  const rule = node.type === "rule" ? node : node.parent;
  if (rule?.type !== "rule") return undefined;
  // Narrowing a flat selector list is safe; nested rules are kept exact-only.
  for (let parent = rule.parent; parent; parent = parent.parent) {
    if (parent.type === "rule") return undefined;
  }
  return {
    declaration: fingerprint(`${context(rule.parent)}\n${normalize(detail)}`),
    selectors: [...new Set(postcss.list.comma(rule.selector).map((selector) => fingerprint(normalize(selector))))].sort(),
  };
}

function rawColors(value) {
  // Text and URL contents are not CSS color operands. Keep var() fallbacks.
  const text = value.replace(/url\(\s*(?:"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|[^)])*\)/gi, " ")
    .replace(/"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'/g, " ");
  const values = [];
  const pattern = /#[\da-f]{8}\b|#[\da-f]{6}\b|#[\da-f]{4}\b|#[\da-f]{3}\b|\b(?:rgba?|hsla?|hwb|lab|lch|oklab|oklch|color)\s*\(|[a-z][a-z-]*/gi;
  for (const match of text.matchAll(pattern)) {
    const atom = match[0].toLowerCase();
    // --white, e.g., is a token name, never a named color literal.
    if (atom.startsWith("#") || atom.includes("(") || (namedColors.has(atom) && text[match.index - 1] !== "-")) {
      values.push(atom);
    }
  }
  return values;
}

function offScale(value) {
  const clean = normalize(value.toLowerCase());
  if (/^(?:inherit|initial|unset|revert|revert-layer)$/.test(clean)) return false;
  if (/^var\(\s*--[\w-]+\s*\)$/.test(clean)) return false;
  const variable = /^var\(\s*--[\w-]+\s*,\s*([\s\S]+)\)$/.exec(clean);
  if (variable) return offScale(variable[1]);
  const px = /^(\d+(?:\.\d+)?)px$/.exec(clean);
  return !px || !fontSizes.has(Number(px[1]));
}

function hasArguments(selector) {
  const results = [];
  const pattern = /:has\s*\(/gi;
  for (const match of selector.matchAll(pattern)) {
    let depth = 1;
    let quote = null;
    const start = match.index + match[0].length;
    let index = start;
    for (; index < selector.length && depth; index += 1) {
      const char = selector[index];
      if (char === "\\") { index += 1; continue; }
      if (quote) { if (char === quote) quote = null; continue; }
      if (char === '"' || char === "'") { quote = char; continue; }
      if (char === "(") depth += 1;
      if (char === ")") depth -= 1;
    }
    results.push(selector.slice(start, depth ? index : index - 1));
  }
  return results;
}

function pageHas(argument) {
  return /\[\s*data-(?:moss-theme-scope|publication-capture|route)(?:\s|[=\]])/i.test(argument)
    || /\[\s*data-testid\s*=\s*["'][^"']*(?:-page|module-workbench-home|module-home-portfolio-cockpit)["']\s*\]/i.test(argument)
    || /\.[\w-]*(?:-page|-page-shell)(?![\w-])/i.test(argument)
    || /\.(?:market-finance-workbench|workbench-shell-root--publication-capture|marketPageMain)(?![\w-])/.test(argument);
}

export function auditCss(text, repoPath) {
  const root = postcss.parse(text, { from: repoPath });
  const findings = [];
  const add = (metric, node, detail) => {
    const selector = context(node);
    const identity = `${selector}\n${normalize(detail)}`;
    findings.push({ metric, id: fingerprint(identity), selector, detail: normalize(detail), line: node.source.start.line, scope: selectorScope(node, detail) });
  };
  root.walkDecls((decl) => {
    const property = decl.prop.toLowerCase();
    if (decl.important) add("important", decl, `${property}: ${decl.value} !important`);
    if (repoPath === tokenSource) return;
    for (const color of rawColors(decl.value)) {
      add("rawColor", decl, `${property}: ${decl.value} [${color}]`);
    }
    if (property === "font-size" && offScale(decl.value)) add("fontScale", decl, `${property}: ${decl.value}`);
    if (property === "font") {
      const size = /(?:^|\s)(\d*\.?\d+(?:px|rem|em|%|vw|vh|pt)|(?:xx?-)?small|medium|(?:xx?-)?large|smaller|larger)(?=[\s/]|$)/i.exec(decl.value);
      if (size && offScale(size[1])) add("fontScale", decl, `${property}: ${decl.value}`);
    }
  });
  root.walkRules((rule) => {
    for (const argument of hasArguments(rule.selector)) {
      if (pageHas(argument)) add("pageHas", rule, `:has(${normalize(argument)})`);
    }
  });
  return findings;
}

function cssFiles(dir, files = []) {
  for (const entry of readdirSync(dir, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) cssFiles(full, files);
    else if (entry.isFile() && entry.name.endsWith(".css")) files.push(full);
  }
  return files;
}

export function collect(root = repoRoot) {
  const files = {};
  const selectorScopes = {};
  const details = [];
  let scanned = 0;
  for (const full of cssFiles(path.join(root, "frontend/src"))) {
    scanned += 1;
    const repoPath = path.relative(root, full).replace(/\\/g, "/");
    for (const finding of auditCss(readFileSync(full, "utf8"), repoPath)) {
      files[repoPath] ??= {};
      files[repoPath][finding.metric] ??= {};
      const counts = files[repoPath][finding.metric];
      counts[finding.id] = (counts[finding.id] ?? 0) + 1;
      if (finding.scope) {
        selectorScopes[repoPath] ??= {};
        selectorScopes[repoPath][finding.id] = finding.scope;
      }
      details.push({ repoPath, ...finding });
    }
  }
  return { files, details, scanned, selectorScopes };
}

function totals(files) {
  const result = Object.fromEntries(metrics.map((metric) => [metric, 0]));
  for (const entry of Object.values(files)) {
    for (const metric of metrics) {
      result[metric] += Object.values(entry[metric] ?? {}).reduce((sum, count) => sum + count, 0);
    }
  }
  return result;
}

export function growth(current, baseline, currentScopes = {}, baselineScopes = {}) {
  const failures = [];
  for (const [file, entry] of Object.entries(current)) {
    for (const [metric, identities] of Object.entries(entry)) {
      // Exact identities get their budget first. A deleted selector from a
      // comma group may then consume unused budget from a strict superset,
      // with the same declaration and at-rule context. Consume once only.
      const remaining = { ...baseline[file]?.[metric] };
      const pending = [];
      for (const [id, count] of Object.entries(identities)) {
        const allowed = Math.min(count, remaining[id] ?? 0);
        remaining[id] = (remaining[id] ?? 0) - allowed;
        if (count > allowed) pending.push({ id, count, allowed });
      }
      for (const item of pending) {
        const actualScope = currentScopes[file]?.[item.id];
        if (actualScope) {
          for (const [baselineId, budget] of Object.entries(remaining)) {
            if (budget <= 0 || item.allowed === item.count) continue;
            const baseScope = baselineScopes[file]?.[baselineId];
            if (!baseScope || baseScope.declaration !== actualScope.declaration) continue;
            if (actualScope.selectors.length >= baseScope.selectors.length) continue;
            if (!actualScope.selectors.every((selector) => baseScope.selectors.includes(selector))) continue;
            const used = Math.min(budget, item.count - item.allowed);
            remaining[baselineId] -= used;
            item.allowed += used;
          }
        }
        if (item.count > item.allowed) failures.push({ file, metric, ...item });
      }
    }
  }
  return failures;
}

function loadBaseline() {
  const baseline = JSON.parse(readFileSync(baselinePath, "utf8"));
  assert.equal(baseline.version, 1, "A5 baseline version must be 1");
  assert.ok(baseline.files && typeof baseline.files === "object" && !Array.isArray(baseline.files), "A5 baseline files must be an object");
  for (const [file, entry] of Object.entries(baseline.files)) {
    assert.ok(file.startsWith("frontend/src/") && file.endsWith(".css"), `Invalid CSS baseline path: ${file}`);
    assert.ok(entry && typeof entry === "object" && !Array.isArray(entry), `Invalid baseline entry: ${file}`);
    for (const [metric, identities] of Object.entries(entry)) {
      assert.ok(metrics.includes(metric), `Unknown A5 metric: ${metric}`);
      assert.ok(identities && typeof identities === "object" && !Array.isArray(identities), `Invalid A5 identities: ${file}/${metric}`);
      for (const [id, count] of Object.entries(identities)) {
        assert.match(id, /^[a-f0-9]{24}$/);
        assert.ok(Number.isInteger(count) && count > 0, `Invalid count: ${file}/${metric}/${id}`);
      }
    }
  }
  for (const [file, scopes] of Object.entries(baseline.selectorScopes ?? {})) {
    assert.ok(baseline.files[file], `Unexpected selector scope file: ${file}`);
    for (const [id, scope] of Object.entries(scopes)) {
      assert.ok(Object.values(baseline.files[file]).some((entries) => entries[id]), `Unbudgeted selector scope: ${file}/${id}`);
      assert.match(scope.declaration, /^[a-f0-9]{24}$/);
      assert.ok(Array.isArray(scope.selectors) && scope.selectors.length > 0, "Selector scope must be nonempty");
      assert.equal(new Set(scope.selectors).size, scope.selectors.length, "Duplicate selector identity");
      for (const selector of scope.selectors) assert.match(selector, /^[a-f0-9]{24}$/);
    }
  }
  return baseline;
}

export function runAudit({ ratchet = false } = {}) {
  const baseline = loadBaseline();
  const current = collect(); // Parse/read failures abort; partial scans never rewrite debt.
  const failures = growth(current.files, baseline.files, current.selectorScopes, baseline.selectorScopes);
  const actual = totals(current.files);
  const allowed = totals(baseline.files);
  console.log(`A5 CSS architecture audit: ${current.scanned} CSS files; ${metrics.map((key) => `${key} ${actual[key]}/${allowed[key]}`).join(", ")}.`);
  console.log("Scope: all frontend/src CSS; tokens.css exempt only for rawColor/fontScale. Existing home font sizes: DESIGN §3/§9.2, approved D-B. Token font values need browser verification.");
  if (failures.length) {
    console.error(`A5 FAIL: ${failures.length} new/increased violation identities. Baseline unchanged; reductions elsewhere cannot offset them.`);
    for (const failure of failures) {
      const finding = current.details.find((item) => item.repoPath === failure.file && item.metric === failure.metric && item.id === failure.id);
      console.error(`- ${failure.file}:${finding.line} ${failure.metric} ${failure.count}/${failure.allowed} | ${finding.selector} | ${finding.detail}`);
    }
    return 1;
  }
  if (ratchet) {
    baseline.files = current.files;
    baseline.selectorScopes = current.selectorScopes;
    writeFileSync(baselinePath, `${JSON.stringify(baseline, null, 2)}\n`, "utf8");
    console.log("A5 baseline ratcheted down (no new identities or increased counts).");
  }
  console.log("A5 CSS architecture audit: PASS (no new violations).");
  return 0;
}

function selfTest() {
  const findings = auditCss(`
    /* .fake:has([data-moss-theme-scope="fake"]) { color: #fff !important; } */
    .a { color: var(--ink, #fff); border-color: rgba(1, 2, 3, .5); background: white; content: "#abc !important"; font-size: 16px; }
    .b { font-size: var(--size, 12.5px); font: 500 1rem/1.5 sans-serif; color: var(--white); }
    .c { font-size: 12px; color: currentColor; background: transparent; }
    @media (min-width: 720px) { .shell:has(:is([data-moss-theme-scope="demo"], .demo-page)) { padding: 12px !important; } }
    .a:has(> :only-child), .b:has(input:checked) { gap: 8px; }
  `, "frontend/src/features/demo/Demo.css");
  assert.deepEqual(Object.fromEntries(metrics.map((key) => [key, findings.filter((item) => item.metric === key).length])), { rawColor: 3, fontScale: 3, important: 1, pageHas: 1 });
  const canonical = auditCss('.x:has([data-moss-theme-scope="x"]) { color: #abcd; font-size: 16px !important; }', tokenSource);
  assert.deepEqual(canonical.map((item) => item.metric).sort(), ["important", "pageHas"]);
  assert.equal(auditCss('.x { color: var(--white); }', 'frontend/src/a.css').length, 0);
  assert.equal(auditCss('.x { color: #aabbccdd; }', 'frontend/src/a.css').length, 1);
  const old = { "frontend/src/a.css": { important: { existing: 1 } } };
  assert.equal(growth(old, old).length, 0);
  assert.equal(growth({}, old).length, 0);
  assert.equal(growth({ "frontend/src/a.css": { important: { replacement: 1 } } }, old).length, 1);
  assert.equal(growth({ "frontend/src/a.css": { important: { existing: 2 } } }, old).length, 1);
  const file = "frontend/src/a.css";
  const scope = (selectors, declaration = "same declaration/context") => ({ selectors, declaration });
  const original = { [file]: { important: { group: 1 } } };
  const originalScopes = { [file]: { group: scope(["a", "b", "c"]) } };
  const subset = { [file]: { important: { smaller: 1 } } };
  assert.equal(growth(subset, original, { [file]: { smaller: scope(["b", "c"]) } }, originalScopes).length, 0);
  assert.equal(growth(subset, original, { [file]: { smaller: scope(["b", "replacement"]) } }, originalScopes).length, 1);
  assert.equal(growth(subset, original, { [file]: { smaller: scope(["a", "b", "c", "d"]) } }, originalScopes).length, 1);
  assert.equal(growth(subset, original, { [file]: { smaller: scope(["b"], "changed declaration/context") } }, originalScopes).length, 1);
  assert.equal(growth({ [file]: { important: { smaller: 1, duplicate: 1 } } }, original, { [file]: { smaller: scope(["b"]), duplicate: scope(["c"]) } }, originalScopes).length, 1);
  assert.equal(growth({ [file]: { important: { group: 1, smaller: 1 } } }, original, { [file]: { group: scope(["a", "b", "c"]), smaller: scope(["b"]) } }, originalScopes).length, 1);
  const withPriority = auditCss('.a, .b { color: #fff !important; font-size: 16px !important; }', file);
  const withoutPriority = auditCss('.a, .b { color: #fff; font-size: 16px; }', file);
  assert.deepEqual(withPriority.filter((item) => item.metric !== "important"), withoutPriority);
  assert.throws(() => auditCss('.a { color: #fff;', 'frontend/src/a.css'));
  console.log("audit_frontend_style_architecture self-test: ok (CSS parsing, token source scope, same-count replacement, growth, parse failure).");
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    const args = process.argv.slice(2);
    assert.ok(args.every((arg) => ["--self-test", "--ratchet"].includes(arg)), "Usage: node scripts/audit_frontend_style_architecture.mjs [--self-test | --ratchet]");
    if (args.includes("--self-test")) selfTest();
    else {
      assert.ok(existsSync(baselinePath), "Missing reviewed A5 baseline. Initialization is a one-time P0 action; --ratchet never creates one.");
      process.exitCode = runAudit({ ratchet: args.includes("--ratchet") });
    }
  } catch (error) {
    console.error(`A5 CSS architecture audit failed: ${error.message}`);
    process.exitCode = 1;
  }
}
