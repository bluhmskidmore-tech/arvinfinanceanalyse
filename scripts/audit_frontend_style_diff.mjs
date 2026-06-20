#!/usr/bin/env node
/**
 * Incremental frontend style audit: fail on newly added hard-coded hex colors
 * outside designSystem.ts tokens. style= usage on new lines -> warning only.
 */

import { readFileSync, existsSync } from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";

const repoRoot = path.resolve(import.meta.dirname, "..");
const designSystemPath = path.join(repoRoot, "frontend/src/theme/designSystem.ts");

const EXT_RE = /\.(tsx?|css|module\.css)$/i;

/** @type {RegExp} */
const HEX_RE = /#([0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\b/g;
const PRIVATE_SHADOW_RE = /\bboxShadow\s*:|box-shadow\s*:/;
const TOKEN_SHADOW_RE = /designTokens\.shadow|shellTokens\.shadow|var\(--moss-shadow-/;
const NONE_SHADOW_RE = /\bboxShadow\s*:\s*["']?none["']?|box-shadow\s*:\s*none\b/;
const LARGE_RADIUS_RE = /\bborderRadius\s*:\s*(?:1[89]|[2-9]\d)|border-radius\s*:\s*(?:1[89]|[2-9]\d)px/;
const TOKEN_RADIUS_RE = /designTokens\.radius|shellTokens\.radius|var\(--moss-radius-/;
const KPI_DISPLAY_RE = /\b(KpiBandMetric|KpiCard|MetricCard|SummaryBlock)\b/;
const STATE_SURFACE_RE = /\b(PageStateSurface|DataStatusStrip|moss-page-v2-state-surface|moss-page-v2-data-status)\b/;

function git(args, cwd = repoRoot) {
  const r = spawnSync("git", args, {
    cwd,
    encoding: "utf8",
    maxBuffer: 50 * 1024 * 1024,
  });
  return {
    ok: r.status === 0,
    out: (r.stdout ?? "").trimEnd(),
    err: (r.stderr ?? "").trimEnd(),
    status: r.status,
  };
}

function gitRevExists(ref) {
  const r = git(["rev-parse", "--verify", ref]);
  return r.ok;
}

function resolveBaseRef() {
  const fromEnv = (process.env.BASE_REF ?? "").trim();
  const candidates = fromEnv.length
    ? [fromEnv]
    : ["origin/codex/choice-stock-field-catalog", "origin/main"];
  for (const c of candidates) {
    if (gitRevExists(c)) return c;
  }
  if (gitRevExists("HEAD")) return "HEAD";
  return "HEAD";
}

/** Expand #rgb to #rrggbb, keep 8-char as-is, lowercase */
function normalizeHex(raw) {
  const h = raw.startsWith("#") ? raw.slice(1) : raw;
  const lower = h.toLowerCase();
  if (lower.length === 3) {
    return (
      "#" +
      lower
        .split("")
        .map((ch) => ch + ch)
        .join("")
    );
  }
  return "#" + lower;
}

/** Collect #hex from designSystem.ts string literals and comments (anchors). */
function extractAllowlistFromDesignSystem(filePath) {
  const text = readFileSync(filePath, "utf8");
  const allow = new Set();
  for (const m of text.matchAll(HEX_RE)) {
    allow.add(normalizeHex(m[0]));
  }
  return allow;
}

function isUnderFrontendSrc(repoRelPath) {
  const p = repoRelPath.replace(/\\/g, "/");
  return p.startsWith("frontend/src/") && EXT_RE.test(p);
}

function isExcludedPath(repoRelPath) {
  const p = repoRelPath.replace(/\\/g, "/");
  if (!p.startsWith("frontend/src/")) return true;
  if (/\/theme\//.test(p)) return true;
  if (/\/mocks\//.test(p)) return true;
  if (/\/__tests__\//.test(p)) return true;
  if (p.startsWith("frontend/src/test/")) return true;
  if (/\.(test|spec)\.(tsx?|jsx?)$/.test(p)) return true;
  return false;
}

/** Skip lines that are only line/block comments (low false-positive for hex in strings). */
function isCommentOnlyLine(line) {
  const t = line.trim();
  if (!t) return true;
  if (t.startsWith("//")) return true;
  if (t === "*/" || t.startsWith("*")) return true;
  if (/^\/\*.*\*\/$/.test(t)) return true;
  return false;
}

function stripTrailingLineComment(code) {
  let s = code;
  const idx = s.indexOf("//");
  if (idx === -1) return s;
  const before = s.slice(0, idx);
  const quotes =
    (before.match(/"/g) || []).length + (before.match(/'/g) || []).length;
  if (quotes % 2 !== 0) return s;
  return before.trimEnd();
}

function findBadHexesInLine(line, allowlist) {
  const scan = stripTrailingLineComment(line);
  const bad = [];
  HEX_RE.lastIndex = 0;
  let m;
  while ((m = HEX_RE.exec(scan)) !== null) {
    const norm = normalizeHex(m[0]);
    if (!allowlist.has(norm)) bad.push({ raw: m[0], norm, index: m.index });
  }
  return bad;
}

function countStylePropsInLine(line) {
  return (line.match(/\bstyle\s*=/g) || []).length;
}

function hasPrivateShadow(line) {
  return PRIVATE_SHADOW_RE.test(line) && !TOKEN_SHADOW_RE.test(line) && !NONE_SHADOW_RE.test(line);
}

function hasLargeRadiusWithoutToken(line) {
  return LARGE_RADIUS_RE.test(line) && !TOKEN_RADIUS_RE.test(line);
}

/**
 * Parse `git diff` unified format: current file + accumulated + lines.
 * @param {string} diffText
 * @returns {{ path: string, additions: { line: string, globalLine?: number }[] }[]}
 */
function parseGitDiffAdditions(diffText) {
  /** @type {{ path: string, additions: { line: string }[] }[]} */
  const files = [];
  let currentPath = null;

  for (const rawLine of diffText.split(/\r?\n/)) {
    if (rawLine.startsWith("diff --git ")) {
      const rest = rawLine.slice("diff --git ".length).trim();
      const parts = rest.split(/\s+/);
      if (parts.length >= 2) {
        const bPath = parts[1].replace(/^b\//, "");
        currentPath = bPath;
        if (!files.length || files[files.length - 1].path !== currentPath) {
          files.push({ path: currentPath, additions: [] });
        }
      }
      continue;
    }
    if (!currentPath) continue;
    if (
      rawLine.startsWith("+++ ") &&
      !rawLine.startsWith("+++ /dev/null")
    ) {
      const np = rawLine.slice(4).trim().replace(/^[ab]\//, "");
      if (np && files.length) {
        files[files.length - 1].path = np;
      }
      continue;
    }
    if (rawLine.startsWith("+") && !rawLine.startsWith("+++")) {
      const added = rawLine.slice(1);
      const last = files[files.length - 1];
      if (last) last.additions.push({ line: added });
    }
  }

  const merged = new Map();
  for (const f of files) {
    if (!merged.has(f.path)) merged.set(f.path, []);
    merged.get(f.path).push(...f.additions);
  }
  return [...merged.entries()].map(([p, additions]) => ({ path: p, additions }));
}

function runDiff(baseRef, cached) {
  const scope = ["--", "frontend/src"];
  const args = cached
    ? ["diff", "--cached", "HEAD", "--unified=0", ...scope]
    : ["diff", baseRef, "--unified=0", ...scope];
  const r = git(args);
  if (!r.ok) {
    console.error(r.err || r.out || `git ${args.join(" ")} failed`);
    process.exit(2);
  }
  return r.out;
}

function runWorkspaceDiff(cached) {
  const scope = ["--", "frontend/src"];
  const args = cached
    ? ["diff", "--cached", "HEAD", "--unified=0", ...scope]
    : ["diff", "HEAD", "--unified=0", ...scope];
  const r = git(args);
  if (!r.ok) {
    console.error(r.err || r.out || `git ${args.join(" ")} failed`);
    process.exit(2);
  }
  return r.out;
}

function auditDiff(diffText, allowlist) {
  const parsed = parseGitDiffAdditions(diffText);
  /** @type {string[]} */
  const hexFailures = [];
  /** @type {string[]} */
  const styleWarnings = [];
  /** @type {string[]} */
  const shadowFailures = [];
  /** @type {string[]} */
  const radiusWarnings = [];
  /** @type {string[]} */
  const stateWarnings = [];

  for (const { path: repoPath, additions } of parsed) {
    const rel = repoPath.replace(/\\/g, "/");
    if (!isUnderFrontendSrc(rel) || isExcludedPath(rel)) continue;
    const addedText = additions.map(({ line }) => line).join("\n");
    const addedKpiDisplay = KPI_DISPLAY_RE.test(addedText);
    const addedStateSurface = STATE_SURFACE_RE.test(addedText);

    for (const { line } of additions) {
      if (isCommentOnlyLine(line)) continue;
      const bad = findBadHexesInLine(line, allowlist);
      if (bad.length) {
        for (const b of bad) {
          hexFailures.push(
            `${rel}: non-token hex ${b.raw} (${b.norm}) — ${line.trim().slice(0, 120)}`,
          );
        }
      }
      const sc = countStylePropsInLine(line);
      if (hasPrivateShadow(line)) {
        shadowFailures.push(
          `${rel}: private shadow on added line - ${line.trim().slice(0, 120)}`,
        );
      }
      if (hasLargeRadiusWithoutToken(line)) {
        radiusWarnings.push(
          `${rel}: large radius should use tokens/classes - ${line.trim().slice(0, 120)}`,
        );
      }
      if (sc > 0) {
        styleWarnings.push(
          `${rel}: +${sc} style= on added line — ${line.trim().slice(0, 120)}`,
        );
      }
    }
    if (addedKpiDisplay && !addedStateSurface) {
      stateWarnings.push(
        `${rel}: added KPI/metric display without added DataStatusStrip/PageStateSurface evidence in the same diff`,
      );
    }
  }

  return { hexFailures, styleWarnings, shadowFailures, radiusWarnings, stateWarnings };
}

function emptyAuditResult() {
  return {
    hexFailures: [],
    styleWarnings: [],
    shadowFailures: [],
    radiusWarnings: [],
    stateWarnings: [],
  };
}

function findingKey(value) {
  return value.trim();
}

function subtractFindings(allFindings, currentFindings) {
  const current = new Set(currentFindings.map(findingKey));
  return allFindings.filter((item) => !current.has(findingKey(item)));
}

function subtractAuditResult(allFindings, currentFindings) {
  return {
    hexFailures: subtractFindings(allFindings.hexFailures, currentFindings.hexFailures),
    styleWarnings: subtractFindings(allFindings.styleWarnings, currentFindings.styleWarnings),
    shadowFailures: subtractFindings(allFindings.shadowFailures, currentFindings.shadowFailures),
    radiusWarnings: subtractFindings(allFindings.radiusWarnings, currentFindings.radiusWarnings),
    stateWarnings: subtractFindings(allFindings.stateWarnings, currentFindings.stateWarnings),
  };
}

function hasAnyFinding(findings) {
  return (
    findings.hexFailures.length > 0 ||
    findings.styleWarnings.length > 0 ||
    findings.shadowFailures.length > 0 ||
    findings.radiusWarnings.length > 0 ||
    findings.stateWarnings.length > 0
  );
}

function hasBlockingFinding(findings) {
  return findings.hexFailures.length > 0 || findings.shadowFailures.length > 0;
}

function printFindingGroup(title, findings, limit = 50) {
  if (!findings.length) return;
  console.warn(title);
  for (const item of findings.slice(0, limit)) console.warn(`  ${item}`);
  if (findings.length > limit) {
    console.warn(`  ... and ${findings.length - limit} more`);
  }
}

function printAuditResult(findings, label, { detailLimit = 50, blocking = true } = {}) {
  printFindingGroup(
    `[style:audit] ${label} warning: ${findings.styleWarnings.length} added line(s) with style= (review for debt)`,
    findings.styleWarnings,
    detailLimit,
  );
  printFindingGroup(
    `[style:audit] ${label} warning: ${findings.radiusWarnings.length} added large-radius line(s) should use tokens/classes`,
    findings.radiusWarnings,
    detailLimit,
  );
  printFindingGroup(
    `[style:audit] ${label} warning: ${findings.stateWarnings.length} added metric display file(s) need visible status evidence review`,
    findings.stateWarnings,
    detailLimit,
  );
  printFindingGroup(
    `[style:audit] ${label} ${blocking ? "FAIL" : "non-blocking debt"}: ${findings.hexFailures.length} non-token hex on added line(s)`,
    findings.hexFailures,
    detailLimit,
  );
  printFindingGroup(
    `[style:audit] ${label} ${blocking ? "FAIL" : "non-blocking debt"}: ${findings.shadowFailures.length} private shadow on added line(s)`,
    findings.shadowFailures,
    detailLimit,
  );
}

function summarizeAuditResult(findings) {
  const parts = [];
  if (findings.hexFailures.length) parts.push(`${findings.hexFailures.length} non-token hex`);
  if (findings.shadowFailures.length) parts.push(`${findings.shadowFailures.length} private shadow`);
  if (findings.styleWarnings.length) parts.push(`${findings.styleWarnings.length} style= warning`);
  if (findings.radiusWarnings.length) parts.push(`${findings.radiusWarnings.length} radius warning`);
  if (findings.stateWarnings.length) parts.push(`${findings.stateWarnings.length} state warning`);
  return parts.length ? parts.join(", ") : "no findings";
}

function die(msg, code = 1) {
  console.error(msg);
  process.exit(code);
}

function runSelfTest() {
  if (!existsSync(designSystemPath)) {
    die(`missing ${path.relative(repoRoot, designSystemPath)}`, 2);
  }
  const allow = extractAllowlistFromDesignSystem(designSystemPath);
  if (!allow.has(normalizeHex("#1850a1"))) {
    die("self-test: expected #1850a1 in allowlist from designSystem.ts", 2);
  }

  const tokenLine = `color: '#1850a1'`;
  if (findBadHexesInLine(tokenLine, allow).length !== 0) {
    die("self-test: token hex should pass", 2);
  }

  const badLine = `border: 1px solid #aabbcc`;
  if (!normalizeHex("#aabbcc").startsWith("#") || allow.has(normalizeHex("#aabbcc"))) {
    die("self-test: fixture #aabbcc should not be in allowlist", 2);
  }
  if (findBadHexesInLine(badLine, allow).length === 0) {
    die("self-test: non-token hex should fail line scan", 2);
  }

  const testPathDiff = [
    "diff --git a/frontend/src/x/TestThing.test.tsx b/frontend/src/x/TestThing.test.tsx",
    "+++ b/frontend/src/x/TestThing.test.tsx",
    `+  const c = '#aabbcc'`,
  ].join("\n");
  const ex = auditDiff(testPathDiff, allow);
  if (ex.hexFailures.length !== 0) {
    die(`self-test: test file should be exempt, got: ${ex.hexFailures.join("; ")}`, 2);
  }

  const failDiff = [
    "diff --git a/frontend/src/x/Bad.tsx b/frontend/src/x/Bad.tsx",
    "+++ b/frontend/src/x/Bad.tsx",
    `+  const c = '#aabbcc'`,
  ].join("\n");
  const af = auditDiff(failDiff, allow);
  if (af.hexFailures.length === 0) {
    die("self-test: non-test file with bad hex should fail", 2);
  }

  const styleDiff = [
    "diff --git a/frontend/src/x/Ok.tsx b/frontend/src/x/Ok.tsx",
    "+++ b/frontend/src/x/Ok.tsx",
    `+  <div style={{ color: '#1850a1' }} />`,
  ].join("\n");
  const sw = auditDiff(styleDiff, allow);
  if (sw.hexFailures.length !== 0) {
    die(`self-test: token hex + style should not hex-fail: ${sw.hexFailures.join("; ")}`, 2);
  }
  if (sw.styleWarnings.length === 0) {
    die("self-test: expected style= warning", 2);
  }

  const shadowDiff = [
    "diff --git a/frontend/src/x/Shadow.tsx b/frontend/src/x/Shadow.tsx",
    "+++ b/frontend/src/x/Shadow.tsx",
    `+  <section style={{ boxShadow: '0 20px 44px rgba(22, 35, 46, 0.08)' }} />`,
  ].join("\n");
  const sh = auditDiff(shadowDiff, allow);
  if (sh.shadowFailures.length === 0) {
    die("self-test: expected private shadow failure", 2);
  }

  const noShadowDiff = [
    "diff --git a/frontend/src/x/NoShadow.tsx b/frontend/src/x/NoShadow.tsx",
    "+++ b/frontend/src/x/NoShadow.tsx",
    `+  <section style={{ boxShadow: 'none' }} />`,
  ].join("\n");
  const ns = auditDiff(noShadowDiff, allow);
  if (ns.shadowFailures.length !== 0) {
    die("self-test: boxShadow none should not be treated as private shadow", 2);
  }

  const largeRadiusDiff = [
    "diff --git a/frontend/src/x/Radius.tsx b/frontend/src/x/Radius.tsx",
    "+++ b/frontend/src/x/Radius.tsx",
    `+  <section style={{ borderRadius: 24 }} />`,
  ].join("\n");
  const lr = auditDiff(largeRadiusDiff, allow);
  if (lr.radiusWarnings.length === 0) {
    die("self-test: expected large radius warning", 2);
  }

  const statusDiff = [
    "diff --git a/frontend/src/x/Page.tsx b/frontend/src/x/Page.tsx",
    "+++ b/frontend/src/x/Page.tsx",
    `+  <KpiBandMetric label="AUM" value={aum} />`,
  ].join("\n");
  const st = auditDiff(statusDiff, allow);
  if (st.stateWarnings.length === 0) {
    die("self-test: expected KPI/status warning", 2);
  }

  console.log("audit_frontend_style_diff self-test: ok");
}

function main() {
  const argv = new Set(process.argv.slice(2));
  if (argv.has("--self-test")) {
    runSelfTest();
    return;
  }

  const cached = argv.has("--cached");
  const baseRef = resolveBaseRef();

  if (!existsSync(designSystemPath)) {
    die(`missing design system: ${path.relative(repoRoot, designSystemPath)}`, 2);
  }
  const allowlist = extractAllowlistFromDesignSystem(designSystemPath);

  const fullDiffText = runDiff(baseRef, cached);
  const workspaceDiffText = runWorkspaceDiff(cached);
  if (!fullDiffText && !workspaceDiffText) {
    console.log(
      `style diff audit: no changes vs ${cached ? "index (staged)" : baseRef}`,
    );
    return;
  }

  const fullFindings = fullDiffText ? auditDiff(fullDiffText, allowlist) : emptyAuditResult();
  const workspaceFindings = workspaceDiffText
    ? auditDiff(workspaceDiffText, allowlist)
    : emptyAuditResult();
  const useWorkspaceGate = workspaceDiffText.length > 0;
  const primaryFindings = useWorkspaceGate ? workspaceFindings : fullFindings;
  const primaryLabel = useWorkspaceGate
    ? cached
      ? "staged delta vs HEAD"
      : "workspace delta vs HEAD"
    : `branch delta vs ${baseRef}`;
  const existingBranchFindings = useWorkspaceGate
    ? subtractAuditResult(fullFindings, workspaceFindings)
    : emptyAuditResult();

  printAuditResult(primaryFindings, primaryLabel);

  if (hasAnyFinding(existingBranchFindings)) {
    console.warn(
      `[style:audit] existing branch/base debt vs ${baseRef}: ${summarizeAuditResult(existingBranchFindings)}`,
    );
    printAuditResult(existingBranchFindings, "existing branch/base", {
      detailLimit: 10,
      blocking: false,
    });
  }

  if (hasBlockingFinding(primaryFindings)) {
    console.error(
      `  gate: ${primaryLabel} failed; use designTokens / designSystem, token shadows, or documented primitives`,
    );
    process.exit(1);
  }

  console.log(
    `style diff audit: pass (${primaryLabel}; ${summarizeAuditResult(primaryFindings)})`,
  );
}

main();
