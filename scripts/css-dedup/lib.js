#!/usr/bin/env node
/* css-dedup 共享库：配置加载、CSS 解析、选择器工具、共现判定、合并计划。
 * 只读——绝不写目标 CSS 文件。 */
'use strict';
const fs = require('fs');
const path = require('path');
const os = require('os');

const REPO_ROOT = path.resolve(__dirname, '..', '..');

function loadConfig(configPath) {
  const abs = path.isAbsolute(configPath) ? configPath : path.resolve(process.cwd(), configPath);
  const cfg = JSON.parse(fs.readFileSync(abs, 'utf8'));
  const resolveRepo = p => (path.isAbsolute(p) ? p : path.join(REPO_ROOT, p));
  cfg.cssPath = resolveRepo(cfg.cssPath);
  cfg.tsxFiles = (cfg.tsxFiles || []).map(resolveRepo);
  cfg.wildcards = cfg.wildcards || [];
  cfg.workDir = cfg.workDir
    ? resolveRepo(cfg.workDir)
    : path.join(os.tmpdir(), 'css-dedup-' + path.basename(abs, '.json'));
  fs.mkdirSync(cfg.workDir, { recursive: true });
  cfg.configName = path.basename(abs, '.json');
  return cfg;
}

/* ---------------- parser ---------------- */
function parse(src) {
  const rules = [];
  const atStack = [];
  const nodeStack = [];
  let i = 0, line = 1;
  let buf = '', bufLine = 1, bufOffset = 0;
  let curRule = null;
  const warnings = [];
  const n = src.length;

  function flushDecl(endOffset) {
    const text = buf.trim();
    buf = '';
    if (!text) return;
    const ci = text.indexOf(':');
    if (ci === -1) {
      warnings.push(`decl-without-colon line ${bufLine}: ${text.slice(0, 80)}`);
      return;
    }
    const prop = text.slice(0, ci).trim();
    let value = text.slice(ci + 1).trim();
    let important = false;
    const im = /!\s*important\s*$/i;
    if (im.test(value)) { important = true; value = value.replace(im, '').trim(); }
    curRule.decls.push({ prop, value, important, line: bufLine, offset: bufOffset, endOffset });
  }

  while (i < n) {
    const ch = src[i];
    if (ch === '/' && src[i + 1] === '*') {
      let j = src.indexOf('*/', i + 2);
      if (j === -1) { warnings.push(`unterminated comment line ${line}`); j = n - 2; }
      for (let k = i; k < j + 2; k++) if (src[k] === '\n') line++;
      i = j + 2;
      continue;
    }
    if (ch === '"' || ch === "'") {
      if (buf === '') { bufOffset = i; bufLine = line; }
      buf += ch;
      i++;
      while (i < n) {
        const c2 = src[i];
        buf += c2;
        if (c2 === '\\') { buf += src[i + 1] || ''; if (src[i + 1] === '\n') line++; i += 2; continue; }
        if (c2 === '\n') line++;
        i++;
        if (c2 === ch) break;
      }
      continue;
    }
    if (ch === '{') {
      const prelude = buf.trim();
      const preludeLine = bufLine, preludeOffset = bufOffset;
      buf = '';
      if (curRule) {
        warnings.push(`NESTED RULE inside rule at line ${line}: ${prelude.slice(0, 60)}`);
        nodeStack.push({ type: 'nested' });
      } else if (prelude.startsWith('@')) {
        nodeStack.push({ type: 'at' });
        atStack.push(prelude.replace(/\s+/g, ' ').trim());
      } else {
        curRule = {
          selRaw: prelude, selLine: preludeLine, selOffset: preludeOffset,
          braceLine: line, braceOffset: i, at: atStack.slice(), decls: [],
          endLine: -1, endOffset: -1,
        };
        nodeStack.push({ type: 'rule' });
      }
      i++;
      continue;
    }
    if (ch === '}') {
      const top = nodeStack.pop();
      if (!top) warnings.push(`unbalanced '}' at line ${line}`);
      else if (top.type === 'rule') {
        flushDecl(i);
        curRule.endLine = line;
        curRule.endOffset = i;
        rules.push(curRule);
        curRule = null;
      } else if (top.type === 'at') {
        if (buf.trim()) warnings.push(`junk before at-close line ${line}: ${buf.trim().slice(0, 60)}`);
        atStack.pop();
        buf = '';
      } else buf = '';
      i++;
      continue;
    }
    if (ch === ';') {
      if (curRule) flushDecl(i);
      else {
        const t = buf.trim();
        if (t) warnings.push(`top-level statement line ${bufLine}: ${t.slice(0, 60)}`);
        buf = '';
      }
      i++;
      continue;
    }
    if (ch === '\n') line++;
    if (buf === '') {
      if (/\S/.test(ch)) { bufOffset = i; bufLine = line; buf += ch; }
    } else buf += ch;
    i++;
  }
  if (nodeStack.length) warnings.push(`unclosed blocks at EOF: depth=${nodeStack.length}`);
  if (buf.trim()) warnings.push(`trailing junk at EOF: ${buf.trim().slice(0, 60)}`);
  return { rules, warnings };
}

/* ---------------- selector helpers ---------------- */
function normSel(s) {
  return s
    .replace(/\s+/g, ' ')
    .replace(/\s*,\s*/g, ', ')
    .replace(/\s*>\s*/g, ' > ')
    .replace(/\s*\+\s*/g, ' + ')
    .replace(/\s*~\s*(?![=\]])/g, ' ~ ')
    .trim();
}
function ctxKey(at) {
  if (!at.length) return 'ROOT';
  return at.map(a => a.replace(/\s+/g, ' ').replace(/\s*:\s*/g, ': ').trim()).join(' | ');
}
function splitSelList(sel) {
  const parts = [];
  let depth = 0, cur = '';
  for (const ch of sel) {
    if (ch === '(' || ch === '[') depth++;
    else if (ch === ')' || ch === ']') depth--;
    if (ch === ',' && depth === 0) { parts.push(cur.trim()); cur = ''; }
    else cur += ch;
  }
  if (cur.trim()) parts.push(cur.trim());
  return parts;
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
  return [a, b, c];
}
function specEq(s1, s2) { return s1[0] === s2[0] && s1[1] === s2[1] && s1[2] === s2[2]; }

const SHORTHANDS = {
  'margin': ['margin-top', 'margin-right', 'margin-bottom', 'margin-left'],
  'padding': ['padding-top', 'padding-right', 'padding-bottom', 'padding-left'],
  'inset': ['top', 'right', 'bottom', 'left'],
  'gap': ['row-gap', 'column-gap'],
  'overflow': ['overflow-x', 'overflow-y'],
  'border-radius': ['border-top-left-radius', 'border-top-right-radius', 'border-bottom-right-radius', 'border-bottom-left-radius'],
  'border-width': ['border-top-width', 'border-right-width', 'border-bottom-width', 'border-left-width'],
  'border-style': ['border-top-style', 'border-right-style', 'border-bottom-style', 'border-left-style'],
  'border-color': ['border-top-color', 'border-right-color', 'border-bottom-color', 'border-left-color'],
  'border-top': ['border-top-width', 'border-top-style', 'border-top-color'],
  'border-right': ['border-right-width', 'border-right-style', 'border-right-color'],
  'border-bottom': ['border-bottom-width', 'border-bottom-style', 'border-bottom-color'],
  'border-left': ['border-left-width', 'border-left-style', 'border-left-color'],
  'border': ['border-top-width', 'border-top-style', 'border-top-color', 'border-right-width', 'border-right-style', 'border-right-color', 'border-bottom-width', 'border-bottom-style', 'border-bottom-color', 'border-left-width', 'border-left-style', 'border-left-color', 'border-image'],
  'border-block': ['border-top-width', 'border-top-style', 'border-top-color', 'border-bottom-width', 'border-bottom-style', 'border-bottom-color'],
  'border-inline': ['border-left-width', 'border-left-style', 'border-left-color', 'border-right-width', 'border-right-style', 'border-right-color'],
  'background': ['background-color', 'background-image', 'background-position', 'background-size', 'background-repeat', 'background-origin', 'background-clip', 'background-attachment'],
  'font': ['font-family', 'font-size', 'font-weight', 'font-style', 'font-variant', 'font-stretch', 'line-height'],
  'flex': ['flex-grow', 'flex-shrink', 'flex-basis'],
  'flex-flow': ['flex-direction', 'flex-wrap'],
  'place-items': ['align-items', 'justify-items'],
  'place-content': ['align-content', 'justify-content'],
  'place-self': ['align-self', 'justify-self'],
  'grid': ['grid-template-rows', 'grid-template-columns', 'grid-template-areas', 'grid-auto-rows', 'grid-auto-columns', 'grid-auto-flow'],
  'grid-template': ['grid-template-rows', 'grid-template-columns', 'grid-template-areas'],
  'grid-area': ['grid-row-start', 'grid-row-end', 'grid-column-start', 'grid-column-end'],
  'grid-row': ['grid-row-start', 'grid-row-end'],
  'grid-column': ['grid-column-start', 'grid-column-end'],
  'grid-gap': ['row-gap', 'column-gap'],
  'grid-row-gap': ['row-gap'],
  'grid-column-gap': ['column-gap'],
  'text-decoration': ['text-decoration-line', 'text-decoration-style', 'text-decoration-color', 'text-decoration-thickness'],
  'transition': ['transition-property', 'transition-duration', 'transition-timing-function', 'transition-delay'],
  'animation': ['animation-name', 'animation-duration', 'animation-timing-function', 'animation-delay', 'animation-iteration-count', 'animation-direction', 'animation-fill-mode', 'animation-play-state'],
  'outline': ['outline-width', 'outline-style', 'outline-color'],
  'list-style': ['list-style-type', 'list-style-position', 'list-style-image'],
  'columns': ['column-width', 'column-count'],
  'column-rule': ['column-rule-width', 'column-rule-style', 'column-rule-color'],
  'inset-block': ['top', 'bottom'],
  'inset-inline': ['left', 'right'],
  'padding-block': ['padding-top', 'padding-bottom'],
  'padding-inline': ['padding-left', 'padding-right'],
  'margin-block': ['margin-top', 'margin-bottom'],
  'margin-inline': ['margin-left', 'margin-right'],
};
function expandProp(p) {
  if (p.startsWith('--')) return [p];
  const lp = p.toLowerCase();
  if (lp === 'all') return ['*ALL*'];
  if (SHORTHANDS[lp]) return SHORTHANDS[lp];
  return [lp];
}
function propsOverlap(a, b) {
  if (a.startsWith('--') || b.startsWith('--')) return a === b;
  const ea = expandProp(a), eb = expandProp(b);
  if (ea.includes('*ALL*') || eb.includes('*ALL*')) return true;
  return ea.some(x => eb.includes(x));
}
function samePropName(a, b) {
  if (a.startsWith('--') || b.startsWith('--')) return a === b;
  return a.toLowerCase() === b.toLowerCase();
}
function normVal(v) { return v.replace(/\s+/g, ' ').trim(); }
function mediaInterval(at) {
  let lo = 0, hi = Infinity, unknown = false;
  for (const q of at) {
    if (!q.startsWith('@media')) { unknown = true; continue; }
    if (q.includes(',')) unknown = true;
    if (!/width/.test(q)) unknown = true;
    for (const m of q.matchAll(/min-width:\s*([\d.]+)px/g)) lo = Math.max(lo, parseFloat(m[1]));
    for (const m of q.matchAll(/max-width:\s*([\d.]+)px/g)) hi = Math.min(hi, parseFloat(m[1]));
  }
  return { lo, hi, unknown };
}
function mediaIntersects(A, B) {
  if (A.unknown || B.unknown) return true;
  return Math.max(A.lo, B.lo) <= Math.min(A.hi, B.hi);
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
    for (const c of (m[1].match(/\.[A-Za-z0-9_-]+/g) || [])) globals.push(c.slice(1));
    const tm = m[1].match(/(^|[\s(])([a-zA-Z][\w-]*)/);
    t = t.replace(m[0], tm ? tm[2] : '');
  }
  t = t.replace(/\[[^\]]*\]/g, '');
  const classes = (t.match(/\.[A-Za-z0-9_-]+/g) || []).map(x => x.slice(1));
  const tagM = t.match(/^([a-zA-Z][\w-]*)/);
  return { classes, globals, tag: tagM ? tagM[1].toLowerCase() : null };
}
function subjectInfo(sel) {
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
  const pm = subject.match(/::([\w-]+)$/) || subject.match(/:(before|after)$/);
  if (pm) { pseudoEl = pm[1]; subject = subject.slice(0, subject.length - pm[0].length); }
  const subj = compoundParts(subject);
  const allClasses = [], allGlobals = [];
  for (const c of compounds) {
    const p = compoundParts(c === compounds[compounds.length - 1] ? subject : c);
    allClasses.push(...p.classes);
    allGlobals.push(...p.globals);
  }
  return {
    classes: subj.classes, globals: subj.globals, tag: subj.tag, pseudoEl,
    allClasses, allGlobals,
    bare: subj.classes.length + subj.globals.length === 0 && !subj.tag,
  };
}

/* ---------------- analysis bundle ---------------- */
function buildAnalysis(cfg) {
  const src = fs.readFileSync(cfg.cssPath, 'utf8');
  const markerOffset = (() => {
    if (!cfg.finalMarker) return Infinity;
    const i = src.lastIndexOf(cfg.finalMarker);
    return i === -1 ? Infinity : i;
  })();

  const WILDCARDS = new Set(cfg.wildcards);
  const ev2 = [];
  const evidenceSets = (() => {
    const sets = [];
    const seen2 = new Set();
    const tryLoad = (p, fn) => { try { fn(JSON.parse(fs.readFileSync(p, 'utf8'))); } catch (e) {} };
    tryLoad(path.join(cfg.workDir, 'tsx-evidence.json'), arr => { for (const a of arr) sets.push(new Set(a)); });
    for (const f of fs.readdirSync(cfg.workDir).filter(x => /^(base-\d+|mbase-\d+|evidence-[\w-]+|ev2-[\w-]+)\.json$/.test(x))) {
      tryLoad(path.join(cfg.workDir, f), raw => {
        const snap = raw.result && raw.result.value ? JSON.parse(raw.result.value) : raw;
        for (const k of snap.evidence || []) sets.push(new Set(k.split('|')));
        for (const k of snap.evidence2 || []) {
          if (seen2.has(k)) continue;
          seen2.add(k);
          const [tag, own, closure] = k.split('§');
          ev2.push({ tag, own: new Set(own ? own.split('.') : []), closure: new Set(closure ? closure.split('.') : []) });
        }
      });
    }
    return sets;
  })();

  function coMatch(sa, sb) {
    if ((sa.pseudoEl || null) !== (sb.pseudoEl || null)) return false;
    if (sa.tag && sb.tag && sa.tag !== sb.tag && sa.tag !== '*' && sb.tag !== '*') return false;
    const own = [
      ...sa.classes.filter(c => !WILDCARDS.has(c)),
      ...sb.classes.filter(c => !WILDCARDS.has(c)),
      ...sa.globals, ...sb.globals,
    ];
    if (own.length) {
      const ownOK =
        evidenceSets.some(E => own.every(c => E.has(c))) ||
        ev2.some(e => own.every(c => e.own.has(c)));
      if (!ownOK && (evidenceSets.length || ev2.length)) return false;
    }
    // 闭包（祖先）否决权只在真的涉及祖先类时启用：同复合内组合必须由 TSX∪DOM 自身证据裁决，
    // 因为 DOM 闭包看不到当前数据态未出现的条件态。
    const ancestorExtra = [
      ...sa.allClasses.filter(c => !WILDCARDS.has(c) && !sa.classes.includes(c)),
      ...sb.allClasses.filter(c => !WILDCARDS.has(c) && !sb.classes.includes(c)),
      ...sa.allGlobals.filter(c => !sa.globals.includes(c)),
      ...sb.allGlobals.filter(c => !sb.globals.includes(c)),
    ];
    if (ev2.length && ancestorExtra.length) {
      const all = [
        ...sa.allClasses.filter(c => !WILDCARDS.has(c)),
        ...sb.allClasses.filter(c => !WILDCARDS.has(c)),
        ...sa.allGlobals, ...sb.allGlobals,
      ];
      if (all.length) {
        const tagReq = sa.tag && sa.tag !== '*' ? sa.tag : (sb.tag && sb.tag !== '*' ? sb.tag : null);
        const closureOK = ev2.some(e => (!tagReq || e.tag === tagReq) && all.every(c => e.closure.has(c)));
        if (!closureOK) return false;
      }
    }
    return true;
  }

  const { rules, warnings } = parse(src);
  const groups = new Map();
  for (const r of rules) {
    if (r.at.some(a => a.startsWith('@keyframes'))) continue;
    r.selKey = normSel(r.selRaw);
    r.ctx = ctxKey(r.at);
    const key = r.ctx + '\u0000' + r.selKey;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(r);
  }
  for (const list of groups.values()) list.sort((a, b) => a.selOffset - b.selOffset);

  function planGroup(key) {
    const blocks = groups.get(key);
    const [ctx, selKey] = key.split('\u0000');
    const out = { ctx, selKey, blocks: blocks.map(b => ({ lines: [b.selLine, b.endLine], decls: b.decls.length })), notes: [], conflicts: [], merged: null };
    const inFinal = blocks.filter(b => b.selOffset >= markerOffset);
    let mergeable = blocks.filter(b => b.selOffset < markerOffset);
    if (inFinal.length) out.notes.push(`${inFinal.length} block(s) in FINAL section (kept as-is): lines ${inFinal.map(b => b.selLine).join(',')}`);
    const excluded = mergeable.filter(b => b.decls.some(d => d.important));
    if (excluded.length) out.notes.push(`${excluded.length} block(s) contain !important (excluded, treated as obstacles): lines ${excluded.map(b => b.selLine).join(',')}`);
    mergeable = mergeable.filter(b => !excluded.includes(b));
    out.mergeableCount = mergeable.length;
    if (mergeable.length < 2) { out.notes.push('nothing to merge'); return out; }
    const target = mergeable[mergeable.length - 1];
    out.targetLines = [target.selLine, target.endLine];
    const all = [];
    for (const b of mergeable) for (const d of b.decls) all.push({ ...d, blockLine: b.selLine, isTarget: b === target });
    const retained = [], dropped = [];
    for (let idx = 0; idx < all.length; idx++) {
      const d = all[idx];
      let killer = null;
      for (let j = idx + 1; j < all.length; j++) {
        if (samePropName(all[j].prop, d.prop)) { killer = all[j]; break; }
      }
      if (killer) dropped.push({ prop: d.prop, value: d.value, line: d.line, overriddenByLine: killer.line });
      else retained.push(d);
    }
    const myInterval = mediaInterval(blocks[0].at);
    const myList = splitSelList(selKey).map(s => ({ spec: specificity(s), subj: subjectInfo(s) }));
    const mergeSet = new Set(mergeable);
    out.suppressedByCoMatch = 0;
    for (const d of retained) {
      if (d.isTarget) continue;
      for (const r of rules) {
        if (mergeSet.has(r)) continue;
        if (r.at.some(a => a.startsWith('@keyframes'))) continue;
        if (r.endOffset <= d.offset || r.braceOffset >= target.endOffset) continue;
        if (!mediaIntersects(myInterval, mediaInterval(r.at))) continue;
        const rSelKey = r.selKey || normSel(r.selRaw);
        // 同名选择器共匹配恒真（同一元素必然同时命中两处），不得要求证据；
        // 这是 2026-08-12 确认的三处回归（dhApiMobileFoldSummary 等）的根因修复。
        const myParts = splitSelList(selKey);
        const identicalSel = rSelKey === selKey || splitSelList(rSelKey).some(p => myParts.includes(p));
        const rList = splitSelList(rSelKey).map(s => ({ spec: specificity(s), subj: subjectInfo(s) }));
        const pairOk = identicalSel || myList.some(m => rList.some(t => specEq(m.spec, t.spec) && coMatch(m.subj, t.subj)));
        const pairSpecOnly = identicalSel || myList.some(m => rList.some(t => specEq(m.spec, t.spec)));
        if (!pairSpecOnly) continue;
        for (const od of r.decls) {
          if (od.offset <= d.offset || od.offset >= target.endOffset) continue;
          if (od.important) continue;
          if (!propsOverlap(od.prop, d.prop)) continue;
          if (samePropName(od.prop, d.prop) && normVal(od.value) === normVal(d.value)) continue;
          if (!pairOk) { out.suppressedByCoMatch++; continue; }
          out.conflicts.push({
            prop: d.prop, value: normVal(d.value).slice(0, 60), declLine: d.line, fromBlockLine: d.blockLine,
            obstacleSel: normSel(r.selRaw).slice(0, 90), obstacleLine: od.line, obstacleProp: od.prop,
            obstacleValue: normVal(od.value).slice(0, 60), obstacleCtx: r.ctx,
          });
        }
      }
    }
    out.merged = {
      targetLines: out.targetLines,
      deleteBlocks: mergeable.filter(b => b !== target).map(b => ({ lines: [b.selLine, b.endLine] })),
      retained: retained.map(d => ({ prop: d.prop, value: d.value, line: d.line, fromBlockLine: d.blockLine, isTarget: d.isTarget })),
      dropped,
    };
    return out;
  }

  return { cfg, src, rules, warnings, groups, planGroup, markerOffset, evidenceCounts: { flat: evidenceSets.length, ev2: ev2.length } };
}

module.exports = {
  REPO_ROOT, loadConfig, parse, normSel, ctxKey, splitSelList, specificity, specEq,
  propsOverlap, samePropName, normVal, mediaInterval, mediaIntersects,
  compoundParts, subjectInfo, buildAnalysis,
};
