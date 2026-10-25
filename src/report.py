# -*- coding: utf-8 -*-
"""HTML 报告生成：把天气、灾害、价格与静态知识库渲染为单页报告。"""

from __future__ import annotations

import html
import json
import os
import re
from collections.abc import Sequence
from datetime import date, datetime, timezone, timedelta

# 统一北京时间（UTC+8）：本地与 GitHub CI(UTC 服务器) 运行结果一致
BJ_TZ = timezone(timedelta(hours=8))
def bjnow():
    return datetime.now(BJ_TZ)

from .config import CORE_REGION, CULTIVARS, MODEL, PROVINCES, VARIETIES
from .longterm import svg_line, svg_season
from .price import direction_tag
from . import sources

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
/* ---- 盘口统计条 ---- */
.bars{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:10px;margin:10px 4px 2px;}
.bar{background:#f4f8fd;border:1px solid var(--line);border-radius:10px;padding:8px 14px;
  font-size:12.5px;display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 16px;}
.bar .bt2{font-weight:700;font-size:13px;color:var(--accent);}
.bar i{font-style:normal;color:var(--sub);}
.bar i b{color:var(--ink,#1a2733);font-size:14px;}
.bar i.up b{color:var(--up);}
.bar i.down b{color:var(--down);}
.bar i.k b{color:var(--accent);}
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
def _series_obs(hist: dict, variety: str) -> list[dict]:
    pts = [p for p in hist.get("series", [])
           if p["variety"] == variety and p.get("source") == "observed"]
    pts.sort(key=lambda p: p["date"])
    return pts


def _quote_find(quotes: list[dict], market_kw: str, item: str) -> dict | None:
    # 品名匹配做「香」字归一化：红香葱/红葱、黑香葱/黑葱 视为同一品类，
    # 避免产区改名或加「香」字后静默匹配失败（曾导致盘口整列变 —）。
    def norm(s: str) -> str:
        return s.replace("香", "").replace(" ", "")

    n_item = norm(item)
    for q in quotes:
        if market_kw in q.get("market", "") and n_item in norm(q.get("item", "")):
            return q
    return None


def _arrow(chg: float | None) -> str:
    if chg is None:
        return '<span class="arrow-flat">—</span>'
    if chg > 0.001:
        return '<span class="arrow-up">↑</span>'
    if chg < -0.001:
        return '<span class="arrow-down">↓</span>'
    return '<span class="arrow-flat">→</span>'


def _stat_bars(samples: list[dict], title: str) -> str:
    """盘口底部统计条：同口径涨跌家数 + 分口径中枢横截面。

    不同口径（集散净葱 / 全省综合 / 销区批发 / 产地毛葱）只分组罗列，
    不做跨口径平均——避免把口径差误当成行情波动。
    """
    if not samples:
        return ""
    cmp_ = [s for s in samples if s.get("chg") is not None]
    up = sum(1 for s in cmp_ if s["chg"] > 0.001)
    down = sum(1 for s in cmp_ if s["chg"] < -0.001)
    flat = len(cmp_) - up - down
    if cmp_:
        net = sum(s["chg"] for s in cmp_) / len(cmp_)
        net_cls = "up" if net > 0.001 else ("down" if net < -0.001 else "")
        net_txt = "0.00" if abs(net) < 0.005 else f"{net:+.2f}"
        move = (f'<i class="k">同口径可比 <b>{len(cmp_)}</b> 项</i>'
                f'<i class="up">涨 <b>{up}</b></i>'
                f'<i class="down">跌 <b>{down}</b></i>'
                f'<i>平 <b>{flat}</b></i>'
                f'<i>平均变动 <b class="{net_cls}">{net_txt}</b> 元/kg</i>')
    else:
        move = '<i class="k">本页签暂无跨日可比口径，涨跌项空缺</i>'
    groups: dict[str, list] = {}
    for s in samples:
        groups.setdefault(s.get("cal") or "未标注口径", []).append(s)
    g_html = "".join(
        f'<i>{esc(cal)}：' + " / ".join(
            f'{esc(it["name"])} <b>{it["mid"]:.2f}</b>' for it in items) + '</i>'
        for cal, items in groups.items())
    return f"""
    <div class="bars">
      <div class="bar"><span class="bt2">{esc(title)}</span>{move}</div>
      <div class="bar"><span class="bt2">分口径中枢（今日，元/kg）</span>{g_html}
        <i class="k">不同口径不可横比</i></div>
    </div>"""


def build_board(ctx: dict) -> str:
    """仿「小香葱行情」小程序的三页签盘口：产地行情 / 全国行情 / 行情解析。"""
    hist = ctx["history"]
    quotes = ctx.get("spot_quotes", [])
    data_date = ctx.get("data_date", ctx["today"])
    mkt = ctx.get("market_api") or {}

    red_pts = _series_obs(hist, "红香葱")
    blk_pts = _series_obs(hist, "黑葱")
    xcong_pts = _series_obs(hist, "小葱")

    def pair(pts):
        if len(pts) >= 2:
            return pts[-2]["price"], pts[-1]["price"]
        if len(pts) == 1:
            return None, pts[-1]["price"]
        return None, None

    red_prev, red_today = pair(red_pts)
    blk_prev, blk_today = pair(blk_pts)
    x_prev, x_today = pair(xcong_pts)

    # 基准口径为泸西产区（与模型基准一致）；若数据里改回「滇中」片区命名则自动回退
    q_red_local = _quote_find(quotes, "泸西", "红葱") or _quote_find(quotes, "滇中", "红葱") or {}
    q_blk_local = _quote_find(quotes, "泸西", "黑葱") or _quote_find(quotes, "滇中", "黑葱") or {}
    q_red_all = _quote_find(quotes, "云南产地综合", "红香葱") or {}
    q_blk_all = _quote_find(quotes, "云南产地综合", "黑葱") or {}
    q_wqy = _quote_find(quotes, "王旗营", "小葱") or {}

    def rng(v):
        return esc(v.get("range", "—")) if v else "—"

    def up_edge(v):
        try:
            return float(str(v.get("range", "")).split("-")[-1])
        except (ValueError, AttributeError):
            return None

    # 行：品名 | 区间 | 昨日 | 今日 | 涨跌 | 趋势 | 查看
    rows = []
    # 统计样本：仅收数值型今日价；cal 标注口径，不同口径不并入同一横截面
    samples = []

    def add(name, rg, prev, today, tag="", link="#sec6-forecast", note="", onclick=None,
            sname=None, cal=None, today_val=None):
        # today 为带单位字符串（如「2750 元/亩」）时，用 today_val 传裸数值以计算涨跌
        tv = today_val if today_val is not None else (
            None if isinstance(today, str) else today)
        chg = None
        if prev is not None and tv is not None:
            chg = round(tv - prev, 2)
        # 入统计：推算/模型/待接入行（cal=None 或非数值）不进样本，避免把推算值当报价
        if cal and today is not None and not isinstance(today, str):
            samples.append({"name": sname or name, "mid": float(today),
                            "chg": chg, "cal": cal})
        # 元/亩 等大额口径不显示小数，元/kg 保留两位
        if chg is None:
            chg_txt = "—"
        elif abs(chg) < 0.005:
            chg_txt = "0.00"
        elif abs(chg) >= 100:
            chg_txt = f"{chg:+.0f}"
        else:
            chg_txt = f"{chg:+.2f}"
        if prev is None:
            prev_txt = "—"
        elif abs(prev - round(prev)) < 0.005 and abs(prev) >= 100:
            prev_txt = str(int(round(prev)))
        else:
            prev_txt = num(prev)
        if today is None:
            today_txt = "暂无报价"
        elif isinstance(today, str):
            today_txt = esc(today)  # 已含单位（如「2620 元/吨」）
        else:
            today_txt = num(today)
        if tag == "待接入":
            chg_txt, arrow = "—", '<span class="arrow-flat">—</span>'
        else:
            arrow = _arrow(chg)
        tag_html = f'<span class="tag">{esc(tag)}</span>' if tag else ""
        note_html = f'<div class="legend">{esc(note)}</div>' if note else ""
        # onclick 为受信任的内部 JS，不经 esc 转义
        onclick_html = f' onclick="{onclick}"' if onclick else ""
        rows.append(
            f'<tr><td class="name">{esc(name)}{tag_html}{note_html}</td>'
            f'<td class="num">{esc(rg)}</td><td class="num">{prev_txt}</td>'
            f'<td class="num">{today_txt}</td><td class="num">{chg_txt}</td>'
            f'<td class="num">{arrow}</td>'
            f'<td><a class="see" href="{link}"{onclick_html}>查看</a></td></tr>')

    # 产地行情（泸西/滇中）——集散净葱为实测，A货为区间上沿推算；毛葱地头价另列（口径不同）
    add("红葱（泸西集散·净葱）", rng(q_red_local), red_prev, red_today,
        note="泸西产区集散成交均价（精品净葱口径），模型基准",
        sname="红葱", cal="泸西集散·净葱")
    add("红葱 A货（精品净葱）", rng(q_red_local), None, up_edge(q_red_local),
        tag="推算", note="取当日集散区间上沿，仅供结构参考")
    add("黑葱（泸西集散·净葱）", rng(q_blk_local), blk_prev, blk_today,
        note="泸西产区集散成交均价（净葱口径）", sname="黑葱", cal="泸西集散·净葱")
    add("黑葱 A货（中条）", None, None, up_edge(q_blk_local),
        tag="推算", note="取当日集散区间上沿")
    # 全省综合 + 主要销区
    add("红香葱（云南全省综合）", rng(q_red_all), None, q_red_all.get("mid"),
        sname="红香葱", cal="云南全省综合")
    add("黑葱（云南全省综合）", rng(q_blk_all), None, q_blk_all.get("mid"),
        sname="黑葱", cal="云南全省综合")
    add("小葱（昆明王旗营批发）", rng(q_wqy), x_prev, x_today,
        sname="小葱", cal="销区批发（王旗营）")
    # ---- 惠农网产地接口（泸西香葱真实报价）----
    cnhnb = (mkt.get("cnhnb") or {}).get("rows", [])
    lux_xi = sorted([r for r in cnhnb if "泸西" in r.get("origin", "") and r.get("item") == "香葱"],
                    key=lambda r: r["date"])
    lushi = lux_xi[-1] if lux_xi else None

    # 等级盘口 / 包地 / 期货盘 —— 真实数据源映射（禁止用推算冒充接口）
    if lushi:
        js = round(lushi["mid"] * 1.66, 2)
        add("红葱 包地价（泸西·毛葱）", f"{lushi['mid']} 元/kg", None,
            f"{int(lushi['ton'])} 元/吨",
            tag="接口", link="#sec6-spot", onclick="bdGo(1,'sec6-spot',this);return false;",
            note=f"惠农网产地接口·泸西香葱 {lushi['date']} 报价 {lushi['mid']}元/kg"
                 f"——地头通货毛葱口径；毛葱经加工去损折算集散净葱口径（×约1.66）"
                 f"≈ {js} 元/kg，与上行「滇中集散」衔接，两口径不可直接对比"
                 + ("；今日为缓存数据" if lushi.get("cached") else ""))
    else:
        add("红葱 包地价（泸西·毛葱）", "—", None, None, tag="待接入", link="#sec6-spot",
            note="惠农网产地接口暂不可用，待接入")
    # 红铁杆期货盘：全国无葱类期货合约与公开远期盘，取模型2个月远期中枢折算元/吨
    red_fc = ctx["forecast"].get("红香葱", {}).get("rows", [])
    red2 = red_fc[4]["center"] if len(red_fc) > 4 else None
    add("红铁杆 期货盘", "—", None,
        (f"{round(red2 * 1000)} 元/吨" if red2 else None), tag="模型",
        link="#sec6-forecast",
        note="全国无葱类期货合约与公开远期盘；取模型2个月远期中枢折算元/吨（情景推演，非成交价）")
    # 黑葱中条 A货（2吨）整车吨级批发盘：无公开接口，按泸西黑葱通货上沿×1000推算元/吨
    blk_up = up_edge(q_blk_local)
    add("黑葱中条 A货（2吨）", "—", None,
        (f"{round(blk_up * 1000)} 元/吨" if blk_up else None),
        tag="推算", link="#sec6-spot", onclick="bdGo(1,'sec6-spot',this);return false;",
        note="整车吨级批发盘无公开接口；按泸西黑葱集散上沿×1000 推算元/吨")

    # ---- 白葱（白铁杆）与包地价（元/亩）：云南产区报价单实测口径 ----
    def _qget(lst, item):
        hit = [q for q in lst if q.get("item") == item]
        return hit[-1] if hit else None

    wht = _qget(hist.get("white_quotes", []), "白铁杆（白葱）")
    if wht:
        add("白葱·白铁杆（云南产区）", rng(wht), wht.get("prev"), wht.get("mid"),
            tag="实测", link="#sec6-spot", onclick="bdGo(1,'sec6-spot',this);return false;",
            sname="白葱", cal="云南产区·白葱",
            note=f"产区报价单 {wht['date']}：{wht['range']} 元/kg（昨日 {wht.get('prev')}）。"
                 f"白葱与红/黑葱同季竞争，可作为香葱总供给的交叉验证")

    red_jp = _qget(hist.get("white_quotes", []), "红香葱（精品好货）")
    if red_jp:
        add("红香葱（精品好货）", rng(red_jp), red_jp.get("prev"), red_jp.get("mid"),
            tag="实测", link="#sec6-spot", onclick="bdGo(1,'sec6-spot',this);return false;",
            sname="红香葱", cal="云南产区·精品好货",
            note=f"产区报价单 {red_jp['date']}：{red_jp['range']} 元/kg（昨日 {red_jp.get('prev')}）。"
                 f"精品好货口径，高于全省综合交易价（{rng(q_red_all)}），反映优质优价价差")

    # 包地价按「元/亩」计价，不并入元/kg 横截面（cal=None 排除）
    for q in hist.get("mu_quotes", []):
        add(q["item"], rng(q), q.get("prev"), f"{int(q['mid'])} 元/亩",
            tag="实测", link="#sec6-spot", onclick="bdGo(1,'sec6-spot',this);return false;",
            today_val=q.get("mid"),
            note=f"包地（整片承包）口径 {q['date']}：{q['range']} 元/亩（昨日 {int(q.get('prev') or 0)}）。"
                 f"按亩计价，直接反映地头对后市的预期，领先于现货价变化")

    red = ctx["forecast"]["红香葱"]
    red_rows = red["rows"]
    r3, r90 = red_rows[0], red_rows[5]
    r_mid = red_rows[len(red_rows) // 2]
    base = red.get("current")

    # 今日判断：以最近一次采集变动为主、前一段走势为辅，动态生成，不写死文案
    verdict_txt, verdict_note = "磨底企稳", "样本不足，暂不给出方向判断"
    if len(red_pts) >= 2:
        d = round(red_pts[-1]["price"] - red_pts[-2]["price"], 2)
        d_prev = (round(red_pts[-2]["price"] - red_pts[-3]["price"], 2)
                  if len(red_pts) >= 3 else None)
        pdate = esc(red_pts[-2]["date"][5:])
        if abs(d) >= 0.001:
            verdict_txt = "延续上行" if d > 0 else "延续下行"
            verdict_note = f"较上一采集日（{pdate}）{d:+.2f} 元/kg"
        elif d_prev is not None and d_prev < -0.001:
            verdict_txt = "磨底企稳"
            verdict_note = (f"较上一采集日持平（前次下跌 {abs(d_prev):.2f} 元/kg 后止跌），"
                            "近端以稳为主")
        elif d_prev is not None and d_prev > 0.001:
            verdict_txt = "涨势暂缓"
            verdict_note = f"较上一采集日持平（前次 +{d_prev:.2f} 元/kg 后走平）"
        else:
            verdict_txt = "横盘整理"
            verdict_note = "连续两个采集日持平，方向不明"

    # 模型路径卡片：直接复算预测表统计
    path_card = f"""
      <div class="ms"><b>模型路径（红香葱中枢）</b>
        基准 <b>{num(base)}</b> → {esc(r3['label'])} <b>{num(r3['center'])}</b>（{r3['delta_pct']:+.1f}%）→
        {esc(r_mid['label'])} <b>{num(r_mid['center'])}</b>（{r_mid['delta_pct']:+.1f}%）→
        {esc(r90['label'])} <b>{num(r90['center'])}</b>（{r90['delta_pct']:+.1f}%）。
        远端区间 {num(r90['low'])}–{num(r90['high'])} 元/kg，置信度 {esc(r90['confidence'])}。
        <a class="see" href="#sec6-forecast">看预测表 →</a></div>"""

    # 天气驱动卡片：周/半月窗口统计
    _win = (ctx.get("weather", {}).get("core", {}).get("windows", {}) or {})
    w1, h1 = _win.get("w1", {}), _win.get("h1", {})
    weather_card = f"""
      <div class="ms"><b>天气驱动（未来 1 周 / 半月）</b>
        一周累计降水 <b>{num(w1.get('precip_total'), 1)}</b> mm、雨日
        <b>{w1.get('rainy_days', '—')}</b> 天、大风 <b>{w1.get('gale_days', '—')}</b> 天；
        半月累计降水 <b>{num(h1.get('precip_total'), 1)}</b> mm、雨日
        <b>{h1.get('rainy_days', '—')}</b> 天。
        <a class="see" href="#sec3-weather">看天气 →</a></div>"""

    # 长周期与季节性卡片
    lt = ctx.get("longterm") or {}
    lt_card = ""
    if lt:
        w0 = (lt.get("windows") or [{}])[0]
        season = lt.get("season", {}) or {}
        try:
            cur_month = date.fromisoformat(str(ctx["today"])[:10]).month
        except (ValueError, TypeError):
            cur_month = datetime.now().month
        cur_idx = season.get(cur_month)
        pos = "旺季" if (cur_idx or 0) > 1.08 else ("淡季" if (cur_idx or 0) < 0.92 else "过渡窗口")
        lt_card = f"""
      <div class="ms"><b>长周期与季节性</b>
        近 12 个月 {esc(w0.get('start_ym', '—'))}→{esc(w0.get('end_ym', '—'))}：
        中枢 {num(w0.get('start', 0))} → {num(w0.get('end', 0))} 元/kg
        （{w0.get('change_pct', 0):+.1f}%），年化波动 {w0.get('vol', 0):.0f}%；
        当前 {cur_month} 月季节指数 {num(cur_idx, 2) if cur_idx else '—'}，处于<b>{pos}</b>。
        <a class="see" href="#sec2-longterm">看长周期 →</a></div>"""

    # 关键跟踪变量卡片：直接引用风险结论模块
    risk_card = ""
    risks = ctx.get("risks")
    if risks:
        risk_card = ('<div class="ms"><b>关键跟踪变量</b>'
                     + "".join(f"<div class='legend'>· {esc(r[3])}</div>" for r in risks[:3])
                     + '<a class="see" href="#sec8-risks">看风险 →</a></div>')

    ms = f"""
    <div class="mini-sum">
      <div class="ms"><b>今日判断：{verdict_txt}</b>
        产区红葱（集散·净葱）{num(red_today)} 元/kg {esc(verdict_note)}。</div>
      <div class="ms"><b>近端（3天-半月）</b>
        中枢 {num(r3['center'])} → {num(red['rows'][2]['center'])} 元/kg，
        天气平稳、后市温和回升。</div>
      <div class="ms"><b>远端（1-3月）</b>
        冬旺 + 春节备货支撑，3 月目标日 {esc(r90['target_date'])} 情景中枢
        {num(r90['center'])} 元/kg（±{r90['band_pct']:.0f}%），属情景推演。</div>{path_card}{weather_card}{lt_card}{risk_card}
    </div>"""

    s_rows = []
    for q in quotes:
        s_rows.append(
            f'<tr><td>{esc(q["date"])}</td><td>{esc(q["market"])}</td>'
            f'<td>{esc(q["item"])}</td>'
            f'<td class="num">{esc(q["range"])}</td>'
            f'<td class="num">{num(q["mid"])}</td>'
            f'<td>{esc(q["note"])}</td></tr>')
    spot_panel = f"""
    <table id="sec6-spot">
      <tr><th>日期</th><th>市场/口径</th><th>品项</th><th>报价区间</th><th>中枢(元/kg)</th><th>说明</th></tr>
      {''.join(s_rows) or '<tr><td colspan="6">暂无数据</td></tr>'}
    </table>
    <div class="legend">口径提示：不同市场口径不可直接横比——「云南产地综合交易价」为全省加权综合价，
      高于单一产区集散报价；滇中产区报价为预测模型基准口径；北方销区「葱/大葱」多为大葱口径，仅作参照。</div>"""

    # ---- 接口自动行情（新发地）
    mkt = ctx.get("market_api") or {}
    # 全国行情页签统计样本：新发地销区批发 + 惠农网产地毛葱（分口径，不混算）
    n_samples = []
    api_rows = mkt.get("rows") or []
    for it in dict.fromkeys(r["item"] for r in api_rows):
        rows_it = sorted([r for r in api_rows if r["item"] == it],
                         key=lambda r: r["date"])
        if not rows_it:
            continue
        cur = rows_it[-1]
        chg = round(cur["mid"] - rows_it[-2]["mid"], 2) if len(rows_it) > 1 else None
        n_samples.append({"name": it, "mid": float(cur["mid"]), "chg": chg,
                          "cal": "销区批发（新发地）"})
    for r in ((mkt.get("cnhnb") or {}).get("rows") or []):
        org = (r.get("origin") or "")[-3:]
        nm = f'{r.get("item", "产地")}（{org}）' if org else r.get("item", "产地")
        n_samples.append({"name": nm, "mid": float(r.get("mid") or 0), "chg": None,
                          "cal": "产地毛葱（惠农网）"})
    api_html = ""
    if mkt.get("ok") and mkt.get("rows"):
        items = []
        for it in dict.fromkeys(r["item"] for r in mkt["rows"]):
            rows_it = sorted([r for r in mkt["rows"] if r["item"] == it],
                             key=lambda r: r["date"])
            cur, prev = rows_it[-1], (rows_it[-2] if len(rows_it) > 1 else None)
            chg = None
            if prev and cur:
                chg = round(cur["mid"] - prev["mid"], 2)
            chg_html = ("—" if chg is None else
                        ("0.00" if abs(chg) < 0.005 else f"{chg:+.2f}"))
            arrow = _arrow(chg)
            dcls = "up" if (chg or 0) > 0 else ("down" if (chg or 0) < 0 else "flat")
            items.append(
                f'<tr><td class="name">{esc(it)}<span class="tag">接口自动</span></td>'
                f'<td>{esc(cur["date"])}</td>'
                f'<td class="num">{num(cur["low"])} – {num(cur["high"])}</td>'
                f'<td class="num">{num(cur["mid"])}</td>'
                f'<td class="num {dcls}">{chg_html}</td>'
                f'<td class="num">{arrow}</td>'
                f'<td>{esc(cur["places"] or "—")}</td>'
                f'<td><a class="see" href="#sec6-spot">明细</a></td></tr>')
        api_html = f"""
    <p style="margin:10px 4px 0"><strong>接口自动行情 · {esc(mkt.get('market', '北京新发地'))}</strong>
      <span class="tag">抓取时间 {esc(mkt.get('fetched_at', ''))}</span></p>
    <table class="btab">
      <tr><th>品名</th><th>最新日期</th><th>区间(元/kg)</th><th>中枢</th>
          <th>较前日</th><th>趋势</th><th>产地</th><th>查看</th></tr>
      {''.join(items)}
    </table>
    <div class="legend">数据来源：新发地批发市场公开行情接口（原始单位元/斤，×2 换算为元/公斤）；
      每日运行自动抓取并归档至 data/market_quotes.json。</div>"""
        # 全量明细：抓取到的每一行都展示（不再只取每个品项的最新一条）
        det = sorted(mkt["rows"], key=lambda r: (r["date"], r["item"]), reverse=True)
        det_rows = "".join(
            f'<tr><td>{esc(r["date"])}</td><td class="name">{esc(r["item"])}</td>'
            f'<td class="num">{num(r["low"])} – {num(r["high"])}</td>'
            f'<td class="num">{num(r["mid"])}</td>'
            f'<td>{esc(r.get("places") or "—")}</td></tr>'
            for r in det)
        api_html += f"""
    <p style="margin:14px 4px 0"><strong>接口全部明细 · 共 {len(det)} 条</strong>
      <span class="tag">全量不截断</span></p>
    <table class="btab">
      <tr><th>日期</th><th>品名</th><th>区间(元/kg)</th><th>中枢</th><th>产地</th></tr>
      {det_rows}
    </table>
    <div class="legend">上表为本次抓取到的全部行情行（{len(det)} 条，按日期倒序），未做任何截断；
      上方汇总表仅取各品项最新一条用于看盘对比。</div>"""
    else:
        api_html = ('<div class="note">接口自动行情暂不可用（' + esc(mkt.get("error", "未知原因"))
                    + '），本页签仅展示人工录入数据。</div>')

    # ---- 惠农网产地行情（cnhnb.com）
    cnhnb = (mkt.get("cnhnb") or {})
    cnhnb_html = ""
    if cnhnb.get("ok") and cnhnb.get("rows"):
        crows = sorted(cnhnb["rows"], key=lambda r: (r["origin"], r["item"], r["date"]))
        body = "".join(
            f'<tr><td class="name">{esc(r["item"])}<span class="tag">惠农网</span></td>'
            f'<td>{esc(r["date"])}</td>'
            f'<td>{esc(r["origin"])}</td>'
            f'<td class="num">{num(r["mid"])}</td>'
            f'<td class="num">{num(r["ton"])}</td></tr>'
            for r in crows)
        cnhnb_html = f"""
    <p style="margin:10px 4px 0"><strong>接口自动行情 · 惠农网产地报价（云南产区）</strong>
      <span class="tag">抓取时间 {esc(cnhnb.get('fetched_at', ''))}</span>{'<span class="tag">缓存回退</span>' if cnhnb.get('cached') else ''}</p>
    <table class="btab">
      <tr><th>品名</th><th>日期</th><th>产地</th><th>元/公斤</th><th>元/吨</th></tr>
      {body}
    </table>
    <div class="legend">数据来源：惠农网（cnhnb.com）公开产地行情页，原始单位元/斤、×2 换算元/公斤、×2000 换算元/吨；
      覆盖云南泸西/宾川/弥渡等产区，每日运行自动抓取（接口限流时自动回退最近一次缓存，并保留原报价日期）。
      注意：产地挂牌为地头通货毛葱口径，与滇中集散净葱口径（×约1.66）不可直接对比。</div>"""
    else:
        cnhnb_html = ('<div class="note">惠农网产地接口暂不可用（'
                      + esc(cnhnb.get("error", "未知原因")) + '）。</div>')

    return f"""
<div class="board">
  <div class="board-head">
    <div class="board-title">小香葱行情 · 盘口直览</div>
    <div class="board-meta">更新时间：{esc(ctx['today'])}（北京时间）｜ 数据截至：{esc(data_date)}（行情发布为 T-1）｜
      单位：元/kg（另注除外）｜ 红涨 <b>↑</b> / 绿跌 ↓</div>
  </div>
  <div class="board-tabs">
    <span class="bt active" onclick="bdTab(0,this)">产地行情</span>
    <span class="bt" onclick="bdTab(1,this)">全国行情</span>
    <span class="bt" onclick="bdTab(2,this)">行情解析</span>
  </div>
  <div class="board-panel active">
    <table class="btab">
      <tr><th>品名</th><th>区间</th><th>昨日</th><th>今日</th><th>涨跌</th><th>趋势</th><th>查看</th></tr>
      {''.join(rows)}
    </table>
    {_stat_bars(samples, "产地涨跌家数")}
    <div class="legend">「推算」档取当日集散区间上沿，非实际成交；「接口」档为惠农网公开产地报价（地头通货毛葱口径，
      ×约1.66 折算集散净葱口径后才与上行集散价同口径）；「模型」档为价格预测中枢折算（非成交价）。
      红葱包地价取自惠农网泸西产地接口（元/吨），与下方「元/亩」包地价分属不同计价方式；
      黑葱A货吨盘按集散上沿推算；红铁杆期货盘无公开合约，取模型2个月远期中枢。
      白葱（白铁杆）与红/黑葱同季竞争，其走弱可作为香葱总供给宽松的交叉验证；
      「元/亩」包地价不并入上方元/kg 分口径横截面。</div>
  </div>
  <div class="board-panel">{api_html}{cnhnb_html}{_stat_bars(n_samples, "接口行情涨跌家数")}{spot_panel}</div>
  <div class="board-panel">{ms}</div>
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
function bdGo(i, anchor, el){{
  bdTab(i, el);
  var a = document.getElementById(anchor);
  if(a){{ a.scrollIntoView({{behavior:'smooth', block:'start'}}); }}
}}
</script>"""
def build_sources_section(src: dict) -> str:
    """多源行情汇总：各定时任务落盘到 data/sources/ 的行情数据，全量展示不截断。"""
    src = src or {}
    items = list(src.get("items") or [])
    if not items:
        return ('<div class="note">本期 data/sources/ 下暂无其他定时任务落盘的行情数据'
                '（目录为空，或文件日期超出汇总窗口）。各生成任务按统一 schema 写入'
                ' 任务名_YYYY-MM-DD.json 后，将在推送任务中全量汇总展示。</div>')

    head = (
        f'<div class="grid">'
        f'<div class="kpi"><div class="lab">接入任务</div>'
        f'<div class="val">{src.get("task_count", 0)}</div>'
        f'<div class="chg">个定时任务落盘</div></div>'
        f'<div class="kpi"><div class="lab">行情报价</div>'
        f'<div class="val">{src.get("total_quotes", 0)}</div>'
        f'<div class="chg">条 · 全量展示不截断</div></div>'
        f'<div class="kpi"><div class="lab">预测档位</div>'
        f'<div class="val">{src.get("total_forecasts", 0)}</div>'
        f'<div class="chg">条 · 各任务六档预测</div></div>'
        f'<div class="kpi"><div class="lab">汇总窗口</div>'
        f'<div class="val">{src.get("window_days", 3)} 天</div>'
        f'<div class="chg">扫描 {src.get("files_scanned", 0)} 个文件</div></div>'
        f'</div>')

    blocks: list[str] = []
    for it in items:
        qs = sorted(it["quotes"], key=lambda q: (q["date"], q["item"]), reverse=True)
        q_rows = "".join(
            f'<tr><td>{esc(q["date"])}</td><td class="name">{esc(q["item"])}</td>'
            f'<td>{esc(q["market"])}</td><td>{esc(q["province"])}</td>'
            f'<td>{esc(q["price_type"])}</td>'
            f'<td class="num">{num(q["low"])} – {num(q["high"])}</td>'
            f'<td class="num">{num(q["mid"])}</td><td>{esc(q["unit"])}</td>'
            f'<td>{esc(q["source"])}</td><td>{esc(q["note"])}</td></tr>'
            for q in qs)
        q_table = (
            '<table><tr><th>日期</th><th>品项</th><th>市场</th><th>省份</th>'
            '<th>口径</th><th>区间</th><th>中枢</th><th>单位</th>'
            '<th>来源</th><th>备注</th></tr>'
            + (q_rows or '<tr><td colspan="10">无报价明细</td></tr>') + '</table>')

        f_html = ""
        if it["forecasts"]:
            f_rows: list[str] = []
            for f in it["forecasts"]:
                dp = f["delta_pct"]
                d_txt = f"{dp:+.1f}%" if dp is not None else "—"
                f_rows.append(
                    f'<tr><td>{esc(f["horizon"])}</td><td>{esc(f["target_date"])}</td>'
                    f'<td>{esc(f["item"])}</td><td class="num">{num(f["center"])}</td>'
                    f'<td class="num">{num(f["low"])} – {num(f["high"])}</td>'
                    f'<td class="num">{d_txt}</td>'
                    f'<td>{esc(f["confidence"])}</td></tr>')
            f_html = (
                '<table><tr><th>周期</th><th>目标日</th><th>品项</th>'
                '<th>中枢(元/kg)</th><th>区间</th><th>涨跌</th><th>置信度</th></tr>'
                + "".join(f_rows) + '</table>')

        blocks.append(
            f'<h3>{esc(it["task"])}'
            f'<span class="tag">数据日 {esc(it["date"])}</span>'
            f'<span class="tag">{esc(it["market_scope"])}</span>'
            f'<span class="tag">报价 {len(it["quotes"])} 条</span></h3>'
            + (f'<p>{esc(it["summary"])}</p>' if it["summary"] else "")
            + q_table + f_html)
    return head + "".join(blocks)


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
    <div class="kpi"><div class="lab">红香葱·产地中枢</div><div class="val">{num(red['current'])}</div><div class="chg">元/公斤（泸西产区集散价）</div></div>
    <div class="kpi"><div class="lab">黑葱·产地中枢</div><div class="val">{num(blk['current'])}</div><div class="chg">元/公斤（泸西产区集散价）</div></div>
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
          <th>黑葱区间(元/kg)</th><th>黑葱中枢</th><th>中枢涨跌(红葱)</th>
          <th>中枢涨跌(黑葱)</th><th>区间半宽</th><th>方向/置信度</th></tr>
      {''.join(rows)}
    </table>"""

    # ---- 盘口直览（小程序样式，三页签）
    board_html = build_board(ctx)

    # ---- 多任务行情汇总（其余定时任务落盘到 data/sources/ 的全量数据）
    sources_section = build_sources_section(ctx.get("sources"))

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
  <div class="meta">数据日期：{today}（{'一二三四五六日'[bjnow().date().weekday()]}）｜
    覆盖周期：未来 3天 / 1周 / 半月 / 1月 / 2月 / 3月 ｜
    重点产区：云南·红河州·泸西县 ｜ 生成时间：{ctx['generated_at']}</div>
</header>

<div class="card">
  <h2>一、核心结论速览<span class="en">Executive Summary</span></h2>
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
  <h2>六、全国行情分析与预测<span class="en">National Market</span></h2>
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
  <h2>七、{esc(CORE_REGION['name'])}专题<span class="en">Luxi County Focus</span></h2>
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
  <h3 id="sec6-forecast">7.2 价格预测</h3>
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

<div class="card">
  <h2 id="sec9-sources">九、多源行情汇总 · 全部定时任务<span class="en">All Sources</span></h2>
  <p>本节汇总其余香葱行情定时任务落盘到 <code>data/sources/</code> 的全部数据，按任务分组、
     <strong>全量展示、不做截断</strong>，与本仓库流水线数据一并推送到 GitHub。</p>
  {sources_section}
  <div class="legend">口径提示：各任务的报价口径（地头价 / 收购价 / 销地批发价 / 零售价）与单位可能不同，
    跨任务横向比较前请先核对「口径」与「单位」两列；不同口径不可直接横比。</div>
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


def build_sources_page(src: dict, today: str) -> str:
    """独立页：多源行情汇总全量总览（供 GitHub Pages 直接访问）。"""
    body = build_sources_section(src)
    return f"""{page('多源行情汇总 · 全部定时任务 · ' + today)}
<header>
  <h1>多源行情汇总 · 全部定时任务</h1>
  <div class="meta">数据日期：{esc(today)}（北京时间）｜ 数据源：data/sources/*.json ｜
    全量展示、不截断 ｜ <a class="back" href="index.html">← 返回报告归档</a></div>
</header>
<div class="card">
  <h2>全部定时任务行情明细<span class="en">All Sources</span></h2>
  <p>本节汇总其余香葱行情定时任务落盘到 <code>data/sources/</code> 的全部数据，按任务分组、
     <strong>全量展示、不做截断</strong>。</p>
  {body}
  <div class="legend">口径提示：不同任务的报价口径与单位可能不同，横向比较前请先核对
    「口径」与「单位」两列；不同口径不可直接横比。</div>
</div>
<footer>自动化生成 · 由多个香葱行情定时任务落盘、日报流水线汇总并推送到 GitHub</footer>
</div>
</body>
</html>
"""


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
  <p><a class="back" href="sources.html">→ 多源行情汇总 · 全部定时任务（全量明细）</a></p>
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

    # sources.html（多源行情汇总独立页，Pages 上可直接访问全量明细）
    try:
        with open(os.path.join(OUTPUT_DIR, "sources.html"), "w", encoding="utf-8") as f:
            f.write(build_sources_page(ctx.get("sources") or {}, today))
    except Exception:  # noqa: BLE001
        pass  # 汇总页失败不影响主报告

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
        # 全量行情：新发地抓取到的每一行明细（不截断）
        "market_rows": (ctx.get("market_api") or {}).get("rows") or [],
        # 其余定时任务落盘的行情汇总
        "sources": ctx.get("sources") or {},
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
