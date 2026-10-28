# -*- coding: utf-8 -*-
"""渲染香葱行情分析 HTML（图表 + 长周期 + 全国横截面 + 泸西专题）。"""
import os, pickle, json
from datetime import datetime, timezone, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "outputs")
CACHE = os.path.join(OUT, "_lt_cache.pkl")
with open(CACHE, "rb") as f:
    C = pickle.load(f)

from src import longterm, config

lt = C["lt"]; series = lt["series"]; season = lt["season"]; premium = C["premium"]
NAT = C["NAT"]; NAT_MEAN = C["NAT_MEAN"]; NAT_N = C["NAT_N"]
forecasts = C["forecasts"]; BASE_RED = C["BASE_RED"]; BASE_BLACK = C["BASE_BLACK"]
summary = C["summary"]; GEN = C["GEN"]; TODAY = C["TODAY"]; DATA_DATE = C["DATA_DATE"]

w = {x["months"]: x for x in lt["windows"]}

# ---- SVG 图
svg_10y = longterm.svg_line(series, anchors=lt["anchors"])
svg_36 = longterm.svg_line(series, months=36, title="香葱产地价近 36 个月走势")
svg_12 = longterm.svg_line(series, months=12, title="香葱产地价近 12 个月走势")
svg_season = longterm.svg_season()

# 预测路径（红香葱）
fmap = {(r["horizon"], r["item"]): r for r in forecasts}
DAYS = {"未来3天": 3, "未来7天": 7, "未来15天": 15, "未来1个月": 30, "未来2个月": 60, "未来3个月": 90}
red_rows = []
for h in ["未来3天", "未来7天", "未来15天", "未来1个月", "未来2个月", "未来3个月"]:
    r = fmap[(h, "红香葱（泸西产地中枢）")]
    red_rows.append({"days": DAYS[h], "label": h.replace("未来", ""), "center": r["center"],
                     "low": r["low"], "high": r["high"]})
svg_fc = longterm.svg_forecast_path(BASE_RED, red_rows)

# ---- 省份汇总
prov = {}
for mkt, p, price in NAT:
    prov.setdefault(p, []).append(price)
prov_rows = []
for p, lst in sorted(prov.items(), key=lambda kv: -sum(kv[1]) / len(kv[1])):
    av = sum(lst) / len(lst)
    prov_rows.append((p, len(lst), round(min(lst), 2), round(max(lst), 2), round(av, 2)))

# ---- 六档预测表
def fc_block(name, item):
    rows = [forecasts[i] for i in range(len(forecasts)) if forecasts[i]["item"] == item]
    body = ""
    for r in rows:
        cls = "up" if r["delta_pct"] > 0 else "flat"
        body += ("<tr><td>{h}</td><td>{td}</td><td class='c'>{c}</td>"
                 "<td class='c'>{lo}–{hi}</td><td class='c {cls}'>{d:+.1f}%</td>"
                 "<td>{cf}</td></tr>").format(
            h=r["horizon"], td=r["target_date"], c=r["center"], lo=r["low"], hi=r["high"],
            d=r["delta_pct"], cls=cls, cf=r["confidence"])
    return ("<h3>{name}（当前中枢 {b} 元/公斤，{dd} 实测）</h3>"
            "<table><thead><tr><th>周期</th><th>目标日</th><th>中枢</th><th>区间</th>"
            "<th>较基准</th><th>置信度</th></tr></thead><tbody>{body}</tbody></table>").format(
        name=name, b=BASE_RED if "红" in item else BASE_BLACK, dd=DATA_DATE, body=body)

fc_html = fc_block("红香葱", "红香葱（泸西产地中枢）") + fc_block("黑香葱", "黑香葱（泸西产地中枢）")

# ---- 种类表
var_html = "<table><thead><tr><th>商品分类</th><th>特征</th><th>主要用途</th></tr></thead><tbody>"
for v in config.VARIETIES:
    var_html += "<tr><td><b>{n}</b></td><td>{d}</td><td>{u}</td></tr>".format(n=v["name"], d=v["desc"], u=v["use"])
var_html += "</tbody></table>"

cul_html = "<table><thead><tr><th>栽培品种</th><th>特性</th><th>主产区</th><th>产量</th></tr></thead><tbody>"
for c in config.CULTIVARS:
    cul_html += "<tr><td>{n}</td><td>{t}</td><td>{a}</td><td>{y}</td></tr>".format(
        n=c["name"], t=c["trait"], a=c["area"], y=c["yield"])
cul_html += "</tbody></table>"

# ---- 省份表
prov_html = "<table><thead><tr><th>省份</th><th>重点县市</th><th>规模</th><th>季节</th></tr></thead><tbody>"
for p in config.PROVINCES:
    prov_html += ("<tr><td><b>{p}</b></td><td>{c}</td><td>{s}</td><td>{se}</td></tr>").format(
        p=p["province"], c=p["counties"], s=p["scale"], se=p["season"])
prov_html += "</tbody></table>"

# ---- 全国横截面表（省份汇总 + 明细）
prov_sum_html = ("<table><thead><tr><th>省份</th><th>市场数</th><th>最低</th><th>最高</th>"
                 "<th>均价</th></tr></thead><tbody>")
for p, n, lo, hi, av in prov_rows:
    prov_sum_html += "<tr><td>{p}</td><td class='c'>{n}</td><td class='c'>{lo}</td><td class='c'>{hi}</td><td class='c'><b>{av}</b></td></tr>".format(
        p=p, n=n, lo=lo, hi=hi, av=av)
prov_sum_html += "</tbody></table>"

nat_detail = "<div class='scroll'>"
for mkt, p, price in NAT:
    nat_detail += "<div class='row'><span>{m}</span><span class='tag'>{p}</span><span class='num'>{pr} 元/kg</span></div>".format(
        m=mkt, p=p, pr=price)
nat_detail += "</div>"

# ---- KPI
kpi = """
<div class="kpis">
  <div class="kpi"><div class="v">{red}</div><div class="l">泸西红香葱中枢(元/kg)</div><div class="s">{dd} 实测 · 模型基准</div></div>
  <div class="kpi"><div class="v">{blk}</div><div class="l">泸西黑香葱中枢(元/kg)</div><div class="s">{dd} 实测</div></div>
  <div class="kpi"><div class="v">{nat}</div><div class="l">全国批发均价(元/kg)</div><div class="s">{nn} 家市场 · 10-27</div></div>
  <div class="kpi"><div class="v">{lt}</div><div class="l">十年期末通货(元/kg)</div><div class="s">精品净葱 {pre}</div></div>
  <div class="kpi"><div class="v">{drop:.0f}%</div><div class="l">较 10-14 高点累计回落</div><div class="s">6.10 → {red}</div></div>
</div>""".format(red=BASE_RED, blk=BASE_BLACK, nat=NAT_MEAN, nn=NAT_N, lt=series[-1]["price"],
               pre=series[-1]["premium"], drop=abs((BASE_RED/6.10-1)*100), dd=DATA_DATE)

# ---- 泸西专题
luxi = config.CORE_REGION
luxi_html = """
<div class="card">
  <h3>七、泸西县专题（全国最大香葱单品基地）</h3>
  <div class="grid">
    <div><b>种植基地</b> {bm} 万亩</div>
    <div><b>复种面积</b> {rm} 万亩次</div>
    <div><b>年产量</b> {ao} 万吨</div>
    <div><b>年产值</b> {av} 亿元</div>
    <div><b>占云南</b> {sy:.0f}%</div>
    <div><b>日外运</b> {ds} 吨</div>
  </div>
  <p>低纬度高原气候实现全年轮番种植；水肥一体化使单人管理面积由 5-6 亩提升至 30 亩；建成制冰—清洗—冷藏—分拣—包装—运输完整加工链，附加值提升约 3 倍；《泸西小香葱生产规程》为国内该品类产品标准；曾为 G20 杭州峰会、杭州亚运会蔬菜直供基地；销售覆盖 20 省市 100 余城并出口马来西亚、新加坡、泰国。</p>
  <p><b>当前判断：</b>红香葱 {red}、黑香葱 {blk}（{dd} 实测）已贴近成本线，处磨底企稳期；六档中枢呈「近端磨底、中段修复、远端节日支撑」震荡上行，2027 年春节（2 月 6 日）前备货是确定性较高的季节性利多。</p>
</div>""".format(bm=luxi["base_mu"]/10000, rm=luxi["replant_mu"]/10000, ao=luxi["annual_output_t"]/10000,
               av=luxi["annual_value_yi"], sy=luxi["share_of_yunnan"]*100, ds=luxi["daily_shipment_t"],
               red=BASE_RED, blk=BASE_BLACK, dd=DATA_DATE)

# ---- 天气/灾害
weather_html = """
<div class="card warn">
  <h3>三、天气与自然灾害（2026-10-28 中央气象台）</h3>
  <ul>
    <li><b>大风蓝色预警</b>（10-28 06 时继续发布）：甘肃河西、宁夏北部、内蒙古大部、山西北部、河北北部、辽宁中西部 5-7 级风、阵风 8-9 级；东海、台湾海峡等海域 7-8 级、阵风 9 级——影响北方陆运与海上运输。</li>
    <li><b>云南降雨</b>：昨日云南西部、贵州西部出现大雨或暴雨，云南西部局地大暴雨（116.9mm）；10-28 云南西南部中到大雨。泸西位于云南东南，处降雨外围、非暴雨核心，采收扰动温和。</li>
    <li><b>29-31 日</b>：西藏南部强雨雪（暴雪到大暴雪，局地特大暴雪），非香葱产区，影响极小；新一股冷空气影响内蒙古东北、东北、华北北部，降温 4-8℃、局地 10℃以上。</li>
    <li><b>结论</b>：全国生效预警以大风为主，云南产区无暴雨红/橙预警；温和降雨利于止跌但非强利多，产区供给仍充裕。</li>
  </ul>
</div>"""

# ---- 风险
risk_html = """
<div class="card">
  <h3>八、风险提示</h3>
  <ul>
    <li><b>极端天气缺位（最大下行风险）</b>：厄尔尼诺下 11 月江南、西南降水偏多未兑现，产区持续晴好 → 下修半月/一月预测 3-8 个百分点。</li>
    <li><b>强降雨/渍涝超预期</b>：上调涨幅，同时关注采收与运输中断。</li>
    <li><b>销区本地菜持续替代</b>：中东部本地秋菜上市压制云南外调菜份额。</li>
    <li><b>冬季阶段性强寒潮/雨雪冰冻</b>：12 月-次年 2 月或阶段性跳涨 15%-30%，但阻断运输、持续短。</li>
    <li><b>云南单极供给下的集中上市踩踏</b>：冬季全国高度依赖云南，若天气持续利好、茬口集中，12-1 月或现供给洪峰压制涨幅。</li>
    <li><b>2-3 月档属情景推演</b>，置信度低，需按月滚动修正。</li>
  </ul>
</div>"""

# ---- 长周期文字
def wf(m):
    x = w[m]
    return ("{m}个月（{s}→{e}）：{st:.2f}→{en:.2f} 元/kg，{c:+.1f}%，CAGR {a:+.1f}%，"
            "区间高 {hi:.2f}（{hiy}）低 {lo:.2f}（{loy}），振幅 {amp:.0f}%").format(
        m=m, s=x["start_ym"], e=x["end_ym"], st=x["start"], en=x["end"], c=x["change_pct"],
        a=x["cagr"], hi=x["hi"], hiy=x["hi_ym"], lo=x["lo"], loy=x["lo_ym"], amp=x["amplitude"])
longterm_txt = ("把视线拉长到十年，香葱产地价整体呈「产能扩张驱动的中枢下移 + 极端天气驱动的脉冲式尖峰」双重特征。"
                + wf(120) + "。分窗口：" + wf(12) + "；" + wf(24) + "；" + wf(36) + "；" + wf(60) + "。"
                "十年最高峰出现在 {hiy} 的 {hi:.2f} 元/kg（泸西小香葱产地价一度报 6 元/斤），最低谷出现在 {loy} 的 {lo:.2f} 元/kg（疫情冲击叠加夏谷），峰谷倍数约 {pk:.1f} 倍，属典型高波动小宗调味菜。"
                "中枢下移主因是产能扩张：泸西至 2024 年底已形成年产 118 万吨、产值 35-36 亿元的全国最大蔬菜单品基地，叠加水肥一体化降本，长期价格重心系统性下移。"
                ).format(hi=w[120]["hi"], hiy=w[120]["hi_ym"], lo=w[120]["lo"], loy=w[120]["lo_ym"],
                         pk=w[120]["hi"]/w[120]["lo"] if w[120]["lo"] else 0)

season_txt = ("春峰（4-5 月）季节指数 1.25/1.16、冬旺（11-1 月）1.09-1.14，夏谷（7-8 月）仅 0.68-0.72，峰值/谷值约 1.8 倍。"
              "当前 10 月指数 1.03，处过渡窗口，但供给节奏压制了季节性涨幅。")

HTML = """<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>香葱行情分析 · {t}</title>
<style>
*{{box-sizing:border-box}}
body{{font-family:-apple-system,'Segoe UI','PingFang SC','Microsoft YaHei',sans-serif;margin:0;background:#f4f6f9;color:#1c2024;line-height:1.6}}
.wrap{{max-width:1080px;margin:0 auto;padding:24px 18px 60px}}
header{{background:linear-gradient(135deg,#0f6fd6,#0f9960);color:#fff;border-radius:14px;padding:26px 28px;margin-bottom:18px}}
header h1{{margin:0 0 6px;font-size:24px}}
header .meta{{opacity:.92;font-size:13px}}
h2{{font-size:19px;margin:30px 0 12px;padding-left:11px;border-left:5px solid #0f6fd6}}
h3{{font-size:16px;margin:16px 0 8px;color:#0f4f9e}}
.card{{background:#fff;border-radius:12px;padding:18px 20px;margin:14px 0;box-shadow:0 1px 4px rgba(20,40,80,.07)}}
.kpis{{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin:16px 0}}
.kpi{{background:#fff;border-radius:12px;padding:16px 10px;text-align:center;box-shadow:0 1px 4px rgba(20,40,80,.07)}}
.kpi .v{{font-size:26px;font-weight:700;color:#0f6fd6}}
.kpi .l{{font-size:12.5px;color:#5b6470;margin-top:4px}}
.kpi .s{{font-size:11px;color:#9aa3ad;margin-top:2px}}
table{{width:100%;border-collapse:collapse;font-size:13px;margin:8px 0}}
th,td{{border:1px solid #e6eaf0;padding:7px 9px;text-align:left}}
th{{background:#eef3f9;color:#33414f;font-weight:600}}
td.c{{text-align:center}}
.up{{color:#d93025;font-weight:600}}
.flat{{color:#0f9960;font-weight:600}}
.tag{{display:inline-block;background:#eef3f9;color:#33414f;border-radius:5px;padding:1px 7px;font-size:11px;margin-left:8px}}
.scroll{{max-height:300px;overflow:auto;border:1px solid #e6eaf0;border-radius:8px}}
.row{{display:flex;justify-content:space-between;padding:6px 10px;border-bottom:1px solid #f0f3f7;font-size:13px}}
.row .num{{color:#0f6fd6;font-weight:600}}
.warn{{border-left:5px solid #f0a500}}
.note{{font-size:12.5px;color:#7b8595;background:#fafbfc;border-radius:8px;padding:10px 12px;margin-top:8px}}
svg{{display:block;margin:6px auto}}
.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:10px 0}}
.grid div{{background:#f6f9fc;border-radius:8px;padding:10px;font-size:13.5px}}
@media(max-width:760px){{.kpis{{grid-template-columns:repeat(2,1fr)}}.grid{{grid-template-columns:repeat(2,1fr)}}}}
</style></head><body><div class="wrap">
<header><h1>香葱行情分析 · 全国 / 云南 / 泸西县</h1>
<div class="meta">生成时间：{g} ｜ 数据日期：产地实测 {dd}（10-27 公众号未命中，沿用为基准）｜ 销区横截面 2026-10-27 ｜ 长周期期末 2026-10</div></header>

<h2>一、速览</h2>
{kpi}
<div class="card"><p>{sum}</p></div>

<h2>二、历史长周期（12 / 24 / 36 个月 → 10 年）</h2>
<div class="card"><p>{ltxt}</p>
<div class="note">口径：主序列为云南泸西/滇中南产地通货毛葱价（元/kg）；精品净葱 = 通货 × {pre}。长周期含 {obs} 个实测锚点 + {inf} 个推断锚点，序列在锚点月份精确命中。</div>
{svg10y}{svg36}{svg12}
<h3>季节指数</h3><p>{stxt}</p>{svgseason}</div>

<h2>三、天气与自然灾害</h2>
{weather}

<h2>四、常见香葱种类</h2>
<div class="card"><h3>流通端商品分类</h3>{var}{cul}</div>

<h2>五、全国香葱种植省份</h2>
<div class="card">{prov}</div>

<h2>六、全国行情与预测</h2>
<div class="card"><h3>6.1 2026-10-27 全国主要批发市场小葱销地横截面</h3>
<p>共 {nn} 家市场，均价 <b>{nat}</b> 元/kg（含极端值；众数区间 3-8）；昆明王旗营 3.00（较 10-26 的 3.50 再下探），青岛城阳 8.00 仍为最高销区报价。</p>
<h4>省份汇总</h4>{provsum}
<h4>市场明细（滚动查看）</h4>{natdetail}</div>
<div class="card"><h3>6.2 六档价格预测（泸西产地中枢）</h3>{fc}{svgfc}
<div class="note">预测口径为精品净葱/产地集散价，与第二章通货毛葱口径相差约 {pre} 倍，不可直接横比。2-3 月档属情景推演，置信度低。</div></div>

<h2>七、泸西县专题</h2>
{luxi}

<h2>八、风险提示</h2>
{risk}

<div class="note">数据来源：地慧数农（云南产区每日菜价/蔬菜综合报价）、华磷肥料菜价行情专报、农业农村部信息中心（证券之星转载）、一亩田/惠农网产地挂牌、中央气象台天气公报、泸西小香葱产业资料。本报告为行情分析与预测，不构成投资建议。</div>
</div></body></html>""".format(
    t=TODAY, g=GEN, dd=DATA_DATE, kpi=kpi, sum=summary, ltxt=longterm_txt, pre=premium,
    svg10y=svg_10y, svg36=svg_36, svg12=svg_12, stxt=season_txt, svgseason=svg_season,
    weather=weather_html, var=var_html, cul=cul_html, prov=prov_html, nn=NAT_N, nat=NAT_MEAN,
    provsum=prov_sum_html, natdetail=nat_detail, fc=fc_html, svgfc=svg_fc, luxi=luxi_html,
    risk=risk_html, obs=lt["obs_count"], inf=lt["inf_count"])

out_html = os.path.join(OUT, "香葱行情分析_{0}.html".format(TODAY))
with open(out_html, "w", encoding="utf-8") as f:
    f.write(HTML)
print("写入:", out_html, "大小", len(HTML), "字节")
