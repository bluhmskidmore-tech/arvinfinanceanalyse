#!/usr/bin/env node
/* 只读：从页面 TSX 提取 className 共现证据集，写入 workDir/tsx-evidence.json。
 * usage: node tsx-evidence.js <config.json>
 */
'use strict';
const fs = require('fs');
const path = require('path');
const { loadConfig } = require('./lib.js');

const cfg = loadConfig(process.argv[2]);
const sets = new Set();

function addSet(names) {
  const uniq = [...new Set(names)].sort();
  if (uniq.length >= 2) sets.add(JSON.stringify(uniq));
}

for (const f of cfg.tsxFiles) {
  const src = fs.readFileSync(f, 'utf8');
  // (1) className={...} 属性区间（括号配对，含字符串/模板字面量）
  const re = /className=\{/g;
  let m;
  while ((m = re.exec(src))) {
    let depth = 1, i = m.index + m[0].length;
    const start = i;
    while (i < src.length && depth > 0) {
      const ch = src[i];
      if (ch === '{') depth++;
      else if (ch === '}') depth--;
      else if (ch === '"' || ch === "'" || ch === '`') {
        const q = ch;
        i++;
        while (i < src.length) {
          if (src[i] === '\\') { i += 2; continue; }
          if (src[i] === q) break;
          if (q === '`' && src[i] === '$' && src[i + 1] === '{') {
            i += 2; let d2 = 1;
            while (i < src.length && d2 > 0) {
              if (src[i] === '{') d2++;
              else if (src[i] === '}') d2--;
              i++;
            }
            continue;
          }
          i++;
        }
      }
      i++;
    }
    addSet([...src.slice(start, i - 1).matchAll(/styles\.([A-Za-z0-9_]+)/g)].map(x => x[1]));
  }
  // (2) 行级证据（捕获组合类字符串的辅助常量）
  for (const line of src.split('\n')) addSet([...line.matchAll(/styles\.([A-Za-z0-9_]+)/g)].map(x => x[1]));
  // (3) 模板字面量
  for (const t of src.matchAll(/`[^`]*`/gs)) addSet([...t[0].matchAll(/styles\.([A-Za-z0-9_]+)/g)].map(x => x[1]));
  // (4) 小型辅助函数体（组合类的 helper）
  const fnRe = /function\s+[A-Za-z0-9_]+\s*\([^)]*\)[^{]*\{/g;
  let fm;
  while ((fm = fnRe.exec(src))) {
    let depth = 1, i = fnRe.lastIndex;
    const start = i;
    while (i < src.length && depth > 0) {
      if (src[i] === '{') depth++;
      else if (src[i] === '}') depth--;
      i++;
    }
    const body = src.slice(start, i);
    if (body.split('\n').length <= 20) addSet([...body.matchAll(/styles\.([A-Za-z0-9_]+)/g)].map(x => x[1]));
  }
  // (5) 动态方括号变体：styles[`name${...}`] -> 基类与 config.wildcards 中同前缀变体配对
  for (const bm of src.matchAll(/styles\[`([A-Za-z0-9_]+)\$\{/g)) {
    const base = bm[1];
    for (const v of cfg.wildcards.filter(w => w.startsWith(base))) addSet([base, v]);
  }
}

const out = [...sets].map(s => JSON.parse(s));
const outPath = path.join(cfg.workDir, 'tsx-evidence.json');
fs.writeFileSync(outPath, JSON.stringify(out, null, 1));
console.log(`evidence sets (>=2 names): ${out.length} -> ${outPath}`);
out.slice(0, 60).forEach(s => console.log('  ' + s.join(' + ')));
