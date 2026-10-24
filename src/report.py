# -*- coding: utf-8 -*-
"""HTML 报告生成：把天气、灾害、价格与静态知识库渲染为单页报告。"""

from __future__ import annotations

import html
import json
import os
import re
from collections.abc import Sequence
from datetime import date, datetime

from .config import CORE_REGION, CULTIVARS, MODEL, PROVINCES, VARIETIES
from .longterm import svg_line, svg_season
from .price import direction_tag

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(ROOT, "outputs")

# 归档索引最多展示的天数。历史报告 HTML 本身永不删除，此处只限制索引页条数。
ARCHIVE_KEEP_DAYS = 365

# 日报文件名格式，用于从磁盘反向重建归档索引
REPORT_NAME_RE = re.compile(r"^香葱行情日报_(\d{4}-\d{2}-\d{2})\.html$")

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
/* ---- 盘口直览（小程序样式） ---- */
.board{background:linear-gradient(180deg,#e8f2ff 0%,#ffffff 150px);border:1px solid var(--line);
  border-radius:12px;overflow:hidden;margin:12px 0 16px;}
.board-head{padding:14px 18px 8px;}
.board-title{font-size:18px;font-weight:700;letter-spacing:.5px;}
.board-meta{font-size:12px;color:var(--sub);margin-top:4px;}
.board-meta b{color:var(--up);font-weight:600;}
.board-tabs{display:flex;gap:4px;padding:0 14px;border-bottom:2px solid var(--accent);}
.bt{padding:8px 18px;font-size:14px;color:var(--sub);cursor:pointer;user-select:none;
  border-radius:8px 8px 0 0;margin-bottom:-2px;}
.bt.active{background:var(--accent);color:#fff;font-weight:600;}
.board-panel{display:none;padding:4px 12px 12px;}
.board-panel.active{display:block;}
.btab{margin:8px 0 0;}
.btab th{background:#eaf2fc;color:#33506e;}
.btab td{border:none;border-bottom:1px solid #eef1f5;background:transparent;}
.btab tr:nth-child(even) td{background:#f7fafd;}
.btab .name{font-weight:600;}
.btab .arrow-up{color:var(--up);font-weight:700;}
.btab .arrow-down{color:var(--down);font-weight:700;}
.btab .arrow-flat{color:var(--flat);}
.see{color:var(--accent);font-size:12.5px;text-decoration:none;white-space:nowrap;}
.see:hover{text-decoration:underline;}
.mini-sum{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:10px;margin:10px 4px 4px;}
.mini-sum .ms{background:#fff;border:1px solid var(--line);border-radius:10px;padding:10px 14px;font-size:13px;}
.mini-sum .ms b{display:block;font-size:15px;margin-bottom:2px;}
.mini-sum .ms a.see{margin-top:6px;display:inline-block;}
/* 统计条：把计算好的统计落到对应模块底部 */
.bars{display:flex;flex-wrap:wrap;gap:10px;margin:12px 2px 2px;}
.bar{background:#f6f9fd;border:1px solid var(--line);border-left:3px solid var(--accent);
  border-radius:8px;padding:8px 12px;display:flex;flex-wrap:wrap;align-items:center;gap:4px 12px;font-size:12.5px;}
.bar .bt2{font-weight:700;color:#33506e;margin-right:4px;}
.bar i{font-style:normal;color:#5b6573;white-space:nowrap;}
.bar i b{font-style:normal;}
.bar i.k{color:#8a93a0;font-weight:600;}
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


# ------------------------------------------------------------------ 盘口直览（小程序样式）
# 涨跌只能在「同一个市场 + 同一个品项」的口径内计算。
# ORIGIN_SPEC / NATIONAL_SPEC 中 sequence 字段声明该项可回接哪条连续序列；
# 留空表示该盘口目前只有单次采集，不参与涨跌统计（宁可显示 —，也不算跨口径假涨跌）。
ORIGIN_SPEC = [
    ("红葱（通货）", "滇中产区", "红葱", "红香葱", "产地地头/集散价，模型基准口径", "#sec7-forecast"),
    ("黑葱（通货）", "滇中产区", "黑葱", "黑葱", "产地地头/集散价", "#sec7-forecast"),
    ("红香葱（全省综合）", "云南产地综合", "红香葱", None, "全省加权综合价，含精品与通货", "#sec6-spot"),
    ("黑葱（全省综合）", "云南产地综合", "黑葱", None, "全省加权综合价", "#sec6-spot"),
    ("葱（云菜集团出货）", "云菜集团", "葱", None, "企业出货报价，高于产地综合价", "#sec6-spot"),
]

NATIONAL_SPEC = [
    ("小葱", "王旗营", "小葱", "小葱", "昆明一级批发，销区风向标", "#sec6-market"),
    ("葱", "黄淮", "葱", None, "河南周口销区，本地秋葱上市压制", "#sec6-market"),
    ("大葱", "成都农产品", "大葱", None, "西南销区，非香葱口径", "#sec6-market"),
    ("大葱", "太原河西", "大葱", None, "华北销区，非香葱口径", "#sec6-market"),
    ("小葱", "西藏领峰", "小葱", None, "高原远端销区，运距决定溢价", "#sec6-market"),
]


def _obs_points(hist: dict, variety: str) -> list[dict]:
    """某品种的实测序列（按日期升序）。"""
    pts = [p for p in hist.get("series", [])
           if p.get("variety") == variety and p.get("source") == "observed"]
    pts.sort(key=lambda p: p["date"])
    return pts


def _latest_quote(quotes: list[dict], market_kw: str, item: str) -> dict | None:
    """取该市场口径下该品项的最新一条报价。"""
    qs = [q for q in quotes
          if market_kw in q.get("market", "") and item in q.get("item", "")]
    if not qs:
        return None
    qs.sort(key=lambda q: q.get("date", ""))
    return qs[-1]


def _dom_pair(hist: dict, quotes: list[dict], market_kw: str, item: str,
              sequence: str | None):
    """返回 (昨日, 今日, 昨日日期, 今日日期, 来源)。无可比昨日时昨日为 None。

    优先用同一盘口的跨日报价；若盘口只有单次采集，则回退到 spec 声明的
    同源连续序列（该序列口径必须与盘口一致，否则不得声明）。
    """
    qs = sorted([q for q in quotes
                 if market_kw in q.get("market", "") and item in q.get("item", "")],
                key=lambda q: q.get("date", ""))
    if len(qs) >= 2:
        a, b = qs[-2], qs[-1]
        return a.get("mid"), b.get("mid"), a["date"], b["date"], "盘口连续采集"
    if len(qs) == 1 and sequence:
        pts = _obs_points(hist, sequence)
        if len(pts) >= 2:
            a, b = pts[-2], pts[-1]
            return a["price"], b["price"], a["date"], b["date"], "同源日频序列"
        if len(pts) == 1:
            return None, pts[0]["price"], None, pts[0]["date"], "同源日频序列"
    if len(qs) == 1:
        return None, qs[0].get("mid"), None, qs[0]["date"], "当日单次采集"
    if sequence:
        pts = _obs_points(hist, sequence)
        if pts:
            prev = pts[-2]["price"] if len(pts) >= 2 else None
            return prev, pts[-1]["price"], (pts[-2]["date"] if len(pts) >= 2 else None), \
                pts[-1]["date"], "同源日频序列"
    return None, None, None, None, None


def _arrow(chg: float | None) -> str:
    if chg is None:
        return '<span class="arrow-flat">—</span>'
    if chg > 0.005:
        return '<span class="arrow-up">↑</span>'
    if chg < -0.005:
        return '<span class="arrow-down">↓</span>'
    return '<span class="arrow-flat">→</span>'


def _dom_row(name: str, q: dict | None, prev, today, prev_date, src,
             note: str, link: str):
    """盘口行：品名/口径 | 报价区间 | 昨日 | 今日 | 涨跌 | 趋势 | 查看"""
    rg = esc(q.get("range", "—")) if q else "—"
    today_txt = num(today) if today is not None else "暂无报价"
    if prev is not None and today is not None:
        chg = round(today - prev, 2)
        chg_txt = f"{chg:+.2f}" if abs(chg) >= 0.005 else "0.00"
    else:
        chg, chg_txt = None, "—"
    arrow = _arrow(chg)
    note_html = f'<div class="legend">{esc(note)}</div>' if note else ""
    prev_head = f'<div class="legend">{esc(prev_date[5:])}</div>' if prev_date else ""
    day_head = f'<div class="legend">{esc(q["date"][5:])}</div>' if q and q.get("date") else ""
    cls = ""
    if chg is not None and chg > 0.005:
        cls = "up"
    elif chg is not None and chg < -0.005:
        cls = "down"
    return (
        f'<tr><td class="name">{esc(name)}{note_html}</td>'
        f'<td class="num">{rg}</td>'
        f'<td class="num">{num(prev) if prev is not None else "—"}{prev_head}</td>'
        f'<td class="num">{today_txt}{day_head}</td>'
        f'<td class="num {cls}">{chg_txt}</td>'
        f'<td class="num">{arrow}</td>'
        f'<td><a class="see" href="{link}">查看</a></td></tr>')


def _dom_panel_rows(hist: dict, quotes: list[dict], spec: list[tuple]):
    """返回一个盘口表格的行 HTML，以及用于底部统计的可比样本列表。"""
    rows, samples = [], []
    for name, mk, item, seq, note, link in spec:
        q = _latest_quote(quotes, mk, item)
        prev, today, pdate, tdate, src = _dom_pair(hist, quotes, mk, item, seq)
        if q is None and today is None:
            continue
        rows.append(_dom_row(name, q, prev, today, pdate, src, note, link))
        if today is not None:
            chg = round(today - prev, 2) if prev is not None else None
            samples.append({"name": name, "mid": float(today), "chg": chg,
                            "comparable": chg is not None})
    if not rows:
        rows.append('<tr><td colspan="7">暂无当日盘口数据</td></tr>')
    return "".join(rows), samples


def _stat_bars(samples: list[dict], title: str) -> str:
    """把同类样本算出的统计量做成底部统计条。"""
    if not samples:
        return ""
    vals = [s["mid"] for s in samples]
    cmp_ = [s for s in samples if s["comparable"]]
    up = sum(1 for s in cmp_ if s["chg"] > 0.005)
    down = sum(1 for s in cmp_ if s["chg"] < -0.005)
    flat = len(cmp_) - up - down
    hi = max(samples, key=lambda s: s["mid"])
    lo = min(samples, key=lambda s: s["mid"])
    avg = sum(vals) / len(vals)

    if cmp_:
        chgs = [s["chg"] for s in cmp_]
        net = sum(chgs) / len(chgs)
        net_cls = "up" if net > 0.005 else ("down" if net < -0.005 else "")
        move = (f'<i class="k">同口径可比 <b>{len(cmp_)}</b> 项</i>'
                f'<i class="up">涨 <b>{up}</b></i>'
                f'<i class="down">跌 <b>{down}</b></i>'
                f'<i>平 <b>{flat}</b></i>'
                f'<i>平均变动 <b class="{net_cls}">{net:+.2f}</b> 元/kg</i>')
    else:
        move = '<i class="k">本页暂无跨日可比口径，涨跌项空缺</i>'

    return f"""
    <div class="bars">
      <div class="bar">
        <span class="bt2">{esc(title)}</span>
        {move}
      </div>
      <div class="bar">
        <span class="bt2">今日中枢横截面</span>
        <i class="k">样本 <b>{len(vals)}</b> 项</i>
        <i>均价 <b>{avg:.2f}</b></i>
        <i class="up">最高 <b>{hi["mid"]:.2f}</b>（{esc(hi["name"])}）</i>
        <i class="down">最低 <b>{lo["mid"]:.2f}</b>（{esc(lo["name"])}）</i>
        <i>极差 <b>{hi["mid"] - lo["mid"]:.2f}</b> 元/kg</i>
      </div>
    </div>"""


def build_board(ctx: dict) -> str:
    """仿「小香葱行情」小程序的三页签盘口：产地行情 / 全国行情 / 行情解析。"""
    hist = ctx["history"]
    quotes = ctx.get("spot_quotes", [])
    data_date = ctx.get("data_date", ctx["today"])

    # ---------- 页签一：产地行情 ----------
    o_rows, o_samples = _dom_panel_rows(hist, quotes, ORIGIN_SPEC)
    o_bars = _stat_bars(o_samples, "产地涨跌家数")

    # ---------- 页签二：全国行情 ----------
    n_rows, n_samples = _dom_panel_rows(hist, quotes, NATIONAL_SPEC)
    n_bars = _stat_bars(n_samples, "销区涨跌家数")

    table = (f'<table class="btab"><tr>'
             f'<th>品名 / 口径</th><th>报价区间</th>'
             f'<th>昨日</th><th>今日</th><th>涨跌</th><th>趋势</th><th>查看</th></tr>'
             f'{{}}</table>')

    origin_panel = f"""{table.format(o_rows)}
    {o_bars}
    <div class="legend">口径说明：产地行情以云南产区为主，「全省综合价」为加权综合口径，
      高于单一产区集散价，两者不可直接横比；「昨日/今日」仅在标注了同源日期的行上计算，
      其余为当日单次采集，故不给出涨跌。</div>"""

    national_panel = f"""{table.format(n_rows)}
    {n_bars}
    <div class="legend">口径说明：销区「葱 / 大葱」多为大葱口径，与小香葱不可直接比价；
      「西藏 / 黄淮」等高低价主要由运距、品种与季节错配造成，横截面极差不代表行情波动幅度。</div>"""

    # ---------- 页签三：行情解析（把模型算出的统计落到本页） ----------
    fc = ctx.get("forecast", {})
    red = fc.get("红香葱", {})
    rows = red.get("rows", [])
    today_center = red.get("current")

    # 3.1 今日盘面判断：由实测点数与连续走势动态生成，不写死文案
    pts = _obs_points(hist, "红香葱")
    day_txt, move_txt, streak = "—", "样本不足，暂不给出方向判断", ""
    if len(pts) >= 2:
        a, b = pts[-2], pts[-1]
        d = round(b["price"] - a["price"], 2)
        if d > 0.005:
            day_txt = "温和回升"
        elif d < -0.005:
            day_txt = "延续下行"
        else:
            day_txt = "磨底企稳"
        move_txt = "最近采集日 {0} → {1}：{2} → {3} 元/kg".format(
            a["date"], b["date"], num(a["price"]), num(b["price"]))
        streak = "较上一采集日 " + (f"{d:+.2f} 元/kg" if abs(d) >= 0.005 else "持平")
    verdict = f"""
    <div class="ms"><b>今日判断：{day_txt}</b>
      {esc(move_txt)}；{esc(streak)}。
      红香葱产地中枢 <b>{num(today_center)}</b> 元/kg
      （{esc(ctx.get('price_source_label', '产地集散价'))}）。</div>"""

    # 3.2 模型路径：直接复用预测表的统计结果
    if rows:
        r3, rh, r90 = rows[0], rows[len(rows) // 2], rows[-1]
        path = f"""
      <div class="ms"><b>模型路径（红香葱中枢）</b>
        今日基准 <b>{num(today_center)}</b> →
        {esc(r3['label'])} <b>{num(r3['center'])}</b>（{r3['delta_pct']:+.1f}%） →
        {esc(rh['label'])} <b>{num(rh['center'])}</b>（{rh['delta_pct']:+.1f}%） →
        {esc(r90['label'])} <b>{num(r90['center'])}</b>（{r90['delta_pct']:+.1f}%）。
        远端区间 {num(r90['low'])} – {num(r90['high'])} 元/kg，
        置信度 {esc(r90['confidence'])}。<a class="see" href="#sec7-forecast">看预测表 →</a></div>"""
    else:
        path = ""

    # 3.3 天气驱动的量化统计
    wx = ctx.get("weather", {})
    win = wx.get("core", {}).get("windows", {}) or {}
    w1, h1 = win.get("w1", {}), win.get("h1", {})
    weather_card = f"""
      <div class="ms"><b>天气驱动（未来 1 周 / 半月）</b>
        一周累计降水 <b>{num(w1.get('precip_total'), 1)}</b> mm、雨日
        <b>{w1.get('rainy_days', '—')}</b> 天、大风 <b>{w1.get('gale_days', '—')}</b> 天，
        最大风速 <b>{num(w1.get('wind_max'), 1)}</b> km/h；
        半月累计降水 <b>{num(h1.get('precip_total'), 1)}</b> mm、雨日
        <b>{h1.get('rainy_days', '—')}</b> 天。
        <a class="see" href="#sec3-weather">看天气 →</a></div>"""

    # 3.4 长周期与季节性统计
    lt = ctx.get("longterm") or {}
    lt_card = ""
    if lt:
        w = lt.get("windows", [{}])[0]
        season = lt.get("season", {})
        try:
            cur_month = date.fromisoformat(str(ctx["today"])[:10]).month
        except (ValueError, TypeError):
            cur_month = datetime.now().month
        cur_idx = season.get(cur_month)
        pos = "旺季" if (cur_idx or 0) > 1.08 else ("淡季" if (cur_idx or 0) < 0.92 else "过渡窗口")
        lt_card = f"""
      <div class="ms"><b>长周期与季节性</b>
        近 12 个月 {esc(w.get('start_ym', '—'))}→{esc(w.get('end_ym', '—'))}：
        中枢 {num(w.get('start', 0))} → {num(w.get('end', 0))} 元/kg
        （{w.get('change_pct', 0):+.1f}%），年化波动 {w.get('vol', 0):.0f}%；
        当前 {cur_month} 月季节指数 {num(cur_idx, 2) if cur_idx else '—'}，处于<b>{pos}</b>。
        <a class="see" href="#sec2-longterm">看长周期 →</a></div>"""

    # 3.5 关键风险（直接引用结论模块）
    risk_card = ""
    risks = ctx.get("risks")
    if risks:
        risk_card = (
            '<div class="ms"><b>关键跟踪变量</b>'
            + "".join(f"<div class='legend'>· {esc(r)}</div>" for r in risks[:3])
            + f'<a class="see" href="#sec8-risks">看风险 →</a></div>')

    analysis_panel = f"""
    <div class="mini-sum">
      {verdict}{path}{weather_card}{lt_card}{risk_card}
    </div>"""

    return f"""
<div class="board">
  <div class="board-head">
    <div class="board-title">小香葱行情 · 盘口直览</div>
    <div class="board-meta">更新时间：{esc(data_date)} 数据（行情发布为 T-1）｜
      单位：元/kg（另注除外）｜ 红涨 <b>↑</b> / 绿跌 ↓</div>
  </div>
  <div class="board-tabs">
    <span class="bt active" onclick="bdTab(0,this)">产地行情</span>
    <span class="bt" onclick="bdTab(1,this)">全国行情</span>
    <span class="bt" onclick="bdTab(2,this)">行情解析</span>
  </div>
  <div class="board-panel active">
    {origin_panel}
  </div>
  <div class="board-panel">
    {national_panel}
  </div>
  <div class="board-panel">
    {analysis_panel}
  </div>
</div>
<script>
function bdTab(i, el){{
  var card = el.closest('.board');
  var tabs = card.querySelectorAll('.bt');
  var panels = card.querySelectorAll('.board-panel');
  tabs.forEach(function(t){{ t.classList.remove('active'); }});
  panels.forEach(function(p){{ p.classList.remove('active'); }});
  el.classList.add('active');
  panels[i].classList.add('active');
}}
</script>"""
def build_longterm_section(lt: dict, summary: str = "", conclusion=None) -> str:
    series = lt["series"]
    conclusion = conclusion or []
    concl_html = "".join(
        f'<li><strong>{esc(t)}</strong>——{esc(b)}</li>' for t, b in conclusion)

    # 锚点表
    a_rows = "".join(
        f'<tr><td>{esc(a["ym"])}</td><td class="num">{a["price"]:.2f}</td>'
        f'<td><span class="tag {"t-key" if a["kind"]=="obs" else "t-flat"}">'
        f'{"实测" if a["kind"]=="obs" else "推断"}</span></td>'
        f'<td>{esc(a["note"])}</td></tr>'
        for a in lt["anchors"])

    # 窗口统计表
    w_rows = []
    for w in lt["windows"]:
        cls = "up" if w["change_pct"] > 0 else ("down" if w["change_pct"] < 0 else "flat")
        w_rows.append(
            f'<tr><td><strong>{esc(w["label"])}</strong></td>'
            f'<td>{esc(w["start_ym"])} → {esc(w["end_ym"])}</td>'
            f'<td class="num">{w["start"]:.2f}</td><td class="num">{w["end"]:.2f}</td>'
            f'<td class="num {cls}">{w["change_pct"]:+.1f}%</td>'
            f'<td class="num {cls}">{w["cagr"]:+.1f}%</td>'
            f'<td class="num">{w["avg"]:.2f}</td>'
            f'<td class="num">{w["hi"]:.2f}<br><span style="color:#8a93a0">{esc(w["hi_ym"])}</span></td>'
            f'<td class="num">{w["lo"]:.2f}<br><span style="color:#8a93a0">{esc(w["lo_ym"])}</span></td>'
            f'<td class="num">{w["amplitude"]:.0f}%</td>'
            f'<td class="num">{w["vol"]:.0f}%</td></tr>')

    # 近 12 个月同比
    y_rows = "".join(
        f'<tr><td>{esc(y["ym"])}</td><td class="num">{y["price"]:.2f}</td>'
        f'<td class="num">{y["prev"]:.2f}</td>'
        f'<td class="num {"up" if y["yoy"]>0 else "down"}">{y["yoy"]:+.1f}%</td></tr>'
        for y in lt["yoy"])

    svg10 = svg_line(series, lt["anchors"], title="近十年香葱产地价走势")
    svg36 = svg_line(series, lt["anchors"], months=36, title="近 36 个月香葱产地价走势")
    svg_season_chart = svg_season()

    return f"""
  <p>{esc(summary)}</p>
  <h3>2.1 口径与数据质量说明</h3>
  <div class="note">
    <strong>口径：</strong>主序列为「云南泸西 / 滇中南产地香葱综合交易价」，单位元/公斤，
    通货（毛葱）口径。另给出「精品净葱」折算序列 = 主序列 × {lt['premium']:.2f}
    （折算系数据 2026-10 同期两组报价测算：通货 2.62 元/kg vs 精品红香葱 4.35 元/kg）。<br>
    <strong>样本量：</strong>月频 {len(series)} 个数据点（{esc(series[0]['ym'])} — {esc(series[-1]['ym'])}），
    其中实测锚点 {lt['obs_count']} 个、区间推断锚点 {lt['inf_count']} 个。<br>
    <strong>重建方法（可复算）：</strong>先用季节因子对锚点去季节化 → 去季节化水平做对数线性插值 → 再乘回季节因子。
    序列在锚点月份精确等于锚点值。<br>
    <strong>保留意见：</strong>推断锚点仅用于连接形态，不单独支撑趋势结论；
    2016—2019 年缺少产地直报数据，系由销区均价按 0.55 折算，置信度低；
    波动率为季节形态主导的重建值，实际现货波动略低于该数值。
  </div>
  <h3>2.2 锚点清单</h3>
  <table>
    <tr><th>年月</th><th>价格(元/kg)</th><th>类型</th><th>依据 / 来源</th></tr>
    {a_rows}
  </table>
  <h3>2.3 十年长周期走势（2016-10 — {esc(series[-1]['ym'])}）</h3>
  {svg10}
  <div class="legend">蓝色实线=通货毛葱；黄色虚线=精品净葱折算；红点=实测锚点；灰点=推断锚点。</div>
  <h3>2.4 近 36 个月走势</h3>
  {svg36}
  <h3>2.5 多周期窗口统计（12 / 24 / 36 / 60 / 120 个月）</h3>
  <table>
    <tr><th>窗口</th><th>起止</th><th>期初</th><th>期末</th><th>区间涨跌</th>
        <th>年化(CAGR)</th><th>均值</th><th>最高</th><th>最低</th><th>振幅</th><th>年化波动</th></tr>
    {''.join(w_rows)}
  </table>
  <div class="legend">年化波动率 = 月度对数收益率标准差 × √12。振幅 = 区间最高 / 最低 − 1。</div>
  <h3>2.6 近 12 个月逐月同比</h3>
  <table>
    <tr><th>年月</th><th>本期(元/kg)</th><th>上年同期(元/kg)</th><th>同比</th></tr>
    {y_rows}
  </table>
  <h3>2.7 季节性规律（月度季节指数）</h3>
  {svg_season_chart}
  <div class="legend">季节指数 = 该月价格 / 全年均价。&gt;1.08 为旺季（红），&lt;0.92 为淡季（绿）。
    香葱季节规律：春峰 4—5 月最高、冬旺 11—1 月次高（春节备货 + 北方产区退市后云南单极供给），
    夏谷 7—8 月最低。与第六章预测模型共用同一季节曲线（config.SEASONALITY）。</div>
  <h3>2.8 长周期结论</h3>
  <ul>{concl_html}</ul>
"""


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
    <div class="kpi"><div class="lab">红香葱·产地中枢</div><div class="val">{num(red['current'])}</div><div class="chg">元/公斤（滇中产区集散价）</div></div>
    <div class="kpi"><div class="lab">黑葱·产地中枢</div><div class="val">{num(blk['current'])}</div><div class="chg">元/公斤（滇中产区集散价）</div></div>
    <div class="kpi"><div class="lab">全国生效气象预警</div><div class="val">{d['total']}</div><div class="chg">条（中央气象台）</div></div>
    <div class="kpi"><div class="lab">未来7天产区降水</div><div class="val">{num(win.get('w1', {}).get('precip_total'), 1)}</div><div class="chg">mm · 雨日 {win.get('w1', {}).get('rainy_days', '—')} 天</div></div>
    """

    # ---- 长周期说明用到的节日与目标日（动态计算，避免写死后逐日失效）
    _rows = red.get("rows", [])
    tgt60 = _rows[4]["target_date"] if len(_rows) > 4 else "—"
    tgt90 = _rows[5]["target_date"] if len(_rows) > 5 else "—"
    # 2027 年春节（丁未羊年）= 2027-02-06，除夕 2027-02-05
    cny_label, cny_date, cny_eve = "2027 年春节", "2 月 6 日", "2 月 5 日"
    try:
        days_to_cny = (date(2027, 2, 6) - date.fromisoformat(tgt90)).days
    except (TypeError, ValueError):
        days_to_cny = "—"

    # ---- 预测总表
    # 表头 10 列：周期 | 目标日 | 红香葱区间 | 红香葱中枢 | 黑葱区间 | 黑葱中枢 |
    #             中枢涨跌(红葱) | 中枢涨跌(黑葱) | 区间半宽 | 方向/置信度
    # 每一行必须输出满 10 格，否则整行会左移错位。
    rows = []
    rows.append(f'<tr><td>当前基准</td><td>{today}</td>'
                f'<td class="num">—</td><td class="num">{num(red["current"])}</td>'
                f'<td class="num">—</td><td class="num">{num(blk["current"])}</td>'
                f'<td class="num">—</td><td class="num">—</td>'
                f'<td class="num">—</td>'
                f'<td><span class="tag t-flat">基准</span></td></tr>')
    for r, b in zip(red["rows"], blk["rows"]):
        tag_txt, tag_cls = direction_tag(r["delta_pct"])
        dcls = "up" if r["delta_pct"] > 0 else ("down" if r["delta_pct"] < 0 else "flat")
        bcls = "up" if b["delta_pct"] > 0 else ("down" if b["delta_pct"] < 0 else "flat")
        rows.append(
            f'<tr><td><strong>{esc(r["label"])}</strong></td><td>{esc(r["target_date"])}</td>'
            f'<td class="num">{num(r["low"])} – {num(r["high"])}</td>'
            f'<td class="num">{num(r["center"])}</td>'
            f'<td class="num">{num(b["low"])} – {num(b["high"])}</td>'
            f'<td class="num">{num(b["center"])}</td>'
            f'<td class="num {dcls}">{r["delta_pct"]:+.1f}%</td>'
            f'<td class="num {bcls}">{b["delta_pct"]:+.1f}%</td>'
            f'<td class="num">±{r["band_pct"]:.1f}%</td>'
            f'<td><span class="tag {tag_cls}">{tag_txt}</span>'
            f'<span class="tag">{esc(r["confidence"])}</span></td></tr>')

    forecast_table = f"""
    <table>
      <tr><th>周期</th><th>目标日</th><th>红香葱区间(元/kg)</th><th>红香葱中枢</th>
          <th>黑葱区间(元/kg)</th><th>黑葱中枢</th><th>红葱涨跌</th><th>黑葱涨跌</th>
          <th>区间半宽</th><th>方向/置信度</th></tr>
      {''.join(rows)}
    </table>"""

    # ---- 盘口直览（小程序样式，三页签）
    board_html = build_board(ctx)

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

    # ---- 长周期章节 + 预测路径图
    lt = ctx.get("longterm")
    longterm_section = (build_longterm_section(lt, ctx.get("longterm_summary", ""),
                                               ctx.get("longterm_conclusion"))
                        if lt else "<p>长周期数据不可用。</p>")
    from .longterm import svg_forecast_path
    svg_path = svg_forecast_path(red["current"], red["rows"]) if red.get("rows") else ""

    # 各档理由
    why_rows = "".join(
        f'<tr><td><strong>{esc(r["label"])}</strong></td><td>{esc(r["target_date"])}</td>'
        f'<td class="num">{r["delta_pct"]:+.1f}%</td>'
        f'<td>{esc("；".join(r["reasons"]))}</td>'
        f'<td><span class="tag">{esc(r["confidence"])}</span></td></tr>'
        for r in red["rows"])

    html_doc = f"""{page('全国香葱行情日报 · ' + today)}
<header>
  <h1>全国香葱行情日报 · 泸西专题</h1>
  <div class="meta">数据日期：{today}（{'一二三四五六日'[date.today().weekday()]}）｜
    覆盖周期：未来 3天 / 1周 / 半月 / 1月 / 2月 / 3月 ｜
    重点产区：云南·红河州·泸西县 ｜ 生成时间：{ctx['generated_at']}</div>
</header>

<div class="card">
  <h2 id="sec1-summary">一、核心结论速览<span class="en">Executive Summary</span></h2>
  <p>{esc(ctx['summary'])}</p>
  <div class="grid">{kpi}</div>
  {forecast_table}
  <div class="note"><strong>关键变量：</strong>{esc(ctx['key_variable'])}</div>
</div>

<div class="card">
  <h2 id="sec2-longterm">二、历史长周期行情回顾（12 / 24 / 36 / 60 / 120 个月）<span class="en">Long-term Review</span></h2>
  {longterm_section}
</div>

<div class="card">
  <h2 id="sec3-weather">三、全国天气与自然灾害<span class="en">Weather &amp; Disaster</span></h2>
  <h3>3.1 {esc(CORE_REGION['name'])}逐日预报（Open-Meteo，未来16天）</h3>
  {daily_table}
  <h3>3.2 窗口统计</h3>
  {window_table}
  <h3>3.3 全国主要观测点（未来7天）</h3>
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
  <h3>3.4 生效气象预警（中央气象台，共 {d['total']} 条）</h3>
  <p>{hazard_chips}</p>
  {disaster_table}
</div>

<div class="card">
  <h2>四、市面常见香葱种类<span class="en">Varieties</span></h2>
  <p>市售"香葱"在植物学上属百合科葱属，主要涵盖<strong>分葱、细香葱、胡葱（火葱/红葱）</strong>三类；
     在批发流通端则主要按<strong>根茎颜色 + 商品规格</strong>分成红香葱、黑葱、白葱（钢葱/铁杆葱）。</p>
  <h3>4.1 流通端商品分类（决定报价）</h3>
  <table>
    <tr><th>类型</th><th>特征</th><th>主要用途/流向</th></tr>
    {var_rows}
  </table>
  <h3>4.2 常见栽培品种</h3>
  <table>
    <tr><th>品种</th><th>特性</th><th>适种/主产区</th><th>参考亩产</th></tr>
    {cultivar_rows}
  </table>
</div>

<div class="card">
  <h2>五、全国香葱种植省份分布<span class="en">Production Map</span></h2>
  <p>全国已形成<strong>"云南为核心、两广为南翼、华东为加工带、川湘豫多点补充"</strong>的格局。</p>
  <table>
    <tr><th>省区</th><th>主产市县</th><th>规模（公开数据）</th><th>上市季节/定位</th></tr>
    {prov_rows}
  </table>
  <div class="note">口径提示：不同机构对小香葱的统计口径差异较大（有按"在田基地面积"、有按"复种面积/亩次"），
    上表以各地官方发布的基地面积与产量为准，不宜直接横向加总。</div>
</div>

<div class="card">
  <h2 id="sec6-market">六、全国行情分析与预测<span class="en">National Market</span></h2>
  <h3>6.1 盘口直览（产地行情 / 全国行情 / 行情解析）</h3>
  {board_html}
  <h3>6.2 供需逻辑</h3>
  <div class="split">
    <div><p><strong>供给端（压制项）</strong></p><ul>{''.join(f'<li>{esc(x)}</li>' for x in ctx['supply_press'])}</ul></div>
    <div><p><strong>潜在利多（触发项）</strong></p><ul>{''.join(f'<li>{esc(x)}</li>' for x in ctx['demand_trigger'])}</ul></div>
  </div>
  <h3>6.3 六档预测依据</h3>
  <table>
    <tr><th>周期</th><th>目标日</th><th>中枢涨跌</th><th>主要驱动因素</th><th>置信度</th></tr>
    {why_rows}
  </table>
  <p class="legend">价格模型：
    P(h) = P₀ × 季节性比 × (1 + 天气冲击 × 衰减系数) × (1 + 动量回归)
    × (1 + 超预报期气候态修正) × (1 + 节日备货脉冲)。<br>
    区间半宽随周期递增（3天 ±5.5% → 3月 ±16.5%），反映不确定性的时间累积；
    天气冲击按 1/(1+超出天数/45) 衰减，即近端降雨不会线性传导到远端；
    节日脉冲刻画月内临近节日的额外拉升，与月尺度季节性不重复计数。</p>
  <div class="note"><strong>长周期（2-3个月）特别说明：</strong>
    未来 2 月目标日 {tgt60} 落在冬至与元旦备货窗口；未来 3 月目标日 {tgt90}
    距 {cny_label}（{cny_date}，除夕 {cny_eve}）仅 {days_to_cny} 天，处于全年最强的节前备货窗口。
    该档位属<strong>情景推演</strong>而非精确预测，实盘需以临近的一个月档滚动修正为准，
    并重点跟踪厄尔尼诺峰值（预计 11 月前后）后冬季西南降水的实际兑现程度。</div>
</div>

<div class="card">
  <h2 id="sec7-luxi">七、{esc(CORE_REGION['name'])}专题<span class="en">Luxi County Focus</span></h2>
  <h3>7.1 产业底盘</h3>
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
  <h3 id="sec7-forecast">7.2 价格预测</h3>
  {forecast_table}
  <h3>7.3 预测路径图（精品净葱口径）</h3>
  {svg_path}
  <div class="legend">横轴按目标天数等距（0 / 3 / 7 / 15 / 30 / 60 / 90 天），
    绿虚线为中枢路径，浅绿带为各档区间上下限。</div>
  <h3>7.4 近期走势与预测示意</h3>
  {svg}
  <div class="legend">蓝线为实测成交中枢（产地综合交易价），绿虚线为模型预测中枢。</div>
  <h3>7.5 专项建议</h3>
  <ul>{''.join(f'<li>{esc(x)}</li>' for x in ctx['advice'])}</ul>
</div>

<div class="card">
  <h2 id="sec8-risks">八、风险提示与假设<span class="en">Risks &amp; Assumptions</span></h2>
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

    # 以磁盘上真实存在的报告为准回填索引：即便 archive.json 被旧版本覆盖、
    # 合并冲突丢失或手工误删，历史报告也不会从归档页消失（价格字段缺失时显示 —）。
    by_date: dict[str, dict] = {}
    for a in archive:
        d = a.get("date")
        if d:
            by_date[d] = a
    for name in os.listdir(OUTPUT_DIR):
        m = REPORT_NAME_RE.match(name)
        if not m:
            continue
        d = m.group(1)
        if d not in by_date:
            by_date[d] = {"date": d, "file": name, "red_current": None,
                          "black_current": None, "generated_at": ""}
        else:
            by_date[d]["file"] = name

    red_c = ctx["forecast"].get("红香葱", {}).get("current")
    blk_c = ctx["forecast"].get("黑葱", {}).get("current")
    by_date[today] = {
        "date": today,
        "file": fname,
        "red_current": red_c,
        "black_current": blk_c,
        "generated_at": ctx["generated_at"],
    }

    archive = sorted(by_date.values(), key=lambda x: x["date"], reverse=True)
    archive = archive[:ARCHIVE_KEEP_DAYS]
    with open(archive_path, "w", encoding="utf-8") as f:
        json.dump(archive, f, ensure_ascii=False, indent=2)

    idx = build_index(archive)
    with open(os.path.join(OUTPUT_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(idx)

    return {"file": fname, "path": path}
