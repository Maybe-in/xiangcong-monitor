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
    day_txt, move_txt = "—", "样本不足，暂不给出方向判断"
    if len(pts) >= 2:
        last3 = pts[-3:]
        diffs = [round(b["price"] - a["price"], 2) for a, b in zip(last3, last3[1:])]
        up_n = sum(1 for d in diffs if d > 0.005)
        dn_n = sum(1 for d in diffs if d < -0.005)
        if up_n and not dn_n:
            day_txt = "温和回升"
        elif dn_n and not up_n:
            day_txt = "延续下行"
        elif up_n and dn_n:
            day_txt = "震荡整理"
        else:
            day_txt = "磨底企稳"
        move_txt = "近 {0} 个采集日：{1} → {2} 元/kg".format(
            len(last3), num(last3[0]["price"]), num(last3[-1]["price"]))
    streak = ""
    if len(pts) >= 2:
        d = round(pts[-1]["price"] - pts[-2]["price"], 2)
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
