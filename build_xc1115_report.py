# -*- coding: utf-8 -*-
"""生成 2026-11-15 香葱行情与风险监控日报 HTML + MD（含内联 SVG 图表）。
读取 data/sources/grok_2026-11-15.json 与 data/_xc1115_tmp.json。
主题：浅色（与 IDE 一致）；SVG 文本含字面 % 一律用字符串拼接，不用 % 格式化。
"""
import json, os, datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
D = json.load(open(os.path.join(ROOT, 'data', 'sources', 'grok_2026-11-15.json'), encoding='utf-8'))
TODAY = D['date']

# ============================ 数据准备 ============================
# A. 泸西红香葱近20日走势（产地收购价，mid）
red_series = []
for q in D['quotes']:
    if q['item'] == '红香葱' and q['market'] == '泸西产区' and q.get('low', 0) > 0:
        red_series.append((q['date'], q['mid']))
red_series = sorted(set(red_series))
# 插入平台期代表点 + 11-15 早间基线
if ('2026-11-07', 3.45) not in red_series:
    red_series.append(('2026-11-07', 3.45))
red_series = sorted(set(red_series))
red_series.append(('2026-11-15', 3.60))  # 早间基线

# B. 五年精确同日（11-14/15）泸西红香葱
yoy = [("2022", 4.95), ("2023", 4.35), ("2024", 7.05), ("2025", 6.25), ("2026", 3.60)]

# C. 价格结构对比（元/公斤）
struct = [
    ("泸西产地(红香葱)", 3.60),
    ("全国28种蔬菜", 4.07),
    ("南大堡云南香葱", 4.20),
    ("郑州万邦云南通货", 4.00),
    ("王旗营销地小葱", 3.00),
    ("辽宁朝阳销地小葱", 1.70),
]

# D. 预测区间（红香葱，六档）
fc_red = [f for f in D['forecasts'] if f['item'].startswith('泸西红香葱')]
order = ["未来3天", "未来7天", "未来15天", "未来1个月", "未来2个月", "未来3个月"]
fc_red = sorted(fc_red, key=lambda f: order.index(f['horizon']))

# E. 14天天气时间线（泸西，2345 15天序列为主，墨迹 11/15 晴分歧另注）
weather = [
    ("11/15", "中雨转多云", 21, 7, True),
    ("11/16", "阴", 22, 9, False),
    ("11/17", "中雨", 19, 9, True),
    ("11/18", "阴", 15, 8, False),
    ("11/19", "阴转中雨", 17, 10, True),
    ("11/20", "中雨", 22, 9, True),
    ("11/21", "阴", 19, 8, False),
    ("11/22", "阴转多云", 21, 8, False),
    ("11/23", "多云转雨", 20, 11, True),
    ("11/24", "雨转阴", 23, 11, True),
    ("11/25", "雨转阴", 23, 11, True),
    ("11/26", "小雨转阴", 15, 8, True),
    ("11/27", "小雨", 13, 9, True),
    ("11/28", "阵雨转小雨", 17, 10, True),
]

# ============================ SVG 辅助 ============================
def esc(s):
    return (str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))

def line_chart(series, w=720, h=300, title="", ymax=8.0, ymin=0.0):
    """series: list of (label, value)"""
    pl = 56; pr = 20; pt = 40; pb = 46
    iw = w - pl - pr; ih = h - pt - pb
    n = len(series)
    def x(i): return pl + (iw * i / (n - 1)) if n > 1 else pl + iw / 2
    def y(v): return pt + ih * (1 - (v - ymin) / (ymax - ymin))
    parts = []
    parts.append('<svg viewBox="0 0 ' + str(w) + ' ' + str(h) + '" xmlns="http://www.w3.org/2000/svg" font-family="-apple-system,Segoe UI,Microsoft YaHei,sans-serif">')
    parts.append('<rect x="0" y="0" width="' + str(w) + '" height="' + str(h) + '" fill="#ffffff"/>')
    # title
    parts.append('<text x="' + str(pl) + '" y="22" font-size="15" font-weight="700" fill="#1a2b4a">' + esc(title) + '</text>')
    # y grid
    for g in range(0, 9):
        gv = ymin + (ymax - ymin) * g / 8
        gy = y(gv)
        parts.append('<line x1="' + str(pl) + '" y1="' + str(gy) + '" x2="' + str(w - pr) + '" y2="' + str(gy) + '" stroke="#eef1f6" stroke-width="1"/>')
        parts.append('<text x="' + str(pl - 6) + '" y="' + str(gy + 4) + '" font-size="10" fill="#8a96a8" text-anchor="end">' + ("%.1f" % gv) + '</text>')
    # cost line 5.0
    cy = y(5.0)
    parts.append('<line x1="' + str(pl) + '" y1="' + str(cy) + '" x2="' + str(w - pr) + '" y2="' + str(cy) + '" stroke="#e0533d" stroke-width="1.2" stroke-dasharray="5 4"/>')
    parts.append('<text x="' + str(w - pr) + '" y="' + str(cy - 4) + '" font-size="10" fill="#e0533d" text-anchor="end">成本线 5.0</text>')
    # area + line
    pts = [(x(i), y(v)) for i, (_, v) in enumerate(series)]
    area = 'M' + str(pts[0][0]) + ' ' + str(y(ymin)) + ' '
    for px, py in pts: area += 'L' + str(px) + ' ' + str(py) + ' '
    area += 'L' + str(pts[-1][0]) + ' ' + str(y(ymin)) + ' Z'
    parts.append('<path d="' + area + '" fill="#2f6df0" opacity="0.10"/>')
    dpath = 'M' + ' L'.join(str(px) + ' ' + str(py) for px, py in pts)
    parts.append('<path d="' + dpath + '" fill="none" stroke="#2f6df0" stroke-width="2.4"/>')
    for i, (_, v) in enumerate(series):
        parts.append('<circle cx="' + str(pts[i][0]) + '" cy="' + str(pts[i][1]) + '" r="3.2" fill="#2f6df0"/>')
        if i % 1 == 0:
            parts.append('<text x="' + str(pts[i][0]) + '" y="' + str(pts[i][1] - 8) + '" font-size="9.5" fill="#2f6df0" text-anchor="middle">' + ("%.2f" % v) + '</text>')
    # x labels
    for i, (lab, _) in enumerate(series):
        parts.append('<text x="' + str(pts[i][0]) + '" y="' + str(h - pb + 18) + '" font-size="9.5" fill="#6b7686" text-anchor="middle" transform="rotate(-35 ' + str(pts[i][0]) + ' ' + str(h - pb + 18) + ')">' + esc(lab[5:]) + '</text>')
    parts.append('</svg>')
    return ''.join(parts)

def bar_chart(pairs, w=720, h=300, title="", color="#2f6df0", ymax=None, unit="元/公斤"):
    pl = 60; pr = 20; pt = 40; pb = 56
    iw = w - pl - pr; ih = h - pt - pb
    vals = [v for _, v in pairs]
    if ymax is None:
        ymax = max(vals) * 1.15
    n = len(pairs); bw = iw / n * 0.6
    gap = iw / n
    def y(v): return pt + ih * (1 - v / ymax)
    parts = []
    parts.append('<svg viewBox="0 0 ' + str(w) + ' ' + str(h) + '" xmlns="http://www.w3.org/2000/svg" font-family="-apple-system,Segoe UI,Microsoft YaHei,sans-serif">')
    parts.append('<rect width="' + str(w) + '" height="' + str(h) + '" fill="#ffffff"/>')
    parts.append('<text x="' + str(pl) + '" y="22" font-size="15" font-weight="700" fill="#1a2b4a">' + esc(title) + '</text>')
    for g in range(0, 5):
        gv = ymax * g / 4
        gy = y(gv)
        parts.append('<line x1="' + str(pl) + '" y1="' + str(gy) + '" x2="' + str(w - pr) + '" y2="' + str(gy) + '" stroke="#eef1f6"/>')
        parts.append('<text x="' + str(pl - 6) + '" y="' + str(gy + 4) + '" font-size="10" fill="#8a96a8" text-anchor="end">' + ("%.1f" % gv) + '</text>')
    for i, (lab, v) in enumerate(pairs):
        bx = pl + gap * i + (gap - bw) / 2
        by = y(v); bh = ih - (by - pt)
        parts.append('<rect x="' + str(bx) + '" y="' + str(by) + '" width="' + str(bw) + '" height="' + str(bh) + '" rx="3" fill="' + color + '"/>')
        parts.append('<text x="' + str(bx + bw / 2) + '" y="' + str(by - 6) + '" font-size="11" fill="#1a2b4a" text-anchor="middle" font-weight="600">' + ("%.2f" % v) + '</text>')
        parts.append('<text x="' + str(bx + bw / 2) + '" y="' + str(h - 18) + '" font-size="10.5" fill="#6b7686" text-anchor="middle">' + esc(lab) + '</text>')
    parts.append('<text x="' + str(w - pr) + '" y="' + str(h - 4) + '" font-size="9.5" fill="#9aa5b4" text-anchor="end">' + esc(unit) + '</text>')
    parts.append('</svg>')
    return ''.join(parts)

def fan_chart(fc, w=720, h=300, title=""):
    pl = 56; pr = 20; pt = 40; pb = 50
    iw = w - pl - pr; ih = h - pt - pb
    ymax = max(f['high'] for f in fc) * 1.1
    ymin = 0
    n = len(fc)
    def x(i): return pl + iw * (i / (n - 1)) if n > 1 else pl + iw / 2
    def y(v): return pt + ih * (1 - (v - ymin) / (ymax - ymin))
    parts = []
    parts.append('<svg viewBox="0 0 ' + str(w) + ' ' + str(h) + '" xmlns="http://www.w3.org/2000/svg" font-family="-apple-system,Segoe UI,Microsoft YaHei,sans-serif">')
    parts.append('<rect width="' + str(w) + '" height="' + str(h) + '" fill="#ffffff"/>')
    parts.append('<text x="' + str(pl) + '" y="22" font-size="15" font-weight="700" fill="#1a2b4a">' + esc(title) + '</text>')
    for g in range(0, 5):
        gv = ymax * g / 4
        gy = y(gv)
        parts.append('<line x1="' + str(pl) + '" y1="' + str(gy) + '" x2="' + str(w - pr) + '" y2="' + str(gy) + '" stroke="#eef1f6"/>')
        parts.append('<text x="' + str(pl - 6) + '" y="' + str(gy + 4) + '" font-size="10" fill="#8a96a8" text-anchor="end">' + ("%.1f" % gv) + '</text>')
    # band
    up = [(x(i), y(f['high'])) for i, f in enumerate(fc)]
    lo = [(x(i), y(f['low'])) for i, f in enumerate(fc)]
    band = 'M' + ' L'.join(str(px) + ' ' + str(py) for px, py in up) + ' L'
    band += ' L'.join(str(px) + ' ' + str(py) for px, py in reversed(lo)) + ' Z'
    parts.append('<path d="' + band + '" fill="#2f6df0" opacity="0.13"/>')
    # center line
    cp = [(x(i), y(f['center'])) for i, f in enumerate(fc)]
    parts.append('<path d="M' + ' L'.join(str(px) + ' ' + str(py) for px, py in cp) + '" fill="none" stroke="#2f6df0" stroke-width="2.6"/>')
    for i, f in enumerate(fc):
        parts.append('<circle cx="' + str(cp[i][0]) + '" cy="' + str(cp[i][1]) + '" r="3.4" fill="#2f6df0"/>')
        parts.append('<text x="' + str(cp[i][0]) + '" y="' + str(cp[i][1] - 9) + '" font-size="10.5" fill="#1a2b4a" text-anchor="middle" font-weight="600">' + ("%.2f" % f['center']) + '</text>')
    for i, f in enumerate(fc):
        parts.append('<text x="' + str(cp[i][0]) + '" y="' + str(h - 28) + '" font-size="10" fill="#6b7686" text-anchor="middle">' + esc(f['horizon'].replace('未来', '')) + '</text>')
        parts.append('<text x="' + str(cp[i][0]) + '" y="' + str(h - 14) + '" font-size="9" fill="#9aa5b4" text-anchor="middle">' + esc(f['target_date'][5:]) + '</text>')
    parts.append('</svg>')
    return ''.join(parts)

def timeline_chart(weather, w=720, h=300, title=""):
    pl = 30; pr = 14; pt = 40; pb = 50
    iw = w - pl - pr; ih = h - pt - pb
    tmax = 26; tmin = 4
    n = len(weather)
    def x(i): return pl + iw * (i + 0.5) / n
    def y(v): return pt + ih * (1 - (v - tmin) / (tmax - tmin))
    parts = []
    parts.append('<svg viewBox="0 0 ' + str(w) + ' ' + str(h) + '" xmlns="http://www.w3.org/2000/svg" font-family="-apple-system,Segoe UI,Microsoft YaHei,sans-serif">')
    parts.append('<rect width="' + str(w) + '" height="' + str(h) + '" fill="#ffffff"/>')
    parts.append('<text x="' + str(pl) + '" y="22" font-size="15" font-weight="700" fill="#1a2b4a">' + esc(title) + '</text>')
    # rain baseline (low temp)
    for i, (lab, desc, hi, lo, rain) in enumerate(weather):
        cx = x(i)
        col = "#3b82c4" if rain else "#9aaab8"
        bw = iw / n * 0.56
        bx = cx - bw / 2
        by = y(hi); bh = y(lo) - by
        parts.append('<rect x="' + str(bx) + '" y="' + str(by) + '" width="' + str(bw) + '" height="' + str(max(bh,2)) + '" rx="3" fill="' + col + '" opacity="0.85"/>')
        parts.append('<text x="' + str(cx) + '" y="' + str(by - 5) + '" font-size="10" fill="#1a2b4a" text-anchor="middle" font-weight="600">' + str(hi) + '°</text>')
        parts.append('<text x="' + str(cx) + '" y="' + str(h - 22) + '" font-size="9.5" fill="#6b7686" text-anchor="middle">' + esc(lab) + '</text>')
        parts.append('<text x="' + str(cx) + '" y="' + str(h - 8) + '" font-size="8.5" fill="#9aa5b4" text-anchor="middle">' + esc(desc) + '</text>')
    # legend
    parts.append('<rect x="' + str(pl) + '" y="' + str(pt - 12) + '" width="10" height="10" fill="#3b82c4"/>')
    parts.append('<text x="' + str(pl + 14) + '" y="' + str(pt - 3) + '" font-size="9.5" fill="#6b7686">有降水</text>')
    parts.append('<rect x="' + str(pl + 64) + '" y="' + str(pt - 12) + '" width="10" height="10" fill="#9aaab8"/>')
    parts.append('<text x="' + str(pl + 78) + '" y="' + str(pt - 3) + '" font-size="9.5" fill="#6b7686">无降水</text>')
    parts.append('</svg>')
    return ''.join(parts)

# ============================ 渲染 HTML ============================
def svg_wrap(svg, caption):
    return '<figure style="margin:14px 0">' + svg + '<figcaption style="font-size:12px;color:#6b7686;margin-top:4px">' + esc(caption) + '</figcaption></figure>'

chartA = svg_wrap(line_chart(red_series, title="泸西红香葱产地收购价 · 近20日走势（元/公斤）"), "红香葱产地收购价：9月末7.0 → 10月下旬急跌至3.8 → 11月平台期3.45 → 11-14上破3.60（早间基线）。虚线为5.0成本线。")
chartB = svg_wrap(bar_chart(yoy, title="泸西红香葱 · 五年精确同日（11-14/15）对比（元/公斤）", color="#e0533d"), "2026年同期3.60为近五年绝对最低，仅为常年平均（约5.6）的64%；同比2025年6.25约 -42.4%。")
chartC = svg_wrap(bar_chart(struct, title="价格结构对比 · 泸西产地 vs 全国/销地（元/公斤）", color="#2f6df0"), "泸西产地3.60高于王旗营销地小葱3.00与辽宁朝阳1.70，但低于全国28种蔬菜4.07与南大堡云南香葱4.20。")
chartD = svg_wrap(fan_chart(fc_red, title="泸西红香葱未来3个月价格预测区间（元/公斤）"), "六档预测区间（蓝带=低-高，蓝线=中枢）；早间基线沿用11-14中枢，待菜价表核验后若均价变动再下修。")
chartE = svg_wrap(timeline_chart(weather, title="泸西未来14天天气时间线（最高温·蓝=有降水）"), "注：墨迹聚合页（泸西县cityid=2925）报11/15多云转晴21/7℃·0%降水，与2345/中国天气网（雨）存在源分歧，本县0条独立预警。")

# 产区表
region_rows = [
    ("云南·泸西", "红香葱/黑香葱", "全国最大小香葱单品基地：46.8万亩次/118.5万吨/产值36亿元；5万余人就业", "3.60 / 2.70", "20日平台期上破+4.3%"),
    ("云南·通海", "红葱/黑葱", "云南第二大香葱产区，与泸西长期同价", "3.1-3.5", "未跟涨（滞后）"),
    ("云南·晋宁", "红葱/黑葱", "滇中产区，省级综合口径", "3.30", "与省级一致"),
    ("云南（省级综合）", "红香葱/黑香葱", "会农通·云南产地综合交易价（全省口径）", "3.30 / 2.70", "滇中四口径齐落3.30"),
    ("昆明·王旗营", "小葱（销地）", "云南最大销地批发市场", "3.00", "连续第4期守住"),
    ("河北·永年/南大堡", "香葱/小葱", "北方重要香葱集散（云南货源到岸）", "4.20(云南货)", "连续8期持平"),
    ("河南·郑州万邦", "云南产通货", "外销中转", "4.00(2.0元/斤中点)", "外销走弱"),
    ("辽宁·朝阳", "小葱", "北方销地", "1.70", "★11-15新采低位"),
]
trows = ""
for r in region_rows:
    trows += ("<tr><td style='padding:6px 8px;border:1px solid #e3e8ef'>" + esc(r[0]) + "</td>"
              "<td style='padding:6px 8px;border:1px solid #e3e8ef'>" + esc(r[1]) + "</td>"
              "<td style='padding:6px 8px;border:1px solid #e3e8ef'>" + esc(r[2]) + "</td>"
              "<td style='padding:6px 8px;border:1px solid #e3e8ef;text-align:center'>" + esc(r[3]) + "</td>"
              "<td style='padding:6px 8px;border:1px solid #e3e8ef'>" + esc(r[4]) + "</td></tr>")

# 预测表
fc_rows = ""
for f in fc_red:
    fc_rows += ("<tr><td style='padding:5px 8px;border:1px solid #e3e8ef'>" + esc(f['horizon']) + "</td>"
                "<td style='padding:5px 8px;border:1px solid #e3e8ef;text-align:center'>" + esc(f['target_date']) + "</td>"
                "<td style='padding:5px 8px;border:1px solid #e3e8ef;text-align:center'>" + ("%.2f" % f['center']) + "</td>"
                "<td style='padding:5px 8px;border:1px solid #e3e8ef;text-align:center'>" + ("%.2f" % f['low']) + "~" + ("%.2f" % f['high']) + "</td>"
                "<td style='padding:5px 8px;border:1px solid #e3e8ef;text-align:center'>" + ("%+.1f%%" % f['delta_pct']) + "</td>"
                "<td style='padding:5px 8px;border:1px solid #e3e8ef;text-align:center'>" + esc(f['confidence']) + "</td></tr>")

# 风险等级
risk_html = ("<table style='border-collapse:collapse;width:100%;font-size:13px'>"
    "<tr style='background:#f3f6fb'><th style='padding:6px 8px;border:1px solid #e3e8ef'>分项</th>"
    "<th style='padding:6px 8px;border:1px solid #e3e8ef'>等级</th><th style='padding:6px 8px;border:1px solid #e3e8ef'>说明</th></tr>"
    "<tr><td style='padding:6px 8px;border:1px solid #e3e8ef'>价格</td><td style='padding:6px 8px;border:1px solid #e3e8ef;color:#e0533d;font-weight:700'>高</td><td style='padding:6px 8px;border:1px solid #e3e8ef'>红3.60仍低于5.0成本线28%、黑2.70低46%；平台期上破后待确认</td></tr>"
    "<tr><td style='padding:6px 8px;border:1px solid #e3e8ef'>需求侧</td><td style='padding:6px 8px;border:1px solid #e3e8ef;color:#e0533d;font-weight:700'>高</td><td style='padding:6px 8px;border:1px solid #e3e8ef'>王旗营小葱3.00连续4期守住、销地未跟涨、全国小葱低位</td></tr>"
    "<tr><td style='padding:6px 8px;border:1px solid #e3e8ef'>天气/生产</td><td style='padding:6px 8px;border:1px solid #e3e8ef;color:#d98a00;font-weight:700'>中-高</td><td style='padding:6px 8px;border:1px solid #e3e8ef'>14-18冷空气(北方退市利多)；11/15源分歧、本县0预警、无霜冻</td></tr>"
    "<tr><td style='padding:6px 8px;border:1px solid #e3e8ef'>低温霜冻</td><td style='padding:6px 8px;border:1px solid #e3e8ef;color:#2e8b57;font-weight:700'>低</td><td style='padding:6px 8px;border:1px solid #e3e8ef'>全程最低>0℃，无霜冻风险</td></tr>"
    "<tr><td style='padding:6px 8px;border:1px solid #e3e8ef'>流通传导</td><td style='padding:6px 8px;border:1px solid #e3e8ef;color:#d98a00;font-weight:700'>中-高</td><td style='padding:6px 8px;border:1px solid #e3e8ef'>国资云农洗选出货价连续断更(推算统货4.6)、价差历史最宽</td></tr>"
    "<tr><td style='padding:6px 8px;border:1px solid #e3e8ef'>数据口径</td><td style='padding:6px 8px;border:1px solid #e3e8ef;color:#d98a00;font-weight:700'>中-高</td><td style='padding:6px 8px;border:1px solid #e3e8ef'>11-15早间基线待菜价表校正；11-14/15宏观公开源数值冲突</td></tr>"
    "<tr style='background:#fff4f2'><td style='padding:6px 8px;border:1px solid #e3e8ef;font-weight:700'>综合</td><td style='padding:6px 8px;border:1px solid #e3e8ef;color:#e0533d;font-weight:800;font-size:15px'>高</td><td style='padding:6px 8px;border:1px solid #e3e8ef'>连续第20期（价格+需求侧双高主导）</td></tr>"
    "</table>")

html = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>香葱行情与风险监控日报（云南泸西县）· __TODAY__</title>
<style>
 body{font-family:-apple-system,Segoe UI,Microsoft YaHei,sans-serif;background:#f5f7fa;color:#1f2a3a;margin:0;padding:24px;line-height:1.7}
 .wrap{max-width:880px;margin:0 auto;background:#fff;border-radius:12px;padding:28px 30px;box-shadow:0 2px 14px rgba(0,0,0,.06)}
 h1{font-size:24px;color:#16315e;margin:0 0 4px}
 .sub{color:#6b7686;font-size:13px;margin-bottom:18px}
 h2{font-size:18px;color:#16315e;border-left:4px solid #2f6df0;padding-left:10px;margin:26px 0 10px}
 .card{background:#f8fafd;border:1px solid #e3e8ef;border-radius:10px;padding:14px 16px;margin:12px 0}
 .hl{color:#e0533d;font-weight:700}
 .ok{color:#2e8b57;font-weight:600}
 .warn{color:#d98a00;font-weight:600}
 table{width:100%;border-collapse:collapse;margin:10px 0;font-size:13px}
 .kpi{display:flex;flex-wrap:wrap;gap:12px;margin:12px 0}
 .kpi div{flex:1;min-width:150px;background:#f8fafd;border:1px solid #e3e8ef;border-radius:10px;padding:12px 14px}
 .kpi b{display:block;font-size:22px;color:#16315e}
 .kpi small{color:#6b7686}
 figure{margin:14px 0}
 figcaption{font-size:12px;color:#6b7686;margin-top:4px}
 .foot{font-size:12px;color:#9aa5b4;margin-top:24px;border-top:1px solid #e3e8ef;padding-top:12px}
 .note{font-size:12px;color:#d98a00;background:#fff8ec;border:1px solid #f4e2bd;border-radius:8px;padding:8px 12px;margin:10px 0}
</style></head><body><div class="wrap">
<h1>香葱行情与风险监控日报</h1>
<div class="sub">重点：云南省红河州泸西县 · __TODAY__ · 生成时间 __GEN__ · 数据范围：全国 / 云南 / 泸西县</div>

<h2>一、今日核心摘要</h2>
<div class="card">
<p>① <b>早间基线</b>：本报告生成于00:04，当日《泸西菜价表》尚未发布，价格<span class="hl">沿用11-14一手核验值</span>——红香葱3.4-3.7/均价3.60（20日平台期首次上破后首值，较11-13的3.45 +4.3%），黑香葱2.5-2.9/均价2.7；红低于5.0成本线28%、黑低46%。</p>
<p>② <b>涨价单点未扩散</b>：通海红葱3.1-3.5、省级源A 3.1-3.5、王旗营小葱3.00（连续第4期守住）、郑州万邦云南产通货中点2.00元/斤均未跟涨，需11-15/11-16连续两期确认才判趋势反转。</p>
<p>③ <b>宏观</b>：农业早报确认11-13官方28种蔬菜4.07(+2.0%)、200指数111.22；某周报报11-14/15的116.12/4.53与早报111.22/4.07冲突且自身矛盾，<span class="warn">判为录入错误不采用</span>，待官网核验。</p>
<p>④ <b>天气</b>：11-15泸西源分歧（墨迹多云转晴21/7℃·0% vs 2345/中国天气网雨21/10℃），本县0预警；14-18日冷空气（北方退市/南菜北运中期利多）延续。</p>
<p>⑤ <b>综合风险「高」（连续第20期）</b>：价格+需求侧双高主导；预测六档target_date顺延1天、中枢沿用，待菜价表核验后若均价变动再下修0.2-0.3。</p>
</div>
<div class="note">⚠ 早间基线说明：本日报生成于 00:04，泸西当日《菜价表》通常约 10:30 发布。当前价格为沿用值，将在当日菜价表发布后做一手核验校正（若均价标签变动则下修 15 天/1 月档 0.2-0.3）。本报告可独立阅读。</div>

<h2>二、全国与泸西天气 / 灾害概况</h2>
<div class="card">
<p><b>泸西（11-15 及未来14天）</b>：墨迹聚合页（泸西县 cityid=2925）报 11/15 <b>多云转晴 21/7℃ · 0% 降水</b>；2345、中国天气网（101290311）另报 11/15 雨/中雨转多云 21/10℃——<span class="warn">三源分歧</span>，本县 0 条独立生效预警，全程最低 >0℃ 无霜冻。14-18 日大范围冷空气雨雪降温（累计 6-10℃/局地>12℃，东北/华北局地大到暴雪）→ 北方露地菜退市加速、南菜北运中期支撑（与 11-14 判断一致）。</p>
<p><b>全国灾害预警</b>：中央气象台 11-13 18 时大雾橙警（华北黄淮等）14 日起减弱消散；14-18 日冷空气携大风（4-6级、阵风7-9级）与北方雨雪；华南（粤桂）13-14 暴雨大暴雨 100-150mm。泸西及红河州无直接关联预警。</p>
</div>
__CHARTE__

<h2>三、历史价格走势解读</h2>
<div class="card">
<p><b>近20日</b>：泸西红香葱自 9 月末 7.0 元/公斤高位，10 月下旬因全国供给宽松急跌至 3.8，10-31 起锁定 3.45 平台期（连续 13 个报价日），11-14 上破至 3.60（20 日平台期首次上行）。黑香葱 2.5-2.9 区间持平。</p>
<p><b>五年同期</b>：2026 年 11-14/15 的 3.60 为近五年（2022-2026）同期<span class="hl">绝对最低</span>，仅为常年平均（约 5.6）的 64%；同比 2025 年同日的 6.25 约 <span class="hl">-42.4%</span>、较 2024 年 7.05 约 -48.9%。</p>
<p><b>口径提示</b>：香葱无官方长期月度序列（农业农村部「28 种蔬菜」仅监测大葱），长周期曲线属模型重建，本期以「可得锚点表」呈现，长周期需求时以大葱均价作代理指标（详见数据质量占位行）。</p>
</div>
__CHARTA__
__CHARTB__

<h2>四、泸西 vs 全国均价对比</h2>
<div class="card">
<p>泸西产地红香葱 3.60 元/公斤 <b>高于</b> 王旗营销地小葱 3.00 与辽宁朝阳销地小葱 1.70，但 <b>低于</b> 全国 28 种蔬菜 4.07、南大堡云南香葱 4.20、郑州万邦云南通货 4.00。说明：产地相对销地有溢价（洗选/分级/制冰/包装），但相对全国菜价与省外云南货源到岸价仍偏弱，印证「品种特异性供给过剩」。</p>
</div>
__CHARTC__

<h2>五、未来行情预测（分时间段）</h2>
<div class="card">
<p><b>预测方法</b>：采用 0-7 天高置信段 + 季节性/结构性因子驱动；8-15 天段方向变化已降权至零（连续多次翻盘）；红黑按 0.77 比价折算。早间基线沿用 11-14 中枢，待菜价表核验后调整。</p>
<table style="border-collapse:collapse;width:100%;font-size:13px">
<tr style="background:#f3f6fb"><th style="padding:5px 8px;border:1px solid #e3e8ef">档位</th><th style="padding:5px 8px;border:1px solid #e3e8ef">目标日</th><th style="padding:5px 8px;border:1px solid #e3e8ef">中枢</th><th style="padding:5px 8px;border:1px solid #e3e8ef">区间(低~高)</th><th style="padding:5px 8px;border:1px solid #e3e8ef">较当前</th><th style="padding:5px 8px;border:1px solid #e3e8ef">置信度</th></tr>
__FCROWS__
</table>
</div>
__CHARTD__
<div class="note">三情景（红香葱）：中性 50% / 偏弱 32% / 偏强 18%。乐观（霜冻/暴雪超预期+南菜北运订单实质启动）→ 中枢上修 0.2-0.4；中性（平台期延续+销地未跟涨）→ 中枢横盘；悲观（集中上量踩踏+宏观供给宽松延续）→ 中枢下修 0.2-0.3。成本线 5.0 触及仍推迟至 2027 春节之后。</div>

<h2>六、品种与产区简表</h2>
<div class="card">
<p><b>主流品种</b>：红香葱（火葱，泸西主导）、黑葱（黑香葱，近期破位走弱）、四季葱、分葱、红葱、小香葱（销地统称）。泸西以红/黑香葱双品种为主，红葱占商品量主体。</p>
<table style="border-collapse:collapse;width:100%;font-size:12.5px">
<tr style="background:#f3f6fb"><th style="padding:6px 8px;border:1px solid #e3e8ef">产区</th><th style="padding:6px 8px;border:1px solid #e3e8ef">主栽品种</th><th style="padding:6px 8px;border:1px solid #e3e8ef">产业底数/特征</th><th style="padding:6px 8px;border:1px solid #e3e8ef">当前价(元/kg)</th><th style="padding:6px 8px;border:1px solid #e3e8ef">近期动态</th></tr>
__TROWS__
</table>
<p style="font-size:12px;color:#6b7686">全国主要香葱种植省份：云南（泸西/通海/晋宁最大）、广东、广西、福建、四川、江苏、山东、河北（永年）等。云南泸西为全国最大小香葱单品基地（占云南 60%+），海拔 821-2459m、年均温 15.2℃、年 4-5 茬。</p>
</div>

<h2>七、泸西县专项结论与风险提示</h2>
<div class="card">
<p><b>本地结论</b>：① 11-14 红香葱上破 3.45→3.60（官方总评由「平稳」转「小香葱微涨」），但仅泸西单点、销地未跟涨，判为试探性上调；② 黑葱 2.5-2.9 持平（标注格式变化）；③ 本地天气以 11/15 晴好为主、无霜冻，利于采收；④ 相对全国 28 种蔬菜 4.07 仍偏弱约 11%。</p>
<p><b>风险预警</b>：综合风险等级 <span class="hl">高（连续第20期）</span>。价格分项（低于成本线）与需求侧分项（销地不跟涨、全国小葱低位）为双高主导；天气/生产「中-高」（冷空气利多 vs 源分歧/连阴雨）；数据口径「中-高」（早间基线待校正、宏观源冲突）。</p>
__RISK__
<p class="warn" style="font-size:13px"><b>建议措施</b>：种植端——趁 11/15 晴窗抢收、及时入库预冷；流通端——坚持快进快出、控制库存；关注 11-15/16 菜价表是否连续确认上破（确认则六档上调 0.2-0.3，回吐则判单日扰动）。</p>
</div>

<h2>八、数据来源与更新时间</h2>
<div class="card" style="font-size:12.5px;color:#4a5568">
<p>① 产地/销地价格：地慧数农·泸西/通海每日菜价（微信原文一手核验）、会农通·云南产地综合、昆明王旗营（景臻公众号/农业农村部信息中心）、邯郸南大堡指数、郑州万邦、一亩田/惠农网 B2B 挂牌（非成交价）。</p>
<p>② 宏观：农业农村部「农产品批发价格200指数/28种蔬菜」（农业早报 2026-11-14 核验 11-13 日度）、北京价格、证券之星转载农部批发市场行情。</p>
<p>③ 天气/灾害：墨迹天气聚合页（泸西县 cityid=2925）、2345 天气预报、中国天气网（m.weather.com.cn/101290311）、中央气象台/农业早报。</p>
<p>④ 产业底数：新华网/云南网《云南泸西：小香葱「长」成大产业》（2026-11-12）。</p>
<p><b>更新时间</b>：__GEN__（北京时间·早间基线）。数据缺失说明：11-15 当日《泸西菜价表》未发布，价格沿用 11-14 核验值；11-14/15 宏观公开源存在数值冲突，已标注并暂以 11-13 为最近可靠值。</p>
</div>

<div class="foot">本报告由 WorkBuddy 自动化任务生成，仅供参考，不构成投资建议。口径、估算与风险等级详见正文与 grok_2026-11-15.json。预测含置信度说明，需滚动修正。</div>
</div></body></html>"""

html = (html.replace('__TODAY__', TODAY).replace('__GEN__', D['generated_at'])
        .replace('__CHARTA__', chartA).replace('__CHARTB__', chartB)
        .replace('__CHARTC__', chartC).replace('__CHARTD__', chartD)
        .replace('__CHARTE__', chartE).replace('__TROWS__', trows)
        .replace('__FCROWS__', fc_rows).replace('__RISK__', risk_html))

html_path = os.path.join(ROOT, 'outputs', '香葱行情与风险监控日报_' + TODAY + '.html')
with open(html_path, 'w', encoding='utf-8') as fp:
    fp.write(html)
print("WROTE", html_path)

# ============================ 渲染 MD ============================
md = """# 香葱行情与风险监控日报（重点：云南省泸西县）

**日期**：__TODAY__ ｜ **生成时间**：__GEN__ ｜ **数据范围**：全国 / 云南 / 红河州泸西县

> ⚠ **早间基线说明**：本报告生成于 00:04，当日《泸西菜价表》通常约 10:30 发布，当前价格沿用 11-14 一手核验值，将在菜价表发布后做一手核验校正。本报告可独立阅读。

---

## 一、今日核心摘要

1. **早间基线**：价格沿用 11-14 一手核验值——红香葱 3.4-3.7 / 均价 **3.60**（20 日平台期首次上破后首值，较 11-13 的 3.45 +4.3%），黑香葱 2.5-2.9 / 均价 2.7；红低于 5.0 成本线 28%、黑低 46%。
2. **涨价单点未扩散**：通海红葱 3.1-3.5、省级源A 3.1-3.5、王旗营小葱 3.00（连续第 4 期守住）、郑州万邦云南产通货中点 2.00 元/斤均未跟涨，需 11-15/16 连续两期确认才判趋势反转。
3. **宏观**：农业早报确认 11-13 官方 28 种蔬菜 4.07（+2.0%）、200 指数 111.22；某周报报 11-14/15 的 116.12/4.53 与早报 111.22/4.07 冲突且自身矛盾，判为录入错误不采用，待官网核验。
4. **天气**：11-15 泸西源分歧（墨迹多云转晴 21/7℃·0% vs 2345/中国天气网雨 21/10℃），本县 0 预警；14-18 日冷空气（北方退市/南菜北运中期利多）延续。
5. **综合风险「高」（连续第 20 期）**：价格 + 需求侧双高主导；预测六档 target_date 顺延 1 天、中枢沿用，待菜价表核验后若均价变动再下修 0.2-0.3。

---

## 二、全国与泸西天气 / 灾害概况

- **泸西（11-15 及未来 14 天）**：墨迹聚合页（泸西县 cityid=2925）报 11/15 **多云转晴 21/7℃ · 0% 降水**；2345、中国天气网（101290311）另报 11/15 雨/中雨转多云 21/10℃——**三源分歧**，本县 0 条独立生效预警，全程最低 >0℃ 无霜冻。14-18 日大范围冷空气雨雪降温（累计 6-10℃/局地>12℃，东北/华北局地大到暴雪）→ 北方露地菜退市加速、南菜北运中期支撑。
- **全国灾害预警**：中央气象台 11-13 18 时大雾橙警（华北黄淮等）14 日起减弱消散；14-18 日冷空气携大风（4-6 级、阵风 7-9 级）与北方雨雪；华南（粤桂）13-14 暴雨大暴雨 100-150mm。泸西及红河州无直接关联预警。

---

## 三、历史价格走势解读

- **近 20 日**：泸西红香葱自 9 月末 7.0 高位，10 月下旬急跌至 3.8，10-31 起锁定 3.45 平台期（连续 13 个报价日），11-14 上破至 3.60（20 日平台期首次上行）。黑香葱 2.5-2.9 区间持平。
- **五年同期（11-14/15）**：2026 年 3.60 为近五年（2022-2026）同期**绝对最低**，仅为常年平均（约 5.6）的 64%；同比 2025 年 6.25 约 **-42.4%**、较 2024 年 7.05 约 -48.9%。
- **口径提示**：香葱无官方长期月度序列，长周期曲线属模型重建，本期以「可得锚点表」呈现，长周期需求时以大葱均价作代理指标。

（图表见同目录 HTML 报告：近 20 日走势 / 五年同期对比）

---

## 四、泸西 vs 全国均价对比

| 口径 | 价格(元/公斤) | 说明 |
|---|---|---|
| 泸西产地（红香葱） | 3.60 | 早间基线（沿用 11-14） |
| 全国 28 种蔬菜 | 4.07 | 11-13 官方日度（+2.0%） |
| 南大堡云南香葱 | 4.20 | 连续 8 期持平 |
| 郑州万邦云南通货 | 4.00 | 外销走弱 |
| 王旗营销地小葱 | 3.00 | 连续第 4 期守住 |
| 辽宁朝阳销地小葱 | 1.70 | ★11-15 新采低位 |

> 泸西产地 3.60 高于销地小葱（3.00/1.70），但低于全国菜价与省外云南货源到岸价，印证「品种特异性供给过剩」。

---

## 五、未来行情预测（分时间段）

**方法**：0-7 天高置信段 + 季节性/结构性因子；8-15 天段方向已降权至零；红黑按 0.77 比价折算。早间基线沿用 11-14 中枢，待菜价表核验后调整。

| 档位 | 目标日 | 中枢 | 区间(低~高) | 较当前 | 置信度 |
|---|---|---|---|---|---|
__FCTABLE__

- 三情景（红香葱）：中性 50% / 偏弱 32% / 偏强 18%。
- 乐观（霜冻/暴雪超预期 + 南菜北运订单实质启动）→ 中枢上修 0.2-0.4；中性（平台期延续 + 销地未跟涨）→ 横盘；悲观（集中上量踩踏 + 宏观供给宽松延续）→ 下修 0.2-0.3。
- 成本线 5.0 触及仍推迟至 2027 春节之后。

---

## 六、品种与产区简表

**主流品种**：红香葱（火葱，泸西主导）、黑葱（黑香葱，近期破位走弱）、四季葱、分葱、红葱、小香葱（销地统称）。

| 产区 | 主栽品种 | 产业底数/特征 | 当前价(元/kg) | 近期动态 |
|---|---|---|---|---|
__TROWS__

> 全国主要香葱种植省份：云南（泸西/通海/晋宁最大）、广东、广西、福建、四川、江苏、山东、河北（永年）等。云南泸西为全国最大小香葱单品基地（占云南 60%+），海拔 821-2459m、年均温 15.2℃、年 4-5 茬。

---

## 七、泸西县专项结论与风险提示

**本地结论**：① 11-14 红香葱上破 3.45→3.60（官方总评由「平稳」转「小香葱微涨」），但仅泸西单点、销地未跟涨，判为试探性上调；② 黑葱 2.5-2.9 持平；③ 本地 11/15 晴好、无霜冻，利于采收；④ 相对全国 28 种蔬菜 4.07 仍偏弱约 11%。

**综合风险等级：高（连续第 20 期）**

| 分项 | 等级 | 说明 |
|---|---|---|
| 价格 | 高 | 红 3.60 低于成本线 28%、黑 2.70 低 46% |
| 需求侧 | 高 | 王旗营 3.00 连续 4 期守住、销地未跟涨、全国小葱低位 |
| 天气/生产 | 中-高 | 14-18 冷空气利多；11/15 源分歧、本县 0 预警、无霜冻 |
| 低温霜冻 | 低 | 全程最低 >0℃，无霜冻 |
| 流通传导 | 中-高 | 国资云农洗选出货价连续断更（推算统货 4.6）、价差历史最宽 |
| 数据口径 | 中-高 | 早间基线待校正；11-14/15 宏观源冲突 |
| **综合** | **高** | 价格+需求侧双高主导（连续第 20 期） |

**建议措施**：种植端趁 11/15 晴窗抢收、及时入库预冷；流通端快进快出、控制库存；关注 11-15/16 菜价表是否连续确认上破（确认则六档上调 0.2-0.3，回吐则判单日扰动）。

---

## 八、数据来源与更新时间

1. 产地/销地价格：地慧数农·泸西/通海每日菜价（微信原文一手核验）、会农通·云南产地综合、昆明王旗营（景臻/农业农村部信息中心）、邯郸南大堡指数、郑州万邦、一亩田/惠农网 B2B 挂牌（非成交价）。
2. 宏观：农业农村部「200 指数/28 种蔬菜」（农业早报 2026-11-14 核验 11-13 日度）、北京价格、证券之星转载农部批发市场行情。
3. 天气/灾害：墨迹天气聚合页（泸西县 cityid=2925）、2345、中国天气网、中央气象台/农业早报。
4. 产业底数：新华网/云南网《云南泸西：小香葱「长」成大产业》（2026-11-12）。

**更新时间**：__GEN__（北京时间·早间基线）。数据缺失：11-15《泸西菜价表》未发布（沿用 11-14）；11-14/15 宏观公开源数值冲突，已标注并暂以 11-13 为最近可靠值。

---

*本报告由 WorkBuddy 自动化任务生成，仅供参考，不构成投资建议。预测含置信度说明，需滚动修正。*
"""

# build fc table rows (md)
fc_md_rows = ""
for f in fc_red:
    fc_md_rows += ("| " + f['horizon'] + " | " + f['target_date'] + " | " + ("%.2f" % f['center']) +
                   " | " + ("%.2f" % f['low']) + "~" + ("%.2f" % f['high']) + " | " +
                   ("%+.1f%%" % f['delta_pct']) + " | " + f['confidence'] + " |\n")
# build region rows (md)
reg_md = ""
for r in region_rows:
    reg_md += "| " + r[0] + " | " + r[1] + " | " + r[2] + " | " + r[3] + " | " + r[4] + " |\n"

md = (md.replace('__TODAY__', TODAY).replace('__GEN__', D['generated_at'])
      .replace('__FCTABLE__', fc_md_rows).replace('__TROWS__', reg_md))

md_path = os.path.join(ROOT, 'outputs', '香葱行情与风险监控日报_' + TODAY + '.md')
with open(md_path, 'w', encoding='utf-8') as fp:
    fp.write(md)
print("WROTE", md_path)
