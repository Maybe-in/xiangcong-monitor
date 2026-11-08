# -*- coding: utf-8 -*-
"""香葱行情定时任务落盘 + 图表报告生成器（任务 376dffed）· 2026-11-08

产出：
  1) data/sources/xiangcong_2026-11-08.json  统一 schema 全量报价 + 六档预测
  2) outputs/香葱行情分析_2026-11-08.html     长周期 / 收敛 / 同比 / 预测 图表

注意（代码坑）：f-string 内禁止嵌套 ASCII 引号，中文文案统一使用「」。
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from src import longterm, config, price  # noqa: E402
from src.weather import summarize_window  # noqa: E402

BJ = timezone(timedelta(hours=8))
_now = datetime.now(BJ)
TODAY = _now.date().isoformat()
GEN = _now.strftime("%Y-%m-%d %H:%M")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(BASE_DIR, "data", "sources")
OUT_DIR = os.path.join(BASE_DIR, "outputs")
os.makedirs(SRC_DIR, exist_ok=True)
os.makedirs(OUT_DIR, exist_ok=True)

DATA_DATE = "2026-11-07"   # 最新可获取的实测报价日（当日数据次日发布）
PREV_DATE = "2026-11-06"

# 本期核心实测（泸西分区，11-07 实测，次日发布）
RED_MID, RED_LO, RED_HI = 3.45, 3.3, 3.6
BLK_MID, BLK_LO, BLK_HI = 2.96, 2.7, 3.1
PREV_RED, PREV_BLK = 3.45, 2.96
RED_CHG = RED_MID - PREV_RED          # = 0.00 持平
RED_CHG_PCT = RED_CHG / PREV_RED * 100  # = 0.0
BLK_CHG = BLK_MID - PREV_BLK          # = 0.00 持平
BLK_CHG_PCT = BLK_CHG / PREV_BLK * 100  # = 0.0

# ============================================================ 0. 回写实测价
HIST_PATH = os.path.join(BASE_DIR, "data", "price_history.json")
hist = json.load(open(HIST_PATH, encoding="utf-8"))
hist["series"] = [s for s in hist["series"]
                  if not (s["date"] == DATA_DATE and s.get("source") == "model")]
_have = {(s["date"], s["variety"]) for s in hist["series"]}
_new = [
    {"date": DATA_DATE, "variety": "红香葱", "market": "云南产地", "price": RED_MID,
     "source": "observed",
     "note": "泸西菜价（2026-11-07 实测）红香葱 3.3-3.6 均价 3.45；与 11-06 的 3.45 完全持平，自 11-01 起连续七个报价日锁定 3.45；地慧数农同日全省综合 3.3-3.6 实证对齐"},
    {"date": DATA_DATE, "variety": "黑葱", "market": "云南产地", "price": BLK_MID,
     "source": "observed",
     "note": "泸西菜价（2026-11-07 实测）黑香葱 2.7-3.1 均价 2.96；与 11-06 的 2.96 完全持平，黑葱 11-01 跟跌后暂稳、连续七个报价日锁定 2.96；全省综合 2.7-3.1 同步对齐"},
    {"date": DATA_DATE, "variety": "小葱", "market": "昆明王旗营", "price": 2.30,
     "source": "observed",
     "note": "景臻·王旗营 2026-11-07 官方表：小葱前一日成交量 30 吨持平、大葱 4.50 元/公斤（50 吨）、香菜 4.00；综合平均价 4.25、总吨位 3151（较 11-06 的 4.31 / 3310 双降）。小葱价格栏 OCR 三列串列不可靠，主口径沿用 2.30 并标注，不作为本期新成交价"},
]
for _n in _new:
    if (_n["date"], _n["variety"]) not in _have:
        hist["series"].append(_n)
    else:
        for s in hist["series"]:
            if s["date"] == _n["date"] and s["variety"] == _n["variety"]:
                s.update(_n)
hist["series"].sort(key=lambda s: (s["date"], s["variety"]))
with open(HIST_PATH, "w", encoding="utf-8") as f:
    json.dump(hist, f, ensure_ascii=False, indent=2)
print("[OK] price_history 回写", DATA_DATE, "实测 3 条")

# ============================================================ 1. 长周期
lt = longterm.build_longterm()
series = lt["series"]
windows = {w["months"]: w for w in lt["windows"]}
season = lt["season"]
PREMIUM = lt["premium"]

# ============================================================ 2. 天气（按今日重切窗口）
wx = json.load(open(os.path.join(BASE_DIR, "data", "weather_2026-11-08.json"), encoding="utf-8"))
_all = [d for d in wx["core"]["daily"] if d.get("tmax") is not None]
core_daily = [d for d in _all if d["date"] >= TODAY]
if len(core_daily) < 15:
    core_daily = _all
clim = wx["core"].get("climatology") or {}
w3 = summarize_window(core_daily, 0, 3)
w7 = summarize_window(core_daily, 0, 7)
wh = summarize_window(core_daily, 7, 15)
wm = summarize_window(core_daily, 0, min(30, len(core_daily)))
WX_GEN = wx["generated_at"]

# ============================================================ 3. 六档预测（模型）
history = price.load_history()
fc = price.build_forecast(history, core_daily, clim=clim)
FRED = fc["红香葱"]
FBLK = fc["黑葱"]
BASE_RED = FRED["current"]
BASE_BLACK = FBLK["current"]

HORIZON_MAP = [("d3", "未来3天"), ("w1", "未来7天"), ("h1", "未来15天"),
               ("m1", "未来1个月"), ("m2", "未来2个月"), ("m3", "未来3个月")]


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


# —— 本期天气要点（动态计算，禁止硬编码落点）
_fc16 = core_daily[:16]
_peak = max(_fc16, key=lambda d: (d.get("precip") or 0))
PEAK_DATE = _peak["date"][5:].replace("-", "/")
PEAK_MM = round(_peak.get("precip") or 0, 1)
PEAK_TMAX = _peak.get("tmax")
PEAK_TMIN = _peak.get("tmin")
_cold = min([d for d in _fc16 if d.get("tmin") is not None], key=lambda d: d["tmin"])
COLD_DATE = _cold["date"][5:].replace("-", "/")
COLD_TMIN = _cold["tmin"]
RAIN_DAYS = sum(1 for d in _fc16 if (d.get("precip") or 0) >= 1)
RAIN_TOTAL = round(sum((d.get("precip") or 0) for d in _fc16), 1)
HEAVY_DATES = [d["date"][5:].replace("-", "/") for d in _fc16 if (d.get("precip") or 0) >= 5]
FIRST_RAIN = HEAVY_DATES[0] if HEAVY_DATES else "—"
HEAVY_DESC = "、".join("{0} {1:.1f}mm".format(d["date"][5:].replace("-", "/"), d["precip"])
                     for d in _fc16 if (d.get("precip") or 0) >= 5) or "无"
DZ = json.load(open(os.path.join(BASE_DIR, "data", "disaster_2026-11-08.json"), encoding="utf-8"))
DZ_TOP = (DZ.get("production_area") or [t for t in DZ.get("top", []) if t.get("is_production_area")])
DZ_DESC = "、".join("{0} {1}{2}".format(t["region"], t["hazard"], t["level"])
                   for t in DZ_TOP[:4]) or "无"

# —— 本期新增动态量（由鲜抓数据计算，禁止硬编码）
_RR = [t for t in DZ_TOP if "红河" in t.get("region", "")]
_LX = [t for t in DZ_TOP if "泸西" in t.get("region", "")]
RR_COUNT = len(_RR)
LX_COUNT = len(_LX)
RAIN_WARN = dict(DZ.get("hazard_stats", [])).get("暴雨", 0)
RR_DESC = ("红河州（泸西所属州）<b>{0}</b> 条、泸西本县 <b>{1}</b> 条").format(RR_COUNT, LX_COUNT)
YOY_RED = round((3.45 / 6.25 - 1) * 100, 1)  # 2025-11-07 隔年精确同日
YOY_BLK = round((2.96 / 4.16 - 1) * 100, 1)
YOY_WQ = round((2.30 / 7.00 - 1) * 100, 1)
# ============================================================ 4. 全量报价
def Q(date, item, variety, market, province, ptype, low, high, mid, source, url="", note=""):
    return {"date": date, "item": item, "variety": variety, "market": market,
            "province": province, "price_type": ptype, "unit": "元/公斤",
            "low": low, "high": high, "mid": mid,
            "source": source, "source_url": url, "note": note}


QUOTES = []
A = QUOTES.append

WX_URL = "http://mp.weixin.qq.com/s?__biz=MzU5MTc0MTM0MA==&mid=2247595891&idx=1&sn=9f328019a5a22eff99db2907d1d7e231"
DH_URL = "http://mp.weixin.qq.com/s?__biz=Mzg3Mzg1MTgwNw==&mid=2247490623&idx=1&sn=a968cfe8e8c71872004ac7fd12bf541d"
DH2_URL = "http://mp.weixin.qq.com/s?__biz=MzI2NzIyNTU1Ng==&mid=2247513958&idx=1&sn=cd02e1bf34d493aa03385ed74a085009"
XF_URL = "http://mp.weixin.qq.com/s?__biz=Mzg5NDcwNzI5MQ==&mid=2247504204&idx=1&sn=d29e17345f8ad69741a3659ca909fae0"
YMT_URL = "https://www.ymt.com/supply/61068014"
CNC_URL = "http://www.cncyms.cn/"
FOOD21_URL = "https://wap.21food.cn/price/product/3993.html"

# —— 泸西核心产区（11-07 实测，模型基准口径）
A(Q(DATA_DATE, "香葱", "红香葱", "云南红河州泸西县", "云南", "产地收购价",
    RED_LO, RED_HI, RED_MID, "云南蔬菜主产区每日菜价（泸西菜价表 11-07）", WX_URL,
    "本期模型基准。泸西红香葱 3.3-3.6、均价 3.45，与 11-06 的 3.45 完全持平；自 11-01 起连续七个报价日锁定 3.45，低位横盘已逾一周。公众号原表定调「今天行情行情整体平稳」"))
A(Q(DATA_DATE, "香葱", "黑香葱", "云南红河州泸西县", "云南", "产地收购价",
    BLK_LO, BLK_HI, BLK_MID, "云南蔬菜主产区每日菜价（泸西菜价表 11-07）", WX_URL,
    "泸西黑香葱 2.7-3.1、均价 2.96，与 11-06 完全持平；11-01 由 3.36 破位后连续七个报价日锁定 2.96，红黑价差 0.49"))
A(Q(DATA_DATE, "香葱", "红葱", "云南玉溪市通海县", "云南", "产地收购价",
    3.3, 3.6, 3.45, "云南蔬菜主产区每日菜价（通海菜价表 11-07）", WX_URL,
    "通海红葱 3.3-3.6 与泸西红香葱同步持平，确认滇中产区整体性定价"))
A(Q(DATA_DATE, "香葱", "黑葱", "云南玉溪市通海县", "云南", "产地收购价",
    2.7, 3.1, 2.96, "云南蔬菜主产区每日菜价（通海菜价表 11-07）", WX_URL,
    "通海黑葱 2.7-3.1 与泸西黑香葱同步锁定 2.96"))

# —— 全省综合（地慧数农 11-07 实证：红香葱 3.3-3.6 / 黑葱 2.7-3.1，与泸西完全对齐）
A(Q(DATA_DATE, "香葱", "红香葱", "云南产地综合交易价（全省）", "云南", "产地批发价",
    3.3, 3.6, 3.45, "云南蔬菜综合报价（11-07）", DH_URL,
    "全省综合交易价红香葱 3.3-3.6，与泸西、通海分区价完全对齐；官方总评「行情持续平稳，低位运行」，香葱未列入涨跌"))
A(Q(DATA_DATE, "香葱", "黑葱", "云南产地综合交易价（全省）", "云南", "产地批发价",
    2.7, 3.1, 2.96, "云南蔬菜综合报价（11-07）", DH_URL,
    "全省综合交易价黑葱 2.7-3.1，与泸西 / 通海同步持平于 2.96"))
A(Q(PREV_DATE, "香葱", "红香葱", "云南产地综合交易价（全省）", "云南", "产地批发价",
    3.3, 3.6, 3.45, "云南蔬菜综合报价（11-06 档案）", "", "上期全省综合价，与本期完全一致"))
A(Q("2026-10-30", "香葱", "红香葱", "云南产地综合交易价（全省）", "云南", "产地批发价",
    3.3, 3.6, 3.45, "云南蔬菜综合报价（10-30 档案）", "", "10-30 全省综合价首次低于当时泸西分区价 0.40 元，形成倒挂先行信号"))
A(Q("2026-10-29", "香葱", "红香葱", "云南产地综合交易价（全省）", "云南", "产地批发价",
    3.6, 4.0, 3.80, "云南蔬菜综合报价（10-29 档案）", "", "10-29 全省综合价，用于观察三级下移"))
A(Q("2026-10-26", "香葱", "红香葱", "云南产地综合交易价（全省）", "云南", "产地批发价",
    4.4, 5.0, 4.70, "云南蔬菜综合报价（10-26 档案）", "", "10-26 全省综合报价，当时仍高于泸西 0.85 元"))

# —— 晋宁次级产区（小蜂菜价通 11-07 其他菜价区）
A(Q(DATA_DATE, "香葱", "红香葱", "云南昆明市晋宁区（小蜂菜价通）", "云南", "产地收购价",
    3.50, 3.50, 3.50, "小蜂菜价通 · 晋宁菜价（11-07）", XF_URL,
    "晋宁其他菜价区红香葱 3.50、黑葱 2.90，与泸西 3.45 / 2.96 接近，验证滇中片区定价一致"))
A(Q(DATA_DATE, "香葱", "黑葱", "云南昆明市晋宁区（小蜂菜价通）", "云南", "产地收购价",
    2.90, 2.90, 2.90, "小蜂菜价通 · 晋宁菜价（11-07）", XF_URL,
    "晋宁黑葱 2.90，略低于泸西 2.96（0.06 元）"))

# —— 隔年精确同日档案（本期首次取得 2025-11-07 泸西 / 通海 / 王旗营 / 龙城全套）
A(Q("2025-11-07", "香葱", "红香葱", "云南红河州泸西县（隔年精确同日档案）", "云南", "产地收购价",
    6.0, 6.4, 6.25, "云南蔬菜主产区每日菜价（2025-11-07 历史档案）",
    "http://mp.weixin.qq.com/s?__biz=MzU5MTc0MTM0MA==&mid=2247592614&idx=1&sn=e58ff01cb0f5143c3b38cc3ef9b0553c",
    "⭐ 隔年精确同日泸西分区档案。本期 3.45 与之相比 -44.8%，为近五年同期最低且唯一跌破 4 元"))
A(Q("2025-11-07", "香葱", "黑香葱", "云南红河州泸西县（隔年精确同日档案）", "云南", "产地收购价",
    4.1, 4.6, 4.16, "云南蔬菜主产区每日菜价（2025-11-07 历史档案）", "",
    "隔年精确同日黑香葱 4.16，本期 2.96 与之相比 -28.8%"))
A(Q("2025-11-07", "香葱", "红葱", "云南玉溪市通海县（隔年精确同日档案）", "云南", "产地收购价",
    6.0, 6.4, 6.20, "云南蔬菜主产区每日菜价（2025-11-07 历史档案）", "", "隔年精确同日通海红葱 6.0-6.4"))
A(Q("2025-11-07", "香葱", "黑葱", "云南玉溪市通海县（隔年精确同日档案）", "云南", "产地收购价",
    4.1, 4.6, 4.35, "云南蔬菜主产区每日菜价（2025-11-07 历史档案）", "", "隔年精确同日通海黑葱 4.1-4.6"))
A(Q("2025-11-07", "小葱", "小葱", "昆明景臻王旗营蔬菜批发市场（隔年精确同日档案）", "云南", "销地批发价",
    7.0, 7.0, 7.00, "昆明市农业农村局（2025-11-07）", "https://nyncj.km.gov.cn/c/2025-11-07/5032963.shtml",
    "⭐ 隔年精确同日王旗营小葱 7.00、前一日成交量 35 吨；综合平均价 6.6、总吨位 2871。本期 2.30 与之相比 -67.1%"))
A(Q("2025-11-07", "小葱", "小葱（大宗价）", "昆明景臻王旗营蔬菜批发市场（隔年精确同日档案）", "云南", "销地批发价",
    7.0, 7.0, 7.00, "农业农村部信息中心（2025-11-07，证券之星转载）",
    "https://4g.stockstar.com/detail/IG2025110700017928", "隔年精确同日王旗营小葱大宗价 7.00，与昆明市农业农村局官方表互证"))
A(Q("2025-11-07", "大葱", "大葱", "云南昆明呈贡龙城农产品经营股份有限公司（隔年精确同日档案）", "云南", "销地批发价",
    2.5, 3.5, 3.00, "昆明市农业农村局（2025-11-07）", "https://nyncj.km.gov.cn/c/2025-11-07/5032981.shtml",
    "隔年精确同日替代品大葱中间价 3.00（最高 3.5 / 最低 2.5），成交量 45 吨"))
A(Q("2025-11-07", "香葱", "小香葱（平台挂牌）", "云南红河州泸西县（一亩田隔年同日档案）", "云南", "产地收购价",
    2.64, 2.64, 2.64, "一亩田全国小葱行情分析（2025-11-09 回溯 11-07）",
    "https://www.ymt.com/hangqing/hqfx-xiaocong-3-0-649574-20251109",
    "原始 1.32 元/斤 ×2 折算；平台挂牌口径，与同期官方地头价 6.25 差异显著，仅作口径分歧佐证"))
A(Q("2025-11-07", "香葱", "四季小葱（平台挂牌）", "河南平顶山（一亩田隔年同日档案）", "河南", "产地收购价",
    2.32, 2.32, 2.32, "一亩田全国小葱行情分析（2025-11-09 回溯 11-07）", "", "原始 1.16 元/斤 ×2 折算；北方产区挂牌"))
A(Q("2025-11-07", "香葱", "四季小葱（平台挂牌）", "河北产区（一亩田隔年同日档案）", "河北", "产地收购价",
    2.48, 2.48, 2.48, "一亩田全国小葱行情分析（2025-11-09 回溯 11-07）", "", "原始 1.24 元/斤 ×2 折算；北方产区挂牌"))
A(Q("2023-11-06", "香葱", "红香葱", "云南红河州泸西县（近似同日档案）", "云南", "产地收购价",
    4.0, 4.5, 4.35, "云南蔬菜主产区每日菜价（2023-11-06 历史档案）", "", "三年前近似同日泸西红香葱均价 4.35，本期较之 -20.7%"))
A(Q("2023-11-06", "香葱", "黑香葱", "云南红河州泸西县（近似同日档案）", "云南", "产地收购价",
    2.5, 3.2, 2.66, "云南蔬菜主产区每日菜价（2023-11-06 历史档案）", "", "三年前近似同日黑香葱均价 2.66，本期 2.96 反而高出 11.3%"))
A(Q("2022-11-06", "香葱", "红香葱", "云南红河州泸西县（近似同日档案）", "云南", "产地收购价",
    4.7, 5.2, 4.95, "云南蔬菜主产区每日菜价（2022-11-06 历史档案）", "", "四年前近似同日红香葱 4.7-5.2，本期较之 -30.3%"))
A(Q("2022-11-06", "香葱", "黑香葱", "云南红河州泸西县（近似同日档案）", "云南", "产地收购价",
    4.7, 5.2, 4.95, "云南蔬菜主产区每日菜价（2022-11-06 历史档案）", "", "四年前近似同日黑香葱 4.7-5.2，本期较之 -40.2%"))
A(Q("2025-11-06", "香葱", "红香葱", "云南产地综合交易价（全省·隔日档案）", "云南", "产地批发价",
    6.0, 6.4, 6.20, "云南蔬菜综合报价（2025-11-06 历史档案）", "", "隔日全省综合红香葱 6.20，与 11-07 泸西 6.25 相互印证"))
A(Q("2024-11-05", "香葱", "红香葱", "云南产地综合交易价（全省·近似同日档案）", "云南", "产地批发价",
    6.5, 7.6, 7.05, "云南蔬菜综合报价（2024-11-05 历史档案）", "", "两年前近似同日全省综合 7.05，本期 3.45 较之 -51.1%"))

# —— 昆明王旗营（11-07 官方表，价格栏 OCR 串列，口径显式标注）
A(Q(DATA_DATE, "小葱", "小葱（沿用序列口径）", "昆明景臻王旗营蔬菜批发市场", "云南", "销地批发价",
    2.30, 2.30, 2.30, "景臻·王旗营蔬菜批发平均价格统计（11-07）", DH2_URL,
    "⚠️ 口径提示：11-07 官方表小葱价格栏因三列并排 OCR 串列不可靠，疑似读数 4.00 无法与相邻的香菜 4.00 / 红椒 4.00 区分；"
    "本期主口径沿用 11-06 的 2.30（与农业农村部信息中心转载序列连续），明确标注为沿用值而非本期新成交价，"
    "不与其他口径平均、不并入销地样本均价的计算中枢解释"))
A(Q(DATA_DATE, "小葱", "小葱（成交量 / 市场总量）", "昆明景臻王旗营蔬菜批发市场", "云南", "销地批发价",
    2.30, 2.30, 2.30, "景臻·王旗营蔬菜批发平均价格统计（11-07）", DH2_URL,
    "本期可确证量能：小葱前一日成交量 30 吨（与 11-06 持平），市场综合平均价 4.25、总吨位 3151；"
    "较 11-06 的 4.31 / 3310 分别 -1.4% / -4.8%，量价齐弱"))
A(Q(DATA_DATE, "大葱", "大葱", "昆明景臻王旗营蔬菜批发市场", "云南", "销地批发价",
    4.50, 4.50, 4.50, "景臻·王旗营蔬菜批发平均价格统计（11-07）", DH2_URL,
    "替代品。王旗营大葱 4.50 元/公斤、前一日成交量 50 吨，较 11-06 的 5.50 / 70 吨回落；可与大葱行情日报 4.50 互证"))
A(Q(DATA_DATE, "香菜", "香菜", "昆明景臻王旗营蔬菜批发市场", "云南", "销地批发价",
    4.00, 4.00, 4.00, "农业农村部信息中心（11-07，证券之星转载）",
    "https://futures.stockstar.com/IG2026110700012916.shtml",
    "相邻品类参照。王旗营香菜 4.00，用于说明 OCR 表中「4」可能属香菜 / 红椒而非小葱"))

# —— 销区批发（11-07 实测，本期采集样本，元/公斤）
SALES_1107 = [
    ("广东汕头农副产品批发中心市场", "广东", 4.70, 4.70, 4.70, "农业农村部信息中心（11-07）",
     "https://4g.stockstar.com/detail/IG2026110700013075", "销地大宗批发价，与上期 4.70 持平"),
    ("江苏苏州南环桥农副产品批发市场", "江苏", 3.90, 3.90, 3.90, "农业农村部信息中心（11-07）",
     "https://futures.stockstar.com/IG2026110700013105.shtml", "销地大宗批发价"),
    ("武威昊天农产品交易市场暨仓储物流中心", "甘肃", 3.70, 3.70, 3.70, "农业农村部信息中心（11-07）",
     "https://futures.stockstar.com/IG2026110700013094.shtml", "西北销地小葱 3.70；同市场大葱仅 1.30"),
    ("辽宁朝阳市果菜批发市场", "辽宁", 1.50, 1.50, 1.50, "农业农村部信息中心（11-07）",
     "https://futures.stockstar.com/IG2026110700013152.shtml", "本期全国最低销区报价，较上期 1.70 再跌 -11.8%"),
    ("河北省怀来县京西果菜批发市场", "河北", 6.00, 6.00, 6.00, "京西果菜批发市场官网（11-07）",
     "http://www.jxgcsc.cn/Default/Price?Type=1", "官网小葱最高 / 最低 / 均价均 6.00 元/公斤"),
    ("安吉农副产品综合批发市场", "浙江", 7.00, 8.00, 7.50, "安吉农批市场今日菜价（11-07）",
     "http://mp.weixin.qq.com/s?__biz=MzA3ODU5MDAzNQ==&mid=2247511956&idx=1&sn=98f406e6d36d54b120b1a9ed36852545",
     "原始 3.5-4.0 元/斤 ×2 折算 = 7.0-8.0 元/公斤"),
    ("邯郸市经开区南大堡蔬菜批发市场（云南货源香葱）", "河北", 4.00, 4.40, 4.20, "邯郸南大堡批发市场（11-07）",
     "http://mp.weixin.qq.com/s?__biz=MzI2MzI3MjAwMw==&mid=2247503287&idx=1&sn=446061736ebae1319770465b9d134a65",
     "原始 高 2.2 / 中 2.1 / 低 2.0 元/斤 ×2 折算；云南货源香葱，产销地价差优质样本"),
    ("邯郸市经开区南大堡蔬菜批发市场（本地小葱香/钢）", "河北", 1.40, 3.20, 2.40, "邯郸南大堡批发市场（11-07）", "",
     "原始 高 1.6 / 中 1.2 / 低 0.7 元/斤 ×2 折算；本地货 2.40 对云南货 4.20 折价 43%"),
]
for _m, _p, _lo, _hi, _mid, _src, _url, _note in SALES_1107:
    A(Q(DATA_DATE, "小葱", "小葱", _m, _p, "销地批发价", _lo, _hi, _mid, _src, _url, _note))
A(Q(DATA_DATE, "小葱", "小葱（全国销地样本均价）", "本期采集销地批发市场聚合", "全国", "销地批发价",
    None, None, None, "本报告聚合（11-07 实测样本）", "",
    "聚合行仅用于标注样本量，不参与横截面均值计算"))

# —— 替代品 / 相邻品类 / 宏观参考（不同口径，单列，不并入小葱均价）
A(Q(DATA_DATE, "大葱", "大葱", "云南昆明呈贡龙城农产品经营股份有限公司", "云南", "销地批发价",
    3.75, 3.75, 3.75, "农业农村部信息中心（11-07）", "https://futures.stockstar.com/IG2026110700012986.shtml",
    "替代品。呈贡龙城大葱 3.75 元/公斤，同表无小葱品名"))
A(Q(DATA_DATE, "大葱", "大葱", "红星实业集团红星农副产品大市场", "湖南", "销地批发价",
    3.60, 3.60, 3.60, "农业农村部信息中心（11-07）", "https://futures.stockstar.com/IG2026110700013144.shtml",
    "替代品。长沙红星大市场大葱 3.60 元/公斤"))
A(Q(DATA_DATE, "葱", "葱（品类未细分）", "黄淮农产品股份有限公司", "河南", "销地批发价",
    2.00, 2.00, 2.00, "农业农村部信息中心（11-07）", "https://futures.stockstar.com/IG2026110700013185.shtml",
    "口径未细分（葱），单列参考，不并入香葱 / 小葱均价"))
A(Q(DATA_DATE, "葱", "葱（品类未细分）", "甘肃邦农农产品批发市场", "甘肃", "销地批发价",
    1.50, 1.50, 1.50, "农业农村部信息中心（11-07）", "https://futures.stockstar.com/IG2026110700013136.shtml",
    "口径未细分（葱），单列参考"))
A(Q(DATA_DATE, "大葱", "大葱", "吴忠鑫鲜农副产品批发市场", "宁夏", "销地批发价",
    1.60, 1.60, 1.60, "宁夏润鑫 / 吴忠鑫鲜官网（11-07）", "http://www.nxwzsncp.com/",
    "替代品。元/公斤直报；同表无小葱品名"))
A(Q(DATA_DATE, "大葱", "大葱（批发加权）", "北京市 6 家批发市场加权", "北京", "销地批发价",
    1.76, 1.76, 1.76, "北京价格网每日价格（11-07）", "https://www.beijingprice.cn/mrjg/",
    "替代品。原始 0.88 元/斤 ×2 折算，批发成交量 63.56 万公斤"))
A(Q(DATA_DATE, "大葱", "大葱", "青岛市城阳蔬菜水产品批发市场", "山东", "销地批发价",
    2.20, 3.60, 3.00, "大葱价格行情日报（11-07，折算自 1.10-1.80 元/斤）",
     "http://mp.weixin.qq.com/s?__biz=MzY5NzQzNTU3Nw==&mid=2247484202&idx=2&sn=82df50f5fbcd2d69a0c6314647feeb47",
    "替代品。大葱口径 2.20-3.60 元/公斤，勿与同城香葱 7-8 元/公斤档混淆"))
A(Q(DATA_DATE, "大葱", "大葱（产地挂牌）", "一亩田全国大葱产地均价", "全国", "产地收购价",
    1.36, 1.36, 1.36, "一亩田大葱产地行情（11-07 8:00 更新）",
    "http://mp.weixin.qq.com/s?__biz=MzY5NzQzNTU3Nw==&mid=2247484202&idx=2&sn=82df50f5fbcd2d69a0c6314647feeb47",
    "替代品。原始 0.68 元/斤 ×2 折算，20 条挂牌中 17 平 / 1 涨 / 2 跌，区间 0.29-0.95 元/斤"))
A(Q(DATA_DATE, "小香葱", "小香葱（高校食堂采购）", "中国科学技术大学饮食服务集团（11-05）", "安徽", "零售价",
    3.50, 3.50, 3.50, "中科大饮食服务集团蔬菜价格信息（第7725期）",
    "https://ysjt.ustc.edu.cn/2026/1105/c18022a758769/page.htm",
    "团餐采购口径，日期 11-05；单位元/斤，因该表按 500 克计，×2 折算前为 3.50，此处按原表直报并于 note 标注口径待核"))
A(Q(DATA_DATE, "大葱", "大葱（唐山乐亭冀东果菜）", "河北唐山乐亭冀东果菜批发市场", "河北", "销地批发价",
    3.50, 3.50, 3.50, "一亩田大葱全国行情分析（11-07）", "", "替代品。原始 1.75 元/斤 ×2 折算，常规销地通货最高"))
A(Q(DATA_DATE, "大葱", "大葱（郑州万邦国际）", "河南郑州万邦国际农产品物流股份公司", "河南", "销地批发价",
    1.64, 1.64, 1.64, "一亩田大葱全国行情分析（11-07）", "", "替代品。原始 0.82 元/斤 ×2 折算，常规销地通货最低"))

# —— 泸西产地→销地实时成交（农业农村部重点农产品市场信息平台，11-03 抓取存档）
A(Q("2026-11-03", "香葱", "细香葱", "江苏无锡市惠山区（泸西产地外销成交）", "江苏", "销地批发价",
    7.69, 7.69, 7.69, "农业农村部重点农产品市场信息平台（ncpscxx.moa.gov.cn）", "",
    "泸西县→无锡惠山实时成交 7.6923 元/kg，精品净葱含物流，对应产地集散价 3.45 形成产销价差约 2.2 倍"))
A(Q("2026-11-03", "香葱", "细香葱", "江苏无锡市新吴区（泸西产地外销成交）", "江苏", "销地批发价",
    6.67, 6.67, 6.67, "农业农村部重点农产品市场信息平台（ncpscxx.moa.gov.cn）", "",
    "泸西县→无锡新吴实时成交 6.6667 元/kg，精品净葱含物流"))

# —— 合并同仓其他自动化任务今日已采集的报价（glob 自动发现，去重）
import glob
import re
_seen = {(q["date"], q["market"], q["variety"], round(q["mid"], 2))
         for q in QUOTES if q["mid"] is not None}
_self = "xiangcong_{0}.json".format(TODAY)
for p in sorted(glob.glob(os.path.join(SRC_DIR, "*_{0}.json".format(TODAY)))):
    if os.path.basename(p) == _self:
        continue
    try:
        d = json.load(open(p, encoding="utf-8"))
    except Exception:
        continue
    for q in d.get("quotes", []):
        # 统一 schema 要求 date 为 YYYY-MM-DD；兄弟任务中的非精确日期无法按日归集，剔除
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(q.get("date", ""))):
            continue
        _m = q.get("mid")
        if _m is None:
            _l, _h = q.get("low"), q.get("high")
            _m = (_l + _h) / 2 if (_l is not None and _h is not None) else None
        if _m is None:
            continue
        key = (q.get("date"), q.get("market"), q.get("variety"), round(float(_m), 2))
        if key in _seen:
            continue
        _seen.add(key)
        QUOTES.append({
            "date": q.get("date"), "item": q.get("item", "香葱"),
            "variety": q.get("variety", ""), "market": q.get("market", ""),
            "province": q.get("province", ""), "price_type": q.get("price_type", "产地收购价"),
            "unit": "元/公斤", "low": q.get("low"), "high": q.get("high"), "mid": _m,
            "source": q.get("source", ""), "source_url": q.get("source_url", ""),
            "note": q.get("note", ""),
        })
# 移除占位聚合行（mid=None），保证落盘 schema 无空值
QUOTES = [q for q in QUOTES if q["mid"] is not None]
QUOTES.sort(key=lambda q: (q["date"], q["province"], -(q["mid"] or 0)))

_sales_mids = [v[4] for v in SALES_1107]
NATIONAL_MEAN = round(sum(_sales_mids) / len(_sales_mids), 2)
SALES_N = len(_sales_mids)
PROV_COUNT = len({q["province"] for q in QUOTES if q["province"]})

SUMMARY = (
    "泸西产地红香葱 11-07 报 <b>3.3-3.6、均价 3.45</b>，与 11-06 完全持平，"
    "自 11-01 起<b>连续七个报价日锁定 3.45</b>；地慧数农同日全省综合 3.3-3.6、通海 3.3-3.6，"
    "<b>滇中产区三口径实证完全对齐</b>，官方定调「行情持续平稳，低位运行」。"
    "黑香葱 2.7-3.1、均价 <b>2.96</b> 同样持平，红黑价差维持 0.49，晋宁 3.50 / 2.90 旁证片区定价一致。"
    "<b>本期首次取得隔年精确同日 2025-11-07 全套档案</b>：泸西红香葱 6.25、黑香葱 4.16、"
    "通海 6.0-6.4 / 4.1-4.6、王旗营小葱 7.00（35 吨、综合均价 6.6、总吨位 2871）、龙城大葱 3.00；"
    "本期分别 <b>{yoyred:+.1f}% / {yoyblk:+.1f}% / {yoywq:+.1f}%</b>，红香葱为近五年同期绝对最低且唯一跌破 4 元。"
    "<b>本期最大数据事件在销地口径</b>：王旗营 11-07 官方表小葱价格栏因三列并排 OCR 串列不可靠，"
    "疑似 4.00 与同表香菜 4.00 / 红椒 4.00 无法区分，本报告按「缺失值标注不插补」原则"
    "<b>沿用 2.30 序列口径并显式标注为沿用值</b>，不虚构跳涨、不与其他口径平均；"
    "可确证的是量能 30 吨持平、综合平均价 4.25、总吨位 3151（较 11-06 双降）。"
    "本期采集 <b>{sn}</b> 家销地批发市场样本，均价 <b>{nmean:.2f}</b> 元/公斤，"
    "区间 1.50（辽宁朝阳）~7.50（浙江安吉）；样本口径与上期不同，均值不可直接横比。"
    "气象端：未来 3 天泸西累计降水 {w3p} mm、最高温均 {w3t}℃、较近 30 日均值距平 <b>{ano:+.1f}℃</b>，"
    "<b>为本轮监测以来最大降温</b>；未来 15 天累计降水<b>再下修至 {rtot} mm</b>（雨日 {rdays} 天、峰值 {pdate} {pmm} mm、最冷 {cdate} {ctmin}℃），"
    "上行驱动由「强降水」进一步切换为<b>低温霜冻 + 采收受阻 + 洗葱损耗 + 霜霉/灰霉病</b>，洪涝型断供概率继续下降。"
    "灾害端出现方向性变化：中央气象台 11-08 生效预警全网 <b>{dtot}</b> 条，结构切换为<b>大风 {dwind} 条主导</b>（暴雨仅 {drain} 条、暴雪 {dsnow} 条）；"
    "<b>上期成片覆盖红河州的暴雨预警消退至 1 条</b>（{rrcount}），"
    "而<b>河北唐山 / 承德 / 秦皇岛、辽宁葫芦岛暴雪红色预警成片</b>，北方产区退市对南菜北运形成新的支撑。"
    "六档中枢（精品净葱 / 集散价口径）：{path} 元/公斤。"
).format(nmean=NATIONAL_MEAN, sn=SALES_N,
         yoyred=YOY_RED, yoyblk=YOY_BLK, yoywq=YOY_WQ,
         w3p=w3.get("precip_total"), w3t=w3.get("tmax_avg"),
         ano=(w3.get("tmax_avg") or 0) - (clim.get("tmax_mean") or 0),
         rtot=RAIN_TOTAL, rdays=RAIN_DAYS, pdate=PEAK_DATE, pmm=PEAK_MM,
         cdate=COLD_DATE, ctmin=COLD_TMIN,
         dtot=DZ.get("total", 0), drain=RAIN_WARN,
         dwind=dict(DZ.get("hazard_stats", [])).get("大风", 0),
         dsnow=dict(DZ.get("hazard_stats", [])).get("暴雪", 0),
         dprod=len(DZ_TOP), rrcount=RR_DESC, ddesc=DZ_DESC,
         path=" → ".join(str(f["center"]) for f in FORECASTS))

DOC = {
    "task": "香葱行情",
    "task_id": "376dffed-c5e4-4904-a77a-29193947212a",
    "date": TODAY,
    "generated_at": GEN,
    "market_scope": "全国 / 云南 / 红河州泸西县（本期覆盖 {0} 省区）".format(PROV_COUNT),
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
    """全国横截面：按 price_type 分组均值（剔除大类葱与零售价）。"""
    groups = {}
    for q in QUOTES:
        if q["item"] in ("大葱", "葱"):
            continue
        if q["price_type"] == "零售价":
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


def chart_diverge():
    """本期重点：全省综合价 vs 泸西分区价 —— 倒挂后收敛。"""
    pts = [("10-26", 3.85, 4.70), ("10-29", 3.85, 3.80),
           ("10-30", 3.85, 3.45), ("10-31", 3.45, 3.45), ("11-01", 3.45, 3.45),
           ("11-05", 3.45, 3.45), ("11-06", 3.45, 3.45), ("11-07", 3.45, 3.45)]
    ml, mr, mt, mb = 60, 120, 36, 44
    hi, lo = 5.0, 3.0
    hh = 200
    xmap = lambda i: ml + i * (W - ml - mr) / (len(pts) - 1)
    ymap = lambda v: mt + (hi - v) * (hh - mt - mb) / (hi - lo)
    g = ['<svg viewBox="0 0 {0} {1}" class="cv">'.format(W, hh + 34)]
    g.append('<rect width="{0}" height="{1}" fill="#fbfcfe"/>'.format(W, hh + 34))
    for k in range(5):
        v = hi - (hi - lo) * k / 4
        y = ymap(v)
        g.append('<line x1="{0}" y1="{1:.1f}" x2="{2}" y2="{1:.1f}" stroke="#e6eaf0"/>'.format(ml, y, W - mr))
        g.append('<text x="{0}" y="{1:.1f}" font-size="11" fill="#6b7280" text-anchor="end">{2:.2f}</text>'.format(ml - 8, y + 4, v))
    g.append('<path d="{0}" fill="none" stroke="#2563eb" stroke-width="2.4"/>'.format(
        _path([(i, p[1]) for i, p in enumerate(pts)], xmap, ymap)))
    g.append('<path d="{0}" fill="none" stroke="#dc2626" stroke-width="2.4" stroke-dasharray="6 3"/>'.format(
        _path([(i, p[2]) for i, p in enumerate(pts)], xmap, ymap)))
    for i, (d, lx, qs) in enumerate(pts):
        x = xmap(i)
        g.append('<circle cx="{0:.1f}" cy="{1:.1f}" r="4.2" fill="#2563eb"/>'.format(x, ymap(lx)))
        g.append('<circle cx="{0:.1f}" cy="{1:.1f}" r="4.2" fill="#dc2626"/>'.format(x, ymap(qs)))
        g.append('<text x="{0:.1f}" y="{1:.1f}" font-size="11.5" fill="#2563eb" text-anchor="middle">{2:.2f}</text>'.format(x, ymap(lx) + 18, lx))
        g.append('<text x="{0:.1f}" y="{1:.1f}" font-size="11.5" fill="#dc2626" text-anchor="middle">{2:.2f}</text>'.format(x, ymap(qs) - 10, qs))
        diff = qs - lx
        col = "#16a34a" if diff < 0 else ("#dc2626" if diff > 0 else "#6b7280")
        txt = "差 {0:+.2f}".format(diff) if abs(diff) > 0.001 else "收敛 0.00"
        g.append('<text x="{0:.1f}" y="{1}" font-size="11" fill="{2}" font-weight="600" text-anchor="middle">{3}</text>'.format(
            x, hh + 12, col, txt))
        g.append('<text x="{0:.1f}" y="{1}" font-size="11" fill="#6b7280" text-anchor="middle">{2}</text>'.format(x, hh - mb + 60, d))
    g.append('<text x="{0}" y="{1}" font-size="11.5" fill="#2563eb">━ 泸西分区价（模型基准）</text>'.format(ml + 6, mt - 14))
    g.append('<text x="{0}" y="{1}" font-size="11.5" fill="#dc2626">┅ 云南全省综合交易价</text>'.format(ml + 190, mt - 14))
    g.append("</svg>")
    return "".join(g)


def chart_wq():
    """王旗营：价格 + 成交量（双线）。"""
    pts = [("10-25", 3.5, 35), ("10-26", 3.5, 35), ("10-27", 3.0, 35),
           ("10-28", 2.5, 35), ("10-29", 2.5, 25), ("10-30", 2.5, 30),
           ("10-31", 2.2, 30), ("11-01", 2.5, 30),
           ("11-04", 2.5, 30), ("11-05", 2.3, 25), ("11-06", 2.3, 30), ("11-07", 2.3, 30)]
    ml, mr, mt, mb = 56, 56, 34, 46
    hh = 220
    xmap = lambda i: ml + i * (W - ml - mr) / (len(pts) - 1)
    ymap = lambda v: mt + (4.0 - v) * (hh - mt - mb) / (4.0 - 2.0)
    vmap = lambda v: mt + (40 - v) * (hh - mt - mb) / (40 - 15)
    g = ['<svg viewBox="0 0 {0} {1}" class="cv">'.format(W, hh + 40)]
    g.append('<rect width="{0}" height="{1}" fill="#fbfcfe"/>'.format(W, hh + 40))
    for k in range(5):
        v = 4.0 - (4.0 - 2.0) * k / 4
        y = ymap(v)
        g.append('<line x1="{0}" y1="{1:.1f}" x2="{2}" y2="{1:.1f}" stroke="#e6eaf0"/>'.format(ml, y, W - mr))
        g.append('<text x="{0}" y="{1:.1f}" font-size="11" fill="#6b7280" text-anchor="end">{2:.1f}</text>'.format(ml - 8, y + 4, v))
    for t in (15, 20, 25, 30, 35, 40):
        y = vmap(t)
        g.append('<text x="{0}" y="{1:.1f}" font-size="10.5" fill="#f59e0b" text-anchor="start">{2}t</text>'.format(W - mr + 8, y + 4, t))
    g.append('<path d="{0}" fill="none" stroke="#2563eb" stroke-width="2.4"/>'.format(
        _path([(i, p[1]) for i, p in enumerate(pts)], xmap, ymap)))
    g.append('<path d="{0}" fill="none" stroke="#f59e0b" stroke-width="2.0" stroke-dasharray="5 3"/>'.format(
        _path([(i, p[2]) for i, p in enumerate(pts)], xmap, vmap)))
    for i, (d, pr, vol) in enumerate(pts):
        x = xmap(i)
        g.append('<circle cx="{0:.1f}" cy="{1:.1f}" r="3.8" fill="#2563eb"/>'.format(x, ymap(pr)))
        g.append('<circle cx="{0:.1f}" cy="{1:.1f}" r="3.8" fill="#f59e0b"/>'.format(x, vmap(vol)))
        g.append('<text x="{0:.1f}" y="{1:.1f}" font-size="11" fill="#2563eb" text-anchor="middle">{2:.1f}</text>'.format(x, ymap(pr) + 17, pr))
        g.append('<text x="{0:.1f}" y="{1:.1f}" font-size="10.5" fill="#b45309" text-anchor="middle">{2}</text>'.format(x, vmap(vol) - 9, vol))
        g.append('<text x="{0:.1f}" y="{1}" font-size="10.5" fill="#6b7280" text-anchor="middle">{2}</text>'.format(x, hh + 20, d))
    g.append('<text x="{0}" y="{1}" font-size="11.5" fill="#2563eb">━ 小葱批发均价（元/公斤，左轴）</text>'.format(ml + 6, mt - 14))
    g.append('<text x="{0}" y="{1}" font-size="11.5" fill="#b45309">┅ 前一日成交量（吨，右轴）</text>'.format(ml + 250, mt - 14))
    g.append('<text x="{0}" y="{1}" font-size="10.5" fill="#9ca3af">注：成交量为各期发布表中标注的前一日交易量</text>'.format(ml + 6, hh + 36))
    g.append("</svg>")
    return "".join(g)


def chart_yoy():
    """近五年同期（2025-11-07 精确同日；2022/2023/2024 为近似日）泸西红香葱均价对比。"""
    pts = [("2022-11-06*", 4.95), ("2023-11-06*", 4.35), ("2024-11-05*", 7.05),
           ("2025-11-07", 6.25), ("2026-11-07", 3.45)]
    ml, mr, mt, mb = 60, 30, 34, 48
    hh = 230
    hi = max(v for _, v in pts) * 1.18
    xmap = lambda i: ml + i * (W - ml - mr) / (len(pts) - 1)
    ymap = lambda v: mt + (hi - v) * (hh - mt - mb) / hi
    g = ['<svg viewBox="0 0 {0} {1}" class="cv">'.format(W, hh + 30)]
    g.append('<rect width="{0}" height="{1}" fill="#fbfcfe"/>'.format(W, hh + 30))
    for k in range(5):
        v = hi * k / 4
        y = ymap(v)
        g.append('<line x1="{0}" y1="{1:.1f}" x2="{2}" y2="{1:.1f}" stroke="#e6eaf0"/>'.format(ml, y, W - mr))
        g.append('<text x="{0}" y="{1:.1f}" font-size="11" fill="#6b7280" text-anchor="end">{2:.1f}</text>'.format(ml - 8, y + 4, v))
    g.append('<path d="{0}" fill="none" stroke="#94a3b8" stroke-width="1.8" stroke-dasharray="5 3"/>'.format(
        _path([(i, v) for i, (_, v) in enumerate(pts)], xmap, ymap)))
    for i, (d, v) in enumerate(pts):
        x = xmap(i)
        cur = d.startswith("2026")
        c = "#dc2626" if cur else "#2563eb"
        bw = 46
        g.append('<rect x="{0:.1f}" y="{1:.1f}" width="{2}" height="{3:.1f}" rx="4" fill="{4}" opacity="0.85"/>'.format(
            x - bw / 2, ymap(v), bw, hh - mb - ymap(v), c))
        g.append('<text x="{0:.1f}" y="{1:.1f}" font-size="12" font-weight="600" fill="{2}" text-anchor="middle">{3:.2f}</text>'.format(
            x, ymap(v) - 7, c, v))
        g.append('<text x="{0:.1f}" y="{1}" font-size="10.5" fill="#6b7280" text-anchor="middle">{2}</text>'.format(x, hh + 14, d[:7]))
        if not cur:
            pct = (3.45 / v - 1) * 100
            g.append('<text x="{0:.1f}" y="{1}" font-size="10" fill="#16a34a" text-anchor="middle">{2:.1f}%</text>'.format(
                x, hh + 26, pct))
    g.append('<text x="{0}" y="{1}" font-size="11.5" fill="#1f2937">11 月初同期泸西红香葱均价（元/公斤，* 为近似日）</text>'.format(ml + 6, mt - 14))
    g.append('<text x="{0}" y="{1}" font-size="10.5" fill="#16a34a">柱下绿色百分比 = 2026 年相对该年的同比涨跌幅</text>'.format(ml + 250, mt - 14))
    g.append("</svg>")
    return "".join(g)


def chart_luxi_spread():
    """泸西多源口径分歧。"""
    pts = [("一亩田·黑葱视频看货(8.00元/斤)", 16.00),
           ("惠农网·代收代办挂牌(6.00元/斤)", 12.00),
           ("惠农网·白铁杆整车(10000元/吨)", 10.00),
           ("惠农网·精品小香葱(4.50元/斤)", 9.00),
           ("惠农网·香葱常年供货(3.50元/斤)", 7.00),
           ("惠农网·小葱产地直供(3.00元/斤)", 6.00),
           ("惠农网·小香葱35cm(2.80元/斤)", 5.60),
           ("惠农网·分葱粗管细管(2.75元/斤)", 5.50),
           ("国资云农·地头大宗(10-28,已断更)", 5.00),
           ("本报告推算·地头统货大宗", 4.60),
           ("惠农网·加工厂/电商/精品货", 4.00),
           ("泸西·集散均价 红香葱(模型基准)", 3.45),
           ("云南全省综合交易价 红香葱", 3.45),
           ("惠农网·地头价挂牌(1.70元/斤)", 3.40),
           ("惠农网·红葱通货35-50cm", 3.00),
           ("泸西·集散均价 黑香葱", 2.96),
           ("云南全省综合交易价 黑香葱", 2.96),
           ("一亩田·泸西平台行情 小葱(1.32元/斤)", 2.64),
           ("昆明王旗营·小葱销地(11-07沿用口径)", 2.30),
           ("一亩田·泸西平台行情 四季小葱", 2.28),
           ("一亩田·小葱通货(2.10元/公斤)", 2.10),
           ("惠农网·香葱通货/代发(1.00元/斤)", 2.00),
           ("惠农网·葱苗/香葱通货(0.80元/斤)", 1.60),
           ("一亩田·泸西45-55cm整车(元/公斤)", 1.50),
           ("一亩田·四季小香葱整车(0.60元/斤)", 1.20)]
    pts.sort(key=lambda x: -x[1])
    ml, mt = 250, 34
    hi = max(v for _, v in pts) * 1.25
    row_h = 30
    g = ['<svg viewBox="0 0 {0} {1}" class="cv">'.format(W, mt + row_h * len(pts) + 16)]
    g.append('<rect width="{0}" height="{1}" fill="#fbfcfe"/>'.format(W, mt + row_h * len(pts) + 16))
    for i, (name, v) in enumerate(pts):
        y = mt + i * row_h
        bw = (W - ml - 90) * v / hi
        c = "#dc2626" if v >= 5.0 else ("#2563eb" if v >= 3.4 else "#16a34a")
        g.append('<text x="18" y="{0}" font-size="11.5" fill="#374151">{1}</text>'.format(y + 15, name))
        g.append('<rect x="{0}" y="{1}" width="{2:.1f}" height="16" rx="4" fill="{3}" opacity="0.85"/>'.format(ml, y + 2, bw, c))
        g.append('<text x="{0:.1f}" y="{1}" font-size="11" fill="#111827" font-weight="600">{2:.2f}</text>'.format(ml + bw + 8, y + 15, v))
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


base_row = ("<tr class='base'><td>当前基准（{0} 实测）</td><td>—</td><td>{1:.2f}</td>"
            "<td>—</td><td>{2:.2f}</td><td>—</td><td>—</td><td>—</td><td>基准</td></tr>").format(
    DATA_DATE, BASE_RED, BASE_BLACK)
_inv = {v: k for k, v in HORIZON_MAP}
frows = []
for f in FORECASTS:
    r = RRED[_inv[f["horizon"]]]
    b = RBLK[_inv[f["horizon"]]]
    cls = "up" if r["delta_pct"] >= 3 else ("flat" if r["delta_pct"] > -3 else "down")
    bcls = "up" if b["delta_pct"] >= 3 else ("flat" if b["delta_pct"] > -3 else "down")
    frows.append("<tr><td>{0}</td><td>{1}</td><td><b>{2:.2f}</b></td><td>{3:.2f}~{4:.2f}</td>"
                 "<td>{5:.2f}</td><td>{6:.2f}~{7:.2f}</td>"
                 "<td><span class='{8}'>{9:+.1f}%</span></td>"
                 "<td><span class='{10}'>{11:+.1f}%</span></td><td>{12}</td></tr>".format(
                     f["horizon"], f["target_date"], r["center"], r["low"], r["high"],
                     b["center"], b["low"], b["high"],
                     cls, r["delta_pct"], bcls, b["delta_pct"], r["confidence"]))

_centers = [r["center"] for r in FRED["rows"]]
_mono = all(_centers[i] <= _centers[i + 1] for i in range(len(_centers) - 1))
if _mono:
    MONO_DESC = "六档呈<b>单调递增</b>"
else:
    _gap = _centers[-1] - _centers[-2]
    MONO_DESC = ("六档<b>前五档单调递增</b>，第 6 档（3 个月）与第 5 档（2 个月）<b>基本持平</b>"
                 "（{0:+.2f} 元 / {1:+.1f}%）".format(_gap, _gap / _centers[-2] * 100))

def _nf(v):
    return "—" if v is None else "{:.2f}".format(v)


qrows = []
for q in QUOTES:
    qrows.append("<tr><td>{0}</td><td>{1}</td><td>{2}</td><td>{3}</td><td>{4}</td>"
                 "<td class='num'>{5}</td><td class='num'>{6}</td><td class='num'><b>{7}</b></td>"
                 "<td class='src'>{8}</td></tr>".format(
                     q["date"], q["item"], q["variety"] or "—", q["market"], q["price_type"],
                     _nf(q["low"]), _nf(q["high"]), _nf(q["mid"]), q["source"]))

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

disaster_top = DZ
prod_hits = DZ_TOP
d_rows = "".join(
    "<tr><td>{0}</td><td>{1}</td><td>{2}预警</td><td>{3}</td><td>{4}</td></tr>".format(
        t["region"], t["hazard"], t["level"], t["impact"], t["issuetime"]) for t in prod_hits)
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
.good{background:#f0fdf4;border-left:3px solid #16a34a;padding:10px 13px;border-radius:0 7px 7px 0;font-size:13px;margin:12px 0}
ul{margin:8px 0 8px 20px;padding:0}
li{margin:4px 0}
.foot{color:var(--mu);font-size:12px;margin-top:30px;border-top:1px solid var(--bd);padding-top:14px}
"""

HTML = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>香葱行情分析 · {today}</title><style>{css}</style></head><body><div class="wrap">
<h1>香葱行情分析 · {today}</h1>
<div class="sub">生成时间 {gen}（北京时间） · 全国 / 云南 / 红河州泸西县 · 数据日期 {ddate}（当日行情次日发布） · 天气快照 {wxgen}</div>

<div class="kpis">
  <div class="kpi"><div class="l">泸西模型基准（红香葱）</div><div class="v" style="color:#2563eb">{br:.2f}</div><div class="d">元/公斤 · 滇中产区集散价 · {ddate} 实测 · <b>0.00% 持平（连续 7 日）</b></div></div>
  <div class="kpi"><div class="l">泸西黑香葱</div><div class="v" style="color:#16a34a">{bb:.2f}</div><div class="d">元/公斤 · {ddate} 实测 · <b>连续锁定 2.96</b></div></div>
  <div class="kpi"><div class="l">云南全省综合（红）</div><div class="v">3.45</div><div class="d">元/公斤 · 3.3-3.6 · <b>三口径实证对齐</b></div></div>
  <div class="kpi"><div class="l">昆明王旗营小葱</div><div class="v">2.30*</div><div class="d">元/公斤 · <b>*沿用口径</b> · 量 30 吨持平</div></div>
  <div class="kpi"><div class="l">本期销地样本均价</div><div class="v">{nmean:.2f}</div><div class="d">元/公斤 · 11-07 实测 · <b>{sn}</b> 家市场</div></div>
  <div class="kpi"><div class="l">同比（隔年精确同日）</div><div class="v" style="color:#16a34a">{yoyred:.1f}%</div><div class="d">2025-11-07 泸西 6.25 → 3.45</div></div>
</div>

<div class="note"><b>本期核心结论：</b>{summ}</div>

<h2>一、历史长周期回顾（近 10 年）</h2>
<div class="card">{c_decade}</div>
<table><thead><tr><th>窗口</th><th>期初</th><th>期末</th><th>涨跌</th><th>均值</th><th>最低</th><th>最高</th></tr></thead>
<tbody>{wrows}</tbody></table>
<div class="note">口径：主序列为<b>通货毛葱</b>（元/公斤），精品净葱 = 主序列 × 1.66。
10 年 CAGR <b>{cagr:.1f}%</b>，长周期中枢下移；近 12 个月 -6.2%、近 24 个月 +2.5%、近 36 个月 -5.9%，
显示长周期下行但近两年已在低位企稳。<b>不可与第六章预测口径横向比较</b>：预测与「当前中枢」为精品净葱 / 集散价。</div>
<h3>近 36 个月</h3><div class="card">{c_36}</div>
<h3>季节指数（1.00 = 年度均值）</h3><div class="card">{c_season}</div>
<div class="note">季节规律：春峰 4-5 月（1.25 / 1.16）→ 夏谷 7-8 月（0.68 / 0.72）→ 冬旺 11-1 月（1.09-1.14）。
11 月因子升至 1.121、12 月 1.140，<b>季节性本身对四季度构成上行动力</b>；
但 2026 年 11 月初已是近五年同期绝对最低（见 5.1），<b>季节性上行未必能抵消同比低基数与结构性供给充裕</b>。</div>

<h2>二、天气与灾害（{today} 鲜抓）</h2>
<div class="card">{c_wx}</div>
<table><thead><tr><th>窗口</th><th>最高温均</th><th>最低温均</th><th>累计降水</th><th>雨日</th><th>大风日</th><th>主导天气</th></tr></thead><tbody>
<tr><td>未来 3 天</td><td>{w3t}</td><td>{w3t2}</td><td>{w3p} mm</td><td>{w3r}</td><td>{w3g}</td><td>{w3d}</td></tr>
<tr><td>未来 1 周</td><td>{w7t}</td><td>{w7t2}</td><td>{w7p} mm</td><td>{w7r}</td><td>{w7g}</td><td>{w7d}</td></tr>
<tr><td>第 8-15 天</td><td>{wht}</td><td>{wht2}</td><td>{whp} mm</td><td>{whr}</td><td>{whg}</td><td>{whd}</td></tr>
</tbody></table>
<div class="warn"><b>关键天气过程（降温创本轮监测最大，降水继续下修）：</b>未来 3 天泸西累计降水 {w3p} mm、
最高气温均 {w3t}℃、最低温均 {w3t2}℃、较近 30 日均值距平 <b>{ano:+.1f}℃</b>，
<b>降温幅度超过上期的 -6.9℃，为本轮监测以来最大</b>；
其中 11-09 最高温骤降至约 10.7℃、最低 6.6℃，由前期 21℃ 级水平断崖式回落，随后 11-10 最低 6.5℃。
未来 15 天累计降水 <b>{rtot} mm</b>、雨日 <b>{rdays}</b> 天（上期鲜抓 15 天 36.6 mm，本期<b>再下修约 19%</b>），
降水峰值落在 <b>{pdate}（{pmm} mm）</b>，当日最高温 {ptmax}℃、最低温 {ptmin}℃；最冷日 <b>{cdate} 最低温 {ctmin}℃</b>。
主要强降水日：{hdesc}。11-14 起连续多日无有效降水，转为干冷大风为主。
本期上行驱动由「强降水」进一步切换为<b>低温霜冻 + 采收受阻 + 洗葱损耗上升 + 霜霉/灰霉病风险</b>：
低温对香葱生长与外运的抑制不弱于强降水，但<b>降水预期连续两期下修意味着洪涝型断供概率持续下降</b>，
上行情景不宜线性外推，低温能否兑现为实际减产仍需未来 1-2 周田间反馈验证。</div>
<div class="warn"><b>全国层面（中央气象台 {today} 生效预警）：</b>全网生效预警 <b>{dtot}</b> 条，
其中<b>大风 {dwind} 条、暴雨 {drain} 条、暴雪 {dsnow} 条、大雾 {dfog} 条</b>（上期为大雾 42 / 雷电 31 / 暴雨 13）。
灾种结构：{hazard_desc}。涉及香葱主产区 <b>{dprod}</b> 条（{prod_desc}）。
{dprod_note}</div>
<div class="warn"><b>本期最大气象变化：红河州暴雨预警消退，北方暴雪红色成片。</b>
{rrcount}；上期曾出现河口 / 个旧 / 屏边 / 蒙自 / 金平等 6 条成片暴雨预警，
本期红河州仅剩金平县地质灾害黄色 1 条，<b>核心产区所在州的洪涝型断供风险显著回落</b>；
云南境内强降水中心退至普洱澜沧（暴雨红 + 地质灾害橙）、孟连（暴雨橙 + 雷电黄），均位于滇西南、非泸西外运主通道。
与此同时，<b>河北唐山迁安 / 迁西 / 遵化、承德兴隆 / 宽城、秦皇岛卢龙及辽宁葫芦岛建昌共 7 条暴雪红色预警</b>，
另有承德、朝阳凌源暴雪橙与内蒙赤峰暴雪黄——北方产区进入退市期，
对「南菜北运」形成新增需求支撑，是本期唯一明确的方向性利多。
泸西本县仍无独立生效预警，未来 3 天 {w3p} mm 降水与断崖式降温为主要本地扰动。</div>
<h3>当前生效预警（涉及香葱主产区）</h3>
<table><thead><tr><th>区域</th><th>灾种</th><th>级别</th><th>影响</th><th>发布时间</th></tr></thead><tbody>{drows}</tbody></table>
<div class="note">全网生效预警合计 <b>{dtot}</b> 条，其中涉及主产区 <b>{dprod}</b> 条（取 production_area 全量，非 top 截断）。
灾害数据由中央气象台 findAlarm 接口于本期运行开始时鲜抓，落盘至 <code>data/disaster_{today}.json</code>；
天气由 Open-Meteo 15 天预报 + 近 30 日归档计算，落盘至 <code>data/weather_{today}.json</code>。</div>

<h2>三、市面常见香葱种类</h2>
<h3>3.1 流通端商品分类（决定报价口径）</h3>
<table><thead><tr><th>分类</th><th>特征</th><th>主要用途</th></tr></thead><tbody>{varieties}</tbody></table>
<h3>3.2 主要栽培品种</h3>
<table><thead><tr><th>品种</th><th>特征</th><th>适种区域</th><th>产量</th></tr></thead><tbody>{cultivars}</tbody></table>

<h2>四、全国香葱种植省份</h2>
<table><thead><tr><th>省/区域</th><th>主产县市</th><th>产业地位</th></tr></thead><tbody>{provs}</tbody></table>
<div class="note">口径提示：全国小香葱种植面积第三方统计分歧较大（有 78.56 万亩与主产区加总两种量级），
本报告以<b>主产区加总</b>口径呈现，仅用于判断区域供给权重，不建议作为绝对面积引用。
本期北方暴雪红色预警集中在河北、辽宁，对应华北 / 东北夏秋产区已基本退市，
四季度供给进一步向云南、广西、广东等南方产区集中。</div>

<h2>五、全国行情横截面（{ddate}）</h2>
<div class="card">{c_cross}</div>
<h3>5.1 五年同期对比：本期首次取得 2025-11-07 精确同日全套档案</h3>
<div class="card">{c_yoy}</div>
<div class="warn"><b>同比腰斩（2025-11-07 精确同日）：</b>
泸西分区红香葱 <b>6.25</b>（6.0-6.4）、黑香葱 <b>4.16</b>（4.1-4.6），通海红葱 6.0-6.4、黑葱 4.1-4.6；
王旗营小葱 <b>7.00</b>、成交量 35 吨，市场综合平均价 6.6、总吨位 2871；呈贡龙城大葱中间价 3.00。
本期泸西 3.45 / 2.96、王旗营 2.30（沿用口径），红香葱同比 <b>{yoyred:.1f}%</b>、黑香葱 <b>{yoyblk:.1f}%</b>、王旗营 <b>{yoywq:+.1f}%</b>。
更早近似同日：2023-11-06 泸西红 4.35 / 黑 2.66（本期 -20.7% / <b>+11.3%</b>，黑葱是唯一同比转正的口径）、
2022-11-06 泸西红 4.95 / 黑 4.95（-30.3% / -40.2%）、2024-11-05 全省综合 7.05（本期 -51.1%）。
<b>红香葱为近五年同期绝对最低，且是唯一跌破 4 元的一年</b>；
但需注意去年同期的 6.25 亦属近年高位，同比跌幅部分来自高基数，不宜简单等同于本年度供给恶化的全部幅度。
另有 2025-11-07 一亩田平台挂牌泸西小香葱 1.32 元/斤（折 2.64 元/公斤），与官方地头价 6.25 相差 2.4 倍，
再次印证跨口径横比严重失真。</div>
<h3>5.2 全省综合价与泸西分区价：收敛后长期锁定</h3>
<div class="card">{c_div}</div>
<div class="good"><b>收敛后进入「平台锁定」第七个报价日：</b>10-30 全省综合价首次跌破泸西分区价 0.40 元（倒挂先行信号），
10-31 泸西由 3.85 一步下调至 3.45 完成收敛；此后 11-01 至 11-07 <b>全省综合、泸西分区、通海分区三口径全部锁定 3.45 / 2.96</b>，
连续七个报价日无变动。本期地慧数农 11-07 全省综合报价 3.3-3.6 / 2.7-3.1 为当日实证，
总评「行情持续平稳，低位运行」，<b>三口径对齐已由模型沿用升级为实地确认</b>。
晋宁小蜂菜价通 3.50 / 2.90 亦在 0.06 元内，滇中片区定价高度一致。
这既确认了<b>全省综合口径对泸西分区价约 1 个报价日的领先性</b>，
也提示当前定价已进入<b>低流动性 / 报价黏性</b>状态——真实成交重心可能低于挂牌；
历史上该口径多次「长期不动、一次性跳变」，需以销地量能与全省综合价的下一步变动为破位信号。</div>
<h3>5.3 本期最大数据事件：王旗营小葱口径分歧</h3>
<div class="card">{c_wq}</div>
<div class="warn"><b>官方表小葱价格栏 OCR 串列，按「缺失值标注不插补」处理：</b>
景臻·王旗营 11-07 蔬菜批发平均价格统计表为三列并排版式，检索到的 OCR 文本中
「小葱 4 30」的 4.00 与同表「香菜 4 7」「红椒 4 60」高度重合，无法排除列错位；
若采信 4.00 将意味着单日 +73.9% 跳涨，与产地横盘、销地普弱、市场综合平均价由 4.31 回落至 4.25 全部矛盾。
本报告<b>不虚构跳涨、不插补、不与其他口径平均</b>：主序列沿用 11-06 的 2.30（与农业农村部信息中心转载序列连续），
并在报价表中显式标注为「沿用序列口径、非本期新成交价」。
可确证的量能信息为：<b>小葱前一日成交量 30 吨持平</b>、大葱 4.50（50 吨，较 11-06 的 5.50 / 70 吨回落）、
香菜 4.00、<b>市场综合平均价 4.25、总吨位 3151</b>，较 11-06 的 4.31 / 3310 分别 -1.4% / -4.8%，
<b>量价齐弱，上期「量先于价」回暖信号本期未获延续</b>。</div>
<div class="warn"><b>销地横截面：</b>本期采集 {sn} 家销地批发市场小葱样本，均价 <b>{nmean:.2f}</b> 元/公斤，
区间 1.50（辽宁朝阳）~7.50（浙江安吉）；邯郸南大堡云南货源香葱 4.20 对本地小葱 2.40 溢价 75%，
云南货仍有品质溢价。<b>口径提示：</b>本期样本构成与上期 16 家不同（上期含海口、青岛城阳、武汉四季美等高价样本），
<b>均价下降主要来自样本变化，不可解读为销地价格整体下跌</b>；上期可比样本中，
汕头 4.70 持平、辽宁朝阳 1.70→1.50（-11.8%）、京西果菜 6.00 持平，实际走势分化但无断崖。
11-07 农业农村部「全国 49 家批发市场小葱 roundup」未检索到，本期不虚构全量样本，仅以实际取得的 {sn} 家呈现。</div>
<h3>5.4 泸西多源口径分歧</h3>
<div class="card">{c_spread}</div>
<div class="warn"><b>口径分层（延续上期框架，本期未重新采集平台挂牌）：</b>按可信度分为
①<b>成交价层</b>——泸西红香葱集散均价 3.45（模型基准）、全省综合 3.45、黑香葱 2.96、通海同价、晋宁 3.50 / 2.90、王旗营销地 2.30（沿用）；
②<b>推算层</b>——地头统货大宗约 4.60（国资云农源自 10/29 断更，按历史加成率 1.33 推算，已标注）；
③<b>平台挂牌层</b>——1.20-5.60（整车 / 通货 / 精品，长期不刷新、非成交）；
④<b>服务 / 精选层</b>——6.00-16.00（代收代办、视频看货、包邮精装，含服务费与包装，不可用于定价）。
判断：<b>真实成交中枢落在 3.00（通货）～4.60（水洗统货大宗）之间</b>，跨平台横比必须同口径同规格。
本期新增的隔年同日一亩田挂牌 2.64 对官方地头 6.25 的 2.4 倍偏离，进一步说明挂牌层不可用于定价。</div>
<h3>5.5 全量报价明细（{n} 条）</h3>
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
本期基准<b>维持 {br:.2f}</b>（泸西分区 {ddate} 实测，红黑均较 11-06 持平），
当前现价低于 20 日实测均线 {ma:.2f}（缺口 {gap:.1f}%），均值回归项为正向，
叠加 11-12 月季节因子上行与断崖式降温带来的供给收缩，{mono}：{path}。
区间为情景区间，非统计置信区间。
<b>为何第 6 档上行乏力：</b>3 个月档目标日虽处春节前备货窗口，但季节因子在 1 月末已向 2 月（0.969）插值回落，
与节日脉冲相互抵消；真正的高点窗口在 2 月上旬春节当周，已超出 3 个月预测边界。
<b>较上期变动：</b>起算基准未变，六档中枢随天气窗口推进调整；本期降水总量再下修 19%、红河州暴雨预警消退，
但降温幅度创监测最大且北方暴雪成片，供给端风险结构由「洪涝」转为「低温 + 南菜北运」，
<b>上行情景概率由 25% 下调至 20%、下行情景由 25% 上调至 30%</b>（见第八章）。
<b>口径铁律：</b>本章预测为精品净葱 / 集散价，第一章长周期主序列为通货毛葱，二者相差约 1.66 倍，禁止横向混用。</div>

<h2>七、风险提示</h2>
<ul>
<li><b>销地口径不可靠（本期首要风险）：</b>王旗营 11-07 官方表小葱价格栏 OCR 串列，
疑似 4.00 与香菜 / 红椒 4.00 混淆；本期已按缺失值标注处理并沿用 2.30，
但<b>连续两期无法取得可靠销地小葱成交价</b>，销地先行指标实质失效，需补充农业农村部单市场转载或市场直报源。</li>
<li><b>剧烈降温与霜冻：</b>未来 3 天最高温均 {w3t}℃、距平 <b>{ano:+.1f}℃</b>（本轮监测最大），
11-09 最高约 10.7℃ / 最低 6.6℃，最冷日 {cdate} 最低温 {ctmin}℃。
低温抑制生长、抬升洗葱损耗与霜霉 / 灰霉病风险，但也可能延缓上市、短期收缩供给；<b>是否兑现为减产尚未验证</b>。</li>
<li><b>降水连续下修的双刃性：</b>未来 15 天累计降水 {rtot} mm、雨日 {rdays} 天（上期 36.6 mm，本期再降约 19%），
峰值 {pdate}（{pmm} mm），11-14 起转为干冷无有效降水。<b>洪涝型断供概率进一步下降</b>，
若低温亦不及预期，季节性上行将被供给充裕抵消。</li>
<li><b>红河州暴雨预警消退：</b>上期成片覆盖核心产区所在州的 6 条暴雨预警本期仅剩金平地质灾害黄 1 条，
{rrcount}。这是上期上修情景概率的主要依据，<b>本期该依据已消失</b>，构成下行情景概率上调的核心理由。</li>
<li><b>北方暴雪的间接利多需时间传导：</b>河北、辽宁 7 条暴雪红色预警意味着北方产区退市，
理论上支撑南菜北运；但外运通道同时受大风影响（全网大风 {dwind} 条），
且终端需求疲弱时产区议价能力有限，<b>不宜据单条气象信号直接外推价格</b>。</li>
<li><b>报价黏性 / 一次性跳变风险：</b>泸西分区价自 11-01 起连续七个报价日锁在 3.45，
历史上该口径多次呈现「长期不动、一次性跳变」（10-26 前连续三日 3.85 → 10-31 一步下调至 3.45）。
锁定时间越长，累计未释放的调价压力越大，应继续以全省综合价与销地量能作为先行指标。</li>
<li><b>同比高基数与结构性过剩：</b>2026 年 11 月初红香葱同比 {yoyred:.1f}%，但去年同期 6.25 属近年高位；
跌幅不宜全部归因于本年度供给恶化，然而泸西复种 46.7 万亩次面积高企，<b>供给过剩仍是结构性约束</b>，
不宜线性外推「跌得多就会涨得多」。</li>
<li><b>口径分歧：</b>泸西当日公开报价极值差可达 13 倍以上（1.20 ~ 16.00 元/公斤，沿用上期挂牌快照），
跨平台横比严重失真；本期隔年同日一亩田挂牌 2.64 与官方 6.25 的 2.4 倍偏离为新增佐证。</li>
<li><b>替代竞争：</b>大葱处明显低位（北京新发地加权 1.76、宁夏海吉星 1.60、武威昊天 1.30、呈贡龙城 3.75 元/公斤；
一亩田全国大葱产地均价 0.68 元/斤，11-07 止跌微涨 1.49%），对香葱消费形成替代压制。</li>
<li><b>数据源断更：</b>国资云农泸西地头大宗价自 10/29 起连续多期未发布（末值 10-28 的 5.00），
地头统货大宗 4.60 为<b>推算值</b>，已在报价表与图表中标注，建议补充替代实地采集源。</li>
</ul>

<h2>八、情景推演</h2>
<table><thead><tr><th>情景</th><th>触发条件</th><th>3 个月中枢</th><th>概率</th></tr></thead><tbody>
<tr><td><b>A 基准</b></td><td>泸西维持 3.45，季节性上行 + 降温温和兑现，北方暴雪带来南菜北运增量但需求端不恶化</td><td>{a3:.2f} 元/公斤</td><td>50%</td></tr>
<tr><td><b>B 上修</b></td><td>{cdate} 前后低温超预期致明显减产、霜霉病扩散，或南菜北运提前放量、销地跟涨；
基准口径上修至地头统货大宗 4.60（较现基准 +33%）</td><td>{b3:.2f} 元/公斤</td><td>20%</td></tr>
<tr><td><b>C 下修</b></td><td>红河州暴雨风险消退 + 降水连续下修使供给持续充裕，销地量价齐弱带动泸西二次下调至 3.00（较现基准 -13%）</td><td>{c3:.2f} 元/公斤</td><td>30%</td></tr>
</tbody></table>
<div class="note">情景中枢按<b>基准价替代法</b>推演：以 A 档 3 个月中枢 {a3:.2f} 为基数，
按替代基准 / 现基准（{br:.2f}）等比缩放——B 档替代基准为地头统货大宗 4.60、C 档为再跌至 3.00。
<b>概率较上期调整</b>：A 维持 50%、B 由 25% 下调至 20%、C 由 25% 上调至 30%。
依据是本期出现三项边际转弱：① 上期据以上修的红河州成片暴雨预警消退至 1 条；
② 15 天降水总量再下修约 19%，洪涝型断供概率继续下降；
③ 王旗营销地口径连续两期不可靠且可确证的综合平均价 / 总吨位双降，「量先于价」信号未延续。
反向支撑为降温创监测最大与北方暴雪红色成片，故 A 档概率维持、下调幅度克制。
此处概率仅反映<b>相对路径</b>分歧，不构成价格承诺。</div>

<div class="foot">
数据来源：中央气象台（nmc.cn）、Open-Meteo 预报与归档 API、农业农村部信息中心（含证券之星转载）、
农业农村部重点农产品市场信息平台、昆明市农业农村局 / 景臻·王旗营、云南蔬菜主产区每日菜价、
云南蔬菜综合报价（地慧数农）、小蜂菜价通（晋宁）、昆明市呈贡龙城农产品经营股份公司、
京西果菜批发市场（怀来）、安吉农副产品综合批发市场、邯郸南大堡蔬菜批发市场、
吴忠鑫鲜农副产品市场、北京价格网、中国科学技术大学饮食服务集团、一亩田、大葱价格行情日报、国资云农。<br>
本报告由自动化任务 376dffed 生成，仅供经营参考，不构成交易建议。价格单位除特别标注外均为元/公斤；
带 * 的数值为沿用口径或近似日档案，已在对应条目注明。
</div>
</div></body></html>"""

a3 = FRED["rows"][5]["center"]
b3 = a3 * 4.60 / BASE_RED
c3 = a3 * 3.00 / BASE_RED
_hz = dict(disaster_top.get("hazard_stats", []))
HAZARD_DESC = "、".join("{0} {1}".format(k, v) for k, v in sorted(_hz.items(), key=lambda x: -x[1])[:7]) or "无"
PROD_DESC = "、".join("{0} {1}{2}".format(t["region"], t["hazard"], t["level"])
                     for t in prod_hits[:6]) or "无"
if prod_hits:
    DPROD_NOTE = ("主产区相关预警共 {n} 条，结构由前期「红河州成片暴雨」切换为「大风主导 + 滇西南局地强降水」；"
                  "其中红河州 {rn} 条、泸西本县 {ln} 条，上期成片暴雨预警已基本消退。"
                  "本期天气风险以断崖式降温、{pdate} 降水（{pmm} mm）与北方暴雪红色成片导致的"
                  "南菜北运需求变化三者叠加为主。").format(
        n=len(prod_hits), rn=RR_COUNT, ln=LX_COUNT, pdate=PEAK_DATE, pmm=PEAK_MM)
else:
    DPROD_NOTE = ("本期无直接影响香葱主产区的生效预警，天气风险以断崖式降温与 {pdate} 本地降水（{pmm} mm）为主。").format(
        pdate=PEAK_DATE, pmm=PEAK_MM)


html = HTML.format(
    css=CSS, today=TODAY, gen=GEN, ddate=DATA_DATE, summ=SUMMARY, wxgen=WX_GEN,
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
    dfog=_hz.get("大雾", 0), dwind=_hz.get("大风", 0), drain=_hz.get("暴雨", 0),
    dice=_hz.get("道路结冰", 0) + _hz.get("道路冰雪", 0),
    dsnow=_hz.get("暴雪", 0), dthu=_hz.get("雷电", 0), ddust=_hz.get("沙尘", 0),
    varieties=varieties, cultivars=cultivars, provs=prov_html,
    c_cross=chart_cross(), c_div=chart_diverge(), c_wq=chart_wq(), c_yoy=chart_yoy(),
    c_spread=chart_luxi_spread(),
    n=len(QUOTES), qrows="".join(qrows),
    c_fc=chart_forecast(), base=base_row, frows="".join(frows), mono=MONO_DESC,
    path=" → ".join(str(r["center"]) for r in FRED["rows"]),
    nmean=NATIONAL_MEAN, sn=SALES_N,
    yoyred=YOY_RED, yoyblk=YOY_BLK, yoywq=YOY_WQ,
    rrcount=RR_DESC,
    rtot=RAIN_TOTAL, rdays=RAIN_DAYS, pdate=PEAK_DATE, pmm=PEAK_MM,
    ptmax=PEAK_TMAX, ptmin=PEAK_TMIN, cdate=COLD_DATE, ctmin=COLD_TMIN,
    hdesc=HEAVY_DESC, hazard_desc=HAZARD_DESC, prod_desc=PROD_DESC, dprod_note=DPROD_NOTE,
    a3=a3, b3=b3, c3=c3,
)

html_path = os.path.join(OUT_DIR, "香葱行情分析_{0}.html".format(TODAY))
with open(html_path, "w", encoding="utf-8") as f:
    f.write(html)
print("[OK] 报告", html_path, len(html) // 1024, "KB")
print("红葱中枢:", BASE_RED, "→", [r["center"] for r in FRED["rows"]])
print("黑葱中枢:", BASE_BLACK, "→", [r["center"] for r in FBLK["rows"]])
print("20日均线:", FRED["ma20"])
