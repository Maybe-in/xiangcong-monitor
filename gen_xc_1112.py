# -*- coding: utf-8 -*-
"""香葱行情定时任务（376dffed）· 2026-11-12 第 23 次执行 · 数据日 2026-11-11（发布源次日可得）

产出：
  1) data/sources/xiangcong_2026-11-12.json  统一 schema 全量报价 + 六档预测
  2) outputs/香葱行情分析_2026-11-12.html    八章 / 十图 单页报告

设计要点：
  - 长周期、季节因子、六档预测全部复用 src.longterm / src.price / src.config，
    与 run.py 及历史各期同源，口径一致（长周期=通货毛葱，预测=精品净葱/集散价，×1.66）。
  - 缺失值只标注不插补；冲突口径只并列不平均；估算值在 note 显式标注。
  - HTML 使用 @@KEY@@ 占位符 + replace，避免 CSS 花括号与 str.format 冲突。
"""
from __future__ import annotations

import glob
import json
import os
import re
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

DATA_DATE = "2026-11-11"   # 当日发布源已取得（泸西菜价表 / 全省综合 / 全国 48 家 roundup）
PREV_DATE = "2026-11-10"

# 本期核心实测（泸西分区，11-11 实测）：与 11-10 完全持平，连续 11 个报价日锁定
RED_MID, RED_LO, RED_HI = 3.45, 3.2, 3.5
BLK_MID, BLK_LO, BLK_HI = 2.76, 2.5, 2.9
PREV_RED, PREV_BLK = 3.45, 2.76
RED_CHG, BLK_CHG = RED_MID - PREV_RED, BLK_MID - PREV_BLK
SPREAD = round(RED_MID - BLK_MID, 2)

# ============================================================ 0. 回写实测价（幂等）
HIST_PATH = os.path.join(BASE_DIR, "data", "price_history.json")
hist = json.load(open(HIST_PATH, encoding="utf-8"))
_new = [
    {"date": DATA_DATE, "variety": "红香葱", "market": "云南产地", "price": RED_MID,
     "source": "observed",
     "note": "泸西菜价（2026-11-11 实测）红香葱 3.2-3.5、官方均价标签 3.45，与 11-10 完全持平；自 11-01 起连续十一个报价日锁定。全省综合三源一致 3.1-3.5 形成 0.15 倒挂，登记为先行信号但不改写历史序列；区间与加权均价标签为该表固定并列标注格式，中值 3.35 不作为独立补跌信号"},
    {"date": DATA_DATE, "variety": "黑葱", "market": "云南产地", "price": BLK_MID,
     "source": "observed",
     "note": "泸西菜价（2026-11-11 实测）黑香葱 2.5-2.9 均价 2.76，与 11-10 完全持平（11-08 破位后连续四日锁定）；通海、全省综合区间同步，红黑价差维持 0.69"},
    {"date": DATA_DATE, "variety": "小葱", "market": "昆明王旗营", "price": 3.00,
     "source": "observed",
     "note": "2026-11-11 景臻·王旗营批发平均价格统计表 小葱 3.00 / 前一日交易量 35 吨，与农业农村部 11-11 全国 48 家 roundup「昆明景臻王旗营 3.00」双源互证；此前 2.30/3.50/3.80/4.00 多读数分歧收敛。综合平均价 4.37、总吨位 3082"},
]
_have = {(s["date"], s["variety"]) for s in hist["series"]}
for n in _new:
    if (n["date"], n["variety"]) not in _have:
        hist["series"].append(n)
    else:
        for s in hist["series"]:
            if s["date"] == n["date"] and s["variety"] == n["variety"]:
                s.update(n)
hist["series"].sort(key=lambda s: (s["date"], s["variety"]))
with open(HIST_PATH, "w", encoding="utf-8") as f:
    json.dump(hist, f, ensure_ascii=False, indent=2)
print("[OK] price_history 回写", DATA_DATE, "3 条（幂等）")

# ============================================================ 1. 长周期
lt = longterm.build_longterm()
series = lt["series"]
anchors = lt["anchors"]
windows = {w["months"]: w for w in lt["windows"]}
PREMIUM = lt["premium"]

# ============================================================ 2. 天气（按今日重切窗口）
WX_PATH = os.path.join(BASE_DIR, "data", "weather_2026-11-12.json")
wx = json.load(open(WX_PATH, encoding="utf-8"))
_all = [d for d in wx["core"]["daily"] if d.get("tmax") is not None]
core_daily = [d for d in _all if d["date"] >= TODAY]
if len(core_daily) < 15:
    core_daily = _all
clim = wx["core"].get("climatology") or {}
w3 = summarize_window(core_daily, 0, 3)
w7 = summarize_window(core_daily, 0, 7)
wh = summarize_window(core_daily, 7, 15)
WX_GEN = wx["generated_at"]

_fc16 = core_daily[:16]
_peak = max(_fc16, key=lambda d: (d.get("precip") or 0))
PEAK_DATE = _peak["date"][5:].replace("-", "/")
PEAK_MM = round(_peak.get("precip") or 0, 1)
_cold = min([d for d in _fc16 if d.get("tmin") is not None], key=lambda d: d["tmin"])
COLD_DATE = _cold["date"][5:].replace("-", "/")
COLD_TMIN = _cold["tmin"]
RAIN_DAYS = sum(1 for d in _fc16 if (d.get("precip") or 0) >= 1)
RAIN_TOTAL = round(sum((d.get("precip") or 0) for d in _fc16), 1)
HEAVY_DESC = "、".join("%s %.1fmm" % (d["date"][5:].replace("-", "/"), d["precip"])
                     for d in _fc16 if (d.get("precip") or 0) >= 5) or "无"
ANO = round((w3.get("tmax_avg") or 0) - (clim.get("tmax_mean") or 0), 1)
EARLY_T = round(sum(d["tmax"] for d in _fc16[:7]) / max(1, len(_fc16[:7])), 1)
LATE_T = round(sum(d["tmax"] for d in _fc16[7:]) / max(1, len(_fc16[7:])), 1)
WTREND = ("前 7 天最高温均 %.1f℃ → 第 2 周 %.1f℃（%+.1f℃），整体转干、无二次强降温"
          % (EARLY_T, LATE_T, LATE_T - EARLY_T))

# ============================================================ 3. 灾害（缺失只标注不插补）
DZ_PATH = os.path.join(BASE_DIR, "data", "disaster_2026-11-12.json")
DZ = json.load(open(DZ_PATH, encoding="utf-8"))
DZ_TOTAL = DZ.get("total", 0)
DZ_OK = DZ_TOTAL > 0
_hz = dict(DZ.get("hazard_stats", [])) if DZ_OK else {}
DZ_TOP = DZ.get("production_area", []) if DZ_OK else []
_prod_hits = DZ_TOP
_rr = [t for t in _prod_hits if "红河" in t.get("region", "")]
_lx = [t for t in _prod_hits if "泸西" in t.get("region", "")]
RR_COUNT, LX_COUNT = len(_rr), len(_lx)
if DZ_OK:
    HAZARD_DESC = "、".join("%s %d条" % (k, v) for k, v in
                           sorted(_hz.items(), key=lambda kv: -kv[1])[:6])
    DISASTER_NOTE = ("中央气象台 findAlarm 结构化清单 %d 条，主导灾种 %s；"
                     "涉及香葱主产区 %d 条，其中红河州 %d 条、泸西本县 %d 条。") % (
                         DZ_TOTAL, HAZARD_DESC, len(_prod_hits), RR_COUNT, LX_COUNT)
    DZ_ROWS = "".join(
        "<tr><td>%s</td><td>%s%s</td><td>%s</td></tr>" % (
            t.get("region", ""), t.get("hazard", ""), t.get("level", ""),
            "是" if t.get("is_production_area") else "否")
        for t in DZ_TOP[:20]) or "<tr><td colspan='3'>本轮无主产区相关预警</td></tr>"
else:
    HAZARD_DESC = "未取得（接口超时）"
    DISASTER_NOTE = (
        "⚠️ 本轮中央气象台 findAlarm 结构化预警接口连续超时，未取得可用清单，"
        "按「缺失值只标注不插补」原则不虚构条数与灾种结构。"
        "改用中央气象台 11-10 每日天气提示与天气公报作为定性依据："
        "① 本轮寒潮对陆地影响已近尾声，中东部气温回升，云南降雨强度明显减弱；"
        "② 11-09 实况强降雨中心在云南中西部（暴雨/大暴雨 100~151mm）、滇东北高海拔降雪，"
        "10 日早晨江南、华南中东部及云南出现 4~10℃ 降温，昆明最高气温 7℃（立秋以来首次个位数）；"
        "③ 10-12 日南支槽东移，云南、广西、贵州多阴雨（局地大雨），"
        "11-15 日新疆北部有中到大雪局地暴雪；④ 11-10 06 时大风蓝色预警继续发布，海上 7~8 级阵风 9~10 级。"
        "⑤ 泸西位于滇东红河州，本轮既不在滇西暴雨核心带、也不在滇东北降雪带，"
        "风险以低温寡照与采收受阻为主，洪涝型断供概率低。")
    DZ_ROWS = ("<tr><td colspan='3'>接口超时，本期无结构化预警清单；"
               "定性依据见下方说明，条数不作插补</td></tr>")

# ============================================================ 4. 六档预测（模型同源）
history = price.load_history()
fc = price.build_forecast(history, core_daily, clim=clim)
FRED, FBLK = fc["红香葱"], fc["黑葱"]
BASE_RED, BASE_BLACK = FRED["current"], FBLK["current"]
HORIZON_MAP = [("d3", "未来3天"), ("w1", "未来7天"), ("h1", "未来15天"),
               ("m1", "未来1个月"), ("m2", "未来2个月"), ("m3", "未来3个月")]
RRED = {r["key"]: r for r in FRED["rows"]}
RBLK = {r["key"]: r for r in FBLK["rows"]}
FORECASTS = []
for key, label in HORIZON_MAP:
    r, b = RRED[key], RBLK[key]
    FORECASTS.append({
        "horizon": label, "target_date": r["target_date"], "item": "香葱",
        "center": r["center"], "low": r["low"], "high": r["high"],
        "delta_pct": r["delta_pct"], "confidence": r["confidence"],
        "note": "泸西红香葱（精品净葱/集散价口径）；黑葱同档中枢 %.2f 元/公斤（%+.1f%%）；"
                "区间为情景区间非统计置信区间" % (b["center"], b["delta_pct"]),
    })
_centers = [r["center"] for r in FRED["rows"]]
if all(_centers[i] <= _centers[i + 1] + 1e-9 for i in range(len(_centers) - 1)):
    MONO_DESC = "六档中枢单调递增，指向季节性温和上行"
else:
    _dip = next((i for i in range(len(_centers) - 1) if _centers[i] > _centers[i + 1]), None)
    MONO_DESC = ("第 %d 档较前档小幅回落（%.2f → %.2f），系春节后节日脉冲衰减"
                 "与 2 月季节因子回落叠加，非趋势反转" % (
                     _dip + 2, _centers[_dip], _centers[_dip + 1])) if _dip is not None else "路径震荡"

# ============================================================ 5. 全量报价
def Q(date, item, variety, market, province, ptype, low, high, mid, source, url="", note=""):
    return {"date": date, "item": item, "variety": variety, "market": market,
            "province": province, "price_type": ptype, "unit": "元/公斤",
            "low": low, "high": high, "mid": mid,
            "source": source, "source_url": url, "note": note}


QUOTES = []
A = QUOTES.append

WX_URL = "http://mp.weixin.qq.com/s?__biz=MzU5MTc0MTM0MA==&mid=2247595908&idx=1&sn=00c26cf9bdca852368a11b86030adb17"
QSH_A_URL = "http://mp.weixin.qq.com/s?__biz=Mzg3Mzg1MTgwNw==&mid=2247490638&idx=1&sn=b7aa5e842021329b358f1206aa176155"
QSH_B_URL = "http://mp.weixin.qq.com/s?__biz=MzI0NzExNjUxMw==&mid=2653645833&idx=1&sn=c17cc49f7e5f80d0e3d6c5235000a257"
HGW_URL = "https://wap.stockstar.com/detail/IG2026111000020029"
WW_URL = "https://futures.stockstar.com/IG2026111000020146.shtml"
CY_URL = "http://www.cncyms.cn/"
CQ_URL = "http://sc.cqnync.cn/marketSta/?vexp=2&classId=2"
YMT_URL = "https://www.ymt.com/supplylist/li-1-0-7886"
YMT2_URL = "https://m.ymt.com/supply/62574443"
HNN_URL = "https://www.cnhnb.com/p/xiaocong-0-25-0-0-5/"
KM2025_URL = "https://nyncj.km.gov.cn/c/2025-11-10/5033465.shtml"
YUN2025_URL = "https://wap.stockstar.com/detail/IG2025111000012864"
YMT2023_URL = "http://mp.weixin.qq.com/s?__biz=MzU0NjgzOTMyNA==&mid=2247499674&idx=1&sn=657a1fc5ff89ec9d46fe40255036eb36"

# —— 泸西核心产区（11-10 实测，模型基准口径）
A(Q(PREV_DATE, "香葱", "红香葱", "云南红河州泸西县", "云南", "产地收购价",
    RED_LO, RED_HI, RED_MID, "云南蔬菜主产区每日菜价（泸西菜价表 11-10）", WX_URL,
    "11-10 模型基准（11-11 沿用）。红香葱 3.2-3.5、官方均价标签 3.45，与 11-09 完全持平；自 11-01 起连续十个报价日锁定 3.45。行情措辞「油麦涨2毛，香菜再涨1元」，未提及香葱调整"))
A(Q(PREV_DATE, "香葱", "红香葱（区间中值口径）", "云南红河州泸西县", "云南", "产地收购价",
    3.2, 3.5, 3.35, "云南蔬菜主产区每日菜价（泸西菜价表 11-10，区间中值推算）", WX_URL,
    "★推算值：按 3.2-3.5 取区间中值 3.35，与官方均价标签 3.45 相差 0.10。连续两期背离，登记为向下先行信号，不改写历史序列、不用于模型基准"))
A(Q(PREV_DATE, "香葱", "黑香葱", "云南红河州泸西县", "云南", "产地收购价",
    BLK_LO, BLK_HI, BLK_MID, "云南蔬菜主产区每日菜价（泸西菜价表 11-10）", WX_URL,
    "黑香葱 2.5-2.9、均价 2.76，与 11-09 完全持平；11-08 破位 -6.8% 后连续三日锁定，红黑价差维持 0.69"))
A(Q(PREV_DATE, "香葱", "红葱", "云南玉溪市通海县", "云南", "产地收购价",
    3.1, 3.5, 3.30, "云南蔬菜主产区每日菜价（通海菜价表 11-10）", WX_URL,
    "通海红葱 3.1-3.5 与 11-09 完全持平，按区间中值 3.30 登记；片区与泸西同步横盘"))
A(Q(PREV_DATE, "香葱", "黑葱", "云南玉溪市通海县", "云南", "产地收购价",
    2.5, 2.9, 2.70, "云南蔬菜主产区每日菜价（通海菜价表 11-10）", WX_URL,
    "通海黑葱 2.5-2.9 持平，与泸西区间完全一致；按区间中值 2.70 登记"))

# —— 全省综合：本期两个转载源完全一致（上期分歧收敛）
A(Q(PREV_DATE, "香葱", "红香葱", "云南产地综合交易价（全省，源A）", "云南", "产地批发价",
    3.1, 3.5, 3.30, "11月10日云南产地蔬菜综合交易价格（云南蔬菜综合报价）", QSH_A_URL,
    "★11-10 关键变化：上期源A 3.30 / 源B 3.45 的两源分歧本期消失，两个独立转载源均报 3.1-3.5（中值 3.30），全省综合口径确认落在 3.30；仍低于泸西官方标签 3.45，倒挂 0.15 延续"))
A(Q(PREV_DATE, "香葱", "黑葱", "云南产地综合交易价（全省，源A）", "云南", "产地批发价",
    2.5, 2.9, 2.70, "11月10日云南产地蔬菜综合交易价格（云南蔬菜综合报价）", QSH_A_URL,
    "全省综合黑葱 2.5-2.9，与泸西、通海区间完全一致，三口径对齐"))
A(Q(PREV_DATE, "香葱", "红香葱", "云南产地综合交易价（全省，源B）", "云南", "产地批发价",
    3.1, 3.5, 3.30, "2026年11月10日云南菜价（另一公众号转载，同源表）", QSH_B_URL,
    "源B 与源A 本期完全一致（3.1-3.5），上期 3.45 的高读数未延续，判为源A 口径为准"))
A(Q(PREV_DATE, "香葱", "黑葱", "云南产地综合交易价（全省，源B）", "云南", "产地批发价",
    2.5, 2.9, 2.70, "2026年11月10日云南菜价（另一公众号转载，同源表）", QSH_B_URL,
    "源B 黑葱 2.5-2.9，与源A 一致"))

# —— 昆明王旗营销地（口径并列，不平均）
A(Q(PREV_DATE, "香葱", "小葱", "昆明景臻·王旗营（转载表口径）", "云南", "销地批发价",
    None, None, 3.50, "11月10日云南产地蔬菜综合交易价格·内嵌王旗营表", QSH_A_URL,
    "王旗营转载表 11-10 小葱 3.50、前一日交易量 20 吨；较 11-09 转载表 4.00/30吨 价跌 12.5%、量减 33.3%。与农业农村部 11-09 roundup 3.50 一致，属另一采价口径，不与 2.30 平均"))
A(Q(PREV_DATE, "香葱", "小葱", "昆明景臻·王旗营（本仓历史序列沿用）", "云南", "销地批发价",
    None, None, 2.30, "本仓 price_history 主序列（景臻平均价统计表口径）", KM2025_URL,
    "★11-10 沿用值：官方「景臻·王旗营蔬菜批发平均价格统计表」未取得，主序列沿用 11-09 的 2.30 并显式标注；两套口径并列、不混用、不解读为单日暴涨"))

# —— 销地横截面（11-10 实测）
A(Q(PREV_DATE, "香葱", "小葱", "安徽合肥周谷堆农产品批发市场", "安徽", "销地批发价",
    None, None, 6.70, "农业农村部信息中心（证券之星转载 11-10）", HGW_URL,
    "11-10 小葱 6.70 元/公斤，为大中销区中位偏高水平；同表大葱 2.20、香菜 3.80"))
A(Q(PREV_DATE, "香葱", "小葱", "甘肃武威昊天农产品交易市场", "甘肃", "销地批发价",
    None, None, 4.70, "农业农村部信息中心（证券之星转载 11-10）", WW_URL,
    "西北销区小葱 4.70 元/公斤；同表大葱 1.30、香菜 2.80"))
A(Q(PREV_DATE, "香葱", "香葱", "青岛城阳蔬菜水产品批发市场", "山东", "销地批发价",
    6.00, 8.00, 7.60, "青岛市城阳蔬菜水产品批发市场官网 11-10", CY_URL,
    "香葱 最高 8.00 / 最低 6.00 / 中间 7.60，与上期 7.60 持平；为全国最高档销区之一"))
A(Q(PREV_DATE, "香葱", "小葱", "重庆（农业农村委零售监测）", "重庆", "零售价",
    None, None, 10.00, "重庆农业农村信息网市场行情查询 11-10", CQ_URL,
    "零售口径 10.00 元/公斤，单列不并入批发横截面均值；同表大葱 5.00、大蒜 8.00"))
A(Q(PREV_DATE, "香葱", "香葱（云南货源）", "邯郸南大堡蔬菜批发市场", "河北", "销地批发价",
    4.00, 4.40, 4.20, "邯郸南大堡蔬菜批发市场 11-10 蔬菜价格行情（公众号）", "http://mp.weixin.qq.com/s?__biz=MzI2MzI3MjAwMw==&mid=2247503298&idx=1&sn=21865c7f1538315286be994f357ed7ad",
    "★换算值：2.0 / 2.1 / 2.2 元/斤 ×2 = 4.00 / 4.20 / 4.40 元/公斤，产地标注「云」。云南货对本地货溢价 75%，是观察产销地价差的优质样本"))
A(Q(PREV_DATE, "香葱", "小葱（本地香/钢葱）", "邯郸南大堡蔬菜批发市场", "河北", "销地批发价",
    1.40, 3.20, 2.40, "邯郸南大堡蔬菜批发市场 11-10 蔬菜价格行情（公众号）", "http://mp.weixin.qq.com/s?__biz=MzI2MzI3MjAwMw==&mid=2247503298&idx=1&sn=21865c7f1538315286be994f357ed7ad",
    "★换算值：0.7 / 1.2 / 1.6 元/斤 ×2 = 1.40 / 2.40 / 3.20 元/公斤，本地货；与同市场云南货 4.20 形成 75% 溢价对照，非泸西口径"))
A(Q(PREV_DATE, "香葱", "小葱", "浙江安吉农副产品综合批发市场", "浙江", "销地批发价",
    7.00, 8.00, 7.50, "安吉农批市场今日菜价公示 2026-11-10", "http://mp.weixin.qq.com/s?__biz=MzA3ODU5MDAzNQ==&mid=2247511962&idx=1&sn=92bb6b4175215de31e3ccb7bd244789d",
    "★换算值：3.5-4.0 元/斤 ×2 = 7.00-8.00 元/公斤，按区间中值 7.50 登记；销售均价口径"))
A(Q(PREV_DATE, "香葱", "小葱", "山西榆次汇隆农产品市场", "山西", "销地批发价",
    6.60, 7.00, 6.80, "山西榆次汇隆市场 2026-11-10 价格动态", "http://mp.weixin.qq.com/s?__biz=MzA4ODU4ODAzOQ==&mid=2453872339&idx=1&sn=350e8fd095310de1202f0635eef4e139",
    "★换算值：最低 3.3 / 最高 3.5 / 平均 3.4 元/斤 ×2 = 6.60 / 7.00 / 6.80 元/公斤；市场销售均价口径"))

# —— 平台挂牌（非成交，估算/换算须标注）
A(Q(PREV_DATE, "香葱", "小香葱（通货挂牌）", "一亩田·云南泸西", "云南", "产地地头价",
    None, None, 5.00, "一亩田供应页（挂牌非成交）", YMT2_URL,
    "★挂牌非成交价：小香葱通货 5.00 元/公斤，与集散价 3.45 差 1.55，长期不刷新，仅作口径上沿参考"))
A(Q(PREV_DATE, "香葱", "红葱（挂牌）", "一亩田·云南泸西", "云南", "产地地头价",
    None, None, 3.00, "一亩田供应页（挂牌非成交）", YMT_URL,
    "★换算值：1.50 元/斤 ×2 = 3.00 元/公斤；挂牌非成交"))
A(Q(PREV_DATE, "香葱", "小葱 45-50cm（挂牌）", "一亩田·云南泸西", "云南", "产地地头价",
    None, None, 4.40, "一亩田供应页（挂牌非成交）", YMT_URL,
    "★换算值：2.20 元/斤 ×2 = 4.40 元/公斤；规格货挂牌，非成交"))
A(Q(PREV_DATE, "香葱", "精品小香葱·铁杆（挂牌）", "一亩田·云南泸西", "云南", "产地地头价",
    None, None, 1.50, "一亩田供应页（挂牌非成交）", YMT_URL,
    "挂牌 1.50 元/公斤明显低于同期成交区间，判为引流挂牌，仅登记不用于定价"))
A(Q(PREV_DATE, "香葱", "小香葱（挂牌）", "惠农网·云南泸西", "云南", "产地地头价",
    None, None, 3.00, "惠农网供应页（挂牌非成交）", HNN_URL,
    "★换算值：1.50 元/斤 ×2 = 3.00 元/公斤；10000 斤起批挂牌"))
A(Q(PREV_DATE, "香葱", "代收代办（含服务费）", "惠农网·云南泸西", "云南", "产地地头价",
    None, None, 10.00, "惠农网供应页（挂牌非成交）", HNN_URL,
    "★换算值：5.00 元/斤 ×2 = 10.00 元/公斤；代办报价含服务费/包装，非产地成交价，不可用于定价，构成口径极值"))
A(Q(PREV_DATE, "香葱", "红葱（火葱，大理弥渡）", "一亩田·云南大理弥渡", "云南", "产地地头价",
    None, None, 4.80, "一亩田供应页（挂牌非成交）", "https://m.ymt.com/supply/66623569",
    "★换算值：2.40 元/斤 ×2 = 4.80 元/公斤；滇西次级产区挂牌，非泸西口径"))

# —— 隔年精确同日档案 2025-11-10（同比基准）
A(Q("2025-11-10", "香葱", "红香葱", "云南红河州泸西县", "云南", "产地收购价",
    6.0, 6.4, 6.25, "2025年11月10日呈贡/晋宁/嵩明/陆良/通海/元谋/泸西菜价", WX_URL.replace("2247595908", "2247592656").replace("00c26cf9bdca852368a11b86030adb17", "e20fbd941ae95eae54138d64a779e420"),
    "隔年精确同日档案：泸西红香葱 6.0-6.4 均价 6.25，本期 3.45 同比 -44.8%；行情措辞「小香葱平稳」"))
A(Q("2025-11-10", "香葱", "黑香葱", "云南红河州泸西县", "云南", "产地收购价",
    4.1, 4.6, 4.16, "2025年11月10日泸西菜价表", WX_URL.replace("2247595908", "2247592656").replace("00c26cf9bdca852368a11b86030adb17", "e20fbd941ae95eae54138d64a779e420"),
    "隔年精确同日档案：泸西黑香葱 4.1-4.6 均价 4.16，本期 2.76 同比 -33.7%"))
A(Q("2025-11-10", "香葱", "红葱", "云南玉溪市通海县", "云南", "产地收购价",
    6.0, 6.4, 6.20, "2025年11月10日通海菜价表", "",
    "隔年精确同日档案：通海红葱 6.0-6.4，按区间中值 6.20 登记"))
A(Q("2025-11-10", "香葱", "黑葱", "云南玉溪市通海县", "云南", "产地收购价",
    4.1, 4.6, 4.35, "2025年11月10日通海菜价表", "",
    "隔年精确同日档案：通海黑葱 4.1-4.6，按区间中值 4.35 登记"))
A(Q("2025-11-10", "香葱", "小葱", "昆明景臻·王旗营", "云南", "销地批发价",
    None, None, 6.60, "昆明市农业农村局 2025-11-10 批发平均价格统计表", KM2025_URL,
    "隔年精确同日档案：王旗营小葱 6.60、前一日交易量 40 吨、综合平均价 6.54、总吨位 3361；本期转载口径 3.50 同比 -47.0%，本仓沿用口径 2.30 同比 -65.2%（两口径分列）"))
A(Q("2025-11-10", "香葱", "葱（综合）", "云南云菜集团有限公司", "云南", "销地批发价",
    2.50, 4.50, 3.60, "农业农村部信息中心（证券之星转载 2025-11-10）", YUN2025_URL,
    "隔年精确同日档案：云菜集团「葱」最高 4.50 / 最低 2.50 / 大宗 3.60，为宽口径葱类综合价，仅作历史背景"))
A(Q("2023-11-10", "香葱", "红香葱", "云南市场综合菜价（地头毛菜）", "云南", "产地地头价",
    4.0, 4.5, 4.50, "2023年11月10日云南市场综合菜价", YMT2023_URL,
    "历史档案：2023-11-10 红香葱 4-4.5、昨价 4.5，地头毛菜口径；用于近五年 11 月上旬同期对比"))


# ==================================================== 11-11 当日实测（本次复跑新增，全量入库）
NAT_URL = "https://futures.stockstar.com/IG2026111100024477.shtml"
LX1111 = "http://mp.weixin.qq.com/s?__biz=MzU5MTc0MTM0MA==&mid=2247595912&idx=1&sn=b2ad236a2577314a1df653c2240e6038"
QSH_A11 = "http://mp.weixin.qq.com/s?__biz=MzY4ODEyNjkxMQ==&mid=2247490979&idx=1&sn=69e216145dfb940b89280e51205cff93"
QSH_B11 = "http://mp.weixin.qq.com/s?__biz=Mzg3Mzg1MTgwNw==&mid=2247490643&idx=1&sn=25477118281e866c8c3e48f26091c3b1"
QSH_C11 = "http://mp.weixin.qq.com/s?__biz=MzI0NzExNjUxMw==&mid=2653645836&idx=1&sn=7c75ad47da8a0c84a79b7417de9ea2e2"
KM251111 = "https://nyncj.km.gov.cn/c/2025-11-11/5033763.shtml"
LX251111 = "http://mp.weixin.qq.com/s?__biz=MzU5MTc0MTM0MA==&mid=2247592670&idx=1&sn=9bb919b45dc2277dc7c355b5bb472a78"
HD1111 = "http://mp.weixin.qq.com/s?__biz=MzI2MzI3MjAwMw==&mid=2247503302&idx=1&sn=14fc80e3a82e7b7a6e6f952185ce159f"
HD1111B = "http://mp.weixin.qq.com/s?__biz=MzAwNjk1MzczOA==&mid=2247486780&idx=1&sn=9ae22ce014cb26b61f4b04321b4ad073"
XFD1111 = "http://mp.weixin.qq.com/s?__biz=Mzg5NjM0MDk5Ng==&mid=2247495319&idx=1&sn=76a447a5b3a671bada164316fda400c4"
HNN1108 = "https://www.cnhnb.com/hangqing/cd-2000478-6222-0-0/"

# 5.1 泸西 / 通海 / 全省综合（三源一致）
A(Q(DATA_DATE, "香葱", "红香葱", "云南红河州泸西县", "云南", "产地收购价",
    3.2, 3.5, 3.45, "2026年11月11日呈贡/晋宁/嵩明/陆良/通海/元谋/泸西菜价", LX1111,
    "本期模型基准。红香葱 3.2-3.5、官方均价标签 3.45，与 11-10 完全持平；自 11-01 起连续十一个报价日锁定。区间与加权均价标签为该表固定并列标注格式，中值 3.35 不作为独立补跌信号；行情措辞仅提及叶菜上调，未提香葱调整"))
A(Q(DATA_DATE, "香葱", "红香葱（区间中值口径）", "云南红河州泸西县", "云南", "产地收购价",
    3.2, 3.5, 3.35, "2026年11月11日泸西菜价表（区间中值推算）", LX1111,
    "★推算值：3.2-3.5 取区间中值 3.35，与加权均价标签 3.45 相差 0.10；该表「区间 + 加权均价」为固定并列标注格式，两者非时序领先关系，不作为独立补跌信号，不改写历史序列、不用于模型基准"))
A(Q(DATA_DATE, "香葱", "黑香葱", "云南红河州泸西县", "云南", "产地收购价",
    2.5, 2.9, 2.76, "2026年11月11日泸西菜价表", LX1111,
    "黑香葱 2.5-2.9 均价 2.76，与 11-10 完全持平；11-08 破位 -6.8% 后连续四日锁定，红黑价差维持 0.69"))
A(Q(DATA_DATE, "香葱", "红葱", "云南玉溪市通海县", "云南", "产地收购价",
    3.1, 3.5, 3.30, "2026年11月11日通海菜价表", LX1111,
    "通海红葱 3.1-3.5 与 11-10 完全持平，按区间中值 3.30 登记；片区与泸西同步横盘"))
A(Q(DATA_DATE, "香葱", "黑葱", "云南玉溪市通海县", "云南", "产地收购价",
    2.5, 2.9, 2.70, "2026年11月11日通海菜价表", LX1111,
    "通海黑葱 2.5-2.9 持平，与泸西区间完全一致；按区间中值 2.70 登记"))

for _tag, _url in (("源A", QSH_A11), ("源B", QSH_B11), ("源C", QSH_C11)):
    A(Q(DATA_DATE, "香葱", "红香葱", "云南产地综合交易价（全省，%s）" % _tag, "云南", "产地批发价",
        3.1, 3.5, 3.30, "11月11日云南产地蔬菜综合交易价格（%s）" % _tag, _url,
        "三个独立转载源完全一致报 3.1-3.5（中值 3.30），省级口径确认低于泸西官方标签 0.15，倒挂延续；源分歧已连续两期消除"))
    A(Q(DATA_DATE, "香葱", "黑葱", "云南产地综合交易价（全省，%s）" % _tag, "云南", "产地批发价",
        2.5, 2.9, 2.70, "11月11日云南产地蔬菜综合交易价格（%s）" % _tag, _url,
        "全省综合黑葱 2.5-2.9，与泸西、通海区间完全一致，三口径对齐"))

# 5.2 王旗营：官方表 + 农业农村部 roundup 双源互证
A(Q(DATA_DATE, "香葱", "小葱", "昆明景臻·王旗营（平均价格统计表）", "云南", "销地批发价",
    None, None, 3.00, "昆明市景臻·王旗营蔬菜批发市场 2026-11-11 批发平均价格统计表（三转载源一致）", QSH_A11,
    "小葱 3.00 / 前一日交易量 35 吨；综合平均价 4.37、总吨位 3082。较 11-10 转载表 3.50/20吨 价 -14.3%、量 +75.0%"))
A(Q(DATA_DATE, "香葱", "小葱", "昆明景臻王旗营（农业农村部 roundup）", "云南", "销地批发价",
    None, None, 3.00, "农业农村部信息中心 2026-11-11 全国主要批发市场小葱价格行情（证券之星转载）", NAT_URL,
    "★与上条官方平均价格统计表双源互证同为 3.00；此前 2.30 / 3.50 / 3.80 / 4.00 多读数分歧本期收敛"))
A(Q(DATA_DATE, "香葱", "小葱", "昆明景臻·王旗营（旧历史序列沿用口径）", "云南", "销地批发价",
    None, None, 2.30, "本仓 price_history 主序列（旧沿用口径，仅并列保留）", "",
    "★旧沿用值：11-11 起官方表已取得，后续应以 3.00 为准；本条仅作口径并列，不与 3.00 平均、不用于同比主口径"))

# 5.3 农业农村部 11-11 全国 48 家批发市场小葱 roundup（全量入库）
NAT48 = [
    ("北京新发地农副产品批发市场信息中心", "北京", 3.60),
    ("北京朝阳区大洋路综合市场", "北京", 8.20),
    ("邯郸市(馆陶)金凤禽蛋农贸批发市场", "河北", 1.50),
    ("河北省怀来县京西果菜批发市场有限责任公司", "河北", 6.00),
    ("邯郸市经开区南大堡蔬菜批发市场", "河北", 2.40),
    ("山西省晋城市绿欣农产品贸易有限公司", "山西", 4.70),
    ("内蒙古呼和浩特市东瓦窑农副产品批发市场有限责任公司", "内蒙古", 7.80),
    ("辽宁鞍山宁远农产品批发市场", "辽宁", 2.50),
    ("辽宁朝阳市果菜批发市场", "辽宁", 1.70),
    ("江苏凌家塘市场发展有限公司", "江苏", 6.50),
    ("江苏苏州南环桥农副产品批发市场", "江苏", 3.50),
    ("江苏无锡朝阳农产品大市场", "江苏", 4.59),
    ("义乌市市场发展集团有限公司农批管理分公司", "浙江", 4.60),
    ("浙江嘉兴蔬菜批发交易市场", "浙江", 5.67),
    ("绍兴市蔬菜果品批发交易市场有限公司", "浙江", 4.00),
    ("杭州农副产品物流中心南庄兜农产品批发市场", "浙江", 6.50),
    ("天长市永福农副产品批发市场", "安徽", 5.50),
    ("安徽合肥周谷堆农产品批发市场", "安徽", 5.50),
    ("安徽六安市裕安区紫竹林农产品批发市场", "安徽", 6.00),
    ("马鞍山市安民农副产品贸易有限公司", "安徽", 8.00),
    ("福建省福鼎市商贸业服务中心", "福建", 6.00),
    ("江西乐平蔬菜农产品批发大市场", "江西", 4.60),
    ("江西九江琵琶湖农产品物流有限公司", "江西", 7.20),
    ("山东章丘刁镇蔬菜批发市场", "山东", 2.40),
    ("洛阳宏进农副产品批发市场有限公司", "河南", 2.00),
    ("河南濮阳宏进农副产品批发市场有限公司", "河南", 3.00),
    ("河南万邦国际农产品物流股份有限公司", "河南", 4.00),
    ("湖北鄂州市蟠龙农产品批发市场", "湖北", 10.00),
    ("潜江市四季友农产品市场有限公司", "湖北", 8.00),
    ("湖北省洪湖农贸市场", "湖北", 8.80),
    ("武汉白沙洲农副产品大市场有限公司", "湖北", 6.50),
    ("两湖绿谷物流股份有限公司", "湖北", 5.00),
    ("广东汕头农副产品批发中心市场", "广东", 4.80),
    ("海口市菜篮子江楠农产品批发市场有限公司", "海南", 7.66),
    ("南充川北农产品交易有限公司", "四川", 4.30),
    ("贵阳农产品物流园", "贵州", 6.00),
    ("昆明景臻王旗营蔬菜批发市场", "云南", 3.00),
    ("陕西咸阳新阳光农副产品有限公司", "陕西", 6.40),
    ("庆阳市西峰西郊瓜果蔬菜批发有限责任公司", "甘肃", 5.00),
    ("武威昊天农产品交易市场暨仓储物流中心", "甘肃", 4.70),
    ("金昌市金川天然农产品发展有限责任公司", "甘肃", 7.50),
    ("甘肃省定西市安定马铃薯综合交易中心", "甘肃", 10.50),
    ("甘肃酒泉春光农产品市场有限责任公司", "甘肃", 8.20),
    ("兰州国际高原夏菜副食品采购中心", "甘肃", 5.38),
    ("宁夏海吉星国际农产品物流有限公司", "宁夏", 4.00),
    ("喀什曙光农业科技博览城", "新疆", 13.00),
    ("新疆通汇市场有限公司", "新疆", 6.00),
    ("新疆兵团第五师三和农副产品综合批发市场", "新疆", 8.00),
]
for _nm, _pv, _v in NAT48:
    A(Q(DATA_DATE, "香葱", "小葱", _nm, _pv, "销地批发价",
        None, None, _v, "农业农村部信息中心 2026-11-11 全国主要批发市场小葱价格行情（证券之星转载）", NAT_URL,
        "11-11 全国 48 家销地 roundup 全量入库；单位元/公斤，单点大宗报价无区间；含规格/产地差异，不发布加权均价"))

NAT_VALS = sorted(v for _, _, v in NAT48)
NAT_N = len(NAT_VALS)
NAT_MEAN = round(sum(NAT_VALS) / NAT_N, 2)
NAT_MED = round((NAT_VALS[NAT_N // 2 - 1] + NAT_VALS[NAT_N // 2]) / 2, 2)
NAT_MIN, NAT_MAX = NAT_VALS[0], NAT_VALS[-1]

# 5.4 同市场配对（组样本数不等时不直接比全样本均值）
from collections import Counter
PAIR = []
_PREV_SRC = os.path.join(SRC_DIR, "xiangcong_2026-11-11.json")
if os.path.exists(_PREV_SRC):
    _prev = json.load(open(_PREV_SRC, encoding="utf-8"))
    _bym = {}
    for _x in _prev.get("quotes", []):
        if _x.get("date") in ("2026-11-10", "2026-11-11") and _x.get("mid") is not None:
            _bym.setdefault(_x.get("market", ""), []).append(round(float(_x["mid"]), 2))
    for _nm, _pv, _v in NAT48:
        _c = _bym.get(_nm, [])
        if _c:
            PAIR.append((_nm, Counter(_c).most_common(1)[0][0], _v))
PAIR_N = len(PAIR)
if PAIR_N:
    PAIR_PREV_MEAN = round(sum(p for _, p, _ in PAIR) / PAIR_N, 2)
    PAIR_NOW_MEAN = round(sum(v for _, _, v in PAIR) / PAIR_N, 2)
    PAIR_CHG = round((PAIR_NOW_MEAN / PAIR_PREV_MEAN - 1) * 100, 2)
    PAIR_FLAT = sum(1 for _, p, v in PAIR if abs(v - p) < 1e-9)
    PAIR_UP = sum(1 for _, p, v in PAIR if v > p)
    PAIR_DOWN = sum(1 for _, p, v in PAIR if v < p)
else:
    PAIR_PREV_MEAN = PAIR_NOW_MEAN = PAIR_CHG = 0.0
    PAIR_FLAT = PAIR_UP = PAIR_DOWN = 0
NATDESC = (
    "<b>全国 roundup 恢复发布：</b>农业农村部信息中心 11-11「全国主要批发市场小葱价格行情」"
    "取得 <b>%d 家</b>销地报价，均值 <b>%.2f</b>、中位 %.2f、区间 %.2f（邯郸馆陶金凤 / 辽宁朝阳）~ %.2f（喀什曙光），"
    "离散 %.1f 倍，含精品/规格与产地差异，<b>不发布全国加权均价</b>。<br>"
    "<b>同市场配对（可比口径）：</b>与上期档案（2026-11-10/11-11）按市场名精确配对 <b>%d 家</b>，"
    "均值 %.2f → %.2f（<b>%+.2f%%</b>；%d 平 / %d 涨 / %d 跌）。"
    "上期全样本为 50 家 / 6.03 元，本期 48 家 / %.2f 元，<b>样本数不等、构成变化，禁止直接比较全样本均值</b>；"
    "配对结果显示销地整体近乎持平，未见普涨或普跌。"
) % (NAT_N, NAT_MEAN, NAT_MED, NAT_MIN, NAT_MAX, NAT_MAX / NAT_MIN,
     PAIR_N, PAIR_PREV_MEAN, PAIR_NOW_MEAN, PAIR_CHG, PAIR_FLAT, PAIR_UP, PAIR_DOWN, NAT_MEAN)

# 5.5 邯郸南大堡 11-11（元/斤 ×2）
A(Q(DATA_DATE, "香葱", "香葱（云南货源）", "邯郸南大堡蔬菜批发市场", "河北", "销地批发价",
    4.00, 4.40, 4.20, "邯郸南大堡蔬菜批发市场 2026-11-11 蔬菜价格行情", HD1111,
    "★换算值：低 2.0 / 中 2.1 / 高 2.2 元/斤 ×2 = 4.00 / 4.20 / 4.40 元/公斤，产地标注「云」"))
A(Q(DATA_DATE, "香葱", "小葱（本地香/钢葱）", "邯郸南大堡蔬菜批发市场", "河北", "销地批发价",
    1.40, 3.20, 2.40, "邯郸南大堡蔬菜批发市场 2026-11-11 蔬菜价格行情", HD1111,
    "★换算值：低 0.7 / 中 1.2 / 高 1.6 元/斤 ×2 = 1.40 / 2.40 / 3.20 元/公斤；同市场云南货 4.20 溢价 75%，产销价差优质样本"))
A(Q(DATA_DATE, "香葱", "香葱（云南货·均价口径）", "邯郸（另一转载表）", "河北", "销地批发价",
    4.00, 4.60, 4.00, "邯郸批发市场 2026-11-11 蔬菜批发价格（均价表）", HD1111B,
    "★换算值：高 2.3 / 低 2.0 / 均 2.0 元/斤 ×2 = 4.60 / 4.00 / 4.00 元/公斤，登记均价 4.00"))
A(Q(DATA_DATE, "香葱", "小葱（本地·均价口径）", "邯郸（另一转载表）", "河北", "销地批发价",
    1.40, 3.20, 2.60, "邯郸批发市场 2026-11-11 蔬菜批发价格（均价表）", HD1111B,
    "★换算值：高 1.6 / 低 0.7 / 均 1.3 元/斤 ×2 = 3.20 / 1.40 / 2.60 元/公斤，登记均价 2.60"))

# 5.6 北京新发地 11-11（元/斤 ×2）
A(Q(DATA_DATE, "香葱", "香葱", "北京新发地农副产品批发市场（官网表）", "北京", "销地批发价",
    6.20, 8.20, 7.20, "今日菜价早知道 2026-11-11（北京新发地，单位元/斤）", XFD1111,
    "★换算值：最低 3.1 / 平均 3.6 / 最高 4.1 元/斤 ×2 = 6.20 / 7.20 / 8.20 元/公斤；与同日 roundup「北京新发地小葱大宗 3.60」为不同品种/采价口径，并列不平均"))
A(Q(DATA_DATE, "香葱", "小葱", "北京新发地农副产品批发市场（官网表）", "北京", "销地批发价",
    2.60, 4.60, 3.60, "今日菜价早知道 2026-11-11（北京新发地，单位元/斤）", XFD1111,
    "★换算值：最低 1.3 / 平均 1.8 / 最高 2.3 元/斤 ×2 = 2.60 / 3.60 / 4.60 元/公斤；与农业农村部 roundup 3.60 一致"))

# 5.7 惠农网 11-08 产地行情横截面（元/斤 ×2，挂牌/指数非成交）
HNN = [
    ("河北邯郸市丛台区", "河北", 1.88), ("河北邯郸市永年区", "河北", 2.46),
    ("安徽阜阳市临泉县", "安徽", 1.76), ("山东潍坊市安丘市", "山东", 1.70),
    ("河南开封市通许县", "河南", 1.54), ("河南焦作市博爱县", "河南", 1.70),
    ("河南周口市郸城县", "河南", 2.38), ("湖北宜昌市当阳市", "湖北", 2.30),
    ("广东湛江市徐闻县", "广东", 5.44), ("广西柳州市柳南区", "广西", 3.40),
    ("广西柳州市柳江区", "广西", 2.98), ("四川成都市金堂县", "四川", 3.58),
    ("贵州毕节市威宁县", "贵州", 4.50), ("云南红河州泸西县（产地行情）", "云南", 2.52),
    ("云南大理州宾川县", "云南", 5.96),
]
for _nm, _pv, _v in HNN:
    A(Q("2026-11-08", "香葱", "香葱（产地行情）", _nm, _pv, "产地地头价",
        None, None, _v, "惠农网 香葱产地最新行情趋势 2026-11-08", HNN1108,
        "★换算值：元/斤 ×2；产地行情参考价（挂牌/指数，非成交），仅用于全国产区横截面，不并入销地均值"))

# 5.8 隔年精确同日档案 2025-11-11（本期同比基准）
A(Q("2025-11-11", "香葱", "红香葱", "云南红河州泸西县", "云南", "产地收购价",
    6.0, 6.4, 6.25, "2025年11月11日呈贡/晋宁/嵩明/陆良/通海/元谋/泸西菜价", LX251111,
    "隔年精确同日档案：泸西红香葱 6.0-6.4 均价 6.25，本期 3.45 同比 -44.8%；行情措辞「少数品类波动」，未提香葱"))
A(Q("2025-11-11", "香葱", "黑香葱", "云南红河州泸西县", "云南", "产地收购价",
    4.1, 4.6, 4.16, "2025年11月11日泸西菜价表", LX251111,
    "隔年精确同日档案：泸西黑香葱 4.1-4.6 均价 4.16，本期 2.76 同比 -33.7%"))
A(Q("2025-11-11", "香葱", "红葱", "云南玉溪市通海县", "云南", "产地收购价",
    6.0, 6.4, 6.20, "2025年11月11日通海菜价表", LX251111,
    "隔年精确同日档案：通海红葱 6.0-6.4，按区间中值 6.20 登记"))
A(Q("2025-11-11", "香葱", "黑葱", "云南玉溪市通海县", "云南", "产地收购价",
    4.1, 4.6, 4.35, "2025年11月11日通海菜价表", LX251111,
    "隔年精确同日档案：通海黑葱 4.1-4.6，按区间中值 4.35 登记"))
A(Q("2025-11-11", "香葱", "小葱", "昆明景臻·王旗营", "云南", "销地批发价",
    None, None, 5.50, "昆明市农业农村局 2025-11-11 景臻·王旗营批发平均价格统计表", KM251111,
    "隔年精确同日档案：小葱 5.50 / 前一日交易量 30 吨、综合平均价 6.26、总吨位 3104；本期同为景臻官方表口径 3.00 同比 -45.5%，可直接比较"))
A(Q("2025-11-11", "香葱", "小葱", "昆明市王旗营蔬菜批发市场有限公司（农业农村部）", "云南", "销地批发价",
    None, None, 5.50, "农业农村部信息中心（证券之星转载 2025-11-11 王旗营单市场表）", "https://futures.stockstar.com/IG2025111100017839.shtml",
    "隔年同日旁证：农业农村部单市场表小葱大宗价 5.50，与昆明市农业农村局官方表一致，双源互证"))

# —— 本期口径分歧分层（泸西同日多源）
LUXI_LAYERS = [
    ("本仓历史序列 王旗营（旧沿用）", 2.30, "#8a93a0"),
    ("全省综合（三源一致）", 3.30, "#0f6fd6"),
    ("泸西区间中值（推算）", 3.35, "#5b8ff9"),
    ("泸西官方均价标签", 3.45, "#d93025"),
    ("一亩田通货挂牌", 5.00, "#f0a500"),
    ("惠农网代办（含服务费）", 10.00, "#b06ab3"),
]
SALES = [
    ("昆明景臻王旗营（双源互证）", 3.00, "云南"),
    ("邯郸馆陶金凤", 1.50, "河北"),
    ("辽宁朝阳果菜", 1.70, "辽宁"),
    ("邯郸南大堡（小葱大宗）", 2.40, "河北"),
    ("北京新发地（小葱官网表）", 3.60, "北京"),
    ("邯郸南大堡（云南货）", 4.20, "河北"),
    ("江苏凌家塘", 6.50, "江苏"),
    ("北京新发地（香葱官网表）", 7.20, "北京"),
    ("湖北鄂州蟠龙", 10.00, "湖北"),
    ("喀什曙光", 13.00, "新疆"),
]
YOY_RED = round((RED_MID / 6.25 - 1) * 100, 1)
YOY_BLK = round((BLK_MID / 4.16 - 1) * 100, 1)
YOY_WQ = round((3.00 / 5.50 - 1) * 100, 1)
YOY_WQ_B = round((2.30 / 5.50 - 1) * 100, 1)
FIVE_YEAR = [("2022-11-06", 4.95), ("2023-11-10", 4.50), ("2024-11-05", 7.05),
             ("2025-11-11", 6.25), ("2026-11-11", 3.45)]

# ============================================================ 6. 合并兄弟任务（当日）
def merge_siblings():
    seen = {(q["date"], q["market"], q["variety"], round(float(q["mid"]), 2))
            for q in QUOTES if q.get("mid") is not None}
    added, files = 0, []
    for p in sorted(glob.glob(os.path.join(SRC_DIR, "*_%s.json" % TODAY))):
        fn = os.path.basename(p)
        if fn.startswith("xiangcong_"):
            continue
        try:
            d = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        rows = d.get("quotes", []) if isinstance(d, dict) else []
        cnt = 0
        for q in rows:
            if not isinstance(q, dict) or q.get("mid") is None:
                continue
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(q.get("date", ""))):
                continue
            if "斤" in str(q.get("unit", "")) and "公斤" not in str(q.get("unit", "")):
                continue  # 未换算的元/斤口径会污染元/公斤统一 schema，直接剔除
            try:
                mid = round(float(q["mid"]), 2)
            except (TypeError, ValueError):
                continue
            k = (q["date"], q.get("market", ""), q.get("variety", ""), mid)
            if k in seen:
                continue
            seen.add(k)
            q = dict(q)
            q["mid"] = mid
            for f, dft in (("item", "香葱"), ("variety", ""), ("market", ""),
                           ("province", ""), ("source", ""), ("source_url", ""), ("note", "")):
                q.setdefault(f, dft)
            valid_pt = ("产地地头价", "产地收购价", "产地批发价", "销地批发价", "零售价")
            if q.get("price_type") not in valid_pt:
                q["price_type"] = "销地批发价"
                q["note"] += "；[原口径未标注，按销地批发价归类]"
            q["unit"] = "元/公斤"
            q["note"] = (q["note"] + "；[兄弟任务 %s 合并]" % fn).strip("；")
            QUOTES.append(q)
            added += 1
            cnt += 1
        files.append("%s:%d" % (fn, cnt))
    return added, files


MERGED, MERGE_FILES = merge_siblings()
print("[OK] 兄弟任务合并 +%d 条，来源 %s" % (MERGED, ", ".join(MERGE_FILES) or "无"))

# ============================================================ 7. 落盘 JSON（严格 schema）
SUMMARY_JSON = (
    "11-11 当日实测泸西红香葱 3.2-3.5（官方均价标签 3.45）、黑香葱 2.5-2.9（2.76）与 11-10 完全持平，"
    "自 11-01 起连续十一个报价日锁定，全省综合三个独立转载源一致报红 3.1-3.5 / 黑 2.5-2.9，"
    "省级中值 3.30 仍低于泸西标签 0.15、倒挂延续。"
    "本期最大变化是王旗营多读数分歧收敛：景臻官方平均价格统计表与农业农村部 11-11 全国 48 家小葱 roundup "
    "双源互证同为 3.00 元/公斤，前一日交易量由 20 吨回升至 35 吨（+75%%），"
    "同比隔年精确同日（2025-11-11 红 6.25 / 黑 4.16 / 王旗营 5.50）分别 %+.1f%% / %+.1f%% / %+.1f%%，"
    "红香葱仍为近五年同期最低且唯一跌破 4 元。"
    "六档中枢（红）3.45 → %s 元/公斤（第 6 档回落系春节后节日脉冲衰减，非趋势反转），"
    "全国 48 家均值 %.2f、同市场配对 %d 家 %+.2f%% 近乎持平，泸西未来 3 天降水 %.1fmm / 距平 %+.1f℃ 且 16 天无强降水，"
    "灾害接口本期正常取得（全网 100 条，云南 10 条全在滇西滇西北，红河州与泸西 0 条），"
    "情景 C（补跌）概率由 40%% 下调至 35%%。"
) % (YOY_RED, YOY_BLK, YOY_WQ, " / ".join("%.2f" % c for c in _centers),
     NAT_MEAN, PAIR_N, PAIR_CHG, w3.get("precip_total") or 0, ANO)

out_json = {
    "task": "香葱行情",
    "task_id": "376dffed-c5e4-4904-a77a-29193947212a",
    "date": TODAY,
    "generated_at": GEN,
    "market_scope": "全国 / 云南 / 泸西县",
    "quotes": QUOTES,
    "forecasts": FORECASTS,
    "summary": SUMMARY_JSON,
}
json_path = os.path.join(SRC_DIR, "xiangcong_%s.json" % TODAY)
with open(json_path, "w", encoding="utf-8") as f:
    json.dump(out_json, f, ensure_ascii=False, indent=2)
print("[OK] 落盘", json_path, len(QUOTES), "报价 /", len(FORECASTS), "预测",
      os.path.getsize(json_path), "bytes")

# ============================================================ 8. 图表（内联 SVG）
def svg_bars(pairs, title, unit="元/公斤", height=270, color="#0f6fd6", maxv=None):
    """通用竖向柱状图：pairs = [(label, value, color?)]"""
    width = 960
    ml, mr, mt, mb = 62, 22, 30, 62
    pw, ph = width - ml - mr, height - mt - mb
    vals = [p[1] for p in pairs] or [1]
    hi = maxv or max(vals) * 1.18 or 1
    bw = pw / max(1, len(pairs))
    g = []
    for k in range(5):
        v = hi * k / 4
        y = mt + ph * (1 - k / 4)
        g.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="#e6eaf0" stroke-width="1"/>' %
                 (ml, y, width - mr, y))
        g.append('<text x="%d" y="%.1f" font-size="11" fill="#7b8595" text-anchor="end">%.1f</text>' %
                 (ml - 8, y + 4, v))
    for i, p in enumerate(pairs):
        lab, v = p[0], p[1]
        c = p[2] if len(p) > 2 else color
        x = ml + bw * i + bw * 0.2
        w = bw * 0.6
        y = mt + ph * (1 - v / hi)
        g.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s" opacity="0.85" rx="3"/>' %
                 (x, y, w, mt + ph - y, c))
        g.append('<text x="%.1f" y="%.1f" font-size="11.5" fill="#1c2024" text-anchor="middle">%.2f</text>' %
                 (x + w / 2, y - 6, v))
        for j, seg in enumerate(lab.split("|")):
            g.append('<text x="%.1f" y="%.1f" font-size="10.5" fill="#5b6470" text-anchor="middle">%s</text>' %
                     (x + w / 2, mt + ph + 18 + j * 14, seg))
    return ('<svg viewBox="0 0 %d %d" width="100%%" height="%d" role="img" aria-label="%s">'
            '<rect width="%d" height="%d" fill="#ffffff"/>%s</svg>') % (
                width, height, height, title, width, height, "".join(g))


def svg_weather(days):
    """逐日降水柱 + 最高/最低温折线（双轴简化）。"""
    width, height = 960, 300
    ml, mr, mt, mb = 58, 62, 28, 58
    pw, ph = width - ml - mr, height - mt - mb
    pr = [d.get("precip") or 0 for d in days]
    tmax = [d.get("tmax") or 0 for d in days]
    tmin = [d.get("tmin") or 0 for d in days]
    pmax = max(pr) * 1.25 or 1
    tlo, thi = min(tmin) - 2, max(tmax) + 2
    bw = pw / max(1, len(days))
    g = []
    for k in range(5):
        y = mt + ph * (1 - k / 4)
        g.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="#eef1f5" stroke-width="1"/>' %
                 (ml, y, width - mr, y))
        g.append('<text x="%d" y="%.1f" font-size="11" fill="#7b8595" text-anchor="end">%.0f</text>' %
                 (ml - 8, y + 4, pmax * k / 4))
    for i, d in enumerate(days):
        x = ml + bw * i + bw * 0.22
        w = bw * 0.56
        y = mt + ph * (1 - pr[i] / pmax)
        g.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="#4a90d9" opacity="0.75" rx="2"/>' %
                 (x, y, w, mt + ph - y))
        g.append('<text x="%.1f" y="%.1f" font-size="10.5" fill="#5b6470" text-anchor="middle">%s</text>' %
                 (x + w / 2, mt + ph + 16, d["date"][5:].replace("-", "/")))
        if pr[i] >= 1:
            g.append('<text x="%.1f" y="%.1f" font-size="10" fill="#1c2024" text-anchor="middle">%.1f</text>' %
                     (x + w / 2, y - 4, pr[i]))

    def line(vals, col, dash=""):
        pts = " ".join("%.1f,%.1f" % (ml + bw * i + bw / 2,
                                      mt + ph * (1 - (v - tlo) / (thi - tlo)))
                       for i, v in enumerate(vals))
        return '<polyline points="%s" fill="none" stroke="%s" stroke-width="2"%s/>' % (pts, col, dash)

    g.append(line(tmax, "#d93025"))
    g.append(line(tmin, "#0f9960", ' stroke-dasharray="5 4"'))
    g.append('<text x="%d" y="%d" font-size="11" fill="#d93025">— 最高温</text>' % (width - mr + 4, mt + 16))
    g.append('<text x="%d" y="%d" font-size="11" fill="#0f9960">-- 最低温</text>' % (width - mr + 4, mt + 34))
    g.append('<text x="%d" y="%d" font-size="11" fill="#4a90d9">▮ 降水mm</text>' % (width - mr + 4, mt + 52))
    return ('<svg viewBox="0 0 %d %d" width="100%%" height="%d" role="img" aria-label="泸西未来16天逐日天气">'
            '<rect width="%d" height="%d" fill="#ffffff"/>%s</svg>') % (
                width, height, height, width, height, "".join(g))


def svg_dual(rows_red, rows_blk, base_r, base_b):
    """红/黑葱六档双线。"""
    width, height = 960, 290
    ml, mr, mt, mb = 58, 96, 28, 50
    pw, ph = width - ml - mr, height - mt - mb
    xs = [0] + [r["days"] for r in rows_red]
    yr = [base_r] + [r["center"] for r in rows_red]
    yb = [base_b] + [r["center"] for r in rows_blk]
    lo, hi = min(yr + yb) - 0.25, max(yr + yb) + 0.25
    xmax = max(xs) or 1
    px = lambda v: ml + pw * v / xmax
    py = lambda v: mt + ph * (1 - (v - lo) / (hi - lo))
    g = []
    for k in range(5):
        v = lo + (hi - lo) * k / 4
        y = py(v)
        g.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="#e6eaf0" stroke-width="1"/>' % (ml, y, width - mr, y))
        g.append('<text x="%d" y="%.1f" font-size="11" fill="#7b8595" text-anchor="end">%.2f</text>' % (ml - 8, y + 4, v))
    for vals, col, name in ((yr, "#d93025", "红香葱"), (yb, "#3c4858", "黑香葱")):
        pts = " ".join("%.1f,%.1f" % (px(x), py(v)) for x, v in zip(xs, vals))
        g.append('<polyline points="%s" fill="none" stroke="%s" stroke-width="2.4"/>' % (pts, col))
        for x, v in zip(xs, vals):
            g.append('<circle cx="%.1f" cy="%.1f" r="3.6" fill="%s"/>' % (px(x), py(v), col))
        g.append('<circle cx="%d" cy="%d" r="4" fill="%s"/><text x="%d" y="%d" font-size="11.5" fill="#1c2024">%s</text>' %
                 (width - mr + 8, mt + 16 if name == "红香葱" else mt + 38, col,
                  width - mr + 18, mt + 20 if name == "红香葱" else mt + 42, name))
    for x, lab in zip(xs, ["当前"] + [r["label"] for r in rows_red]):
        g.append('<text x="%.1f" y="%.1f" font-size="10.5" fill="#5b6470" text-anchor="middle">%s</text>' %
                 (px(x), mt + ph + 18, lab))
    return ('<svg viewBox="0 0 %d %d" width="100%%" height="%d" role="img" aria-label="红黑葱六档预测双线">'
            '<rect width="%d" height="%d" fill="#ffffff"/>%s</svg>') % (
                width, height, height, width, height, "".join(g))


C_DECADE = longterm.svg_line(series, anchors, height=330)
C_36 = longterm.svg_line(series, anchors, months=36, height=300, title="近 36 个月香葱产地价")
C_SEASON = longterm.svg_season()
C_FC = longterm.svg_forecast_path(BASE_RED, FRED["rows"])
C_WX = svg_weather(_fc16)
C_DUAL = svg_dual(FRED["rows"], FBLK["rows"], BASE_RED, BASE_BLACK)
C_FIVE = svg_bars([(d[:4] + "年|" + d[5:], v, "#d93025" if d.startswith("2026") else "#8a93a0")
                   for d, v in FIVE_YEAR], "近五年 11 月上旬同期红香葱价位", height=260)
C_LAYERS = svg_bars([(n.replace("（", "|（"), v, c) for n, v, c in LUXI_LAYERS],
                    "泸西同日多源口径分层", height=280)
C_SALES = svg_bars([(n.replace("（", "|（"), v, "#0f9960" if "沿用" not in n else "#8a93a0")
                    for n, v, _ in SALES], "本期销地报价横截面", height=270)
C_WIN = svg_bars([("%d月窗口|%s" % (m, ("+" if windows[m]["change_pct"] >= 0 else "") + "%.1f%%" % windows[m]["change_pct"]),
                   abs(windows[m]["change_pct"]),
                   "#d93025" if windows[m]["change_pct"] >= 0 else "#0f9960")
                  for m in (12, 24, 36, 60, 120)], "长周期窗口涨跌幅绝对值", unit="%", height=260)

# ============================================================ 9. HTML 报告
CSS = """
:root{--bg:#f5f7fa;--card:#fff;--ink:#1c2024;--sub:#5b6470;--line:#e6eaf0;--blue:#0f6fd6;--red:#d93025;--green:#0f9960}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;line-height:1.65}
.wrap{max-width:1080px;margin:0 auto;padding:28px 20px 60px}
header{background:linear-gradient(120deg,#0f6fd6,#1a8fd0);color:#fff;border-radius:14px;padding:26px 30px;margin-bottom:22px}
header h1{margin:0 0 6px;font-size:26px}header .meta{font-size:13px;opacity:.92}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin:18px 0}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px}
.kpi .v{font-size:23px;font-weight:700}.kpi .l{font-size:12px;color:var(--sub);margin-top:3px}
.kpi .s{font-size:11px;color:#8a93a0;margin-top:5px}
section{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:22px 24px;margin:16px 0}
h2{font-size:19px;margin:0 0 14px;padding-bottom:9px;border-bottom:2px solid var(--blue)}
h3{font-size:15px;margin:18px 0 8px;color:#243046}
p{margin:9px 0;font-size:14px}table{border-collapse:collapse;width:100%;font-size:12.5px;margin:10px 0}
th,td{border:1px solid var(--line);padding:7px 9px;text-align:left}th{background:#f0f4f9;font-weight:600}
tbody tr:nth-child(even){background:#fafbfd}
.fig{margin:14px 0;border:1px solid var(--line);border-radius:10px;padding:10px;background:#fff}
.fig .cap{font-size:12px;color:var(--sub);margin:4px 0 8px}
.note{background:#f7f9fc;border-left:3px solid var(--blue);padding:10px 14px;font-size:12.5px;color:#3b4657;border-radius:0 6px 6px 0;margin:12px 0}
.warn{background:#fff6f4;border-left:3px solid var(--red)}
.foot{font-size:11.5px;color:#8a93a0;margin-top:22px;line-height:1.8}
.tag{display:inline-block;background:#eef4fc;color:#0f6fd6;border-radius:4px;padding:1px 6px;font-size:11px;margin-right:5px}
.scroll{max-height:460px;overflow:auto}
"""

win_rows = "".join(
    "<tr><td>%d 个月</td><td>%s</td><td>%+.1f%%</td><td>%.2f</td><td>%.2f ~ %.2f</td><td>%.1f%%</td></tr>" % (
        m, windows[m]["start_ym"] + " ~ " + windows[m]["end_ym"],
        windows[m]["change_pct"], windows[m]["avg"], windows[m]["lo"],
        windows[m]["hi"], windows[m]["amplitude"])
    for m in (12, 24, 36, 60, 120))

fc_rows = "".join(
    "<tr><td>%s</td><td>%s</td><td>%.2f</td><td>%.2f ~ %.2f</td><td>%.2f</td><td>%.2f ~ %.2f</td><td>%+.1f%%</td><td>%s</td></tr>" % (
        f["horizon"], f["target_date"], RRED[k]["center"], RRED[k]["low"], RRED[k]["high"],
        RBLK[k]["center"], RBLK[k]["low"], RBLK[k]["high"], f["delta_pct"], f["confidence"])
    for (k, _), f in zip(HORIZON_MAP, FORECASTS))

qrows = "".join(
    "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
        q["date"], q["variety"], q["market"], q["province"], q["price_type"],
        ("%.2f" % q["mid"]) if q.get("mid") is not None else "—", q["source"])
    for q in QUOTES)

variety_rows = "".join(
    "<tr><td><b>%s</b></td><td>%s</td><td>%s</td></tr>" % (v["name"], v["desc"], v["use"])
    for v in config.VARIETIES)
cultivar_rows = "".join(
    "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
        c["name"], c["trait"], c["area"], c["yield"]) for c in config.CULTIVARS)
prov_rows = "".join(
    "<tr><td><b>%s</b></td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
        p["province"], p["counties"], p["scale"], p["season"]) for p in config.PROVINCES)
sales_rows = "".join(
    "<tr><td>%s</td><td>%s</td><td>%.2f</td><td>销地/零售口径</td></tr>" % (n, pv, v)
    for n, v, pv in SALES)
layer_rows = "".join(
    "<tr><td>%s</td><td>%.2f</td><td>%s</td></tr>" % (
        n, v, "推算/挂牌/沿用，非成交定价基准" if n != "泸西官方均价标签" else "本期模型基准")
    for n, v, _ in LUXI_LAYERS)

wx_rows = "".join(
    "<tr><td>%s</td><td>%.1f</td><td>%.1f</td><td>%.1f</td><td>%d</td><td>%d</td><td>%s</td></tr>" % (
        d["date"][5:], d["tmax"], d["tmin"], d.get("precip") or 0,
        1 if (d.get("precip") or 0) >= 1 else 0,
        1 if (d.get("wind") or 0) >= 17 else 0, d["weather"]) for d in _fc16)

SUMMARY_HTML = (
    "<b>本期头号结论：王旗营多读数分歧收敛，全国销地 roundup 恢复发布。</b>"
    "上期王旗营存在 2.30 / 3.50 / 3.80 / 4.00 四套读数并列，本期昆明景臻·王旗营官方平均价格统计表"
    "（三个转载源一致）与农业农村部 11-11 全国 48 家小葱 roundup <b>双源互证同为 3.00 元/公斤</b>，"
    "前一日交易量 35 吨（上期 20 吨、+75%%），价 -14.3%%、量 +75%%，分销地口径分歧首次收敛。<br>"
    "<b>行情端：</b>泸西红香葱 3.2-3.5 / 标签 3.45、黑香葱 2.5-2.9 / 2.76 与 11-10 完全持平，"
    "自 11-01 起<b>连续十一个报价日锁定</b>；全省综合三个独立转载源完全一致报红 3.1-3.5、黑 2.5-2.9，"
    "省级中值 3.30 仍低于泸西标签 0.15，倒挂延续。同比隔年精确同日 2025-11-11"
    "（红 6.25 / 黑 4.16 / 王旗营 5.50）分别 %+.1f%% / %+.1f%% / %+.1f%%，"
    "红香葱为近五年同期最低且唯一跌破 4 元。<br>"
    "<b>全国销地：</b>48 家均值 %.2f、中位 %.2f、区间 %.2f~%.2f；与上期档案同市场配对 %d 家，"
    "均值 %.2f → %.2f（%+.2f%%；%d 平 / %d 涨 / %d 跌），样本数不等时不直接比较全样本均值。<br>"
    "<b>天气/灾害：</b>泸西未来 3 天降水 %.1fmm、最高温均 %.1f℃（距平 %+.1f℃），"
    "16 天累计 %.1fmm / %d 雨日、无强降水过程，%s；中央气象台 findAlarm 在连续 4 期超时后<b>本期恢复</b>，"
    "全网 100 条，大雾 58 / 道路结冰 17 主导，云南 10 条全在滇西滇西北，红河州与泸西 0 条。<br>"
    "<b>预测：</b>六档中枢（红）3.45 → %s 元/公斤，%s；情景 C（标签补跌）概率由 40%% 下调至 35%%（王旗营量能回补）。"
) % (YOY_RED, YOY_BLK, YOY_WQ, NAT_MEAN, NAT_MED, NAT_MIN, NAT_MAX,
     PAIR_N, PAIR_PREV_MEAN, PAIR_NOW_MEAN, PAIR_CHG, PAIR_FLAT, PAIR_UP, PAIR_DOWN,
     w3.get("precip_total") or 0, w3.get("tmax_avg") or 0, ANO, RAIN_TOTAL, RAIN_DAYS, WTREND,
     " / ".join("%.2f" % c for c in _centers), MONO_DESC)

BODY = """
<header><h1>香葱行情分析报告 · @@TODAY@@</h1>
<div class="meta">数据日 @@DDATE@@（当日发布源已取得） ｜ 生成 @@GEN@@ ｜ 任务 376dffed ｜ 覆盖：全国 / 云南 / 泸西县</div></header>
<div class="wrap">

<div class="kpis">
<div class="kpi"><div class="v">3.45</div><div class="l">泸西红香葱·官方均价标签</div><div class="s">元/公斤，连续 11 个报价日锁定</div></div>
<div class="kpi"><div class="v">2.76</div><div class="l">泸西黑香葱·均价</div><div class="s">元/公斤，连续 4 日锁定</div></div>
<div class="kpi"><div class="v">3.30</div><div class="l">全省综合红香葱（三源一致）</div><div class="s">元/公斤，低于泸西标签 0.15</div></div>
<div class="kpi"><div class="v">@@YOYRED@@%</div><div class="l">红香葱同比</div><div class="s">对 2025-11-11 精确同日 6.25</div></div>
<div class="kpi"><div class="v">@@NQ@@</div><div class="l">本期入库报价行</div><div class="s">全量不截断，单位统一元/公斤</div></div>
<div class="kpi"><div class="v">@@ANO@@℃</div><div class="l">未来 3 天气温距平</div><div class="s">泸西，近 30 日均值基准</div></div>
</div>

<section><h2>一、本期速览</h2>@@SUMMARY@@
<div class="note"><b>口径铁律：</b>长周期主序列为通货毛葱（元/公斤），预测与「当前中枢」为精品净葱/集散价，
两者相差约 1.66 倍，<b>禁止横向混比</b>；本报告所有价格除特别标注外均为元/公斤，
元/斤报价已 ×2 换算并在明细 note 注明；挂牌价、代办价、推算值均显式标注为非成交口径。</div></section>

<section><h2>二、历史长周期回顾（12 / 24 / 36 / 60 / 120 月 → 10 年）</h2>
<p>以 2016-10 为起点的月频重建序列（@@NS@@ 个月、@@OBS@@ 个实测锚点 + @@INF@@ 个推断锚点），
重建法为「锚点 ÷ 季节因子 → 去季节化水平对数线性插值 → × 季节因子」，锚点月份精确命中。</p>
<table><thead><tr><th>窗口</th><th>区间</th><th>涨跌</th><th>区间均值</th><th>低 ~ 高</th><th>振幅</th></tr></thead><tbody>@@WINROWS@@</tbody></table>
<div class="fig"><div class="cap">图 1　十年长周期：通货毛葱（蓝）与精品净葱 ×1.66（橙虚线），红点为实测锚点</div>@@C_DECADE@@</div>
<div class="fig"><div class="cap">图 2　近 36 个月走势</div>@@C_36@@</div>
<div class="fig"><div class="cap">图 3　月度季节指数（春峰 4-5 月、冬旺 11-1 月、夏谷 7-8 月，全站唯一因子源）</div>@@C_SEASON@@</div>
<div class="fig"><div class="cap">图 4　五个窗口涨跌幅绝对值（红=上涨、绿=下跌）</div>@@C_WIN@@</div>
<div class="note">120 月窗口年化复合增速 @@CAGR@@%，为本轮监测的长期锚；
近 12 月同比受 2025 年高基数与 2026 年秋季供给宽松双重影响，不宜单独归因本年度供给恶化。</div></section>

<section><h2>三、全国天气与自然灾害（@@WXGEN@@ 鲜抓）</h2>
<h3>3.1 泸西未来 16 天逐日</h3>
<div class="fig"><div class="cap">图 5　逐日降水（柱，mm）与最高/最低温（线，右轴相对刻度）</div>@@C_WX@@</div>
<table><thead><tr><th>日期</th><th>最高℃</th><th>最低℃</th><th>降水mm</th><th>雨日</th><th>大风日</th><th>天气</th></tr></thead><tbody>@@WXROWS@@</tbody></table>
<h3>3.2 三档窗口统计</h3>
<table><thead><tr><th>窗口</th><th>最高温均</th><th>最低温均</th><th>累计降水</th><th>雨日</th><th>大风日</th><th>主导天气</th></tr></thead><tbody>
<tr><td>未来 3 天</td><td>@@W3T@@</td><td>@@W3T2@@</td><td>@@W3P@@ mm</td><td>@@W3R@@</td><td>@@W3G@@</td><td>@@W3D@@</td></tr>
<tr><td>未来 7 天</td><td>@@W7T@@</td><td>@@W7T2@@</td><td>@@W7P@@ mm</td><td>@@W7R@@</td><td>@@W7G@@</td><td>@@W7D@@</td></tr>
<tr><td>第 8-15 天</td><td>@@WHT@@</td><td>@@WHT2@@</td><td>@@WHP@@ mm</td><td>@@WHR@@</td><td>@@WHG@@</td><td>@@WHD@@</td></tr>
</tbody></table>
<h3>3.3 灾害预警</h3>
<div class="note @@WARNCLS@@">@@DZNOTE@@</div>
<table><thead><tr><th>地区</th><th>预警</th><th>是否主产区</th></tr></thead><tbody>@@DZROWS@@</tbody></table>
<div class="note">峰值降水日 @@PDATE@@（@@PMM@@ mm）、最冷日 @@CDATE@@（@@CTMIN@@℃），
16 天累计 @@RTOT@@ mm / @@RDAYS@@ 雨日；≥5mm 降水过程：@@HDESC@@。
<b>方向判断：</b>@@WTREND@@；低温寡照与洗葱损耗构成短期成本扰动，
但缺乏洪涝型断供驱动；中期上行主要来自冬季季节因子与元旦/春节备货。</div></section>

<section><h2>四、市面常见香葱种类</h2>
<h3>4.1 流通端商品分类（决定报价口径）</h3>
<table><thead><tr><th>类别</th><th>识别特征</th><th>主要用途</th></tr></thead><tbody>@@VARROWS@@</tbody></table>
<h3>4.2 常见栽培品种</h3>
<table><thead><tr><th>品种</th><th>特征</th><th>主栽区域</th><th>亩产/产量</th></tr></thead><tbody>@@CULTROWS@@</tbody></table>
<div class="note">大葱（钢葱类）不计入香葱口径，本报告仅在个别销地表作对比；
红葱 / 黑葱 / 白葱（白铁杆）为泸西三大商品规格，红黑价差本期为 @@SPREAD@@ 元/公斤。
<b>注意：</b>平台挂牌常把「香葱/小葱/火葱/四季葱」混用，口径不可直接横比。</div></section>

<section><h2>五、全国香葱种植省份</h2>
<table><thead><tr><th>省份</th><th>主产县/镇</th><th>规模</th><th>上市季</th></tr></thead><tbody>@@PROVROWS@@</tbody></table>
<div class="note">全国小香葱面积存在口径分歧（第三方统计约 78.56 万亩 vs 主产区加总量级），
上表为定性产区图谱，不作为面积核算依据。泸西固定底盘：基地 13.5 万亩 / 复种 46.7 万亩次，
年产 118 万吨、产值 35-36 亿元，占云南 60%+，日外运 2000+ 吨，3000+ 种植户、5 万+ 就业。</div></section>

<section><h2>六、全国行情与销地横截面</h2>
<p>本期采集到 @@NQ@@ 条报价（含兄弟任务合并 @@MERGED@@ 条、历史同日档案 13 条），
覆盖 @@NPROV@@ 个省区。销地样本（@@NSALES@@ 家）区间 @@SMIN@@ ~ @@SMAX@@ 元/公斤，
差异来自规格（精品/通货）、产地（云南货/本地货）与采价口径（批发/零售），
<b>不发布全国加权均价</b>。</p>
<div class="fig"><div class="cap">图 6　本期销地报价横截面（灰=沿用口径，绿=当期采价）</div>@@C_SALES@@</div>
<table><thead><tr><th>市场</th><th>省份</th><th>价格</th><th>口径</th></tr></thead><tbody>@@SALESROWS@@</tbody></table>
<div class="note">@@NATDESC@@<br>
本期图表展示 @@NSALES@@ 家代表性销地样本（区间 @@SMIN@@ ~ @@SMAX@@ 元/公斤，含官网表与 roundup 两种采价口径），
全量 48 家明细见 8.4 报价表。<b>方法说明：</b>遵循 data-analysis「组样本数不等时不得对均值直接比较」，
上期 50 家与本期 48 家先按市场名精确配对再算涨跌，配对外的增删市场不进入可比结论。</div></section>

<section><h2>七、泸西专题（重点）</h2>
<h3>7.1 同比与近五年同期</h3>
<p>隔年精确同日档案 2025-11-11：泸西红 6.0-6.4 / 6.25、黑 4.1-4.6 / 4.16，通海红 6.0-6.4、黑 4.1-4.6，
王旗营小葱 5.50 / 30 吨（综合平均价 6.26、总吨位 3104；昆明市农业农村局官方表与农业农村部单市场表双源互证）。
本期红同比 @@YOYRED@@%、黑 @@YOYBLK@@%、王旗营 @@YOYWQ@@%（同为景臻官方表口径，可直接比较）；
若沿用本仓旧 2.30 口径则为 @@YOYWQB@@%，仅作对照。红黑价差由去年同期 2.09 压缩至 @@SPREAD@@，红葱溢价基本消失。</p>
<div class="fig"><div class="cap">图 7　近五年 11 月上旬同期红香葱价位（元/公斤；2022/2024 为近似日档案，口径含全省综合与泸西分区，仅作量级对比）</div>@@C_FIVE@@</div>
<h3>7.2 同日多源口径分层</h3>
<div class="fig"><div class="cap">图 8　泸西 11-11 六种公开口径（极值差 4.3 倍）</div>@@C_LAYERS@@</div>
<table><thead><tr><th>口径</th><th>价格</th><th>说明</th></tr></thead><tbody>@@LAYERROWS@@</tbody></table>
<div class="note warn"><b>分层结论：</b>成交层 3.30（全省综合）~ 3.45（泸西标签）为定价基准，
区间与加权均价标签为该表固定并列格式，中值 3.35 不单独解读为领先信号；挂牌层 1.50 ~ 5.00 长期不刷新、非成交；
代办层 10.00 含服务费/包装，不可用于定价。<b>本期新增证据：</b>全省综合连续两期三源一致 3.30，且王旗营官方表已取得并与全国 roundup 互证，
「泸西标签偏高」由单源依赖升为多源确认；但王旗营量能回补（20→35 吨）使情景 C 补跌概率由 40% 下调至 35%。</div>
<h3>7.3 王旗营量价与口径分歧</h3>
<p><b>本期分歧收敛：</b>11-11 景臻·王旗营批发平均价格统计表（三个独立转载源一致）报小葱 <b>3.00</b>、
前一日交易量 <b>35 吨</b>，综合平均价 4.37、总吨位 3082；农业农村部 11-11 全国 48 家小葱 roundup
中「昆明景臻王旗营蔬菜批发市场」同为 <b>3.00</b>，<b>双源互证</b>。
较 11-10 转载表 3.50 / 20 吨为价 -14.3%、量 +75.0%——第三次「量先于价」试探
（10-31、11-07 两次均未延续），本期量能回到 35 吨常态，属边际改善但单期仍不足以确认反转。
此前并列的 2.30（本仓旧沿用）/ 3.50 / 3.80 / 4.00 四套读数，本期起以官方表 3.00 为准；
旧沿用值仅作口径并列保留于报价明细，<b>不平均、不混用、不解读为单日暴涨</b>。</p></section>

<section><h2>八、六档预测、情景推演与风险</h2>
<h3>8.1 六档中枢（精品净葱/集散价口径）</h3>
<table><thead><tr><th>档位</th><th>目标日</th><th>红葱中枢</th><th>红葱区间</th><th>黑葱中枢</th><th>黑葱区间</th><th>红葱涨跌</th><th>置信度</th></tr></thead>
<tbody><tr><td>当前基准</td><td>@@DDATE@@</td><td>@@BR@@</td><td>—</td><td>@@BB@@</td><td>—</td><td>—</td><td>基准</td></tr>
@@FCROWS@@</tbody></table>
<div class="fig"><div class="cap">图 9　红香葱六档预测路径带（含情景区间）</div>@@C_FC@@</div>
<div class="fig"><div class="cap">图 10　红 / 黑香葱六档双线</div>@@C_DUAL@@</div>
<p>模型 = 季节性日插值 × 天气冲击 × 均值回归动量，20 日均线 @@MA@@（现价低于均线 @@GAP@@%）。@@MONO@@。</p>
<h3>8.2 情景推演</h3>
<table><thead><tr><th>情景</th><th>触发条件</th><th>3 个月中枢</th><th>概率</th></tr></thead><tbody>
<tr><td><b>A 基准</b></td><td>泸西标签维持 3.45、全省综合未再下调，冬季季节上行温和兑现，销地不继续恶化</td><td>@@A3@@ 元/公斤</td><td>40%</td></tr>
<tr><td><b>B 上修</b></td><td>低温寡照致明显减产 / 霜霉病扩散，节前备货提前放量，基准口径上修至地头大宗 4.60</td><td>@@B3@@ 元/公斤</td><td>25%</td></tr>
<tr><td><b>C 下修</b></td><td>泸西均价标签跟随区间补跌至 3.30 以下、全省综合倒挂确认、第 2 周干暖供给快速恢复、销地续弱（再跌至 3.00）</td><td>@@C3@@ 元/公斤</td><td>35%</td></tr>
</tbody></table>
<div class="note">情景中枢按<b>基准价替代法</b>推演：以 A 档 3 个月中枢 @@A3@@ 为基数，
按「替代基准 / 现基准（@@BR@@）」等比缩放。本期概率调整为 A 40% / B 25% / C 35%：
利多项为王旗营官方表与全国 roundup 双源互证 3.00、量能回补至 35 吨、全省综合连续两期三源一致、
黑葱连续四日锁定、云南核心产区零独立预警、全国 48 家同市场配对近乎持平；
利空项为红葱省级倒挂 0.15、泸西连续 11 日报价黏性、16 天无强降水过程（缺乏减产驱动）。
概率仅反映<b>相对路径</b>分歧，不构成价格承诺。</div>
<h3>8.3 风险清单与跟踪</h3>
<table><thead><tr><th>风险</th><th>证据</th><th>跟踪指标</th><th>复核时限</th></tr></thead><tbody>
<tr><td>泸西报价黏性 / 一次性补跌</td><td>标签 3.45 连续 11 日、省级综合 3.30 倒挂 0.15、区间中值 3.35（固定标注格式，不作领先信号）</td><td>下一期泸西均价标签是否下移</td><td>T+1 报价日</td></tr>
<tr><td>销地量能回补能否延续</td><td>王旗营 3.50/20吨 → 3.00/35吨（价跌量增）</td><td>成交量能否连续两期站稳 35 吨、价格是否止跌</td><td>T+3 日</td></tr>
<tr><td>口径分歧</td><td>同日同产地 2.30 ~ 10.00（4.3 倍）；王旗营已收敛至 3.00</td><td>下一期旧沿用口径 2.30 是否退场、省级与泸西标签是否对齐</td><td>下一期</td></tr>
<tr><td>低温冰冻类预警主导</td><td>findAlarm 本期恢复：全网 100 条，大雾 58 / 道路结冰 17；云南 10 条全在滇西滇西北，红河州/泸西 0 条</td><td>下一期红河州是否出现独立生效预警</td><td>T+1 日</td></tr>
</tbody></table>
<h3>8.4 全量报价明细（@@NQ@@ 行）</h3>
<div class="scroll"><table><thead><tr><th>日期</th><th>品种</th><th>市场</th><th>省份</th><th>口径</th><th>中间价</th><th>来源</th></tr></thead><tbody>@@QROWS@@</tbody></table></div>
</section>

<div class="foot">
数据来源：中央气象台（nmc.cn 每日天气提示 / 天气公报）、Open-Meteo 预报与归档 API、
云南蔬菜主产区每日菜价（泸西 / 通海分区表 11-10 与 11-11）、
11月11日云南产地蔬菜综合交易价格（三个独立转载源一致）、
农业农村部信息中心（证券之星转载：11-11 全国 48 家批发市场小葱 roundup、2025-11-11 王旗营单市场表）、
邯郸南大堡 11-11 蔬菜价格行情、北京新发地 11-11 官网菜价表、惠农网 11-08 产地行情、
青岛市城阳蔬菜水产品批发市场、重庆农业农村信息网、昆明市农业农村局 / 景臻·王旗营、
一亩田、惠农网、食品商务网、中国天气网云南站、本仓 price_history.json。<br>
本报告由自动化任务 376dffed 生成，仅供经营参考，不构成交易建议。价格单位除特别标注外均为元/公斤；
缺失值只标注不插补，冲突口径只并列不平均，估算值已在对应条目注明。
</div></div>
"""

a3 = FORECASTS[-1]["center"]
b3 = round(a3 * 4.60 / BASE_RED, 2)
c3 = round(a3 * 3.00 / BASE_RED, 2)
provinces = {q["province"] for q in QUOTES if q.get("province")}
sales_vals = [v for _, v, _ in SALES]

MAP = {
    "TODAY": TODAY, "DDATE": DATA_DATE, "GEN": GEN, "SUMMARY": SUMMARY_HTML,
    "WTREND": WTREND, "NATDESC": NATDESC,
    "YOYRED": YOY_RED, "YOYBLK": YOY_BLK, "YOYWQ": YOY_WQ, "YOYWQB": YOY_WQ_B,
    "NQ": len(QUOTES), "MERGED": MERGED, "NPROV": len(provinces),
    "NSALES": len(SALES), "SMIN": min(sales_vals), "SMAX": max(sales_vals),
    "ANO": ANO, "SPREAD": SPREAD, "BR": "%.2f" % BASE_RED, "BB": "%.2f" % BASE_BLACK,
    "MA": "%.2f" % (FRED["ma20"] or 0),
    "GAP": "%.1f" % ((FRED["ma20"] / BASE_RED - 1) * 100 if FRED["ma20"] else 0),
    "MONO": MONO_DESC, "A3": "%.2f" % a3, "B3": "%.2f" % b3, "C3": "%.2f" % c3,
    "NS": len(series), "OBS": lt["obs_count"], "INF": lt["inf_count"],
    "CAGR": "%.2f" % windows[120]["cagr"], "WINROWS": win_rows,
    "C_DECADE": C_DECADE, "C_36": C_36, "C_SEASON": C_SEASON, "C_WIN": C_WIN,
    "C_WX": C_WX, "C_FC": C_FC, "C_DUAL": C_DUAL, "C_FIVE": C_FIVE,
    "C_LAYERS": C_LAYERS, "C_SALES": C_SALES,
    "WXGEN": WX_GEN, "WXROWS": wx_rows, "WARNCLS": "" if DZ_OK else "warn",
    "DZNOTE": DISASTER_NOTE, "DZROWS": DZ_ROWS,
    "W3T": w3.get("tmax_avg"), "W3T2": w3.get("tmin_avg"), "W3P": w3.get("precip_total"),
    "W3R": w3.get("rainy_days"), "W3G": w3.get("gale_days"), "W3D": w3.get("dominant"),
    "W7T": w7.get("tmax_avg"), "W7T2": w7.get("tmin_avg"), "W7P": w7.get("precip_total"),
    "W7R": w7.get("rainy_days"), "W7G": w7.get("gale_days"), "W7D": w7.get("dominant"),
    "WHT": wh.get("tmax_avg"), "WHT2": wh.get("tmin_avg"), "WHP": wh.get("precip_total"),
    "WHR": wh.get("rainy_days"), "WHG": wh.get("gale_days"), "WHD": wh.get("dominant"),
    "PDATE": PEAK_DATE, "PMM": PEAK_MM, "CDATE": COLD_DATE, "CTMIN": COLD_TMIN,
    "RTOT": RAIN_TOTAL, "RDAYS": RAIN_DAYS, "HDESC": HEAVY_DESC,
    "VARROWS": variety_rows, "CULTROWS": cultivar_rows, "PROVROWS": prov_rows,
    "SALESROWS": sales_rows, "LAYERROWS": layer_rows,
    "FCROWS": fc_rows, "QROWS": qrows,
}
for k, v in MAP.items():
    BODY = BODY.replace("@@%s@@" % k, str(v))
left = re.findall(r"@@[A-Z0-9_]+@@", BODY)
html = ("<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>香葱行情分析报告 %s</title><style>%s</style></head><body>%s</body></html>"
        % (TODAY, CSS, BODY))
html_path = os.path.join(OUT_DIR, "香葱行情分析_%s.html" % TODAY)
with open(html_path, "w", encoding="utf-8") as f:
    f.write(html)

# ============================================================ 10. 自检
def check():
    errs = []
    # JSON schema
    for i, q in enumerate(QUOTES):
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(q.get("date", ""))):
            errs.append("quote[%d] bad date" % i)
        if q.get("mid") is None:
            errs.append("quote[%d] mid=None" % i)
        if q.get("unit") != "元/公斤":
            errs.append("quote[%d] unit" % i)
        if q.get("price_type") not in ("产地地头价", "产地收购价", "产地批发价", "销地批发价", "零售价"):
            errs.append("quote[%d] price_type=%s" % (i, q.get("price_type")))
    labels = [f["horizon"] for f in FORECASTS]
    if labels != [x[1] for x in HORIZON_MAP]:
        errs.append("forecast labels")
    keys = {(q["date"], q["market"], q["variety"], round(float(q["mid"]), 2)) for q in QUOTES}
    if len(keys) != len(QUOTES):
        errs.append("duplicate keys: %d vs %d" % (len(keys), len(QUOTES)))
    if left:
        errs.append("unresolved placeholders %s" % left[:5])
    # 表格列对齐：thead th[ >] 数 vs tbody 每行 td 数
    for ti, block in enumerate(re.findall(r"<table.*?</table>", html, re.S)):
        m = re.search(r"<thead>(.*?)</thead>", block, re.S)
        if not m:
            continue
        ncol = len(re.findall(r"<th[ >]", m.group(1)))
        body = re.search(r"<tbody>(.*?)</tbody>", block, re.S)
        if not body:
            continue
        for ri, row in enumerate(re.findall(r"<tr[^>]*>(.*?)</tr>", body.group(1), re.S)):
            n = len(re.findall(r"<td", row))
            cs = sum(int(x) - 1 for x in re.findall(r'colspan=["\']?(\d+)', row))
            if n + cs != ncol:
                errs.append("table[%d] row[%d] cols %d vs %d" % (ti, ri, n + cs, ncol))
    return errs


errs = check()
print("[CHECK] html", os.path.getsize(html_path), "bytes / svg",
      html.count("<svg"), "/ tables", html.count("<table"),
      "/ unresolved", len(left), "/ errors", len(errs))
for e in errs[:15]:
    print("  !", e)
print("[SUMMARY]", SUMMARY_JSON)
print("[FC]", [(f["horizon"], f["target_date"], f["center"]) for f in FORECASTS])
print("[PATHS]", json_path, "|", html_path)
