#!/usr/bin/env node
/**
 * Frontend style audit range gate.
 *
 * This gate is for PRs where the baseline branch already has style debt.
 * It checks whether a candidate range reduces blocking debt without growing
 * touched-file debt, while leaving strict `style:audit` semantics unchanged.
 */

import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const repoRoot = path.resolve(import.meta.dirname, "..");
const defaultFrontendRoot = "frontend/src";
const designSystemRelPath = "frontend/src/theme/designSystem.ts";

const EXT_RE = /\.(tsx?|css|module\.css)$/i;
const HEX_RE = /#([0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\b/g;
const PRIVATE_SHADOW_RE = /\bboxShadow\s*:|box-shadow\s*:/;
const TOKEN_SHADOW_RE =
  /designTokens\.shadow|shellTokens\.shadow|ibTokens\.shadow|var\(--moss-shadow-[^)]+\)|var\(--ib-shadow\)/;
const NONE_SHADOW_RE = /\bboxShadow\s*:\s*["']?none["']?|box-shadow\s*:\s*none\b/;

function normalizePath(value) {
  return value.replace(/\\/g, "/").replace(/^\.\/+/, "").replace(/\/+$/, "");
}

export function normalizeHex(raw) {
  const h = raw.startsWith("#") ? raw.slice(1) : raw;
  const lower = h.toLowerCase();
  if (lower.length === 3) {
    return `#${lower
      .split("")
      .map((ch) => ch + ch)
      .join("")}`;
  }
  return `#${lower}`;
}

function git(args, { cwd = repoRoot, allowFailure = false } = {}) {
  const result = spawnSync("git", args, {
    cwd,
    encoding: "utf8",
    maxBuffer: 100 * 1024 * 1024,
  });
  const output = (result.stdout ?? "").trimEnd();
  const error = (result.stderr ?? "").trimEnd();
  if (result.status !== 0 && !allowFailure) {
    const command = `git ${args.join(" ")}`;
    throw new Error(error || output || `${command} failed with status ${result.status}`);
  }
  return {
    ok: result.status === 0,
    out: output,
    err: error,
    status: result.status,
  };
}

function refExists(ref) {
  return git(["rev-parse", "--verify", ref], { allowFailure: true }).ok;
}

function resolveDefaultUpstream() {
  const candidates = [
    process.env.BASE_REF,
    "origin/codex/choice-stock-field-catalog",
    "origin/main",
    "origin/master",
    "main",
    "master",
  ].filter(Boolean);

  for (const candidate of candidates) {
    if (refExists(candidate)) return candidate;
  }
  return "HEAD~1";
}

function resolveRefLabel(ref) {
  const hash = git(["rev-parse", "--short=12", ref]).out;
  const subject = git(["show", "-s", "--format=%s", ref]).out;
  return { ref, hash, subject };
}

function readTextAtRef(ref, repoRelPath) {
  const result = git(["show", `${ref}:${repoRelPath}`], { allowFailure: true });
  if (result.ok) return result.out;

  const worktreePath = path.join(repoRoot, repoRelPath);
  if (ref === "HEAD" && existsSync(worktreePath)) {
    return readFileSync(worktreePath, "utf8");
  }
  return "";
}

function extractAllowlistFromText(text) {
  const allowlist = new Set();
  HEX_RE.lastIndex = 0;
  for (const match of text.matchAll(HEX_RE)) {
    allowlist.add(normalizeHex(match[0]));
  }
  return allowlist;
}

function isUnderFrontendRoot(repoRelPath, frontendRoot) {
  const normalizedPath = normalizePath(repoRelPath);
  const normalizedRoot = normalizePath(frontendRoot);
  return normalizedPath.startsWith(`${normalizedRoot}/`) && EXT_RE.test(normalizedPath);
}

function isExcludedPath(repoRelPath, frontendRoot) {
  const normalizedPath = normalizePath(repoRelPath);
  const normalizedRoot = normalizePath(frontendRoot);
  if (!normalizedPath.startsWith(`${normalizedRoot}/`)) return true;
  if (!EXT_RE.test(normalizedPath)) return true;
  if (normalizedPath.includes("/theme/")) return true;
  if (normalizedPath.includes("/mocks/")) return true;
  if (normalizedPath.includes("/__tests__/")) return true;
  if (normalizedPath.startsWith(`${normalizedRoot}/test/`)) return true;
  if (/\.(test|spec)\.(tsx?|jsx?)$/.test(normalizedPath)) return true;
  return false;
}

function isCommentOnlyLine(line) {
  const trimmed = line.trim();
  if (!trimmed) return true;
  if (trimmed.startsWith("//")) return true;
  if (trimmed === "*/" || trimmed.startsWith("*")) return true;
  if (/^\/\*.*\*\/$/.test(trimmed)) return true;
  return false;
}

function stripTrailingLineComment(code) {
  const idx = code.indexOf("//");
  if (idx === -1) return code;
  const before = code.slice(0, idx);
  const quoteCount =
    (before.match(/"/g) || []).length + (before.match(/'/g) || []).length;
  if (quoteCount % 2 !== 0) return code;
  return before.trimEnd();
}

function findBadHexesInLine(line, allowlist) {
  const scan = stripTrailingLineComment(line);
  const bad = [];
  HEX_RE.lastIndex = 0;
  let match;
  while ((match = HEX_RE.exec(scan)) !== null) {
    const norm = normalizeHex(match[0]);
    if (!allowlist.has(norm)) {
      bad.push({ raw: match[0], norm, index: match.index });
    }
  }
  return bad;
}

function hasPrivateShadow(line) {
  return PRIVATE_SHADOW_RE.test(line) && !TOKEN_SHADOW_RE.test(line) && !NONE_SHADOW_RE.test(line);
}

function parseGitDiffAdditions(diffText) {
  const files = [];
  let currentPath = null;

  for (const rawLine of diffText.split(/\r?\n/)) {
    if (rawLine.startsWith("diff --git ")) {
      const rest = rawLine.slice("diff --git ".length).trim();
      const parts = rest.split(/\s+/);
      if (parts.length >= 2) {
        currentPath = parts[1].replace(/^b\//, "");
        files.push({ path: currentPath, additions: [] });
      }
      continue;
    }

    if (!currentPath) continue;

    if (rawLine.startsWith("+++ ") && !rawLine.startsWith("+++ /dev/null")) {
      const nextPath = rawLine.slice(4).trim().replace(/^[ab]\//, "");
      if (nextPath && files.length) {
        files[files.length - 1].path = nextPath;
      }
      continue;
    }

    if (rawLine.startsWith("+") && !rawLine.startsWith("+++")) {
      files[files.length - 1]?.additions.push({ line: rawLine.slice(1) });
    }
  }

  const merged = new Map();
  for (const file of files) {
    if (!merged.has(file.path)) merged.set(file.path, []);
    merged.get(file.path).push(...file.additions);
  }
  return [...merged.entries()].map(([filePath, additions]) => ({ path: filePath, additions }));
}

function collectRemovedLineCounts(diffText) {
  const removed = new Map();
  for (const rawLine of diffText.split(/\r?\n/)) {
    if (!rawLine.startsWith("-") || rawLine.startsWith("---")) continue;
    const key = rawLine.slice(1).trim();
    if (!key) continue;
    removed.set(key, (removed.get(key) ?? 0) + 1);
  }
  return removed;
}

function consumeMovedLine(line, removedLineCounts) {
  const key = line.trim();
  const count = removedLineCounts.get(key) ?? 0;
  if (count <= 0) return false;
  if (count === 1) {
    removedLineCounts.delete(key);
  } else {
    removedLineCounts.set(key, count - 1);
  }
  return true;
}

function emptyPerFile() {
  return { hex: 0, shadow: 0, examples: [], signatures: { hex: [], shadow: [] } };
}

function normalizeFindingLine(line) {
  return line.trim().replace(/\s+/g, " ");
}

function addPerFileFinding(perFile, filePath, type, example, signature) {
  const current = perFile.get(filePath) ?? emptyPerFile();
  current[type] += 1;
  if (current.examples.length < 3) current.examples.push(example);
  current.signatures[type].push(signature);
  perFile.set(filePath, current);
}

export function analyzeDiffText(diffText, options = {}) {
  const frontendRoot = normalizePath(options.frontendRoot ?? defaultFrontendRoot);
  const allowlist = options.allowlist ?? new Set();
  const perFile = new Map();
  const findings = {
    hexFailures: [],
    shadowFailures: [],
  };
  const removedLineCounts = collectRemovedLineCounts(diffText);

  for (const { path: repoPath, additions } of parseGitDiffAdditions(diffText)) {
    const filePath = normalizePath(repoPath);
    if (!isUnderFrontendRoot(filePath, frontendRoot) || isExcludedPath(filePath, frontendRoot)) {
      continue;
    }

    for (const { line } of additions) {
      if (isCommentOnlyLine(line)) continue;
      if (consumeMovedLine(line, removedLineCounts)) continue;

      const badHexes = findBadHexesInLine(line, allowlist);
      for (const badHex of badHexes) {
        const example = `${filePath}: non-token hex ${badHex.raw} (${badHex.norm}) - ${line.trim().slice(0, 140)}`;
        const signature = `hex:${badHex.norm}:${normalizeFindingLine(line)}`;
        findings.hexFailures.push(example);
        addPerFileFinding(perFile, filePath, "hex", example, signature);
      }

      if (hasPrivateShadow(line)) {
        const example = `${filePath}: private shadow - ${line.trim().slice(0, 140)}`;
        const signature = `shadow:${normalizeFindingLine(line)}`;
        findings.shadowFailures.push(example);
        addPerFileFinding(perFile, filePath, "shadow", example, signature);
      }
    }
  }

  return {
    counts: {
      hex: findings.hexFailures.length,
      shadow: findings.shadowFailures.length,
    },
    findings,
    perFile,
  };
}

function auditCommitRange({ upstream, ref, frontendRoot }) {
  const designSystem = readTextAtRef(ref, designSystemRelPath);
  const allowlist = extractAllowlistFromText(designSystem);
  const diff = git(["diff", upstream, ref, "--unified=0", "--", frontendRoot]).out;
  return analyzeDiffText(diff, { allowlist, frontendRoot });
}

function auditWorkspace({ frontendRoot }) {
  const designSystemPath = path.join(repoRoot, designSystemRelPath);
  const designSystem = existsSync(designSystemPath)
    ? readFileSync(designSystemPath, "utf8")
    : readTextAtRef("HEAD", designSystemRelPath);
  const allowlist = extractAllowlistFromText(designSystem);
  const unstagedDiff = git(["diff", "HEAD", "--unified=0", "--", frontendRoot]).out;
  const stagedDiff = git(["diff", "--cached", "HEAD", "--unified=0", "--", frontendRoot]).out;
  return analyzeDiffText(`${stagedDiff}\n${unstagedDiff}`, { allowlist, frontendRoot });
}

function listTouchedFiles(base, head, frontendRoot) {
  const output = git(["diff", "--name-only", base, head, "--", frontendRoot]).out;
  return output
    .split(/\r?\n/)
    .map(normalizePath)
    .filter((line) => line.length > 0)
    .filter((line) => isUnderFrontendRoot(line, frontendRoot) && !isExcludedPath(line, frontendRoot));
}

function getPerFileCount(audit, filePath, type) {
  return audit.perFile.get(filePath)?.[type] ?? 0;
}

function getPerFileSignatures(audit, filePath, type) {
  return audit.perFile.get(filePath)?.signatures[type] ?? [];
}

function collectAllSignatures(audit, type) {
  const signatures = new Set();
  for (const summary of audit.perFile.values()) {
    for (const signature of summary.signatures[type]) {
      signatures.add(signature);
    }
  }
  return signatures;
}

function countNewSignatures({ baseAudit, headAudit, filePath, type, baseAllSignatures }) {
  const baseFileSignatures = new Set(getPerFileSignatures(baseAudit, filePath, type));
  let newCount = 0;
  let relocatedCount = 0;
  for (const signature of getPerFileSignatures(headAudit, filePath, type)) {
    if (baseFileSignatures.has(signature)) continue;
    if (baseAllSignatures.has(signature)) {
      relocatedCount += 1;
    } else {
      newCount += 1;
    }
  }
  return { newCount, relocatedCount };
}

function buildTopFiles(perFile, type, limit = 20) {
  return [...perFile.entries()]
    .map(([filePath, summary]) => ({
      file: filePath,
      count: summary[type],
      examples: summary.examples.slice(0, 3),
    }))
    .filter((entry) => entry.count > 0)
    .sort((a, b) => b.count - a.count || a.file.localeCompare(b.file))
    .slice(0, limit);
}

export function evaluateRangeGate({ baseAudit, headAudit, touchedFiles, workspaceAudit, statusLines, allowWorkspace }) {
  const failures = [];
  const warnings = [];
  const baseHexSignatures = collectAllSignatures(baseAudit, "hex");
  const baseShadowSignatures = collectAllSignatures(baseAudit, "shadow");

  if (statusLines.length > 0) {
    if (allowWorkspace) {
      warnings.push(`working tree is not clean (${statusLines.length} status line(s)); --allow-workspace was supplied`);
    } else {
      failures.push(`working tree is not clean (${statusLines.length} status line(s)); rerun from a clean tree or pass --allow-workspace for diagnosis`);
    }
  }

  if (headAudit.counts.hex > baseAudit.counts.hex) {
    failures.push(`non-token hex grew from ${baseAudit.counts.hex} to ${headAudit.counts.hex}`);
  }
  if (headAudit.counts.shadow > baseAudit.counts.shadow) {
    failures.push(`private shadow grew from ${baseAudit.counts.shadow} to ${headAudit.counts.shadow}`);
  }

  const touchedGrowth = [];
  const relocatedGrowth = [];
  for (const filePath of touchedFiles) {
    const baseHex = getPerFileCount(baseAudit, filePath, "hex");
    const headHex = getPerFileCount(headAudit, filePath, "hex");
    const baseShadow = getPerFileCount(baseAudit, filePath, "shadow");
    const headShadow = getPerFileCount(headAudit, filePath, "shadow");
    if (headHex > baseHex) {
      const signatureDelta = countNewSignatures({
        baseAudit,
        headAudit,
        filePath,
        type: "hex",
        baseAllSignatures: baseHexSignatures,
      });
      if (signatureDelta.newCount > 0) {
        touchedGrowth.push({ file: filePath, type: "non-token hex", base: baseHex, head: headHex, delta: headHex - baseHex, newCount: signatureDelta.newCount });
      } else if (signatureDelta.relocatedCount > 0) {
        relocatedGrowth.push({ file: filePath, type: "non-token hex", base: baseHex, head: headHex, delta: headHex - baseHex, relocatedCount: signatureDelta.relocatedCount });
      }
    }
    if (headShadow > baseShadow) {
      const signatureDelta = countNewSignatures({
        baseAudit,
        headAudit,
        filePath,
        type: "shadow",
        baseAllSignatures: baseShadowSignatures,
      });
      if (signatureDelta.newCount > 0) {
        touchedGrowth.push({ file: filePath, type: "private shadow", base: baseShadow, head: headShadow, delta: headShadow - baseShadow, newCount: signatureDelta.newCount });
      } else if (signatureDelta.relocatedCount > 0) {
        relocatedGrowth.push({ file: filePath, type: "private shadow", base: baseShadow, head: headShadow, delta: headShadow - baseShadow, relocatedCount: signatureDelta.relocatedCount });
      }
    }
  }

  if (touchedGrowth.length > 0) {
    failures.push(`${touchedGrowth.length} touched file debt bucket(s) grew`);
  }

  const workspaceBlocking =
    (workspaceAudit?.counts.hex ?? 0) + (workspaceAudit?.counts.shadow ?? 0);
  if (workspaceBlocking > 0) {
    const message = `workspace/staged delta has blocking style debt (${workspaceAudit.counts.hex} hex, ${workspaceAudit.counts.shadow} shadow)`;
    if (allowWorkspace) {
      warnings.push(message);
    } else {
    failures.push(message);
    }
  }

  return {
    passed: failures.length === 0,
    failures,
    warnings,
    touchedGrowth,
    relocatedGrowth,
  };
}

function formatSigned(value) {
  return value > 0 ? `+${value}` : String(value);
}

function formatPercent(base, head) {
  if (base === 0 && head === 0) return "0.0%";
  if (base === 0) return "+inf";
  return `${(((head - base) / base) * 100).toFixed(1)}%`;
}

function buildReport({ upstream, base, head, frontendRoot, baseAudit, headAudit, workspaceAudit, touchedFiles, gate }) {
  return {
    upstream,
    base,
    head,
    frontendRoot,
    counts: {
      hex: {
        base: baseAudit.counts.hex,
        head: headAudit.counts.hex,
        delta: headAudit.counts.hex - baseAudit.counts.hex,
        percent: formatPercent(baseAudit.counts.hex, headAudit.counts.hex),
      },
      shadow: {
        base: baseAudit.counts.shadow,
        head: headAudit.counts.shadow,
        delta: headAudit.counts.shadow - baseAudit.counts.shadow,
        percent: formatPercent(baseAudit.counts.shadow, headAudit.counts.shadow),
      },
    },
    workspace: workspaceAudit
      ? {
          hex: workspaceAudit.counts.hex,
          shadow: workspaceAudit.counts.shadow,
        }
      : null,
    touchedFiles: touchedFiles.length,
    touchedGrowth: gate.touchedGrowth,
    relocatedGrowth: gate.relocatedGrowth,
    topRemaining: {
      hex: buildTopFiles(headAudit.perFile, "hex"),
      shadow: buildTopFiles(headAudit.perFile, "shadow"),
    },
    warnings: gate.warnings,
    failures: gate.failures,
    passed: gate.passed,
  };
}

function printMarkdownReport(report) {
  console.log("# Frontend Style Audit Range Gate");
  console.log("");
  console.log(`- upstream: ${report.upstream.hash} ${report.upstream.subject}`);
  console.log(`- base: ${report.base.hash} ${report.base.subject}`);
  console.log(`- head: ${report.head.hash} ${report.head.subject}`);
  console.log(`- frontend root: ${report.frontendRoot}`);
  console.log(`- touched files checked: ${report.touchedFiles}`);
  console.log("");
  console.log("| Metric | Base | Head | Delta | Delta % |");
  console.log("|---|---:|---:|---:|---:|");
  console.log(
    `| non-token hex | ${report.counts.hex.base} | ${report.counts.hex.head} | ${formatSigned(report.counts.hex.delta)} | ${report.counts.hex.percent} |`,
  );
  console.log(
    `| private shadow | ${report.counts.shadow.base} | ${report.counts.shadow.head} | ${formatSigned(report.counts.shadow.delta)} | ${report.counts.shadow.percent} |`,
  );
  if (report.workspace) {
    console.log("");
    console.log(`Workspace/staged delta: ${report.workspace.hex} non-token hex, ${report.workspace.shadow} private shadow`);
  }

  if (report.warnings.length > 0) {
    console.log("");
    console.log("Warnings:");
    for (const warning of report.warnings) console.log(`- ${warning}`);
  }

  console.log("");
  console.log("Touched-file growth:");
  if (report.touchedGrowth.length === 0) {
    console.log("- none");
  } else {
    for (const growth of report.touchedGrowth.slice(0, 20)) {
      console.log(`- ${growth.file}: ${growth.type} ${growth.base} -> ${growth.head} (${formatSigned(growth.delta)})`);
    }
    if (report.touchedGrowth.length > 20) {
      console.log(`- ... and ${report.touchedGrowth.length - 20} more`);
    }
  }

  if (report.relocatedGrowth.length > 0) {
    console.log("");
    console.log("Relocated existing debt ignored for touched-file growth:");
    for (const growth of report.relocatedGrowth.slice(0, 20)) {
      console.log(`- ${growth.file}: ${growth.type} ${growth.base} -> ${growth.head} (${formatSigned(growth.delta)}), ${growth.relocatedCount} existing signature(s)`);
    }
    if (report.relocatedGrowth.length > 20) {
      console.log(`- ... and ${report.relocatedGrowth.length - 20} more`);
    }
  }

  console.log("");
  console.log("Top remaining non-token hex files:");
  if (report.topRemaining.hex.length === 0) {
    console.log("- none");
  } else {
    for (const entry of report.topRemaining.hex) {
      console.log(`- ${entry.count} ${entry.file}`);
    }
  }

  console.log("");
  console.log("Top remaining private shadow files:");
  if (report.topRemaining.shadow.length === 0) {
    console.log("- none");
  } else {
    for (const entry of report.topRemaining.shadow) {
      console.log(`- ${entry.count} ${entry.file}`);
    }
  }

  console.log("");
  if (report.failures.length > 0) {
    console.log("Failures:");
    for (const failure of report.failures) console.log(`- ${failure}`);
    console.log("");
  }
  console.log(`Result: ${report.passed ? "PASS" : "FAIL"}`);
}

function printHelp() {
  console.log(`Frontend style audit range gate

Usage:
  node scripts/audit_frontend_style_range.mjs [options]

Options:
  --upstream <ref>       Upstream ref used for both comparisons.
  --base <ref>           Baseline PR start ref. Defaults to HEAD~1.
  --head <ref>           Candidate head ref. Defaults to HEAD.
  --frontend-root <path> Frontend source root. Defaults to frontend/src.
  --json                 Print machine-readable JSON.
  --allow-workspace      Allow a dirty worktree for diagnostics, with warning.
  --help                 Show this help.

Pass rules:
  - clean working tree unless --allow-workspace is supplied
  - head non-token hex count <= base count
  - head private shadow count <= base count
  - no touched file grows in either blocking debt bucket
  - workspace/staged delta has no blocking debt unless --allow-workspace is supplied
`);
}

export function parseArgs(argv) {
  const result = {
    upstream: null,
    base: "HEAD~1",
    head: "HEAD",
    frontendRoot: defaultFrontendRoot,
    json: false,
    allowWorkspace: false,
    help: false,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--help" || arg === "-h") {
      result.help = true;
      continue;
    }
    if (arg === "--json") {
      result.json = true;
      continue;
    }
    if (arg === "--allow-workspace") {
      result.allowWorkspace = true;
      continue;
    }
    if (["--upstream", "--base", "--head", "--frontend-root"].includes(arg)) {
      const value = argv[index + 1];
      if (!value || value.startsWith("--")) {
        throw new Error(`${arg} requires a value`);
      }
      if (arg === "--upstream") result.upstream = value;
      if (arg === "--base") result.base = value;
      if (arg === "--head") result.head = value;
      if (arg === "--frontend-root") result.frontendRoot = normalizePath(value);
      index += 1;
      continue;
    }
    throw new Error(`unknown argument: ${arg}`);
  }

  if (!result.upstream) result.upstream = resolveDefaultUpstream();
  return result;
}

function main(argv = process.argv.slice(2)) {
  const options = parseArgs(argv);
  if (options.help) {
    printHelp();
    return 0;
  }

  const statusLines = git(["status", "--porcelain"]).out
    .split(/\r?\n/)
    .filter(Boolean);
  const frontendRoot = normalizePath(options.frontendRoot);
  const upstream = resolveRefLabel(options.upstream);
  const base = resolveRefLabel(options.base);
  const head = resolveRefLabel(options.head);

  const baseAudit = auditCommitRange({
    upstream: options.upstream,
    ref: options.base,
    frontendRoot,
  });
  const headAudit = auditCommitRange({
    upstream: options.upstream,
    ref: options.head,
    frontendRoot,
  });
  const workspaceAudit = auditWorkspace({ frontendRoot });
  const touchedFiles = listTouchedFiles(options.base, options.head, frontendRoot);
  const gate = evaluateRangeGate({
    baseAudit,
    headAudit,
    touchedFiles,
    workspaceAudit,
    statusLines,
    allowWorkspace: options.allowWorkspace,
  });
  const report = buildReport({
    upstream,
    base,
    head,
    frontendRoot,
    baseAudit,
    headAudit,
    workspaceAudit,
    touchedFiles,
    gate,
  });

  if (options.json) {
    console.log(JSON.stringify(report, null, 2));
  } else {
    printMarkdownReport(report);
  }

  return gate.passed ? 0 : 1;
}

const isDirect = process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url);
if (isDirect) {
  try {
    process.exitCode = main();
  } catch (error) {
    console.error(error instanceof Error ? error.message : String(error));
    process.exitCode = 2;
  }
}
