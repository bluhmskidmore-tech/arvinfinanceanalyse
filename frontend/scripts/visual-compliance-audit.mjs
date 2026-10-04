// DESIGN.md §10.1 browser audit. Preserve 2026-10-02 probe statistics for comparison.
import { readFileSync, mkdirSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { classifyControlRoles, classifyTableValues } from './visual-compliance-control-roles.mjs';

export function measureLegacy() {
  const FOLD = innerHeight;
  const main = document.querySelector('[data-testid="workbench-main-content"]') || document.querySelector("main") || document.body;
  const CHROME = '[data-testid="workbench-terminal-bar"], .workbench-section-subnav';
  const CONTROL =
    "button, input, select, textarea, .ant-btn, .ant-select, .ant-picker, .ant-input-number, .ant-input-affix-wrapper, .ant-radio-button-wrapper, .ant-segmented, .ant-switch, .ant-checkbox-wrapper, [role=button], [role=tab]";
  const TABLE_ROOT = ".ag-root-wrapper, .ant-table-wrapper, table";

  const parseColor = (s) => {
    if (!s || s === "transparent") return null;
    let m = s.match(/^rgba?\(([^)]+)\)$/);
    if (m) {
      const p = m[1].split(/[\s,/]+/).filter(Boolean).map(Number);
      return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 };
    }
    m = s.match(/^color\(srgb ([\d.e-]+) ([\d.e-]+) ([\d.e-]+)(?: \/ ([\d.e-]+))?\)$/);
    if (m) return { r: +m[1] * 255, g: +m[2] * 255, b: +m[3] * 255, a: m[4] === undefined ? 1 : +m[4] };
    return null;
  };
  const over = (top, bottom) => ({
    r: top.r * top.a + bottom.r * (1 - top.a),
    g: top.g * top.a + bottom.g * (1 - top.a),
    b: top.b * top.a + bottom.b * (1 - top.a),
    a: 1,
  });
  const diff = (x, y) => Math.max(Math.abs(x.r - y.r), Math.abs(x.g - y.g), Math.abs(x.b - y.b));
  const family = (c) => {
    if (!c || c.a < 0.05) return null;
    const r = c.r / 255, g = c.g / 255, b = c.b / 255;
    const max = Math.max(r, g, b), min = Math.min(r, g, b), d = max - min;
    const l = (max + min) / 2;
    const s = d === 0 ? 0 : d / (1 - Math.abs(2 * l - 1));
    if (d * 255 < 28 || s < 0.2) return "neutral";
    let h = max === r ? ((g - b) / d) % 6 : max === g ? (b - r) / d + 2 : (r - g) / d + 4;
    h *= 60;
    if (h < 0) h += 360;
    if (h >= 225 && h <= 285) return "accent";
    if (h >= 120 && h <= 200) return "up";
    if (h >= 25 && h <= 60) return "warn";
    if (h < 25 || h >= 330) return "down";
    return "other";
  };
  const label = (el) => {
    const cls = [...el.classList].filter((c) => !/^(ant-|css-)/.test(c) || el.classList.length <= 2).slice(0, 2).join(".");
    const tid = el.getAttribute("data-testid");
    return el.tagName.toLowerCase() + (cls ? "." + cls : "") + (tid ? `[${tid}]` : "");
  };
  const selector = (el) => {
    const parts = [];
    for (let cur = el; cur && cur !== document.documentElement; cur = cur.parentElement) {
      if (cur.id) { parts.unshift(`#${CSS.escape(cur.id)}`); break; }
      const siblings = cur.parentElement ? [...cur.parentElement.children].filter((s) => s.tagName === cur.tagName) : [cur];
      parts.unshift(`${cur.tagName.toLowerCase()}:nth-of-type(${siblings.indexOf(cur) + 1})`);
    }
    return parts.join(' > ');
  };
  const visible = (el) =>
    el.checkVisibility ? el.checkVisibility({ checkOpacity: true, checkVisibilityCSS: true }) : el.getClientRects().length > 0;
  const csCache = new Map();
  const css = (el) => {
    let v = csCache.get(el);
    if (!v) csCache.set(el, (v = getComputedStyle(el)));
    return v;
  };

  // 基准底色：从主内容区向上找第一块不透明底。
  let rootBg = { r: 22, g: 24, b: 38, a: 1 };
  for (let el = main; el; el = el.parentElement) {
    const c = parseColor(getComputedStyle(el).backgroundColor);
    if (c && c.a > 0.5) {
      rootBg = { ...c, a: 1 };
      break;
    }
  }

  const mainR = main.getBoundingClientRect();
  const mainCs = getComputedStyle(main);
  const mainInnerW = mainR.width - parseFloat(mainCs.paddingLeft) - parseFloat(mainCs.paddingRight);
  let chromeBottom = mainR.top;
  for (const el of main.querySelectorAll(CHROME)) {
    if (visible(el)) chromeBottom = Math.max(chromeBottom, el.getBoundingClientRect().bottom);
  }
  const bodyH = Math.max(mainR.height, main.scrollHeight) - (chromeBottom - mainR.top);

  // —— 元素遍历：框、标签、按钮、强调色、阴影、圆角、渐变 ——
  const effBg = new Map([[main, rootBg]]);
  const boxInfo = new Map([[main, { depth: 0, rect: null }]]); // 最近框祖先的深度与矩形
  const boxes = [];
  const chips = [];
  const buttons = { total: 0, bordered: 0, primary: 0, foldPrimary: 0 };
  const accent = { text: 0, border: 0, fill: 0 };
  const bars = [];
  const shadows = [];
  const gradients = [];
  const radii = {};

  const sideVisible = (cs, side, ownBg) => {
    const w = parseFloat(cs[`border${side}Width`]);
    const st = cs[`border${side}Style`];
    if (!(w >= 0.5) || st === "none" || st === "hidden") return null;
    const c = parseColor(cs[`border${side}Color`]);
    if (!c || c.a < 0.05) return null;
    if (diff(over(c, ownBg), ownBg) < 4) return null;
    return { w, c };
  };

  for (const el of main.querySelectorAll("*")) {
    const parent = el.parentElement;
    const pBg = effBg.get(parent) || rootBg;
    const pBox = boxInfo.get(parent) || { depth: 0, rect: null };
    if (el.closest("svg, canvas") || el.closest(CHROME)) {
      effBg.set(el, pBg);
      boxInfo.set(el, pBox);
      continue;
    }
    const cs = css(el);
    const own = parseColor(cs.backgroundColor);
    const bg = own && own.a > 0.01 ? over(own, pBg) : pBg;
    effBg.set(el, bg);
    boxInfo.set(el, pBox);
    if (!visible(el)) continue;
    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) continue;

    const sides = ["Top", "Right", "Bottom", "Left"].map((s) => sideVisible(cs, s, bg));
    const nSides = sides.filter(Boolean).length;
    const distinctFill = !!own && own.a > 0.01 && diff(bg, pBg) >= 4;
    const isControl = el.matches(CONTROL);
    const inControl = !isControl && !!parent?.closest(CONTROL);
    const inTable = !!parent?.closest(TABLE_ROOT);
    const hasDirectText = [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim());

    // 强调色用量（文字在文本遍历中按字符统计，这里只记元素数）
    if (hasDirectText && family(parseColor(cs.color)) === "accent") accent.text++;
    if (sides.some((s) => s && family(s.c) === "accent")) accent.border++;
    if (own && own.a >= 0.06 && family(own) === "accent" && !isControl) accent.fill++;

    // 单侧色条（左/上 ≥2px 彩色，其余边无）
    const leftBar = sides[3] && sides[3].w >= 2 && family(sides[3].c) !== "neutral" && !sides[0] && !sides[1] && !sides[2];
    const topBar = sides[0] && sides[0].w >= 2 && family(sides[0].c) !== "neutral" && !sides[1] && !sides[2] && !sides[3];
    if (leftBar || topBar) bars.push(label(el));

    if (cs.boxShadow && cs.boxShadow !== "none") shadows.push(label(el));
    if (/gradient\(/.test(cs.backgroundImage)) gradients.push(label(el));

    if (isControl && el.matches("button, .ant-btn, [role=button]")) {
      buttons.total++;
      if (nSides >= 4) buttons.bordered++;
      if (own && own.a >= 0.5 && family(own) === "accent") {
        buttons.primary++;
        if (r.top < FOLD) buttons.foldPrimary++;
      }
      continue;
    }
    if (isControl || inControl) continue;

    // 标签/徽标：小尺寸、带底或四边框、含短文字
    const text = (el.textContent || "").trim();
    if (r.height >= 14 && r.height <= 30 && r.width >= 16 && r.width <= 260 && text && text.length <= 24 && (distinctFill || nSides >= 4)) {
      const colored =
        [own && own.a > 0.05 ? family(own) : null, ...sides.map((s) => (s ? family(s.c) : null)), family(parseColor(cs.color))].some(
          (f) => f && f !== "neutral",
        );
      chips.push({ text: text.slice(0, 14), colored, top: Math.round(r.top + scrollY) });
      const rad = cs.borderTopLeftRadius;
      radii[rad] = (radii[rad] || 0) + 1;
      continue;
    }

    // 框：≥120×40，三边以上可见边框或与父级可区分的底色；表格内部不计
    if (inTable) continue;
    if (r.width >= 120 && r.height >= 40 && (nSides >= 3 || distinctFill)) {
      const pr = pBox.rect;
      const same = pr && Math.abs(pr.left - r.left) <= 3 && Math.abs(pr.right - r.right) <= 3 && Math.abs(pr.top - r.top) <= 3 && Math.abs(pr.bottom - r.bottom) <= 3;
      if (same) continue;
      const depth = pBox.depth + 1;
      const info = { depth, rect: { left: r.left, right: r.right, top: r.top, bottom: r.bottom } };
      boxInfo.set(el, info);
      boxes.push({ el: label(el), selector: selector(el), depth, x: Math.round(r.left), w: Math.round(r.width), h: Math.round(r.height), top: Math.round(r.top + scrollY) });
      const rad = cs.borderTopLeftRadius;
      radii[rad] = (radii[rad] || 0) + 1;
    }
  }

  // 整页大框：一级框占主内容宽 ≥90%、高 ≥ 页面主体 50%
  const pageFrames = boxes.filter((b) => b.depth === 1 && b.w >= 0.9 * mainInnerW && b.h >= 0.5 * bodyH);

  // —— 文本遍历：字重、字号、彩色字、数字、英文眉标、状态文案 ——
  const t = { chars: 0, bold: 0, heavy: 0, foldChars: 0, foldBold: 0, colored: {}, sizes: {} };
  const nums = { total: 0, nonTabular: 0, mono: 0, fold: 0, samples: [] };
  const eyebrows = [];
  const STATE = /模拟数据|演示数据|示例数据|样例数据|MOCK|Mock|已同步|已接入|已就绪|暂无数据|无数据|数据未就绪|待接入|加载中/g;
  const states = {};
  let dashes = 0;
  const NUM = /^[+\-−±]?[¥$€]?\d[\d,]*(\.\d+)?\s*(%|bp|bps|BP|pp|亿元|万元|亿|万|元|倍|x|X|年|个月|天|笔|只|户)?$/;
  const walker = document.createTreeWalker(main, NodeFilter.SHOW_TEXT);
  for (let n = walker.nextNode(); n; n = walker.nextNode()) {
    const raw = n.textContent.trim();
    if (!raw) continue;
    const el = n.parentElement;
    if (!el || el.closest("svg, script, style") || el.closest(CHROME) || !visible(el)) continue;
    const cs = css(el);
    const rect = el.getBoundingClientRect();
    if (rect.width < 1 || rect.height < 1) continue;
    const len = raw.length;
    const w = parseInt(cs.fontWeight, 10) || 400;
    const size = Math.round(parseFloat(cs.fontSize) * 2) / 2;
    const fold = rect.top < FOLD;
    t.chars += len;
    if (w >= 600) t.bold += len;
    if (w >= 700) t.heavy += len;
    if (fold) {
      t.foldChars += len;
      if (w >= 600) t.foldBold += len;
    }
    t.sizes[size] = (t.sizes[size] || 0) + len;
    const fam = family(parseColor(cs.color));
    if (fam && fam !== "neutral") t.colored[fam] = (t.colored[fam] || 0) + len;
    if (NUM.test(raw.replace(/\s+/g, ""))) {
      nums.total++;
      if (fold) nums.fold++;
      const tab = /tabular-nums/.test(cs.fontVariantNumeric);
      const mono = /mono|consolas|courier|menlo/i.test(cs.fontFamily);
      if (!tab) {
        nums.nonTabular++;
        if (nums.samples.length < 4) nums.samples.push(`${label(el)} "${raw.slice(0, 12)}"`);
      }
      if (mono) nums.mono++;
    }
    if (/[A-Za-z]{3,}/.test(raw) && (cs.textTransform === "uppercase" || (/^[A-Z][A-Z0-9 &/·.\-]{3,}$/.test(raw) && parseFloat(cs.letterSpacing) >= 0.5))) {
      eyebrows.push(raw.slice(0, 20));
    }
    for (const m of raw.matchAll(STATE)) states[m[0]] = (states[m[0]] || 0) + 1;
    if (/^(—|--|-|N\/A)$/.test(raw)) dashes++;
  }

  // —— 表格密度 ——
  const tables = [];
  for (const tb of main.querySelectorAll("table, .ag-root-wrapper")) {
    if (tables.length >= 6 || tb.closest(CHROME) || !visible(tb) || tb.parentElement?.closest(".ag-root-wrapper")) continue;
    const isAg = tb.classList.contains("ag-root-wrapper");
    const rows = [...tb.querySelectorAll(isAg ? ".ag-center-cols-container .ag-row" : "tbody > tr")].filter(visible);
    if (!rows.length) continue;
    const hs = rows.map((r) => Math.round(r.getBoundingClientRect().height)).sort((a, b) => a - b);
    const th = tb.querySelector(isAg ? ".ag-header-cell-text" : "thead th");
    const td = rows[0].querySelector(isAg ? ".ag-cell" : "td");
    const thCs = th && css(th);
    const tdCs = td && css(td);
    tables.push({
      kind: isAg ? "ag" : "html",
      rows: rows.length,
      rowH: hs[Math.floor(hs.length / 2)],
      th: thCs ? `${parseFloat(thCs.fontSize)}/${thCs.fontWeight}` : "-",
      td: tdCs ? `${parseFloat(tdCs.fontSize)}/${tdCs.fontWeight}` : "-",
    });
  }

  // —— 对齐：面包屑、子导航分组标签、页面标题、上部一级框的左边线 ——
  const textLeft = (root) => {
    if (!root) return null;
    const w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    for (let n = w.nextNode(); n; n = w.nextNode()) {
      if (!n.textContent.trim() || !visible(n.parentElement)) continue;
      const range = document.createRange();
      range.selectNodeContents(n);
      const rr = range.getBoundingClientRect();
      if (rr.width > 0) return Math.round(rr.left);
    }
    return null;
  };
  const crumbX = textLeft(document.querySelector('[data-testid="workbench-terminal-bar"]'));

  // —— 壳层框：主内容区及其祖先、终端条是否自成一框（整页大框的来源） ——
  const chainBg = (el) => {
    const chain = [];
    for (let cur = el; cur; cur = cur.parentElement) chain.unshift(cur);
    let bg = { r: 255, g: 255, b: 255, a: 1 };
    for (const cur of chain) {
      const c = parseColor(getComputedStyle(cur).backgroundColor);
      if (c && c.a > 0.01) bg = over(c, bg);
    }
    return bg;
  };
  const framed = (el) => {
    if (!el || !visible(el)) return null;
    const cs = getComputedStyle(el);
    const bg = chainBg(el);
    const nSides = ["Top", "Right", "Bottom", "Left"].filter((s) => sideVisible(cs, s, bg)).length;
    const applicationRoot = el.matches('#root, #app, .workbench-shell-root, [data-moss-app-root]');
    const fill = !applicationRoot && el.parentElement ? diff(bg, chainBg(el.parentElement)) >= 4 : false;
    if (nSides < 3 && !fill) return null;
    const r = el.getBoundingClientRect();
    return `${label(el)}(${Math.round(r.left)},${Math.round(r.width)}w${nSides >= 3 ? " border" : ""}${fill ? " fill" : ""})`;
  };
  const shellFrames = [];
  const shellFrameDetails = [];
  for (let el = main; el && el !== document.body; el = el.parentElement) {
    const f = framed(el);
    if (f) { shellFrames.push(f); shellFrameDetails.push({ selector: selector(el), value: f }); }
  }
  const terminalFrame = framed(document.querySelector('[data-testid="workbench-terminal-bar"]'));
  const subnavX = textLeft(main.querySelector(".workbench-section-subnav__group-label"));
  const heading = [...main.querySelectorAll("h1, h2")].find((h) => !h.closest(CHROME) && visible(h));
  const titleX = textLeft(heading);
  const edges = {};
  for (const b of boxes) {
    if (b.depth === 1 && b.top < scrollY + 2 * FOLD && b.w >= 0.3 * mainInnerW) edges[b.x] = (edges[b.x] || 0) + 1;
  }

  // —— 溢出与截断 ——
  const truncated = [];
  let clipped = 0;
  for (const el of main.querySelectorAll("*")) {
    if (el.closest(CHROME) || el.closest("svg")) continue;
    const cs = css(el);
    if (cs.overflowX === "visible" || el.scrollWidth <= el.clientWidth + 1) continue;
    const hasText = [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim());
    if (!hasText || !visible(el)) continue;
    if (cs.textOverflow === "ellipsis") truncated.push((el.textContent || "").trim().slice(0, 16));
    else if (cs.overflowX === "hidden" || cs.overflowX === "clip") clipped++;
  }

  const pct = (a, b) => (b ? Math.round((1000 * a) / b) / 10 : 0);
  return {
    screens: Math.round((bodyH / FOLD) * 10) / 10,
    mainInnerW: Math.round(mainInnerW),
    overflowX: Math.max(0, document.documentElement.scrollWidth - innerWidth),
    pageFrames: pageFrames.map((b) => `${b.el}(${b.w}×${b.h})`),
    shellFrames,
    terminalFrame,
    boxes: {
      total: boxes.length,
      d2: boxes.filter((b) => b.depth >= 2).length,
      d3: boxes.filter((b) => b.depth >= 3).length,
      max: boxes.reduce((m, b) => Math.max(m, b.depth), 0),
      deepest: boxes.filter((b) => b.depth >= 3).slice(0, 4).map((b) => b.el),
    },
    text: {
      chars: t.chars,
      boldPct: pct(t.bold, t.chars),
      foldBoldPct: pct(t.foldBold, t.foldChars),
      heavyPct: pct(t.heavy, t.chars),
      coloredPct: pct(Object.values(t.colored).reduce((a, b) => a + b, 0), t.chars),
      colored: t.colored,
      sizes: Object.entries(t.sizes)
        .sort((a, b) => b[1] - a[1])
        .map(([s, c]) => `${s}:${pct(c, t.chars)}%`),
      distinctSizes: Object.entries(t.sizes).filter(([, c]) => c / t.chars >= 0.005).length,
    },
    nums,
    eyebrows: eyebrows.slice(0, 6),
    eyebrowCount: eyebrows.length,
    states,
    dashes,
    chips: { total: chips.length, colored: chips.filter((c) => c.colored).length, fold: chips.filter((c) => c.top < FOLD).length, samples: chips.filter((c) => c.colored).slice(0, 5).map((c) => c.text) },
    buttons,
    accent,
    bars: { count: bars.length, samples: [...new Set(bars)].slice(0, 3) },
    shadows: { count: shadows.length, samples: [...new Set(shadows)].slice(0, 3) },
    gradients: { count: gradients.length, samples: [...new Set(gradients)].slice(0, 3) },
    radii,
    tables,
    align: { crumbX, subnavX, titleX, edges },
    truncated: { count: truncated.length, samples: truncated.slice(0, 4) },
    clipped,
    evidence: { boxes, pageFrames, shellFrames: shellFrameDetails },
  };
}

// Browser-only supplement. It adds complete selector evidence without changing the legacy counts.
export function measureCompliance({ config, legacy, route, controlRoles = [], tableValueRoles = [] }) {
  const main = document.querySelector('[data-testid="workbench-main-content"]') || document.querySelector('main') || document.body;
  const chrome = '[data-testid="workbench-terminal-bar"], .workbench-section-subnav';
  const tableRoot = 'table, .ag-root-wrapper, .ant-table-wrapper';
  const controlSelector = 'button, select, textarea, input, .ant-select, .ant-picker, .ant-input-number, .ant-input-affix-wrapper, [role="button"], [role="tab"]';
  const roles = new Map(controlRoles.map((record) => [document.querySelector(record.selector), record]));
  const valueRoles = new Map(tableValueRoles.map((record) => [document.querySelector(record.selector), record]));
  const cfg = config.measurements;
  const metrics = Object.fromEntries(Object.keys(config.rules).map((key) => [key, { value: 0, entries: [] }]));
  const cache = new Map();
  const style = (el) => { if (!cache.has(el)) cache.set(el, getComputedStyle(el)); return cache.get(el); };
  const visible = (el) => el && (el.checkVisibility ? el.checkVisibility({ checkOpacity: true, checkVisibilityCSS: true }) : el.getClientRects().length > 0);
  const selector = (el) => {
    const parts = [];
    for (let cur = el; cur && cur !== document.documentElement; cur = cur.parentElement) {
      if (cur.id) { parts.unshift(`#${CSS.escape(cur.id)}`); break; }
      const siblings = cur.parentElement ? [...cur.parentElement.children].filter((s) => s.tagName === cur.tagName) : [cur];
      parts.unshift(`${cur.tagName.toLowerCase()}:nth-of-type(${siblings.indexOf(cur) + 1})`);
    }
    return parts.join(' > ');
  };
  const matches = (el, selectors) => selectors.some((s) => el.matches(s));
  const add = (rule, el, value, detail = {}) => {
    const exemptions = config.exceptions.filter((e) => e.route === route && e.rule === rule && matches(el, e.selectors));
    metrics[rule].entries.push({ selector: selector(el), value, ...detail, ...(exemptions.length ? { exemptions } : {}) });
    if (!exemptions.length) metrics[rule].value++;
  };
  const color = (value) => {
    const match = value?.match(/^rgba?\(([^)]+)\)$/);
    if (match) { const v = match[1].split(/[\s,/]+/).filter(Boolean).map(Number); return [...v.slice(0, 3), v[3] ?? 1]; }
    const srgb = value?.match(/^color\(srgb ([\d.e-]+) ([\d.e-]+) ([\d.e-]+)(?: \/ ([\d.e-]+))?\)$/);
    return srgb ? [+srgb[1] * 255, +srgb[2] * 255, +srgb[3] * 255, +(srgb[4] ?? 1)] : null;
  };
  const family = (value) => {
    const c = color(value); if (!c || c[3] < 0.05) return 'neutral';
    const [r, g, b] = c.map((v) => v / 255), hi = Math.max(r, g, b), lo = Math.min(r, g, b), d = hi - lo;
    const sat = d === 0 ? 0 : d / (1 - Math.abs(hi + lo - 1));
    if (d * 255 < 28 || sat < 0.2) return 'neutral';
    let hue = (hi === r ? ((g - b) / d) % 6 : hi === g ? (b - r) / d + 2 : (r - g) / d + 4) * 60;
    if (hue < 0) hue += 360;
    return hue >= 225 && hue <= 285 ? 'accent' : 'semantic';
  };
  const borderVisible = (cs, side) => parseFloat(cs[`border${side}Width`]) >= 0.5 && !['none', 'hidden'].includes(cs[`border${side}Style`]) && (color(cs[`border${side}Color`])?.[3] ?? 0) >= 0.05;
  const sides = ['Top', 'Right', 'Bottom', 'Left'];
  const corners = ['TopLeft', 'TopRight', 'BottomRight', 'BottomLeft'];
  const isNumber = (text) => /^[+\-−±]?[¥$€]?\d[\d,]*(\.\d+)?\s*(%|bp|bps|BP|pp|亿元|万元|亿|万|元|倍|x|X|年|个月|天|笔|只|户)?$/.test(text.replace(/\s+/g, ''));
  const isIdentifier = (el) => !!el.closest('code, pre, kbd, samp, [data-moss-value-role="id"], [data-moss-value-role="code"]') || valueRoles.get(el.closest('td, .ag-cell'))?.role === 'identifier';
  const roots = [...legacy.evidence.shellFrames, ...legacy.evidence.pageFrames];
  for (const entry of roots) add('skeleton.frames', document.querySelector(entry.selector), entry.value ?? `${entry.w}×${entry.h}`);
  // The original probe treated every button as a small control, so clickable card roots were
  // absent from its box statistics. Add those roots to compliance only; baseline fields stay intact.
  const complianceBoxes = [...legacy.evidence.boxes];
  const background = (el) => {
    const chain = []; for (let cur = el; cur; cur = cur.parentElement) chain.unshift(cur);
    let bg = [255, 255, 255];
    for (const cur of chain) { const c = color(style(cur).backgroundColor); if (c) bg = bg.map((v, i) => c[i] * c[3] + v * (1 - c[3])); }
    return bg;
  };
  for (const [el, record] of roles) {
    if (!el || record.role !== 'clickable-card' || !main.contains(el) || !visible(el)) continue;
    const cs = style(el), rect = el.getBoundingClientRect(), bg = background(el), parentBg = background(el.parentElement);
    const painted = sides.filter((side) => borderVisible(cs, side)).length >= 3 || bg.some((v, i) => Math.abs(v - parentBg[i]) >= 4);
    if (!painted || rect.width < 120 || rect.height < 40) continue;
    const ancestors = complianceBoxes.filter((box) => document.querySelector(box.selector)?.contains(el));
    const depth = ancestors.reduce((max, box) => Math.max(max, box.depth), 0) + 1;
    complianceBoxes.push({ selector: selector(el), depth, x: rect.left, w: rect.width, h: rect.height, top: rect.top + scrollY, role: 'clickable-card' });
  }
  for (const box of complianceBoxes) {
    const el = document.querySelector(box.selector);
    if (box.depth >= 3) add('containers.depth3', el, box.depth);
    if (box.depth >= 2) {
      add('containers.depth2', el, box.depth);
      const registered = config.depth2Reasons.find((e) => e.route === route && matches(el, e.selectors));
      if (!registered) add('containers.undocumentedDepth2', el, box.depth);
    }
  }

  const textEntries = [];
  const walker = document.createTreeWalker(main, NodeFilter.SHOW_TEXT);
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    const text = node.textContent.trim(), el = node.parentElement;
    if (!text || !el || !visible(el) || el.closest('svg, canvas, script, style') || el.closest(chrome)) continue;
    const rect = el.getBoundingClientRect(); if (rect.width < 1 || rect.height < 1) continue;
    const cs = style(el), size = parseFloat(cs.fontSize), weight = parseInt(cs.fontWeight, 10) || 400;
    const entry = { selector: selector(el), chars: text.length, text: text.slice(0, 80), size, weight, fold: rect.top < innerHeight };
    textEntries.push(entry);
    if (weight >= 700) add('typography.heavy', el, weight, { chars: text.length });
    if (!cfg.fontWeights.includes(weight)) add('typography.weights', el, weight);
    if (!cfg.fontSizes.includes(size)) add('typography.sizes', el, size);
    if (size === 24 && isNumber(text)) add('typography.heroCount', el, text);
    if (isNumber(text) && !isIdentifier(el)) {
      if (!/tabular-nums/.test(cs.fontVariantNumeric)) add('numbers.nonTabular', el, cs.fontVariantNumeric, { text });
      if (/mono|consolas|courier|menlo/i.test(cs.fontFamily)) add('numbers.mono', el, cs.fontFamily, { text });
    }
    for (const token of text.matchAll(/模拟(?:数据)?|演示(?:数据)?|示例(?:数据)?|样例(?:数据)?|MOCK/gi)) add('states.demo', el, token[0]);
    for (const token of text.matchAll(/已就绪|已接入|已同步/g)) add('states.routine', el, token[0]);
  }
  const total = textEntries.reduce((sum, entry) => sum + entry.chars, 0);
  const foldTotal = textEntries.filter((entry) => entry.fold).reduce((sum, entry) => sum + entry.chars, 0);
  for (const [key, predicate, denominator] of [
    ['typography.boldPct', (e) => e.weight >= 600, total],
    ['typography.foldBoldPct', (e) => e.fold && e.weight >= 600, foldTotal],
    ['typography.smallPct', (e) => e.size === 11, total],
  ]) {
    const entries = textEntries.filter(predicate);
    metrics[key] = { value: denominator ? entries.reduce((sum, entry) => sum + entry.chars, 0) * 100 / denominator : 0, entries };
  }

  const white = (kind, el, value) => config.decorationWhitelist.some((item) => {
    if (item.kind !== kind || !el.matches(item.selector)) return false;
    return !item.neutralOnly || [...value.matchAll(/rgba?\([^)]+\)/g)].every((c) => family(c[0]) === 'neutral');
  });
  const primaryGroups = new Map();
  const seenControls = new Set();
  for (const el of main.querySelectorAll('*')) {
    if (!visible(el) || el.closest('svg, canvas, script, style') || el.closest(chrome)) continue;
    const cs = style(el), rect = el.getBoundingClientRect();
    if (rect.width < 1 || rect.height < 1) continue;
    const directText = [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim());
    const borderAccent = sides.some((s) => borderVisible(cs, s) && family(cs[`border${s}Color`]) === 'accent');
    const textAccent = directText && family(cs.color) === 'accent';
    const fillAccent = family(cs.backgroundColor) === 'accent';
    const tableLink = !!el.closest('a[href], [role="link"]') && !!el.closest(tableRoot);
    if (!tableLink && (textAccent || borderAccent || fillAccent)) add('accent.elements', el, [textAccent && 'text', borderAccent && 'border', fillAccent && 'fill'].filter(Boolean).join(','));
    if (!tableLink && borderAccent) add('accent.borders', el, 'accent border');
    const text = (el.textContent || '').trim();
    const fill = color(cs.backgroundColor), borderCount = sides.filter((s) => borderVisible(cs, s)).length;
    if (!el.closest(controlSelector) && rect.height >= 14 && rect.height <= 30 && rect.width >= 16 && rect.width <= 260 && text && text.length <= 24 && ((fill?.[3] ?? 0) >= 0.05 || borderCount === 4) && [cs.color, cs.backgroundColor, ...sides.filter((s) => borderVisible(cs, s)).map((s) => cs[`border${s}Color`])].some((c) => family(c) !== 'neutral')) add('labels.colored', el, text);
    if (cs.boxShadow !== 'none' && !white('shadow', el, cs.boxShadow)) add('decoration.shadows', el, cs.boxShadow);
    if (/gradient\(/.test(cs.backgroundImage) && !white('gradient', el, cs.backgroundImage)) add('decoration.gradients', el, cs.backgroundImage);
    const radii = corners.map((c) => cs[`border${c}Radius`]);
    const circle = Math.abs(rect.width - rect.height) <= 1 && radii.every((r) => r === '50%' || (!r.includes('%') && parseFloat(r) >= Math.min(rect.width, rect.height) / 2));
    if (!circle && radii.some((r) => !cfg.radii.includes(parseFloat(r)) || r.includes('%'))) add('decoration.radii', el, radii.join(' '));

    if (el.matches(controlSelector)) {
      // AntD's input is an implementation detail of its containing visible control.
      if (el.matches('input') && (el.matches('[type="checkbox"], [type="radio"], [type="hidden"], [type="range"], [type="file"]') || el.closest('.ant-select, .ant-picker, .ant-input-number, .ant-input-affix-wrapper, .ag-root-wrapper'))) continue;
      if (seenControls.has(el)) continue;
      seenControls.add(el);
      const role = roles.get(el)?.role || 'control';
      const skin = el.querySelector('.ant-select-selector') || el;
      const skinCs = style(skin);
      const h = rect.height, fs = parseFloat(cs.fontSize), rs = corners.map((c) => parseFloat(skinCs[`border${c}Radius`]));
      const textarea = el.tagName === 'TEXTAREA';
      let invalid = false;
      if (role === 'table-sort') invalid = fs !== cfg.tableFontSize || +cs.fontWeight !== cfg.tableHeaderWeight;
      else if (role === 'text-tab') invalid = fs !== cfg.tabFontSize || +cs.fontWeight !== cfg.tabFontWeight || rs.some((r) => r !== cfg.tabRadius) || borderCount >= 3;
      else if (role === 'control') invalid = fs !== cfg.controlFontSize || (!textarea && (Math.abs(h - cfg.controlHeight) > 0.5 || rs.some((r) => r !== cfg.controlRadius)));
      if (invalid) add('controls.geometry', el, { role, height: h, fontSize: fs, fontWeight: +cs.fontWeight, radii: rs }, { roleEvidence: roles.get(el)?.source || 'DESIGN.md §5.4 controls' });
      if (role === 'control' && el.matches('button, [role="button"]') && (el.matches('.ant-btn-primary') || fillAccent)) {
        const group = el.closest('[role="group"], .ant-space, .ant-space-compact, .filter-bar, [data-testid="filter-bar"]') || el.parentElement;
        if (!primaryGroups.has(group)) primaryGroups.set(group, []);
        primaryGroups.get(group).push(selector(el));
      }
    }

    if (directText) {
      const ownClip = cs.overflowX === 'hidden' || cs.overflowX === 'clip' || cs.textOverflow === 'ellipsis';
      const lineClamp = parseInt(cs.webkitLineClamp, 10) > 0;
      const clipped = (ownClip && el.scrollWidth > el.clientWidth + 1) || (lineClamp && el.scrollHeight > el.clientHeight + 1);
      if (clipped) {
        const label = el.closest('label, th, button, [role="tab"], [role="columnheader"], [class*="label"], [class*="title"], [class*="name"]');
        const title = el.getAttribute('title') || el.closest('[title]')?.getAttribute('title');
        const longExplanation = !label && !isNumber(text) && text.length > 40 && title && title.includes(text);
        if (!longExplanation) add('stability.truncation', el, text.slice(0, 100), { title: title || null, scrollWidth: el.scrollWidth, clientWidth: el.clientWidth });
      }
    }
  }
  for (const [group, selectors] of primaryGroups) if (selectors.length > 1) add('controls.primaryPerGroup', group, selectors.length, { controls: selectors });

  for (const table of main.querySelectorAll('table, .ag-root-wrapper')) {
    if (!visible(table) || table.parentElement?.closest('.ag-root-wrapper')) continue;
    const ag = table.matches('.ag-root-wrapper');
    for (const row of table.querySelectorAll(ag ? '.ag-center-cols-container .ag-row, .ag-floating-bottom .ag-row' : 'tbody > tr')) {
      if (!visible(row) || row.matches('.ant-table-measure-row, .ant-table-placeholder') || row.querySelector('td[colspan]')) continue;
      const height = row.getBoundingClientRect().height;
      if (!cfg.tableRowHeights.some((h) => Math.abs(h - height) <= cfg.tableHeightTolerance)) add('tables.rowHeight', row, height);
    }
    for (const cell of table.querySelectorAll(ag ? '.ag-header-cell-text' : 'thead th')) {
      if (!visible(cell) || !cell.textContent.trim()) continue;
      const cs = style(cell);
      if (parseFloat(cs.fontSize) !== cfg.tableFontSize || +cs.fontWeight !== cfg.tableHeaderWeight) add('tables.headerTypography', cell, `${cs.fontSize}/${cs.fontWeight}`);
    }
    for (const cell of table.querySelectorAll(ag ? '.ag-cell' : 'tbody td')) {
      if (!visible(cell) || cell.closest('.ant-table-placeholder') || cell.matches('[colspan]')) continue;
      const cs = style(cell), text = cell.textContent.trim(); if (!text) continue;
      const total = cell.closest('tr, .ag-row')?.matches('[data-total="true"], .ant-table-summary, .ag-row-pinned, [class*="total"], [class*="summary"]') || !!cell.closest('tfoot');
      const expected = total ? cfg.tableTotalWeight : cfg.tableCellWeight;
      if (parseFloat(cs.fontSize) !== cfg.tableFontSize || +cs.fontWeight !== expected) add('tables.cellTypography', cell, `${cs.fontSize}/${cs.fontWeight}`, { expected });
      if (isNumber(text) && !isIdentifier(cell) && cs.textAlign !== 'right' && cs.textAlign !== 'end' && cs.justifyContent !== 'flex-end') add('tables.numericAlignment', cell, cs.textAlign, { text });
      if (['Left', 'Right'].some((s) => borderVisible(cs, s))) add('tables.verticalBorders', cell, [cs.borderLeftWidth, cs.borderRightWidth].join('/'));
    }
  }

  const textLeft = (root) => {
    if (!root) return null;
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      if (!node.textContent.trim() || !visible(node.parentElement)) continue;
      const range = document.createRange(); range.selectNodeContents(node);
      const r = range.getBoundingClientRect(); if (r.width) return r.left;
    }
    return null;
  };
  const alignment = [];
  const crumb = document.querySelector('[data-testid="workbench-page-context"]') || document.querySelector('[data-testid="workbench-terminal-bar"]');
  const subnav = main.querySelector('.workbench-section-subnav__group-label');
  const heading = [...main.querySelectorAll('h1, h2')].find((h) => !h.closest(chrome) && visible(h));
  for (const el of [crumb, subnav, heading]) {
    const value = textLeft(el); if (value !== null) alignment.push({ selector: selector(el), value });
  }
  // Full-width first-level blocks participate; side-by-side secondary panels do not create a new page edge.
  for (const box of legacy.evidence.boxes) if (box.depth === 1 && box.w >= legacy.mainInnerW * 0.75 && box.top < 2 * innerHeight) alignment.push({ selector: box.selector, value: document.querySelector(box.selector).getBoundingClientRect().left });
  const xs = alignment.map((a) => a.value);
  metrics['skeleton.leftEdgeRange'] = { value: xs.length > 1 ? Math.max(...xs) - Math.min(...xs) : 0, entries: alignment };
  const overflow = Math.max(0, document.documentElement.scrollWidth - innerWidth);
  metrics['stability.overflow'] = { value: overflow, entries: overflow ? [...main.querySelectorAll('*')].filter((el) => visible(el) && el.getBoundingClientRect().right > innerWidth + 1 && !el.closest('svg')).map((el) => ({ selector: selector(el), value: el.getBoundingClientRect().right })) : [] };
  return { metrics, textCharacters: total, alignment, controlRoles, tableValueRoles, complianceBoxes, manualReview: config.manualReview };
}

export function validateConfig(config) {
  if (config.schemaVersion !== 1 || !config.rules || !config.measurements || !config.viewports?.length) throw new Error('Invalid visual-compliance configuration');
  for (const [rule, value] of Object.entries(config.rules)) if (!Number.isFinite(value.max) || value.max < 0) throw new Error(`Invalid maximum for ${rule}`);
  for (const entry of [...config.exceptions, ...config.depth2Reasons]) {
    if (!entry.route?.startsWith('/') || !entry.reason?.trim() || !entry.approvedBy?.trim() || /pending|待批准|待确认/i.test(entry.approvedBy) || !entry.selectors?.length) throw new Error('Every exception/reason requires a route, selectors, reason and recorded approver');
    if (entry.rule && !config.rules[entry.rule]) throw new Error(`Unknown exception rule ${entry.rule}`);
    if ('max' in entry || 'threshold' in entry) throw new Error('Exceptions cannot replace thresholds');
  }
  return config;
}

export function evaluateCompliance(measurement, config, scope = 'full', profile = 'all') {
  const checks = [], violations = [];
  for (const [rule, threshold] of Object.entries(config.rules)) {
    if (profile === 'regression') {
      if (!['controls.geometry', 'controls.primaryPerGroup', 'stability.overflow', 'stability.jsErrors'].includes(rule)) continue;
    } else if (scope === 'minimum' && !threshold.minimum) continue;
    const metric = measurement.metrics[rule];
    if (!metric || !Number.isFinite(metric.value)) throw new Error(`Missing or invalid measurement: ${rule}`);
    const check = { rule, value: metric.value, max: threshold.max, passed: metric.value <= threshold.max };
    checks.push(check);
    if (!check.passed) violations.push({ ...check, entries: metric.entries.filter((entry) => !entry.exemptions?.length) });
  }
  return { passed: violations.length === 0, checks, violations };
}

export function parseArgs(args) {
  const here = dirname(fileURLToPath(import.meta.url));
  const options = { base: process.env.SHOT_BASE || 'http://127.0.0.1:5891', out: resolve(here, '../../.tmp/visual-compliance'), config: join(here, 'visual-compliance.thresholds.json'), profile: 'all', routes: [] };
  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (arg === '--help' || arg === '-h') options.help = true;
    else if (['--out', '--base', '--config', '--profile'].includes(arg)) {
      const value = args[++i]; if (!value || value.startsWith('--')) throw new Error(`Missing value for ${arg}`);
      options[arg.slice(2)] = value;
    } else if (arg.startsWith('/')) options.routes.push(arg);
    else throw new Error(`Unknown argument: ${arg}`);
  }
  if (!['all', 'regression'].includes(options.profile)) throw new Error('--profile must be all or regression');
  const url = new URL(options.base);
  if (!['http:', 'https:'].includes(url.protocol)) throw new Error('--base requires an HTTP(S) URL');
  options.base = options.base.replace(/\/$/, '');
  return options;
}

async function run() {
  const options = parseArgs(process.argv.slice(2));
  if (options.help) {
    console.log('node frontend/scripts/visual-compliance-audit.mjs [--base URL] [--out DIR] [--profile all|regression] [/route ...]\nNo routes: audit all 21 routes in both configured viewports. Start the existing mock server separately (with-server.mjs).\nWrites metrics.json, violations.json and viewport-named fold screenshots. Exit 1 = threshold/navigation failure; exit 2 = tool/configuration failure.\nThe regression profile checks controls, horizontal overflow and JavaScript errors only. It is not full design acceptance.');
    return;
  }
  const config = validateConfig(JSON.parse(readFileSync(options.config, 'utf8')));
  const routes = options.routes.length ? options.routes : config.routes;
  const out = resolve(options.out); mkdirSync(out, { recursive: true });
  const { chromium } = await import('@playwright/test');
  const browser = await chromium.launch();
  const results = [];
  const save = () => {
    writeFileSync(join(out, 'metrics.json'), JSON.stringify(results, null, 2));
    writeFileSync(join(out, 'violations.json'), JSON.stringify({ source: config.source, profile: options.profile, manualReview: config.manualReview, results: results.map((r) => ({ route: r.route, viewport: r.viewport, error: r.error, compliance: r.compliance })) }, null, 2));
  };
  try {
    for (const viewport of config.viewports) {
      const context = await browser.newContext({ viewport: { width: viewport.width, height: viewport.height }, deviceScaleFactor: 1, locale: 'zh-CN', timezoneId: 'Asia/Shanghai', reducedMotion: 'reduce' });
      try {
        for (const route of routes) {
          const page = await context.newPage();
          const errors = [];
          page.on('pageerror', (error) => errors.push(String(error)));
          page.on('console', (message) => { if (message.type() === 'error') errors.push(`console: ${message.text()}`); });
          try {
            await page.goto(options.base + route, { waitUntil: 'networkidle', timeout: 60000 });
            await page.evaluate(() => document.fonts.ready);
            await page.waitForTimeout(2000);
            const legacy = await page.evaluate(measureLegacy);
            const controlRoles = await page.evaluate(classifyControlRoles);
            const tableValueRoles = await page.evaluate(classifyTableValues);
            const measurement = await page.evaluate(measureCompliance, { config, legacy, route, controlRoles, tableValueRoles });
            measurement.metrics['stability.jsErrors'] = { value: errors.length, entries: errors.map((value) => ({ selector: '(page)', value })) };
            const compliance = evaluateCompliance(measurement, config, viewport.scope, options.profile);
            const file = `${route.replace(/^\//, '').replace(/[^a-zA-Z0-9_-]+/g, '_') || 'home'}-${viewport.width}x${viewport.height}-fold.png`;
            await page.screenshot({ path: join(out, file) });
            results.push({ ...legacy, route, viewport, errors: errors.length, errorSamples: errors, measurement, compliance, screenshot: join(out, file) });
            console.log(`${route} ${viewport.width}x${viewport.height}: ${compliance.passed ? 'PASS' : 'FAIL'} (${compliance.violations.length} rules); bold=${legacy.text.boldPct}% fold=${legacy.text.foldBoldPct}% d2=${legacy.boxes.d2} d3=${legacy.boxes.d3} nonTabular=${legacy.nums.nonTabular} errors=${errors.length}`);
            for (const violation of compliance.violations) {
              console.log(`  ${violation.rule}: ${Number(violation.value.toFixed(3))} > ${violation.max}`);
              for (const entry of violation.entries.slice(0, 6)) console.log(`    ${entry.selector}: ${JSON.stringify(entry.value ?? entry.text ?? entry.chars)}`);
              if (violation.entries.length > 6) console.log(`    Full selector list: violations.json (${violation.entries.length} entries)`);
            }
          } catch (error) {
            results.push({ route, viewport, error: String(error), errors: errors.length, errorSamples: errors });
            console.log(`${route} ${viewport.width}x${viewport.height}: ERROR ${String(error)}`);
          } finally { await page.close(); save(); }
        }
      } finally { await context.close(); }
    }
  } finally { await browser.close(); save(); }
  const failed = results.filter((r) => r.error || !r.compliance?.passed).length;
  console.log(`\n${results.length} route/viewports; ${failed} failed. Full selectors: ${join(out, 'violations.json')}`);
  console.log('Automatic checks are heuristic. Manual checks remain required by DESIGN.md §10.1.');
  if (failed) process.exitCode = 1;
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  run().catch((error) => { console.error(error); process.exitCode = 2; });
}
