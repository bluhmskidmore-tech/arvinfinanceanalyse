#!/usr/bin/env node

/**
 * Frontend debt audit aggregator (`npm run debt:audit`).
 *
 * The previous `a && b && c` chain short-circuited on the first failure, so a
 * red segment hid every later segment's findings (e.g. font-size floor
 * regressions stayed invisible for days behind a visual-token failure).
 *
 * This runner executes all three audits unconditionally and sequentially,
 * streams each script's stdout/stderr through verbatim as it arrives, then
 * prints a per-script exit-code summary (with a short failure excerpt for red
 * segments) and exits 1 if any audit failed. The three audit scripts stay
 * untouched; each still resolves the repo root itself via import.meta.dirname,
 * so the aggregator works from any working directory.
 */

import { spawn } from "node:child_process";
import path from "node:path";

const AUDIT_SCRIPTS = [
  "audit_frontend_debt.mjs",
  "audit_visual_tokens.mjs",
  "audit_font_size_floor.mjs",
];

const FAILURE_EXCERPT_LINES = 6;

function runAudit(script) {
  return new Promise((resolvePromise) => {
    const child = spawn(
      process.execPath,
      [path.join(import.meta.dirname, script)],
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
for (const script of AUDIT_SCRIPTS) {
  process.stdout.write(`\n=== ${script} ===\n`);
  results.push(await runAudit(script));
}

const failed = results.filter((result) => result.exitCode !== 0);

process.stdout.write("\n=== debt:audit summary ===\n");
for (const { script, exitCode } of results) {
  process.stdout.write(
    `- ${script}: ${exitCode === 0 ? "PASS" : `FAIL (exit ${exitCode})`}\n`,
  );
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
process.stdout.write(`\nAll ${results.length} audits passed.\n`);
