# -*- coding: utf-8 -*-
"""Generate card-lab.html: 4 KPI card design directions on real tensor data."""
import duckdb, io

con = duckdb.connect(r'F:\MOSS-V3\data\moss.duckdb', read_only=True)

METRICS = [
    dict(key='reg',  col='regulatory_dv01',             label='监管 DV01',      unit='万元', scale=1e4, fmt=',.2f', cap='范围：全部正式行',          alert=False, dk='pct'),
    dict(key='val',  col='portfolio_dv01',              label='估值 DV01',      unit='万元', scale=1e4, fmt=',.2f', cap='敏感度读数 · 同值属口径预期', alert=False, dk='pct'),
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
rows = rows[::-1]  # chronological
d0, d1 = rows[0][0], rows[-1][0]
gap90 = float(rows[-1][-1]) / 1e8
METRICS[-1]['cap'] = f'90D 缺口 {gap90:.2f} 亿元'

for i, m in enumerate(METRICS):
    j = i + 1
    m['series'] = [float(r[j]) / m['scale'] for r in rows]
    cur, prev = m['series'][-1], m['series'][-2]
    m['cur'], lo, hi = cur, min(m['series']), max(m['series'])
    rng = (hi - lo) or 1.0
    m['lo'], m['hi'] = lo, hi
    m['pos'] = max(0.0, min(100.0, (cur - lo) / rng * 100))
    d = cur - prev
    m['d'] = d
    arrow = '▲' if d >= 0 else '▼'
    if m['dk'] == 'pct':
        pct = d / abs(prev) * 100 if prev else 0.0
        m['chip'] = f'{arrow} {abs(pct):.1f}%'
        m['dtxt'] = f'{d:+,.2f}'
    elif m['dk'] == 'pp':
        m['chip'] = f'{arrow} {abs(d):.2f}pp' if m['fmt'] == '.2f' else f'{arrow} {abs(d):.1f}pp'
        m['dtxt'] = f'{d:+.2f} pp' if m['fmt'] == '.2f' else f'{d:+.1f} pp'
    elif m['dk'] == 'absu':
        m['chip'] = f"{arrow} {abs(d):,.2f} {m['unit']}"
        m['dtxt'] = f"{d:+,.2f} {m['unit']}"
    else:
        m['chip'] = f'{arrow} {abs(d):.2f}'
        m['dtxt'] = f'{d:+.2f}'
    m['val_s'] = f"{cur:{m['fmt']}}"
    m['lo_s'] = f"{lo:{m['fmt']}}"
    m['hi_s'] = f"{hi:{m['fmt']}}"

def smooth(vals, w, h, px=2.0, pt=4.0, pb=2.0):
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

def svg_b(vals):  # editorial: hairline stroke only
    p, pts = smooth(vals, 100, 22, 2, 3, 2)
    return (f'<svg viewBox="0 0 100 22" preserveAspectRatio="none">'
            f'<path class="ln" d="{p}" fill="none" stroke-width="1"/></svg>')

def svg_c(vals):  # obsidian: area + glow + halo
    p, pts = smooth(vals, 96, 30, 3, 5, 3)
    area = f'{p} L {pts[-1][0]:.1f},30 L {pts[0][0]:.1f},30 Z'
    x, y = pts[-1]
    return (f'<svg viewBox="0 0 96 30" preserveAspectRatio="none">'
            f'<path class="ar" d="{area}" stroke="none"/>'
            f'<path class="ln glow" d="{p}" fill="none" stroke-width="1.5"/>'
            f'<circle class="halo" cx="{x:.1f}" cy="{y:.1f}" r="5.5"/>'
            f'<circle class="dot" cx="{x:.1f}" cy="{y:.1f}" r="2.2"/></svg>')

def svg_d(vals):  # split: tall chart, min/max hairlines
    p, pts = smooth(vals, 120, 60, 4, 7, 5)
    area = f'{p} L {pts[-1][0]:.1f},60 L {pts[0][0]:.1f},60 Z'
    x, y = pts[-1]
    return (f'<svg viewBox="0 0 120 60" preserveAspectRatio="none">'
            f'<line class="hair" x1="0" y1="7" x2="120" y2="7" stroke-dasharray="2 3"/>'
            f'<line class="hair" x1="0" y1="55" x2="120" y2="55" stroke-dasharray="2 3"/>'
            f'<path class="ar" d="{area}" stroke="none"/>'
            f'<path class="ln" d="{p}" fill="none" stroke-width="1.4"/>'
            f'<circle class="halo" cx="{x:.1f}" cy="{y:.1f}" r="4.5"/>'
            f'<circle class="dot" cx="{x:.1f}" cy="{y:.1f}" r="2"/></svg>')

def unit(m):
    return f'<span class="u"> {m["unit"]}</span>' if m['unit'] else ''

def card_a(m):
    al = ' alert' if m['alert'] else ''
    return f'''<div class="acard{al}">
  <div class="a-top"><span class="a-label">{m['label']}</span><span class="pip"></span></div>
  <div class="a-num">{m['val_s']}{unit(m)}</div>
  <div class="a-mid"><span class="chip mono">{m['chip']}</span><span class="a-vs">vs 上期</span></div>
  <div class="a-range">
    <div class="track"><span class="mark" style="left:{m['pos']:.1f}%"></span></div>
    <div class="rlabels mono"><span>{m['lo_s']}</span><span>24 期区间</span><span>{m['hi_s']}</span></div>
  </div>
  <div class="a-cap">{m['cap']}</div>
</div>'''

def card_b(m):
    al = ' alert' if m['alert'] else ''
    cls = 'up' if m['d'] >= 0 else 'dn'
    return f'''<div class="bcell{al}">
  <div class="b-label">{m['label']}</div>
  <div class="b-row"><span class="b-num">{m['val_s']}{unit(m)}</span><span class="b-delta mono {cls}">{m['chip']}</span></div>
  <div class="b-spark">{svg_b(m['series'])}</div>
  <div class="b-cap">{m['cap']}</div>
</div>'''

def card_c(m):
    al = ' alert' if m['alert'] else ''
    return f'''<div class="ocard{al}">
  <div class="o-top"><span class="o-label">{m['label']}</span><span class="pip"></span></div>
  <div class="o-num">{m['val_s']}{unit(m)}</div>
  <div class="o-spark">{svg_c(m['series'])}</div>
  <div class="o-foot"><span class="chip mono">{m['chip']}</span><span>{m['cap']}</span></div>
</div>'''

def card_d(m):
    al = ' alert' if m['alert'] else ''
    return f'''<div class="dcard{al}">
  <div class="dleft">
    <div class="d-label">{m['label']}</div>
    <div class="d-num">{m['val_s']}{unit(m)}</div>
    <div><span class="chip mono">{m['chip']}</span></div>
    <div class="d-cap">{m['cap']}</div>
  </div>
  <div class="dright">{svg_d(m['series'])}</div>
</div>'''

ga = '\n'.join(card_a(m) for m in METRICS)
gb = '\n'.join(card_b(m) for m in METRICS)
gc = '\n'.join(card_c(m) for m in METRICS)
gd = '\n'.join(card_d(m) for m in METRICS)

CSS = '''
*{margin:0;padding:0;box-sizing:border-box}
:root[data-theme="ink"]{--bg:#0a0d12;--panel:rgba(255,255,255,.028);--panel2:rgba(255,255,255,.055);
--line:rgba(236,242,255,.09);--line2:rgba(236,242,255,.2);--ink:#e9edf5;--mut:#8d96a9;--faint:#5d6678;
--acc:#7db8ff;--acc-dim:rgba(125,184,255,.35);--fill:rgba(125,184,255,.13);
--err:#f0806c;--err-dim:rgba(240,128,108,.4);--err-fill:rgba(240,128,108,.1);--ok:#46c79c;
--num:linear-gradient(175deg,#ffffff 15%,#b9d4ff 90%);--num-err:linear-gradient(175deg,#ffd9d0 10%,#f0806c 90%);
--shadow:0 14px 34px rgba(0,0,0,.42);--track:rgba(255,255,255,.12)}
:root[data-theme="paper"]{--bg:#f3f0e9;--panel:#ffffff;--panel2:#ffffff;
--line:rgba(23,28,40,.12);--line2:rgba(23,28,40,.26);--ink:#161b27;--mut:#66707f;--faint:#9aa2af;
--acc:#1c5fd6;--acc-dim:rgba(28,95,214,.35);--fill:rgba(28,95,214,.09);
--err:#c0492f;--err-dim:rgba(192,73,47,.4);--err-fill:rgba(192,73,47,.07);--ok:#1e8e5a;
--num:linear-gradient(175deg,#161b27 25%,#1c5fd6 95%);--num-err:linear-gradient(175deg,#7e2a18 20%,#c0492f 95%);
--shadow:0 10px 26px rgba(23,28,40,.1);--track:rgba(23,28,40,.14)}
html,body{background:var(--bg);color:var(--ink)}
body{font:14px/1.5 "Inter","PingFang SC","Microsoft YaHei",system-ui,sans-serif;-webkit-font-smoothing:antialiased}
.mono{font-family:"SF Mono","JetBrains Mono","Consolas",monospace}
.bar{display:flex;justify-content:space-between;align-items:center;padding:16px 30px;border-bottom:1px solid var(--line)}
.bar .t{font-size:12px;letter-spacing:.22em;font-weight:700;color:var(--mut)}
.bar .nav{display:flex;gap:10px;align-items:center}
.tbtn{font-size:11px;padding:4px 14px;border-radius:99px;border:1px solid var(--line);background:transparent;color:var(--mut);cursor:pointer;letter-spacing:.08em}
.tbtn.on{background:var(--ink);color:var(--bg);border-color:var(--ink)}
a.lnk{font-size:11px;color:var(--acc);text-decoration:none;letter-spacing:.06em}
.wrap{max-width:1560px;margin:0 auto;padding:0 30px}
.intro{padding:34px 0 6px}
.intro h1{font-size:26px;font-weight:750;letter-spacing:-.01em}
.intro p{margin-top:6px;font-size:12.5px;color:var(--mut)}
.dir{margin:40px 0 10px}
.dirhead{display:flex;align-items:baseline;gap:16px;margin-bottom:16px;border-top:1px solid var(--line);padding-top:14px}
.dirhead .idx{font-size:30px;font-weight:200;color:var(--faint);font-family:"SF Mono","Consolas",monospace}
.dirhead h2{font-size:16px;font-weight:700;letter-spacing:.03em}
.dirhead p{font-size:12px;color:var(--mut)}
.grid8{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}
.pip{width:6px;height:6px;border-radius:50%;background:var(--ok);box-shadow:0 0 6px var(--ok)}
.alert .pip{background:var(--err);box-shadow:0 0 6px var(--err)}
.chip{font-size:10.5px;padding:2px 9px;border-radius:99px;background:var(--fill);color:var(--acc);letter-spacing:.03em;white-space:nowrap}
.alert .chip{background:var(--err-fill);color:var(--err)}
.ln{stroke:var(--acc)}.ar{fill:var(--fill)}.dot{fill:var(--acc)}.halo{fill:var(--fill)}
.alert .ln{stroke:var(--err)}.alert .ar{fill:var(--err-fill)}.alert .dot{fill:var(--err)}.alert .halo{fill:var(--err-fill)}
.hair{stroke:var(--line2);stroke-width:.6}
.glow{filter:drop-shadow(0 0 5px var(--acc-dim))}
/* A 仪表 */
.acard{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:15px 18px 13px;display:flex;flex-direction:column;gap:9px;transition:border-color .2s,transform .2s}
.acard:hover{border-color:var(--line2);transform:translateY(-2px)}
.acard.alert{background:var(--err-fill);border-color:var(--err-dim)}
.a-top{display:flex;justify-content:space-between;align-items:center}
.a-label{font-size:11px;letter-spacing:.13em;color:var(--mut);font-weight:600}
.a-num{font-size:27px;font-weight:700;letter-spacing:-.01em;font-variant-numeric:tabular-nums}
.a-num .u{font-size:12px;font-weight:500;color:var(--mut)}
.a-mid{display:flex;justify-content:space-between;align-items:center}
.a-vs{font-size:10px;color:var(--faint)}
.a-range{padding-top:1px}
.track{position:relative;height:3px;border-radius:99px;background:var(--track);margin:5px 0 5px}
.mark{position:absolute;top:50%;width:8px;height:8px;border-radius:50%;background:var(--acc);border:2px solid var(--bg);transform:translate(-50%,-50%);box-shadow:0 0 0 2px var(--acc-dim)}
.alert .mark{background:var(--err);box-shadow:0 0 0 2px var(--err-dim)}
.rlabels{display:flex;justify-content:space-between;font-size:9px;color:var(--faint)}
.a-cap{font-size:11px;color:var(--faint)}
/* B 编辑 */
.bgrid{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:var(--line);border-top:1px solid var(--line);border-bottom:1px solid var(--line)}
.bcell{background:var(--bg);padding:19px 22px 15px;display:flex;flex-direction:column;gap:8px;min-height:152px}
.b-label{font-size:10px;letter-spacing:.18em;color:var(--faint);font-weight:600}
.b-row{display:flex;align-items:baseline;justify-content:space-between;gap:8px}
.b-num{font-size:30px;font-weight:300;letter-spacing:-.02em;font-variant-numeric:tabular-nums}
.b-num .u{font-size:12px;color:var(--mut);font-weight:400}
.b-delta{font-size:11px;color:var(--mut)}
.alert .b-num{color:var(--err)}.alert .b-delta{color:var(--err)}
.b-spark svg{width:100%;height:22px;display:block}
.b-cap{font-size:10.5px;color:var(--faint)}
/* C 曜石 */
.ocard{position:relative;border-radius:14px;padding:16px 19px 13px;background:linear-gradient(165deg,var(--panel2),var(--panel) 60%);box-shadow:var(--shadow);display:flex;flex-direction:column;gap:8px;transition:transform .25s}
.ocard:hover{transform:translateY(-3px)}
.ocard::before{content:'';position:absolute;inset:0;border-radius:14px;padding:1px;pointer-events:none;
background:linear-gradient(160deg,var(--acc-dim),var(--line) 32%,var(--line) 68%,var(--acc-dim));
-webkit-mask:linear-gradient(#000 0 0) content-box,linear-gradient(#000 0 0);-webkit-mask-composite:xor;mask-composite:exclude}
.ocard.alert::before{background:linear-gradient(160deg,var(--err-dim),var(--line) 32%,var(--line) 68%,var(--err-dim))}
.o-top{display:flex;justify-content:space-between;align-items:center}
.o-label{font-size:11px;letter-spacing:.13em;color:var(--mut);font-weight:600}
.o-num{font-size:26px;font-weight:800;background:var(--num);-webkit-background-clip:text;background-clip:text;color:transparent;font-variant-numeric:tabular-nums;letter-spacing:-.01em}
.ocard.alert .o-num{background:var(--num-err);-webkit-background-clip:text;background-clip:text}
.o-num .u{font-size:11px;font-weight:500;background:none;-webkit-text-fill-color:var(--mut);color:var(--mut)}
.o-spark svg{width:100%;height:30px;display:block}
.o-foot{display:flex;justify-content:space-between;align-items:center;font-size:10.5px;color:var(--faint)}
/* D 分栏 */
.dcard{display:grid;grid-template-columns:1.02fr .98fr;background:var(--panel);border:1px solid var(--line);border-radius:12px;overflow:hidden;min-height:126px;transition:border-color .2s}
.dcard:hover{border-color:var(--line2)}
.dcard.alert{background:var(--err-fill);border-color:var(--err-dim)}
.dleft{padding:14px 16px;display:flex;flex-direction:column;justify-content:center;gap:5px}
.d-label{font-size:10px;letter-spacing:.16em;color:var(--faint);font-weight:600}
.d-num{font-size:23px;font-weight:700;font-variant-numeric:tabular-nums;letter-spacing:-.01em}
.d-num .u{font-size:11px;font-weight:500;color:var(--mut)}
.d-cap{font-size:10.5px;color:var(--faint)}
.dright{border-left:1px solid var(--line);padding:10px 13px;display:flex;align-items:center}
.dright svg{width:100%;height:62px;display:block}
footer{margin:44px 0 40px;border-top:1px solid var(--line);padding-top:14px;font-size:11px;color:var(--faint);display:flex;justify-content:space-between;gap:20px;flex-wrap:wrap}
@media(max-width:1100px){.grid8,.bgrid{grid-template-columns:repeat(2,1fr)}}
'''

HTML = f'''<!doctype html>
<html lang="zh" data-theme="ink"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>KPI 卡片陈列室 · 风险总览</title>
<style>{CSS}</style></head>
<body>
<header class="bar">
  <span class="t">MOSS · 卡片陈列室 CARD LAB</span>
  <nav class="nav">
    <a class="lnk" href="/design-lab/risk-overview-v5.html">← 返回 v5 整页</a>
    <button class="tbtn on" data-t="ink" onclick="setTheme('ink')">墨</button>
    <button class="tbtn" data-t="paper" onclick="setTheme('paper')">纸</button>
  </nav>
</header>
<main class="wrap">
  <section class="intro">
    <h1>风险总览 · KPI 卡片四个设计方向</h1>
    <p>同一份真实数据（报告日 {d1}，近 24 期 {d0} → {d1}，来源 fact_formal_risk_tensor_daily）· 涨跌均为对上一报告期的真实读数变化 · 右上角切换墨 / 纸</p>
  </section>

  <section class="dir">
    <div class="dirhead"><span class="idx">A</span><h2>仪表 Instrument</h2><p>每张卡带 24 期区间标尺，今天读数在历史带宽中的位置一眼可读 —— 上下文密度最高</p></div>
    <div class="grid8">{ga}</div>
  </section>

  <section class="dir">
    <div class="dirhead"><span class="idx">B</span><h2>编辑 Editorial</h2><p>去掉盒子，只靠发丝线与字重分层 —— 最克制，与下半页 03 / 04 节的编辑风无缝衔接</p></div>
    <div class="bgrid">{gb}</div>
  </section>

  <section class="dir">
    <div class="dirhead"><span class="idx">C</span><h2>曜石 Obsidian</h2><p>深色玻璃工艺推到极致：渐变描边、发光数字、走势辉光与端点光晕 —— 视觉冲击最强</p></div>
    <div class="grid8">{gc}</div>
  </section>

  <section class="dir">
    <div class="dirhead"><span class="idx">D</span><h2>分栏 Split</h2><p>左数右图不对称分栏，走势图放大到全高并带极值参考线 —— 读数与图形各占半壁</p></div>
    <div class="grid8">{gd}</div>
  </section>

  <footer>
    <span>数据窗口：近 24 个报告期 · {d0} → {d1} · 涨跌口径：对上一报告期</span>
    <span>来源：data/moss.duckdb · fact_formal_risk_tensor_daily · 单位：万元 / 亿元 / %</span>
  </footer>
</main>
<script>
function setTheme(t){{document.documentElement.dataset.theme=t;
document.querySelectorAll('.tbtn').forEach(b=>b.classList.toggle('on',b.dataset.t===t));}}
</script>
</body></html>'''

out = r'F:\MOSS-V3\frontend\public\design-lab\card-lab.html'
with io.open(out, 'w', encoding='utf-8') as f:
    f.write(HTML)
print('written', out, len(HTML), 'bytes')
print('window', d0, '->', d1)
for m in METRICS:
    print(m['key'], m['val_s'], m['chip'], f"pos={m['pos']:.0f}%")
