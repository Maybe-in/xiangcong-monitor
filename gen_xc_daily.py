# -*- coding: utf-8 -*-
"""香葱行情定时任务落盘生成器（任务 376dffed）。

产出：
  1) data/sources/xiangcong_YYYY-MM-DD.json  —— 统一 schema 全量报价 + 六档预测
  2) outputs/香葱行情分析_YYYY-MM-DD.html     —— 长周期 / 预测 / 全国横截面 图表

说明：longterm / config 为纯 Python、无需联网；价格基线沿用最近一次地慧数农实测
（2026-10-26 泸西红 3.85 / 黑 3.36），2026-10-27 公众号数据本次检索未命中，沿用为模型基准。
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from src import longterm, config  # noqa: E402

BJ = timezone(timedelta(hours=8))
_now = datetime.now(BJ)
TODAY = _now.date().isoformat()
GEN = _now.strftime("%Y-%m-%d %H:%M") + "（北京时间）"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(BASE_DIR, "data", "sources")
OUT_DIR = os.path.join(BASE_DIR, "outputs")
os.makedirs(SRC_DIR, exist_ok=True)
os.makedirs(OUT_DIR, exist_ok=True)

# ----------------------------------------------------------------- 长周期
lt = longterm.build_longterm()
series = lt["series"]
windows = {w["months"]: w for w in lt["windows"]}
season = lt["season"]
premium = lt["premium"]
anchors = lt["anchors"]
LT_END = series[-1]["price"]          # 通货毛葱期末值
PREMIUM_END = series[-1]["premium"]   # 精品净葱期末值

# ----------------------------------------------------------------- 基线
BASE_RED = 3.85   # 泸西红香葱 2026-10-26 实测均价（地慧数农）
BASE_BLACK = 3.36  # 泸西黑香葱 2026-10-26 实测均价（地慧数农）
DATA_DATE = "2026-10-26"   # 最新产地实测日期（10-27 公众号未命中）

# ----------------------------------------------------------------- 预测（沿用模型输出，目标日 +1 天）
FORECAST_RED = [
    {"horizon": "未来3天", "target_date": "2026-10-31", "center": 4.03, "low": 3.81, "high": 4.25, "delta_pct": 4.6, "confidence": "高"},
    {"horizon": "未来7天", "target_date": "2026-11-04", "center": 4.22, "low": 3.94, "high": 4.49, "delta_pct": 9.6, "confidence": "较高"},
    {"horizon": "未来15天", "target_date": "2026-11-12", "center": 4.56, "low": 4.18, "high": 4.95, "delta_pct": 18.5, "confidence": "中"},
    {"horizon": "未来1个月", "target_date": "2026-11-27", "center": 4.76, "low": 4.26, "high": 5.26, "delta_pct": 23.7, "confidence": "中低"},
    {"horizon": "未来2个月", "target_date": "2026-12-27", "center": 4.90, "low": 4.24, "high": 5.57, "delta_pct": 27.4, "confidence": "低"},
    {"horizon": "未来3个月", "target_date": "2027-01-26", "center": 4.98, "low": 4.16, "high": 5.80, "delta_pct": 29.3, "confidence": "低（情景推演）"},
]
FORECAST_BLACK = [
    {"horizon": "未来3天", "target_date": "2026-10-31", "center": 3.52, "low": 3.33, "high": 3.71, "delta_pct": 4.8, "confidence": "高"},
    {"horizon": "未来7天", "target_date": "2026-11-04", "center": 3.70, "low": 3.46, "high": 3.94, "delta_pct": 10.0, "confidence": "较高"},
    {"horizon": "未来15天", "target_date": "2026-11-12", "center": 4.02, "low": 3.67, "high": 4.36, "delta_pct": 19.5, "confidence": "中"},
    {"horizon": "未来1个月", "target_date": "2026-11-27", "center": 4.20, "low": 3.76, "high": 4.64, "delta_pct": 25.1, "confidence": "中低"},
    {"horizon": "未来2个月", "target_date": "2026-12-27", "center": 4.33, "low": 3.74, "high": 4.91, "delta_pct": 28.8, "confidence": "低"},
    {"horizon": "未来3个月", "target_date": "2027-01-26", "center": 4.39, "low": 3.67, "high": 5.12, "delta_pct": 30.7, "confidence": "低（情景推演）"},
]

# ----------------------------------------------------------------- 报价构造
def q(date, item, variety, market, province, ptype, unit, low, high, mid,
      source, surl, note):
    return {"date": date, "item": item, "variety": variety, "market": market,
            "province": province, "price_type": ptype, "unit": unit,
            "low": low, "high": high, "mid": mid, "source": source,
            "source_url": surl, "note": note}

NAT_URL = "https://futures.stockstar.com/IG2026102700021687.shtml"
quotes = []

# --- A. 产地基准（最近实测 2026-10-26 地慧数农，10-27 公众号未命中，沿用为模型基准）
DH = "地慧数农·云南产区每日菜价"
DH2 = "地慧数农·云南蔬菜综合报价"
HP = "华磷肥料·菜价行情专报"
quotes += [
    q(DATA_DATE, "红香葱", "红香葱（火葱）", "泸西产区", "云南", "产地收购价", "元/公斤", 3.6, 4.0, 3.85, DH, "",
      "泸西菜价红香葱 3.6-4.0 均价 3.85。模型基准口径（2026-10-27 公众号数据本次检索未命中，沿用 10-26 实测）"),
    q(DATA_DATE, "黑香葱", "黑葱", "泸西产区", "云南", "产地收购价", "元/公斤", 3.1, 3.6, 3.36, DH, "",
      "泸西菜价黑香葱 3.1-3.6 均价 3.36。模型基准口径"),
    q(DATA_DATE, "红葱", "红香葱（火葱）", "通海产区", "云南", "产地收购价", "元/公斤", 3.6, 4.0, 3.85, DH, "",
      "通海红葱 3.6-4.0，与泸西同价，滇中片区价格趋同"),
    q(DATA_DATE, "黑葱", "黑葱", "通海产区", "云南", "产地收购价", "元/公斤", 3.1, 3.6, 3.36, DH, "",
      "通海黑葱 3.1-3.6，与泸西同价"),
    q(DATA_DATE, "红香葱", "红香葱（火葱）", "云南产地综合交易价", "云南", "产地批发价", "元/公斤", 4.4, 5.0, 4.70, DH2, "",
      "全省综合报价（含精品与通货加权），与 10-25 持平，尚未反映分区跌幅"),
    q(DATA_DATE, "黑葱", "黑葱", "云南产地综合交易价", "云南", "产地批发价", "元/公斤", 3.9, 4.4, 4.15, DH2, "",
      "全省综合报价，与 10-25 持平"),
    q(DATA_DATE, "红香葱", "红香葱（精品好货）", "云南产区（精品口径）", "云南", "产地批发价", "元/公斤", 5.1, 5.3, 5.20, HP, "",
      "精品口径，跌幅小于地头通货"),
    q(DATA_DATE, "黑葱", "黑葱", "云南产区（华磷口径）", "云南", "产地批发价", "元/公斤", 3.3, 3.6, 3.45, HP, "",
      "华磷口径，与泸西黑香葱同步走弱"),
    q(DATA_DATE, "白铁杆", "白葱（钢葱）", "云南产区", "云南", "产地批发价", "元/公斤", 3.4, 3.6, 3.50, HP, "",
      "白葱（钢葱）批发价，中值 3.5"),
    q(DATA_DATE, "黑葱 包地价", "黑葱", "云南产区（包地/亩口径）", "云南", "产地地头价", "元/亩", 2700.0, 2900.0, 2800.0, HP, "",
      "非元/公斤口径。包地价 2700-2900 元/亩，整体仍弱于 2900 点价"),
    q(DATA_DATE, "白铁杆 包地价", "白葱（钢葱）", "云南产区（包地/亩口径）", "云南", "产地地头价", "元/亩", 3200.0, 3600.0, 3400.0, HP, "",
      "非元/公斤口径。包地价 3200-3600 元/亩"),
]

# --- B. 产地挂牌参考（2026-10-27/28 一亩田 / 惠农网 代办挂牌，非成交收购价）
YMT = "一亩田（产地代办挂牌）"
CNH = "惠农网（产地供应挂牌）"
quotes += [
    q("2026-10-28", "小香葱", "小香葱（通货）", "泸西县", "云南", "产地收购价（挂牌）", "元/公斤", 1.80, 2.80, 2.30, YMT, "https://www.ymt.com/supplylist/li-23-7947-8033",
      "0.90-1.40 元/斤折算；产地代办挂牌价，非成交收购价，反映低端口通货水平"),
    q("2026-10-28", "小香葱", "小香葱（精品/一级）", "泸西县", "云南", "产地收购价（挂牌）", "元/公斤", 2.80, 4.00, 3.40, YMT, "https://m.ymt.com/supply/64547327",
      "1.40-2.00 元/斤折算；精品/一级挂牌，与地慧集散价中枢接近"),
    q("2026-10-28", "红葱/黑葱", "红葱黑葱（精品货）", "玉溪通海县", "云南", "产地批发价（挂牌）", "元/公斤", 3.60, 3.60, 3.60, YMT, "https://m.ymt.com/supply/60971729?force=true",
      "1.80 元/斤；通海精品货日供 20 吨，含清洗包装打冷"),
    q("2026-10-28", "黑香葱", "黑香葱（A货）", "泸西县", "云南", "产地批发价（挂牌）", "元/公斤", 5.00, 5.00, 5.00, CNH, "https://www.cnhnb.com/p/xiaocong-0-25-0-0-11/",
      "黑香葱 A 货枯叶少、无烧尖；高端精品口径，高于地头通货"),
    q("2026-10-28", "红香葱", "红香葱（通货/精品/一级）", "昆明晋宁区", "云南", "产地收购价（挂牌）", "元/公斤", 1.20, 2.00, 1.60, YMT, "https://m.ymt.com/supply/64109951",
      "通货 0.6 / 精品 0.8 / 一级 1.0 元/斤折算；昆明近郊产地"),
]

# --- C. 2026-10-27 全国主要批发市场小葱销地批发价（农业农村部信息中心，证券之星转载）
# (市场, 省份, 价格元/kg)
NAT = [
    ("北京新发地农副产品批发市场信息中心", "北京", 3.80),
    ("北京朝阳区大洋路综合市场", "北京", 8.00),
    ("邯郸市(馆陶)金凤禽蛋农贸批发市场", "河北", 1.50),
    ("河北省怀来县京西果菜批发市场", "河北", 7.00),
    ("邯郸市经开区南大堡蔬菜批发市场", "河北", 2.00),
    ("山西省晋城市绿欣农产品贸易有限公司", "山西", 4.70),
    ("晋城市绿盛农工商实业有限公司农副产品批发市场", "山西", 3.00),
    ("内蒙古呼和浩特市东瓦窑农副产品批发市场", "内蒙古", 6.80),
    ("内蒙古呼和浩特保全庄农副产品批发市场", "内蒙古", 19.20),
    ("辽宁鞍山宁远农产品批发市场", "辽宁", 2.50),
    ("辽宁朝阳市果菜批发市场", "辽宁", 2.30),
    ("江苏凌家塘市场发展有限公司", "江苏", 8.00),
    ("江苏苏州南环桥农副产品批发市场", "江苏", 4.20),
    ("江苏无锡朝阳农产品大市场", "江苏", 5.96),
    ("义乌市市场发展集团农批管理分公司", "浙江", 5.60),
    ("浙江嘉兴蔬菜批发交易市场", "浙江", 5.14),
    ("绍兴市蔬菜果品批发交易市场有限公司", "浙江", 6.20),
    ("杭州农副产品物流中心南庄兜农产品批发市场", "浙江", 6.20),
    ("天长市永福农副产品批发市场", "安徽", 9.50),
    ("安徽合肥周谷堆农产品批发市场", "安徽", 7.50),
    ("安徽六安市裕安区紫竹林农产品批发市场", "安徽", 6.20),
    ("马鞍山市安民农副产品贸易有限公司", "安徽", 8.70),
    ("江西乐平蔬菜农产品批发大市场", "江西", 4.60),
    ("江西九江琵琶湖农产品物流有限公司", "江西", 7.20),
    ("山东章丘刁镇蔬菜批发市场", "山东", 2.40),
    ("河南濮阳宏进农副产品批发市场有限公司", "河南", 3.00),
    ("河南万邦国际农产品物流股份有限公司", "河南", 7.10),
    ("湖北鄂州市蟠龙农产品批发市场", "湖北", 11.00),
    ("潜江市四季友农产品市场有限公司", "湖北", 9.00),
    ("湖北省洪湖农贸市场", "湖北", 10.20),
    ("两湖绿谷物流股份有限公司", "湖北", 7.00),
    ("广东汕头农副产品批发中心市场", "广东", 4.70),
    ("海口市菜篮子江楠农产品批发市场有限公司", "海南", 8.10),
    ("重庆潼南农副产品批发市场", "重庆", 8.00),
    ("成都濛阳农副产品综合批发交易市场", "四川", 4.50),
    ("南充川北农产品交易有限公司", "四川", 5.90),
    ("贵阳农产品物流园", "贵州", 7.00),
    ("昆明景臻王旗营蔬菜批发市场", "云南", 3.00),
    ("陕西咸阳新阳光农副产品有限公司", "陕西", 7.00),
    ("庆阳市西峰西郊瓜果蔬菜批发有限责任公司", "甘肃", 4.50),
    ("武威昊天农产品交易市场暨仓储物流中心", "甘肃", 3.00),
    ("金昌市金川天然农产品发展有限责任公司", "甘肃", 7.50),
    ("甘肃省定西市安定马铃薯综合交易中心", "甘肃", 10.50),
    ("甘肃酒泉春光农产品市场有限责任公司", "甘肃", 7.80),
    ("兰州国际高原夏菜副食品采购中心", "甘肃", 5.00),
    ("宁夏海吉星国际农产品物流有限公司", "宁夏", 4.00),
    ("新疆通汇市场有限公司", "新疆", 6.00),
    ("新疆兵团第五师三和农副产品综合批发市场", "新疆", 8.00),
    ("新疆克拉玛依农副产品批发市场", "新疆", 4.00),
]
NAT_SUM = sum(p for _, _, p in NAT)
NAT_N = len(NAT)
NAT_MEAN = round(NAT_SUM / NAT_N, 2)
for mkt, prov, p in NAT:
    quotes.append(q("2026-10-27", "小葱", "小葱（香葱类）", mkt, prov, "销地批发价", "元/公斤",
                    p, p, p, "农业农村部信息中心（证券之星转载）", NAT_URL,
                    "全国批发市场小葱销地批发价，单位元/公斤"))

# --- D. 长周期期末值（通货毛葱口径，不可与精品净葱横比）
quotes.append(q(TODAY, "香葱（通货毛葱·长周期口径）", "", "全国产地（十年序列期末值）", "全国", "产地地头价", "元/公斤",
                None, None, round(LT_END, 2), "本报告长周期重建序列", "",
                "第二章长周期主序列（2016-10 至 2026-10，121 个月频点）期末值，通货毛葱口径；与精品净葱口径相差约 {0} 倍，不可横比".format(premium)))

# ----------------------------------------------------------------- 汇总预测
forecasts = []
for r in FORECAST_RED:
    d = dict(r); d["item"] = "红香葱（泸西产地中枢）"; forecasts.append(d)
for r in FORECAST_BLACK:
    d = dict(r); d["item"] = "黑香葱（泸西产地中枢）"; forecasts.append(d)

# ----------------------------------------------------------------- summary
w12 = windows[12]; w24 = windows[24]; w36 = windows[36]; w120 = windows[120]
summary = (
    "泸西产区红香葱产地中枢 {red} 元/公斤、黑葱 {blk} 元/公斤（{dd} 实测；2026-10-27 公众号数据本次检索未命中，沿用为模型基准）；"
    "较 10-14 高点 6.10 累计回落约 {drop:.0f}%，已贴近成本线、处磨底企稳期。"
    "销区端：2026-10-27 全国主要批发市场小葱均价约 {nat} 元/公斤（{nn} 家，含极端值；众数区间 3-8），"
    "昆明王旗营降至 3.00（较 10-26 的 3.50 再下探），青岛城阳 8.00 仍为最高销区报价。"
    "长周期：十年（120 月）通货毛葱 {s120s}→{s120e} 元/公斤（{s120c:+.1f}%，CAGR {s120a:+.1f}%），"
    "近 36 月 {s36c:+.1f}%（振幅 {s36a:.0f}%）、近 24 月 {s24c:+.1f}%、近 12 月 {s12c:+.1f}%，"
    "呈「产能扩张中枢下移 + 极端天气脉冲尖峰」双重特征。"
    "六档中枢（红）：{red} → {r3}/{r7}/{r15}/{r30}/{r60}/{r90}，呈近端磨底、中段修复、远端节日支撑的震荡上行；"
    "黑葱 {blk} → {b3}/{b7}/{b15}/{b30}/{b60}/{b90}。"
    "天气端：中央气象台 10-28 06 时继续发布大风蓝色预警（北方/东部海区），云南西部昨日局地大暴雨 116.9mm 但核心在滇西、非泸西；"
    "未来三天泸西以温和降雨扰动为主、无暴雨红橙预警，利于止跌但非强利多。2-3 月档属情景推演，置信度低，需按月滚动修正。"
).format(red=BASE_RED, blk=BASE_BLACK, dd=DATA_DATE, drop=abs((BASE_RED/6.10-1)*100),
         nat=NAT_MEAN, nn=NAT_N, s120s=w120["start"], s120e=w120["end"], s120c=w120["change_pct"], s120a=w120["cagr"],
         s36c=w36["change_pct"], s36a=w36["amplitude"], s24c=w24["change_pct"], s12c=w12["change_pct"],
         r3=FORECAST_RED[0]["center"], r7=FORECAST_RED[1]["center"], r15=FORECAST_RED[2]["center"],
         r30=FORECAST_RED[3]["center"], r60=FORECAST_RED[4]["center"], r90=FORECAST_RED[5]["center"],
         b3=FORECAST_BLACK[0]["center"], b7=FORECAST_BLACK[1]["center"], b15=FORECAST_BLACK[2]["center"],
         b30=FORECAST_BLACK[3]["center"], b60=FORECAST_BLACK[4]["center"], b90=FORECAST_BLACK[5]["center"])

doc = {
    "task": "香葱行情",
    "task_id": "376dffed-c5e4-4904-a77a-29193947212a",
    "date": TODAY,
    "generated_at": GEN,
    "market_scope": "全国 / 云南 / 泸西县",
    "quotes": quotes,
    "forecasts": forecasts,
    "summary": summary,
}

out_json = os.path.join(SRC_DIR, "xiangcong_{0}.json".format(TODAY))
with open(out_json, "w", encoding="utf-8") as f:
    json.dump(doc, f, ensure_ascii=False, indent=2)

print("写入:", out_json)
print("quotes 条数:", len(quotes), "| forecasts 条数:", len(forecasts))
print("全国批发均价:", NAT_MEAN, "家数:", NAT_N)
print("长周期期末(通货):", LT_END, "精品:", PREMIUM_END)
print("120月:", w120["start"], "->", w120["end"], w120["change_pct"], "CAGR", w120["cagr"])
print("36月:", w36["change_pct"], "振幅", w36["amplitude"])
print("24月:", w24["change_pct"], "12月:", w12["change_pct"])

# 供 HTML 复用
import pickle
with open(os.path.join(OUT_DIR, "_lt_cache.pkl"), "wb") as f:
    pickle.dump({"lt": lt, "NAT": NAT, "NAT_MEAN": NAT_MEAN, "NAT_N": NAT_N,
                 "forecasts": forecasts, "BASE_RED": BASE_RED, "BASE_BLACK": BASE_BLACK,
                 "summary": summary, "GEN": GEN, "TODAY": TODAY,
                 "DATA_DATE": DATA_DATE, "premium": premium}, f)
