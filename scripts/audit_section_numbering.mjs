#!/usr/bin/env node

/**
 * Section numbering guardrail (ratchet-only).
 *
 * `SectionHead` prints its ordinal from a CSS counter. A counter that is never
 * reset by an ancestor gets implicitly created on the printing element itself,
 * so every head in the page starts over at 01. The failure is silent: the
 * numbers render, they are just all the same. No snapshot, DOM query, or
 * computed-style assertion catches it, because jsdom does not evaluate
 * `counter()` and a screenshot diff of "01 01 01" looks like valid output.
 *
 * A numbered head therefore needs exactly one of:
 *   - an ancestor carrying SECTION_HEAD_STACK_CLASSNAME (the primitive's own
 *     numbering domain), or
 *   - `numbered={{ counter, increment? }}` naming a counter whose reset point
 *     the page's own CSS already owns (used where a page had a numbering
 *     sequence before the migration and still has unmigrated consumers on it), or
 *   - `numbered={false}` where the head is a panel/card title outside any
 *     sequence.
 *
 * This audit is static, so it judges per domain rather than per element: a
 * domain that renders two or more defaulted (implicitly numbered) heads without
 * any file referencing SECTION_HEAD_STACK_CLASSNAME cannot be numbering them
 * correctly. It cannot prove the container actually wraps the heads when one is
 * present — that remains covered by SectionHead's dev-time self-check (which
 * warns at render) and by browser-level probes.
 *
 * Baseline lives in scripts/audit_section_numbering.baseline.json and is
 * ratchet-only: counts may go down, never up. Regenerate after paying debt
 * down with:  node scripts/audit_section_numbering.mjs --ratchet
 */

import { readdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import path from "node:path";

const repoRoot = path.resolve(import.meta.dirname, "..");
const baselinePath = path.join(repoRoot, "scripts", "audit_section_numbering.baseline.json");

const SCAN_ROOT = path.join(repoRoot, "frontend", "src");
const SKIP = /node_modules|[\\/]\.git[\\/]|[\\/]dist[\\/]|__pycache__/;
// the primitive's own directory defines the contract; its tests exercise every shape on purpose
const SELF = /[\\/]components[\\/]layout[\\/]/;
const IS_TEST = /\.(test|spec)\.tsx?$/;
const STACK_TOKEN = "SECTION_HEAD_STACK_CLASSNAME";
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
    else if (/\.tsx$/.test(full) && !IS_TEST.test(full) && !SELF.test(full)) out.push(full);
  }
  return out;
}

function toRepoPath(fullPath) {
  return path.relative(repoRoot, fullPath).replace(/\\/g, "/");
}

/** Domain = the subtree that can plausibly share one numbering container. */
function domainOf(repoPath) {
  const rel = repoPath.replace("frontend/src/", "");
  const parts = rel.split("/");
  return parts.length > 1 ? `${parts[0]}/${parts[1]}` : parts[0];
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

function hasStackTokenReference(expression) {
  const tokenPattern = new RegExp(`\\b${STACK_TOKEN}\\b`);
  if (tokenPattern.test(stripStringContents(expression))) return true;
  const templateReferencePattern = new RegExp(
    `\\$\\{[^}]*\\b${STACK_TOKEN}\\b[^}]*\\}`,
  );
  return templateReferencePattern.test(expression);
}

function hasStackClassUsage(source) {
  const classNamePattern = /\bclassName\s*=\s*\{/g;
  let match;
  while ((match = classNamePattern.exec(source))) {
    const expressionStart = source.indexOf("{", match.index);
    let quote = null;
    let depth = 0;
    for (let index = expressionStart; index < source.length; index += 1) {
      const char = source[index];
      if (quote) {
        if (char === "\\") {
          index += 1;
        } else if (char === quote) {
          quote = null;
        }
        continue;
      }
      if (char === '"' || char === "'" || char === "`") {
        quote = char;
      } else if (char === "{") {
        depth += 1;
      } else if (char === "}") {
        depth -= 1;
        if (depth === 0) {
          const expression = source.slice(expressionStart + 1, index);
          if (hasStackTokenReference(expression)) return true;
          classNamePattern.lastIndex = index + 1;
          break;
        }
      }
    }
  }
  return false;
}

function classifyHeads(source) {
  const tags = [...source.matchAll(/<SectionHead\b([\s\S]*?)(?:\/>|>)/g)].map((m) => m[1]);
  let defaulted = 0;
  let unnumbered = 0;
  let external = 0;
  for (const attrs of tags) {
    if (!/\bnumbered=/.test(attrs)) defaulted += 1;
    else if (/\bnumbered=\{false\}/.test(attrs)) unnumbered += 1;
    else external += 1;
  }
  return { defaulted, unnumbered, external };
}

const domains = new Map();
let scanned = 0;
for (const file of walk(SCAN_ROOT)) {
  let source;
  try {
    source = readFileSync(file, "utf8");
  } catch (error) {
    scanErrors.push(`cannot read ${toRepoPath(file)}: ${errorMessage(error)}`);
    continue;
  }
  scanned += 1;
  const sourceWithoutComments = stripComments(source);
  if (!sourceWithoutComments.includes("<SectionHead")) continue;
  const repoPath = toRepoPath(file);
  const key = domainOf(repoPath);
  const counts = classifyHeads(sourceWithoutComments);
  const entry = domains.get(key) ?? { defaulted: 0, unnumbered: 0, external: 0, stackFiles: 0 };
  entry.defaulted += counts.defaulted;
  entry.unnumbered += counts.unnumbered;
  entry.external += counts.external;
  if (hasStackClassUsage(sourceWithoutComments)) entry.stackFiles += 1;
  domains.set(key, entry);
}

if (scanErrors.length > 0) {
  console.error("section numbering: scan incomplete; baseline comparison and update refused.");
  for (const error of scanErrors) console.error(`- ${error}`);
  process.exit(1);
}

const actual = {};
for (const [domain, entry] of domains) {
  if (entry.defaulted >= 2 && entry.stackFiles === 0) actual[domain] = entry.defaulted;
}

function loadBaseline() {
  let document;
  try {
    document = JSON.parse(readFileSync(baselinePath, "utf8"));
  } catch {
    console.error(
      `section numbering: cannot read ${toRepoPath(baselinePath)}; create and review an explicit zero baseline first.`,
    );
    process.exit(1);
  }
  if (document === null || typeof document !== "object" || Array.isArray(document)) {
    console.error("section numbering: invalid baseline; top level must be an object.");
    process.exit(1);
  }
  for (const [domain, count] of Object.entries(document)) {
    if (!Number.isInteger(count) || count < 0) {
      console.error(`section numbering: invalid baseline count for ${domain}; expected a non-negative integer.`);
      process.exit(1);
    }
  }
  return document;
}

const baseline = loadBaseline();

if (process.argv.includes("--ratchet") || process.argv.includes("--update-baseline")) {
  const blocked = [];
  const tightened = [];
  const domainsToCompare = new Set([...Object.keys(baseline), ...Object.keys(actual)]);
  for (const domain of domainsToCompare) {
    const count = actual[domain] ?? 0;
    const allowed = baseline[domain] ?? 0;
    if (count > allowed) {
      blocked.push(`${domain}: actual ${count} > baseline ${allowed}`);
    } else if (count < allowed) {
      tightened.push(`${domain}: baseline ${allowed} -> ${count}`);
    }
  }
  if (blocked.length > 0) {
    console.error("section numbering: refused to raise baseline; baseline file left unchanged.");
    for (const line of blocked) console.error(`- ${line}`);
    process.exit(1);
  }
  if (tightened.length === 0) {
    console.log("section numbering: no baseline lowered; baseline file left unchanged.");
    process.exit(0);
  }
  writeFileSync(baselinePath, `${JSON.stringify(actual, null, 2)}\n`, "utf8");
  console.log(`section numbering: baseline tightened (${Object.keys(actual).length} domain(s))`);
  process.exit(0);
}

const failures = [];
for (const [domain, count] of Object.entries(actual)) {
  const allowed = baseline[domain] ?? 0;
  if (count > allowed) {
    failures.push(`  ${domain}: ${count} defaulted numbered head(s), no ${STACK_TOKEN} > baseline ${allowed}`);
  }
}

const improved = [];
for (const [domain, allowed] of Object.entries(baseline)) {
  const count = actual[domain] ?? 0;
  if (count < allowed) improved.push(`  ${domain}: ${allowed} -> ${count}`);
}

const totals = [...domains.values()].reduce(
  (acc, e) => ({
    defaulted: acc.defaulted + e.defaulted,
    unnumbered: acc.unnumbered + e.unnumbered,
    external: acc.external + e.external,
  }),
  { defaulted: 0, unnumbered: 0, external: 0 },
);
const totalActual = Object.values(actual).reduce((sum, n) => sum + n, 0);
const totalBaseline = Object.values(baseline).reduce((sum, n) => sum + n, 0);
console.log(
  `section numbering: scanned ${scanned} tsx; ${domains.size} domain(s) render SectionHead ` +
    `(stack-numbered ${totals.defaulted}, external-counter ${totals.external}, unnumbered ${totals.unnumbered})`,
);
console.log(`section numbering: at-risk heads ${totalActual}/${totalBaseline}`);

if (improved.length > 0) {
  console.log("Improved (run --ratchet to lock in):");
  for (const line of improved) console.log(line);
}

if (failures.length > 0) {
  console.error("Section numbering domains without a numbering container:");
  for (const line of failures) console.error(line);
  console.error(
    "\nTwo or more SectionHead instances numbering off the primitive's own counter, with no\n" +
      `${STACK_TOKEN} anywhere in the domain, means each head implicitly creates its own\n` +
      "counter and every section renders 01. Pick one:\n" +
      `  - wrap the sequence in <div className={${STACK_TOKEN}}>;\n` +
      "  - pass numbered={{ counter: \"<page-counter>\" }} when the page's CSS owns the reset point;\n" +
      "  - pass numbered={false} for panel/card titles that are not part of a sequence.",
  );
  process.exit(1);
}

console.log("section numbering: every numbered sequence has a numbering domain.");
