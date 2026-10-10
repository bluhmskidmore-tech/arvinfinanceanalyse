#!/usr/bin/env node
/* 只读：全局（非 module）CSS 合并前置预检。
 * 1) 跨文件类名定义分布：目标文件里出现的类名是否也在其他 CSS 文件中定义（信息披露 +
 *    识别真正的风险面——文件内合并不会改变跨文件相对顺序，前提是各文件内容在级联中连续）。
 * 2) @import 审计：目标文件与全库 CSS 中的 @import 会破坏"文件连续"假设，必须为零或人工确认。
 * 3) 目标文件被哪些 TS/TSX 以副作用方式导入（import "./x.css"）——多入口导入提示 prod 分包可能复制
 *    该文件内容；复制不破坏合并正确性（每份拷贝内部各自收敛），但要披露。
 * usage: node precheck-global.js <targetCssRepoRelPath>
 */
'use strict';
const fs = require('fs');
const path = require('path');
const { REPO_ROOT, parse, normSel, splitSelList } = require('./lib.js');

const target = process.argv[2];
const targetAbs = path.isAbsolute(target) ? target : path.join(REPO_ROOT, target);
const FRONT_SRC = path.join(REPO_ROOT, 'frontend', 'src');

const cssFiles = [];
(function walk(dir) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    if (e.name === 'node_modules' || e.name === 'dist') continue;
    const p = path.join(dir, e.name);
    if (e.isDirectory()) walk(p);
    else if (/\.css$/.test(e.name)) cssFiles.push(p);
  }
})(FRONT_SRC);

function classesOf(file) {
  const src = fs.readFileSync(file, 'utf8');
  const { rules } = parse(src);
  const set = new Set();
  let importCount = 0;
  for (const m of src.matchAll(/@import\b/g)) importCount++;
  for (const r of rules) {
    for (const sel of splitSelList(normSel(r.selRaw))) {
      for (const c of (sel.match(/\.[A-Za-z0-9_-]+/g) || [])) set.add(c.slice(1));
    }
  }
  return { classes: set, importCount };
}

const targetInfo = classesOf(targetAbs);
console.log(`target: ${path.relative(REPO_ROOT, targetAbs)}`);
console.log(`target classes: ${targetInfo.classes.size}, @import in target: ${targetInfo.importCount}`);

let totalImports = 0;
const collisions = new Map(); // class -> [files]
for (const f of cssFiles) {
  if (path.resolve(f) === path.resolve(targetAbs)) continue;
  const info = classesOf(f);
  totalImports += info.importCount;
  for (const c of targetInfo.classes) {
    if (info.classes.has(c)) {
      if (!collisions.has(c)) collisions.set(c, []);
      collisions.get(c).push(path.relative(FRONT_SRC, f));
    }
  }
}
console.log(`@import across frontend/src css (excl target): ${totalImports}`);
console.log(`classes also defined in other css files: ${collisions.size} / ${targetInfo.classes.size}`);
const byFile = new Map();
for (const [c, fl] of collisions) for (const f of fl) {
  if (!byFile.has(f)) byFile.set(f, []);
  byFile.get(f).push(c);
}
for (const [f, cs] of [...byFile.entries()].sort((a, b) => b[1].length - a[1].length).slice(0, 15)) {
  console.log(`  ${String(cs.length).padStart(4)}  ${f}  e.g. ${cs.slice(0, 6).join(', ')}`);
}

// side-effect importers of the target css
const rel = path.basename(targetAbs);
const importers = [];
(function walkTsx(dir) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    if (e.name === 'node_modules' || e.name === 'dist') continue;
    const p = path.join(dir, e.name);
    if (e.isDirectory()) walkTsx(p);
    else if (/\.(tsx?|jsx?)$/.test(e.name)) {
      const src = fs.readFileSync(p, 'utf8');
      if (new RegExp('import\\s+"[^"]*' + rel.replace(/\./g, '\\.') + '"').test(src) ||
          new RegExp("import\\s+'[^']*" + rel.replace(/\./g, '\\.') + "'").test(src)) {
        importers.push(path.relative(FRONT_SRC, p));
      }
    }
  }
})(FRONT_SRC);
console.log(`side-effect importers: ${importers.length}`);
importers.forEach(i => console.log('  ' + i));
