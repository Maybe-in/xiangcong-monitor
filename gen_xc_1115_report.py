# -*- coding: utf-8 -*-
"""香葱行情分析 · 2026-11-15 报告生成（八章 / 多 SVG 图表），读取 xiangcong_2026-11-15.json。"""
import json, os, sys
from collections import defaultdict, Counter
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(BASE, "data", "sources")
DATA = os.path.join(BASE, "data")
OUT = os.path.join(BASE, "outputs")
D = json.load(open(os.path.join(SRC, "xiangcong_2026-11-15.json"), encoding="utf-8"))
TODAY = D["date"]
GEN = D["generated_at"]
CUR_RED = 3.65
CUR_BLK = 2.76

# ---------------- 数据准备 ----------------
# A. 泸西 红香葱 近20日（取每日最大 mid 代表官方均价标签）
red_map = {}
for q in D["quotes"]:
    m = q.get("mid")
    if not m:
        continue
    mk = q.get("market", "")
    vr = (q.get("variety", "") + q.get("item", ""))
    if "泸西" in mk and "红" in vr and "葱" in vr:
        d = q["date"]
        red_map[d] = max(red_map.get(d, 0), m)
red_series = sorted(red_map.items())[-20:]
red_series = [(d[5:], v) for d, v in red_series]
if ("11-15", CUR_RED) not in red_series:
    red_series.append(("11-15", CUR_RED))
red_series = sorted(red_series)

# B. 五年同期（11月中旬，泸西 红香葱 元/公斤）
yoy = [("2022", 4.95), ("2023", 4.35), ("2024", 7.05), ("2025", 6.25), ("2026", CUR_RED)]

# C. 价格结构对比
struct = [
    ("泸西产地红香葱", CUR_RED), ("全国28种蔬菜", 4.07), ("南大堡云南香葱", 4.20),
    ("郑州万邦云南通货", 4.00), ("王旗营销地小葱", 3.00), ("辽宁朝阳销地小葱", 1.70),
]

# D. 六档预测（红香葱）
order = ["未来3天", "未来7天", "未来15天", "未来1个月", "未来2个月", "未来3个月"]
fc = sorted(D["forecasts"], key=lambda f: order.index(f["horizon"]))

# E. 天气 14 天
wx = json.load(open(os.path.join(DATA, "weather_2026-11-15.json"), encoding="utf-8"))
wdays = wx["core"]["daily"][:14]
weather = []
for d in wdays:
    lab = d["date"][5:].replace("-", "/")
    weather.append((lab, d.get("weather", ""), d.get("tmax"), d.get("tmin"), (d.get("precip") or 0) >= 1))

# F. 长周期（通货毛葱，src.longterm）
try:
    from src import longterm
    lt = longterm.build_longterm()
    series = lt["series"]
    windows = {w["months"]: w for w in lt["windows"]}
    LONG_OK = True
except Exception:
    series, windows, LONG_OK = [], {}, False

# G. 品种 / 省份 统计（口径：mid>0 的成交/挂牌价行）
var_counter = Counter()
prov_counter = Counter()
for q in D["quotes"]:
    m = q.get("mid")
    if not m:
        continue
    vr = q.get("variety", "") or q.get("item", "")
    vr = vr.replace("（", " ").replace("）", " ").replace("(", " ").replace(")", " ").strip()
    vr0 = vr.split()[0] if vr.split() else vr
    var_counter[vr0] += 1
    pv = q.get("province", "")
    if pv and pv != "全国":
        prov_counter[pv] += 1
top_var = var_counter.most_common(12)
top_prov = prov_counter.most_common(15)

# ---------------- SVG 辅助 ----------------
def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def line_chart(series, w=720, h=300, title="", ymax=None, ymin=0.0, show_every=1, cost=None):
    pl, pr, pt, pb = 56, 20, 40, 46
    iw, ih = w - pl - pr, h - pt - pb
    vals = [v for _, v in series]
    if ymax is None:
        ymax = (max(vals) * 1.15) if vals else 8
    n = len(series)
    def x(i): return pl + (iw * i / (n - 1)) if n > 1 else pl + iw / 2
    def y(v): return pt + ih * (1 - (v - ymin) / (ymax - ymin))
    p = ['<svg viewBox="0 0 %d %d" xmlns="http://www.w3.org/2000/svg" font-family="-apple-system,Segoe UI,Microsoft YaHei,sans-serif">' % (w, h)]
    p.append('<rect width="%d" height="%d" fill="#ffffff"/>' % (w, h))
    p.append('<text x="%d" y="22" font-size="15" font-weight="700" fill="#1a2b4a">%s</text>' % (pl, esc(title)))
    for g in range(0, 9):
        gv = ymin + (ymax - ymin) * g / 8
        gy = y(gv)
        p.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#eef1f6"/>' % (pl, gy, w - pr, gy))
        p.append('<text x="%d" y="%d" font-size="10" fill="#8a96a8" text-anchor="end">%.1f</text>' % (pl - 6, gy + 4, gv))
    if cost is not None:
        cy = y(cost)
        p.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#e0533d" stroke-width="1.2" stroke-dasharray="5 4"/>' % (pl, cy, w - pr, cy))
        p.append('<text x="%d" y="%d" font-size="10" fill="#e0533d" text-anchor="end">成本线 %.1f</text>' % (w - pr, cy - 4, cost))
    pts = [(x(i), y(v)) for i, (_, v) in enumerate(series)]
    area = "M%d %d " % (pts[0][0], y(ymin)) + " ".join("L%d %d" % (px, py) for px, py in pts) + " L%d %d Z" % (pts[-1][0], y(ymin))
    p.append('<path d="%s" fill="#2f6df0" opacity="0.10"/>' % area)
    p.append('<path d="M' + " L".join("%d %d" % (px, py) for px, py in pts) + '" fill="none" stroke="#2f6df0" stroke-width="2.4"/>')
    for i, (lab, v) in enumerate(series):
        p.append('<circle cx="%d" cy="%d" r="3" fill="#2f6df0"/>' % (pts[i][0], pts[i][1]))
        if i % show_every == 0 or i == n - 1:
            p.append('<text x="%d" y="%d" font-size="9.5" fill="#2f6df0" text-anchor="middle">%.2f</text>' % (pts[i][0], pts[i][1] - 8, v))
            p.append('<text x="%d" y="%d" font-size="9" fill="#6b7686" text-anchor="middle" transform="rotate(-35 %d %d)">%s</text>' % (pts[i][0], h - pb + 18, pts[i][0], h - pb + 18, esc(lab)))
    p.append('</svg>')
    return "".join(p)

def bar_chart(pairs, w=720, h=300, title="", color="#2f6df0", ymax=None, unit="元/公斤"):
    pl, pr, pt, pb = 64, 20, 40, 56
    iw, ih = w - pl - pr, h - pt - pb
    vals = [v for _, v in pairs]
    if ymax is None:
        ymax = max(vals) * 1.18 if vals else 8
    n = len(pairs); bw = iw / n * 0.62; gap = iw / n
    def y(v): return pt + ih * (1 - v / ymax)
    p = ['<svg viewBox="0 0 %d %d" xmlns="http://www.w3.org/2000/svg" font-family="-apple-system,Segoe UI,Microsoft YaHei,sans-serif">' % (w, h)]
    p.append('<rect width="%d" height="%d" fill="#ffffff"/>' % (w, h))
    p.append('<text x="%d" y="22" font-size="15" font-weight="700" fill="#1a2b4a">%s</text>' % (pl, esc(title)))
    for g in range(0, 5):
        gv = ymax * g / 4; gy = y(gv)
        p.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#eef1f6"/>' % (pl, gy, w - pr, gy))
        p.append('<text x="%d" y="%d" font-size="10" fill="#8a96a8" text-anchor="end">%.1f</text>' % (pl - 6, gy + 4, gv))
    for i, (lab, v) in enumerate(pairs):
        bx = pl + gap * i + (gap - bw) / 2; by = y(v); bh = ih - (by - pt)
        p.append('<rect x="%d" y="%d" width="%d" height="%d" rx="3" fill="%s"/>' % (bx, by, bw, max(bh, 2), color))
        p.append('<text x="%d" y="%d" font-size="11" fill="#1a2b4a" text-anchor="middle" font-weight="600">%.2f</text>' % (bx + bw / 2, by - 6, v))
        p.append('<text x="%d" y="%d" font-size="10.5" fill="#6b7686" text-anchor="middle">%s</text>' % (bx + bw / 2, h - 18, esc(lab)))
    p.append('<text x="%d" y="%d" font-size="9.5" fill="#9aa5b4" text-anchor="end">%s</text>' % (w - pr, h - 4, unit))
    p.append('</svg>')
    return "".join(p)

def fan_chart(fc, w=720, h=300, title=""):
    pl, pr, pt, pb = 56, 20, 40, 50
    iw, ih = w - pl - pr, h - pt - pb
    ymax = max(f["high"] for f in fc) * 1.1; ymin = 0
    n = len(fc)
    def x(i): return pl + iw * (i / (n - 1)) if n > 1 else pl + iw / 2
    def y(v): return pt + ih * (1 - (v - ymin) / (ymax - ymin))
    p = ['<svg viewBox="0 0 %d %d" xmlns="http://www.w3.org/2000/svg" font-family="-apple-system,Segoe UI,Microsoft YaHei,sans-serif">' % (w, h)]
    p.append('<rect width="%d" height="%d" fill="#ffffff"/>' % (w, h))
    p.append('<text x="%d" y="22" font-size="15" font-weight="700" fill="#1a2b4a">%s</text>' % (pl, esc(title)))
    for g in range(0, 5):
        gv = ymax * g / 4; gy = y(gv)
        p.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#eef1f6"/>' % (pl, gy, w - pr, gy))
        p.append('<text x="%d" y="%d" font-size="10" fill="#8a96a8" text-anchor="end">%.1f</text>' % (pl - 6, gy + 4, gv))
    up = [(x(i), y(f["high"])) for i, f in enumerate(fc)]
    lo = [(x(i), y(f["low"])) for i, f in enumerate(fc)]
    band = "M" + " L".join("%d %d" % t for t in up) + " L" + " L".join("%d %d" % t for t in reversed(lo)) + " Z"
    p.append('<path d="%s" fill="#2f6df0" opacity="0.13"/>' % band)
    cp = [(x(i), y(f["center"])) for i, f in enumerate(fc)]
    p.append('<path d="M' + " L".join("%d %d" % t for t in cp) + '" fill="none" stroke="#2f6df0" stroke-width="2.6"/>')
    for i, f in enumerate(fc):
        p.append('<circle cx="%d" cy="%d" r="3.4" fill="#2f6df0"/>' % (cp[i][0], cp[i][1]))
        p.append('<text x="%d" y="%d" font-size="10.5" fill="#1a2b4a" text-anchor="middle" font-weight="600">%.2f</text>' % (cp[i][0], cp[i][1] - 9, f["center"]))
        p.append('<text x="%d" y="%d" font-size="10" fill="#6b7686" text-anchor="middle">%s</text>' % (cp[i][0], h - 28, esc(f["horizon"].replace("未来", ""))))
        p.append('<text x="%d" y="%d" font-size="9" fill="#9aa5b4" text-anchor="middle">%s</text>' % (cp[i][0], h - 14, esc(f["target_date"][5:])))
    p.append('</svg>')
    return "".join(p)

def timeline_chart(weather, w=720, h=300, title=""):
    pl, pr, pt, pb = 30, 14, 40, 50
    iw, ih = w - pl - pr, h - pt - pb
    tmax, tmin = 28, 4
    n = len(weather)
    def x(i): return pl + iw * (i + 0.5) / n
    def y(v): return pt + ih * (1 - (v - tmin) / (tmax - tmin))
    p = ['<svg viewBox="0 0 %d %d" xmlns="http://www.w3.org/2000/svg" font-family="-apple-system,Segoe UI,Microsoft YaHei,sans-serif">' % (w, h)]
    p.append('<rect width="%d" height="%d" fill="#ffffff"/>' % (w, h))
    p.append('<text x="%d" y="22" font-size="15" font-weight="700" fill="#1a2b4a">%s</text>' % (pl, esc(title)))
    for i, (lab, desc, hi, lo, rain) in enumerate(weather):
        cx = x(i); col = "#3b82c4" if rain else "#9aaab8"
        bw = iw / n * 0.56; bx = cx - bw / 2; by = y(hi); bh = max(y(lo) - by, 2)
        p.append('<rect x="%d" y="%d" width="%d" height="%d" rx="3" fill="%s" opacity="0.85"/>' % (bx, by, bw, bh, col))
        p.append('<text x="%d" y="%d" font-size="10" fill="#1a2b4a" text-anchor="middle" font-weight="600">%d°</text>' % (cx, by - 5, hi))
        p.append('<text x="%d" y="%d" font-size="9.5" fill="#6b7686" text-anchor="middle">%s</text>' % (cx, h - 22, lab))
        p.append('<text x="%d" y="%d" font-size="8" fill="#9aa5b4" text-anchor="middle">%s</text>' % (cx, h - 8, esc(desc[:4])))
    p.append('<rect x="%d" y="%d" width="10" height="10" fill="#3b82c4"/><text x="%d" y="%d" font-size="9.5" fill="#6b7686">有降水</text>' % (pl, pt - 12, pl + 14, pt - 3))
    p.append('<rect x="%d" y="%d" width="10" height="10" fill="#9aaab8"/><text x="%d" y="%d" font-size="9.5" fill="#6b7686">无降水</text>' % (pl + 64, pt - 12, pl + 78, pt - 3))
    p.append('</svg>')
    return "".join(p)

# ---------------- 组装图表 ----------------
chartA = line_chart(red_series, title="泸西 红香葱 产地收购价 · 近20日走势（元/公斤）", ymax=8, cost=5.0, show_every=1)
chartB = bar_chart(yoy, title="泸西 红香葱 · 五年同期（11月中旬）对比（元/公斤）", color="#e0533d")
chartC = bar_chart(struct, title="价格结构对比 · 泸西产地 vs 全国/销地（元/公斤）", color="#2f6df0")
chartD = fan_chart(fc, title="泸西 红香葱 未来三个月预测区间（元/公斤）")
chartE = timeline_chart(weather, title="泸西 未来14天天气时间线（最高温·蓝=有降水）")
long_series = [(s["ym"], s["price"]) for s in series] if LONG_OK else []
chartF = line_chart(long_series, title="全国香葱 十年月频走势（通货毛葱·元/公斤·模型重建）", ymax=9, show_every=10) if LONG_OK else ""
chartG = bar_chart(top_var, title="常见香葱种类出现频次（采集样本）", color="#2f6df0", unit="条") if top_var else ""
chartH = bar_chart([(k, v) for k, v in top_prov], title="全国香葱报价省份覆盖 Top15（采集样本）", color="#3aa76d", unit="条") if top_prov else ""

# 窗口统计表（长周期）
win_rows = ""
if LONG_OK:
    for mo in (12, 24, 36, 60, 120):
        w = windows.get(mo)
        if not w:
            continue
        win_rows += ("<tr><td style='padding:5px 8px;border:1px solid #e3e8ef'>%s</td>"
                     "<td style='padding:5px 8px;border:1px solid #e3e8ef;text-align:center;color:%s;font-weight:600'>%+.1f%%</td>"
                     "<td style='padding:5px 8px;border:1px solid #e3e8ef;text-align:center'>%+.1f%%</td>"
                     "<td style='padding:5px 8px;border:1px solid #e3e8ef;text-align:center'>%.2f</td>"
                     "<td style='padding:5px 8px;border:1px solid #e3e8ef;text-align:center'>%.2f~%.2f</td>"
                     "<td style='padding:5px 8px;border:1px solid #e3e8ef;text-align:center'>%.1f%%</td></tr>" %
                     (w["label"], "#e0533d" if w["change_pct"] < 0 else "#2e8b57", w["change_pct"], w["cagr"],
                      w["avg"], w["lo"], w["hi"], w["amplitude"]))

# 预测表
fc_rows = ""
for f in fc:
    fc_rows += ("<tr><td style='padding:5px 8px;border:1px solid #e3e8ef'>%s</td>"
                "<td style='padding:5px 8px;border:1px solid #e3e8ef;text-align:center'>%s</td>"
                "<td style='padding:5px 8px;border:1px solid #e3e8ef;text-align:center;font-weight:600'>%.2f</td>"
                "<td style='padding:5px 8px;border:1px solid #e3e8ef;text-align:center'>%.2f~%.2f</td>"
                "<td style='padding:5px 8px;border:1px solid #e3e8ef;text-align:center;color:%s;font-weight:600'>%+.1f%%</td>"
                "<td style='padding:5px 8px;border:1px solid #e3e8ef;text-align:center'>%s</td></tr>" %
                (f["horizon"], f["target_date"], f["center"], f["low"], f["high"],
                 "#2e8b57" if f["delta_pct"] >= 0 else "#e0533d", f["delta_pct"], f["confidence"]))

# 品种表
var_rows = ""
for k, v in top_var:
    var_rows += "<tr><td style='padding:4px 8px;border:1px solid #e3e8ef'>%s</td><td style='padding:4px 8px;border:1px solid #e3e8ef;text-align:center'>%d</td></tr>" % (esc(k), v)
# 省份表
prov_rows = ""
for k, v in top_prov:
    prov_rows += "<tr><td style='padding:4px 8px;border:1px solid #e3e8ef'>%s</td><td style='padding:4px 8px;border:1px solid #e3e8ef;text-align:center'>%d</td></tr>" % (esc(k), v)

# 风险表
risk_html = ("<table style='border-collapse:collapse;width:100%;font-size:13px'>"
    "<tr style='background:#f3f6fb'><th style='padding:6px 8px;border:1px solid #e3e8ef'>分项</th><th style='padding:6px 8px;border:1px solid #e3e8ef'>等级</th><th style='padding:6px 8px;border:1px solid #e3e8ef'>说明</th></tr>"
    "<tr><td style='padding:6px 8px;border:1px solid #e3e8ef'>价格</td><td style='padding:6px 8px;border:1px solid #e3e8ef;color:#e0533d;font-weight:700'>高</td><td style='padding:6px 8px;border:1px solid #e3e8ef'>红 3.65 低于 5.0 成本线 27%、黑 2.76 低 46%；11-14 上破后仍处低位</td></tr>"
    "<tr><td style='padding:6px 8px;border:1px solid #e3e8ef'>需求侧</td><td style='padding:6px 8px;border:1px solid #e3e8ef;color:#e0533d;font-weight:700'>高</td><td style='padding:6px 8px;border:1px solid #e3e8ef'>王旗营小葱 3.00 横盘、销地未跟涨、全国小葱低位、B2B 挂牌「大掉价」</td></tr>"
    "<tr><td style='padding:6px 8px;border:1px solid #e3e8ef'>天气/生产</td><td style='padding:6px 8px;border:1px solid #e3e8ef;color:#d98a00;font-weight:700'>中-高</td><td style='padding:6px 8px;border:1px solid #e3e8ef'>11/14-18 两股冷空气（北方退市利多）；泸西晴、无霜冻、本地无直接影响</td></tr>"
    "<tr><td style='padding:6px 8px;border:1px solid #e3e8ef'>低温霜冻</td><td style='padding:6px 8px;border:1px solid #e3e8ef;color:#2e8b57;font-weight:700'>低</td><td style='padding:6px 8px;border:1px solid #e3e8ef'>全程最低 >0℃，无霜冻风险</td></tr>"
    "<tr><td style='padding:6px 8px;border:1px solid #e3e8ef'>流通传导</td><td style='padding:6px 8px;border:1px solid #e3e8ef;color:#d98a00;font-weight:700'>中-高</td><td style='padding:6px 8px;border:1px solid #e3e8ef'>国资云农洗选出货价断更（推算统货 4.6）、挂牌-成交价差历史最宽</td></tr>"
    "<tr style='background:#fff4f2'><td style='padding:6px 8px;border:1px solid #e3e8ef;font-weight:700'>综合</td><td style='padding:6px 8px;border:1px solid #e3e8ef;color:#e0533d;font-weight:800;font-size:15px'>高</td><td style='padding:6px 8px;border:1px solid #e3e8ef'>价格+需求侧双高主导（连续第 21 期）</td></tr>"
    "</table>")

HTML = r"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>香葱行情分析（云南泸西县）· __TODAY__</title>
<style>
 body{font-family:-apple-system,Segoe UI,Microsoft YaHei,sans-serif;background:#f5f7fa;color:#1f2a3a;margin:0;padding:24px;line-height:1.7}
 .wrap{max-width:920px;margin:0 auto;background:#fff;border-radius:12px;padding:28px 30px;box-shadow:0 2px 14px rgba(0,0,0,.06)}
 h1{font-size:24px;color:#16315e;margin:0 0 4px}
 .sub{color:#6b7686;font-size:13px;margin-bottom:18px}
 h2{font-size:18px;color:#16315e;border-left:4px solid #2f6df0;padding-left:10px;margin:26px 0 10px}
 .card{background:#f8fafd;border:1px solid #e3e8ef;border-radius:10px;padding:14px 16px;margin:12px 0}
 .hl{color:#e0533d;font-weight:700}.ok{color:#2e8b57;font-weight:600}.warn{color:#d98a00;font-weight:600}
 .kpi{display:flex;flex-wrap:wrap;gap:12px;margin:12px 0}
 .kpi div{flex:1;min-width:150px;background:#f8fafd;border:1px solid #e3e8ef;border-radius:10px;padding:12px 14px}
 .kpi b{display:block;font-size:22px;color:#16315e}.kpi small{color:#6b7686}
 figure{margin:14px 0}figcaption{font-size:12px;color:#6b7686;margin-top:4px}
 .foot{font-size:12px;color:#9aa5b4;margin-top:24px;border-top:1px solid #e3e8ef;padding-top:12px}
 .note{font-size:12px;color:#d98a00;background:#fff8ec;border:1px solid #f4e2bd;border-radius:8px;padding:8px 12px;margin:10px 0}
 table{width:100%;border-collapse:collapse;margin:10px 0;font-size:13px}
</style></head><body><div class="wrap">
<h1>香葱行情分析 · 重点云南泸西县</h1>
<div class="sub">数据范围：全国 / 云南 / 红河州泸西县 ｜ 数据日 2026-11-14（一手核验）｜ 报告生成 __GEN__</div>

<h2>一、今日核心摘要</h2>
<div class="kpi">
 <div><b>3.65</b><small>泸西 红香葱 元/公斤（均价，较 11-13 的 3.45 +5.8%）</small></div>
 <div><b>2.76</b><small>泸西 黑香葱 元/公斤（持平）</small></div>
 <div><b>4.07</b><small>全国28种蔬菜 元/公斤（11-13 官方 +2.0%）</small></div>
 <div><b>高</b><small>综合风险等级（价格+需求侧双高）</small></div>
</div>
<div class="card">
<p>① <b>价格</b>：11-14 泸西红香葱 3.4-3.7 / 均价 <span class="hl">3.65</span>，结束自 11-01 起连续十三个报价日锁定（3.45），但红仍低于 5.0 成本线 <span class="hl">27%</span>、黑 2.76 低 <span class="hl">46%</span>；黑葱区间 2.5-2.9 持平。</p>
<p>② <b>产销背离</b>：通海红葱 3.1-3.5、省级综合源A 3.1-3.5 未跟涨，王旗营小葱 3.00 横盘第四期；11-15 B2B 挂牌（惠农网/一亩田）出现「大掉价」描述（0.5-1.0 元/斤），印证品种特异性供给宽松。</p>
<p>③ <b>天气/灾害</b>：11/14-18 两股冷空气接力南下，云南大部晴、泸西无霜冻、本地无直接影响；中央气象台 11-14 大雾橙警，红河州与泸西本县 0 条独立预警。</p>
<p>④ <b>预测</b>：六档中枢（红）3.61 / 3.77 / 3.81 / 3.88 / 4.02 / 3.72 元/公斤，target_date 顺延 1 天，综合风险维持<span class="hl">高</span>（第 21 期）。</p>
</div>

<h2>二、全国与泸西天气 / 灾害概况</h2>
<div class="card">
<p><b>泸西（11-15 起 14 天）</b>：以晴到多云为主，最高温 20-22℃、最低 10-11℃，无霜冻、无强降水过程（11-14 快照切片）。<b>全国</b>：11/14-18 两股冷空气（累计降温 6-10℃、局地>12℃），东北/华北局地大到暴雪，北方露地菜退市加速、南菜北运中期支撑；华南（粤桂）13-14 暴雨大暴雨。泸西及红河州无直接关联预警。</p>
</div>
__CHARTE__
<div class="note">⚠ 天气快照由 11-14 中央气象台/Open-Meteo 窗口按 11-15 起算切片；11-15 当日《泸西菜价表》未发布（约 10:30），价格沿用 11-14 核验值。</div>

<h2>三、历史价格走势（12/24/36 月 → 10 年）</h2>
<div class="card">
<p><b>近 20 日</b>：泸西 红香葱自 9 月末 7.0 高位，10 月下旬急跌至 3.8，10-31 起锁定 3.45 平台（连续 13 日报价日），11-14 上破至 3.65（平台期首次上行）。黑香葱 2.5-2.9 区间持平。</p>
<p><b>五年同期</b>：2026 年 11 月中旬 3.65 为近五年（2022-2026）<span class="hl">绝对最低</span>，仅为常年平均（约 5.6）的 65%；同比 2025 年 6.25 约 <span class="hl">-41.6%</span>、较 2024 年 7.05 约 -48.2%。</p>
<p><b>长周期（模型重建）</b>：香葱无官方长期月度序列，下图为通货毛葱口径（×1.66 = 精品净葱），与预测中枢不可横比；近十年呈震荡下行，2024-08 峰值后回落，2026 年处历史低位。</p>
</div>
__CHARTA__
__CHARTB__
__CHARTF__
<table style="border-collapse:collapse;width:100%;font-size:13px;margin-top:8px">
<tr style="background:#f3f6fb"><th style="padding:5px 8px;border:1px solid #e3e8ef">窗口</th><th style="padding:5px 8px;border:1px solid #e3e8ef">区间涨跌</th><th style="padding:5px 8px;border:1px solid #e3e8ef">年化(CAGR)</th><th style="padding:5px 8px;border:1px solid #e3e8ef">均值</th><th style="padding:5px 8px;border:1px solid #e3e8ef">高低</th><th style="padding:5px 8px;border:1px solid #e3e8ef">振幅</th></tr>
__WINROWS__
</table>
<div class="note">长周期主序列用通货毛葱（元/kg）；预测与「当前中枢」用精品净葱/集散价，两者相差约 1.66 倍，报告中禁止横向混用比较。</div>

<h2>四、价格结构对比</h2>
<div class="card"><p>泸西产地红香葱 3.65 高于王旗营销地小葱 3.00 与辽宁朝阳销地小葱 1.70，但低于全国 28 种蔬菜 4.07、南大堡云南香葱 4.20、郑州万邦云南通货 4.00。说明产地相对销地有溢价（洗选/分级/制冰/包装），但相对全国菜价与省外云南货源到岸价仍偏弱，印证「品种特异性供给过剩」。</p></div>
__CHARTC__

<h2>五、未来行情预测（分时间段）</h2>
<div class="card"><p><b>方法</b>：0-7 天高置信段 + 季节性/结构性因子；红黑按 0.77 比价折算。本期沿用 11-14 中枢（3.65 基准），target_date 顺延 1 天，待 11-15 菜价表核验后若均价变动再滚动修正。</p>
<table style="border-collapse:collapse;width:100%;font-size:13px">
<tr style="background:#f3f6fb"><th style="padding:5px 8px;border:1px solid #e3e8ef">档位</th><th style="padding:5px 8px;border:1px solid #e3e8ef">目标日</th><th style="padding:5px 8px;border:1px solid #e3e8ef">中枢</th><th style="padding:5px 8px;border:1px solid #e3e8ef">区间(低~高)</th><th style="padding:5px 8px;border:1px solid #e3e8ef">较当前</th><th style="padding:5px 8px;border:1px solid #e3e8ef">置信度</th></tr>
__FCROWS__
</table></div>
__CHARTD__
<div class="note">三情景（红香葱）：中性 50% / 偏弱 32% / 偏强 18%。乐观（霜冻超预期+南菜北运订单实质启动）→ 中枢上修 0.2-0.4；中性（平台期延续+销地未跟涨）→ 横盘；悲观（集中上量踩踏+供给宽松延续）→ 下修 0.2-0.3。成本线 5.0 触及仍推迟至 2027 春节后。</div>

<h2>六、常见香葱种类统计</h2>
<div class="card"><p>市面上常见香葱种类以<b>红香葱（火葱）</b>、<b>黑葱（黑香葱）</b>为主，泸西主导；另有四季葱、分葱、红葱、白葱（铁杆葱）、小香葱（销地统称）。本期采集样本覆盖以下种类（按出现频次）：</p>
<table style="border-collapse:collapse;width:60%;font-size:13px"><tr style="background:#f3f6fb"><th style="padding:4px 8px;border:1px solid #e3e8ef">种类</th><th style="padding:4px 8px;border:1px solid #e3e8ef">样本条数</th></tr>__VARROWS__</table>
</div>
__CHARTG__

<h2>七、全国香葱种植省份</h2>
<div class="card"><p>全国主要香葱种植省份：<b>云南</b>（泸西/通海/晋宁最大，泸西占全国小香葱单品 60%+）、广东、广西、福建、四川、江苏、山东、河北（永年）、河南、贵州、湖北等。本期采集报价覆盖 <b>__PROVCNT__ 个省份</b>，Top15 如下：</p>
<table style="border-collapse:collapse;width:60%;font-size:13px"><tr style="background:#f3f6fb"><th style="padding:4px 8px;border:1px solid #e3e8ef">省份</th><th style="padding:4px 8px;border:1px solid #e3e8ef">样本条数</th></tr>__PROVROWS__</table>
</div>
__CHARTH__

<h2>八、泸西县专项结论与风险提示</h2>
<div class="card">
<p><b>本地结论</b>：① 11-14 红香葱上破 3.45→3.65（官方总评由「平稳」转「小香葱微涨」），但仅泸西单点、销地未跟涨，判为试探性上调；② 黑葱 2.5-2.9 持平；③ 本地晴好无霜冻，利于采收；④ 相对全国 28 种蔬菜 4.07 仍偏弱约 11%。</p>
<p><b>产业底盘</b>：泸西 46.8 万亩次、118.5 万吨、产值 36 亿元、5 万余人就业、日加工转运数千吨，为全国最大小香葱单品基地。</p>
<p><b>风险预警</b>：综合风险等级 <span class="hl">高（第 21 期）</span>。价格与需求侧为双高主导；天气/生产「中-高」（冷空气利多 vs 本地无直接影响）；流通传导「中-高」（挂牌-成交价差历史最宽）。</p>
__RISK__
<p class="warn"><b>建议措施</b>：种植端趁晴窗抢收、及时入库预冷；流通端快进快出、控制库存；关注 11-15/16 菜价表是否连续确认上破（确认则六档上调 0.2-0.3，回吐则判单日扰动）。</p>
</div>

<div class="foot">本报告由 WorkBuddy 自动化任务（376dffed）生成，仅供参考，不构成投资建议。口径、估算与风险等级详见正文与 xiangcong_2026-11-15.json。预测含置信度说明，需滚动修正。</div>
</div></body></html>"""

HTML = (HTML.replace("__TODAY__", TODAY).replace("__GEN__", GEN)
        .replace("__CHARTA__", chartA).replace("__CHARTB__", chartB).replace("__CHARTC__", chartC)
        .replace("__CHARTD__", chartD).replace("__CHARTE__", chartE).replace("__CHARTF__", chartF)
        .replace("__CHARTG__", chartG).replace("__CHARTH__", chartH)
        .replace("__WINROWS__", win_rows).replace("__FCROWS__", fc_rows)
        .replace("__VARROWS__", var_rows).replace("__PROVROWS__", prov_rows)
        .replace("__PROVCNT__", str(len(prov_counter))).replace("__RISK__", risk_html))

html_path = os.path.join(OUT, "香葱行情分析_2026-11-15.html")
open(html_path, "w", encoding="utf-8").write(HTML)
print("[OK] WROTE", html_path, "size", os.path.getsize(html_path))
print("[OK] charts: A近20日 B五年 C结构 D预测 E天气 F十年 G种类 H省份 ; 省份覆盖", len(prov_counter), "省, 品种", len(var_counter))
