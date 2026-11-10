# -*- coding: utf-8 -*-
"""香葱行情定时任务落盘 + 图表报告生成器（任务 376dffed）· 2026-11-10

产出：
  1) data/sources/xiangcong_2026-11-10.json  统一 schema 全量报价 + 六档预测
  2) outputs/香葱行情分析_2026-11-10.html     长周期 / 收敛 / 同比 / 预测 图表

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

DATA_DATE = "2026-11-09"   # 最新可获取的实测报价日（当日数据次日发布）
PREV_DATE = "2026-11-08"

# 本期核心实测（泸西分区，11-09 实测，次日发布）
RED_MID, RED_LO, RED_HI = 3.45, 3.2, 3.5   # 区间下移 0.1，官方均价标签仍 3.45
BLK_MID, BLK_LO, BLK_HI = 2.76, 2.5, 2.9
PREV_RED, PREV_BLK = 3.45, 2.76
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
     "note": "泸西菜价（2026-11-09 实测）红香葱 3.2-3.5，官方均价标签 3.45；区间较 11-08 的 3.3-3.6 下移 0.1、官方措辞「红香葱微掉」，但均价标签未同步（区间中值 3.35）。按不改写历史序列原则，模型基准沿用标签值 3.45，同时显式登记区间中值 3.35 作为先行信号；自 11-01 起连续九个报价日锁定 3.45"},
    {"date": DATA_DATE, "variety": "黑葱", "market": "云南产地", "price": BLK_MID,
     "source": "observed",
     "note": "泸西菜价（2026-11-09 实测）黑香葱 2.5-2.9 均价 2.76，与 11-08 完全持平（11-08 破位后暂稳，连续两日锁定）；通海黑葱 2.5-2.9 同步，红黑价差维持 0.69"},
    {"date": DATA_DATE, "variety": "小葱", "market": "昆明王旗营", "price": 2.30,
     "source": "observed",
     "note": "2026-11-09 王旗营三种读数并存：农业农村部 50 家 roundup 3.50、景臻平均价统计表（公众号转载）4.00/30吨（与 11-07 争议读数一致，疑 T-1 转载）、本仓历史序列沿用 2.30。三口径并列、不平均、不改写历史序列；主序列仍沿用 2.30 并标注为沿用值"},
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
wx = json.load(open(os.path.join(BASE_DIR, "data", "weather_2026-11-10.json"), encoding="utf-8"))
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

# —— 3 个月档：本期已修复节日脉冲（节后线性衰减尾），不再存在日历悬崖
FORECASTS[-1]["note"] += ("；目标日 2027-02-08 为春节（2027-02-06）后 2 天，本期已为节日脉冲"
                          "增加节后 21 天线性衰减尾、消除上一版日历悬崖；中枢较 2 个月档小幅回落"
                          "系节后需求渐退叠加 2 月季节因子回落，属正常路径而非模型边界效应")


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
DZ = json.load(open(os.path.join(BASE_DIR, "data", "disaster_2026-11-10.json"), encoding="utf-8"))
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
YOY_RED = round((3.45 / 6.25 - 1) * 100, 1)  # 2025-11-09 隔年精确同日
YOY_BLK = round((2.76 / 4.16 - 1) * 100, 1)
YOY_WQ = round((2.30 / 6.50 - 1) * 100, 1)
# ============================================================ 4. 全量报价
def Q(date, item, variety, market, province, ptype, low, high, mid, source, url="", note=""):
    return {"date": date, "item": item, "variety": variety, "market": market,
            "province": province, "price_type": ptype, "unit": "元/公斤",
            "low": low, "high": high, "mid": mid,
            "source": source, "source_url": url, "note": note}


QUOTES = []
A = QUOTES.append

# 本期主要来源 URL
WX_URL = "http://mp.weixin.qq.com/s?__biz=MzU5MTc0MTM0MA==&mid=2247595902&idx=1&sn=b071594ff8a2a067b793973392d54855"
QSH_A_URL = "http://mp.weixin.qq.com/s?__biz=MzI0NzExNjUxMw==&mid=2653645827&idx=1&sn=71b969c7435b68f6f91e8b81aaa74d71"
QSH_B_URL = "http://mp.weixin.qq.com/s?__biz=MzkxNzY0OTUwMA==&mid=2247489176&idx=1&sn=26d7b99449da78ace5cda4d826231e88"
ROUND50_URL = "https://wap.stockstar.com/detail/IG2026110900006185"
DCONG_URL = "https://futures.stockstar.com/IG2026110900006166.shtml"
LONGCHENG_URL = "https://futures.stockstar.com/IG2026110900006737.shtml"
KM2025_URL = "https://nyncj.km.gov.cn/c/2025-11-10/5033363.shtml"
YMT_URL = "https://www.ymt.com/supplylist/search-25-7300/pn95"

# —— 泸西核心产区（11-09 实测，模型基准口径）
A(Q(DATA_DATE, "香葱", "红香葱", "云南红河州泸西县", "云南", "产地收购价",
    RED_LO, RED_HI, RED_MID, "云南蔬菜主产区每日菜价（泸西菜价表 11-09）", WX_URL,
    "本期模型基准。红香葱 3.2-3.5、官方均价标签 3.45；区间较 11-08 的 3.3-3.6 下移 0.1，官方措辞「云南强降温来袭…红香葱微掉」，但均价标签未同步更新，自 11-01 起连续九个报价日锁定 3.45"))
A(Q(DATA_DATE, "香葱", "红香葱（区间中值口径）", "云南红河州泸西县", "云南", "产地收购价",
    3.2, 3.5, 3.35, "云南蔬菜主产区每日菜价（泸西菜价表 11-09，区间中值推算）", WX_URL,
    "★推算值：按 3.2-3.5 取区间中值 3.35，与官方均价标签 3.45 相差 0.10。登记为「区间先行的向下信号」，不改写历史序列、不用于模型基准；若下一期均价标签跟随下移，则确认补跌"))
A(Q(DATA_DATE, "香葱", "黑香葱", "云南红河州泸西县", "云南", "产地收购价",
    BLK_LO, BLK_HI, BLK_MID, "云南蔬菜主产区每日菜价（泸西菜价表 11-09）", WX_URL,
    "黑香葱 2.5-2.9、均价 2.76，与 11-08 完全持平；11-08 破位 -6.8% 后暂稳，连续两日锁定，红黑价差维持 0.69"))
A(Q(DATA_DATE, "香葱", "红葱", "云南玉溪市通海县", "云南", "产地收购价",
    3.1, 3.5, 3.30, "云南蔬菜主产区每日菜价（通海菜价表 11-09）", WX_URL,
    "通海红葱由 11-08 的 3.3-3.6 下调至 3.1-3.5（中值 3.30），与泸西区间下移方向一致，片区同步走弱而非单市场噪声"))
A(Q(DATA_DATE, "香葱", "黑葱", "云南玉溪市通海县", "云南", "产地收购价",
    2.5, 2.9, 2.70, "云南蔬菜主产区每日菜价（通海菜价表 11-09）", WX_URL,
    "通海黑葱 2.5-2.9 持平，与泸西区间完全一致；按区间中值 2.70 登记"))

# —— 全省综合：上期首要缺口本期补齐（11-09 两个转载源并列，不平均）
A(Q(DATA_DATE, "香葱", "红香葱", "云南产地综合交易价（全省，源A）", "云南", "产地批发价",
    3.1, 3.5, 3.30, "11月9日云南产地蔬菜综合交易价格（云南本地公众号）", QSH_A_URL,
    "★上期首要数据缺口已补齐。源A 红香葱 3.1-3.5（中值 3.30）、黑葱 2.5-2.9；同表香菜 4.0-5.0、茴香 3.0-3.5、韭黄 8.0-8.5，与 11-09 分区表一致，判为本期现值"))
A(Q(DATA_DATE, "香葱", "黑葱", "云南产地综合交易价（全省，源A）", "云南", "产地批发价",
    2.5, 2.9, 2.70, "11月9日云南产地蔬菜综合交易价格（云南本地公众号）", QSH_A_URL,
    "全省综合黑葱 2.5-2.9，已与泸西 2.5-2.9 完全对齐 → 上期「黑葱下调是否传导至省级口径」的验证问题得到肯定答案"))
A(Q(DATA_DATE, "香葱", "红香葱", "云南产地综合交易价（全省，源B）", "云南", "产地批发价",
    3.3, 3.6, 3.45, "11月9日云南产地蔬菜综合交易价格（宁夏四季鲜/北方蔬菜报转载）", QSH_B_URL,
    "⚠️ 同日另一转载源给出 3.3-3.6（中值 3.45），与源A 相差 0.15；该表香菜 3.0-4.0、茴香 2.9-3.1、韭黄 7.5-8.0 整体偏低，疑为 T-1 转载。两源并列登记、不平均、不混用"))
A(Q(DATA_DATE, "香葱", "黑葱", "云南产地综合交易价（全省，源B）", "云南", "产地批发价",
    2.5, 2.9, 2.70, "11月9日云南产地蔬菜综合交易价格（宁夏四季鲜/北方蔬菜报转载）", QSH_B_URL,
    "两转载源黑葱完全一致 2.5-2.9，故黑葱传导结论无源依赖；红葱是否倒挂则取决于取哪一源，报告已限定"))

# —— 全省综合历史档案（11-08 仍缺失，不插补）
A(Q(PREV_DATE, "香葱", "红香葱", "云南产地综合交易价（全省，11-08 缺口标注）", "云南", "产地批发价",
    None, None, None, "数据缺口（11-08 全省综合数值表未取得）", "",
    "⚠️ 缺失值占位：11-08 地慧数农全省综合数值表本期仍未取得，按「缺失值只标注不插补」保留空值，不虚构。收敛图 11-07 → 11-09 连线跨此缺口"))
A(Q("2026-11-07", "香葱", "红香葱", "云南产地综合交易价（全省）", "云南", "产地批发价",
    3.3, 3.6, 3.45, "云南蔬菜综合报价（11-07 档案）", "",
    "11-07 全省综合实证 3.3-3.6，为收敛图最后一个连续观测点"))
A(Q("2026-11-07", "香葱", "黑葱", "云南产地综合交易价（全省）", "云南", "产地批发价",
    2.7, 3.1, 2.96, "云南蔬菜综合报价（11-07 档案）", "", "11-07 全省综合黑葱 2.7-3.1，此后下调至 2.5-2.9"))
A(Q("2026-10-30", "香葱", "红香葱", "云南产地综合交易价（全省）", "云南", "产地批发价",
    3.3, 3.6, 3.45, "云南蔬菜综合报价（10-30 档案）", "", "10-30 全省综合首次低于当时泸西分区价 0.40 元，形成倒挂先行信号"))
A(Q("2026-10-29", "香葱", "红香葱", "云南产地综合交易价（全省）", "云南", "产地批发价",
    3.6, 4.0, 3.80, "云南蔬菜综合报价（10-29 档案）", "", "10-29 全省综合价，用于观察三级下移"))
A(Q("2026-10-26", "香葱", "红香葱", "云南产地综合交易价（全省）", "云南", "产地批发价",
    4.4, 5.0, 4.70, "云南蔬菜综合报价（10-26 档案）", "", "10-26 全省综合报价，当时仍高于泸西 0.85 元"))

# —— 隔年精确同日 2025-11-09 全套档案（本期首次取得）
A(Q("2025-11-09", "香葱", "红香葱", "云南红河州泸西县（隔年精确同日档案）", "云南", "产地收购价",
    6.0, 6.4, 6.25, "云南蔬菜主产区每日菜价（2025-11-09 历史档案）",
    "http://mp.weixin.qq.com/s?__biz=MzU5MTc0MTM0MA==&mid=2247592642&idx=1&sn=7596d3ec2975dbe3f96db61a9accb079",
    "⭐ 隔年精确同日泸西分区档案。本期 3.45 与之相比 -44.8%，为近五年同期绝对最低且唯一跌破 4 元；当日措辞「小香葱平稳，白蒜苗小涨」"))
A(Q("2025-11-09", "香葱", "黑香葱", "云南红河州泸西县（隔年精确同日档案）", "云南", "产地收购价",
    4.1, 4.6, 4.16, "云南蔬菜主产区每日菜价（2025-11-09 历史档案）", "",
    "隔年精确同日黑香葱 4.1-4.6 均价 4.16，本期 2.76 与之相比 -33.7%"))
A(Q("2025-11-09", "香葱", "红葱", "云南玉溪市通海县（隔年精确同日档案）", "云南", "产地收购价",
    6.0, 6.4, 6.20, "云南蔬菜主产区每日菜价（2025-11-09 历史档案）", "", "隔年精确同日通海红葱 6.0-6.4"))
A(Q("2025-11-09", "香葱", "黑葱", "云南玉溪市通海县（隔年精确同日档案）", "云南", "产地收购价",
    4.1, 4.6, 4.35, "云南蔬菜主产区每日菜价（2025-11-09 历史档案）", "", "隔年精确同日通海黑葱 4.1-4.6"))
A(Q("2025-11-09", "香葱", "红香葱", "云南产地综合交易价（全省，隔年同日档案）", "云南", "产地批发价",
    6.0, 6.4, 6.20, "云南蔬菜市场综合菜价（2025-11-09 历史档案）", "http://zhongdapeng.com/shucaijiage/2015.html",
    "隔年同日全省综合红香葱 6.0-6.4，与泸西分区同价，说明 2025 年不存在本期所见的分化"))
A(Q("2025-11-09", "香葱", "黑葱", "云南产地综合交易价（全省，隔年同日档案）", "云南", "产地批发价",
    4.1, 4.6, 4.35, "云南蔬菜市场综合菜价（2025-11-09 历史档案）", "", "隔年同日全省综合黑葱 4.1-4.6"))
A(Q("2025-11-09", "小葱", "小葱", "昆明景臻王旗营蔬菜批发市场（隔年精确同日档案）", "云南", "销地批发价",
    6.50, 6.50, 6.50, "昆明市农业农村局（2025-11-09 官方平均价格统计表）", KM2025_URL,
    "⭐ 隔年精确同日王旗营小葱 6.50、前一日成交量 45 吨；市场综合平均价 6.37、总吨位 3264。本期本仓沿用序列 2.30 与之相比 -64.6%；若用农业农村部口径 3.50 则为 -46.2%"))
A(Q("2025-11-09", "小葱", "小葱（农业农村部单市场表）", "昆明景臻王旗营蔬菜批发市场（隔年精确同日档案）", "云南", "销地批发价",
    6.50, 6.50, 6.50, "农业农村部信息中心（2025-11-09，证券之星转载）", "https://4g.stockstar.com/detail/IG2025110900003000",
    "隔年同日农业农村部单市场表小葱大宗价 6.50，与景臻官方表互证；同表大葱 4.20、香菜 28.00"))
A(Q("2025-11-09", "小葱", "小葱（平台挂牌）", "云南红河州泸西县（隔年同日平台档案）", "云南", "产地收购价",
    2.64, 2.64, 2.64, "一亩田全国小葱价格行情分析（2025-11-09 档案）",
    "https://www.ymt.com/hangqing/hqfx-xiaocong-3-0-649574-20251109",
    "★平台挂牌非成交。原始 1.32 元/斤 ×2 折算 = 2.64 元/公斤，泸西小葱 11-03 至 11-09 连续 7 日锁定 1.32 元/斤"))

# —— 两年前精确同日 2024-11-09 档案（首次取得）
A(Q("2024-11-09", "香葱", "红香葱", "云南红河州泸西县（两年前精确同日档案）", "云南", "产地收购价",
    6.5, 7.5, 7.05, "云南蔬菜主产区每日菜价（2024-11-09 历史档案）",
    "http://mp.weixin.qq.com/s?__biz=MzU5MTc0MTM0MA==&mid=2247582593&idx=1&sn=4908302f1071c92c37406c108fe5b1cb",
    "两年前精确同日泸西红香葱 6.5-7.5 均价 7.05，本期 3.45 较之 -51.1%；当日措辞「黑香葱下滑，蒜苗回落」"))
A(Q("2024-11-09", "香葱", "黑香葱", "云南红河州泸西县（两年前精确同日档案）", "云南", "产地收购价",
    6.0, 6.3, 6.06, "云南蔬菜主产区每日菜价（2024-11-09 历史档案）", "",
    "两年前精确同日黑香葱 6.0-6.3 均价 6.06，本期 2.76 较之 -54.5%；较 11-08 档案的 6.36 已下滑 0.30，与当日「黑香葱下滑」措辞一致"))
A(Q("2024-11-09", "香葱", "红葱", "云南玉溪市通海县（两年前精确同日档案）", "云南", "产地收购价",
    6.5, 7.0, 6.75, "云南蔬菜主产区每日菜价（2024-11-09 历史档案）", "", "两年前精确同日通海红葱 6.5-7.0"))
A(Q("2024-11-09", "香葱", "黑葱", "云南玉溪市通海县（两年前精确同日档案）", "云南", "产地收购价",
    6.0, 6.3, 6.15, "云南蔬菜主产区每日菜价（2024-11-09 历史档案）", "", "两年前精确同日通海黑葱 6.0-6.3"))
A(Q("2024-11-09", "香葱", "红香葱", "云南产地综合交易价（全省，两年前同日档案）", "云南", "产地批发价",
    6.5, 7.6, 7.05, "云南综合菜价（2024-11-09 历史档案）",
    "http://mp.weixin.qq.com/s?__biz=MzI1ODY0ODU1NQ==&mid=2247491371&idx=1&sn=b53a1d0ccf88436dc6ffb2057f495bde",
    "两年前同日全省综合红香葱 6.5-7.6、黑葱 5.6-6.3，明显高于本期 3.1-3.6 / 2.5-2.9"))
A(Q("2023-11-08", "香葱", "红香葱（全省综合地头毛菜口径）", "云南市场综合（菜易通地头毛菜）", "云南", "产地地头价",
    4.0, 4.5, 4.25, "云南每日菜价·云南市场综合菜价（2023-11-08 历史档案）", "",
    "★三年前近似同日：口径为全省综合地头毛菜采购价，非泸西分区集散价，不可与 3.45 严格横比；仅作五年同期量级参照"))
A(Q("2022-11-06", "香葱", "红香葱", "云南红河州泸西县（四年前近似同日档案）", "云南", "产地收购价",
    4.7, 5.2, 4.95, "云南蔬菜主产区每日菜价（2022-11-06 历史档案）", "",
    "四年前近似同日红香葱 4.7-5.2，本期 3.45 较之 -30.3%；2022-11-09 当日香葱单品档案缺失"))

# —— 王旗营：11-09 三种读数并列（不平均、不混用、不改写历史序列）
A(Q(DATA_DATE, "小葱", "小葱（农业农村部 roundup 口径）", "昆明景臻王旗营蔬菜批发市场", "云南", "销地批发价",
    3.50, 3.50, 3.50, "农业农村部信息中心·全国主要批发市场小葱价格行情（11-09，50 家）", ROUND50_URL,
    "★本期新采实测。农业农村部 50 家 roundup 中王旗营小葱 3.50，较 11-08 同口径 3.80 下跌 0.30 / -7.9%，为 42 家配对市场中最大跌幅之一；销地续弱"))
A(Q(DATA_DATE, "小葱", "小葱（景臻平均价统计表转载）", "昆明景臻王旗营蔬菜批发市场", "云南", "销地批发价",
    4.00, 4.00, 4.00, "景臻·王旗营蔬菜批发平均价格统计（11-09 公众号转载表）", QSH_A_URL,
    "⚠️ 待复核：转载表小葱 4.00 / 前一日成交量 30 吨，与并行任务第015期核出的 11-07 读数完全一致，疑为 T-1/T-2 转载而非 11-09 新值；同表大葱 4.50/50吨、香菜 4.00/7吨。登记为第三口径，不并入序列"))
A(Q(DATA_DATE, "小葱", "小葱（沿用平均价统计序列）", "昆明景臻王旗营蔬菜批发市场", "云南", "销地批发价",
    2.30, 2.30, 2.30, "景臻·王旗营蔬菜批发平均价格统计（序列沿用值）", "",
    "⚠️ 沿用值而非本期新成交价。本仓历史序列 11-07 起沿用 2.30；与农业农村部 3.50、转载表 4.00 三者并存，严禁平均或直接计算日涨跌"))
A(Q(DATA_DATE, "大葱", "大葱", "昆明景臻王旗营蔬菜批发市场", "云南", "销地批发价",
    4.50, 4.50, 4.50, "景臻·王旗营平均价格统计表（11-09 公众号转载）", QSH_A_URL,
    "★替代品，用于校验转载表口径：与农业农村部 11-09 大葱 roundup 中王旗营 4.00 相差 0.50"))
A(Q(DATA_DATE, "香菜", "香菜", "昆明景臻王旗营蔬菜批发市场", "云南", "销地批发价",
    4.00, 4.00, 4.00, "景臻·王旗营平均价格统计表（11-09 公众号转载）", QSH_A_URL,
    "★相邻品类参照：11-09 云南产地综合香菜 4.0-5.0，转载表 4.00 与之量级一致"))

# —— 全国 50 家批发市场小葱 roundup（11-09，农业农村部信息中心，全量入库）
SALES_1109 = [
    ("北京新发地农副产品批发市场信息中心", "北京", 3.60),
    ("北京朝阳区大洋路综合市场", "北京", 8.20),
    ("河北省怀来县京西果菜批发市场有限责任公司", "河北", 6.00),
    ("邯郸市经开区南大堡蔬菜批发市场", "河北", 2.40),
    ("山西省晋城市绿欣农产品贸易有限公司", "山西", 4.70),
    ("晋城市绿盛农工商实业有限公司农副产品批发市场", "山西", 2.40),
    ("内蒙古呼和浩特市东瓦窑农副产品批发市场有限责任公司", "内蒙古", 7.80),
    ("内蒙古呼和浩特保全庄农副产品批发市场", "内蒙古", 19.50),
    ("辽宁鞍山宁远农产品批发市场", "辽宁", 2.50),
    ("辽宁朝阳市果菜批发市场", "辽宁", 1.60),
    ("江苏凌家塘市场发展有限公司", "江苏", 6.50),
    ("江苏苏州南环桥农副产品批发市场", "江苏", 3.50),
    ("江苏无锡朝阳农产品大市场", "江苏", 4.51),
    ("义乌市市场发展集团有限公司农批管理分公司", "浙江", 4.60),
    ("浙江嘉兴蔬菜批发交易市场", "浙江", 4.79),
    ("绍兴市蔬菜果品批发交易市场有限公司", "浙江", 4.00),
    ("杭州农副产品物流中心南庄兜农产品批发市场", "浙江", 6.00),
    ("天长市永福农副产品批发市场", "安徽", 5.75),
    ("安徽合肥周谷堆农产品批发市场", "安徽", 6.70),
    ("安徽六安市裕安区紫竹林农产品批发市场", "安徽", 6.00),
    ("马鞍山市安民农副产品贸易有限公司", "安徽", 8.50),
    ("福建省福鼎市商贸业服务中心", "福建", 7.50),
    ("江西乐平蔬菜农产品批发大市场", "江西", 4.40),
    ("江西九江琵琶湖农产品物流有限公司", "江西", 7.20),
    ("山东章丘刁镇蔬菜批发市场", "山东", 2.40),
    ("河南濮阳宏进农副产品批发市场有限公司", "河南", 3.40),
    ("河南万邦国际农产品物流股份有限公司", "河南", 4.40),
    ("湖北鄂州市蟠龙农产品批发市场", "湖北", 10.00),
    ("潜江市四季友农产品市场有限公司", "湖北", 8.00),
    ("湖北省洪湖农贸市场", "湖北", 8.80),
    ("武汉白沙洲农副产品大市场有限公司", "湖北", 6.00),
    ("两湖绿谷物流股份有限公司", "湖北", 5.60),
    ("广东汕头农副产品批发中心市场", "广东", 4.70),
    ("海口市菜篮子江楠农产品批发市场有限公司", "海南", 6.46),
    ("南充川北农产品交易有限公司", "四川", 4.40),
    ("贵阳农产品物流园", "贵州", 6.20),
    ("昆明景臻王旗营蔬菜批发市场", "云南", 3.50),
    ("西藏领峰农副产品经营管理有限公司", "西藏", 11.00),
    ("陕西咸阳新阳光农副产品有限公司", "陕西", 6.60),
    ("庆阳市西峰西郊瓜果蔬菜批发有限责任公司", "甘肃", 5.00),
    ("武威昊天农产品交易市场暨仓储物流中心", "甘肃", 4.70),
    ("金昌市金川天然农产品发展有限责任公司", "甘肃", 7.50),
    ("甘肃省定西市安定马铃薯综合交易中心", "甘肃", 10.50),
    ("甘肃酒泉春光农产品市场有限责任公司", "甘肃", 8.00),
    ("兰州国际高原夏菜副食品采购中心", "甘肃", 5.19),
    ("宁夏海吉星国际农产品物流有限公司", "宁夏", 4.00),
    ("新疆兵团农二师库尔勒市孔雀农副产品综合批发市场", "新疆", 7.25),
    ("新疆通汇市场有限公司", "新疆", 6.00),
    ("新疆兵团第五师三和农副产品综合批发市场", "新疆", 8.00),
    ("新疆克拉玛依农副产品批发市场", "新疆", 5.00),
]
for _m, _p, _v in SALES_1109:
    _note = ("全国 50 家销地批发市场横截面全量入库；单值报价，low/high/mid 同值。与产地香葱不同口径，不可直接横比")
    if _v == 19.50:
        _note = ("⚠️ 极端离群值：呼和浩特保全庄 19.50 元/公斤，为次高值（西藏领峰 11.00）的 1.77 倍，"
                 "疑为精品/有机规格或录入异常。按 IQR 法判为越界点，保留但不删除，均值统计另给剔除口径")
    elif _v == 3.50:
        _note = ("★王旗营条目，较 11-08 同口径 3.80 下跌 7.9%；同时为 42 家配对市场中最大跌幅之一")
    A(Q(DATA_DATE, "小葱", "小葱（全国 roundup 大宗价）", _m, _p, "销地批发价",
        _v, _v, _v, "农业农村部信息中心·全国主要批发市场小葱价格行情（11-09）", ROUND50_URL, _note))

# —— 全国大葱 roundup 云南相关样本（替代品，单列）
A(Q(DATA_DATE, "大葱", "大葱", "云南昆明呈贡龙城农产品经营股份有限公司", "云南", "销地批发价",
    3.75, 3.75, 3.75, "农业农村部信息中心·全国大葱价格行情（11-09）", DCONG_URL,
    "★替代品。呈贡龙城大葱 3.75；同市场单表亦为 3.75、香菜 6.00"))
A(Q(DATA_DATE, "大葱", "大葱", "昆明景臻王旗营蔬菜批发市场", "云南", "销地批发价",
    4.00, 4.00, 4.00, "农业农村部信息中心·全国大葱价格行情（11-09）", DCONG_URL,
    "★替代品。农业农村部口径王旗营大葱 4.00，与景臻转载表 4.50 并列参照"))
A(Q(DATA_DATE, "大葱", "大葱", "师宗县鼎禾物业服务有限公司", "云南", "销地批发价",
    5.00, 5.00, 5.00, "农业农村部信息中心·全国大葱价格行情（11-09）", DCONG_URL,
    "★替代品。曲靖师宗大葱 5.00"))
A(Q(DATA_DATE, "大葱", "大葱", "西藏领峰农副产品经营管理有限公司", "西藏", "销地批发价",
    8.00, 8.00, 8.00, "农业农村部信息中心·全国大葱价格行情（11-09）", DCONG_URL,
    "★替代品高位。西藏领峰大葱 8.00"))
A(Q(DATA_DATE, "大葱", "大葱", "龙门实业(集团)有限公司西三街农副水产品市场", "重庆", "销地批发价",
    9.00, 9.00, 9.00, "农业农村部信息中心·全国大葱价格行情（11-09）", DCONG_URL,
    "★替代品全国最高档。重庆龙门实业 9.00"))
A(Q(DATA_DATE, "小葱", "小葱", "辽宁朝阳市果菜批发市场（单市场表）", "辽宁", "销地批发价",
    1.60, 1.60, 1.60, "农业农村部信息中心·朝阳果菜单市场价格行情（11-09）",
    "https://futures.stockstar.com/IG2026110900006984.shtml",
    "全国最低档小葱 1.60，与 50 家 roundup 中该市场条目互证；同表「葱」大类亦 1.60"))
A(Q(DATA_DATE, "香菜", "香菜", "云南昆明呈贡龙城农产品经营股份有限公司", "云南", "销地批发价",
    6.00, 6.00, 6.00, "农业农村部信息中心·呈贡龙城单市场价格行情（11-09）", LONGCHENG_URL,
    "★相邻品类参照，用于校验云南转载表口径"))

# —— 平台挂牌（11-09 检索快照，非成交价）
PLATFORM = [
    ("泸西小香葱（红/黑/白/白铁杆整车挂牌）", "云南红河州泸西县", "云南", 1.84, "一亩田（11-09 检索）", "https://m.ymt.com/supply/63950370", "原始 0.92 元/斤 ×2 折算；10 万斤起批，挂牌非成交"),
    ("小香葱通货（挂牌）", "云南红河州泸西县", "云南", 5.00, "一亩田（11-09 检索）", "https://m.ymt.com/supply/62574443", "原始 5.00 元/公斤直报；1 公斤起批，挂牌非成交"),
    ("云南泸西小乡葱（代办 10 吨起批）", "云南红河州泸西县", "云南", 9.80, "惠农网（11-09 检索）", "https://www.cnhnb.com/gongying/8460077/", "原始 9800 元/吨 ÷1000 折算；含代收代办服务费，不可用于定价"),
    ("小红葱（整车挂牌）", "云南红河州泸西县", "云南", 2.40, "一亩田（11-09 检索）", "https://www.ymt.com/supply/59212963", "原始 1.20 元/斤 ×2 折算；1 万斤起批，挂牌非成交"),
    ("泸西小香葱（整车挂牌）", "云南红河州泸西县", "云南", 2.10, "一亩田（11-09 检索）", YMT_URL, "原始 2.10 元/公斤直报；挂牌非成交"),
    ("泸西小葱（挂牌低价档）", "云南红河州泸西县", "云南", 1.00, "一亩田（11-09 检索）", YMT_URL, "原始 1.00 元/公斤直报；挂牌非成交，长期不刷新"),
    ("大理铁杆小香葱（挂牌）", "云南大理市", "云南", 4.00, "一亩田（11-09 检索）", YMT_URL, "原始 2.00 元/斤 ×2 折算；挂牌非成交"),
    ("白铁杆小香葱葱头（挂牌）", "云南禄劝县", "云南", 4.00, "一亩田（11-09 检索）", YMT_URL, "原始 4.00 元/公斤直报；葱头/种苗口径，非商品葱"),
]
for _v, _m, _p, _v2, _src, _url, _note in PLATFORM:
    A(Q(DATA_DATE, "香葱", _v, _m, _p, "产地收购价",
        _v2, _v2, _v2, _src, _url, _note))

# —— 泸西产地→销地实时成交存档（农业农村部重点农产品市场信息平台，11-03 抓取）
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
QUOTES = [q for q in QUOTES if q["mid"] is not None]
QUOTES.sort(key=lambda q: (q["date"], q["province"], -(q["mid"] or 0)))

# —— 本期统计量（全部可复算）
_sales_mids = [v[2] for v in SALES_1109]
NATIONAL_MEAN = round(sum(_sales_mids) / len(_sales_mids), 2)
SALES_N = len(_sales_mids)
N43 = SALES_N
MEAN43 = NATIONAL_MEAN
MED50 = round(sorted(_sales_mids)[24] / 2 + sorted(_sales_mids)[25] / 2, 2)
MIN50 = min(_sales_mids)
MAX50 = max(_sales_mids)
EXCL50 = round(sum(v for v in _sales_mids if v != 19.50) / (len(_sales_mids) - 1), 2)
PREV_N, PREV_MEAN = 43, 5.51
NAIVE_CHG = round((NATIONAL_MEAN / PREV_MEAN - 1) * 100, 1)
# 同市场配对口径（11-08 43 家 ∩ 11-09 50 家 = 42 家）
MATCH_N, MATCH_PREV, MATCH_NOW, MATCH_CHG = 42, 5.61, 5.66, 1.02
S_UP, S_DOWN, S_FLAT = 9, 7, 26
QS_A, QS_B = 3.30, 3.45
WQ_NEW, WQ_PREV, WQ_JZ = 3.50, 3.80, 4.00
WQ_CHG = round((WQ_NEW / WQ_PREV - 1) * 100, 1)
BLK_CHG_TXT = "0.00"
BLK_CHG_PCT_TXT = "0.0"
SPREAD = round(RED_MID - BLK_MID, 2)
YN_WARN = dict(DZ.get("province_stats", []) or []).get("云南", 0)
DGE = dict(DZ.get("hazard_stats", []) or []).get("地质灾害", 0)
_hz = dict(DZ.get("hazard_stats", []) or [])
DCOLD = sum(_hz.get(k, 0) for k in ("道路结冰", "道路冰雪", "寒潮", "霜冻", "低温凝冻", "强降温", "暴雪"))
PROV_COUNT = len({q["province"] for q in QUOTES if q["province"]})

SUMMARY = (
    "泸西产地红香葱 11-09 报 <b>3.2-3.5</b>（官方均价标签仍 3.45），区间较 11-08 下移 0.1、"
    "官方措辞「红香葱微掉」但均价标签未同步，<b>自 11-01 起连续九个报价日锁定 3.45</b>；"
    "黑香葱 2.5-2.9 / <b>2.76 持平</b>（11-08 破位后暂稳），红黑价差维持 {spread}；"
    "通海红葱同步下调至 3.1-3.5。"
    "<b>上期首要数据缺口本期补齐</b>：11-09 全省综合两个转载源并列 红 3.1-3.5（中值 3.30）/ 3.3-3.6（3.45），"
    "<b>黑葱两源完全一致 2.5-2.9</b> → 上期「黑葱下调是否传导至省级口径」得到肯定答案；"
    "取源A 则红葱全省 3.30 <b>低于泸西 3.45 形成倒挂 -0.15</b>（源B 则持平），该结论源依赖、已限定。"
    "王旗营 11-09 <b>三读数并列</b>：农业农村部 50 家 roundup <b>3.50</b>（较 11-08 的 3.80 <b>{wqchg:+.1f}%</b>）、"
    "景臻转载表 4.00/30吨（疑 T-1）、本仓沿用序列 2.30，三者不平均不混用。"
    "<b>本期最重要分析结论：全国销地「大涨」是样本构成假象。</b>11-09 取得 <b>{n} 家</b>市场全量，"
    "表观均值 <b>{mean50:.2f}</b> 元/公斤（上期 43 家 5.51，看似 <b>{naive:+.1f}%</b>），"
    "但 50 家中新增 7 家多为高价市场且含 19.50 元极端离群值（剔除后 {excl:.2f}）；"
    "<b>同市场配对 42 家 5.61 → 5.66 仅 {mchg:+.2f}%</b>（26 平 / 9 涨 / 7 跌），"
    "销地实为<b>基本持平、局部走弱</b>，严禁把样本扩容误读为需求回暖。"
    "本期首次取得 <b>2025-11-09 与 2024-11-09 隔年/两年前精确同日全套档案</b>：泸西红 6.25 / 7.05、黑 4.16 / 6.06、"
    "王旗营小葱 6.50（45 吨、综合均价 6.37、总吨位 3264）；本期红 <b>{yoyred:+.1f}%</b>、黑 <b>{yoyblk:+.1f}%</b>，"
    "红香葱为近五年同期绝对最低且唯一跌破 4 元。"
    "气象端鲜抓：未来 3 天泸西降水 {w3p} mm、最高温均 {w3t}℃、距平 <b>{ano:+.1f}℃</b>（上期 -12.1℃，降温收窄）；"
    "<b>今日 11-10 最低 {ctmin}℃ 为本轮最冷点</b>，11-11 起快速回暖至 21℃ 区间，"
    "15 天累计仅 <b>{rtot} mm</b>、第 8-15 天 {whp} mm / {whr} 雨日 → 低温与降水均为短脉冲，中期供给恢复概率高。"
    "灾害端：全网 <b>{dtot}</b> 条，<b>低温冰冻类 {dcold} 条主导</b>（道路结冰 25 / 寒潮 8 / 暴雪 1 / 霜冻 1），"
    "云南 <b>{yn} 条</b>跃居绝对首位（上期 24），但 10 条主产区相关全在滇西（临沧/德宏/大理），{rrcount}，"
    "核心产区与外运主通道无直接冲击。"
    "<b>模型修复</b>：本期为节日脉冲增加节后 21 天线性衰减尾，消除上一版 3 个月档日历悬崖；"
    "六档中枢（精品净葱 / 集散价口径）：{path} 元/公斤，第 6 档小幅回落系节后需求渐退的正常路径。"
).format(spread=SPREAD, wqchg=WQ_CHG, n=NATIONAL_MEAN and SALES_N, mean50=NATIONAL_MEAN,
         naive=NAIVE_CHG, excl=EXCL50, mchg=MATCH_CHG,
         yoyred=YOY_RED, yoyblk=YOY_BLK,
         w3p=w3.get("precip_total"), w3t=w3.get("tmax_avg"),
         ano=(w3.get("tmax_avg") or 0) - (clim.get("tmax_mean") or 0),
         rtot=RAIN_TOTAL, whp=wh.get("precip_total"), whr=wh.get("rainy_days"),
         ctmin=COLD_TMIN, dtot=DZ.get("total", 0), dcold=DCOLD, yn=YN_WARN,
         rrcount=RR_DESC, path=" → ".join(str(f["center"]) for f in FORECASTS))

# JSON 的 summary 供 03:00 日报第九章汇总，report.esc() 会做 html.escape，
# 因此必须是无标签纯文本且遵循 schema 的「1-3 句」；HTML 报告仍使用上面的富文本 SUMMARY。
SUMMARY_JSON = (
    "11-09 泸西红香葱报 3.2-3.5 元/公斤（官方均价标签仍 3.45、连续九个报价日未同步），黑香葱 2.76 持平；"
    "全省综合黑葱两源一致，确认产地下调已传导至省级口径，红葱取源A 3.30 与泸西形成 -0.15 倒挂（源B 持平，结论源依赖）。"
    "本期最关键结论是全国销地表观均值由 43 家 5.51 升至 50 家 6.03（看似 +9.4%）实为样本扩容与 19.50 元极端离群值造成的假象，"
    "同市场配对 42 家仅由 5.61 升至 5.66（+1.02%，26 平 / 9 涨 / 7 跌），销地实为基本持平、局部走弱。"
    "未来 3 天低温与降水均为短脉冲、红河州及泸西无灾害预警，六档预测中枢 3.77 / 3.82 / 3.88 / 3.96 / 4.08 / 3.97 元/公斤，"
    "本期已修复春节后节日脉冲的日历悬崖。"
)

DOC = {
    "task": "香葱行情",
    "task_id": "376dffed-c5e4-4904-a77a-29193947212a",
    "date": TODAY,
    "generated_at": GEN,
    "market_scope": "全国 / 云南 / 红河州泸西县（本期覆盖 {0} 省区）".format(PROV_COUNT),
    "quotes": QUOTES,
    "forecasts": FORECASTS,
    "summary": SUMMARY_JSON,
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
           ("11-05", 3.45, 3.45), ("11-06", 3.45, 3.45), ("11-07", 3.45, 3.45),
           ("11-09*", 3.45, 3.30)]
    ml, mr, mt, mb = 60, 120, 36, 44
    hi, lo = 5.0, 3.0
    hh = 200
    xmap = lambda i: ml + i * (W - ml - mr) / (len(pts) - 1)
    ymap = lambda v: mt + (hi - v) * (hh - mt - mb) / (hi - lo)
    g = ['<svg viewBox="0 0 {0} {1}" class="cv">'.format(W, hh + 60)]
    g.append('<rect width="{0}" height="{1}" fill="#fbfcfe"/>'.format(W, hh + 60))
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
    g.append('<text x="{0}" y="{1}" font-size="10.5" fill="#dc2626">* 11-08 全省综合数值表缺失（不插补）；11-09 为源A 3.30，另一转载源 3.45 并列，连线跨缺口</text>'.format(ml + 6, hh + 50))
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
    g = ['<svg viewBox="0 0 {0} {1}" class="cv">'.format(W, hh + 60)]
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
    g.append('<text x="{0}" y="{1}" font-size="10.5" fill="#dc2626">11-09 三口径并列：农业农村部 3.50 / 景臻转载表 4.00（疑 T-1） / 沿用序列 2.30，均未并入本序列</text>'.format(ml + 6, hh + 52))
    g.append("</svg>")
    return "".join(g)


def chart_yoy():
    """近五年同期（2024/2025/2026 均为 11-09 精确同日；2022/2023 为近似日或跨口径）泸西红香葱均价对比。"""
    pts = [("2022-11-06*", 4.95), ("2023-11-08*", 4.25), ("2024-11-09", 7.05),
           ("2025-11-09", 6.25), ("2026-11-09", 3.45)]
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
           ("云南全省综合交易价 红香葱(11-09 源A)", 3.30),
           ("云南全省综合交易价 红香葱(11-09 源B)", 3.45),
           ("惠农网·地头价挂牌(1.70元/斤)", 3.40),
           ("惠农网·红葱通货35-50cm", 3.00),
           ("泸西·集散均价 黑香葱(11-09 持平)", 2.76),
           ("云南全省综合交易价 黑香葱(11-09)", 2.70),
           ("一亩田·泸西平台行情 小葱(1.32元/斤)", 2.64),
           ("昆明王旗营·小葱销地(11-09沿用口径)", 2.30),
           ("昆明王旗营·小葱(农业农村部11-09口径)", 3.50),
           ("昆明王旗营·小葱(景臻转载表11-09)", 4.00),
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
    _gpct = _gap / _centers[-2] * 100
    if _gpct <= -5:
        MONO_DESC = ("六档<b>前五档单调递增，第 6 档（3 个月）明显回落</b>"
                     "（{0:+.2f} 元 / {1:+.1f}%）——系春节备货脉冲窗口在节日当日截止所致的"
                     "<b>模型边界效应</b>，非市场趋势反转，详见 6.2 提示").format(_gap, _gpct)
    else:
        MONO_DESC = ("六档<b>前五档单调递增</b>，第 6 档（3 个月）与第 5 档（2 个月）<b>基本持平</b>"
                     "（{0:+.2f} 元 / {1:+.1f}%）".format(_gap, _gpct))

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
  <div class="kpi"><div class="l">泸西模型基准（红香葱）</div><div class="v" style="color:#2563eb">{br:.2f}</div><div class="d">元/公斤 · 滇中产区集散价 · {ddate} 实测 · <b>持平（连续 9 日）</b></div></div>
  <div class="kpi"><div class="l">泸西红香葱区间</div><div class="v" style="color:#dc2626">3.2~3.5</div><div class="d">较 11-08 的 3.3~3.6 <b>下移 0.1</b> · 均价标签滞后</div></div>
  <div class="kpi"><div class="l">泸西黑香葱</div><div class="v" style="color:#16a34a">{bb:.2f}</div><div class="d">元/公斤 · {ddate} 实测 · <b>持平（连续 2 日）</b></div></div>
  <div class="kpi"><div class="l">全省综合（红 / 黑）</div><div class="v">{qs_a:.2f}</div><div class="d">元/公斤 · 源A 中值 · 黑葱 2.70 · <b>倒挂 -0.15*</b></div></div>
  <div class="kpi"><div class="l">昆明王旗营小葱</div><div class="v">{wqnew:.2f}*</div><div class="d">元/公斤 · 农业农村部口径 · <b>{wqchg:+.1f}%</b> 较 11-08</div></div>
  <div class="kpi"><div class="l">全国销地：配对口径</div><div class="v" style="color:#16a34a">{matchchg:+.2f}%</div><div class="d">42 家同市场 · 5.61 → 5.66 · <b>表观 +9.4% 为假象</b></div></div>
</div>

<div class="note"><b>本期核心结论：</b>{summ}</div>

<h2>一、历史长周期回顾（近 10 年）</h2>
<div class="card">{c_decade}</div>
<table><thead><tr><th>窗口</th><th>期初</th><th>期末</th><th>涨跌</th><th>均值</th><th>最低</th><th>最高</th></tr></thead>
<tbody>{wrows}</tbody></table>
<div class="note">口径：主序列为<b>通货毛葱</b>（元/公斤），精品净葱 = 主序列 × 1.66。
10 年 CAGR <b>{cagr:.1f}%</b>，长周期中枢下移。<b>不可与第六章预测口径横向比较</b>：预测与「当前中枢」为精品净葱 / 集散价。
本期补入 2024-11-09（泸西分区 + 全省综合）、2025-11-09（泸西/通海/全省/王旗营全套）两个精确同日锚点；
但 2022 年及更早官方价格表普遍未列「小葱/香葱/红葱/黑葱」单品，<b>10 年窗口对香葱单品仍不完整</b>，
长周期最高/最低/均值仅为模型重建序列，不得当作实测统计引用。</div>
<h3>近 36 个月</h3><div class="card">{c_36}</div>
<h3>季节指数（1.00 = 年度均值）</h3><div class="card">{c_season}</div>
<div class="note">季节规律：春峰 4-5 月（1.25 / 1.16）→ 夏谷 7-8 月（0.68 / 0.72）→ 冬旺 11-1 月（1.09-1.14）。
11 月因子 1.121、12 月 1.140，<b>季节性本身对四季度构成上行动力</b>；但 2026 年 11 月初已是近五年同期绝对最低（见 5.1），
且本期第 8-15 天转干暖，<b>季节性上行未必能抵消同比低基数与结构性供给充裕</b>。</div>

<h2>二、天气与灾害（{today} 鲜抓）</h2>
<div class="card">{c_wx}</div>
<table><thead><tr><th>窗口</th><th>最高温均</th><th>最低温均</th><th>累计降水</th><th>雨日</th><th>大风日</th><th>主导天气</th></tr></thead><tbody>
<tr><td>未来 3 天</td><td>{w3t}</td><td>{w3t2}</td><td>{w3p} mm</td><td>{w3r}</td><td>{w3g}</td><td>{w3d}</td></tr>
<tr><td>未来 1 周</td><td>{w7t}</td><td>{w7t2}</td><td>{w7p} mm</td><td>{w7r}</td><td>{w7g}</td><td>{w7d}</td></tr>
<tr><td>第 8-15 天</td><td>{wht}</td><td>{wht2}</td><td>{whp} mm</td><td>{whr}</td><td>{whg}</td><td>{whd}</td></tr>
</tbody></table>
<div class="warn"><b>本期气象结论：本轮降温今日见底，随后快速回暖转干，供给收缩窗口比上期更短。</b>
未来 3 天泸西累计降水 {w3p} mm、最高气温均 {w3t}℃、最低温均 {w3t2}℃、
较近 30 日均值距平 <b>{ano:+.1f}℃</b>（上期 -12.1℃，<b>降温幅度收窄</b>）。
<b>{cdate}（今日）最低 {ctmin}℃ 为本轮监测最冷点</b>，单日最高仅 10.6℃；
11-11 起最高温回升至 16.5℃ → 11-16 达 21.4℃，<b>低温是单日脉冲而非持续过程</b>。
降水同样高度集中在近端：15 天累计仅 <b>{rtot} mm</b>（上期 17.6 mm，基本持平），
其中前 7 天贡献 {w7p} mm，<b>第 8-15 天仅 {whp} mm、{whr} 个雨日</b>，主导天气转为「阴」与大风（{whg} 天）。
降水峰值 <b>{pdate}（{pmm} mm）</b>，当日最高 {ptmax}℃ / 最低 {ptmin}℃；主要较强降水日：{hdesc}。
<b>判断：</b>霜冻 / 采收受阻 / 洗葱损耗 / 霜霉灰霉病风险集中在未来 1-3 天，
第 2 周起光照与温度同步恢复，<b>供给恢复速度可能快于预期，洪涝型断供概率进一步下降</b>；
上行情景不宜线性外推，低温能否兑现为实际减产仍需未来 1-2 周田间反馈验证。</div>
<div class="warn"><b>全国层面（中央气象台 {today} 生效预警）：</b>全网生效预警 <b>{dtot}</b> 条，
其中<b>道路结冰 {dice} 条、大风 {dwind} 条、大雾 {dfog} 条、暴雨 {drain} 条、寒潮 8 条、地质灾害 {dge} 条</b>。
灾种结构：{hazard_desc}。涉及香葱主产区 <b>{dprod}</b> 条（{prod_desc}）。{dprod_note}</div>
<div class="warn"><b>本期最大灾害结构变化：由「暴雨主导」切换为「低温冰冻主导」，且低温预警首次触及云南次级产区。</b>
全网 <b>{dcold} 条低温类预警</b>（道路结冰 25 + 寒潮 8 + 道路冰雪 2 + 暴雪 1 + 霜冻 1 + 低温凝冻 1 + 强降温 1），
与产区断崖降温同步；<b>云南以 {yn} 条跃居绝对首位</b>（上期 24 条，近翻倍；贵州 11、四川 10、福建 10 次之）。
10 条主产区相关预警集中在<b>滇西滇西南</b>：临沧耿马/镇康/凤庆/永德/沧源暴雨、德宏芒市/陇川暴雨，
<b>大理剑川/弥渡首次出现道路结冰黄色</b>（弥渡属本报告第四章所列云南次级香葱产区），
另四川凉山会东县暴雪橙色 —— 低温冻害向西南高海拔扩散，是本期新增的方向性风险。
但<b>{rrcount}</b>，泸西所在的滇东南红河州本轮完全不在雨带/冰冻带内，<b>对核心产区与外运主通道无直接冲击</b>；
不宜据全省预警条数外推泸西减产。</div>
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
<div class="note">本期红葱区间下移而黑葱持平，再次印证分类口径不可混用：泸西红香葱 3.2-3.5 / 标签均价 3.45、黑香葱 2.5-2.9 / 2.76，价差 {spread:.2f} 元/公斤。
若把两者合并为「香葱均价」会掩盖本期最重要的结构性信号；白葱（钢葱/白铁杆）与大葱另有独立报价体系，仅作对比。</div>

<h2>四、全国香葱种植省份</h2>
<table><thead><tr><th>省/区域</th><th>主产县市</th><th>产业地位</th></tr></thead><tbody>{provs}</tbody></table>
<div class="note">口径提示：全国小香葱种植面积第三方统计分歧较大（有 78.56 万亩与主产区加总两种量级），
本报告以<b>主产区加总</b>口径呈现，仅用于判断区域供给权重，不建议作为绝对面积引用。
<b>本期补充：</b>云南 {yn} 条预警虽多，但成片暴雨在临沧、德宏等滇西，<b>首次出现的道路结冰预警落在大理剑川/弥渡</b>
（弥渡属上表云南次级产区带），低温冻害对高海拔次级产区有边际影响；
<b>泸西、通海、师宗、晋宁等滇中滇东核心主产带本轮仍无独立生效预警</b>；四季度供给继续向云南、广西、广东等南方产区集中。</div>

<h2>五、全国行情横截面（{ddate}）</h2>
<div class="card">{c_cross}</div>
<div class="good"><b>本期取得农业农村部信息中心「全国主要批发市场小葱价格行情」50 家全量 roundup</b>（上期 43 家），
覆盖 20 个以上省区，均值 <b>{mean50:.2f}</b> 元/公斤、中位数 {med50:.2f}，
区间 <b>{min50:.2f}</b>（辽宁朝阳）~ <b>{max50:.2f}</b>（呼和浩特保全庄，极端离群值）。
该表为「小葱」销地大宗价口径，与泸西产地香葱集散价（{br:.2f}）存在约 1.7 倍产销价差，不可直接横比；
本期另单列大葱替代品与平台挂牌报价，均未并入该均值。</div>
<h3>5.1 五年同期对比：本期集齐 2024 / 2025 / 2026 三个精确同日 11-09</h3>
<div class="card">{c_yoy}</div>
<div class="warn"><b>同比腰斩（隔年精确同日 2025-11-09，本期首次取得全套）：</b>
泸西分区红香葱 <b>6.25</b>（6.0-6.4）、黑香葱 <b>4.16</b>（4.1-4.6），通海红葱 6.0-6.4、黑葱 4.1-4.6，
全省综合红 6.0-6.4 / 黑 4.1-4.6（与分区同价，说明 2025 年不见本期分化）；
王旗营小葱 <b>6.50</b>、成交量 45 吨，市场综合平均价 6.37、总吨位 3264；农业农村部单市场表小葱 6.50 互证。
本期泸西 3.45 / 2.76、王旗营沿用序列 2.30，红香葱同比 <b>{yoyred:.1f}%</b>、黑香葱 <b>{yoyblk:.1f}%</b>、王旗营 <b>{yoywq:+.1f}%</b>（改用农业农村部同口径 3.50 则为 -46.2%）。
<b>两年前精确同日 2024-11-09</b>（本期首次取得）：泸西红 7.05 / 黑 6.06、通海红 6.5-7.0 / 黑 6.0-6.3，
全省综合红 6.5-7.6 / 黑 5.6-6.3；本期红较之 -51.1%、黑 -54.5%。当日措辞「黑香葱下滑」与黑葱自 11-08 档案 6.36 降至 6.06 一致。
<b>红香葱为近五年同期绝对最低，且是唯一跌破 4 元的一年</b>；
但需注意 2024/2025 同期均属近年高位，同比跌幅部分来自高基数，不宜简单等同于本年度供给恶化的全部幅度。</div>
<h3>5.2 全省综合价与泸西分区价：上期首要缺口已补齐，但出现两源分歧</h3>
<div class="card">{c_div}</div>
<div class="warn"><b>上期首要行动项已闭环，结论分两层：</b>
① <b>黑葱传导得到肯定答案</b> —— 11-09 全省综合两个转载源<b>一致</b>报 2.5-2.9（中值 2.70），
与泸西 / 通海分区 2.5-2.9 完全对齐，上期「泸西黑葱破位是否已传导至省级口径」的疑问解除；
② <b>红葱出现 0.15 元两源分歧</b> —— 源A（云南本地公众号）3.1-3.5（中值 3.30）、
源B（宁夏四季鲜 / 北方蔬菜报转载）3.3-3.6（中值 3.45）。
源A 同表香菜 4.0-5.0、茴香 3.0-3.5、韭黄 8.0-8.5 与 11-09 分区表一致，判为本期现值；
源B 整体偏低一档，<b>疑为 T-1 转载</b>。按口径铁律<b>两源并列登记、不平均、不混用</b>。
取源A 则全省 3.30 <b>低于泸西 3.45，倒挂 -0.15 再现</b>，延续「全省综合价对泸西分区价约 1 个报价日领先性」的判断；
取源B 则完全持平、倒挂不成立。<b>因此「倒挂」结论是源依赖的，须限定为源A 口径</b>，不可写成无条件事实。
11-08 全省综合数值表本期仍未取得，按「缺失值只标注不插补」不虚构；收敛图 11-07 → 11-09 连线跨此缺口并已在图中标注。</div>
<div class="note"><b>与泸西区间下移的交叉印证：</b>本期泸西红香葱报价区间由 3.3-3.6 下移至 3.2-3.5（中值 3.35），
官方措辞「红香葱微掉」，但「均价」标签仍标 3.45 未同步 —— 属典型的<b>报价黏性 / 标签滞后</b>。
三个独立观测（泸西区间 3.35、通海红葱 3.30、全省综合源A 3.30）均指向真实成交重心已落到 <b>3.30~3.35</b>，
模型基准沿用的标签值 3.45 存在 <b>0.10~0.15 元偏高风险</b>。本报告按「不改写历史序列」原则保留 3.45，
但已在落盘 JSON 中把区间中值 3.35 作为推算行独立登记，并上调 C 情景概率；下一期若均价标签跟随下移即确认补跌。</div>
<h3>5.3 本期最大分析结论：全国销地「大涨 9.4%」是样本构成假象</h3>
<div class="warn"><b>⚠️ 口径陷阱（数据工程红线：分母漂移 / 组样本数不等时算术平均≠加权）：</b>
11-08 取得 43 家 roundup 均值 <b>{prev_mean:.2f}</b>，11-09 取得 {sn} 家均值 <b>{mean50:.2f}</b>，
表面环比 <b>{naive:+.1f}%</b>，极易被误读为「销地需求回暖、价格大涨」。但两期<b>样本集合不同</b>：
本期新增 7 家市场（多为中高价），且新增的呼和浩特保全庄报 <b>19.50 元/公斤</b>，
为次高值（西藏领峰 11.00）的 1.77 倍，按 IQR 法属越界离群点；仅剔除该一条，均值即降至 <b>{excl:.2f}</b>。
<b>正确做法是同市场配对比较</b>：取两期共同出现的 <b>{matchn} 家</b>市场，
11-08 均值 {matchprev:.2f} → 11-09 均值 {matchnow:.2f}，环比仅 <b>{matchchg:+.2f}%</b>；
其中 <b>{sflat} 家持平、{sup} 家上涨、{sdn} 家下跌</b>。
<b>结论：全国销地实为基本持平、局部走弱，不存在普涨</b>。
最大跌幅包括王旗营 3.80 → 3.50（-7.9%）、苏州南环桥 3.90 → 3.50、无锡朝阳 4.84 → 4.51；
最大涨幅为克拉玛依 4.00 → 5.00、新疆通汇 5.00 → 6.00、武威昊天 3.70 → 4.70（西北局部补涨）。
本报告所有跨期全国均值比较均<b>以配对口径为准</b>，表观全样本均值仅登记、不用于趋势结论。</div>
<h3>5.4 王旗营三口径并列（不平均、不混用）</h3>
<div class="card">{c_wq}</div>
<div class="note">11-09 王旗营小葱存在<b>三种读数</b>：
① <b>农业农村部 50 家 roundup 口径 3.50</b>（同日同源、可复算，较 11-08 同口径 3.80 <b>{wqchg:+.1f}%</b>，为本期最可靠的销地走弱证据）；
② <b>景臻·王旗营平均价格统计表公众号转载 4.00 / 前一日成交量 30 吨</b>（与并行任务第015期核出的 11-07 争议读数完全一致，<b>疑 T-1/T-2 转载</b>，同表大葱 4.50/50吨、香菜 4.00/7吨）；
③ <b>本仓历史序列沿用值 2.30</b>（11-07 起沿用，非本期新成交价）。
三者相差最高达 1.70 元 / 74%，<b>严禁平均或直接计算日涨跌</b>。
本期起把 3.50 作为「农业农村部口径」独立入库，4.00 标注为待复核转载值，2.30 序列保留但不混用；
上期遗留的「4.00 是否为 11-07 景臻表真实读数」分歧仍<b>未武断改写历史序列</b>，继续列入复核清单，以原始表影像为准。</div>
<h3>5.5 泸西多源口径分歧</h3>
<div class="card">{c_spread}</div>
<div class="note"><b>口径分层（本期按 11-09 平台挂牌快照刷新）：</b>
①<b>成交价层</b>——泸西红香葱标签均价 3.45（模型基准）/ 区间中值推算 3.35、黑香葱 2.76、通海红 3.30 / 黑 2.70、
全省综合源A 3.30 / 源B 3.45、王旗营 3.50（农业农村部）/ 2.30（沿用）；
②<b>推算层</b>——地头统货大宗约 4.60（国资云农源自 10/29 断更，按历史加成率 1.33 推算，已标注为估算值）；
③<b>平台挂牌层</b>——一亩田 / 惠农网 1.00~5.00 元/公斤（整车 / 通货 / 精品，长期不刷新、非成交）；
④<b>服务 / 加工层</b>——惠农网代办 9800 元/吨（折 9.80，含服务费）、脱水香葱 40 元/公斤（不同商品形态）。
判断：<b>真实成交中枢落在 2.70（全省黑葱）～3.45（泸西红葱标签）之间，且重心偏向 3.30~3.35</b>；
跨平台横比必须同口径同规格，销地价不可倒推产地价。</div>
<h3>5.6 全量报价明细（{n} 条）</h3>
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
<div class="note">模型：<b>季节因子 × 天气冲击（衰减）× 均值回归动量 × 节日脉冲（三角形）</b>。
本期基准<b>维持 {br:.2f}</b>（泸西分区 {ddate} 官方均价标签，红黑均持平），
20 日实测均线 {ma:.2f}，均线高出基准 {gap:.1f}%，均值回归项为正向；
叠加 11-12 月季节因子上行与未来 3 天低温短脉冲带来的短期供给收缩，{mono}：{path}。
区间为情景区间，非统计置信区间。
<b>口径铁律：</b>本章预测为精品净葱 / 集散价，第一章长周期主序列为通货毛葱，二者相差约 1.66 倍，禁止横向混用。</div>
<div class="good"><b>模型改进（本期落地）：节日脉冲增加「节后衰减尾」，消除上一版日历悬崖。</b>
上一版 <code>festival_factor()</code> 对节后目标日直接返回 0，导致 3 个月档（目标日恰在春节后）
损失全部 +15% 节日加成，中枢从 2 个月档 4.09 骤降至 3.53，产生与正文自相矛盾的断崖。
本期改为<b>三角形脉冲</b>：节前按 <code>ramp_days</code> 线性爬升、节日当日取峰值、节后按 <code>tail_days</code> 线性衰减
（元旦 7 天 / 春节 21 天，配置于 <code>src/config.py</code>，实现于 <code>src/price.py</code>），
两侧在节日当日连续。修复后 3 个月档为 <b>{a3:.2f}</b> 元/公斤，较 2 个月档小幅回落属<b>节后需求渐退 + 2 月季节因子回落的正常路径</b>，
不再是模型边界效应；第八章情景中枢也不再系统性偏低。</div>

<h2>七、风险提示</h2>
<ul>
<li><b>模型基准偏高（本期首要风险）：</b>泸西红香葱区间已下移至 3.2-3.5（中值 3.35）、通海 3.1-3.5（3.30）、
全省综合源A 3.1-3.5（3.30），三个独立观测均低于模型基准标签值 3.45 约 0.10~0.15 元。
官方「均价」标签连续九个报价日锁在 3.45 属明显黏性；历史上该口径多次「长期不动、一次性跳变」
（10-26 前连续三日 3.85 → 10-31 一步至 3.45）。<b>红葱补跌压力随锁定时间累积，C 情景概率上调至 40%</b>。</li>
<li><b>全省综合两源分歧与 11-08 缺口：</b>红葱 3.1-3.5 与 3.3-3.6 相差 0.15，「倒挂 / 领先性」结论源依赖；
11-08 全省综合仍缺失（不插补）。下一期须以地慧数农原表与两转载源发布时间交叉核实。</li>
<li><b>销地续弱：</b>王旗营农业农村部口径 3.80 → 3.50（{wqchg:+.1f}%），苏州南环桥 3.90 → 3.50；
全国配对 42 家仅 {matchchg:+.2f}%，<b>需求端未出现实质回暖</b>，产地温和上行缺乏销地承接。</li>
<li><b>全国均值的样本构成陷阱：</b>表观 {naive:+.1f}% 与配对 {matchchg:+.2f}% 差异巨大；
任何引用「全国均价大涨」的判断都须先核对样本集合，否则构成虚假信号。</li>
<li><b>王旗营多口径不可混用：</b>3.50 / 4.00 / 2.30 三者并存，最高差 74%；
把三者平均或据其计算「单日暴涨/暴跌」都会产生虚假信号。</li>
<li><b>低温霜冻短脉冲：</b>{cdate} 最低 {ctmin}℃ 为本轮最冷点，未来 3 天最高温均 {w3t}℃、距平 <b>{ano:+.1f}℃</b>；
但 11-11 起快速回暖至 21℃ 区间，第 8-15 天仅 {whp} mm / {whr} 雨日。
低温抑制生长、抬升洗葱损耗与霜霉/灰霉病风险，但<b>是否兑现为减产尚未验证</b>，且窗口明显短于上期判断。</li>
<li><b>低温冰冻预警向西南高海拔扩散：</b>全网 {dcold} 条低温类预警主导，云南 {yn} 条居首，
<b>大理剑川/弥渡道路结冰黄色首次触及云南次级香葱产区</b>、四川凉山会东暴雪橙色；
但 {rrcount}，<b>核心产区与外运主通道无直接冲击</b>，不宜据条数外推泸西减产。</li>
<li><b>同比高基数与结构性过剩：</b>红香葱同比 {yoyred:.1f}%，但 2024/2025 同期 7.05 / 6.25 均属近年高位；
跌幅不宜全部归因于本年度供给恶化，然而泸西复种 46.7 万亩次面积高企，<b>供给过剩仍是结构性约束</b>。</li>
<li><b>口径分歧：</b>泸西公开报价从平台挂牌 1.00 到加工品 40.00 元/公斤，跨口径横比严重失真；
19.50 元/公斤的呼和浩特保全庄为极端离群值，已单列标注、不删除但排除出可比均值。</li>
<li><b>替代竞争：</b>大葱处明显低位（呈贡龙城 3.75、王旗营 4.00、师宗 5.00、全国最高重庆 9.00 元/公斤），
对香葱消费形成替代压制。</li>
<li><b>数据源断更：</b>国资云农泸西地头大宗价自 10/29 起连续多期未发布（末值 10-28 的 5.00），
地头统货大宗 4.60 为<b>推算值</b>，已标注，建议补充替代实地采集源。</li>
</ul>

<h3>7.1 行动建议与跟踪指标</h3>
<table><thead><tr><th>建议</th><th>责任人</th><th>时限</th><th>验证指标</th></tr></thead><tbody>
<tr><td>以地慧数农原表核实 11-09 全省综合两转载源（3.1-3.5 vs 3.3-3.6），并补齐 11-08 缺口</td><td>行情采集岗</td><td>下一期日报前</td><td>确定唯一本期值；全省综合与泸西分区价差可复算且不再源依赖</td></tr>
<tr><td>以景臻·王旗营原始表影像复核 11-07 / 11-08 / 11-09 三期小葱读数，裁定 4.00 与 2.30 分歧</td><td>行情采集岗</td><td>下一期日报前</td><td>三期读数与成交量、综合平均价、总吨位逐项对齐，历史序列是否回写有据</td></tr>
<tr><td>全国销地跨期比较固定采用「同市场配对口径」，全样本均值仅登记</td><td>模型维护岗</td><td>即日起每日</td><td>每期输出配对样本数、配对均值、涨跌家数；表观均值不得单独用于趋势结论</td></tr>
<tr><td>跟踪泸西红香葱「均价」标签是否跟随区间下移，验证基准偏高假设</td><td>产区联络岗</td><td>未来 3 个报价日</td><td>均价标签由 3.45 下移至 3.35 或以下即确认补跌，触发模型基准重算</td></tr>
<tr><td>跟踪 11-11 至 11-17 回暖后田间上市量，验证低温是否兑现减产</td><td>产区联络岗</td><td>未来 7 天</td><td>泸西日外运量、王旗营小葱成交量、黑葱是否继续下调</td></tr>
</tbody></table>
<div class="note">以上为决策支持，非交易建议；每条建议均绑定可复算指标与时限，概率与中枢均不构成价格承诺。</div>

<h2>八、情景推演</h2>
<table><thead><tr><th>情景</th><th>触发条件</th><th>3 个月中枢</th><th>概率</th></tr></thead><tbody>
<tr><td><b>A 基准</b></td><td>泸西红葱标签维持 3.45，季节性上行 + 降温温和兑现，全省综合未出现确认下调，需求端不继续恶化</td><td>{a3:.2f} 元/公斤</td><td>40%</td></tr>
<tr><td><b>B 上修</b></td><td>低温超预期致明显减产、霜霉病扩散，或销地跟涨、节前备货提前放量；
基准口径上修至地头统货大宗 4.60（较现基准 +33%）</td><td>{b3:.2f} 元/公斤</td><td>20%</td></tr>
<tr><td><b>C 下修</b></td><td>泸西均价标签跟随区间补跌、全省综合源A 倒挂确认、第 2 周干暖使供给快速恢复、销地续弱，
泸西二次下调至 3.00（较现基准 -13%）</td><td>{c3:.2f} 元/公斤</td><td>40%</td></tr>
</tbody></table>
<div class="note">情景中枢按<b>基准价替代法</b>推演：以 A 档 3 个月中枢 {a3:.2f} 为基数，
按替代基准 / 现基准（{br:.2f}）等比缩放——B 档替代基准为地头统货大宗 4.60、C 档为再跌至 3.00。
<b>概率较上期调整：A 由 45% 下调至 40%、B 维持 20%、C 由 35% 上调至 40%。</b>
依据四项边际转弱：① 泸西红葱区间下移 0.1、均价标签黏性，三个独立观测指向 3.30~3.35，基准偏高；
② 全省综合源A 3.30 低于泸西 3.45，倒挂再现（源依赖已限定）；
③ 王旗营农业农村部口径 3.80 → 3.50（{wqchg:+.1f}%），全国配对 42 家仅 {matchchg:+.2f}%，销地未回暖；
④ 低温与降水均为短脉冲，11-11 起快速回暖转干，供给收缩窗口比上期更短。
反向支撑：全省综合黑葱已与泸西对齐（下行未失控）、云南核心产区零预警、销地绝对价位仍显著高于产地（配对均值 {matchnow:.2f} 对 {br:.2f}），
故 B 档维持、A 档下调幅度克制。
<b>保留意见：</b>本期全省综合两源分歧与 11-08 缺口、王旗营三口径并存、泸西区间与均价标签背离，三项均降低结论置信度；
节日脉冲修复后情景中枢不再继承日历悬崖，但节后衰减尾参数（21 天）为模型假设，尚待实际节后行情校验。
此处概率仅反映<b>相对路径</b>分歧，不构成价格承诺。</div>

<div class="foot">
数据来源：中央气象台（nmc.cn）、Open-Meteo 预报与归档 API、农业农村部信息中心（含证券之星转载：全国 50 家小葱 / 大葱 roundup、王旗营与呈贡龙城单市场表）、
农业农村部重点农产品市场信息平台、昆明市农业农村局 / 景臻·王旗营、云南蔬菜主产区每日菜价、
11月9日云南产地蔬菜综合交易价格（两个转载源并列）、云南蔬菜市场综合菜价（2024/2025 历史档案）、
昆明市呈贡龙城农产品经营股份公司、辽宁朝阳果菜批发市场、一亩田、惠农网、国资云农。<br>
本报告由自动化任务 376dffed 生成，仅供经营参考，不构成交易建议。价格单位除特别标注外均为元/公斤；
带 * 的数值为沿用口径、近似日档案、推算值或另一采价口径，已在对应条目注明。缺失值只标注不插补，冲突值只并列不平均。
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
    DPROD_NOTE = ("主产区相关预警共 {n} 条，结构由暴雨转为<b>低温冰冻与暴雨并存</b>："
                  "滇西滇西南（临沧/德宏）暴雨为主，<b>大理剑川/弥渡道路结冰黄色</b>为云南次级香葱产区"
                  "首次出现低温冰冻预警，另四川凉山会东暴雪橙色；属云南 {yn} 条预警跃居全国首位、"
                  "全网低温类 {cold} 条主导的结构性变化。其中红河州 {rn} 条、泸西本县 {ln} 条，"
                  "<b>核心产区与外运主通道本轮完全不在雨带/冰冻带内</b>。"
                  "本期风险以 {cdate} 最低 {ctmin}℃ 的单日低温脉冲、{pdate} 降水（{pmm} mm）"
                  "与第 2 周快速回暖转干三者叠加为主。").format(
        n=len(prod_hits), yn=YN_WARN, cold=DCOLD, rn=RR_COUNT, ln=LX_COUNT,
        cdate=COLD_DATE, ctmin=COLD_TMIN, pdate=PEAK_DATE, pmm=PEAK_MM)
else:
    DPROD_NOTE = ("本期无直接影响香葱主产区的生效预警，天气风险以 {cdate} 最低 {ctmin}℃ 的单日低温"
                  "与 {pdate} 本地降水（{pmm} mm）为主。").format(
        cdate=COLD_DATE, ctmin=COLD_TMIN, pdate=PEAK_DATE, pmm=PEAK_MM)


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
    n43=N43, mean43=MEAN43, wqnew=WQ_NEW,
    blkchg=BLK_CHG_TXT, blkchgpct=BLK_CHG_PCT_TXT, spread=SPREAD,
    yn=YN_WARN, dge=DGE, dcold=DCOLD,
    med50=MED50, min50=MIN50, max50=MAX50, excl50=EXCL50,
    prev_mean=PREV_MEAN, naive=NAIVE_CHG,
    matchn=MATCH_N, matchprev=MATCH_PREV, matchnow=MATCH_NOW, matchchg=MATCH_CHG,
    sup=S_UP, sdn=S_DOWN, sflat=S_FLAT,
    qs_a=QS_A, qs_b=QS_B, wq_prev=WQ_PREV, wq_chg=WQ_CHG, wq_jz=WQ_JZ,
    # HTML 中使用的短别名（与上方长名同源，确保 format 不缺键）
    excl=EXCL50, mean50=NATIONAL_MEAN, wqchg=WQ_CHG,
)

html_path = os.path.join(OUT_DIR, "香葱行情分析_{0}.html".format(TODAY))
with open(html_path, "w", encoding="utf-8") as f:
    f.write(html)
print("[OK] 报告", html_path, len(html) // 1024, "KB")
print("红葱中枢:", BASE_RED, "→", [r["center"] for r in FRED["rows"]])
print("黑葱中枢:", BASE_BLACK, "→", [r["center"] for r in FBLK["rows"]])
print("20日均线:", FRED["ma20"])
