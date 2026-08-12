#!/usr/bin/env node
/* 只读：对比两份快照（几何 ±tol px、computed style 与伪元素字符串全等、横带指标）。
 * usage: node geodiff.js <baseline.json> <current.json> [tolerancePx=1]
 */
'use strict';
const fs = require('fs');

function load(p) {
  const raw = JSON.parse(fs.readFileSync(p, 'utf8'));
  if (raw.result && raw.result.value) return JSON.parse(raw.result.value);
  if (raw.meta && raw.items) return raw;
  throw new Error('unrecognized snapshot format: ' + p);
}

const A = load(process.argv[2]);
const B = load(process.argv[3]);
const tol = parseFloat(process.argv[4] || '1');

let fail = 0;
const report = [];

if (A.meta.measured !== B.meta.measured || A.meta.elCount !== B.meta.elCount || A.meta.textLen !== B.meta.textLen) {
  report.push(`META MISMATCH (data state may have changed): measured ${A.meta.measured}->${B.meta.measured}, elCount ${A.meta.elCount}->${B.meta.elCount}, textLen ${A.meta.textLen}->${B.meta.textLen}`);
  fail++;
}
if (Math.abs(A.meta.docH - B.meta.docH) > tol) { report.push(`docH: ${A.meta.docH} -> ${B.meta.docH}`); fail++; }

const n = Math.min(A.items.length, B.items.length);
for (let i = 0; i < n; i++) {
  const a = A.items[i], b = B.items[i];
  if (a.k !== b.k || a.t !== b.t) { report.push(`ITEM ${i} identity: ${a.k}/${a.t} -> ${b.k}/${b.t}`); fail++; continue; }
  for (const f of ['x', 'y', 'w', 'h']) {
    if (Math.abs(a[f] - b[f]) > tol) { report.push(`ITEM ${i} ${a.t || a.k} ${f}: ${a[f]} -> ${b[f]} (d=${(b[f] - a[f]).toFixed(2)})`); fail++; }
  }
  for (const f of ['s', 'pb', 'pa']) {
    if ((a[f] || '') !== (b[f] || '')) { report.push(`ITEM ${i} ${a.t || a.k} style[${f}]: "${a[f] || ''}" -> "${b[f] || ''}"`); fail++; }
  }
}

const bandKey = b => `${b.src}#${b.bi}`;
const mapB = new Map(B.bands.map(b => [bandKey(b), b]));
const numRe = /-?\d+(\.\d+)?/g;
function numsClose(s1, s2) {
  if (s1 === s2) return true;
  const n1 = (s1.match(numRe) || []).map(Number);
  const n2 = (s2.match(numRe) || []).map(Number);
  if (n1.length !== n2.length) return false;
  if (s1.replace(numRe, '#') !== s2.replace(numRe, '#')) return false;
  return n1.every((v, i) => Math.abs(v - n2[i]) <= tol);
}
for (const a of A.bands) {
  const b = mapB.get(bandKey(a));
  if (!b) { report.push(`BAND missing: ${bandKey(a)} ${a.k}`); fail++; continue; }
  if (a.k !== b.k) { report.push(`BAND ${bandKey(a)} identity: ${a.k} -> ${b.k}`); fail++; continue; }
  for (const f of ['display', 'gtc', 'gap', 'padding', 'minHeight']) {
    if (!numsClose(a[f], b[f])) { report.push(`BAND ${a.k} ${f}: "${a[f]}" -> "${b[f]}"`); fail++; }
  }
}
if (A.bands.length !== B.bands.length) { report.push(`BAND count: ${A.bands.length} -> ${B.bands.length}`); fail++; }
if (A.items.length !== B.items.length) { report.push(`ITEM count: ${A.items.length} -> ${B.items.length}`); fail++; }

console.log(`compared items=${n} bands=${A.bands.length} tol=${tol}px`);
if (fail === 0) console.log('GEODIFF PASS');
else {
  console.log(`GEODIFF FAIL: ${fail} differences`);
  report.slice(0, 80).forEach(r => console.log('  ' + r));
  process.exitCode = 2;
}
