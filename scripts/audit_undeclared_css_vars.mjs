#!/usr/bin/env node

/**
 * Undeclared CSS custom property guardrail (ratchet-only).
 *
 * `color: var(--never-declared)` with no fallback is invalid at computed-value
 * time. The declaration is not ignored — it resolves to `unset`, so an
 * inherited property silently takes the parent's value and a non-inherited one
 * silently takes its initial value (a panel background becomes transparent, a
 * border-color becomes currentColor). Nothing errors, nothing logs, and the
 * page still renders, which is why this class of defect survives review,
 * snapshots, and screenshot diffs. Adding `!important` makes it worse: the
 * declaration first wins the cascade against a correct rule, then drops.
 *
 * This already happened here. `frontend/src/styles/dashboardCockpit.css`
 * (globally applied via `styles/global.css`) references a `--cockpit-*` palette
 * across ~40 declarations on the home cockpit's own selectors. The palette was
 * declared in `global.css` at commit b4ead374f and was lost when 3fb0119ab
 * split the global stylesheet; the references stayed behind.
 *
 * A reference is counted only when the name is never declared anywhere, in any
 * of these forms:
 *   - a CSS declaration `--name: value`;
 *   - `element.style.setProperty("--name", …)`;
 *   - a quoted key in a token map injected as an inline style
 *     (`{"--sa-color-text": "var(--dh-api-ink)"}` in stockAnalysisTokens.ts).
 * References carrying a fallback (`var(--name, …)`) are reported separately and
 * are not failures: the fallback is what renders.
 *
 * Prose mentions of wildcard families (`var(--dh-api-*)` in a file header) and
 * assertion strings in tests are excluded.
 *
 * Baseline lives in scripts/audit_undeclared_css_vars.baseline.json and is
 * ratchet-only: counts may go down, never up. Regenerate after paying debt
 * down with:  node scripts/audit_undeclared_css_vars.mjs --ratchet
 */

import { readdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import path from "node:path";

const repoRoot = path.resolve(import.meta.dirname, "..");
const baselinePath = path.join(repoRoot, "scripts", "audit_undeclared_css_vars.baseline.json");

const SCAN_DIRS = ["frontend/src"];
const EXTRA_FILES = ["frontend/index.html"];
const EXT = /\.(css|ts|tsx|js|mjs|html)$/;
const SKIP = /node_modules|[\\/]\.git[\\/]|[\\/]dist[\\/]/;
const IS_TEST = /[\\/]test[\\/]|\.(test|spec)\.[jt]sx?$/;

const DECLARATION = /(?:^|[;{,\s])(--[A-Za-z0-9_-]+)\s*:/g;
const SET_PROPERTY = /setProperty\(\s*["'`](--[A-Za-z0-9_-]+)["'`]/g;
const QUOTED_KEY = /["'`](--[A-Za-z0-9_-]+)["'`]\s*:/g;
const CONSTANT_BINDING =
  /\b(?:const|let|var)\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*["'`](--[A-Za-z0-9_-]+)["'`]/g;
// `var(--prefix-${tone}-bg, fallback)`: the interpolation ends the name, and the
// fallback sits after the closing brace rather than right after the name
const VAR_REFERENCE = /var\(\s*(--[A-Za-z0-9_-]+)\s*(,|\$\{)?/g;
const scanErrors = [];

function errorMessage(error) {
  return error instanceof Error ? error.message : String(error);
}

function walk(dir, out = []) {
  let entries;
  try {
    entries = readdirSync(dir);
  } catch (error) {
    scanErrors.push(`cannot read directory ${toRepoPath(dir)}: ${errorMessage(error)}`);
    return out;
  }
  for (const entry of entries) {
    const full = path.join(dir, entry);
    if (SKIP.test(full)) continue;
    let stats;
    try {
      stats = statSync(full);
    } catch (error) {
      scanErrors.push(`cannot inspect ${toRepoPath(full)}: ${errorMessage(error)}`);
      continue;
    }
    if (stats.isDirectory()) walk(full, out);
    else if (EXT.test(full)) out.push(full);
  }
  return out;
}

function toRepoPath(fullPath) {
  return path.relative(repoRoot, fullPath).replace(/\\/g, "/");
}

function stripComments(source) {
  let result = "";
  let quote = null;
  let lineComment = false;
  let blockComment = false;
  for (let index = 0; index < source.length; index += 1) {
    const char = source[index];
    const next = source[index + 1];
    if (lineComment) {
      if (char === "\n") {
        lineComment = false;
        result += char;
      } else {
        result += " ";
      }
      continue;
    }
    if (blockComment) {
      if (char === "*" && next === "/") {
        result += "  ";
        index += 1;
        blockComment = false;
      } else {
        result += char === "\n" ? "\n" : " ";
      }
      continue;
    }
    if (quote) {
      result += char;
      if (char === "\\" && next !== undefined) {
        result += next;
        index += 1;
      } else if (char === quote) {
        quote = null;
      }
      continue;
    }
    if (char === '"' || char === "'" || char === "`") {
      quote = char;
      result += char;
    } else if (char === "/" && next === "/") {
      result += "  ";
      index += 1;
      lineComment = true;
    } else if (char === "/" && next === "*") {
      result += "  ";
      index += 1;
      blockComment = true;
    } else {
      result += char;
    }
  }
  return result;
}

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function stripStringContents(source) {
  let result = "";
  let quote = null;
  for (let index = 0; index < source.length; index += 1) {
    const char = source[index];
    const next = source[index + 1];
    if (quote) {
      if (char === "\\" && next !== undefined) {
        result += "  ";
        index += 1;
      } else if (char === quote) {
        quote = null;
        result += " ";
      } else {
        result += char === "\n" ? "\n" : " ";
      }
    } else if (char === '"' || char === "'" || char === "`") {
      quote = char;
      result += " ";
    } else {
      result += char;
    }
  }
  return result;
}

function collectVerifiedConstantDeclarations(source, declared) {
  const codeOnly = stripStringContents(source);
  for (const match of source.matchAll(CONSTANT_BINDING)) {
    const identifier = escapeRegExp(match[1]);
    const usedAsComputedKey = new RegExp(`\\[\\s*${identifier}\\s*\\]\\s*:`).test(codeOnly);
    const usedBySetProperty = new RegExp(`\\bsetProperty\\(\\s*${identifier}\\b`).test(codeOnly);
    if (usedAsComputedKey || usedBySetProperty) declared.add(match[2]);
  }
}

/** A wildcard family mention such as `var(--dh-api-*)` documents a convention. */
function isWildcardMention(line, name) {
  const idx = line.indexOf("var(" + name);
  if (idx === -1) return false;
  const after = line.slice(idx + 4 + name.length);
  return after.trimStart().startsWith("*");
}

const files = [];
for (const relativePath of SCAN_DIRS) {
  const full = path.join(repoRoot, relativePath);
  try {
    const stats = statSync(full);
    if (!stats.isDirectory()) {
      scanErrors.push(`scan root ${relativePath} is not a directory`);
    } else {
      walk(full, files);
    }
  } catch (error) {
    scanErrors.push(`cannot inspect scan root ${relativePath}: ${errorMessage(error)}`);
  }
}
for (const rel of EXTRA_FILES) {
  const full = path.join(repoRoot, rel);
  try {
    if (statSync(full).isFile()) files.push(full);
  } catch (error) {
    if (error?.code !== "ENOENT") {
      scanErrors.push(`cannot inspect optional file ${rel}: ${errorMessage(error)}`);
    }
  }
}

const declared = new Set();
const sources = new Map();
for (const file of files) {
  let text;
  try {
    text = readFileSync(file, "utf8");
  } catch (error) {
    scanErrors.push(`cannot read ${toRepoPath(file)}: ${errorMessage(error)}`);
    continue;
  }
  const sourceWithoutComments = stripComments(text);
  sources.set(file, sourceWithoutComments);
  for (const m of sourceWithoutComments.matchAll(DECLARATION)) declared.add(m[1]);
  for (const m of sourceWithoutComments.matchAll(SET_PROPERTY)) declared.add(m[1]);
  for (const m of sourceWithoutComments.matchAll(QUOTED_KEY)) declared.add(m[1]);
  collectVerifiedConstantDeclarations(sourceWithoutComments, declared);
}

if (scanErrors.length > 0) {
  console.error("undeclared css vars: scan incomplete; baseline comparison and update refused.");
  for (const error of scanErrors) console.error(`- ${error}`);
  process.exit(1);
}

const actual = {};
const detail = [];
let fallbackOnly = 0;
let interpolated = 0;
for (const [file, text] of sources) {
  const repoPath = toRepoPath(file);
  if (IS_TEST.test(repoPath)) continue;
  let bare = 0;
  const names = new Set();
  text.split(/\r?\n/).forEach((line, index) => {
    for (const m of line.matchAll(VAR_REFERENCE)) {
      const name = m[1];
      if (declared.has(name)) continue;
      if (isWildcardMention(line, name)) continue;
      if (m[2] === ",") {
        fallbackOnly += 1;
        continue;
      }
      if (m[2] === "${") {
        // the real name is built at runtime; the static prefix is not judgeable
        interpolated += 1;
        continue;
      }
      bare += 1;
      names.add(name);
      detail.push({ repoPath, line: index + 1, name, text: line.trim().slice(0, 100) });
    }
  });
  if (bare > 0) actual[repoPath] = bare;
}

function loadBaseline() {
  let document;
  try {
    document = JSON.parse(readFileSync(baselinePath, "utf8"));
  } catch {
    console.error(
      `undeclared css vars: cannot read ${toRepoPath(baselinePath)}; create and review an explicit zero baseline first.`,
    );
    process.exit(1);
  }
  if (document === null || typeof document !== "object" || Array.isArray(document)) {
    console.error("undeclared css vars: invalid baseline; top level must be an object.");
    process.exit(1);
  }
  for (const [file, count] of Object.entries(document)) {
    if (!Number.isInteger(count) || count < 0) {
      console.error(`undeclared css vars: invalid baseline count for ${file}; expected a non-negative integer.`);
      process.exit(1);
    }
  }
  return document;
}

const baseline = loadBaseline();

if (process.argv.includes("--ratchet") || process.argv.includes("--update-baseline")) {
  const blocked = [];
  const tightened = [];
  const filesToCompare = new Set([...Object.keys(baseline), ...Object.keys(actual)]);
  for (const file of filesToCompare) {
    const count = actual[file] ?? 0;
    const allowed = baseline[file] ?? 0;
    if (count > allowed) {
      blocked.push(`${file}: actual ${count} > baseline ${allowed}`);
    } else if (count < allowed) {
      tightened.push(`${file}: baseline ${allowed} -> ${count}`);
    }
  }
  if (blocked.length > 0) {
    console.error("undeclared css vars: refused to raise baseline; baseline file left unchanged.");
    for (const line of blocked) console.error(`- ${line}`);
    process.exit(1);
  }
  if (tightened.length === 0) {
    console.log("undeclared css vars: no baseline lowered; baseline file left unchanged.");
    process.exit(0);
  }
  writeFileSync(baselinePath, `${JSON.stringify(actual, null, 2)}\n`, "utf8");
  console.log(`undeclared css vars: baseline tightened (${Object.keys(actual).length} file(s))`);
  process.exit(0);
}

const failures = [];
for (const [file, count] of Object.entries(actual)) {
  const allowed = baseline[file] ?? 0;
  if (count > allowed) {
    const names = [...new Set(detail.filter((d) => d.repoPath === file).map((d) => d.name))];
    failures.push(`  ${file}: ${count} fallback-less use(s) > baseline ${allowed} (${names.slice(0, 6).join(", ")})`);
  }
}

const improved = [];
for (const [file, allowed] of Object.entries(baseline)) {
  const count = actual[file] ?? 0;
  if (count < allowed) improved.push(`  ${file}: ${allowed} -> ${count}`);
}

const totalActual = Object.values(actual).reduce((sum, n) => sum + n, 0);
const totalBaseline = Object.values(baseline).reduce((sum, n) => sum + n, 0);
console.log(
  `undeclared css vars: scanned ${sources.size} file(s); ${declared.size} declared name(s); ` +
    `fallback-less uses of undeclared names ${totalActual}/${totalBaseline} ` +
    `(${fallbackOnly} carry a fallback, ${interpolated} are built at runtime; neither is judged)`,
);

if (improved.length > 0) {
  console.log("Improved (run --ratchet to lock in):");
  for (const line of improved) console.log(line);
}

if (failures.length > 0) {
  console.error("Undeclared custom properties referenced without a fallback:");
  for (const line of failures) console.error(line);
  console.error(
    "\nSuch a declaration is invalid at computed-value time and resolves to `unset`: inherited\n" +
      "properties take the parent value, non-inherited ones take the initial value (transparent\n" +
      "background, currentColor border). Either declare the name, give the reference a fallback,\n" +
      "or point it at an existing token.",
  );
  process.exit(1);
}

console.log("undeclared css vars: no new fallback-less references.");
