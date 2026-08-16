# -*- coding: utf-8 -*-
"""Generate risk-overview-v6.html: v5 skeleton + Obsidian (direction C) KPI cards."""
import duckdb, io

con = duckdb.connect(r'F:\MOSS-V3\data\moss.duckdb', read_only=True)

METRICS = [
    dict(key='reg',  col='regulatory_dv01',             label='监管 DV01',      unit='万元', scale=1e4, fmt=',.2f', cap='范围：全部正式行',          alert=False, dk='pct'),
    dict(key='val',  col='portfolio_dv01',              label='估值 DV01',      unit='万元', scale=1e4, fmt=',.2f', cap='同值属口径预期',            alert=False, dk='pct'),
    dict(key='dur',  col='portfolio_modified_duration', label='修正久期',       unit='',     scale=1,   fmt='.2f',  cap='市值加权',                alert=False, dk='abs'),
    dict(key='cvx',  col='portfolio_convexity',         label='组合凸度',       unit='',     scale=1,   fmt='.2f',  cap='张量直读',                alert=False, dk='abs'),
    dict(key='cs',   col='cs01',                        label='CS01 信用利差',  unit='万元', scale=1e4, fmt=',.2f', cap='每 bp 利差',              alert=False, dk='pct'),
    dict(key='hhi',  col='issuer_concentration_hhi',    label='发行人 HHI',     unit='%',    scale=0.01, fmt='.2f', cap='集中度指数 · 低集中',      alert=False, dk='pp'),
    dict(key='top5', col='issuer_top5_weight',          label='前五大权重',     unit='%',    scale=0.01, fmt='.1f', cap='发行人口径',              alert=False, dk='pp'),
    dict(key='gap',  col='liquidity_gap_30d',           label='30D 流动性缺口', unit='亿元', scale=1e8, fmt=',.2f', cap='',                        alert=True,  dk='absu'),
]

cols = ', '.join(m['col'] for m in METRICS) + ', liquidity_gap_90d'
rows = con.execute(
    f"SELECT report_date, {cols} FROM fact_formal_risk_tensor_daily "
    "ORDER BY report_date DESC LIMIT 24").fetchall()
rows = rows[::-1]
gap90 = float(rows[-1][-1]) / 1e8
METRICS[-1]['cap'] = f'90D 缺口 {gap90:.2f} 亿'

for i, m in enumerate(METRICS):
    j = i + 1
    m['series'] = [float(r[j]) / m['scale'] for r in rows]
    cur, prev = m['series'][-1], m['series'][-2]
    d = cur - prev
    arrow = '▲' if d >= 0 else '▼'
    if m['dk'] == 'pct':
        m['chip'] = f"{arrow} {abs(d / abs(prev) * 100 if prev else 0):.1f}%"
    elif m['dk'] == 'pp':
        m['chip'] = f"{arrow} {abs(d):.2f}pp" if m['fmt'] == '.2f' else f"{arrow} {abs(d):.1f}pp"
    else:
        m['chip'] = f"{arrow} {abs(d):,.2f} {m['unit']}".rstrip()
    m['val_s'] = f"{cur:{m['fmt']}}"

def smooth(vals, w, h, px, pt, pb):
    n = len(vals); lo = min(vals); hi = max(vals); rng = (hi - lo) or 1.0
    pts = [(px + i * (w - 2 * px) / (n - 1), pt + (1 - (v - lo) / rng) * (h - pt - pb))
           for i, v in enumerate(vals)]
    d = [f'M {pts[0][0]:.1f},{pts[0][1]:.1f}']
    for i in range(n - 1):
        p0 = pts[i - 1] if i > 0 else pts[0]
        p1, p2 = pts[i], pts[i + 1]
        p3 = pts[i + 2] if i + 2 < n else pts[-1]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        d.append(f'C {c1[0]:.1f},{c1[1]:.1f} {c2[0]:.1f},{c2[1]:.1f} {p2[0]:.1f},{p2[1]:.1f}')
    return ' '.join(d), pts

def card(m):
    line, pts = smooth(m['series'], 96, 30, 3, 5, 3)
    area = f'{line} L {pts[-1][0]:.1f},30 L {pts[0][0]:.1f},30 Z'
    x, y = pts[-1]
    fill = 'var(--spark-fill-err)' if m['alert'] else 'var(--spark-fill)'
    stroke = 'var(--err)' if m['alert'] else 'var(--acc)'
    al = ' alert' if m['alert'] else ''
    bad = ' class="bad"' if m['alert'] else ''
    unit = f'<small> {m["unit"]}</small>' if m['unit'] else ''
    return f'''      <div class="kpi{al}">
        <div class="cap">{m['label']}<i{bad}></i></div>
        <div class="num">{m['val_s']}{unit}</div>
        <svg viewBox="0 0 96 30" preserveAspectRatio="none"><path d="{area}" fill="{fill}"/><path class="glow" d="{line}" fill="none" stroke="{stroke}" stroke-width="1.5"/><circle cx="{x:.1f}" cy="{y:.1f}" r="5.5" fill="{fill}"/><circle cx="{x:.1f}" cy="{y:.1f}" r="2.2" fill="{stroke}"/></svg>
        <div class="kfoot2"><span class="chip">{m['chip']}</span><span class="sub">{m['cap']}</span></div>
      </div>'''

cards_html = '\n'.join(card(m) for m in METRICS)

NEW_CSS = '''.kpis { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; }
.kpi { position: relative; border-radius: 14px; padding: 15px 18px 12px; display: flex; flex-direction: column; gap: 8px; background: linear-gradient(165deg, var(--glass-hi), rgba(255, 255, 255, 0.012) 58%), var(--panel); box-shadow: inset 0 1px 0 var(--glass-hi-line), var(--glass-shadow); transition: transform 0.2s ease; }
.kpi:hover { transform: translateY(-3px); }
.kpi::before { content: ""; position: absolute; inset: 0; border-radius: 14px; padding: 1px; pointer-events: none; background: linear-gradient(160deg, var(--acc-dim), var(--glass-line) 32%, var(--glass-line) 68%, var(--acc-dim)); -webkit-mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0); -webkit-mask-composite: xor; mask-composite: exclude; }
.kpi.alert::before { background: linear-gradient(160deg, var(--err), var(--glass-line) 32%, var(--glass-line) 68%, var(--err)); }
.kpi .cap { font-family: var(--mono); font-size: 10px; letter-spacing: 0.14em; color: var(--mut); display: flex; justify-content: space-between; align-items: center; }
.kpi .cap i { width: 6px; height: 6px; border-radius: 50%; background: var(--ok); box-shadow: 0 0 8px var(--ok); }
.kpi .cap i.bad { background: var(--err); box-shadow: 0 0 8px var(--err); }
.kpi .num { font-family: var(--mono); font-size: 25px; font-weight: 800; white-space: nowrap; letter-spacing: -0.01em; background: var(--num-grad); -webkit-background-clip: text; background-clip: text; color: transparent; }
.kpi .num small { font-size: 11px; font-weight: 650; -webkit-text-fill-color: var(--mut); }
.kpi.alert .num { background: var(--num-err); -webkit-background-clip: text; background-clip: text; }
.kpi svg { display: block; width: 100%; height: 30px; }
.kpi .glow { filter: drop-shadow(0 0 5px var(--acc-dim)); }
.kpi.alert .glow { filter: drop-shadow(0 0 5px var(--err)); }
.kfoot2 { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
.kfoot2 .chip { font-family: var(--mono); font-size: 10px; letter-spacing: 0.03em; padding: 2px 9px; border-radius: 999px; background: var(--spark-fill); color: var(--acc); white-space: nowrap; }
.kpi.alert .chip { background: var(--spark-fill-err); color: var(--err); }
.kfoot2 .sub { font-size: 10.5px; color: var(--mut); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }'''

OLD_CSS = '''.kpis { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; }
.kpi { padding: 14px 16px 12px; display: grid; gap: 2px; }
.kpi .cap { font-family: var(--mono); font-size: 10px; letter-spacing: 0.14em; color: var(--mut); display: flex; justify-content: space-between; align-items: center; }
.kpi .cap i { width: 6px; height: 6px; border-radius: 50%; background: var(--ok); box-shadow: 0 0 8px var(--ok); }
.kpi .cap i.bad { background: var(--err); box-shadow: 0 0 8px var(--err); }
.kpi .num { margin-top: 7px; font-family: var(--mono); font-size: 23px; font-weight: 750; white-space: nowrap; background: var(--num-grad); -webkit-background-clip: text; background-clip: text; color: transparent; }
.kpi .num small { font-size: 11px; font-weight: 650; -webkit-text-fill-color: var(--mut); }
.kpi .num.err { background: none; color: var(--err); -webkit-text-fill-color: var(--err); }
.kpi .sub { margin-top: 4px; font-size: 11px; color: var(--ink-2); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.kpi svg { margin-top: 8px; display: block; width: 100%; height: 26px; }'''

src = io.open(r'F:\MOSS-V3\frontend\public\design-lab\risk-overview-v5.html', encoding='utf-8').read()

def swap(s, old, new, tag):
    assert s.count(old) == 1, f'anchor not unique: {tag} ({s.count(old)})'
    return s.replace(old, new)

s = src
s = swap(s, '<title>风险总览 · 设计原型 LAB v5 · 融合定稿候选</title>',
         '<title>风险总览 · 设计原型 LAB v6 · 曜石卡定稿候选</title>', 'title')
s = swap(s, '风险总览 高保真原型 v5 · V3×V4 融合版',
         '风险总览 高保真原型 v6 · V3×V4 融合 + C 曜石卡', 'css comment')
s = swap(s, '  --num-grad: linear-gradient(92deg, #f2f7ff 20%, #7db8ff 90%);',
         '  --num-grad: linear-gradient(92deg, #f2f7ff 20%, #7db8ff 90%);\n  --num-err: linear-gradient(92deg, #ffd9d0 12%, #f0806c 95%);', 'ink num-err')
s = swap(s, '  --num-grad: linear-gradient(92deg, #1a2433 25%, #1c5fd6 95%);',
         '  --num-grad: linear-gradient(92deg, #1a2433 25%, #1c5fd6 95%);\n  --num-err: linear-gradient(92deg, #7e2a18 22%, #c0492f 95%);', 'paper num-err')
s = swap(s, OLD_CSS, NEW_CSS, 'kpi css')
s = swap(s, '''  <b>设计原型 LAB v5</b><span>V3×V4 融合 · 上半页玻璃工艺 × 下半页编辑纪律 · 数据与 v3/v4 完全一致</span>
  <span class="spacer"></span>
  <a href="/design-lab/risk-overview.html">编辑风 v3</a>
  <a href="/design-lab/risk-overview-glass.html">曜石玻璃 v4</a>''',
         '''  <b>设计原型 LAB v6</b><span>C 曜石卡合入融合骨架 · 渐变描边 × 辉光走势 × 涨跌胶囊 · 数据与 v3/v4/v5 完全一致</span>
  <span class="spacer"></span>
  <a href="/design-lab/risk-overview-v5.html">融合 v5</a>
  <a href="/design-lab/card-lab.html">卡片陈列室</a>''', 'banner')

# KPI section: replace between the section comment and the sparkcap line
start = s.index('    <!-- KPI 玻璃卡 × 8(V4 工艺) -->')
end = s.index('    <div class="sparkcap">')
new_section = ('    <!-- KPI 曜石卡 × 8(C 方向:渐变描边 + 辉光走势 + 涨跌胶囊) -->\n'
               '    <section class="kpis">\n' + cards_html + '\n    </section>\n')
s = s[:start] + new_section + s[end:]

out = r'F:\MOSS-V3\frontend\public\design-lab\risk-overview-v6.html'
io.open(out, 'w', encoding='utf-8').write(s)
print('written', out, len(s), 'bytes')
for m in METRICS:
    print(m['key'], m['val_s'], m['chip'])
