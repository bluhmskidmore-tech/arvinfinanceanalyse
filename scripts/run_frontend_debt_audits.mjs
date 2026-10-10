#!/usr/bin/env node

/**
 * Frontend debt audit aggregator (`npm run debt:audit`).
 *
 * The previous `a && b && c` chain short-circuited on the first failure, so a
 * red segment hid every later segment's findings (e.g. font-size floor
 * regressions stayed invisible for days behind a visual-token failure).
 *
 * This runner executes every audit unconditionally and sequentially, streams
 * each script's stdout/stderr through verbatim as it arrives, then prints a
 * per-script exit-code summary (with a short failure excerpt for red segments)
 * and exits 1 if any audit failed. Each audit resolves the repo root itself via
 * import.meta.dirname, so the aggregator works from any working directory.
 * `--scope frontend` is a local feedback command, not the complete debt gate:
 * it excludes repository monolith counts and the repository encoding audit.
 */

import { spawn } from "node:child_process";
import path from "node:path";
import { parseArgs } from "node:util";

const { values: options } = parseArgs({
  options: { scope: { type: "string", default: "all" } },
});
if (!["all", "frontend"].includes(options.scope)) {
  console.error("Invalid --scope: expected all or frontend.");
  process.exit(1);
}

// audit_encoding_integrity.mjs scans the whole repository, not just frontend/.
// It rides this aggregator because `debt:audit` is the established debt gate;
// encoding corruption is silent and unrecoverable, so it needs the same ratchet.
const AUDIT_SCRIPTS = [
  "audit_frontend_debt.mjs",
  "audit_visual_tokens.mjs",
  "audit_font_size_floor.mjs",
  "audit_frontend_style_architecture.mjs",
  "audit_encoding_integrity.mjs",
  "audit_section_numbering.mjs",
  "audit_undeclared_css_vars.mjs",
];

const FAILURE_EXCERPT_LINES = 6;

function runAudit(script, args = []) {
  return new Promise((resolvePromise) => {
    const child = spawn(
      process.execPath,
      [path.join(import.meta.dirname, script), ...args],
      { stdio: ["ignore", "pipe", "pipe"] },
    );
    let captured = "";
    child.stdout.on("data", (chunk) => {
      captured += chunk;
      process.stdout.write(chunk);
    });
    child.stderr.on("data", (chunk) => {
      captured += chunk;
      process.stderr.write(chunk);
    });
    child.on("error", (error) => {
      process.stderr.write(`${script}: failed to start (${error.message})\n`);
      resolvePromise({ script, exitCode: 1, captured });
    });
    child.on("close", (code, signal) => {
      resolvePromise({ script, exitCode: code ?? (signal ? 1 : 0), captured });
    });
  });
}

function failureExcerpt(captured) {
  return captured
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .slice(0, FAILURE_EXCERPT_LINES);
}

const results = [];
process.stdout.write(`Debt audit scope=${options.scope}.\n`);
if (options.scope === "frontend") {
  process.stdout.write("Frontend feedback only; not a full repository audit. Repository monolith guards and repository encoding are not covered. Run npm run debt:audit for the complete gate.\n");
}
for (const script of AUDIT_SCRIPTS) {
  if (options.scope === "frontend" && script === "audit_encoding_integrity.mjs") {
    process.stdout.write(`\n=== ${script} [repository]: NOT RUN (outside frontend scope) ===\n`);
    continue;
  }
  const owner = script === "audit_encoding_integrity.mjs"
    ? "repository"
    : script === "audit_frontend_debt.mjs" && options.scope === "all"
      ? "frontend + repository monoliths"
      : "frontend";
  process.stdout.write(`\n=== ${script} [${owner}] ===\n`);
  const args = script === "audit_frontend_debt.mjs" ? ["--scope", options.scope] : [];
  results.push({ ...await runAudit(script, args), owner });
}

const failed = results.filter((result) => result.exitCode !== 0);

process.stdout.write(`\n=== debt:audit summary (scope=${options.scope}) ===\n`);
for (const { script, exitCode, owner } of results) {
  process.stdout.write(
    `- ${script} [${owner}]: ${exitCode === 0 ? "PASS" : `FAIL (exit ${exitCode})`}\n`,
  );
}
if (options.scope === "frontend") {
  process.stdout.write("- audit_encoding_integrity.mjs [repository]: NOT RUN; repository encoding is not covered.\n");
}
for (const { script, captured } of failed) {
  process.stdout.write(`\n${script} failure excerpt:\n`);
  for (const line of failureExcerpt(captured)) {
    process.stdout.write(`  ${line}\n`);
  }
}

if (failed.length > 0) {
  process.stdout.write(
    `\n${failed.length}/${results.length} audit(s) failed; all segments ran to completion (no short-circuit).\n`,
  );
  process.exit(1);
}
process.stdout.write(`\nAll ${results.length} selected audits passed (scope=${options.scope}).${options.scope === "frontend" ? " This is not a full repository audit; run npm run debt:audit before final acceptance." : ""}\n`);
