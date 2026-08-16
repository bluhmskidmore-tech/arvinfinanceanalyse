#!/usr/bin/env node
/* 级联等价终裁器（只读）：对每个元素原型（DOM 证据 ∪ TSX 扩展 ∪ 通配类扩展），
 * 在 8 个断点区间 × 动效开关 × 伪元素维度上逐属性计算胜者声明，比较两份 CSS 必须逐项一致。
 * usage: node equivalence.js <config.json> <originalCss> <candidateCss> [reportName]
 */
'use strict';
const fs = require('fs');
const path = require('path');
const { loadConfig, splitSelList } = require('./lib.js');

const cfg = loadConfig(process.argv[2]);

function parse(src) {
  const rules = [];
  const atStack = [];
  const nodeStack = [];
  let i = 0, buf = '', cur = null;
  const n = src.length;
  function flushDecl() {
    const text = buf.trim();
    buf = '';
    if (!text) return;
    const ci = text.indexOf(':');
    if (ci === -1) return;
    const prop = text.slice(0, ci).trim();
    let value = text.slice(ci + 1).trim();
    let important = false;
    const im = /!\s*important\s*$/i;
    if (im.test(value)) { important = true; value = value.replace(im, '').trim(); }
    cur.decls.push({ prop, value, important });
  }
  while (i < n) {
    const ch = src[i];
    if (ch === '/' && src[i + 1] === '*') {
      let j = src.indexOf('*/', i + 2); if (j === -1) j = n - 2;
      i = j + 2; continue;
    }
    if (ch === '"' || ch === "'") {
      buf += ch; i++;
      while (i < n) { const c2 = src[i]; buf += c2; if (c2 === '\\') { buf += src[i + 1] || ''; i += 2; continue; } i++; if (c2 === ch) break; }
      continue;
    }
    if (ch === '{') {
      const prelude = buf.trim(); buf = '';
      if (cur) nodeStack.push({ type: 'nested' });
      else if (prelude.startsWith('@')) { nodeStack.push({ type: 'at' }); atStack.push(prelude.replace(/\s+/g, ' ').trim()); }
      else { cur = { selRaw: prelude, at: atStack.slice(), decls: [], order: rules.length }; nodeStack.push({ type: 'rule' }); }
      i++; continue;
    }
    if (ch === '}') {
      const top = nodeStack.pop();
      if (top && top.type === 'rule') { flushDecl(); rules.push(cur); cur = null; }
      else if (top && top.type === 'at') { atStack.pop(); buf = ''; }
      else buf = '';
      i++; continue;
    }
    if (ch === ';') { if (cur) flushDecl(); else buf = ''; i++; continue; }
    if (buf !== '' || /\S/.test(ch)) buf += ch;
    i++;
  }
  return rules;
}

function specificity(sel) {
  let s = ' ' + sel + ' ';
  for (let g = 0; g < 20; g++) { const m = s.match(/:global\(([^()]*)\)/); if (!m) break; s = s.replace(m[0], ' ' + m[1] + ' '); }
  s = s.replace(/:global\b/g, ' ');
  for (let g = 0; g < 20; g++) { const m = s.match(/:where\(([^()]*)\)/); if (!m) break; s = s.replace(m[0], ' '); }
  for (let g = 0; g < 20; g++) { const m = s.match(/:(not|is|has)\(([^()]*)\)/); if (!m) break; s = s.replace(m[0], ' ' + splitSelList(m[2])[0] + ' '); }
  let a = 0, b = 0, c = 0;
  const pe = s.match(/::[\w-]+/g); if (pe) c += pe.length;
  s = s.replace(/::[\w-]+/g, ' ');
  const ids = s.match(/#[\w-]+/g); if (ids) a += ids.length;
  s = s.replace(/#[\w-]+/g, ' ');
  const attrs = s.match(/\[[^\]]*\]/g); if (attrs) b += attrs.length;
  s = s.replace(/\[[^\]]*\]/g, ' ');
  const classes = s.match(/\.[\w-]+/g); if (classes) b += classes.length;
  s = s.replace(/\.[\w-]+/g, ' ');
  const pseudos = s.match(/:[\w-]+/g); if (pseudos) b += pseudos.length;
  s = s.replace(/:[\w-]+/g, ' ');
  const els = s.match(/(^|[\s>+~])[a-zA-Z][\w-]*/g); if (els) c += els.length;
  return a * 1e6 + b * 1e3 + c;
}
function compoundParts(compound) {
  let t = compound;
  for (let g = 0; g < 20; g++) {
    const m = t.match(/:(has|not|nth-child|nth-of-type|nth-last-child|nth-last-of-type|is|where)\(([^()]*)\)/);
    if (!m) break;
    t = t.replace(m[0], '');
  }
  const globals = [];
  for (let g = 0; g < 20; g++) {
    const m = t.match(/:global\(([^()]*)\)/);
    if (!m) break;
    for (const cc of (m[1].match(/\.[A-Za-z0-9_-]+/g) || [])) globals.push(cc.slice(1));
    const tm = m[1].match(/(^|[\s(])([a-zA-Z][\w-]*)/);
    t = t.replace(m[0], tm ? tm[2] : '');
  }
  t = t.replace(/\[[^\]]*\]/g, '');
  const classes = (t.match(/\.[A-Za-z0-9_-]+/g) || []).map(x => x.slice(1));
  const tagM = t.match(/^([a-zA-Z*][\w-]*)/);
  return { classes: [...classes, ...globals], tag: tagM && tagM[1] !== '*' ? tagM[1].toLowerCase() : null };
}
function parseSelector(sel) {
  const compounds = [];
  let depth = 0, cur = '';
  for (const ch of sel.trim()) {
    if (ch === '(' || ch === '[') depth++;
    else if (ch === ')' || ch === ']') depth--;
    if (depth === 0 && /[\s>+~]/.test(ch)) { if (cur) { compounds.push(cur); cur = ''; } }
    else cur += ch;
  }
  if (cur) compounds.push(cur);
  let subject = compounds[compounds.length - 1] || '';
  let pseudoEl = null;
  const pm = subject.match(/::([\w-]+)$/);
  if (pm) { pseudoEl = pm[1]; subject = subject.slice(0, subject.length - pm[0].length); }
  const subj = compoundParts(subject);
  const ancestors = compounds.slice(0, -1).map(compoundParts);
  return { subj, ancestors, pseudoEl, spec: specificity(sel) };
}
function mediaInfo(at) {
  let lo = 0, hi = Infinity, reduced = false, other = false;
  for (const q of at) {
    if (q.startsWith('@keyframes')) return null;
    if (!q.startsWith('@media')) { other = true; continue; }
    if (/prefers-reduced-motion:\s*reduce/.test(q)) reduced = true;
    for (const m of q.matchAll(/min-width:\s*([\d.]+)px/g)) lo = Math.max(lo, parseFloat(m[1]));
    for (const m of q.matchAll(/max-width:\s*([\d.]+)px/g)) hi = Math.min(hi, parseFloat(m[1]));
  }
  return { lo, hi, reduced, other };
}

function loadArchetypes() {
  const seen = new Set();
  const archs = [];
  const tsxSets = [];
  const tryLoad = (p, fn) => { try { fn(JSON.parse(fs.readFileSync(p, 'utf8'))); } catch (e) {} };
  tryLoad(path.join(cfg.workDir, 'tsx-evidence.json'), arr => { for (const a of arr) tsxSets.push(a); });
  const add = (tag, own, closure) => {
    const key = tag + '§' + [...own].sort().join('.') + '§' + [...closure].sort().join('.');
    if (seen.has(key)) return;
    seen.add(key);
    archs.push({ tag, own, closure });
  };
  for (const f of fs.readdirSync(cfg.workDir).filter(x => /^(base-\d+|mbase-\d+|evidence-[\w-]+|ev2-[\w-]+)\.json$/.test(x))) {
    tryLoad(path.join(cfg.workDir, f), raw => {
      const snap = raw.result && raw.result.value ? JSON.parse(raw.result.value) : raw;
      for (const k of snap.evidence2 || []) {
        const [tag, own, closure] = k.split('§');
        add(tag, new Set(own ? own.split('.') : []), new Set(closure ? closure.split('.') : []));
      }
    });
  }
  // TSX 集合的两种建模，都不允许经由高频基类桥接出嵌合体：
  // (a) 直接原型：own=T 本身（TSX 声明"这些类可同元素"，按原样建模，零桥接）；
  // (b) DOM 扩展：仅当共享锚点是低频"身份类"（≤ max(4, 0.5% base)）才把 T 叠加到真实 DOM 原型上，
  //     以覆盖"隐藏变体挂在真实元素（携带 dhCard 等基类）"的场景。
  const WILD = new Set(cfg.wildcards);
  const baseCount = archs.length;
  for (const T of tsxSets) {
    add(null, new Set(T), new Set(T));
  }
  const ownFreq = new Map();
  for (let i = 0; i < baseCount; i++) for (const c of archs[i].own) ownFreq.set(c, (ownFreq.get(c) || 0) + 1);
  const freqLimit = Math.max(4, Math.round(baseCount * 0.005));
  const isAnchor = c => !WILD.has(c) && (ownFreq.get(c) || 0) <= freqLimit;
  for (let i = 0; i < baseCount; i++) {
    const A = archs[i];
    for (const T of tsxSets) {
      if (!T.some(c => A.own.has(c) && isAnchor(c))) continue;
      add(A.tag, new Set([...A.own, ...T]), new Set([...A.closure, ...T]));
    }
  }
  const count2 = archs.length;
  for (let i = 0; i < count2; i++) {
    const A = archs[i];
    for (const t of cfg.wildcards) {
      if (A.own.has(t)) continue;
      add(A.tag, new Set([...A.own, t]), new Set([...A.closure, t]));
    }
  }
  return archs;
}

function compoundMatches(cp, arch, isSubject) {
  if (isSubject && cp.tag && arch.tag !== cp.tag) return false;
  const pool = isSubject ? arch.own : arch.closure;
  for (const c of cp.classes) if (!pool.has(c)) return false;
  return true;
}
function selectorMatches(ps, arch) {
  if (!compoundMatches(ps.subj, arch, true)) return false;
  for (const anc of ps.ancestors) if (!compoundMatches(anc, arch, false)) return false;
  return true;
}
function buildFile(css) {
  const rules = parse(css).map(r => ({ ...r, media: mediaInfo(r.at) })).filter(r => r.media !== null);
  for (const r of rules) r.parsedSels = splitSelList(r.selRaw).map(parseSelector);
  return rules;
}
const BANDS = [640, 720, 840, 900, 1000, 1200, 1300, 1920];

function winnersForArch(matches, width, reducedMotion) {
  const out = new Map();
  for (const m of matches) {
    const r = m.rule;
    if (width < r.media.lo || width > r.media.hi) continue;
    if (r.media.reduced && !reducedMotion) continue;
    for (const d of r.decls) {
      const key = (m.pseudoEl || '') + '|' + d.prop.toLowerCase();
      const cur = out.get(key);
      const cand = { value: d.value.replace(/\s+/g, ' ').trim(), important: d.important, spec: m.spec, order: r.order };
      if (!cur) { out.set(key, cand); continue; }
      if (cand.important !== cur.important) { if (cand.important) out.set(key, cand); continue; }
      if (cand.spec > cur.spec) { out.set(key, cand); continue; }
      if (cand.spec === cur.spec && cand.order >= cur.order) { out.set(key, cand); continue; }
    }
  }
  return out;
}

const origCss = fs.readFileSync(process.argv[3], 'utf8');
const candCss = fs.readFileSync(process.argv[4], 'utf8');
const reportPath = path.join(cfg.workDir, process.argv[5] || 'equivalence-report.txt');

const fileA = buildFile(origCss);
const fileB = buildFile(candCss);

const archs = loadArchetypes();
const preSynth = archs.length;
{
  // 免证据合成原型（2026-08-12 三处确认回归的终裁盲区修复）：
  // (a) 每个选择器一个"精确匹配原型"——匹配该选择器的元素必然存在层叠意义（同名选择器共匹配恒真）；
  // (b) 每个类名一个单类原型——单类元素不依赖任何 TSX/DOM 证据。
  const seen = new Set(archs.map(A => A.tag + '§' + [...A.own].sort().join('.') + '§' + [...A.closure].sort().join('.')));
  const add = (tag, own, closure) => {
    const key = tag + '§' + [...own].sort().join('.') + '§' + [...closure].sort().join('.');
    if (seen.has(key)) return;
    seen.add(key);
    archs.push({ tag, own, closure });
  };
  const classSet = new Set();
  for (const rules of [fileA, fileB]) {
    for (const r of rules) {
      for (const ps of r.parsedSels) {
        const own = new Set(ps.subj.classes);
        const closure = new Set(ps.subj.classes);
        for (const anc of ps.ancestors) for (const c of anc.classes) closure.add(c);
        for (const c of closure) classSet.add(c);
        add(ps.subj.tag, own, closure);
      }
    }
  }
  for (const c of classSet) add(null, new Set([c]), new Set([c]));
}
console.log('archetypes:', archs.length, '(synthetic +' + (archs.length - preSynth) + ')');
console.log('rules: original', fileA.length, ' candidate', fileB.length);

function buildMatchCache(rules) {
  const cache = [];
  for (let ai = 0; ai < archs.length; ai++) {
    const list = [];
    for (const r of rules) {
      const byPseudo = new Map();
      for (const ps of r.parsedSels) {
        if (!selectorMatches(ps, archs[ai])) continue;
        const k = ps.pseudoEl || '';
        const cur = byPseudo.get(k);
        if (cur == null || ps.spec > cur) byPseudo.set(k, ps.spec);
      }
      for (const [k, spec] of byPseudo) list.push({ rule: r, spec, pseudoEl: k || null });
    }
    cache.push(list);
  }
  return cache;
}
const cacheA = buildMatchCache(fileA);
const cacheB = buildMatchCache(fileB);

const diffs = [];
let checked = 0;
for (let ai = 0; ai < archs.length; ai++) {
  for (const w of BANDS) {
    for (const rm of [false, true]) {
      const wa = winnersForArch(cacheA[ai], w, rm);
      const wb = winnersForArch(cacheB[ai], w, rm);
      const keys = new Set([...wa.keys(), ...wb.keys()]);
      for (const k of keys) {
        checked++;
        const a = wa.get(k), b = wb.get(k);
        const av = a ? a.value + (a.important ? ' !important' : '') : '(none)';
        const bv = b ? b.value + (b.important ? ' !important' : '') : '(none)';
        if (av !== bv) {
          const A = archs[ai];
          diffs.push(`DIFF w=${w} rm=${rm} arch=<${A.tag} own=${[...A.own].sort().join('.')}> ${k}: "${av}" -> "${bv}"`);
        }
      }
    }
  }
}
const uniq = [...new Set(diffs)];
fs.writeFileSync(reportPath, uniq.join('\n') || '(no differences)');
console.log('checked winner slots:', checked);
console.log('DIFFS:', uniq.length);
uniq.slice(0, 30).forEach(d => console.log(d));
process.exit(uniq.length ? 3 : 0);
