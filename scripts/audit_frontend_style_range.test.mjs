import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";

import {
  analyzeDiffText,
  evaluateRangeGate,
  normalizeHex,
  parseArgs,
} from "./audit_frontend_style_range.mjs";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const scriptPath = path.join(repoRoot, "scripts/audit_frontend_style_range.mjs");
const emptyWorkspaceAudit = makeAudit("");

function diffFor(filePath, lines) {
  return [
    `diff --git a/${filePath} b/${filePath}`,
    `+++ b/${filePath}`,
    ...lines.map((line) => `+${line}`),
  ].join("\n");
}

function makeAudit(diffText) {
  return analyzeDiffText(diffText, {
    frontendRoot: "frontend/src",
    allowlist: new Set([normalizeHex("#1850a1"), normalizeHex("#f7f8fa")]),
  });
}

function evaluate(baseAudit, headAudit, touchedFiles = []) {
  return evaluateRangeGate({
    baseAudit,
    headAudit,
    touchedFiles,
    workspaceAudit: emptyWorkspaceAudit,
    statusLines: [],
    allowWorkspace: false,
  });
}

test("passes when head has lower blocking debt", () => {
  const base = makeAudit(
    diffFor("frontend/src/pages/Base.tsx", [
      "const a = '#aabbcc';",
      "const b = '#bbccdd';",
      "<section style={{ boxShadow: '0 1px 2px rgba(1, 2, 3, 0.2)' }} />",
    ]),
  );
  const head = makeAudit(
    diffFor("frontend/src/pages/Base.tsx", [
      "const a = '#aabbcc';",
    ]),
  );

  const result = evaluate(base, head, ["frontend/src/pages/Base.tsx"]);

  assert.equal(result.passed, true);
  assert.deepEqual(result.failures, []);
});

test("fails when head grows non-token hex", () => {
  const base = makeAudit(diffFor("frontend/src/pages/A.tsx", ["const a = '#aabbcc';"]));
  const head = makeAudit(
    diffFor("frontend/src/pages/A.tsx", [
      "const a = '#aabbcc';",
      "const b = '#bbccdd';",
    ]),
  );

  const result = evaluate(base, head, ["frontend/src/pages/A.tsx"]);

  assert.equal(result.passed, false);
  assert.match(result.failures.join("\n"), /non-token hex grew/);
});

test("fails when head grows private shadow", () => {
  const base = makeAudit("");
  const head = makeAudit(
    diffFor("frontend/src/pages/Shadow.tsx", [
      "<section style={{ boxShadow: '0 4px 12px rgba(1, 2, 3, 0.18)' }} />",
    ]),
  );

  const result = evaluate(base, head, ["frontend/src/pages/Shadow.tsx"]);

  assert.equal(result.passed, false);
  assert.match(result.failures.join("\n"), /private shadow grew/);
});

test("fails when total is down but a touched file grows", () => {
  const base = makeAudit(
    [
      diffFor("frontend/src/pages/A.tsx", [
        "const a = '#aabbcc';",
        "const b = '#bbccdd';",
        "const c = '#ccddee';",
      ]),
    ].join("\n"),
  );
  const head = makeAudit(
    [
      diffFor("frontend/src/pages/A.tsx", ["const a = '#aabbcc';"]),
      diffFor("frontend/src/pages/B.tsx", ["const b = '#ddeeff';"]),
    ].join("\n"),
  );

  const result = evaluate(base, head, [
    "frontend/src/pages/A.tsx",
    "frontend/src/pages/B.tsx",
  ]);

  assert.equal(result.passed, false);
  assert.match(result.failures.join("\n"), /touched file debt/);
  assert.deepEqual(result.touchedGrowth, [
    {
      file: "frontend/src/pages/B.tsx",
      type: "non-token hex",
      base: 0,
      head: 1,
      delta: 1,
      newCount: 1,
    },
  ]);
});

test("allows relocated existing debt signatures in touched files", () => {
  const base = makeAudit(
    diffFor("frontend/src/styles/global.css", [
      ".a { color: #aabbcc; }",
      ".b { box-shadow: 0 1px 2px rgba(1, 2, 3, 0.2); }",
    ]),
  );
  const head = makeAudit(
    diffFor("frontend/src/styles/split.css", [
      ".a { color: #aabbcc; }",
      ".b { box-shadow: 0 1px 2px rgba(1, 2, 3, 0.2); }",
    ]),
  );

  const result = evaluate(base, head, ["frontend/src/styles/split.css"]);

  assert.equal(result.passed, true);
  assert.equal(result.relocatedGrowth.length, 2);
});

test("allows official shadow tokens", () => {
  const audit = makeAudit(
    diffFor("frontend/src/pages/Tokens.css", [
      ".a { box-shadow: var(--ib-shadow); }",
      ".b { box-shadow: var(--moss-shadow-card); }",
      "const style = { boxShadow: ibTokens.shadow };",
      "const shell = { boxShadow: shellTokens.shadow.card };",
      "const design = { boxShadow: designTokens.shadow.panel };",
    ]),
  );

  assert.equal(audit.counts.shadow, 0);
});

test("blocks raw fallback in ib shadow token", () => {
  const audit = makeAudit(
    diffFor("frontend/src/pages/Fallback.css", [
      ".a { box-shadow: var(--ib-shadow, 0 1px 2px rgba(16, 24, 29, 0.05)); }",
    ]),
  );

  assert.equal(audit.counts.shadow, 1);
});

test("blocks raw rgba shadow", () => {
  const audit = makeAudit(
    diffFor("frontend/src/pages/RawShadow.tsx", [
      "<section style={{ boxShadow: '0 8px 24px rgba(10, 20, 30, 0.15)' }} />",
    ]),
  );

  assert.equal(audit.counts.shadow, 1);
});

test("parseArgs accepts documented flags", () => {
  const parsed = parseArgs([
    "--upstream",
    "origin/main",
    "--base",
    "abc123",
    "--head",
    "def456",
    "--frontend-root",
    "frontend/src",
    "--json",
    "--allow-workspace",
  ]);

  assert.deepEqual(parsed, {
    upstream: "origin/main",
    base: "abc123",
    head: "def456",
    frontendRoot: "frontend/src",
    json: true,
    allowWorkspace: true,
    help: false,
  });
});

test("--help prints usage", () => {
  const result = spawnSync(process.execPath, [scriptPath, "--help"], {
    cwd: repoRoot,
    encoding: "utf8",
  });

  assert.equal(result.status, 0);
  assert.match(result.stdout, /Frontend style audit range gate/);
  assert.match(result.stdout, /--upstream <ref>/);
  assert.match(result.stdout, /--allow-workspace/);
});
