# -*- coding: utf-8 -*-
"""HTML 报告生成：把天气、灾害、价格与静态知识库渲染为单页报告。"""

from __future__ import annotations

import html
import json
import os
from collections.abc import Sequence
from datetime import date, datetime

from .config import CORE_REGION, CULTIVARS, MODEL, PROVINCES, VARIETIES
from .price import direction_tag

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(ROOT, "outputs")

CSS = """
:root{
  --bg:#f7f8fa; --card:#ffffff; --ink:#1c2024; --sub:#5b6470; --line:#e4e8ee;
  --up:#d93025; --down:#0f9960; --flat:#8a93a0;
  --accent:#0f6fd6; --accent-soft:#eaf2fd; --warn:#fff5e6; --warn-line:#f0a500;
}
*{box-sizing:border-box;}
body{margin:0;padding:32px 20px 64px;background:var(--bg);color:var(--ink);
  font-family:"PingFang SC","Microsoft YaHei","Hiragino Sans GB",system-ui,sans-serif;
  font-size:15px;line-height:1.75;}
.wrap{max-width:1040px;margin:0 auto;}
header{margin-bottom:28px;}
h1{font-size:26px;margin:0 0 6px;letter-spacing:.5px;}
.meta{color:var(--sub);font-size:13px;}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;
  padding:22px 24px;margin-bottom:20px;}
h2{font-size:19px;margin:0 0 4px;padding-left:11px;border-left:4px solid var(--accent);}
h2 .en{font-size:12px;color:var(--sub);font-weight:400;margin-left:8px;}
h3{font-size:15.5px;margin:20px 0 8px;color:#2b3440;}
p{margin:8px 0;}
table{width:100%;border-collapse:collapse;margin:12px 0;font-size:13.5px;}
th,td{border:1px solid var(--line);padding:8px 10px;text-align:left;vertical-align:top;}
th{background:#f2f5f9;font-weight:600;color:#3a4453;white-space:nowrap;}
td.num{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums;}
.up{color:var(--up);font-weight:600;}
.down{color:var(--down);font-weight:600;}
.flat{color:var(--flat);}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px;margin:14px 0;}
.kpi{background:#fbfcfe;border:1px solid var(--line);border-radius:10px;padding:12px 14px;}
.kpi .lab{font-size:12px;color:var(--sub);}
.kpi .val{font-size:22px;font-weight:700;margin:2px 0;font-variant-numeric:tabular-nums;}
.kpi .chg{font-size:12px;}
.tag{display:inline-block;font-size:11.5px;padding:1px 8px;border-radius:20px;margin-right:6px;
  border:1px solid var(--line);background:#f4f6f9;color:var(--sub);}
.t-up{background:#fdecea;border-color:#f5c6c0;color:var(--up);}
.t-down{background:#e9f7f0;border-color:#bfe5d1;color:var(--down);}
.t-flat{background:#f0f2f5;border-color:#dde1e7;color:#5b6470;}
.t-key{background:var(--accent-soft);border-color:#bcd9f7;color:var(--accent);}
.note{background:var(--warn);border-left:3px solid var(--warn-line);padding:10px 14px;
  border-radius:0 8px 8px 0;font-size:13.5px;margin:12px 0;color:#6b4a00;}
ul{margin:8px 0;padding-left:22px;}
li{margin:4px 0;}
.split{display:grid;grid-template-columns:1fr 1fr;gap:18px;}
@media(max-width:760px){.split{grid-template-columns:1fr;}}
footer{color:var(--sub);font-size:12.5px;text-align:center;margin-top:28px;line-height:1.9;}
.legend{font-size:12px;color:var(--sub);margin-top:6px;}
.back{display:inline-block;margin-bottom:12px;font-size:13px;color:var(--accent);text-decoration:none;}
</style>
"""

# 注意：CSS 中含大量花括号，不能用 str.format，改用占位符替换
HEAD = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>__TITLE__</title>
<style>""" + CSS + """</head>
<body>
<div class="wrap">
"""


def page(title: str) -> str:
    return HEAD.replace("__TITLE__", title)


def esc(text) -> str:
    return html.escape(str(text if text is not None else "—"))


def num(v, digits=2):
    if v is None:
        return "—"
    return f"{v:.{digits}f}"


# ------------------------------------------------------------------ 走势图
def build_svg_trend(hist_pts: Sequence[tuple], fc_pts: Sequence[tuple],
                    width=900, height=300, title="红香葱产地价走势与预测") -> str:
    """hist_pts: [(date_str, price)], fc_pts: [(date_str, price)]，第一个预测点应接在历史末点之后。"""
    all_pts = [(d, p, "h") for d, p in hist_pts] + [(d, p, "f") for d, p in fc_pts]
    if len(all_pts) < 2:
        return "<p>数据点不足，无法生成走势图。</p>"

    prices = [p for _, p, _ in all_pts]
    lo, hi = min(prices), max(prices)
    pad = max(0.3, (hi - lo) * 0.25)
    y_min, y_max = lo - pad, hi + pad

    ml, mr, mt, mb = 62, 30, 34, 46
    pw = width - ml - mr
    ph = height - mt - mb

    def px(i):
        return ml + pw * i / (len(all_pts) - 1)

    def py(v):
        return mt + ph * (1 - (v - y_min) / (y_max - y_min))

    # 网格
    grid = []
    for k in range(5):
        v = y_min + (y_max - y_min) * k / 4
        y = py(v)
        dash = ' stroke-dasharray="4 4"' if k > 0 else ""
        grid.append(f'<line x1="{ml}" y1="{y:.1f}" x2="{width-mr}" y2="{y:.1f}" '
                    f'stroke="{"#c9d1da" if k==0 else "#e6eaf0"}" stroke-width="1"'
                    f'{dash}/>')
        grid.append(f'<text x="{ml-8}" y="{y+4:.1f}" font-size="11" fill="#7b8595" '
                    f'text-anchor="end">{v:.1f}</text>')

    # 折线：历史段（含与预测点的连接）
    hist_line = []
    for i, (_, p, t) in enumerate(all_pts):
        if t == "h":
            hist_line.append(f"{px(i):.1f},{py(p):.1f}")
    # 连接到第一个预测点
    first_f = next((i for i, (_, _, t) in enumerate(all_pts) if t == "f"), None)
    if first_f is not None:
        hist_line.append(f"{px(first_f):.1f},{py(all_pts[first_f][1]):.1f}")
        fc_line = [f"{px(first_f):.1f},{py(all_pts[first_f][1]):.1f}"]
        for i in range(first_f + 1, len(all_pts)):
            fc_line.append(f"{px(i):.1f},{py(all_pts[i][1]):.1f}")
    else:
        fc_line = []

    dots = []
    labels = []
    for i, (d, p, t) in enumerate(all_pts):
        color = "#0f6fd6" if t == "h" else "#0f9960"
        dots.append(f'<circle cx="{px(i):.1f}" cy="{py(p):.1f}" r="4.2" fill="{color}"/>')
        labels.append(f'<text x="{px(i):.1f}" y="{py(p)-10:.1f}" font-size="11.5" '
                      f'fill="#1c2024" text-anchor="middle">{p:.2f}</text>')
        md = d[5:].replace("-", "/")
        labels.append(f'<text x="{px(i):.1f}" y="{mt+ph+18:.1f}" font-size="10.5" '
                      f'fill="#5b6470" text-anchor="middle">{md}</text>')

    svg = [f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" '
           f'role="img" aria-label="{esc(title)}">',
           f'<rect x="0" y="0" width="{width}" height="{height}" fill="#ffffff"/>']
    svg += grid
    if len(hist_line) >= 2:
        svg.append(f'<polyline points="{" ".join(hist_line)}" fill="none" '
                   f'stroke="#0f6fd6" stroke-width="2.5"/>')
    if len(fc_line) >= 2:
        svg.append(f'<polyline points="{" ".join(fc_line)}" fill="none" stroke="#0f9960" '
                   f'stroke-width="2.5" stroke-dasharray="7 5"/>')
    svg += dots + labels
    svg.append('</svg>')
    return "\n".join(svg)


# ------------------------------------------------------------------ 报告组装
def render_report(ctx: dict) -> str:
    today = ctx["today"]
    w = ctx["weather"]
    d = ctx["disaster"]
    fc = ctx["forecast"]
    hist = ctx["history"]

    core = w["core"]
    daily = core["daily"]
    win = core["windows"]

    # ---- KPI
    red = fc["红香葱"]
    blk = fc["黑葱"]
    kpi = f"""
    <div class="kpi"><div class="lab">红香葱·产地中枢</div><div class="val">{num(red['current'])}</div><div class="chg">元/公斤（云南综合交易价）</div></div>
    <div class="kpi"><div class="lab">黑葱·产地中枢</div><div class="val">{num(blk['current'])}</div><div class="chg">元/公斤（云南综合交易价）</div></div>
    <div class="kpi"><div class="lab">全国生效气象预警</div><div class="val">{d['total']}</div><div class="chg">条（中央气象台）</div></div>
    <div class="kpi"><div class="lab">未来7天产区降水</div><div class="val">{num(win.get('w1', {}).get('precip_total'), 1)}</div><div class="chg">mm · 雨日 {win.get('w1', {}).get('rainy_days', '—')} 天</div></div>
    """

    # ---- 预测总表
    rows = []
    rows.append(f'<tr><td>当前基准</td><td>{today}</td><td class="num">{num(red["current"])}</td>'
                f'<td class="num">{num(blk["current"])}</td><td class="num">—</td>'
                f'<td><span class="tag t-flat">基准</span></td></tr>')
    for r, b in zip(red["rows"], blk["rows"]):
        tag_txt, tag_cls = direction_tag(r["delta_pct"])
        dcls = "up" if r["delta_pct"] > 0 else ("down" if r["delta_pct"] < 0 else "flat")
        rows.append(
            f'<tr><td><strong>{esc(r["label"])}</strong></td><td>{esc(r["target_date"])}</td>'
            f'<td class="num">{num(r["low"])} – {num(r["high"])}</td>'
            f'<td class="num">{num(b["low"])} – {num(b["high"])}</td>'
            f'<td class="num {dcls}">{r["delta_pct"]:+.1f}%</td>'
            f'<td><span class="tag {tag_cls}">{tag_txt}</span></td></tr>')

    forecast_table = f"""
    <table>
      <tr><th>周期</th><th>目标日</th><th>红香葱(元/kg)</th><th>黑葱(元/kg)</th>
          <th>中枢涨跌</th><th>方向</th></tr>
      {''.join(rows)}
    </table>"""

    # ---- 天气逐日表
    day_rows = []
    for d_ in daily[:16]:
        day_rows.append(
            f'<tr><td>{esc(d_["date"])}</td><td>{esc(d_["weather"])}</td>'
            f'<td class="num">{num(d_["tmin"], 1)} / {num(d_["tmax"], 1)}</td>'
            f'<td class="num">{num(d_["precip"], 1)}</td>'
            f'<td class="num">{num(d_["wind"], 1)}</td>'
            f'<td class="num">{esc(d_.get("pop"))}</td></tr>')
    daily_table = f"""
    <table>
      <tr><th>日期</th><th>天气</th><th>最低/最高(℃)</th><th>降水(mm)</th>
          <th>最大风速(m/s)</th><th>降水概率(%)</th></tr>
      {''.join(day_rows) or '<tr><td colspan="6">暂无数据</td></tr>'}
    </table>"""

    # ---- 窗口统计表
    win_labels = {"d3": "未来3天", "w1": "未来1周", "h1": "未来半月(第8-15天)", "m1": "预报期全程"}
    win_rows = []
    for k in ("d3", "w1", "h1", "m1"):
        s = win.get(k, {})
        if not s:
            continue
        win_rows.append(
            f'<tr><td>{esc(win_labels.get(k, k))}</td>'
            f'<td class="num">{num(s.get("tmax_avg"), 1)}</td>'
            f'<td class="num">{num(s.get("tmin_avg"), 1)}</td>'
            f'<td class="num">{num(s.get("precip_total"), 1)}</td>'
            f'<td class="num">{s.get("rainy_days", "—")}</td>'
            f'<td class="num">{s.get("heavy_rain_days", "—")}</td>'
            f'<td class="num">{s.get("gale_days", "—")}</td>'
            f'<td>{esc(s.get("dominant"))}</td></tr>')
    window_table = f"""
    <table>
      <tr><th>窗口</th><th>平均最高(℃)</th><th>平均最低(℃)</th><th>累计降水(mm)</th>
          <th>雨日</th><th>强降水日</th><th>大风日</th><th>主导天气</th></tr>
      {''.join(win_rows)}
    </table>"""

    # ---- 灾害表
    dis_rows = []
    for it in d.get("top", [])[:12]:
        cls = "t-up" if it["rank"] >= 3 else ("t-flat" if it["rank"] == 2 else "t-down")
        area = "产区" if it["is_production_area"] else "销区"
        dis_rows.append(
            f'<tr><td>{esc(it["region"])}</td><td><span class="tag {cls}">'
            f'{esc(it["hazard"])}{esc(it["level"])}</span></td><td>{area}</td>'
            f'<td>{esc(it["impact"])}</td><td>{esc(it["issuetime"])}</td></tr>')
    disaster_table = f"""
    <table>
      <tr><th>区域</th><th>预警</th><th>属性</th><th>产业链影响</th><th>发布时间</th></tr>
      {''.join(dis_rows) or '<tr><td colspan="5">暂无生效预警</td></tr>'}
    </table>"""

    hazard_chips = " ".join(
        f'<span class="tag">{esc(h)} × {c}</span>' for h, c in (d.get("hazard_stats") or [])[:10]
    )

    # ---- 品种 / 栽培品种 / 省份 表
    var_rows = "".join(
        f'<tr><td><strong>{esc(v["name"])}</strong></td><td>{esc(v["desc"])}</td>'
        f'<td>{esc(v["use"])}</td></tr>' for v in VARIETIES)
    cultivar_rows = "".join(
        f'<tr><td><strong>{esc(c["name"])}</strong></td><td>{esc(c["trait"])}</td>'
        f'<td>{esc(c["area"])}</td><td class="num">{esc(c["yield"])}</td></tr>'
        for c in CULTIVARS)
    prov_rows = "".join(
        f'<tr><td><strong>{esc(p["province"])}</strong></td><td>{esc(p["counties"])}</td>'
        f'<td>{esc(p["scale"])}</td><td>{esc(p["season"])}</td></tr>' for p in PROVINCES)

    # ---- 走势图
    hist_pts = [(p["date"], p["price"]) for p in hist.get("series", [])
                if p["variety"] == "红香葱" and p["source"] == "observed"]
    hist_pts.sort()
    fc_pts = [(r["target_date"], r["center"]) for r in red["rows"]]
    svg = build_svg_trend(hist_pts, fc_pts)

    # 各档理由
    why_rows = "".join(
        f'<tr><td><strong>{esc(r["label"])}</strong></td><td>{esc(r["target_date"])}</td>'
        f'<td>{esc("；".join(r["reasons"]))}</td></tr>' for r in red["rows"])

    html_doc = f"""{page('全国香葱行情日报 · ' + today)}
<header>
  <h1>全国香葱行情日报 · 泸西专题</h1>
  <div class="meta">数据日期：{today}（{'一二三四五六日'[date.today().weekday()]}）｜
    覆盖周期：未来3天 / 1周 / 半月 / 1月 ｜ 重点产区：云南·红河州·泸西县 ｜
    生成时间：{ctx['generated_at']}</div>
</header>

<div class="card">
  <h2>一、核心结论速览<span class="en">Executive Summary</span></h2>
  <p>{esc(ctx['summary'])}</p>
  <div class="grid">{kpi}</div>
  {forecast_table}
  <div class="note"><strong>关键变量：</strong>{esc(ctx['key_variable'])}</div>
</div>

<div class="card">
  <h2>二、全国天气与自然灾害<span class="en">Weather &amp; Disaster</span></h2>
  <h3>2.1 {esc(CORE_REGION['name'])}逐日预报（Open-Meteo，未来16天）</h3>
  {daily_table}
  <h3>2.2 窗口统计</h3>
  {window_table}
  <h3>2.3 全国主要观测点（未来7天）</h3>
  <table>
    <tr><th>城市</th><th>省份</th><th>属性</th><th>平均最高(℃)</th>
        <th>累计降水(mm)</th><th>雨日</th><th>主导天气</th></tr>
    {''.join(f'<tr><td>{esc(p["name"])}</td><td>{esc(p["province"])}</td>'
             f'<td>{esc(p["role"])}</td><td class="num">{num(p["w7"].get("tmax_avg"), 1)}</td>'
             f'<td class="num">{num(p["w7"].get("precip_total"), 1)}</td>'
             f'<td class="num">{p["w7"].get("rainy_days", "—")}</td>'
             f'<td>{esc(p["w7"].get("dominant"))}</td></tr>'
             for p in w.get('points', []))}
  </table>
  <h3>2.4 生效气象预警（中央气象台，共 {d['total']} 条）</h3>
  <p>{hazard_chips}</p>
  {disaster_table}
</div>

<div class="card">
  <h2>三、市面常见香葱种类<span class="en">Varieties</span></h2>
  <p>市售"香葱"在植物学上属百合科葱属，主要涵盖<strong>分葱、细香葱、胡葱（火葱/红葱）</strong>三类；
     在批发流通端则主要按<strong>根茎颜色 + 商品规格</strong>分成红香葱、黑葱、白葱（钢葱/铁杆葱）。</p>
  <h3>3.1 流通端商品分类（决定报价）</h3>
  <table>
    <tr><th>类型</th><th>特征</th><th>主要用途/流向</th></tr>
    {var_rows}
  </table>
  <h3>3.2 常见栽培品种</h3>
  <table>
    <tr><th>品种</th><th>特性</th><th>适种/主产区</th><th>参考亩产</th></tr>
    {cultivar_rows}
  </table>
</div>

<div class="card">
  <h2>四、全国香葱种植省份分布<span class="en">Production Map</span></h2>
  <p>全国已形成<strong>"云南为核心、两广为南翼、华东为加工带、川湘豫多点补充"</strong>的格局。</p>
  <table>
    <tr><th>省区</th><th>主产市县</th><th>规模（公开数据）</th><th>上市季节/定位</th></tr>
    {prov_rows}
  </table>
  <div class="note">口径提示：不同机构对小香葱的统计口径差异较大（有按"在田基地面积"、有按"复种面积/亩次"），
    上表以各地官方发布的基地面积与产量为准，不宜直接横向加总。</div>
</div>

<div class="card">
  <h2>五、全国行情分析与预测<span class="en">National Market</span></h2>
  <h3>5.1 供需逻辑</h3>
  <div class="split">
    <div><p><strong>供给端（压制项）</strong></p><ul>{''.join(f'<li>{esc(x)}</li>' for x in ctx['supply_press'])}</ul></div>
    <div><p><strong>潜在利多（触发项）</strong></p><ul>{''.join(f'<li>{esc(x)}</li>' for x in ctx['demand_trigger'])}</ul></div>
  </div>
  <h3>5.2 四档预测依据</h3>
  <table>
    <tr><th>周期</th><th>目标日</th><th>主要驱动因素</th></tr>
    {why_rows}
  </table>
  <p class="legend">价格模型：P(h) = P₀ × 季节性比 × (1 + 天气冲击) × (1 + 动量回归)；
    区间为中枢 ±{MODEL['band_pct']*100:.1f}%。</p>
</div>

<div class="card">
  <h2>六、{esc(CORE_REGION['name'])}专题<span class="en">Luxi County Focus</span></h2>
  <h3>6.1 产业底盘</h3>
  <div class="grid">
    <div class="kpi"><div class="lab">种植基地</div><div class="val">{CORE_REGION['base_mu']/10000:.1f} 万亩</div>
      <div class="chg">复种 {CORE_REGION['replant_mu']/10000:.1f} 万亩次</div></div>
    <div class="kpi"><div class="lab">年产量</div><div class="val">{CORE_REGION['annual_output_t']/10000:.0f} 万吨</div>
      <div class="chg">占云南香葱总产 {CORE_REGION['share_of_yunnan']*100:.0f}%+</div></div>
    <div class="kpi"><div class="lab">年产值</div><div class="val">{CORE_REGION['annual_value_yi']:.0f} 亿元</div>
      <div class="chg">占全县农业总产值七成以上</div></div>
    <div class="kpi"><div class="lab">日外运量</div><div class="val">{CORE_REGION['daily_shipment_t']}+ 吨</div>
      <div class="chg">旺季可达数千吨/日</div></div>
  </div>
  <p><strong>竞争壁垒：</strong>{esc(ctx['luxi_moat'])}</p>
  <h3>6.2 价格预测</h3>
  {forecast_table}
  <h3>6.3 走势示意</h3>
  {svg}
  <div class="legend">蓝线为实测成交中枢（产地综合交易价），绿虚线为模型预测中枢。</div>
  <h3>6.4 专项建议</h3>
  <ul>{''.join(f'<li>{esc(x)}</li>' for x in ctx['advice'])}</ul>
</div>

<div class="card">
  <h2>七、风险提示与假设<span class="en">Risks &amp; Assumptions</span></h2>
  <table>
    <tr><th>风险项</th><th>方向</th><th>触发条件</th><th>应对</th></tr>
    {''.join(f'<tr><td>{esc(r[0])}</td><td><span class="tag {r[1]}">{esc(r[2])}</span></td>'
             f'<td>{esc(r[3])}</td><td>{esc(r[4])}</td></tr>' for r in ctx['risks'])}
  </table>
  <div class="note"><strong>数据说明：</strong>天气数据来自 Open-Meteo 公共 API（ECMWF/ICON 等多模式融合）；
    灾害预警来自中央气象台公开接口；价格数据当前使用
    <strong>{esc(ctx['price_source_label'])}</strong>。
    预测基于公开气象预报、国家气候中心月尺度展望、产区供需结构与历史季节性规律推演，
    未接入任何专有交易数据。价格区间为概率意义上的中枢±合理波动带，非成交承诺；
    本报告仅供产业参考，不构成采销、囤货或投资建议。</div>
</div>

<footer>
  数据来源：Open-Meteo 预报与历史归档 API、中央气象台（nmc.cn）预警接口、国家气候中心、
  农业农村部信息中心、昆明市农业农村局（王旗营批发市场）、新发地市场行情、
  泸西县政府及红河州媒体公开报道、百度百科·泸西小香葱产业。<br>
  自动化生成 · GitHub Actions 定时执行（每日 19:00 UTC = 北京时间 03:00）
</footer>

</div>
</body>
</html>
"""
    return html_doc


def build_index(reports: list[dict]) -> str:
    items = "".join(
        f'<tr><td><a class="back" href="{esc(r["file"])}">{esc(r["date"])}</a></td>'
        f'<td class="num">{esc(r.get("red_current"))}</td>'
        f'<td class="num">{esc(r.get("black_current"))}</td>'
        f'<td>{esc(r.get("generated_at", ""))}</td></tr>'
        for r in sorted(reports, key=lambda x: x["date"], reverse=True))
    return f"""{page('香葱行情日报 · 报告归档')}
<header>
  <h1>香葱行情日报 · 报告归档</h1>
  <div class="meta">由 GitHub Actions 每日自动生成（北京时间 03:00）</div>
</header>
<div class="card">
  <table>
    <tr><th>日期</th><th>红香葱(元/kg)</th><th>黑葱(元/kg)</th><th>生成时间</th></tr>
    {items or '<tr><td colspan="3">暂无报告</td></tr>'}
  </table>
  <p><a class="back" href="latest.html">→ 查看最新一期报告</a></p>
</div>
</div></body></html>
"""


def write_outputs(html_doc: str, ctx: dict) -> dict:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    today = ctx["today"]
    fname = f"香葱行情日报_{today}.html"
    path = os.path.join(OUTPUT_DIR, fname)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html_doc)

    # latest.html
    with open(os.path.join(OUTPUT_DIR, "latest.html"), "w", encoding="utf-8") as f:
        f.write(html_doc)

    # data.json（机器可读）
    payload = {
        "date": today,
        "generated_at": ctx["generated_at"],
        "price_source": ctx["price_source_label"],
        "core_region": CORE_REGION["name"],
        "weather_windows": ctx["weather"]["core"]["windows"],
        "weather_daily": ctx["weather"]["core"]["daily"],
        "disaster": {
            "total": ctx["disaster"]["total"],
            "hazard_stats": ctx["disaster"]["hazard_stats"],
            "top": ctx["disaster"]["top"],
        },
        "forecast": ctx["forecast"],
    }
    with open(os.path.join(OUTPUT_DIR, "data.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    # index：维护归档索引（每日价格写入 archive.json，历史报告也能显示价格）
    archive_path = os.path.join(OUTPUT_DIR, "archive.json")
    archive: list[dict] = []
    if os.path.exists(archive_path):
        try:
            with open(archive_path, encoding="utf-8") as f:
                archive = json.load(f)
        except Exception:  # noqa: BLE001
            archive = []

    red_c = ctx["forecast"].get("红香葱", {}).get("current")
    blk_c = ctx["forecast"].get("黑葱", {}).get("current")
    archive = [a for a in archive if a.get("date") != today]
    archive.append({
        "date": today,
        "file": fname,
        "red_current": red_c,
        "black_current": blk_c,
        "generated_at": ctx["generated_at"],
    })
    archive.sort(key=lambda x: x["date"], reverse=True)
    archive = archive[:90]          # 仅保留最近 90 天
    with open(archive_path, "w", encoding="utf-8") as f:
        json.dump(archive, f, ensure_ascii=False, indent=2)

    idx = build_index(archive)
    with open(os.path.join(OUTPUT_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(idx)

    return {"file": fname, "path": path}
