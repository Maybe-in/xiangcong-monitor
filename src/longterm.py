# -*- coding: utf-8 -*-
"""长周期历史行情（10 年）重建与窗口统计。

口径说明（务必与报告一起阅读）：
  主序列 = 云南泸西 / 滇中南产地香葱综合交易价，元/公斤，通货（毛葱）口径。
  另有「精品净葱」折算序列 = 主序列 × PREMIUM（1.66，据 2026-10 同期两组报价测算）。

数据分两类，报告中必须区分：
  obs —— 有公开来源的观测锚点（可用于支撑结论）
  inf —— 区间推断锚点（仅用于连接形态，不单独支撑结论）

重建方法（可复算）：
  1. 用季节因子 S(m) 对每个锚点做去季节化：level = price / S(m)
  2. 在去季节化 level 上做相邻锚点的对数线性插值（时间轴按月）
  3. 再乘回季节因子：P(t) = level(t) × S(m)
  => 序列在锚点月份精确等于锚点值，锚点之间呈平滑的季节化路径。
"""

from __future__ import annotations

import math
from datetime import date

# 精品净葱 / 通货毛葱 折算系数
PREMIUM = 1.66

# 月度季节因子（香葱：春峰 3-5 月、夏谷 7-8 月、秋峰 10-11 月、冬平 12-2 月）
# 依据：中国蔬菜流通协会《2023 年重点蔬菜月度价格白皮书》小葱地头价双峰结构
_SEASON_RAW = {1: 0.88, 2: 0.95, 3: 1.15, 4: 1.45, 5: 1.40, 6: 1.00,
               7: 0.72, 8: 0.78, 9: 1.05, 10: 1.35, 11: 1.30, 12: 0.97}


def _norm_season() -> dict:
    mean = sum(_SEASON_RAW.values()) / 12.0
    return {m: v / mean for m, v in _SEASON_RAW.items()}


SEASON = _norm_season()

# ------------------------------------------------------------------ 锚点
# (年, 月, 价格元/kg, 类型, 来源说明)
ANCHORS = [
    (2016, 6, 3.96, "inf", "2016 年香葱销区年均 7.2 元/kg（南方农村报《2016 年度蔬菜大盘查》，7 月峰值 14 元/kg），按产地/销区 0.55 折算"),
    (2017, 6, 3.30, "inf", "自 2016 高光年回落；西昌冬春小香葱地头均价 2.5 元/kg（2016 冬春为 1.5）"),
    (2018, 6, 3.00, "inf", "西昌 2018-11-20 开市 2.4 元/kg、12-20 升至 3.4 元/kg"),
    (2019, 6, 3.20, "inf", "西昌 2019-02-01 维持 3.4 元/kg，春节后回落至 1.3 元/kg"),
    (2020, 3, 1.30, "obs", "云南网 / 新京报：泸西香葱约 1.3 元/kg，不到往年一半（疫情冲击）；红葱 0.8 元/斤、黑葱 0.6 元/斤"),
    (2020, 11, 3.00, "inf", "2020 下半年「向钱葱」行情启动，全国葱类价格普遍翻倍"),
    (2021, 1, 5.00, "obs", "广西玉林香葱收购价 4.8 元/斤（净葱，约 9.6 元/kg）；全国葱价处高位"),
    (2021, 11, 3.20, "inf", "2021 年高位后震荡回落，种植面积恢复"),
    (2022, 2, 5.50, "obs", "2022-02-22 泸西罕见大雪、受灾约 4 万亩；南京众彩云南小葱 2/23 均价 6.2 → 2/24 14.5 元/kg"),
    (2022, 11, 4.00, "obs", "云南产地蔬菜综合交易价：红香葱 3.8-4.2、黑葱 3.8-4.0 元/kg"),
    (2023, 6, 4.20, "obs", "中国蔬菜流通协会：2023 年全国小葱地头均价 4.2 元/kg（春峰 5.8、夏谷 3.1、秋峰 5.3）"),
    (2024, 1, 2.66, "obs", "泸西香葱 1.33 元/斤（中国报告大厅 2024-01-04）"),
    (2024, 8, 11.00, "obs", "泸西小香葱产地价 8/19 峰值 6 元/斤，随后回落至 5.0-5.5 元/斤"),
    (2024, 11, 2.62, "obs", "泸西香葱 1.31 元/斤（中国报告大厅 2024-11-22）"),
    (2025, 6, 2.90, "inf", "2025 年上半年产地低位运行，季节性夏谷"),
    (2025, 11, 3.26, "obs", "泸西香葱 1.63 元/斤（中国报告大厅 2025-11-06 / 12-30）"),
    (2026, 4, 2.40, "inf", "2026 年春季供给高峰，产地延续低位"),
    (2026, 10, 2.62, "obs", "泸西香葱 1.31 元/斤（惠农网 2026-10-21）；同期精品净葱红香葱 4.35、黑葱 3.86 元/kg（10-23 泸西菜价）"),
]


def _mi(y: int, m: int) -> int:
    return y * 12 + m


def build_series(end: date | None = None, start_year: int = 2016, start_month: int = 10) -> list[dict]:
    """生成月频序列 [{ym, year, month, price, premium}]。"""
    end = end or date.today()
    a = sorted(ANCHORS, key=lambda x: _mi(x[0], x[1]))
    # 去季节化后的锚点
    pts = [(_mi(y, m), p / SEASON[m]) for y, m, p, _, _ in a]

    out = []
    idx = 0
    cur = _mi(start_year, start_month)
    last = _mi(end.year, end.month)
    while cur <= last:
        y, m = divmod(cur, 12)
        if m == 0:
            y -= 1
            m = 12
        # 定位区间
        while idx < len(pts) - 1 and pts[idx + 1][0] <= cur:
            idx += 1
        x0, v0 = pts[idx]
        if cur <= x0:
            level = v0
        elif idx + 1 < len(pts):
            x1, v1 = pts[idx + 1]
            w = (cur - x0) / float(x1 - x0)
            level = math.exp(math.log(v0) * (1 - w) + math.log(v1) * w)
        else:
            level = v0
        price = level * SEASON[m]
        out.append({"ym": f"{y:04d}-{m:02d}", "year": y, "month": m,
                    "price": round(price, 2), "premium": round(price * PREMIUM, 2)})
        cur += 1
    return out


def anchor_table() -> list[dict]:
    return [{"ym": f"{y:04d}-{m:02d}", "price": p, "kind": k, "note": n}
            for y, m, p, k, n in sorted(ANCHORS, key=lambda x: _mi(x[0], x[1]))]


def window_stats(series: list[dict], months: int) -> dict:
    """对最近 months 个月做窗口统计。"""
    seg = series[-months:]
    if len(seg) < 2:
        return {}
    start, end = seg[0]["price"], seg[-1]["price"]
    prices = [s["price"] for s in seg]
    n_years = (len(seg) - 1) / 12.0
    cagr = ((end / start) ** (1 / n_years) - 1) * 100 if n_years > 0 and start > 0 else 0.0
    rets = []
    for i in range(1, len(prices)):
        if prices[i - 1] > 0:
            rets.append(math.log(prices[i] / prices[i - 1]))
    vol = 0.0
    if len(rets) > 1:
        mu = sum(rets) / len(rets)
        var = sum((r - mu) ** 2 for r in rets) / (len(rets) - 1)
        vol = math.sqrt(var * 12) * 100
    hi = max(seg, key=lambda s: s["price"])
    lo = min(seg, key=lambda s: s["price"])
    return {
        "months": len(seg),
        "start_ym": seg[0]["ym"], "start": start,
        "end_ym": seg[-1]["ym"], "end": end,
        "change_pct": (end / start - 1) * 100,
        "cagr": cagr,
        "avg": sum(prices) / len(prices),
        "vol": vol,
        "hi": hi["price"], "hi_ym": hi["ym"],
        "lo": lo["price"], "lo_ym": lo["ym"],
        "amplitude": (hi["price"] / lo["price"] - 1) * 100 if lo["price"] > 0 else 0.0,
    }


WINDOWS = [(12, "近 12 个月"), (24, "近 24 个月"), (36, "近 36 个月"),
           (60, "近 60 个月"), (120, "近 120 个月（10 年）")]


def all_window_stats(series: list[dict]) -> list[dict]:
    out = []
    for m, label in WINDOWS:
        st = window_stats(series, m)
        if st:
            st["label"] = label
            out.append(st)
    return out


def yoy_table(series: list[dict], n: int = 12) -> list[dict]:
    """近 n 个月的同比（与 12 个月前对比）。"""
    out = []
    for i in range(len(series) - n, len(series)):
        cur = series[i]
        prev = series[i - 12]
        out.append({"ym": cur["ym"], "price": cur["price"], "prev": prev["price"],
                    "yoy": (cur["price"] / prev["price"] - 1) * 100 if prev["price"] else 0.0})
    return out


# ------------------------------------------------------------------ 图表
def svg_line(series: list[dict], anchors: list[dict] | None = None,
             months: int | None = None, width=960, height=330,
             title="香葱产地价长周期走势") -> str:
    seg = series[-months:] if months else series
    if len(seg) < 2:
        return "<p>数据点不足。</p>"
    vals = [s["price"] for s in seg] + [s["premium"] for s in seg]
    lo, hi = min(vals), max(vals)
    pad = max(0.3, (hi - lo) * 0.12)
    y_min, y_max = max(0.0, lo - pad), hi + pad

    ml, mr, mt, mb = 58, 96, 26, 44
    pw, ph = width - ml - mr, height - mt - mb

    def px(i):
        return ml + pw * i / (len(seg) - 1)

    def py(v):
        return mt + ph * (1 - (v - y_min) / (y_max - y_min))

    g = []
    for k in range(5):
        v = y_min + (y_max - y_min) * k / 4
        y = py(v)
        g.append(f'<line x1="{ml}" y1="{y:.1f}" x2="{width-mr}" y2="{y:.1f}" '
                 f'stroke="{"#c9d1da" if k==0 else "#e6eaf0"}" stroke-width="1"/>')
        g.append(f'<text x="{ml-8}" y="{y+4:.1f}" font-size="11" fill="#7b8595" '
                 f'text-anchor="end">{v:.1f}</text>')

    def poly(key, color, dash=""):
        pts = " ".join(f"{px(i):.1f},{py(s[key]):.1f}" for i, s in enumerate(seg))
        return (f'<polyline points="{pts}" fill="none" stroke="{color}" '
                f'stroke-width="2.2"{dash}/>')

    # 精品净葱填充带
    top = " ".join(f"{px(i):.1f},{py(s['premium']):.1f}" for i, s in enumerate(seg))
    bot = " ".join(f"{px(len(seg)-1-i):.1f},{py(seg[len(seg)-1-i]['price']):.1f}"
                   for i in range(len(seg)))
    area = f'<polygon points="{top} {bot}" fill="#0f6fd6" opacity="0.07"/>'

    # x 轴年份标签
    xt, last_year = [], None
    for i, s in enumerate(seg):
        if s["month"] == 1 or i == 0:
            if s["year"] != last_year:
                xt.append(f'<text x="{px(i):.1f}" y="{mt+ph+18:.1f}" font-size="10.5" '
                          f'fill="#5b6470" text-anchor="middle">{s["year"]}</text>')
                xt.append(f'<line x1="{px(i):.1f}" y1="{mt}" x2="{px(i):.1f}" '
                          f'y2="{mt+ph}" stroke="#eef1f5" stroke-width="1"/>')
                last_year = s["year"]

    # 锚点
    dots = []
    ym_index = {s["ym"]: i for i, s in enumerate(seg)}
    for a in (anchors or []):
        i = ym_index.get(a["ym"])
        if i is None:
            continue
        color = "#d93025" if a["kind"] == "obs" else "#c9ced6"
        r = 4.0 if a["kind"] == "obs" else 3.0
        dots.append(f'<circle cx="{px(i):.1f}" cy="{py(a["price"]):.1f}" r="{r}" '
                    f'fill="{color}" stroke="#ffffff" stroke-width="1"/>')

    lg = (f'<circle cx="{width-mr+10}" cy="{mt+16}" r="4" fill="#0f6fd6"/>'
          f'<text x="{width-mr+20}" y="{mt+20}" font-size="11.5" fill="#1c2024">通货毛葱</text>'
          f'<circle cx="{width-mr+10}" cy="{mt+38}" r="4" fill="#f0a500"/>'
          f'<text x="{width-mr+20}" y="{mt+42}" font-size="11.5" fill="#1c2024">精品净葱(×1.66)</text>'
          f'<circle cx="{width-mr+10}" cy="{mt+60}" r="4" fill="#d93025"/>'
          f'<text x="{width-mr+20}" y="{mt+64}" font-size="11.5" fill="#1c2024">实测锚点</text>'
          f'<circle cx="{width-mr+10}" cy="{mt+82}" r="3" fill="#c9ced6"/>'
          f'<text x="{width-mr+20}" y="{mt+86}" font-size="11.5" fill="#1c2024">推断锚点</text>')

    return "\n".join([
        f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" '
        f'role="img" aria-label="{title}">',
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="#ffffff"/>',
        *g, area,
        poly("premium", "#f0a500", ' stroke-dasharray="5 4"'),
        poly("price", "#0f6fd6"),
        *xt, *dots, lg, "</svg>"])


def svg_season(width=960, height=250, title="香葱月度季节指数") -> str:
    mean = sum(SEASON.values()) / 12.0
    ml, mr, mt, mb = 58, 20, 22, 44
    pw, ph = width - ml - mr, height - mt - mb
    y_max = 1.6
    bw = pw / 12.0

    def py(v):
        return mt + ph * (1 - v / y_max)

    g = []
    for k in range(5):
        v = y_max * k / 4
        y = py(v)
        g.append(f'<line x1="{ml}" y1="{y:.1f}" x2="{width-mr}" y2="{y:.1f}" '
                 f'stroke="{"#c9d1da" if k==0 else "#e6eaf0"}" stroke-width="1"/>')
        g.append(f'<text x="{ml-8}" y="{y+4:.1f}" font-size="11" fill="#7b8595" '
                 f'text-anchor="end">{v:.2f}</text>')
    # 均值线
    ym = py(mean)
    g.append(f'<line x1="{ml}" y1="{ym:.1f}" x2="{width-mr}" y2="{ym:.1f}" '
             f'stroke="#0f9960" stroke-width="1.5" stroke-dasharray="6 4"/>')

    bars = []
    for m in range(1, 13):
        v = SEASON[m]
        x = ml + bw * (m - 1) + bw * 0.18
        w = bw * 0.64
        y = py(v)
        color = "#d93025" if v > 1.08 else ("#0f9960" if v < 0.92 else "#8a93a0")
        bars.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" '
                    f'height="{mt+ph-y:.1f}" fill="{color}" opacity="0.82" rx="3"/>')
        bars.append(f'<text x="{x+w/2:.1f}" y="{y-5:.1f}" font-size="11" fill="#1c2024" '
                    f'text-anchor="middle">{v:.2f}</text>')
        bars.append(f'<text x="{x+w/2:.1f}" y="{mt+ph+18:.1f}" font-size="11" fill="#5b6470" '
                    f'text-anchor="middle">{m}月</text>')
    return "\n".join([
        f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" '
        f'role="img" aria-label="{title}">',
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="#ffffff"/>',
        *g, *bars, "</svg>"])


def svg_forecast_path(base: float, rows: list[dict], width=960, height=300,
                      title="红香葱（精品净葱口径）预测路径") -> str:
    """base=当前中枢，rows=预测档位。横轴按目标天数等距。"""
    xs = [0] + [r["days"] for r in rows]
    ys = [base] + [r["center"] for r in rows]
    los = [base] + [r["low"] for r in rows]
    his = [base] + [r["high"] for r in rows]
    lo, hi = min(los), max(his)
    pad = max(0.2, (hi - lo) * 0.25)
    y_min, y_max = max(0.0, lo - pad), hi + pad

    ml, mr, mt, mb = 58, 110, 28, 46
    pw, ph = width - ml - mr, height - mt - mb
    xmax = max(xs) or 1

    def px(v):
        return ml + pw * v / xmax

    def py(v):
        return mt + ph * (1 - (v - y_min) / (y_max - y_min))

    g = []
    for k in range(5):
        v = y_min + (y_max - y_min) * k / 4
        y = py(v)
        g.append(f'<line x1="{ml}" y1="{y:.1f}" x2="{width-mr}" y2="{y:.1f}" '
                 f'stroke="{"#c9d1da" if k==0 else "#e6eaf0"}" stroke-width="1"/>')
        g.append(f'<text x="{ml-8}" y="{y+4:.1f}" font-size="11" fill="#7b8595" '
                 f'text-anchor="end">{v:.1f}</text>')

    top = " ".join(f"{px(x):.1f},{py(h):.1f}" for x, h in zip(xs, his))
    bot = " ".join(f"{px(x):.1f},{py(l):.1f}" for x, l in reversed(list(zip(xs, los))))
    band = f'<polygon points="{top} {bot}" fill="#0f9960" opacity="0.12"/>'
    line = " ".join(f"{px(x):.1f},{py(y):.1f}" for x, y in zip(xs, ys))

    marks = []
    for x, y, r in zip(xs, ys, [None] + rows):
        marks.append(f'<circle cx="{px(x):.1f}" cy="{py(y):.1f}" r="4.2" fill="#0f9960"/>')
        marks.append(f'<text x="{px(x):.1f}" y="{py(y)-10:.1f}" font-size="11.5" '
                     f'fill="#1c2024" text-anchor="middle">{y:.2f}</text>')
    labels = [(0, "当前")]
    for r in rows:
        labels.append((r["days"], r["label"]))
    xt = []
    for x, lab in labels:
        xt.append(f'<text x="{px(x):.1f}" y="{mt+ph+18:.1f}" font-size="10.5" fill="#5b6470" '
                  f'text-anchor="middle">{lab}</text>')
    return "\n".join([
        f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" '
        f'role="img" aria-label="{title}">',
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="#ffffff"/>',
        *g, band,
        f'<polyline points="{line}" fill="none" stroke="#0f9960" stroke-width="2.5" '
        f'stroke-dasharray="7 5"/>',
        *marks, *xt, "</svg>"])


def build_longterm(end: date | None = None) -> dict:
    series = build_series(end=end)
    anchors = anchor_table()
    return {
        "series": series,
        "anchors": anchors,
        "obs_count": sum(1 for a in anchors if a["kind"] == "obs"),
        "inf_count": sum(1 for a in anchors if a["kind"] == "inf"),
        "windows": all_window_stats(series),
        "yoy": yoy_table(series, 12),
        "premium": PREMIUM,
        "season": SEASON,
    }


if __name__ == "__main__":
    lt = build_longterm()
    print("月频点数:", len(lt["series"]), "| 观测锚点:", lt["obs_count"],
          "| 推断锚点:", lt["inf_count"])
    for w in lt["windows"]:
        print(f"{w['label']}: {w['start_ym']} {w['start']:.2f} -> {w['end_ym']} "
              f"{w['end']:.2f} | {w['change_pct']:+.1f}% | CAGR {w['cagr']:+.1f}% | "
              f"波动 {w['vol']:.1f}% | 高 {w['hi']:.2f}({w['hi_ym']}) 低 {w['lo']:.2f}({w['lo_ym']})")
