#!/usr/bin/env node
/* 只读生成器：为全部重复组计算合并后的候选内容，写入 workDir（绝不写目标 CSS）。
 * 含四重不变量自检：重解析零警告 / 声明多重集守恒 / 未触组一致 / 权威段逐字节一致。
 * usage: node transform.js <config.json> [outName=merged-candidate.css] [reportName=transform-report.txt]
 */
'use strict';
const fs = require('fs');
const path = require('path');
const { loadConfig, buildAnalysis, parse, normSel } = require('./lib.js');

const cfg = loadConfig(process.argv[2]);
const outPath = path.join(cfg.workDir, process.argv[3] || 'merged-candidate.css');
const reportPath = path.join(cfg.workDir, process.argv[4] || 'transform-report.txt');

const A = buildAnalysis(cfg);
const src = A.src;
const lines = src.split('\n');
const lineStart = [0];
for (let i = 0; i < lines.length; i++) lineStart.push(lineStart[i] + lines[i].length + 1);
function startOfLine(ln) { return lineStart[ln - 1]; }
function endOfLine(ln) { return Math.min(lineStart[ln], src.length); }

const report = [];
const skipped = [];
const edits = [];

function collapse(v) { return v.replace(/\s+/g, ' ').trim(); }
function isCommentLine(ln) {
  const t = (lines[ln - 1] || '').trim();
  return t.startsWith('/*') && t.endsWith('*/');
}
function isBlankLine(ln) { return ((lines[ln - 1] || '').trim() === ''); }

const transformedKeys = new Set();

for (const [key, blocks] of A.groups) {
  if (blocks.length < 2) continue;
  const [ctx, selKey] = key.split('\u0000');
  if (selKey.includes(':global')) { skipped.push('SKIP global: ' + ctx + ' || ' + selKey); continue; }
  const plan = A.planGroup(key);
  if (!plan.merged) { skipped.push('SKIP noop: ' + ctx + ' || ' + selKey + ' :: ' + plan.notes.join(' ; ')); continue; }

  const conflictSet = new Set(plan.conflicts.map(c => c.prop + '@' + c.declLine));
  const target = blocks.find(b => b.selLine === plan.merged.targetLines[0]);
  if (!target) { skipped.push('SKIP no-target: ' + key); continue; }

  const moved = plan.merged.retained.filter(r => !r.isTarget && !conflictSet.has(r.prop + '@' + r.line));
  const keptConflicts = plan.merged.retained.filter(r => !r.isTarget && conflictSet.has(r.prop + '@' + r.line));
  const targetIndent = (ctx === 'ROOT') ? '  ' : '    ';

  if (moved.length) {
    const insLines = [];
    for (const m of moved) {
      const declLn = m.line;
      if (isCommentLine(declLn - 1)) {
        const block = blocks.find(b => b.selLine === m.fromBlockLine);
        if (block && declLn - 1 > block.braceLine) insLines.push(targetIndent + lines[declLn - 2].trim());
      }
      insLines.push(targetIndent + m.prop + ': ' + collapse(m.value) + ';');
    }
    const insertAt = target.braceOffset + 1;
    edits.push({ start: insertAt, end: insertAt, text: '\n' + insLines.join('\n') });
  }

  for (const db of plan.merged.deleteBlocks) {
    const block = blocks.find(b => b.selLine === db.lines[0]);
    if (!block) { skipped.push('SKIP missing-block: ' + key + ' @' + db.lines[0]); continue; }
    const keeps = keptConflicts.filter(k => k.fromBlockLine === block.selLine);
    if (keeps.length === 0) {
      let delStart = startOfLine(block.selLine);
      let delEnd = endOfLine(block.endLine);
      const nextLn = block.endLine + 1;
      const prevLn = block.selLine - 1;
      if (isBlankLine(nextLn) && (prevLn < 1 || isBlankLine(prevLn))) delEnd = endOfLine(nextLn);
      if (prevLn >= 1 && isCommentLine(prevLn)) report.push('ORPHAN-COMMENT? line ' + prevLn + ': ' + lines[prevLn - 1].trim().slice(0, 90));
      edits.push({ start: delStart, end: delEnd, text: '' });
      report.push('DELETE ' + ctx + ' || ' + selKey + ' block @' + block.selLine + '-' + block.endLine);
    } else {
      const selPart = src.slice(startOfLine(block.selLine), block.braceOffset + 1);
      const indent = (ctx === 'ROOT') ? '  ' : '    ';
      const bodyLines = keeps.map(k => indent + k.prop + ': ' + collapse(k.value) + ';');
      const closeIndent = (ctx === 'ROOT') ? '' : '  ';
      const note = indent + '/* 交错冲突：以下属性保持原位（多为刻意保留的死声明或需被后续规则覆盖），详见合并报告 */';
      const newBlock = selPart + '\n' + note + '\n' + bodyLines.join('\n') + '\n' + closeIndent + '}';
      edits.push({ start: startOfLine(block.selLine), end: block.endOffset + 1, text: newBlock });
      report.push('RESIDUAL ' + ctx + ' || ' + selKey + ' block @' + block.selLine + ' keeps: ' + keeps.map(k => k.prop).join(','));
    }
  }
  report.push('MERGE ' + ctx + ' || ' + selKey + ' -> target @' + plan.merged.targetLines[0] + ' moved:' + moved.length + ' dropped:' + plan.merged.dropped.length + (keptConflicts.length ? ' keptConflicts:' + keptConflicts.length : ''));
  transformedKeys.add(key);
}

edits.sort((a, b) => b.start - a.start);
for (let i = 1; i < edits.length; i++) {
  if (edits[i].end > edits[i - 1].start) { console.error('OVERLAPPING EDITS'); process.exit(1); }
}
let out = src;
for (const e of edits) out = out.slice(0, e.start) + e.text + out.slice(e.end);

/* ---------------- 不变量自检 ---------------- */
const errors = [];
const reparsed = parse(out);
if (reparsed.warnings.length) errors.push('REPARSE WARNINGS: ' + reparsed.warnings.join(' | '));

if (cfg.finalMarker) {
  const oldIdx = src.lastIndexOf(cfg.finalMarker);
  if (oldIdx !== -1) {
    const oldFinal = src.slice(oldIdx);
    const newFinal = out.slice(out.lastIndexOf(cfg.finalMarker));
    if (oldFinal !== newFinal) errors.push('FINAL SECTION CHANGED');
  }
}

function declMultiset(rules) {
  const map = new Map();
  for (const r of rules) {
    if (r.at.some(a => a.startsWith('@keyframes'))) continue;
    const key = (r.at.length ? r.at.map(a => a.replace(/\s+/g, ' ')).join(' | ') : 'ROOT') + '\u0000' + normSel(r.selRaw);
    if (!map.has(key)) map.set(key, []);
    for (const d of r.decls) map.get(key).push(d.prop + ':' + collapse(d.value) + (d.important ? '!i' : ''));
  }
  for (const v of map.values()) v.sort();
  return map;
}
const oldDecls = declMultiset(A.rules);
const newDecls = declMultiset(reparsed.rules);
for (const key of transformedKeys) {
  const plan = A.planGroup(key);
  const droppedList = plan.merged.dropped.map(d => d.prop + ':' + collapse(d.value)).sort();
  const oldList = (oldDecls.get(key) || []).slice().sort();
  const newList = (newDecls.get(key) || []).slice().sort();
  const oldCopy = [...oldList];
  for (const d of droppedList) {
    const i = oldCopy.indexOf(d);
    if (i === -1) { errors.push('DROP NOT FOUND in old: ' + key.replace('\u0000', '||') + ' :: ' + d); continue; }
    oldCopy.splice(i, 1);
  }
  if (JSON.stringify(oldCopy) !== JSON.stringify(newList)) {
    errors.push('DECL MISMATCH ' + key.replace('\u0000', ' || '));
  }
}
for (const [key, list] of oldDecls) {
  if (transformedKeys.has(key)) continue;
  const nl = newDecls.get(key) || [];
  if (JSON.stringify(list) !== JSON.stringify(nl)) errors.push('UNTOUCHED GROUP CHANGED: ' + key.replace('\u0000', ' || '));
}

fs.writeFileSync(outPath, out);
fs.writeFileSync(reportPath, [
  '=== transform report ===',
  'css: ' + cfg.cssPath,
  'groups transformed: ' + transformedKeys.size,
  'edits applied: ' + edits.length,
  '',
  ...report,
  '',
  '=== skipped ===',
  ...skipped,
  '',
  '=== errors ===',
  ...(errors.length ? errors : ['(none)']),
].join('\n'));

console.log('transformed groups:', transformedKeys.size, ' edits:', edits.length);
console.log('skipped:', skipped.length);
console.log('errors:', errors.length);
if (errors.length) { errors.slice(0, 10).forEach(e => console.log('ERR: ' + e)); process.exit(2); }
console.log('lines:', lines.length, '->', out.split('\n').length);
console.log('candidate: ' + outPath);
console.log('report:    ' + reportPath);
