#!/usr/bin/env node

/**
 * Encoding integrity guardrail (ratchet-only).
 *
 * U+FFFD (REPLACEMENT CHARACTER) never belongs in a source file: it is what a
 * UTF-8 decoder emits when it is handed bytes from another encoding. Every
 * occurrence means the file was read/written through a wrong code page at some
 * point, and the original characters are unrecoverable from the file itself.
 *
 * This machine's PowerShell 5.1 defaults to the system ANSI code page (936),
 * so `Get-Content`/`Set-Content`/`>` on a BOM-less UTF-8 file silently corrupts
 * every CJK character. That has already happened twice in this repository's
 * history (commit 8c75b268 corrupted marketHome.module.css comments), and once
 * more during an agent session. Text tooling must go through Node's `fs` or a
 * dedicated editor instead.
 *
 * Baseline lives in scripts/audit_encoding_integrity.baseline.json and is
 * ratchet-only: counts may go down, never up. Regenerate after paying debt
 * down with:  node scripts/audit_encoding_integrity.mjs --ratchet
 */

import { readdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import path from "node:path";

const repoRoot = path.resolve(import.meta.dirname, "..");
const baselinePath = path.join(repoRoot, "scripts", "audit_encoding_integrity.baseline.json");

const REQUIRED_SCAN_DIRS = ["frontend/src"];
const OPTIONAL_SCAN_DIRS = ["frontend/tests", "backend/app", "tests", "scripts", "docs", "contracts"];
const ROOT_FILES = ["AGENTS.md", "CLAUDE.md", "CLAUDE.local.md", "DESIGN.md", "README.md"];
const EXT = /\.(ts|tsx|js|mjs|cjs|css|py|md|json|yaml|yml|sql|ps1|cmd)$/;
const SKIP = /node_modules|[\\/]\.git[\\/]|\.venv|[\\/]dist[\\/]|\.tmp-agent|\.gitnexus|__pycache__|\.locks/;
const REPLACEMENT = "\uFFFD";
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

function collectDirectory(relativePath, required, files) {
  const full = path.join(repoRoot, relativePath);
  let stats;
  try {
    stats = statSync(full);
  } catch (error) {
    if (required || error?.code !== "ENOENT") {
      scanErrors.push(`cannot inspect scan root ${relativePath}: ${errorMessage(error)}`);
    }
    return;
  }
  if (!stats.isDirectory()) {
    scanErrors.push(`scan root ${relativePath} is not a directory`);
    return;
  }
  walk(full, files);
}

function collectFiles() {
  const files = [];
  for (const dir of REQUIRED_SCAN_DIRS) collectDirectory(dir, true, files);
  for (const dir of OPTIONAL_SCAN_DIRS) collectDirectory(dir, false, files);
  for (const name of ROOT_FILES) {
    const full = path.join(repoRoot, name);
    try {
      if (statSync(full).isFile()) files.push(full);
    } catch (error) {
      if (error?.code !== "ENOENT") {
        scanErrors.push(`cannot inspect optional root file ${name}: ${errorMessage(error)}`);
      }
    }
  }
  return files;
}

function toRepoPath(fullPath) {
  return path.relative(repoRoot, fullPath).replace(/\\/g, "/");
}

function countReplacements(text) {
  let count = 0;
  let index = text.indexOf(REPLACEMENT);
  while (index !== -1) {
    count += 1;
    index = text.indexOf(REPLACEMENT, index + 1);
  }
  return count;
}

const files = collectFiles();
const actual = {};
for (const file of files) {
  let text;
  try {
    text = readFileSync(file, "utf8");
  } catch (error) {
    scanErrors.push(`cannot read ${toRepoPath(file)}: ${errorMessage(error)}`);
    continue;
  }
  const count = countReplacements(text);
  if (count > 0) actual[toRepoPath(file)] = count;
}

if (scanErrors.length > 0) {
  console.error("encoding integrity: scan incomplete; baseline comparison and update refused.");
  for (const error of scanErrors) console.error(`- ${error}`);
  process.exit(1);
}

function loadBaseline() {
  let document;
  try {
    document = JSON.parse(readFileSync(baselinePath, "utf8"));
  } catch {
    console.error(
      `encoding integrity: cannot read ${toRepoPath(baselinePath)}; create and review an explicit zero baseline first.`,
    );
    process.exit(1);
  }
  if (document === null || typeof document !== "object" || Array.isArray(document)) {
    console.error("encoding integrity: invalid baseline; top level must be an object.");
    process.exit(1);
  }
  for (const [file, count] of Object.entries(document)) {
    if (!Number.isInteger(count) || count < 0) {
      console.error(`encoding integrity: invalid baseline count for ${file}; expected a non-negative integer.`);
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
    console.error("encoding integrity: refused to raise baseline; baseline file left unchanged.");
    for (const line of blocked) console.error(`- ${line}`);
    process.exit(1);
  }
  if (tightened.length === 0) {
    console.log("encoding integrity: no baseline lowered; baseline file left unchanged.");
    process.exit(0);
  }
  writeFileSync(baselinePath, `${JSON.stringify(actual, null, 2)}\n`, "utf8");
  console.log(`encoding integrity: baseline tightened (${Object.keys(actual).length} file(s))`);
  process.exit(0);
}

const failures = [];
for (const [file, count] of Object.entries(actual)) {
  const allowed = baseline[file] ?? 0;
  if (count > allowed) {
    failures.push(`  ${file}: ${count} replacement char(s) > baseline ${allowed}`);
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
  `encoding integrity: scanned ${files.length} file(s); U+FFFD ${totalActual}/${totalBaseline}`,
);

if (improved.length > 0) {
  console.log("Improved (run --ratchet to lock in):");
  for (const line of improved) console.log(line);
}

if (failures.length > 0) {
  console.error("Encoding corruption above baseline:");
  for (const line of failures) console.error(line);
  console.error(
    "\nU+FFFD means a file was read/written through a wrong code page. Do not hand-patch the\n" +
      "replacement characters: recover the original text from git history or the authoring session.\n" +
      "On this machine, never use PowerShell text cmdlets (Get-Content/Set-Content/`>`) on files\n" +
      "containing CJK — PowerShell 5.1 defaults to code page 936 and corrupts BOM-less UTF-8.\n" +
      "Use Node's fs (Buffer-based) or a dedicated editing tool instead.",
  );
  process.exit(1);
}

console.log("encoding integrity: no new corruption.");
