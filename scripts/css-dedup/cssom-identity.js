#!/usr/bin/env node
/* 只读：验证两份 CSS 文本的 CSSOM 相关内容完全一致（规则顺序、at 上下文、选择器、
 * 声明顺序与 !important）。注释与空 at-rule 壳是非语义内容，解析时天然剥离。
 * 用于证明注释类修复零渲染影响。
 * usage: node cssom-identity.js <fileA> <fileB>    （fileA/fileB 可用 "git:<rev>:<repo相对路径>"）
 */
'use strict';
const fs = require('fs');
const { execSync } = require('child_process');
const { REPO_ROOT } = require('./lib.js');

function readInput(spec) {
  if (spec.startsWith('git:')) {
    const rest = spec.slice(4);
    const idx = rest.indexOf(':');
    const rev = rest.slice(0, idx), p = rest.slice(idx + 1);
    return execSync(`git show ${rev}:${p}`, { cwd: REPO_ROOT, maxBuffer: 1 << 26 }).toString('utf8');
  }
  return fs.readFileSync(spec, 'utf8');
}

function serialize(src) {
  const out = [];
  const atStack = [];
  const nodeStack = [];
  let i = 0, buf = '', cur = null;
  const n = src.length;
  const flush = () => {
    const t = buf.trim();
    buf = '';
    if (!t) return;
    cur.decls.push(t.replace(/\s+/g, ' '));
  };
  while (i < n) {
    const ch = src[i];
    if (ch === '/' && src[i + 1] === '*') {
      let j = src.indexOf('*/', i + 2); if (j === -1) j = n - 2;
      i = j + 2; continue;
    }
    if (ch === '"' || ch === "'") {
      buf += ch; i++;
      while (i < n) { const c = src[i]; buf += c; if (c === '\\') { buf += src[i + 1] || ''; i += 2; continue; } i++; if (c === ch) break; }
      continue;
    }
    if (ch === '{') {
      const p = buf.trim(); buf = '';
      if (cur) nodeStack.push('nested');
      else if (p.startsWith('@')) { nodeStack.push('at'); atStack.push(p.replace(/\s+/g, ' ')); }
      else { cur = { sel: p.replace(/\s+/g, ' '), at: atStack.join('|'), decls: [] }; nodeStack.push('rule'); }
      i++; continue;
    }
    if (ch === '}') {
      const t = nodeStack.pop();
      if (t === 'rule') { flush(); out.push(`${cur.at} :: ${cur.sel} { ${cur.decls.join('; ')} }`); cur = null; }
      else if (t === 'at') { atStack.pop(); buf = ''; }
      else buf = '';
      i++; continue;
    }
    if (ch === ';') { if (cur) flush(); else buf = ''; i++; continue; }
    if (buf !== '' || /\S/.test(ch)) buf += ch;
    i++;
  }
  return out;
}

const A = serialize(readInput(process.argv[2]));
const B = serialize(readInput(process.argv[3]));
if (A.length !== B.length) {
  console.log(`RULE COUNT DIFF: ${A.length} vs ${B.length}`);
  process.exit(2);
}
let diffs = 0;
for (let i = 0; i < A.length; i++) {
  if (A[i] !== B[i]) {
    diffs++;
    if (diffs <= 5) console.log(`RULE ${i}:\n  A: ${A[i].slice(0, 160)}\n  B: ${B[i].slice(0, 160)}`);
  }
}
console.log(diffs === 0 ? `CSSOM IDENTICAL (${A.length} rules)` : `CSSOM DIFFS: ${diffs}`);
process.exit(diffs === 0 ? 0 : 2);
