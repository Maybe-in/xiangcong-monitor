# -*- coding: utf-8 -*-
"""香葱行情定时任务落盘 + 图表报告生成器（任务 376dffed）。

产出：
  1) data/sources/xiangcong_2026-10-30.json  统一 schema 全量报价 + 六档预测
  2) outputs/香葱行情分析_2026-10-30.html     长周期 / 全国横截面 / 预测 图表

注意（代码坑）：f-string 内禁止嵌套 ASCII 引号，中文文案统一使用「」。
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from src import longterm, config, price  # noqa: E402

BJ = timezone(timedelta(hours=8))
_now = datetime.now(BJ)
TODAY = _now.date().isoformat()
GEN = _now.strftime("%Y-%m-%d %H:%M")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(BASE_DIR, "data", "sources")
OUT_DIR = os.path.join(BASE_DIR, "outputs")
os.makedirs(SRC_DIR, exist_ok=True)
os.makedirs(OUT_DIR, exist_ok=True)

DATA_DATE = "2026-10-29"   # 最新可获取的实测报价日（当日数据次日发布）

# ============================================================ 1. 长周期
lt = longterm.build_longterm()
series = lt["series"]
windows = {w["months"]: w for w in lt["windows"]}
season = lt["season"]
PREMIUM = lt["premium"]

# ============================================================ 2. 天气
wx = json.load(open(os.path.join(BASE_DIR, "data", "weather_2026-10-30.json"), encoding="utf-8"))
core_daily = [d for d in wx["core"]["daily"] if d.get("tmax") is not None]
clim = wx["core"].get("climatology") or {}
w3, w7, wh, wm = (wx["core"]["windows"].get(k, {}) for k in ("d3", "w1", "h1", "m1"))

# ============================================================ 3. 六档预测（模型）
history = price.load_history()
fc = price.build_forecast(history, core_daily, clim=clim)
FRED = fc["红香葱"]
FBLK = fc["黑葱"]
BASE_RED = FRED["current"]
BASE_BLACK = FBLK["current"]

# 模型内部 label → 任务 schema 要求的档位名
HORIZON_MAP = [("d3", "未来3天"), ("w1", "未来7天"), ("h1", "未来15天"),
               ("m1", "未来1个月"), ("m2", "未来2个月"), ("m3", "未来3个月")]
CANON = dict(HORIZON_MAP)


def horizon_rows(blk):
    return {r["key"]: r for r in blk["rows"]}


RRED = horizon_rows(FRED)
RBLK = horizon_rows(FBLK)

FORECASTS = []
for key, label in HORIZON_MAP:
    r = RRED[key]
    b = RBLK[key]
    FORECASTS.append({
        "horizon": label,
        "target_date": r["target_date"],
        "item": "香葱",
        "variety": "泸西红香葱（精品净葱/集散价口径）",
        "center": r["center"], "low": r["low"], "high": r["high"],
        "delta_pct": r["delta_pct"], "confidence": r["confidence"],
        "note": "黑葱同档中枢 {0} 元/公斤（{1:+.1f}%）；区间为情景区间，非统计置信区间".format(
            b["center"], b["delta_pct"]),
    })

# ============================================================ 4. 全量报价
def Q(date, item, variety, market, province, ptype, low, high, mid, source, url="", note=""):
    return {"date": date, "item": item, "variety": variety, "market": market,
            "province": province, "price_type": ptype, "unit": "元/公斤",
            "low": low, "high": high, "mid": mid,
            "source": source, "source_url": url, "note": note}


QUOTES = []
A = QUOTES.append

WX_URL = "http://mp.weixin.qq.com/s?__biz=MzU5MTc0MTM0MA==&mid=2247595847&idx=1&sn=0e0f9e8358fe84c2fb162b60d70c8eb3"
DH_URL = "http://mp.weixin.qq.com/s?__biz=Mzg3Mzg1MTgwNw==&mid=2247490569&idx=1&sn=30d34c71c5fe7f7c75e5bff6fdc3d902"

# —— 泸西核心产区（10-29 实测，模型基准口径）
A(Q("2026-10-29", "香葱", "红香葱", "云南红河州泸西县", "云南", "产地收购价",
    3.6, 4.0, 3.85, "云南蔬菜主产区每日菜价（泸西菜价表）", WX_URL,
    "本期基准。泸西红香葱 3.6-4.0、均价 3.85，行情简报标注「小香葱平稳」。较 10-26 的 3.85 持平，连续两个报价日横盘"))
A(Q("2026-10-29", "香葱", "黑香葱", "云南红河州泸西县", "云南", "产地收购价",
    3.1, 3.6, 3.36, "云南蔬菜主产区每日菜价（泸西菜价表）", WX_URL,
    "泸西黑香葱 3.1-3.6、均价 3.36，与 10-26 的 3.36 持平"))
A(Q("2026-10-29", "香葱", "红香葱", "云南产地综合交易价（全省）", "云南", "产地批发价",
    3.6, 4.0, 3.80, "云南蔬菜综合报价（10-29）", DH_URL,
    "全省综合报价红香葱 3.6-4.0，与泸西产区同区间，滇中价格完全趋同"))
A(Q("2026-10-29", "香葱", "黑葱", "云南产地综合交易价（全省）", "云南", "产地批发价",
    3.1, 3.6, 3.35, "云南蔬菜综合报价（10-29）", DH_URL,
    "全省综合报价黑葱 3.1-3.6"))
A(Q("2026-10-29", "香葱", "红葱", "云南玉溪市通海县", "云南", "产地收购价",
    3.6, 4.0, 3.80, "云南蔬菜主产区每日菜价（通海菜价表）", WX_URL,
    "通海红葱 3.6-4.0，与泸西完全一致"))
A(Q("2026-10-29", "香葱", "黑葱", "云南玉溪市通海县", "云南", "产地收购价",
    3.1, 3.6, 3.35, "云南蔬菜主产区每日菜价（通海菜价表）", WX_URL,
    "通海黑葱 3.1-3.6"))

# —— 泸西地头大宗价（权威实地采集源，T-1）
A(Q("2026-10-28", "香葱", "小葱（统货）", "红河州泸西县（地头大宗价）", "云南", "产地地头价",
    4.5, 5.5, 5.00, "国资云农（云南省国资云农信息团队每日产地采集）", "",
    "10-28 大宗价 5.00（区间 4.5-5.5），较 10-27 的 4.90 上涨 2.0%。统货口径，较 10-29 地头毛菜 3.85 高约 1.15，差额对应洗葱/整理/损耗"))
A(Q("2026-10-27", "香葱", "小葱（统货）", "红河州泸西县（地头大宗价）", "云南", "产地地头价",
    4.5, 5.5, 4.90, "国资云农", "", "10-27 大宗价 4.90，用于计算真实环比"))

# —— 泸西平台挂牌价（非成交，长期不刷新，仅作区间参考）
A(Q("2026-10-29", "香葱", "小红葱（通货）", "云南红河泸西县", "云南", "产地批发价",
    2.4, 2.4, 2.40, "一亩田", "https://www.ymt.com/supply/59212963", "挂牌 1.20 元/斤 ×2 折算，10000 斤起批，40-45 规格"))
A(Q("2026-10-29", "香葱", "红葱（地头）", "云南红河泸西县", "云南", "产地地头价",
    2.6, 3.0, 2.80, "一亩田", "https://m.ymt.com/supply/60526983", "挂牌 1.30-1.50 元/斤 ×2 折算，按 40-55 规格分档"))
A(Q("2026-10-29", "香葱", "香葱（地头价）", "云南红河泸西县", "云南", "产地地头价",
    3.4, 3.4, 3.40, "惠农网产地行情", "https://www.cnhnb.com/p/xiaocong-0-25-0-0-4/", "挂牌 1.70 元/斤 ×2 折算"))
A(Q("2026-10-29", "香葱", "水洗葱", "云南红河泸西县", "云南", "产地地头价",
    3.6, 3.6, 3.60, "惠农网产地行情", "https://www.cnhnb.com/p/xiaocong-0-25-0-0-4/", "挂牌 1.80 元/斤 ×2 折算"))
A(Q("2026-10-29", "四季葱", "四季葱", "云南红河泸西县", "云南", "产地地头价",
    4.0, 4.0, 4.00, "惠农网产地行情", "https://www.cnhnb.com/p/xiaocong-0-25-0-0-4/", "挂牌 2.00 元/斤 ×2 折算"))
A(Q("2026-10-29", "香葱", "云南香葱", "云南红河泸西县", "云南", "产地收购价",
    4.4, 4.4, 4.40, "惠农网产地行情", "https://www.cnhnb.com/p/xiaocong-0-25-0-0-4/", "挂牌 2.20 元/斤 ×2 折算"))
A(Q("2026-10-29", "小葱", "小葱（常年供应）", "云南红河泸西县", "云南", "产地收购价",
    5.0, 5.0, 5.00, "惠农网产地行情", "https://www.cnhnb.com/p/xiaocong-0-25-0-0-4/", "挂牌 2.50 元/斤 ×2 折算"))
A(Q("2026-10-29", "香葱", "香葱（精品）", "云南红河泸西县", "云南", "产地收购价",
    6.24, 6.24, 6.24, "惠农网产地行情", "https://www.cnhnb.com/p/xiaocong-0-25-0-0-4/", "挂牌 3.12 元/斤 ×2 折算，含部分包邮"))
A(Q("2026-10-29", "小葱", "小葱/香葱", "云南红河泸西县", "云南", "产地收购价",
    6.36, 6.36, 6.36, "惠农网产地行情（永合葱业）", "https://www.cnhnb.com/p/xiaocong-0-25-0-0-4/", "挂牌 3.18 元/斤 ×2 折算，包邮"))
A(Q("2026-10-29", "香葱", "香葱（代收代办）", "云南红河泸西县", "云南", "产地收购价",
    12.0, 12.0, 12.00, "惠农网产地行情", "https://www.cnhnb.com/p/xiaocong-0-25-0-0-4/", "挂牌 6.00 元/斤 ×2 折算，代办服务费口径，离散度极高"))

# —— 云南其他产区
A(Q("2026-10-29", "红葱", "红葱（净葱）", "云南昆明晋宁区", "云南", "产地批发价",
    3.2, 3.2, 3.20, "一亩田", "https://m.ymt.com/supply/65300138", "挂牌 3.20 元/公斤，3000 公斤起批"))
A(Q("2026-10-29", "四季小葱", "四季小葱（通货）", "云南昆明晋宁区", "云南", "产地批发价",
    1.2, 1.2, 1.20, "一亩田", "https://m.ymt.com/supply/64109951", "挂牌 0.60 元/斤 ×2 折算，45-50cm 通货"))
A(Q("2026-10-29", "四季小葱", "四季小葱（精品）", "云南昆明晋宁区", "云南", "产地批发价",
    1.6, 1.6, 1.60, "一亩田", "https://m.ymt.com/supply/64109951", "挂牌 0.80 元/斤 ×2 折算"))
A(Q("2026-10-29", "四季小葱", "四季小葱（一级装车）", "云南昆明晋宁区", "云南", "产地批发价",
    2.0, 2.0, 2.00, "一亩田", "https://m.ymt.com/supply/64109951", "挂牌 1.00 元/斤 ×2 折算，50-60cm 一级"))
A(Q("2026-10-29", "香葱", "白香葱/红香葱", "云南玉溪通海县", "云南", "产地批发价",
    2.4, 2.4, 2.40, "一亩田", "https://www.ymt.com/supplylist/search-25-7300", "挂牌 1.20 元/斤 ×2 折算"))
A(Q("2026-10-29", "黑葱", "黑葱", "云南玉溪通海县", "云南", "产地批发价",
    3.2, 3.2, 3.20, "一亩田", "https://www.ymt.com/supplylist/search-25-7300", "挂牌 3.20 元/公斤"))
A(Q("2026-10-29", "小葱", "小葱（基地直发）", "云南玉溪通海县", "云南", "产地批发价",
    4.0, 4.0, 4.00, "一亩田", "https://www.ymt.com/supplylist/search-25-7300", "挂牌 2.00 元/斤 ×2 折算"))
A(Q("2026-10-29", "小香葱", "精品小香葱", "云南曲靖师宗县", "云南", "产地收购价",
    5.0, 5.0, 5.00, "一亩田", "https://www.ymt.com/supplylist/search-25-7300", "挂牌 2.50 元/斤 ×2 折算"))
A(Q("2026-10-29", "香葱", "水洗香葱", "云南曲靖陆良县", "云南", "产地批发价",
    3.2, 3.2, 3.20, "一亩田", "https://www.ymt.com/supplylist/search-25-7300", "挂牌 1.60 元/斤 ×2 折算"))
A(Q("2026-10-29", "红香葱", "红香葱", "云南曲靖陆良县", "云南", "产地收购价",
    8.0, 8.0, 8.00, "惠农网产地行情", "https://www.cnhnb.com/p/xiaocong-0-25-0-0-4/", "挂牌 8.00 元/公斤，高等级零星报价，离散度大"))
A(Q("2026-10-29", "香葱", "香葱", "云南大理宾川县", "云南", "产地收购价",
    8.0, 8.0, 8.00, "惠农网产地行情", "https://www.cnhnb.com/p/xiaocong-0-25-0-0-4/", "挂牌 4.00 元/斤 ×2 折算"))
A(Q("2026-10-29", "铁杆小香葱", "铁杆小香葱", "云南大理市", "云南", "产地批发价",
    6.2, 6.2, 6.20, "一亩田", "https://www.ymt.com/supplylist/search-25-7300", "挂牌 3.10 元/斤 ×2 折算"))
A(Q("2026-10-29", "小香葱", "小香葱", "云南玉溪市", "云南", "产地收购价",
    7.0, 7.0, 7.00, "惠农网产地行情", "https://www.cnhnb.com/p/xiaocong-0-25-0-0-4/", "挂牌 3.50 元/斤 ×2 折算"))
A(Q("2026-10-29", "香葱", "黑葱/红葱/铁杆白葱（A 货水洗）", "云南昭通鲁甸县", "云南", "产地批发价",
    5.0, 5.0, 5.00, "惠农网产地行情（昭通航禾农业）", "https://www.cnhnb.com/p/xiaocong-0-25-0-0-4/",
    "挂牌 2500 元/吨 = 2.50 元/公斤，吨价折算"))

# —— 销区批发（10-29 实测）
A(Q("2026-10-29", "小葱", "小葱", "昆明景臻王旗营蔬菜批发市场", "云南", "销地批发价",
    2.50, 2.50, 2.50, "昆明市农业农村局 / 景臻·王旗营", "http://mp.weixin.qq.com/s?__biz=MzI2NzIyNTU1Ng==&mid=2247513907&idx=1&sn=351b0abfa4fe7755445792df2b537cf4",
    "10-29 批发均价 2.50，前一日成交量 25 吨（较 10-28 的 35 吨缩量 28.6%）。综合平均价 4.39、总吨位 2735"))
A(Q("2026-10-29", "小葱", "小葱", "昆明景臻王旗营蔬菜批发市场（转载口径）", "云南", "销地批发价",
    3.00, 3.00, 3.00, "云南蔬菜综合报价（10-29 转载）", DH_URL,
    "同日转载口径为 3.00 / 35 吨，与官方 2.50 / 25 吨不一致，疑为前一日数据，两者并列不作平均"))
A(Q("2026-10-29", "香葱", "香葱", "北京新发地农产品批发市场", "北京", "销地批发价",
    6.6, 9.0, 7.80, "北京新发地每日价格行情", "http://dir.xinfadi.com.cn/",
    "10-29 官方口径 最低 3.30 / 平均 3.90 / 最高 4.50 元/斤，×2 折算为 6.60/7.80/9.00 元/公斤"))
A(Q("2026-10-29", "香葱", "香葱", "青岛市城阳蔬菜水产品批发市场", "山东", "销地批发价",
    7.0, 9.0, 8.00, "青岛市城阳蔬菜水产品批发市场", "http://www.cncyms.cn/",
    "官网当日 高 9.00 / 中 8.00 / 低 7.00 元/公斤，连续多日持平，为目前可获取的高位销区报价"))
A(Q("2026-10-29", "小葱", "小葱", "广东汕头农副产品批发中心市场", "广东", "销地批发价",
    4.70, 4.70, 4.70, "农业农村部信息中心", "https://futures.stockstar.com/IG2026102900027959.shtml", "华南销区"))
A(Q("2026-10-29", "小葱", "小葱", "河北怀来县京西果菜批发市场", "河北", "销地批发价",
    6.00, 6.00, 6.00, "河北省怀来县京西果菜批发市场", "http://www.jxgcsc.cn/Default/Price?Type=1", "华北销区，当日最高/最低/均价一致"))
A(Q("2026-10-29", "香葱", "香葱（云南货源）", "邯郸南大堡蔬菜批发市场", "河北", "销地批发价",
    6.4, 7.0, 6.70, "邯郸南大堡蔬菜批发市场官方平台", "http://mp.weixin.qq.com/s?__biz=MzI2MzI3MjAwMw==&mid=2247503269&idx=1&sn=5ddf11cd1a6a31912775848f733dcb67",
    "10-29 报价 高 3.50 / 中 3.20 元/斤，×2 折算；产地标注「云」，即云南调入"))
A(Q("2026-10-29", "小葱", "小葱（香/钢·本地货）", "邯郸南大堡蔬菜批发市场", "河北", "销地批发价",
    1.4, 3.0, 2.20, "邯郸南大堡蔬菜批发市场官方平台", "http://mp.weixin.qq.com/s?__biz=MzI2MzI3MjAwMw==&mid=2247503269&idx=1&sn=5ddf11cd1a6a31912775848f733dcb67",
    "10-29 报价 高 1.50 / 低 0.70 元/斤，×2 折算；本地货与云南货价差达 3.0 倍"))
A(Q("2026-10-29", "香葱", "香葱", "宁夏中卫四季鲜农产品批发市场", "宁夏", "销地批发价",
    10.0, 12.0, 11.00, "宁夏发改委价格监测中心", "https://fzggw.nx.gov.cn/sjfb/jcsj/",
    "原始报价 5-6 元/斤 ×2 折算。西北远端销区，长距离调运后到岸成本高，全国最高档"))

# —— 替代品参考（大葱，非香葱，仅作比价）
A(Q("2026-10-29", "大葱", "大葱", "北京顺鑫石门国际农产品批发市场", "北京", "销地批发价",
    2.00, 2.00, 2.00, "农业农村部信息中心", "https://futures.stockstar.com/IG2026102900027689.shtml", "替代品参考，非香葱，北方大葱低位"))
A(Q("2026-10-29", "大葱", "大葱", "广东汕头农副产品批发中心市场", "广东", "销地批发价",
    3.80, 3.80, 3.80, "农业农村部信息中心", "https://futures.stockstar.com/IG2026102900027959.shtml", "替代品参考"))
A(Q("2026-10-29", "大葱", "大葱（山东本地）", "寿光本地蔬菜价格发布", "山东", "产地批发价",
    1.40, 1.40, 1.40, "寿光本地蔬菜价格发布（2026-10-29）", "",
    "原始报价 0.70 元/斤 ×2 折算，北方大葱供给宽松，对香葱形成替代压制"))

# —— 历史同期档案（同比基准）
A(Q("2024-10-29", "香葱", "红香葱", "云南红河州泸西县（历史同期档案）", "云南", "产地收购价",
    5.1, 6.0, 5.55, "云南蔬菜主产区每日菜价（2024 档案）", "", "两年前同期：红香葱 5.1-6.0 均价 5.55，较今日 3.85 同比 -30.6%"))
A(Q("2024-10-29", "香葱", "黑香葱", "云南红河州泸西县（历史同期档案）", "云南", "产地收购价",
    7.5, 8.4, 8.00, "云南蔬菜主产区每日菜价（2024 档案）", "", "两年前同期：黑香葱 7.5-8.4 均价 8.00，较今日 3.36 同比 -58.0%"))
A(Q("2023-10-29", "香葱", "红香葱", "云南产地（历史同期档案）", "云南", "产地收购价",
    5.5, 6.2, 5.85, "云南市场综合菜价（2023 档案）", "", "三年前同期：红香葱 5.5-6.2，地头毛菜口径"))

SUMMARY = (
    "泸西地头口径确认企稳：10-29 红香葱 3.6-4.0（均价 {0}）、黑香葱 3.1-3.6（均价 {1}），"
    "与 10-26 完全持平，通海产区同价，全省综合报价亦为 3.6-4.0 / 3.1-3.6，滇中价格完全趋同，"
    "行情简报官方措辞为「小香葱平稳」。较 2024 年同期（红 5.55 / 黑 8.00）同比 -30.6% / -58.0%，"
    "仍处近三年同期最低区间。分歧点在于：地头大宗成交价（国资云农 10-28 为 5.00）明显高于集散均价 3.85，"
    "价差约 30%，而销地端昆明王旗营小葱降至 {2:.2f}（前一日成交量由 35 吨缩至 25 吨），"
    "产地止跌、销地缩量，中间环节仍在去库。"
    "天气上泸西未来 3 天暖干（累计 0.7mm、最高 25.8℃、大风 3 天），11/6-11/13 转为多雨寡照"
    "（11/7 单日 25.2mm、11/8 达 21.0mm 且最低温跌至 10.3℃），第 2-4 周供给收缩风险上升。"
    "六档中枢（精品净葱/集散价口径）：{3} → {4} 元/公斤。"
).format(BASE_RED, BASE_BLACK, 2.50, BASE_RED, " / ".join(str(f["center"]) for f in FORECASTS))

DOC = {
    "task": "香葱行情",
    "task_id": "376dffed-c5e4-4904-a77a-29193947212a",
    "date": TODAY,
    "generated_at": GEN,
    "market_scope": "全国 / 云南 / 红河州泸西县",
    "quotes": QUOTES,
    "forecasts": FORECASTS,
    "summary": SUMMARY,
}
json_path = os.path.join(SRC_DIR, "xiangcong_{0}.json".format(TODAY))
with open(json_path, "w", encoding="utf-8") as f:
    json.dump(DOC, f, ensure_ascii=False, indent=2)
print("[OK] 落盘", json_path, "报价", len(QUOTES), "条 / 预测", len(FORECASTS), "条")

# ============================================================ 5. 图表（内联 SVG）
W, H = 900, 340


def _path(pts, xmap, ymap):
    return " ".join(
        ("M" if i == 0 else "L") + "{0:.1f},{1:.1f}".format(xmap(p[0]), ymap(p[1]))
        for i, p in enumerate(pts))


def chart_decade():
    """十年双线：通货毛葱 + 精品净葱。"""
    ml, mr, mt, mb = 60, 30, 40, 46
    vals = [s["price"] for s in series] + [s["premium"] for s in series]
    lo, hi = min(vals), max(vals)
    pad = (hi - lo) * 0.08 or 1
    lo, hi = lo - pad, hi + pad
    xmap = lambda i: ml + i * (W - ml - mr) / (len(series) - 1)
    ymap = lambda v: mt + (hi - v) * (H - mt - mb) / (hi - lo)
    g = ['<svg viewBox="0 0 {0} {1}" class="cv">'.format(W, H)]
    g.append('<rect x="0" y="0" width="{0}" height="{1}" fill="#fbfcfe"/>'.format(W, H))
    for k in range(5):
        v = lo + (hi - lo) * k / 4
        y = ymap(v)
        g.append('<line x1="{0}" y1="{1:.1f}" x2="{2}" y2="{1:.1f}" stroke="#e6eaf0"/>'.format(ml, y, W - mr))
        g.append('<text x="{0}" y="{1:.1f}" font-size="11" fill="#6b7280" text-anchor="end">{2:.1f}</text>'.format(ml - 8, y + 4, v))
    for i, s in enumerate(series):
        if s["month"] == 1 or i == 0:
            x = xmap(i)
            g.append('<line x1="{0:.1f}" y1="{1}" x2="{0:.1f}" y2="{2}" stroke="#eef1f5"/>'.format(x, mt, H - mb))
            g.append('<text x="{0:.1f}" y="{1}" font-size="10.5" fill="#6b7280" text-anchor="middle">{2}</text>'.format(x, H - mb + 16, s["ym"][:4]))
    g.append('<path d="{0}" fill="none" stroke="#c9ced8" stroke-width="1.6" stroke-dasharray="4 3"/>'.format(
        _path([(i, s["premium"]) for i, s in enumerate(series)], xmap, ymap)))
    g.append('<path d="{0}" fill="none" stroke="#2563eb" stroke-width="2.2"/>'.format(
        _path([(i, s["price"]) for i, s in enumerate(series)], xmap, ymap)))
    last = series[-1]
    g.append('<circle cx="{0:.1f}" cy="{1:.1f}" r="4" fill="#2563eb"/>'.format(xmap(len(series) - 1), ymap(last["price"])))
    g.append('<text x="{0:.1f}" y="{1:.1f}" font-size="11.5" fill="#2563eb" text-anchor="end">{2}</text>'.format(
        xmap(len(series) - 1) - 8, ymap(last["price"]) - 8, last["price"]))
    g.append('<text x="{0}" y="{1}" font-size="11.5" fill="#1f2937">通货毛葱（元/公斤）</text>'.format(ml + 6, mt - 14))
    g.append('<text x="{0}" y="{1}" font-size="11.5" fill="#8a93a3">精品净葱 ×1.66</text>'.format(ml + 150, mt - 14))
    g.append("</svg>")
    return "".join(g)


def chart_36m():
    sub = series[-36:]
    ml, mr, mt, mb = 56, 24, 34, 44
    vals = [s["price"] for s in sub]
    lo, hi = min(vals) * 0.9, max(vals) * 1.06
    xmap = lambda i: ml + i * (W - ml - mr) / (len(sub) - 1)
    ymap = lambda v: mt + (hi - v) * (H - mt - mb) / (hi - lo)
    g = ['<svg viewBox="0 0 {0} {1}" class="cv">'.format(W, 260)]
    g.append('<rect x="0" y="0" width="{0}" height="260" fill="#fbfcfe"/>'.format(W))
    for k in range(4):
        v = lo + (hi - lo) * k / 3
        y = ymap(v)
        g.append('<line x1="{0}" y1="{1:.1f}" x2="{2}" y2="{1:.1f}" stroke="#e6eaf0"/>'.format(ml, y, W - mr))
        g.append('<text x="{0}" y="{1:.1f}" font-size="11" fill="#6b7280" text-anchor="end">{2:.1f}</text>'.format(ml - 8, y + 4, v))
    area = [(xmap(0), ymap(lo))] + [(xmap(i), ymap(s["price"])) for i, s in enumerate(sub)] + [(xmap(len(sub) - 1), ymap(lo))]
    g.append('<polygon points="{0}" fill="#2563eb" opacity="0.10"/>'.format(
        " ".join("{0:.1f},{1:.1f}".format(a, b) for a, b in area)))
    g.append('<path d="{0}" fill="none" stroke="#2563eb" stroke-width="2.2"/>'.format(
        _path([(i, s["price"]) for i, s in enumerate(sub)], xmap, ymap)))
    for i, s in enumerate(sub):
        if s["month"] in (1, 4, 7, 10):
            g.append('<text x="{0:.1f}" y="252" font-size="10" fill="#6b7280" text-anchor="middle">{1}</text>'.format(xmap(i), s["ym"][2:]))
    g.append("</svg>")
    return "".join(g)


def chart_season():
    ml, mr, mt, mb = 50, 20, 30, 40
    months = list(range(1, 13))
    hi = max(season.values()) * 1.12
    bw = (W - ml - mr) / 12
    g = ['<svg viewBox="0 0 {0} 250" class="cv">'.format(W)]
    g.append('<rect width="{0}" height="250" fill="#fbfcfe"/>'.format(W))
    base = 210
    for m in months:
        v = season[m]
        h = v / hi * 160
        x = ml + (m - 1) * bw + bw * 0.18
        w = bw * 0.64
        color = "#dc2626" if v >= 1.10 else ("#16a34a" if v <= 0.85 else "#2563eb")
        g.append('<rect x="{0:.1f}" y="{1:.1f}" width="{2:.1f}" height="{3:.1f}" rx="3" fill="{4}" opacity="0.85"/>'.format(
            x, base - h, w, h, color))
        g.append('<text x="{0:.1f}" y="{1:.1f}" font-size="10.5" fill="#374151" text-anchor="middle">{2:.2f}</text>'.format(
            x + w / 2, base - h - 5, v))
        g.append('<text x="{0:.1f}" y="228" font-size="11" fill="#6b7280" text-anchor="middle">{1}月</text>'.format(x + w / 2, m))
    g.append('<line x1="{0}" y1="{1}" x2="{2}" y2="{1}" stroke="#cbd5e1"/>'.format(ml, base, W - mr))
    g.append('<line x1="{0}" y1="{1:.1f}" x2="{2}" y2="{1:.1f}" stroke="#f59e0b" stroke-dasharray="5 3"/>'.format(
        ml, base - 160 / hi, W - mr))
    g.append('<text x="{0}" y="{1:.1f}" font-size="10.5" fill="#b45309">基准 1.00</text>'.format(ml + 4, base - 160 / hi - 5))
    g.append("</svg>")
    return "".join(g)


def chart_forecast():
    ml, mr, mt, mb = 60, 26, 34, 44
    xs = [(0, BASE_RED)] + [(r["days"], r["center"]) for r in FRED["rows"]]
    lows = [(0, BASE_RED)] + [(r["days"], r["low"]) for r in FRED["rows"]]
    highs = [(0, BASE_RED)] + [(r["days"], r["high"]) for r in FRED["rows"]]
    days = [p[0] for p in xs]
    hi = max(p[1] for p in highs) * 1.08
    lo = min(p[1] for p in lows) * 0.92
    xmap = lambda d: ml + d * (W - ml - mr) / 95
    ymap = lambda v: mt + (hi - v) * (H - mt - mb) / (hi - lo)
    g = ['<svg viewBox="0 0 {0} 300" class="cv">'.format(W)]
    g.append('<rect width="{0}" height="300" fill="#fbfcfe"/>'.format(W))
    for k in range(4):
        v = lo + (hi - lo) * k / 3
        y = ymap(v)
        g.append('<line x1="{0}" y1="{1:.1f}" x2="{2}" y2="{1:.1f}" stroke="#e6eaf0"/>'.format(ml, y, W - mr))
        g.append('<text x="{0}" y="{1:.1f}" font-size="11" fill="#6b7280" text-anchor="end">{2:.2f}</text>'.format(ml - 8, y + 4, v))
    poly = [(xmap(d), ymap(v)) for d, v in highs] + [(xmap(d), ymap(v)) for d, v in reversed(lows)]
    g.append('<polygon points="{0}" fill="#f59e0b" opacity="0.16"/>'.format(
        " ".join("{0:.1f},{1:.1f}".format(a, b) for a, b in poly)))
    g.append('<path d="{0}" fill="none" stroke="#ea580c" stroke-width="2.4"/>'.format(_path(xs, xmap, ymap)))
    for d, v in xs:
        g.append('<circle cx="{0:.1f}" cy="{1:.1f}" r="3.6" fill="#ea580c"/>'.format(xmap(d), ymap(v)))
    for r in FRED["rows"]:
        g.append('<text x="{0:.1f}" y="{1:.1f}" font-size="10.5" fill="#9a3412" text-anchor="middle">{2}</text>'.format(
            xmap(r["days"]), ymap(r["high"]) - 9, r["center"]))
    for r in FRED["rows"]:
        g.append('<text x="{0:.1f}" y="288" font-size="10" fill="#6b7280" text-anchor="middle">{1}</text>'.format(
            xmap(r["days"]), r["label"]))
    g.append('<text x="{0:.1f}" y="{1:.1f}" font-size="10.5" fill="#1f2937" text-anchor="start">今</text>'.format(
        xmap(0) - 2, ymap(BASE_RED) - 10))
    g.append("</svg>")
    return "".join(g)


def chart_cross():
    """全国横截面：按 price_type 分组均值。"""
    groups = {}
    for q in QUOTES:
        if q["item"] == "大葱":
            continue
        groups.setdefault(q["price_type"], []).append(q["mid"])
    order = ["产地地头价", "产地收购价", "产地批发价", "销地批发价"]
    items = [(k, groups[k]) for k in order if k in groups]
    ml, mt = 150, 30
    hi = max(sum(v) / len(v) for _, v in items) * 1.2
    row_h = 46
    g = ['<svg viewBox="0 0 {0} {1}" class="cv">'.format(W, mt + row_h * len(items) + 20)]
    g.append('<rect width="{0}" height="{1}" fill="#fbfcfe"/>'.format(W, mt + row_h * len(items) + 20))
    colors = {"产地地头价": "#0d9488", "产地收购价": "#2563eb", "产地批发价": "#7c3aed", "销地批发价": "#ea580c"}
    for i, (k, v) in enumerate(items):
        avg = sum(v) / len(v)
        y = mt + i * row_h
        bw = (W - ml - 120) * avg / hi
        g.append('<text x="{0}" y="{1}" font-size="12.5" fill="#374151">{2}</text>'.format(20, y + 20, k))
        g.append('<rect x="{0}" y="{1}" width="{2:.1f}" height="20" rx="4" fill="{3}" opacity="0.85"/>'.format(
            ml, y + 4, bw, colors.get(k, "#2563eb")))
        g.append('<text x="{0:.1f}" y="{1}" font-size="12" fill="#111827" font-weight="600">{2:.2f}</text>'.format(
            ml + bw + 8, y + 19, avg))
        g.append('<text x="{0:.1f}" y="{1}" font-size="10.5" fill="#9ca3af">n={2}　{3:.2f}~{4:.2f}</text>'.format(
            ml + bw + 58, y + 19, len(v), min(v), max(v)))
    g.append("</svg>")
    return "".join(g)


def chart_luxi_spread():
    """泸西多源口径分歧。"""
    pts = [("惠农网·代收代办挂牌(6元/斤)", 12.00), ("惠农网·陆良红香葱挂牌", 8.00),
           ("惠农网·精品香葱挂牌(3.12元/斤)", 6.24), ("惠农网·小葱包邮挂牌(3.18元/斤)", 6.36),
           ("国资云农·地头大宗成交(T-1)", 5.00), ("惠农网·小葱常年供应挂牌", 5.00),
           ("惠农网·云南香葱挂牌(2.20元/斤)", 4.40), ("惠农网·四季葱挂牌", 4.00),
           ("泸西红香葱·集散均价(模型基准)", 3.85), ("惠农网·水洗葱挂牌", 3.60),
           ("惠农网·香葱地头挂牌(1.70元/斤)", 3.40), ("一亩田·红葱地头挂牌", 2.80),
           ("一亩田·小红葱通货挂牌(1.20元/斤)", 2.40)]
    pts.sort(key=lambda x: -x[1])
    ml, mt = 210, 34
    hi = max(v for _, v in pts) * 1.25
    row_h = 34
    g = ['<svg viewBox="0 0 {0} {1}" class="cv">'.format(W, mt + row_h * len(pts) + 16)]
    g.append('<rect width="{0}" height="{1}" fill="#fbfcfe"/>'.format(W, mt + row_h * len(pts) + 16))
    for i, (name, v) in enumerate(pts):
        y = mt + i * row_h
        bw = (W - ml - 90) * v / hi
        c = "#dc2626" if v >= 4.8 else ("#2563eb" if v >= 3.8 else "#16a34a")
        g.append('<text x="18" y="{0}" font-size="12" fill="#374151">{1}</text>'.format(y + 16, name))
        g.append('<rect x="{0}" y="{1}" width="{2:.1f}" height="18" rx="4" fill="{3}" opacity="0.85"/>'.format(ml, y + 3, bw, c))
        g.append('<text x="{0:.1f}" y="{1}" font-size="11.5" fill="#111827" font-weight="600">{2:.2f}</text>'.format(ml + bw + 8, y + 17, v))
    g.append("</svg>")
    return "".join(g)


def chart_weather():
    days = core_daily[:16]
    ml, mr, mt, mb = 52, 24, 26, 44
    lo, hi = 0, max((d["precip"] or 0) for d in days) * 1.3 or 1
    xmap = lambda i: ml + i * (W - ml - mr) / max(1, len(days) - 1)
    ymap = lambda v: mt + (1 - v / hi) * (200 - mt - mb)
    g = ['<svg viewBox="0 0 {0} 200" class="cv">'.format(W)]
    g.append('<rect width="{0}" height="200" fill="#fbfcfe"/>'.format(W))
    bw = (W - ml - mr) / len(days) * 0.6
    for i, d in enumerate(days):
        p = d["precip"] or 0
        h = max(1.5, p / hi * (200 - mt - mb))
        c = "#dc2626" if p >= 10 else ("#f59e0b" if p >= 1 else "#93c5fd")
        g.append('<rect x="{0:.1f}" y="{1:.1f}" width="{2:.1f}" height="{3:.1f}" rx="2" fill="{4}"/>'.format(
            xmap(i) - bw / 2, 200 - mb - h, bw, h, c))
        if p >= 1:
            g.append('<text x="{0:.1f}" y="{1:.1f}" font-size="9.5" fill="#6b7280" text-anchor="middle">{2:.1f}</text>'.format(
                xmap(i), 200 - mb - h - 4, p))
        if i % 2 == 0:
            g.append('<text x="{0:.1f}" y="192" font-size="9.5" fill="#9ca3af" text-anchor="middle">{1}</text>'.format(
                xmap(i), d["date"][5:]))
    g.append('<line x1="{0}" y1="{1}" x2="{2}" y2="{1}" stroke="#cbd5e1"/>'.format(ml, 200 - mb, W - mr))
    g.append('<text x="{0}" y="{1}" font-size="11.5" fill="#1f2937">泸西逐日降水量（mm）</text>'.format(ml + 4, mt - 8))
    g.append("</svg>")
    return "".join(g)


# ============================================================ 6. HTML
def td(v, cls=""):
    return '<td class="{0}">{1}</td>'.format(cls, v)


def wrow(w):
    up = w["change_pct"] >= 0
    return "<tr><td>{0}</td>{1}{2}{3}{4}{5}{6}</tr>".format(
        w["label"],
        td("{0:.2f}".format(w["start"])),
        td("{0:.2f}".format(w["end"])),
        td('<span class="{0}">{1:+.1f}%</span>'.format("up" if up else "down", w["change_pct"])),
        td("{0:.2f}".format(w["avg"])),
        td("{0:.2f}（{1}）".format(w["lo"], w["lo_ym"])),
        td("{0:.2f}（{1}）".format(w["hi"], w["hi_ym"])),
    )


frows = []
base_row = ("<tr class='base'><td>当前基准（10-29 实测）</td><td>—</td><td>{0:.2f}</td>"
            "<td>—</td><td>{1:.2f}</td><td>—</td><td>—</td><td>—</td><td>基准</td></tr>").format(BASE_RED, BASE_BLACK)
for f in FORECASTS:
    r = RRED[dict((v,k) for k,v in HORIZON_MAP)[f["horizon"]]]
    b = RBLK[dict((v,k) for k,v in HORIZON_MAP)[f["horizon"]]]
    cls = "up" if r["delta_pct"] >= 3 else ("flat" if r["delta_pct"] > -3 else "down")
    bcls = "up" if b["delta_pct"] >= 3 else ("flat" if b["delta_pct"] > -3 else "down")
    frows.append("<tr><td>{0}</td><td>{1}</td><td><b>{2:.2f}</b></td><td>{3:.2f}~{4:.2f}</td>"
                 "<td>{5:.2f}</td><td>{6:.2f}~{7:.2f}</td>"
                 "<td><span class='{8}'>{9:+.1f}%</span></td>"
                 "<td><span class='{10}'>{11:+.1f}%</span></td><td>{12}</td></tr>".format(
                     f["horizon"], f["target_date"], r["center"], r["low"], r["high"],
                     b["center"], b["low"], b["high"],
                     cls, r["delta_pct"], bcls, b["delta_pct"], r["confidence"]))

qrows = []
for q in QUOTES:
    qrows.append("<tr><td>{0}</td><td>{1}</td><td>{2}</td><td>{3}</td><td>{4}</td>"
                 "<td class='num'>{5:.2f}</td><td class='num'>{6:.2f}</td><td class='num'><b>{7:.2f}</b></td>"
                 "<td class='src'>{8}</td></tr>".format(
                     q["date"], q["item"], q["variety"] or "—", q["market"], q["price_type"],
                     q["low"], q["high"], q["mid"], q["source"]))

cultivars = "".join(
    "<tr><td><b>{0}</b></td><td>{1}</td><td>{2}</td><td>{3}</td></tr>".format(
        c["name"], c["trait"], c["area"], c["yield"]) for c in config.CULTIVARS)
varieties = "".join(
    "<tr><td><b>{0}</b></td><td>{1}</td><td>{2}</td></tr>".format(
        v["name"], v["desc"], v["use"]) for v in config.VARIETIES)

prov_rows = [
    ("云南", "泸西（13.5 万亩基地 / 46.7 万亩次复种 / 年产 118 万吨 / 产值 35.5 亿元）", "全国最大，占云南 60%+，日外运 2000+ 吨"),
    ("云南", "曲靖师宗、陆良、通海、宾川、弥渡、晋宁、呈贡、嵩明", "滇中滇东次级集群，分担泸西产能"),
    ("广西", "南宁江南区江西镇（1.53 万亩）、西乡塘金陵镇三联村（4100 亩，红葱 97.6%）、柳州柳江/柳南、玉林", "华南主产，冬春补充"),
    ("广东", "湛江徐闻、韶关翁源", "华南南部，红葱/水葱为主，周年供应"),
    ("山东", "寿光、临沂郯城/兰陵、潍坊安丘/诸城、章丘、青岛", "北方设施+露地，加工带"),
    ("江苏", "兴化（加工带）、盐城大丰、南通海安、徐州", "脱水葱加工全国中心"),
    ("河南", "开封通许、焦作武陟/博爱、平顶山汝州、驻马店", "中原产区，夏秋上市"),
    ("河北", "邯郸永年/丛台、唐山滦南、沧州", "华北产区，夏秋供应京津冀"),
    ("贵州", "毕节威宁、鲁甸（昭通）", "西南高海拔，夏秋错峰"),
    ("辽宁/吉林", "沈阳新民、锦州太和、长春公主岭", "东北夏秋供应"),
    ("四川/湖北/安徽/福建/浙江", "成都金堂、武汉、宜昌当阳、阜阳临泉、漳州、金华", "分散产区，就地消化为主"),
]
prov_html = "".join("<tr><td><b>{0}</b></td><td>{1}</td><td>{2}</td></tr>".format(*r) for r in prov_rows)

disaster_top = json.load(open(os.path.join(BASE_DIR, "data", "disaster_2026-10-30.json"), encoding="utf-8"))
prod_hits = [t for t in disaster_top.get("top", []) if t.get("is_production_area")]
d_rows = "".join(
    "<tr><td>{0}</td><td>{1}</td><td>{2}预警</td><td>{3}</td><td>{4}</td></tr>".format(
        t["region"], t["hazard"], t["level"], t["impact"], t["issuetime"]) for t in prod_hits[:14])
if not d_rows:
    d_rows = "<tr><td colspan='5'>当前无直接影响主产区的预警</td></tr>"

CSS = """
:root{--bd:#e5e9f0;--tx:#1f2937;--mu:#6b7280;--bg:#f6f8fb;--cd:#fff;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--tx);font:15px/1.7 -apple-system,"PingFang SC","Microsoft YaHei",sans-serif}
.wrap{max-width:1080px;margin:0 auto;padding:28px 20px 60px}
h1{font-size:26px;margin:0 0 6px}
h2{font-size:19px;margin:34px 0 12px;padding-left:11px;border-left:4px solid #2563eb}
h3{font-size:15px;margin:20px 0 9px;color:#374151}
.sub{color:var(--mu);font-size:13px;margin-bottom:18px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin:16px 0}
.kpi{background:var(--cd);border:1px solid var(--bd);border-radius:10px;padding:14px 15px}
.kpi .l{font-size:12px;color:var(--mu)}
.kpi .v{font-size:23px;font-weight:700;margin-top:3px}
.kpi .d{font-size:11.5px;color:var(--mu);margin-top:3px}
.card{background:var(--cd);border:1px solid var(--bd);border-radius:11px;padding:16px 18px;margin:14px 0}
.cv{width:100%;height:auto;display:block}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{border-bottom:1px solid var(--bd);padding:7px 8px;text-align:left;vertical-align:top}
th{background:#f1f4f9;font-weight:600;color:#374151;white-space:nowrap}
td.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
td.src{color:var(--mu);font-size:12px}
tr.base{background:#fffbeb}
.up{color:#dc2626;font-weight:600}.down{color:#16a34a;font-weight:600}.flat{color:#6b7280;font-weight:600}
.note{background:#f0f7ff;border-left:3px solid #2563eb;padding:10px 13px;border-radius:0 7px 7px 0;font-size:13px;margin:12px 0}
.warn{background:#fff7ed;border-left:3px solid #f59e0b;padding:10px 13px;border-radius:0 7px 7px 0;font-size:13px;margin:12px 0}
ul{margin:8px 0 8px 20px;padding:0}
li{margin:4px 0}
.foot{color:var(--mu);font-size:12px;margin-top:30px;border-top:1px solid var(--bd);padding-top:14px}
"""

HTML = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>香葱行情分析 · {today}</title><style>{css}</style></head><body><div class="wrap">
<h1>香葱行情分析 · {today}</h1>
<div class="sub">生成时间 {gen}（北京时间） · 全国 / 云南 / 红河州泸西县 · 数据日期 {ddate}（当日行情次日发布）</div>

<div class="kpis">
  <div class="kpi"><div class="l">泸西模型基准（红香葱）</div><div class="v">{br:.2f}</div><div class="d">元/公斤 · 滇中产区集散价 · 10-29 实测 · 持平</div></div>
  <div class="kpi"><div class="l">泸西黑香葱</div><div class="v">{bb:.2f}</div><div class="d">元/公斤 · 10-29 实测 · 3.1-3.6 区间</div></div>
  <div class="kpi"><div class="l">泸西地头大宗价</div><div class="v">5.00</div><div class="d">元/公斤 · 国资云农 10-28 · 较前日 +2.0%</div></div>
  <div class="kpi"><div class="l">昆明王旗营小葱</div><div class="v">2.50</div><div class="d">元/公斤 · 10-29 · 成交量 35→25 吨</div></div>
  <div class="kpi"><div class="l">全国销地批发（城阳）</div><div class="v">8.00</div><div class="d">元/公斤 · 青岛城阳 10-29 · 持平</div></div>
  <div class="kpi"><div class="l">20 日实测均线</div><div class="v">{ma:.2f}</div><div class="d">元/公斤 · 现价低于均线 {gap:.1f}%</div></div>
</div>

<div class="note"><b>本期核心结论：</b>{summ}</div>

<h2>一、历史长周期回顾（近 10 年）</h2>
<div class="card">{c_decade}</div>
<table><thead><tr><th>窗口</th><th>期初</th><th>期末</th><th>涨跌</th><th>均值</th><th>最低</th><th>最高</th></tr></thead>
<tbody>{wrows}</tbody></table>
<div class="note">口径：主序列为<b>通货毛葱</b>（元/公斤），精品净葱 = 主序列 × 1.66。
10 年 CAGR <b>{cagr:.1f}%</b>，长周期中枢下移；近 36 月振幅 628% 主要由 2024-08 峰值 11.00 与 2026-07 夏谷 1.51 拉扯形成。</div>
<h3>近 36 个月</h3><div class="card">{c_36}</div>
<h3>季节指数（1.00 = 年度均值）</h3><div class="card">{c_season}</div>
<div class="note">季节规律：春峰 4-5 月（1.25 / 1.16）→ 夏谷 7-8 月（0.68 / 0.72）→ 冬旺 11-1 月（1.09-1.14）。
当前 10 月因子 1.026，11 月升至 1.121、12 月 1.140，<b>季节性本身对四季度构成上行动力</b>。</div>

<h2>二、天气与灾害</h2>
<div class="card">{c_wx}</div>
<table><thead><tr><th>窗口</th><th>最高温均</th><th>最低温均</th><th>累计降水</th><th>雨日</th><th>大风日</th><th>主导天气</th></tr></thead><tbody>
<tr><td>未来 3 天</td><td>{w3t}</td><td>{w3t2}</td><td>{w3p} mm</td><td>{w3r}</td><td>{w3g}</td><td>{w3d}</td></tr>
<tr><td>未来 1 周</td><td>{w7t}</td><td>{w7t2}</td><td>{w7p} mm</td><td>{w7r}</td><td>{w7g}</td><td>{w7d}</td></tr>
<tr><td>第 8-15 天</td><td>{wht}</td><td>{wht2}</td><td>{whp} mm</td><td>{whr}</td><td>{whg}</td><td>{whd}</td></tr>
</tbody></table>
<div class="note"><b>关键转折：</b>未来 3 天泸西<b>暖干、多大风</b>（累计 {w3p} mm、最高气温 {w3t}℃、距平 {ano:+.1f}℃、
8 级以上大风 {w3g} 天、最大风速 23.6 m/s），气温偏高加速生长，短期供给充裕；
但 <b>11/6 起转入多雨寡照</b>——11/6 至 11/13 共 7 个雨日、累计 {whp} mm，
其中 <b>11/7 单日 25.2 mm、11/8 达 21.0 mm</b>（连续两日达到强降水阈值），
并伴随剧烈降温：最高气温由 11/4 的 26.0℃ 一路降至 11/8 的 16.5℃（四日降幅 9.5℃），
最低气温 11/9 跌至 10.3℃、11/10 进一步降至 9.9℃。
<b>采收受阻 + 洗葱损耗上升 + 根腐/霜霉病风险</b>将在第 2-4 周集中兑现，是本期预测上行的核心驱动。</div>
<div class="warn"><b>全国层面（中央气象台 10-30 凌晨生效预警）：</b>全网生效预警 <b>{dtot}</b> 条，
结构高度集中于<b>大雾</b>（橙色 16 条、红色 2 条），主要分布在辽宁丹东（红色，高速封路）、
安徽滁州/宣城、山东临沂郯城与青岛莱西、江苏南通如东、广东肇庆德庆等；另有新疆克拉玛依道路结冰黄色。
唯一暴雨预警在<b>云南临沧临翔区（橙色，10/30 03:00 发布）</b>，位于滇西，<b>核心产区泸西（滇东）不受直接影响</b>；
但<b>云南曲靖富源县大雾橙色</b>紧邻泸西外运通道，对滇东至黔桂的陆运时效构成扰动。</div>
<h3>当前生效预警（涉及香葱主产区）</h3>
<table><thead><tr><th>区域</th><th>灾种</th><th>级别</th><th>影响</th><th>发布时间</th></tr></thead><tbody>{drows}</tbody></table>
<div class="note">全网生效预警合计 <b>{dtot}</b> 条，其中涉及主产区 <b>{dprod}</b> 条：
云南临沧临翔区暴雨橙色（产区，滇西）、云南曲靖富源大雾橙色（产区，滇东外运通道）、
山东临沂郯城与青岛莱西大雾橙色、江苏南通如东大雾橙色、广东肇庆德庆大雾橙色。
<b>泸西本埠无生效预警</b>，短期天气风险以 11/6 起的预报降水为主。</div>

<h2>三、市面常见香葱种类</h2>
<h3>3.1 流通端商品分类（决定报价口径）</h3>
<table><thead><tr><th>分类</th><th>特征</th><th>主要用途</th></tr></thead><tbody>{varieties}</tbody></table>
<h3>3.2 主要栽培品种</h3>
<table><thead><tr><th>品种</th><th>特征</th><th>适种区域</th><th>产量</th></tr></thead><tbody>{cultivars}</tbody></table>

<h2>四、全国香葱种植省份</h2>
<table><thead><tr><th>省/区域</th><th>主产县市</th><th>产业地位</th></tr></thead><tbody>{provs}</tbody></table>
<div class="note">口径提示：全国小香葱种植面积第三方统计分歧较大（有 78.56 万亩与主产区加总两种量级），
本报告以<b>主产区加总</b>口径呈现，仅用于判断区域供给权重，不建议作为绝对面积引用。</div>

<h2>五、全国行情横截面（{ddate}）</h2>
<div class="card">{c_cross}</div>
<h3>5.1 泸西多源口径分歧（本期重点）</h3>
<div class="card">{c_spread}</div>
<div class="warn"><b>异常发现（本期进一步扩大）：</b>同一日、同一产地泸西，公开报价从 <b>2.40 到 12.00 元/公斤</b>不等，
极值价差达 <b>5.0 倍</b>（上期为 67%）。按可信度分层：
①<b>成交价层</b>（可信度最高）——国资云农地头大宗 5.00（每日实地采集）、泸西集散均价 3.85（产区菜价表，模型基准），
两者差 1.15 元对应洗葱/整理/损耗成本，属正常口径差；
②<b>挂牌价层</b>（可信度中等，非成交、长期不刷新）——一亩田 2.40-2.80、惠农网 3.40-6.36，跨度极大；
③<b>代办/零星层</b>（不可用于定价）——惠农网代收代办挂牌 12.00，含代办服务费与小批量溢价。
判断：<b>真实成交中枢落在 3.85（集散）～5.00（地头大宗）之间</b>，模型沿用 3.85 属保守口径；
若后续集散价向地头价收敛（上修至 5.00），六档中枢应整体上移约 +1.15 元/公斤（见第八章情景 B）。</div>
<h3>5.2 全量报价明细（{n} 条）</h3>
<table><thead><tr><th>日期</th><th>品名</th><th>规格</th><th>市场/产地</th><th>口径</th><th>低</th><th>高</th><th>中值</th><th>来源</th></tr></thead>
<tbody>{qrows}</tbody></table>

<h2>六、泸西专题与六档预测</h2>
<h3>6.1 泸西产业底盘</h3>
<table><thead><tr><th>指标</th><th>数值</th></tr></thead><tbody>
<tr><td>种植基地</td><td>13.5 万亩</td></tr>
<tr><td>复种面积</td><td>46.7 万亩次</td></tr>
<tr><td>年产量</td><td>118 万吨</td></tr>
<tr><td>年产值</td><td>35-36 亿元</td></tr>
<tr><td>占云南比重</td><td>60% 以上</td></tr>
<tr><td>日外运量</td><td>2000 吨以上</td></tr>
<tr><td>带动就业</td><td>5 万人以上（3000+ 种植户）</td></tr>
</tbody></table>
<h3>6.2 六档价格预测（精品净葱 / 集散价口径）</h3>
<div class="card">{c_fc}</div>
<table><thead><tr><th>档位</th><th>目标日</th><th>红葱中枢</th><th>红葱情景区间</th><th>黑葱中枢</th><th>黑葱情景区间</th><th>红葱涨跌</th><th>黑葱涨跌</th><th>置信度</th></tr></thead>
<tbody>{base}{frows}</tbody></table>
<div class="note">模型：<b>季节因子 × 天气冲击（衰减）× 均值回归动量 × 节日脉冲</b>。
当前现价 {br:.2f} 低于 20 日实测均线 {ma:.2f}（缺口 {gap:.1f}%），均值回归项为正向，
叠加 11-12 月季节因子上行（1.026 → 1.121 → 1.140）与 11/6 起多雨寡照带来的供给收缩，
六档呈<b>单调递增</b>：{path}。区间为情景区间，非统计置信区间。</div>

<h2>七、风险提示</h2>
<ul>
<li><b>口径风险（最高）：</b>同一产地泸西当日公开报价极值差已达 <b>5.0 倍</b>（2.40 ~ 12.00 元/公斤），
跨平台横比严重失真。本报告已按 price_type 全量标注，使用时务必同口径、同品种、同规格比较。</li>
<li><b>集散价与地头价背离：</b>泸西集散均价 3.85 与地头大宗成交 5.00 差 1.15 元/公斤（约 30%）。
模型采用较保守的集散口径，若两者收敛，本期预测系统性偏低（见情景 B）。</li>
<li><b>销地缩量：</b>昆明王旗营小葱 3.50→3.00→2.50 后本期维持 2.50，但<b>前一日成交量由 35 吨降至 25 吨（-28.6%）</b>，
量价齐弱，反映销区需求疲弱、中间环节仍在去库，产地企稳信号尚未有效传导。</li>
<li><b>天气风险：</b>11/6-11/13 多雨寡照（累计 58.5 mm、含 2 个强降水日）+ 11/9 起最低温跌破 10℃。
若演变为连续 3 日以上强降水则上行幅度超预期；反之若暖干延续，季节性上行将被供给充裕抵消。</li>
<li><b>替代竞争：</b>大葱处明显低位（北京顺鑫石门 2.00、山东寿光本地 1.40、广东汕头 3.80），
对香葱消费形成替代压制，是本期集散价迟迟无法上修的重要需求侧原因。</li>
<li><b>下行风险：</b>2027 春节在 2/6，节前备货高峰前若暖冬延续、单产超预期，2 月档存在回落可能；
同时平台挂牌价长期横置在 2.40-3.60，若真实成交向其收敛则本期预测系统性偏高。</li>
</ul>

<h2>八、情景推演</h2>
<table><thead><tr><th>情景</th><th>触发条件</th><th>3 个月中枢</th><th>概率</th></tr></thead><tbody>
<tr><td><b>A 基准</b></td><td>基准维持 3.85，季节性上行 + 11/6 起多雨温和兑现</td><td>{a3:.2f} 元/公斤</td><td>55%</td></tr>
<tr><td><b>B 上修</b></td><td>集散价向地头大宗价收敛（上修至 5.00），或多雨超预期演变为连续强降水</td><td>{b3:.2f} 元/公斤</td><td>30%</td></tr>
<tr><td><b>C 下修</b></td><td>暖干延续、供给充裕、销区需求继续走弱、大葱替代压制加深</td><td>{c3:.2f} 元/公斤</td><td>15%</td></tr>
</tbody></table>

<div class="foot">
数据来源：中央气象台（nmc.cn）、Open-Meteo 预报与归档 API、农业农村部信息中心（含证券之星转载）、
农业农村部重点农产品市场信息平台（ncpscxx.moa.gov.cn）、国资云农每日产地采集、青岛市城阳蔬菜水产品批发市场（cncyms.cn）、
北京新发地、昆明景臻王旗营、一亩田、惠农网、食品商务网（21food）、云南蔬菜主产区每日菜价历史档案。<br>
本报告由自动化任务 376dffed 生成，仅供经营参考，不构成交易建议。价格单位除特别标注外均为元/公斤。
</div>
</div></body></html>"""

a3 = FRED["rows"][5]["center"]
b3 = a3 * 5.00 / BASE_RED
c3 = a3 * 0.90

html = HTML.format(
    css=CSS, today=TODAY, gen=GEN, ddate=DATA_DATE, summ=SUMMARY,
    br=BASE_RED, bb=BASE_BLACK, ma=FRED["ma20"], gap=(FRED["ma20"] / BASE_RED - 1) * 100,
    c_decade=chart_decade(), wrows="".join(wrow(windows[m]) for m in (12, 24, 36, 60, 120)),
    cagr=windows[120]["cagr"], c_36=chart_36m(), c_season=chart_season(),
    c_wx=chart_weather(),
    w3t=w3.get("tmax_avg"), w3t2=w3.get("tmin_avg"), w3p=w3.get("precip_total"),
    w3r=w3.get("rainy_days"), w3g=w3.get("gale_days"), w3d=w3.get("dominant"),
    w7t=w7.get("tmax_avg"), w7t2=w7.get("tmin_avg"), w7p=w7.get("precip_total"),
    w7r=w7.get("rainy_days"), w7g=w7.get("gale_days"), w7d=w7.get("dominant"),
    wht=wh.get("tmax_avg"), wht2=wh.get("tmin_avg"), whp=wh.get("precip_total"),
    whr=wh.get("rainy_days"), whg=wh.get("gale_days"), whd=wh.get("dominant"),
    ano=(w3.get("tmax_avg") or 0) - (clim.get("tmax_mean") or 0),
    drows=d_rows, dtot=disaster_top.get("total", 0), dprod=len(prod_hits),
    varieties=varieties, cultivars=cultivars, provs=prov_html,
    c_cross=chart_cross(), c_spread=chart_luxi_spread(), n=len(QUOTES), qrows="".join(qrows),
    c_fc=chart_forecast(), base=base_row, frows="".join(frows),
    path=" → ".join(str(r["center"]) for r in FRED["rows"]),
    a3=a3, b3=b3, c3=c3,
)

html_path = os.path.join(OUT_DIR, "香葱行情分析_{0}.html".format(TODAY))
with open(html_path, "w", encoding="utf-8") as f:
    f.write(html)
print("[OK] 报告", html_path, len(html) // 1024, "KB")
print("红葱中枢:", BASE_RED, "→", [r["center"] for r in FRED["rows"]])
print("黑葱中枢:", BASE_BLACK, "→", [r["center"] for r in FBLK["rows"]])
