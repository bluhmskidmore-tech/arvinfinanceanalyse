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

const cssBase = path.basename(cfg.cssPath);
const literalMode = cfg.evidenceMode === 'literal';

if (literalMode) {
  // 非 module 全局 CSS：className 是字符串字面量。提取每个 className 属性中的静态类名集合
  // （引号字符串与模板字面量的静态段，按空白切分），另加行级与小函数体证据。
  for (const f of cfg.tsxFiles) {
    const src = fs.readFileSync(f, 'utf8');
    const grabNames = txt => {
      const names = [];
      for (const q of txt.matchAll(/"([^"]+)"|'([^']+)'/g)) {
        for (const n of (q[1] || q[2]).split(/\s+/)) if (/^[A-Za-z][\w-]*$/.test(n)) names.push(n);
      }
      for (const t of txt.matchAll(/`([^`]*)`/gs)) {
        for (const seg of t[1].split(/\$\{[^}]*\}/)) {
          for (const n of seg.split(/\s+/)) if (/^[A-Za-z][\w-]*$/.test(n)) names.push(n);
        }
      }
      return names;
    };
    // className="..." 直接字面量
    for (const m of src.matchAll(/className\s*=\s*("[^"]+"|'[^']+')/g)) addSet(grabNames(m[1]));
    // className={...} 表达式区间
    const re = /className=\{/g;
    let m2;
    while ((m2 = re.exec(src))) {
      let depth = 1, i = re.lastIndex;
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
              while (i < src.length && d2 > 0) { if (src[i] === '{') d2++; else if (src[i] === '}') d2--; i++; }
              continue;
            }
            i++;
          }
        }
        i++;
      }
      addSet(grabNames(src.slice(start, i - 1)));
    }
    // 小函数体（返回类名字符串的 helper）
    const fnRe = /function\s+[A-Za-z0-9_]+\s*\([^)]*\)[^{]*\{/g;
    let fm2;
    while ((fm2 = fnRe.exec(src))) {
      let depth = 1, i = fnRe.lastIndex;
      const start = i;
      while (i < src.length && depth > 0) {
        if (src[i] === '{') depth++;
        else if (src[i] === '}') depth--;
        i++;
      }
      const body = src.slice(start, i);
      if (body.split('\n').length <= 20 && /className|class/i.test(body)) addSet(grabNames(body));
    }
  }
  const out = [...sets].map(s => JSON.parse(s));
  const outPath = path.join(cfg.workDir, 'tsx-evidence.json');
  fs.writeFileSync(outPath, JSON.stringify(out, null, 1));
  console.log(`evidence sets (literal mode, >=2 names): ${out.length} -> ${outPath}`);
  out.slice(0, 60).forEach(s => console.log('  ' + s.join(' + ')));
  process.exit(0);
}

for (const f of cfg.tsxFiles) {
  const src = fs.readFileSync(f, 'utf8');
  // 识别该文件导入目标 CSS module 的标识符（如 styles / marketStyles）；未导入则跳过该文件
  const importRe = new RegExp('import\\s+([A-Za-z0-9_$]+)\\s+from\\s+"[^"]*' + cssBase.replace(/\./g, '\\.') + '"');
  const im = src.match(importRe);
  if (!im) { console.log('  (no import of ' + cssBase + ' in ' + path.basename(f) + ', skipped)'); continue; }
  const ident = im[1];
  const tokRe = new RegExp(ident.replace(/\$/g, '\\$') + '\\.([A-Za-z0-9_]+)', 'g');
  const brkRe = new RegExp(ident.replace(/\$/g, '\\$') + '\\[`([A-Za-z0-9_]+)\\$\\{', 'g');
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
    addSet([...src.slice(start, i - 1).matchAll(tokRe)].map(x => x[1]));
  }
  // (2) 行级证据（捕获组合类字符串的辅助常量）
  for (const line of src.split('\n')) addSet([...line.matchAll(tokRe)].map(x => x[1]));
  // (3) 模板字面量
  for (const t of src.matchAll(/`[^`]*`/gs)) addSet([...t[0].matchAll(tokRe)].map(x => x[1]));
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
    if (body.split('\n').length <= 20) addSet([...body.matchAll(tokRe)].map(x => x[1]));
  }
  // (5) 动态方括号变体：<ident>[`name${...}`] -> 前缀与 config.wildcards 中同前缀变体配对
  for (const bm of src.matchAll(brkRe)) {
    const base = bm[1];
    for (const v of cfg.wildcards.filter(w => w.startsWith(base))) addSet([base, v].filter((x, i2, a) => a.indexOf(x) === i2));
  }
}

const out = [...sets].map(s => JSON.parse(s));
const outPath = path.join(cfg.workDir, 'tsx-evidence.json');
fs.writeFileSync(outPath, JSON.stringify(out, null, 1));
console.log(`evidence sets (>=2 names): ${out.length} -> ${outPath}`);
out.slice(0, 60).forEach(s => console.log('  ' + s.join(' + ')));
