#!/usr/bin/env node
/* 只读分析 CLI。
 * usage:
 *   node analyze.js <config.json> stats
 *   node analyze.js <config.json> pseudo
 *   node analyze.js <config.json> plan <selKey> [ctxFilter]
 *   node analyze.js <config.json> planall [outJson]
 *   node analyze.js <config.json> emit <selKey> [ctxFilter]
 */
'use strict';
const fs = require('fs');
const { loadConfig, buildAnalysis, normSel } = require('./lib.js');

const cfg = loadConfig(process.argv[2]);
const mode = process.argv[3] || 'stats';
const arg1 = process.argv[4];
const arg2 = process.argv[5];

const A = buildAnalysis(cfg);
const { src, rules, warnings, groups, planGroup } = A;

if (mode === 'stats') {
  const dupGroups = [...groups.entries()].filter(([, v]) => v.length >= 2);
  const totalDupBlocks = dupGroups.reduce((s, [, v]) => s + v.length, 0);
  console.log(`css: ${cfg.cssPath}`);
  console.log(`total lines: ${src.split('\n').length}`);
  console.log(`total rule blocks (excl keyframes): ${[...groups.values()].reduce((s, v) => s + v.length, 0)}`);
  console.log(`parser warnings: ${warnings.length}`);
  warnings.slice(0, 20).forEach(w => console.log('  WARN: ' + w));
  console.log(`evidence loaded: flat=${A.evidenceCounts.flat} ev2=${A.evidenceCounts.ev2}`);
  console.log(`duplicated groups: ${dupGroups.length}, blocks in duplicated groups: ${totalDupBlocks}`);
  const top = dupGroups.map(([k, v]) => ({ k: k.replace('\u0000', '  ||  '), n: v.length })).sort((a, b) => b.n - a.n).slice(0, 30);
  for (const t of top) console.log(`  x${t.n}  ${t.k}`);
} else if (mode === 'pseudo') {
  const imp = [];
  for (const r of rules) for (const d of r.decls) if (d.important) imp.push(`line ${d.line}: ${normSel(r.selRaw).slice(0, 70)} { ${d.prop} }`);
  console.log(`!important declarations: ${imp.length}`);
  imp.forEach(x => console.log('  ' + x));
  const glob = rules.filter(r => r.selRaw.includes(':global'));
  console.log(`:global rules: ${glob.length}`);
  glob.forEach(r => console.log(`  line ${r.selLine}: ${normSel(r.selRaw).slice(0, 90)}`));
  console.log('contexts:');
  [...new Set(rules.map(r => r.ctx || 'ROOT'))].sort().forEach(c => console.log('  ' + c));
} else if (mode === 'plan') {
  const selKey = normSel(arg1);
  const matches = [...groups.keys()].filter(k => k.split('\u0000')[1] === selKey && (!arg2 || k.split('\u0000')[0].includes(arg2)));
  if (!matches.length) { console.log('no group found for: ' + selKey); process.exit(1); }
  for (const k of matches) console.log(JSON.stringify(planGroup(k), null, 2));
} else if (mode === 'planall') {
  const res = [];
  for (const [k, v] of groups.entries()) {
    if (v.length < 2) continue;
    res.push(planGroup(k));
  }
  res.sort((a, b) => b.blocks.length - a.blocks.length);
  if (arg1) fs.writeFileSync(arg1, JSON.stringify(res, null, 1));
  console.log(`duplicated groups: ${res.length}`);
  console.log(`groups with interleave conflicts: ${res.filter(r => r.conflicts.length).length}`);
} else if (mode === 'emit') {
  const selKey = normSel(arg1);
  const matches = [...groups.keys()].filter(k => k.split('\u0000')[1] === selKey && (!arg2 || k.split('\u0000')[0].includes(arg2)));
  for (const k of matches) {
    const plan = planGroup(k);
    if (!plan.merged) { console.log('/* nothing to merge for ' + k.replace('\u0000', ' || ') + ' */'); continue; }
    const conflictKeys = new Set(plan.conflicts.map(c => c.prop + '@' + c.declLine));
    console.log('/* ===== ' + plan.ctx + ' || ' + plan.selKey + ' -> target lines ' + plan.merged.targetLines.join('-') + ' ===== */');
    let lastBlock = -1;
    for (const r of plan.merged.retained) {
      if (conflictKeys.has(r.prop + '@' + r.line)) { console.log('  /* CONFLICT kept in place @' + r.line + ': ' + r.prop + ' */'); continue; }
      if (r.fromBlockLine !== lastBlock) {
        console.log('  /* -- from block @' + (r.isTarget ? 'target' : r.fromBlockLine) + ' -- */');
        lastBlock = r.fromBlockLine;
      }
      console.log('  ' + r.prop + ': ' + r.value + ';');
    }
  }
} else {
  console.error('unknown mode: ' + mode);
  process.exit(1);
}
