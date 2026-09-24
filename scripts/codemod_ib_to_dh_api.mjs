#!/usr/bin/env node

/**
 * Codemod: 页面 CSS 的 IB 主题 token 引用 -> 深色终端 token 引用。
 *
 * 背景：`frontend/src/styles/tokens.css` 在 `.themed-route-boundary.theme-dh-api`
 * 上把 `--ib-*` 重映射为 `--dh-api-*`。CSS 自定义属性在声明处即完成替换，
 * 路由边界上算出的是钢蓝字面值并按字面值继承，页面根上的 Nocturne scope
 * （重映射 `--dh-api-*`）翻不动它。所以页面接 Nocturne 必须在引用侧改写。
 *
 * 参考实现与回归基准：commit 20f560b0（/ledger-pnl 手工转换，7 个样式文件）。
 *
 * 匹配方式：脚本不做字符串前缀替换，而是解析 `var()` 节点、取出完整的自定义
 * 属性名再比对。`--ib-surface` / `--ib-surface-muted`、`--ib-accent` /
 * `--ib-accent-hover` 这类前缀包含关系因此在结构上不可能误伤。
 *
 * 用法见 --help；单元自测见 --selftest。
 */

import { readdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import path from "node:path";
import process from "node:process";

const repoRoot = path.resolve(import.meta.dirname, "..");

/** 颜色/表面 token 映射（严格 1:1，来自已提交的 ledger-pnl 转换）。 */
const COLOR_MAP = new Map([
  ["--ib-ink", "--dh-api-ink"],
  ["--ib-ink-secondary", "--dh-api-soft"],
  ["--ib-ink-muted", "--dh-api-muted"],
  ["--ib-surface", "--dh-api-panel"],
  ["--ib-surface-muted", "--dh-api-panel-2"],
  ["--ib-hairline", "--dh-api-line"],
  ["--ib-rule-strong", "--dh-api-line"],
  ["--ib-paper", "--dh-api-bg"],
  ["--ib-accent", "--dh-api-blue"],
  ["--ib-accent-hover", "--dh-api-blue"],
  ["--ib-accent-surface", "--dh-api-blue-soft"],
  ["--ib-up", "--dh-api-green"],
  ["--ib-down", "--dh-api-red"],
  ["--ib-warn", "--dh-api-amber"],
  ["--ib-gold", "--dh-api-amber"],
]);

/**
 * 圆角归一（--radius 开启时生效）。
 * 键为源 token，值为允许一并吞掉的 fallback 白名单（"" 表示无 fallback）。
 * 白名单之外的 fallback 一律不改，进 skip 报告等人工决策。
 */
const RADIUS_SOURCES = new Map([
  ["--ib-radius", new Set(["", "2px", "6px"])],
  ["--moss-radius-sm", new Set([""])],
  ["--dh-api-radius", new Set(["6px"])],
]);

const RADIUS_TARGET = "var(--dh-api-radius)";

const CSS_EXTENSIONS = new Set([".css"]);
const CODE_EXTENSIONS = new Set([".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"]);
const IGNORED_DIRECTORIES = new Set([
  ".git",
  ".codex-tmp",
  "node_modules",
  "dist",
  "build",
  "coverage",
  "playwright-report",
  "test-results",
  ".venv",
  "__pycache__",
]);

const HEX_PATTERN = /#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\b/g;
const IB_TOKEN_PATTERN = /--ib-[a-zA-Z0-9_-]+/g;
const BOM = "\ufeff";

const SKIP_REASONS = {
  hasFallback: "has-fallback",
  shadowed: "shadowed-by-local-declaration",
  unmapped: "unmapped-ib-token",
  inComment: "inside-css-comment",
  radiusDisabled: "radius-normalization-disabled",
  radiusUnknownFallback: "radius-unknown-fallback",
  multiline: "spans-newline",
  malformed: "unbalanced-var-parens",
  overlapped: "nested-inside-replaced-node",
};

/**
 * 跳过项的采样上限。
 * 0 = 只计数不采样；有限值 = 只留头部若干条；未登记 = 不限，
 * 因为这些类别必须逐条给人看（带 fallback、未映射 token、解析异常）。
 */
const BULK_SKIP_SAMPLE_CAP = new Map([
  [SKIP_REASONS.radiusDisabled, 0],
  [SKIP_REASONS.shadowed, 40],
  [SKIP_REASONS.inComment, 40],
  [SKIP_REASONS.overlapped, 40],
]);

// ---------------------------------------------------------------------------
// CSS 扫描
// ---------------------------------------------------------------------------

function computeCommentRanges(text) {
  const ranges = [];
  let cursor = 0;
  while (cursor < text.length) {
    const open = text.indexOf("/*", cursor);
    if (open === -1) break;
    const close = text.indexOf("*/", open + 2);
    const end = close === -1 ? text.length : close + 2;
    ranges.push([open, end]);
    cursor = end;
  }
  return ranges;
}

function isInsideRanges(ranges, index) {
  for (const [start, end] of ranges) {
    if (index < start) return false;
    if (index < end) return true;
  }
  return false;
}

function skipString(text, quoteIndex) {
  const quote = text[quoteIndex];
  let cursor = quoteIndex + 1;
  while (cursor < text.length) {
    const char = text[cursor];
    if (char === "\\") {
      cursor += 2;
      continue;
    }
    if (char === quote) return cursor + 1;
    if (char === "\n") return cursor;
    cursor += 1;
  }
  return text.length;
}

function findMatchingParen(text, openIndex) {
  let depth = 0;
  let cursor = openIndex;
  while (cursor < text.length) {
    const char = text[cursor];
    if (char === "'" || char === '"') {
      cursor = skipString(text, cursor);
      continue;
    }
    if (char === "/" && text[cursor + 1] === "*") {
      const close = text.indexOf("*/", cursor + 2);
      cursor = close === -1 ? text.length : close + 2;
      continue;
    }
    if (char === "(") {
      depth += 1;
    } else if (char === ")") {
      depth -= 1;
      if (depth === 0) return cursor;
    }
    cursor += 1;
  }
  return -1;
}

function findTopLevelComma(text, start, end) {
  let depth = 0;
  let cursor = start;
  while (cursor < end) {
    const char = text[cursor];
    if (char === "'" || char === '"') {
      cursor = skipString(text, cursor);
      continue;
    }
    if (char === "/" && text[cursor + 1] === "*") {
      const close = text.indexOf("*/", cursor + 2);
      cursor = close === -1 ? end : close + 2;
      continue;
    }
    if (char === "(") depth += 1;
    else if (char === ")") depth -= 1;
    else if (char === "," && depth === 0) return cursor;
    cursor += 1;
  }
  return -1;
}

/** 解析出全部 `var()` 节点，含名字的精确 offset，便于原地 splice。 */
function collectVarNodes(text) {
  const comments = computeCommentRanges(text);
  const nodes = [];
  const pattern = /var\(/gi;
  let match;
  while ((match = pattern.exec(text)) !== null) {
    const start = match.index;
    const previous = start === 0 ? "" : text[start - 1];
    if (/[-\w]/.test(previous)) continue;

    const openIndex = start + match[0].length - 1;
    const closeIndex = findMatchingParen(text, openIndex);
    if (closeIndex === -1) {
      nodes.push({ start, end: text.length, malformed: true, inComment: isInsideRanges(comments, start) });
      continue;
    }

    const argsStart = openIndex + 1;
    const commaIndex = findTopLevelComma(text, argsStart, closeIndex);
    const nameEndRaw = commaIndex === -1 ? closeIndex : commaIndex;
    const nameRaw = text.slice(argsStart, nameEndRaw);
    const leading = nameRaw.length - nameRaw.trimStart().length;
    const name = nameRaw.trim();
    const nameStart = argsStart + leading;

    nodes.push({
      start,
      end: closeIndex + 1,
      malformed: false,
      inComment: isInsideRanges(comments, start),
      name,
      nameStart,
      nameEnd: nameStart + name.length,
      fallback: commaIndex === -1 ? null : text.slice(commaIndex + 1, closeIndex).trim(),
      raw: text.slice(start, closeIndex + 1),
    });
  }
  return nodes;
}

/** 声明侧：`--ib-x: ...`（注释内的不算）。只报告，从不改写。 */
function collectLocalDeclarations(text) {
  const comments = computeCommentRanges(text);
  const declarations = [];
  const pattern = /(^|[;{}\s])(--[a-zA-Z0-9_-]+)\s*:/g;
  let match;
  while ((match = pattern.exec(text)) !== null) {
    const nameIndex = match.index + match[1].length;
    if (isInsideRanges(comments, nameIndex)) continue;
    if (!match[2].startsWith("--ib-")) continue;
    declarations.push({ name: match[2], index: nameIndex });
  }
  return declarations;
}

function buildLineIndex(text) {
  const starts = [0];
  for (let i = 0; i < text.length; i += 1) {
    if (text[i] === "\n") starts.push(i + 1);
  }
  return starts;
}

function lineOf(lineStarts, index) {
  let low = 0;
  let high = lineStarts.length - 1;
  while (low < high) {
    const mid = (low + high + 1) >> 1;
    if (lineStarts[mid] <= index) low = mid;
    else high = mid - 1;
  }
  return low + 1;
}

// ---------------------------------------------------------------------------
// 转换核心（纯函数，自测直接复用）
// ---------------------------------------------------------------------------

/**
 * @param {string} text
 * @param {{radius?: boolean, withFallback?: boolean, allowShadowed?: boolean, colorMap?: Map<string,string>}} options
 */
export function transform(text, options = {}) {
  const colorMap = options.colorMap ?? COLOR_MAP;
  const radius = options.radius === true;
  const withFallback = options.withFallback === true;
  const allowShadowed = options.allowShadowed === true;

  const lineStarts = buildLineIndex(text);
  const declarations = collectLocalDeclarations(text).map((declaration) => ({
    name: declaration.name,
    line: lineOf(lineStarts, declaration.index),
  }));
  const shadowed = new Set(declarations.map((declaration) => declaration.name));

  const nodes = collectVarNodes(text);
  const candidates = [];
  const skipped = [];

  for (const node of nodes) {
    if (node.malformed) {
      skipped.push({ reason: SKIP_REASONS.malformed, token: null, line: lineOf(lineStarts, node.start), text: "" });
      continue;
    }
    if (!node.name.startsWith("--")) continue;

    const line = lineOf(lineStarts, node.start);
    const isRadiusSource = RADIUS_SOURCES.has(node.name);
    const isColorSource = colorMap.has(node.name);
    const isIbToken = node.name.startsWith("--ib-");
    if (!isRadiusSource && !isColorSource && !isIbToken) continue;

    if (node.inComment) {
      skipped.push({ reason: SKIP_REASONS.inComment, token: node.name, line, text: node.raw });
      continue;
    }

    if (isRadiusSource) {
      const fallback = node.fallback ?? "";
      if (node.name === "--dh-api-radius" && fallback === "") continue; // 已是目标形态
      if (!radius) {
        skipped.push({ reason: SKIP_REASONS.radiusDisabled, token: node.name, line, text: node.raw });
        continue;
      }
      if (!RADIUS_SOURCES.get(node.name).has(fallback)) {
        skipped.push({ reason: SKIP_REASONS.radiusUnknownFallback, token: node.name, line, text: node.raw });
        continue;
      }
      if (/[\r\n]/.test(node.raw)) {
        skipped.push({ reason: SKIP_REASONS.multiline, token: node.name, line, text: node.raw });
        continue;
      }
      candidates.push({
        start: node.start,
        end: node.end,
        replacement: RADIUS_TARGET,
        token: node.name,
        target: "--dh-api-radius",
        label: `${node.raw.replace(/\s+/g, " ")} -> ${RADIUS_TARGET}`,
        line,
        kind: "radius",
      });
      continue;
    }

    if (!isColorSource) {
      skipped.push({ reason: SKIP_REASONS.unmapped, token: node.name, line, text: node.raw });
      continue;
    }

    if (shadowed.has(node.name) && !allowShadowed) {
      skipped.push({ reason: SKIP_REASONS.shadowed, token: node.name, line, text: node.raw });
      continue;
    }

    if (node.fallback !== null && !withFallback) {
      skipped.push({ reason: SKIP_REASONS.hasFallback, token: node.name, line, text: node.raw });
      continue;
    }

    // 只 splice 名字本身：fallback、空白、换行、括号全部原样保留。
    candidates.push({
      start: node.nameStart,
      end: node.nameEnd,
      replacement: colorMap.get(node.name),
      token: node.name,
      target: colorMap.get(node.name),
      label: `${node.name} -> ${colorMap.get(node.name)}`,
      line,
      kind: "color",
    });
  }

  // 外层整节点替换（radius）会吞掉内部的 var()，按 start 升序 + 跨度降序去重。
  candidates.sort((a, b) => (a.start - b.start) || (b.end - a.end));
  const edits = [];
  let boundary = -1;
  for (const candidate of candidates) {
    if (candidate.start < boundary) {
      skipped.push({
        reason: SKIP_REASONS.overlapped,
        token: candidate.token,
        line: candidate.line,
        text: text.slice(candidate.start, candidate.end),
      });
      continue;
    }
    edits.push(candidate);
    boundary = candidate.end;
  }

  let output = text;
  for (let i = edits.length - 1; i >= 0; i -= 1) {
    const edit = edits[i];
    output = output.slice(0, edit.start) + edit.replacement + output.slice(edit.end);
  }

  const replacements = new Map();
  for (const edit of edits) {
    replacements.set(edit.label, (replacements.get(edit.label) ?? 0) + 1);
  }

  return { output, edits, replacements, skipped, declarations };
}

// ---------------------------------------------------------------------------
// 写盘安全校验
// ---------------------------------------------------------------------------

function newlineProfile(text) {
  const crlf = (text.match(/\r\n/g) ?? []).length;
  const lineFeeds = (text.match(/\n/g) ?? []).length;
  const carriageReturns = (text.match(/\r/g) ?? []).length;
  return `crlf=${crlf};lf=${lineFeeds - crlf};cr=${carriageReturns - crlf}`;
}

function countOf(text, pattern) {
  return (text.match(pattern) ?? []).length;
}

/** 写盘前逐文件校验：任何一条不过就不落盘。 */
export function validateRewrite(original, updated, edits) {
  const problems = [];

  const encoded = Buffer.from(updated, "utf8");
  let roundTripped = "";
  try {
    // ignoreBOM: true 表示"不吞掉 BOM"，往返才是逐字符相等。
    roundTripped = new TextDecoder("utf-8", { fatal: true, ignoreBOM: true }).decode(encoded);
  } catch (error) {
    problems.push(`结果不是有效 UTF-8：${error.message}`);
  }
  if (roundTripped !== updated) problems.push("UTF-8 编解码往返不一致");

  if (newlineProfile(original) !== newlineProfile(updated)) problems.push("换行风格发生变化（CRLF/LF 计数不一致）");
  if (countOf(original, /\n/g) !== countOf(updated, /\n/g)) problems.push("行数发生变化");
  if (countOf(original, /\{/g) !== countOf(updated, /\{/g)) problems.push("`{` 数量变化");
  if (countOf(original, /\}/g) !== countOf(updated, /\}/g)) problems.push("`}` 数量变化");
  if (countOf(original, /;/g) !== countOf(updated, /;/g)) problems.push("`;` 数量变化");
  if (countOf(original, HEX_PATTERN) !== countOf(updated, HEX_PATTERN)) problems.push("hex 字面值数量变化（会污染视觉 token 审计基线）");
  if (countOf(original, /var\(/gi) !== countOf(updated, /var\(/gi)) problems.push("`var(` 数量变化");

  const expectedDelta = edits.reduce((sum, edit) => sum + (edit.replacement.length - (edit.end - edit.start)), 0);
  if (updated.length !== original.length + expectedDelta) problems.push("长度变化与替换计划不符");

  return problems;
}

// ---------------------------------------------------------------------------
// 文件收集
// ---------------------------------------------------------------------------

function walk(target, cssFiles, codeFiles) {
  const stats = statSync(target);
  if (stats.isFile()) {
    const extension = path.extname(target).toLowerCase();
    if (CSS_EXTENSIONS.has(extension)) cssFiles.push(target);
    else if (CODE_EXTENSIONS.has(extension)) codeFiles.push(target);
    return;
  }
  for (const entry of readdirSync(target, { withFileTypes: true })) {
    if (entry.isDirectory()) {
      if (IGNORED_DIRECTORIES.has(entry.name)) continue;
      walk(path.join(target, entry.name), cssFiles, codeFiles);
      continue;
    }
    if (!entry.isFile()) continue;
    const full = path.join(target, entry.name);
    const extension = path.extname(entry.name).toLowerCase();
    if (CSS_EXTENSIONS.has(extension)) cssFiles.push(full);
    else if (CODE_EXTENSIONS.has(extension)) codeFiles.push(full);
  }
}

function toRepoPath(fullPath) {
  return path.relative(repoRoot, fullPath).replace(/\\/g, "/");
}

function readTextFile(fullPath) {
  const buffer = readFileSync(fullPath);
  let text;
  try {
    text = new TextDecoder("utf-8", { fatal: true, ignoreBOM: true }).decode(buffer);
  } catch (error) {
    return { error: `不是有效 UTF-8：${error.message}` };
  }
  const hasBom = text.startsWith(BOM);
  return { text: hasBom ? text.slice(BOM.length) : text, hasBom };
}

// ---------------------------------------------------------------------------
// 运行
// ---------------------------------------------------------------------------

function runCodemod(paths, options) {
  const cssFiles = [];
  const codeFiles = [];
  for (const entry of paths) {
    const resolved = path.resolve(repoRoot, entry);
    walk(resolved, cssFiles, codeFiles);
  }
  cssFiles.sort();
  codeFiles.sort();

  const report = {
    mode: options.dryRun ? "dry-run" : "write",
    options: {
      radius: options.radius,
      withFallback: options.withFallback,
      allowShadowed: options.allowShadowed,
    },
    scanned: { css: cssFiles.length, code: codeFiles.length },
    files: [],
    totals: { replacements: 0, filesChanged: 0, byToken: {} },
    skipped: { byReason: {}, samples: [] },
    localDeclarations: [],
    nonCssReferences: [],
    failures: [],
  };

  for (const fullPath of cssFiles) {
    const repoPath = toRepoPath(fullPath);
    const read = readTextFile(fullPath);
    if (read.error) {
      report.failures.push({ file: repoPath, problems: [read.error] });
      continue;
    }

    const result = transform(read.text, options);

    for (const item of result.skipped) {
      report.skipped.byReason[item.reason] = (report.skipped.byReason[item.reason] ?? 0) + 1;
      // 需要人工决策的类别不设采样上限，否则会被大宗跳过项挤掉；
      // 大宗类别（shadowed / 注释内 / 被外层吞掉）只留少量样本，真实计数看 byReason。
      const capped = BULK_SKIP_SAMPLE_CAP.get(item.reason);
      if (capped === 0) continue;
      if (capped !== undefined) {
        const seen = report.skipped.byReason[item.reason];
        if (seen > capped) continue;
      }
      report.skipped.samples.push({
        file: repoPath,
        line: item.line,
        reason: item.reason,
        token: item.token,
        text: item.text,
      });
    }

    if (result.declarations.length > 0) {
      report.localDeclarations.push({
        file: repoPath,
        declarations: result.declarations.map((declaration) => `${declaration.name} @L${declaration.line}`),
      });
    }

    if (result.edits.length === 0) continue;

    const byToken = {};
    for (const [key, count] of result.replacements) byToken[key] = count;
    for (const [key, count] of result.replacements) {
      report.totals.byToken[key] = (report.totals.byToken[key] ?? 0) + count;
    }
    report.totals.replacements += result.edits.length;
    report.totals.filesChanged += 1;

    const fileEntry = { file: repoPath, replacements: result.edits.length, byToken, written: false };

    const problems = validateRewrite(read.text, result.output, result.edits);
    if (problems.length > 0) {
      report.failures.push({ file: repoPath, problems });
      fileEntry.validation = problems;
    } else if (!options.dryRun) {
      writeFileSync(fullPath, Buffer.from((read.hasBom ? BOM : "") + result.output, "utf8"));
      fileEntry.written = true;
    }

    report.files.push(fileEntry);
  }

  for (const fullPath of codeFiles) {
    const read = readTextFile(fullPath);
    if (read.error) continue;
    const matches = read.text.match(IB_TOKEN_PATTERN);
    if (!matches) continue;
    const tokens = {};
    for (const token of matches) tokens[token] = (tokens[token] ?? 0) + 1;
    report.nonCssReferences.push({ file: toRepoPath(fullPath), count: matches.length, tokens });
  }
  report.nonCssReferences.sort((a, b) => b.count - a.count);

  return report;
}

function printReport(report) {
  const flags = [
    `mode=${report.mode}`,
    `radius=${report.options.radius ? "on" : "off"}`,
    `fallback=${report.options.withFallback ? "rewrite" : "skip"}`,
    `shadowed=${report.options.allowShadowed ? "rewrite" : "skip"}`,
  ].join("  ");
  console.log(`IB -> DH-API codemod   ${flags}`);
  console.log(`scanned: ${report.scanned.css} css / ${report.scanned.code} code files`);
  console.log("");

  if (report.files.length === 0) {
    console.log("替换: 无");
  } else {
    for (const file of report.files) {
      const suffix = file.written ? " [written]" : report.mode === "write" ? " [NOT written]" : "";
      console.log(`${file.file}${suffix}`);
      for (const [key, count] of Object.entries(file.byToken).sort((a, b) => b[1] - a[1])) {
        console.log(`    ${String(count).padStart(5)}  ${key}`);
      }
      console.log(`    ----- ${file.replacements} 处`);
    }
    console.log("");
    console.log("按 token 汇总:");
    for (const [key, count] of Object.entries(report.totals.byToken).sort((a, b) => b[1] - a[1])) {
      console.log(`    ${String(count).padStart(5)}  ${key}`);
    }
  }
  console.log("");
  console.log(`TOTAL ${report.totals.replacements} 处替换，涉及 ${report.totals.filesChanged} 个文件`);

  const skipEntries = Object.entries(report.skipped.byReason).sort((a, b) => b[1] - a[1]);
  if (skipEntries.length > 0) {
    console.log("");
    console.log("跳过项:");
    for (const [reason, count] of skipEntries) {
      console.log(`    ${String(count).padStart(5)}  ${reason}`);
    }
  }

  const manualSamples = report.skipped.samples.filter(
    (sample) => sample.reason === SKIP_REASONS.hasFallback || sample.reason === SKIP_REASONS.radiusUnknownFallback,
  );
  if (manualSamples.length > 0) {
    console.log("");
    console.log("带 fallback 的引用（未自动改，需人工决策）:");
    for (const sample of manualSamples) {
      console.log(`    ${sample.file}:${sample.line}  ${sample.text}`);
    }
  }

  const unmapped = report.skipped.samples.filter((sample) => sample.reason === SKIP_REASONS.unmapped);
  if (unmapped.length > 0) {
    const byToken = new Map();
    for (const sample of unmapped) {
      if (!byToken.has(sample.token)) byToken.set(sample.token, []);
      byToken.get(sample.token).push(`${sample.file}:${sample.line}`);
    }
    console.log("");
    console.log("映射表未覆盖的 --ib-* token（未自动改，需人工决策）:");
    for (const [token, locations] of [...byToken].sort((a, b) => b[1].length - a[1].length)) {
      console.log(`    ${String(locations.length).padStart(5)}  ${token}`);
      console.log(`           ${locations.slice(0, 5).join(", ")}${locations.length > 5 ? ", ..." : ""}`);
    }
  }

  if (report.localDeclarations.length > 0) {
    console.log("");
    console.log("本文件自带 --ib-* 声明（页面级 shim，需人工决策；其引用默认跳过）:");
    for (const entry of report.localDeclarations) {
      console.log(`    ${entry.file}`);
      console.log(`        ${entry.declarations.join(", ")}`);
    }
  }

  if (report.nonCssReferences.length > 0) {
    console.log("");
    console.log("非 CSS 文件中的 --ib-* 引用（不自动改）:");
    for (const entry of report.nonCssReferences) {
      console.log(`    ${String(entry.count).padStart(5)}  ${entry.file}`);
    }
  }

  if (report.failures.length > 0) {
    console.log("");
    console.log("校验失败（未写盘）:");
    for (const failure of report.failures) {
      console.log(`    ${failure.file}`);
      for (const problem of failure.problems) console.log(`        ${problem}`);
    }
  }
}

// ---------------------------------------------------------------------------
// 自测
// ---------------------------------------------------------------------------

function runSelftest() {
  const cases = [];

  const collisionInput = [
    ".a { color: var(--ib-ink); }",
    ".b { color: var(--ib-ink-secondary); }",
    ".c { color: var(--ib-ink-muted); }",
    ".d { background: var(--ib-surface); }",
    ".e { background: var(--ib-surface-muted); }",
    ".f { color: var(--ib-accent); }",
    ".g { color: var(--ib-accent-hover); }",
    ".h { background: var(--ib-accent-surface); }",
    "",
  ].join("\n");
  const collisionExpected = [
    ".a { color: var(--dh-api-ink); }",
    ".b { color: var(--dh-api-soft); }",
    ".c { color: var(--dh-api-muted); }",
    ".d { background: var(--dh-api-panel); }",
    ".e { background: var(--dh-api-panel-2); }",
    ".f { color: var(--dh-api-blue); }",
    ".g { color: var(--dh-api-blue); }",
    ".h { background: var(--dh-api-blue-soft); }",
    "",
  ].join("\n");

  cases.push({
    name: "前缀碰撞: ink / ink-secondary / ink-muted、surface / surface-muted、accent / accent-hover / accent-surface",
    run: () => {
      const { output } = transform(collisionInput);
      return output === collisionExpected ? null : `期望:\n${collisionExpected}\n实得:\n${output}`;
    },
  });

  cases.push({
    name: "前缀碰撞: 不得产出 --dh-api-ink-secondary / --dh-api-panel-muted 之类拼接残骸",
    run: () => {
      const { output } = transform(collisionInput);
      const bad = output.match(/--dh-api-[a-z0-9-]*(?:-secondary|-hover|-muted0|-surface0)\b/g);
      return bad ? `出现拼接残骸: ${bad.join(", ")}` : null;
    },
  });

  cases.push({
    name: "映射表顺序无关: 按 token 名升序 / 降序重排映射表结果一致",
    run: () => {
      const ascending = new Map([...COLOR_MAP].sort((a, b) => a[0].length - b[0].length));
      const descending = new Map([...COLOR_MAP].sort((a, b) => b[0].length - a[0].length));
      const base = transform(collisionInput).output;
      const first = transform(collisionInput, { colorMap: ascending }).output;
      const second = transform(collisionInput, { colorMap: descending }).output;
      if (base !== collisionExpected) return "基准输出不符合预期";
      if (first !== base || second !== base) return "重排映射表后输出不一致";
      return null;
    },
  });

  cases.push({
    name: "声明侧不改写: `--ib-surface: ...` 保持原样",
    run: () => {
      const input = ".x {\n  --ib-surface: var(--dh-api-panel);\n  color: var(--ib-ink);\n}\n";
      const { output, declarations } = transform(input, { allowShadowed: true });
      if (!output.includes("--ib-surface: var(--dh-api-panel);")) return "声明侧被改写";
      if (!output.includes("color: var(--dh-api-ink);")) return "引用侧未改写";
      if (declarations.length !== 1 || declarations[0].name !== "--ib-surface") return "声明未被登记";
      return null;
    },
  });

  cases.push({
    name: "shadow 默认跳过: 本文件声明过的 token 不自动改，--allow-shadowed 才改",
    run: () => {
      const input = ".x { --ib-hairline: var(--dh-api-line-soft); }\n.y { border-color: var(--ib-hairline); }\n";
      const guarded = transform(input);
      if (guarded.edits.length !== 0) return "默认应跳过 shadowed token";
      if (!guarded.skipped.some((item) => item.reason === SKIP_REASONS.shadowed)) return "未登记 shadowed 跳过项";
      const forced = transform(input, { allowShadowed: true });
      if (forced.edits.length !== 1) return "--allow-shadowed 下应改写 1 处";
      return null;
    },
  });

  cases.push({
    name: "带 fallback: 默认跳过并登记，--with-fallback 时只换名字、保留 fallback",
    run: () => {
      const input = ".a { color: var(--ib-ink-muted, var(--sa-dh-muted)); }\n";
      const guarded = transform(input);
      if (guarded.edits.length !== 0) return "默认应跳过带 fallback 的引用";
      if (!guarded.skipped.some((item) => item.reason === SKIP_REASONS.hasFallback)) return "未登记 has-fallback 跳过项";
      const forced = transform(input, { withFallback: true });
      const expected = ".a { color: var(--dh-api-muted, var(--sa-dh-muted)); }\n";
      return forced.output === expected ? null : `期望 ${expected.trim()}，实得 ${forced.output.trim()}`;
    },
  });

  cases.push({
    name: "嵌套 fallback: 内外层都是 IB token 时两层都要处理",
    run: () => {
      const input = ".a { color: var(--ib-ink-secondary, var(--ib-ink-muted)); }\n";
      const forced = transform(input, { withFallback: true });
      const expected = ".a { color: var(--dh-api-soft, var(--dh-api-muted)); }\n";
      return forced.output === expected ? null : `期望 ${expected.trim()}，实得 ${forced.output.trim()}`;
    },
  });

  cases.push({
    name: "圆角归一: 默认关闭；开启后 2px/6px/无 fallback 与 --moss-radius-sm、--dh-api-radius 6px 全部收敛",
    run: () => {
      const input = [
        ".a { border-radius: var(--ib-radius, 2px); }",
        ".b { border-radius: var(--ib-radius, 6px); }",
        ".c { border-radius: var(--ib-radius); }",
        ".d { border-radius: var(--moss-radius-sm); }",
        ".e { border-radius: var(--dh-api-radius, 6px); }",
        ".f { border-radius: var(--dh-api-radius); }",
        ".g { border-radius: var(--ib-radius, 2px) var(--ib-radius, 2px) 0 0; }",
        "",
      ].join("\n");
      const off = transform(input);
      if (off.edits.length !== 0) return "默认应关闭圆角归一";
      const on = transform(input, { radius: true });
      const expected = [
        ".a { border-radius: var(--dh-api-radius); }",
        ".b { border-radius: var(--dh-api-radius); }",
        ".c { border-radius: var(--dh-api-radius); }",
        ".d { border-radius: var(--dh-api-radius); }",
        ".e { border-radius: var(--dh-api-radius); }",
        ".f { border-radius: var(--dh-api-radius); }",
        ".g { border-radius: var(--dh-api-radius) var(--dh-api-radius) 0 0; }",
        "",
      ].join("\n");
      return on.output === expected ? null : `期望:\n${expected}\n实得:\n${on.output}`;
    },
  });

  cases.push({
    name: "圆角归一: 白名单外的 fallback 不动，进 skip 报告",
    run: () => {
      const input = ".a { border-radius: var(--ib-radius, 12px); }\n";
      const on = transform(input, { radius: true });
      if (on.edits.length !== 0) return "非白名单 fallback 不应改写";
      return on.skipped.some((item) => item.reason === SKIP_REASONS.radiusUnknownFallback)
        ? null
        : "未登记 radius-unknown-fallback";
    },
  });

  cases.push({
    name: "注释内引用不改写，但要登记",
    run: () => {
      const input = "/* color: var(--ib-ink); */\n.a { color: var(--ib-ink); }\n";
      const { output, edits, skipped } = transform(input);
      if (edits.length !== 1) return `期望 1 处替换，实得 ${edits.length}`;
      if (!output.startsWith("/* color: var(--ib-ink); */")) return "注释被改写";
      return skipped.some((item) => item.reason === SKIP_REASONS.inComment) ? null : "未登记 inside-css-comment";
    },
  });

  cases.push({
    name: "未映射的 --ib-* token 不改写并登记（--ib-serif / --ib-shadow / --ib-warning）",
    run: () => {
      const input = ".a { font-family: var(--ib-serif, serif); box-shadow: var(--ib-shadow); color: var(--ib-warning, red); }\n";
      const { output, edits, skipped } = transform(input, { withFallback: true });
      if (edits.length !== 0) return "未映射 token 不应改写";
      if (output !== input) return "输出被改动";
      const reasons = new Set(skipped.map((item) => item.reason));
      return reasons.has(SKIP_REASONS.unmapped) ? null : "未登记 unmapped-ib-token";
    },
  });

  cases.push({
    name: "CRLF / LF 混用不被规范化，且通过写盘校验",
    run: () => {
      const input = ".a {\r\n  color: var(--ib-ink);\r\n}\n.b {\n  color: var(--ib-down);\n}\r\n";
      const { output, edits } = transform(input);
      if (edits.length !== 2) return `期望 2 处替换，实得 ${edits.length}`;
      if (newlineProfile(input) !== newlineProfile(output)) return "换行风格被改变";
      const problems = validateRewrite(input, output, edits);
      return problems.length === 0 ? null : `校验失败: ${problems.join("; ")}`;
    },
  });

  cases.push({
    name: "换行内嵌的 var() 只换名字，不折叠空白",
    run: () => {
      const input = ".a {\n  color: var(\n    --ib-ink-secondary\n  );\n}\n";
      const expected = ".a {\n  color: var(\n    --dh-api-soft\n  );\n}\n";
      const { output } = transform(input);
      return output === expected ? null : `期望:\n${expected}\n实得:\n${output}`;
    },
  });

  cases.push({
    name: "幂等: 二次运行 0 处替换",
    run: () => {
      const first = transform(collisionInput, { radius: true, withFallback: true });
      const second = transform(first.output, { radius: true, withFallback: true });
      return second.edits.length === 0 ? null : `二次运行仍有 ${second.edits.length} 处替换`;
    },
  });

  cases.push({
    name: "不写入任何 hex 字面值",
    run: () => {
      const input = ".a { color: var(--ib-ink); border-radius: var(--ib-radius, 2px); }\n";
      const { output, edits } = transform(input, { radius: true });
      if (/#[0-9a-fA-F]{3}/.test(output)) return "输出包含 hex 字面值";
      const problems = validateRewrite(input, output, edits);
      return problems.length === 0 ? null : `校验失败: ${problems.join("; ")}`;
    },
  });

  cases.push({
    name: "非自定义属性的 var() 与相邻标识符不误伤（--x-ib-ink / foovar(...)）",
    run: () => {
      const input = ".a { color: var(--x-ib-ink); background: foovar(--ib-ink); }\n";
      const { output, edits } = transform(input);
      if (edits.length !== 0) return `不应改写，实得 ${edits.length} 处`;
      return output === input ? null : "输出被改动";
    },
  });

  let failed = 0;
  for (const testCase of cases) {
    let problem = null;
    try {
      problem = testCase.run();
    } catch (error) {
      problem = `抛出异常: ${error.stack}`;
    }
    if (problem) {
      failed += 1;
      console.log(`FAIL  ${testCase.name}`);
      console.log(
        problem
          .split("\n")
          .map((line) => `        ${line}`)
          .join("\n"),
      );
    } else {
      console.log(`PASS  ${testCase.name}`);
    }
  }
  console.log("");
  console.log(`selftest: ${cases.length - failed}/${cases.length} passed`);
  return failed === 0 ? 0 : 1;
}

// ---------------------------------------------------------------------------
// CLI
// ---------------------------------------------------------------------------

const HELP = `用法:
  node scripts/codemod_ib_to_dh_api.mjs <path...> [options]
  node scripts/codemod_ib_to_dh_api.mjs --selftest

path 为相对仓库根的文件或目录，可给多个。目录会递归，只处理 .css。

options:
  --dry-run          只报告不写盘
  --radius           打开圆角归一（默认关闭）
  --with-fallback    改写带 fallback 的引用（默认跳过，只报告）
  --allow-shadowed   改写被本文件局部 --ib-* 声明遮蔽的 token（默认跳过，只报告）
  --json             输出机器可读 JSON 报告
  --selftest         运行内联单元自测并退出
  -h, --help         显示本帮助

映射（严格 1:1）:
${[...COLOR_MAP].map(([from, to]) => `  var(${from}) -> var(${to})`).join("\n")}

圆角归一（--radius）:
  var(--ib-radius) / var(--ib-radius, 2px) / var(--ib-radius, 6px)
  var(--moss-radius-sm) / var(--dh-api-radius, 6px)            -> var(--dh-api-radius)

注意: --dh-api-* 只在 .theme-dh-api 作用域内定义，--ib-* 定义在 :root。
只对已挂 theme-dh-api 的深色路由页面跑本脚本。`;

function parseArgs(argv) {
  const options = {
    paths: [],
    dryRun: false,
    radius: false,
    withFallback: false,
    allowShadowed: false,
    json: false,
    selftest: false,
    help: false,
  };
  for (const arg of argv) {
    switch (arg) {
      case "--dry-run":
        options.dryRun = true;
        break;
      case "--radius":
        options.radius = true;
        break;
      case "--with-fallback":
        options.withFallback = true;
        break;
      case "--allow-shadowed":
        options.allowShadowed = true;
        break;
      case "--json":
        options.json = true;
        break;
      case "--selftest":
        options.selftest = true;
        break;
      case "-h":
      case "--help":
        options.help = true;
        break;
      default:
        if (arg.startsWith("-")) throw new Error(`未知参数: ${arg}`);
        options.paths.push(arg);
    }
  }
  return options;
}

function main() {
  let options;
  try {
    options = parseArgs(process.argv.slice(2));
  } catch (error) {
    console.error(error.message);
    console.error(HELP);
    process.exit(2);
  }

  if (options.help) {
    console.log(HELP);
    return;
  }

  if (options.selftest) {
    process.exit(runSelftest());
  }

  if (options.paths.length === 0) {
    console.error("缺少路径参数。");
    console.error(HELP);
    process.exit(2);
  }

  for (const entry of options.paths) {
    const resolved = path.resolve(repoRoot, entry);
    if (!resolved.startsWith(repoRoot)) {
      console.error(`路径越出仓库根: ${entry}`);
      process.exit(2);
    }
    try {
      statSync(resolved);
    } catch {
      console.error(`路径不存在: ${entry}`);
      process.exit(2);
    }
  }

  const report = runCodemod(options.paths, options);
  if (options.json) console.log(JSON.stringify(report, null, 2));
  else printReport(report);

  process.exit(report.failures.length > 0 ? 1 : 0);
}

const invokedDirectly = process.argv[1] && path.resolve(process.argv[1]) === path.resolve(import.meta.filename);
if (invokedDirectly) main();
