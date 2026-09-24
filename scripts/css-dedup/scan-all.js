#!/usr/bin/env node
/* READ-ONLY: scan all CSS files under a root for duplicate (ctx, selector-list) groups. */
'use strict';
const fs = require('fs');
const path = require('path');

const ROOT = process.argv[2];
const files = [];
(function walk(dir) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    if (e.name === 'node_modules' || e.name === 'dist') continue;
    const p = path.join(dir, e.name);
    if (e.isDirectory()) walk(p);
    else if (/\.css$/.test(e.name)) files.push(p);
  }
})(ROOT);

function scan(file) {
  const src = fs.readFileSync(file, 'utf8');
  const rules = [];
  const atStack = [];
  const nodeStack = [];
  let i = 0, buf = '', cur = null;
  const n = src.length;
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
      else { cur = { sel: p.replace(/\s+/g, ' '), at: atStack.join('|') || 'ROOT', imp: 0 }; nodeStack.push('rule'); }
      i++; continue;
    }
    if (ch === '}') {
      const t = nodeStack.pop();
      if (t === 'rule') { if (/!important/i.test(buf)) cur.imp++; buf = ''; rules.push(cur); cur = null; }
      else if (t === 'at') { atStack.pop(); buf = ''; }
      else buf = '';
      i++; continue;
    }
    if (ch === ';') { if (cur && /!important/i.test(buf)) cur.imp++; buf = ''; i++; continue; }
    if (buf !== '' || /\S/.test(ch)) buf += ch;
    i++;
  }
  const groups = new Map();
  for (const r of rules) {
    if (r.at.includes('@keyframes')) continue;
    const k = r.at + '\u0000' + r.sel;
    groups.set(k, (groups.get(k) || 0) + 1);
  }
  const dups = [...groups.values()].filter(v => v >= 2);
  return {
    file: path.relative(ROOT, file),
    lines: src.split('\n').length,
    rules: rules.length,
    dupGroups: dups.length,
    dupBlocks: dups.reduce((s, v) => s + v, 0),
  };
}

const results = files.map(scan).filter(r => r.dupGroups > 0).sort((a, b) => b.dupBlocks - a.dupBlocks);
console.log('files scanned:', files.length, ' files with duplicates:', results.length);
console.log('dupGroups dupBlocks lines  file');
for (const r of results.slice(0, 25)) {
  console.log(String(r.dupGroups).padStart(8), String(r.dupBlocks).padStart(9), String(r.lines).padStart(6), ' ' + r.file);
}
