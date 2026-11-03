# -*- coding: utf-8 -*-
"""香葱行情定时任务落盘 + 图表报告生成器（任务 376dffed）· 2026-11-04

产出：
  1) data/sources/xiangcong_2026-11-04.json  统一 schema 全量报价 + 六档预测
  2) outputs/香葱行情分析_2026-11-04.html     长周期 / 收敛 / 同比 / 预测 图表

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

DATA_DATE = "2026-11-03"   # 最新可获取的实测报价日（当日数据次日发布）
PREV_DATE = "2026-11-01"

# 本期核心实测（泸西分区，11-02 实测，次日发布）
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
     "note": "泸西菜价红香葱 3.3-3.6 均价 3.45；与 11-01 的 3.45 完全持平，结束破位后连续三日报价锁定 3.45"},
    {"date": DATA_DATE, "variety": "黑葱", "market": "云南产地", "price": BLK_MID,
     "source": "observed",
     "note": "泸西菜价黑香葱 2.7-3.1 均价 2.96；与 11-01 的 2.96 完全持平，黑葱 11-01 跟跌后暂稳、连续两日报价锁定 2.96"},
    {"date": DATA_DATE, "variety": "小葱", "market": "昆明王旗营", "price": 2.50,
     "source": "observed",
     "note": "景臻·王旗营 11-02 批发均价 2.50，与 11-01 的 2.50 持平，低位平台延续；成交量约 30 吨"},
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
wx = json.load(open(os.path.join(BASE_DIR, "data", "weather_2026-11-04.json"), encoding="utf-8"))
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

# ============================================================ 4. 全量报价
def Q(date, item, variety, market, province, ptype, low, high, mid, source, url="", note=""):
    return {"date": date, "item": item, "variety": variety, "market": market,
            "province": province, "price_type": ptype, "unit": "元/公斤",
            "low": low, "high": high, "mid": mid,
            "source": source, "source_url": url, "note": note}


QUOTES = []
A = QUOTES.append

WX_URL = "http://mp.weixin.qq.com/s?__biz=MzU5MTc0MTM0MA==&mid=2247595855&idx=1&sn=e69c733bdcd68a31cc385e32866aada5"
DH_URL = "http://mp.weixin.qq.com/s?__biz=Mzg3Mzg1MTgwNw==&mid=2247490587&idx=1&sn=9187ec35d47b2885f3d99ee0b2b21aba"
DH2_URL = "http://mp.weixin.qq.com/s?__biz=MzY4ODEyNjkxMQ==&mid=2247490395&idx=1&sn=76e7ba8ba901367f0223a713bdde6012"

# —— 泸西核心产区（11-02 实测，模型基准口径）
A(Q(DATA_DATE, "香葱", "红香葱", "云南红河州泸西县", "云南", "产地收购价",
    RED_LO, RED_HI, RED_MID, "云南蔬菜主产区每日菜价（泸西菜价表）", WX_URL,
    "本期模型基准。泸西红香葱 3.3-3.6、均价 3.45，与 11-01 的 3.45 完全持平，连续三日报价锁定 3.45；"
    "行情简报总评「小香葱低稳、低位躺平」"))
A(Q(DATA_DATE, "香葱", "黑香葱", "云南红河州泸西县", "云南", "产地收购价",
    BLK_LO, BLK_HI, BLK_MID, "云南蔬菜主产区每日菜价（泸西菜价表）", WX_URL,
    "泸西黑香葱 2.7-3.1、均价 2.96，与 11-01 的 2.96 完全持平，黑葱 11-01 跟跌后暂稳、连续两日报价锁定 2.96；"
    "红黑价差维持 0.49，黑葱相对红葱的溢价已彻底消失"))
A(Q(DATA_DATE, "香葱", "红葱", "云南玉溪市通海县", "云南", "产地收购价",
    3.3, 3.6, 3.45, "云南蔬菜主产区每日菜价（通海菜价表）", WX_URL,
    "通海红葱 3.3-3.6 与泸西红香葱完全同步持平，确认为滇中产区整体性定价"))
A(Q(DATA_DATE, "香葱", "黑葱", "云南玉溪市通海县", "云南", "产地收购价",
    2.7, 3.1, 2.96, "云南蔬菜主产区每日菜价（通海菜价表）", WX_URL,
    "通海黑葱 2.7-3.1 与泸西黑香葱同步破位至 2.96，滇中黑葱同价下行"))

# —— 全省综合（11-02：红葱持平 3.45、黑葱跟随暂稳）
A(Q(DATA_DATE, "香葱", "红香葱", "云南产地综合交易价（全省）", "云南", "产地批发价",
    3.3, 3.6, 3.45, "云南蔬菜综合报价（11-02）", DH_URL,
    "全省综合交易价红香葱 3.3-3.6，连续四日锁在 3.45，与泸西分区价完全对齐，倒挂已彻底消除；官方总评「小香葱低稳」"))
A(Q(DATA_DATE, "香葱", "黑葱", "云南产地综合交易价（全省）", "云南", "产地批发价",
    2.7, 3.1, 2.96, "云南蔬菜综合报价（11-02）", DH_URL,
    "全省综合交易价黑葱 2.7-3.1，与泸西/通海同步持平于 2.96，结束此前僵持"))
A(Q(PREV_DATE, "香葱", "红香葱", "云南产地综合交易价（全省）", "云南", "产地批发价",
    3.3, 3.6, 3.45, "云南蔬菜综合报价（10-30 档案）", "", "上期全省综合价，与本期一致；上期已首次低于泸西分区价 0.40 元"))
A(Q("2026-10-29", "香葱", "红香葱", "云南产地综合交易价（全省）", "云南", "产地批发价",
    3.6, 4.0, 3.80, "云南蔬菜综合报价（10-29 档案）", "", "10-29 全省综合价，用于观察三级下移"))
A(Q("2026-10-26", "香葱", "红香葱", "云南产地综合交易价（全省）", "云南", "产地批发价",
    4.4, 5.0, 4.70, "云南蔬菜综合报价（10-26 档案）", "", "10-26 全省综合报价，当时仍高于泸西 0.85 元"))

# —— 泸西地头大宗价（权威实地采集源，本期仍未更新 → 按地头价推算）
A(Q("2026-10-28", "香葱", "小葱（统货）", "红河州泸西县（地头大宗价）", "云南", "产地地头价",
    4.5, 5.5, 5.00, "国资云农（云南国资云农信息团队每日产地采集）", "",
    "10-28 大宗价 5.00（区间 4.5-5.5）。该源自 10/29 起连续四期（10/29-11/01）未发布，11-01 本次检索仍未更新，沿用 10-28 值"))
A(Q(DATA_DATE, "香葱", "小葱（统货·推算）", "红河州泸西县（地头大宗价·推算）", "云南", "产地地头价",
    4.2, 5.0, 4.60, "本报告推算（国资云农源断更）", "",
    "⚠️ 估算值。按地头毛菜 3.45 + 洗葱/整理/损耗加成（历史加成率约 1.33 倍）推算，当前统货大宗价应已回落至约 4.60，"
    "较 10-28 的 5.00 下跌约 8%"))
A(Q("2026-10-27", "香葱", "小葱（统货）", "红河州泸西县（地头大宗价）", "云南", "产地地头价",
    4.5, 5.5, 4.90, "国资云农", "", "10-27 大宗价 4.90，用于计算真实环比"))

# —— 全国产地横截面（一亩田，元/斤 ×2 折算，10-31）
A(Q(DATA_DATE, "小葱", "小葱", "云南红河泸西县（平台行情）", "云南", "产地收购价",
    2.54, 2.54, 2.54, "一亩田·全国小葱价格行情参考", "https://www.ymt.com/hangqing/juhe-7300",
    "挂牌 1.27 元/斤 ×2 折算，环比 0.00；较 10-27 的 1.31 元/斤（2.62）下跌 0.08 元/kg（-3.1%），与地头价破位方向一致"))
A(Q(DATA_DATE, "四季小葱", "四季小葱", "云南红河泸西县（平台行情）", "云南", "产地收购价",
    2.20, 2.20, 2.20, "一亩田·全国小葱价格行情参考", "https://www.ymt.com/hangqing/juhe-7300",
    "挂牌 1.10 元/斤 ×2 折算，环比 0.00；较前值 1.14 元/斤下跌 0.08 元/kg（-3.5%）"))
A(Q(DATA_DATE, "小葱", "小葱（全国均价）", "一亩田全国小葱产地行情聚合", "全国", "产地收购价",
    3.08, 3.08, 3.08, "一亩田·全国小葱价格行情参考", "https://www.ymt.com/hangqing/juhe-7300",
    "全国小葱产地挂牌均价 1.54 元/斤 ×2 折算，涨跌标注「平稳 0.0」。泸西 1.27 元/斤低于全国均价"))
A(Q(DATA_DATE, "小葱", "小葱", "云南大理宾川县（平台行情）", "云南", "产地收购价",
    2.68, 2.68, 2.68, "一亩田·全国小葱价格行情参考", "https://www.ymt.com/hangqing/juhe-7300",
    "挂牌 1.34 元/斤 ×2 折算；滇西产区，与泸西形成省内比价"))
A(Q(DATA_DATE, "四季小葱", "四季小葱", "云南大理宾川县（平台行情）", "云南", "产地收购价",
    2.84, 2.84, 2.84, "一亩田·全国小葱价格行情参考", "https://www.ymt.com/hangqing/juhe-7300",
    "挂牌 1.42 元/斤 ×2 折算"))
A(Q(DATA_DATE, "小葱", "小葱", "河南平顶山汝州市", "河南", "产地收购价",
    2.28, 2.28, 2.28, "一亩田·全国小葱价格行情参考", "https://www.ymt.com/hangqing/juhe-7300",
    "挂牌 1.14 元/斤 ×2 折算"))
A(Q(DATA_DATE, "四季小葱", "四季小葱", "河南平顶山汝州市", "河南", "产地收购价",
    1.90, 1.90, 1.90, "一亩田·全国小葱价格行情参考", "https://www.ymt.com/hangqing/juhe-7300",
    "挂牌 0.95 元/斤 ×2 折算，全国产地最低档"))
A(Q(DATA_DATE, "小葱", "小葱", "河南焦作武陟县", "河南", "产地收购价",
    2.54, 2.54, 2.54, "一亩田·全国小葱价格行情参考", "https://www.ymt.com/hangqing/juhe-7300",
    "挂牌 1.27 元/斤 ×2 折算"))
A(Q(DATA_DATE, "四季小葱", "四季小葱", "河南焦作武陟县", "河南", "产地收购价",
    2.10, 2.10, 2.10, "一亩田·全国小葱价格行情参考", "https://www.ymt.com/hangqing/juhe-7300",
    "挂牌 1.05 元/斤 ×2 折算"))
A(Q(DATA_DATE, "小葱", "小葱", "广西柳州柳江区", "广西", "产地收购价",
    3.14, 3.14, 3.14, "一亩田·全国小葱价格行情参考", "https://www.ymt.com/hangqing/juhe-7300",
    "挂牌 1.57 元/斤 ×2 折算，涨跌 +0.02 元/斤，本期全国产地少数上涨"))
A(Q(DATA_DATE, "四季小葱", "四季小葱", "广西柳州柳江区", "广西", "产地收购价",
    3.08, 3.08, 3.08, "一亩田·全国小葱价格行情参考", "https://www.ymt.com/hangqing/juhe-7300",
    "挂牌 1.54 元/斤 ×2 折算"))
A(Q(DATA_DATE, "小葱", "小葱", "山东临沂郯城县", "山东", "产地收购价",
    3.22, 3.22, 3.22, "一亩田·全国小葱价格行情参考", "https://www.ymt.com/hangqing/juhe-7300",
    "挂牌 1.61 元/斤 ×2 折算，北方产地最高档"))
A(Q(DATA_DATE, "四季小葱", "四季小葱", "江苏盐城大丰区", "江苏", "产地收购价",
    3.36, 3.36, 3.36, "一亩田·全国小葱价格行情参考", "https://www.ymt.com/hangqing/juhe-7300",
    "挂牌 1.68 元/斤 ×2 折算，本期全国挂牌最高档"))
A(Q(DATA_DATE, "小葱", "小葱", "河北邯郸永年区", "河北", "产地收购价",
    2.78, 2.78, 2.78, "一亩田·全国小葱价格行情参考", "https://www.ymt.com/hangqing/juhe-7300",
    "挂牌 1.39 元/斤 ×2 折算，华北主产地"))
A(Q(DATA_DATE, "小葱", "小葱", "河北唐山滦南县", "河北", "产地收购价",
    2.80, 2.80, 2.80, "一亩田·全国小葱价格行情参考", "https://www.ymt.com/hangqing/juhe-7300",
    "挂牌 1.40 元/斤 ×2 折算"))
A(Q(DATA_DATE, "小葱", "小葱", "广东湛江徐闻县", "广东", "产地收购价",
    2.92, 2.92, 2.92, "一亩田·全国小葱价格行情参考", "https://www.ymt.com/hangqing/juhe-7300",
    "挂牌 1.46 元/斤 ×2 折算，粤西产地"))

# —— 泸西挂牌（非成交，分层参考）
A(Q(DATA_DATE, "香葱", "香葱（地头价）", "云南红河州泸西县（惠农网挂牌）", "云南", "产地地头价",
    3.40, 3.40, 3.40, "惠农网供应挂牌（1.70 元/斤换算）", "https://www.cnhnb.com/p/xiaocong-0-25-0-0-4/",
    "卖家王明标注「香葱 地头价」「红葱地头价」，与官方地头价 3.45 高度吻合（差 0.05），可作交叉验证"))
A(Q(DATA_DATE, "香葱", "水洗葱", "云南红河州泸西县（惠农网挂牌）", "云南", "产地收购价",
    3.60, 3.60, 3.60, "惠农网供应挂牌（1.80 元/斤换算）", "https://www.cnhnb.com/p/xiaocong-0-25-0-0-4/",
    "水洗加工后较地头毛菜 3.40 溢价 0.20，反映加工环节成本"))
A(Q(DATA_DATE, "香葱", "香葱（水洗统货）", "云南红河州泸西县（惠农网挂牌）", "云南", "产地收购价",
    4.40, 4.40, 4.40, "惠农网供应挂牌（2.20 元/斤换算）", "https://www.cnhnb.com/gongying/8861162/",
    "水洗白葱/黑葱/红葱，代办报价，10000 斤起批"))
A(Q(DATA_DATE, "香葱", "小葱（40 公分）", "云南红河州泸西县（一亩田挂牌）", "云南", "产地收购价",
    4.00, 4.00, 4.00, "一亩田供应挂牌（2.00 元/斤换算）", "https://m.ymt.com/supply/60633035",
    "10000 斤起批，卖家标注种植面积 20 万余亩"))
A(Q(DATA_DATE, "四季小葱", "四季小葱（40-45cm 精品）", "云南红河州泸西县（一亩田挂牌）", "云南", "产地收购价",
    3.60, 3.60, 3.60, "一亩田供应挂牌（1.80 元/斤换算）", "https://www.ymt.com/supply/66260514",
    "同页通货 1.10 元/斤 = 2.20 元/kg，精品较通货溢价 1.40"))
A(Q(DATA_DATE, "香葱", "小香葱（整车）", "云南红河州泸西县（惠农网挂牌）", "云南", "产地收购价",
    2.00, 2.00, 2.00, "惠农网供应挂牌（2000 元/吨换算）", "https://www.cnhnb.com/p/xiaocong-0-25-0-0-4/",
    "云南地汇农业，按吨计价，全国公开报价最低档之一"))
A(Q(DATA_DATE, "香葱", "小香葱（通货整车）", "云南红河州泸西县（惠农网挂牌）", "云南", "产地收购价",
    1.60, 4.40, 3.00, "惠农网供应挂牌（0.80-2.20 元/斤换算）", "https://www.cnhnb.com/gongying/5867578/",
    "整车通货挂牌区间，跨度大，为代办报价区间而非成交均价"))
A(Q(DATA_DATE, "香葱", "小葱（包邮精装）", "云南红河州泸西县（惠农网挂牌）", "云南", "产地收购价",
    6.36, 6.36, 6.36, "惠农网供应挂牌（3.18 元/斤换算）", "https://www.cnhnb.com/p/xiaocong-0-25-0-0-4/",
    "永合葱业，包邮精装口径"))
A(Q(DATA_DATE, "香葱", "小香葱（代收代办）", "云南红河州泸西县（惠农网挂牌）", "云南", "产地收购价",
    12.00, 12.00, 12.00, "惠农网供应挂牌（6.00 元/斤换算）", "https://www.cnhnb.com/p/xiaocong-0-25-0-0-4/",
    "代收代办服务费口径，非普货成交价，不可用于定价"))
A(Q(DATA_DATE, "香葱", "红香葱", "云南大理州宾川县（惠农网挂牌）", "云南", "产地收购价",
    8.00, 8.00, 8.00, "惠农网供应挂牌（刘富培）", "https://www.cnhnb.com/p/xiaocong-0-25-0-0-4/",
    "滇西宾川红香葱挂牌"))
A(Q(DATA_DATE, "香葱", "小香葱", "云南玉溪市（惠农网挂牌）", "云南", "产地收购价",
    7.00, 7.00, 7.00, "惠农网供应挂牌（3.50 元/斤换算）", "https://www.cnhnb.com/p/xiaocong-0-25-0-0-4/", ""))
A(Q(DATA_DATE, "四季葱", "四季葱（基地直销）", "云南大理州剑川县（惠农网挂牌）", "云南", "产地收购价",
    6.00, 6.00, 6.00, "惠农网供应挂牌（3.00 元/斤换算）", "https://www.cnhnb.com/p/xiaocong-0-25-0-0-4/",
    "滇西北高海拔产区"))
A(Q("2026-10-23", "香葱", "香葱", "河北邯郸市丛台区（惠农网行情）", "河北", "产地收购价",
    2.76, 2.76, 2.76, "惠农网产地行情（1.38 元/斤换算）", "https://www.cnhnb.com/hangqing/cdlist-2000478-6222-0-0-0-1/",
    "华北产地挂牌"))
A(Q("2026-10-23", "香葱", "香葱", "安徽阜阳市临泉县（惠农网行情）", "安徽", "产地收购价",
    1.76, 1.76, 1.76, "惠农网产地行情（0.88 元/斤换算）", "https://www.cnhnb.com/hangqing/cdlist-2000478-6222-0-0-0-1/",
    "华东产地最低档"))
A(Q("2026-10-23", "四季葱", "四季葱", "山东潍坊市安丘市（惠农网行情）", "山东", "产地收购价",
    1.70, 1.70, 1.70, "惠农网产地行情（0.85 元/斤换算）", "https://www.cnhnb.com/hangqing/cdlist-2000478-6222-0-0-0-1/",
    "山东秋茬四季葱"))
A(Q("2026-10-23", "香葱", "香葱", "河南开封市通许县（惠农网行情）", "河南", "产地收购价",
    1.54, 1.54, 1.54, "惠农网产地行情（0.77 元/斤换算）", "https://www.cnhnb.com/hangqing/cdlist-2000478-6222-0-0-0-1/",
    "华中产地"))
A(Q("2026-10-23", "香葱", "香葱", "湖北宜昌市当阳市（惠农网行情）", "湖北", "产地收购价",
    2.88, 2.88, 2.88, "惠农网产地行情（1.44 元/斤换算）", "https://www.cnhnb.com/hangqing/cdlist-2000478-6222-0-0-0-1/",
    "长江中游产地"))
A(Q("2026-10-23", "四季葱", "四季葱", "广西柳州市柳江区（惠农网行情）", "广西", "产地收购价",
    2.98, 2.98, 2.98, "惠农网产地行情（1.49 元/斤换算）", "https://www.cnhnb.com/hangqing/cdlist-2000478-6222-0-0-0-1/",
    "华南产地"))
A(Q("2026-10-23", "香葱", "香葱", "四川成都市金堂县（惠农网行情）", "四川", "产地收购价",
    3.58, 3.58, 3.58, "惠农网产地行情（1.79 元/斤换算）", "https://www.cnhnb.com/hangqing/cdlist-2000478-6222-0-0-0-1/",
    "西南产地（火葱/分葱区）"))
A(Q("2026-10-23", "香葱", "香葱", "贵州毕节市威宁彝族回族苗族自治县（惠农网行情）", "贵州", "产地收购价",
    4.50, 4.50, 4.50, "惠农网产地行情（2.25 元/斤换算）", "https://www.cnhnb.com/hangqing/cdlist-2000478-6222-0-0-0-1/",
    "黔西高海拔冷凉产区"))
A(Q("2026-10-23", "香葱", "香葱", "广东韶关市翁源县（惠农网行情）", "广东", "产地收购价",
    9.86, 9.86, 9.86, "惠农网产地行情（4.93 元/斤换算）", "https://www.cnhnb.com/hangqing/cdlist-2000478-6222-0-0-0-1/",
    "华南产地最高档，疑为种苗或小规格货"))

# —— 销区批发（11-02 实测）
A(Q(DATA_DATE, "小葱", "小葱", "昆明景臻王旗营蔬菜批发市场", "云南", "销地批发价",
    2.50, 2.50, 2.50, "昆明市农业农村局 / 景臻·王旗营", DH2_URL,
    "11-02 批发均价 2.50，与 11-01 的 2.50 持平，低位平台延续；"
    "综合平均价约 4.24、总吨位 2620。销地延续低位，与产地红黑横盘相互印证，"
    "但绝对量仍低于 35 吨常态，未确认趋势反转"))
A(Q(DATA_DATE, "香葱", "香葱（精装规格）", "北京新发地农产品批发市场", "北京", "销地批发价",
    6.6, 9.0, 7.80, "北京新发地官网每日价格行情（10-31）", "http://www.xinfadi.com.cn/",
    "官方口径 最低 3.30 / 平均 3.90 / 最高 4.50 元/斤，×2 折算；与 10-30 完全一致。与农业农村部「小葱」口径差异极大，不可平均"))
A(Q(DATA_DATE, "香葱", "净小葱", "北京新发地农产品批发市场", "北京", "销地批发价",
    2.6, 5.0, 3.80, "北京新发地官网每日价格行情（10-31）", "http://www.xinfadi.com.cn/",
    "最低 1.30 / 平均 1.90 / 最高 2.50 元/斤，×2 折算；与「香葱」为不同规格，价格仅为其 49%"))
A(Q(DATA_DATE, "小葱", "小葱", "安徽合肥周谷堆农产品批发市场", "安徽", "销地批发价",
    5.0, 6.5, 5.80, "合肥周谷堆每日菜价（公众号）",
    "http://mp.weixin.qq.com/s?__biz=MzkzNzcyNDk4Ng==&mid=2247484314&idx=2&sn=282c090e0cd562f2ae39d24018ecbd33",
    "⚠️ 销地端最强走弱信号。较 10-30 的 6.75 再跌 0.95（-14.1%），较 10-27 的 7.50 累计 -22.7%，三连跌"))
A(Q(DATA_DATE, "香葱", "小葱", "海口市菜篮子江楠农产品批发市场", "海南", "销地批发价",
    11.0, 11.0, 11.0, "海口市菜篮子产业集团「天天菜价」（5.50 元/斤换算）", "http://www.hksclz.com/groceries/index",
    "海南终端配送口径，与宁夏中卫并列全国最高档"))
A(Q(DATA_DATE, "香葱", "香葱", "北京平谷大宗食材采购平台", "北京", "销地批发价",
    8.0, 8.0, 8.0, "平谷大宗食材采购平台（4 元/斤换算）", "https://www.pgxyjc.com/", "京津冀食材配送口径"))
A(Q("2026-10-30", "香葱", "香葱", "青岛市城阳蔬菜水产品批发市场", "山东", "销地批发价",
    7.0, 9.0, 8.00, "青岛市城阳蔬菜水产品批发市场", "http://www.cncyms.cn/",
    "官网 高 9.00 / 中 8.00 / 低 7.00 元/公斤，连续多日持平，为可获取的高位销区报价。10-31 本次检索未刷新"))
A(Q("2026-10-29", "香葱", "香葱", "宁夏中卫四季鲜农产品批发市场", "宁夏", "销地批发价",
    10.0, 12.0, 11.00, "宁夏发改委价格监测中心", "", "原始 5-6 元/斤 ×2 折算，西北远端销区，全国最高档"))
A(Q("2026-10-30", "小葱", "小葱", "北京新发地农副产品批发市场", "北京", "销地批发价",
    3.8, 3.8, 3.8, "农业农村部信息中心（10-30）", "https://futures.stockstar.com/IG2026103000028998.shtml",
    "农业农村部「小葱」品类，连续持平"))
A(Q("2026-10-30", "香葱", "香葱", "邯郸市经开区南大堡蔬菜批发市场", "河北", "销地批发价",
    2.0, 2.0, 2.0, "农业农村部信息中心（10-30）", "https://futures.stockstar.com/IG2026103000029278.shtml",
    "华北销地最低档"))
A(Q("2026-10-29", "香葱", "香葱", "云南通海金山蔬菜批发市场", "云南", "销地批发价",
    9.0, 9.0, 9.0, "农业农村部信息中心", "", "滇中产地批发市场"))
A(Q("2026-10-28", "香葱", "小葱", "云南昆明景臻王旗营蔬菜批发市场", "云南", "销地批发价",
    2.5, 2.5, 2.5, "农业农村部信息中心", "", "云南省内销地，处年内低位"))
A(Q("2026-10-27", "香葱", "小葱", "北京朝阳区大洋路综合市场", "北京", "销地批发价",
    8.0, 8.0, 8.0, "农业农村部信息中心", "", "北京二级销地"))
A(Q("2026-10-27", "香葱", "小葱", "江苏凌家塘市场发展有限公司", "江苏", "销地批发价",
    8.0, 8.0, 8.0, "农业农村部信息中心", "", "华东销地"))
A(Q("2026-10-27", "香葱", "小葱", "江苏无锡朝阳农产品大市场", "江苏", "销地批发价",
    5.96, 5.96, 5.96, "农业农村部信息中心", "", "华东销地"))
A(Q("2026-10-27", "香葱", "小葱", "浙江嘉兴蔬菜批发交易市场", "浙江", "销地批发价",
    5.14, 5.14, 5.14, "农业农村部信息中心", "", "华东销地"))
A(Q("2026-10-27", "香葱", "小葱", "湖北鄂州市蟠龙农产品批发市场", "湖北", "销地批发价",
    11.0, 11.0, 11.0, "农业农村部信息中心", "", "华中销地，全国最高档之一"))
A(Q("2026-10-27", "香葱", "小葱", "四川成都濛阳农副产品综合批发交易市场", "四川", "销地批发价",
    4.5, 4.5, 4.5, "农业农村部信息中心", "", "西南销地枢纽"))

# —— 替代品与零售参考
A(Q(DATA_DATE, "大葱", "大葱", "北京新发地农产品批发市场", "北京", "销地批发价",
    1.8, 2.0, 1.9, "北京新发地官网每日价格行情（10-31）", "http://www.xinfadi.com.cn/",
    "替代品。0.9-1.0 元/斤 ×2 折算，大葱处低位，对香葱消费形成分流压制"))
A(Q(DATA_DATE, "大葱", "大葱", "安徽合肥周谷堆农产品批发市场", "安徽", "销地批发价",
    2.4, 3.4, 3.0, "合肥周谷堆每日菜价（公众号）", "", "替代品参考，华东销地大葱"))
A(Q(DATA_DATE, "大葱", "大葱", "海口市菜篮子江楠农产品批发市场", "海南", "销地批发价",
    8.0, 8.0, 8.0, "海口市菜篮子产业集团（4.00 元/斤换算）", "http://www.hksclz.com/groceries/index",
    "海南终端配送口径"))
A(Q(DATA_DATE, "大葱", "大葱", "北京市（发改委价格监测）", "北京", "销地批发价",
    1.94, 1.94, 1.94, "北京市发展和改革委员会蔬菜价格监测（0.97 元/500 克换算）",
    "https://project.fgw.beijing.gov.cn/bmcx/E000030/",
    "10-31 批发 0.97 元/500g，较 10-28 的 1.02 下跌 4.9%；农贸零售 2.39、超市零售 2.28 元/500g"))
A(Q(DATA_DATE, "大葱", "大葱（零售·中上等）", "云南楚雄州市场", "云南", "零售价",
    12.00, 12.00, 12.00, "楚雄州发展和改革委员会", "https://fgw.cxz.gov.cn/info/1280/200036.htm",
    "零售价口径（市场中上等综合平均价），与批发价不可横比"))

# —— 历史同期档案（同比基准）
A(Q("2025-11-01", "香葱", "红香葱", "云南红河州泸西县（历史同期档案）", "云南", "产地收购价",
    6.0, 6.4, 6.20, "云南蔬菜主产区每日菜价（2025-11-01 历史档案）", "",
    "⭐ 隔年精确同日档案。本期 3.45 与之相比为 -44.4%，为本序列近五年最大同比跌幅"))
A(Q("2025-11-01", "香葱", "黑香葱", "云南红河州泸西县（历史同期档案）", "云南", "产地收购价",
    4.1, 4.6, 4.35, "云南蔬菜主产区每日菜价（2025-11-01 历史档案）", "",
    "去年同期黑香葱均价 4.35，本期 2.96 与之相比为 -31.9%，跌幅小于红香葱"))
A(Q("2025-10-31", "香葱", "红香葱", "云南红河州泸西县（历史同期档案·校正前日）", "云南", "产地收购价",
    6.0, 6.4, 6.25, "云南蔬菜主产区每日菜价（2025-10-31 历史档案）", "",
    "校正用：10-31 次日档案 6.25，与 11-01 的 6.20 基本一致"))
A(Q("2025-10-31", "香葱", "黑香葱", "云南红河州泸西县（历史同期档案·校正前日）", "云南", "产地收购价",
    4.1, 4.6, 4.16, "云南蔬菜主产区每日菜价（2025-10-31 历史档案）", "",
    "校正用：10-31 次日黑香葱 4.16"))
A(Q("2024-10-29", "香葱", "红香葱", "云南红河州泸西县（历史同期档案）", "云南", "产地收购价",
    5.1, 6.0, 5.55, "云南蔬菜主产区每日菜价（2024 档案）", "", "两年前同期，本期较之 -37.8%"))
A(Q("2023-10-30", "香葱", "红香葱", "云南红河州泸西县（历史同期档案）", "云南", "产地收购价",
    5.5, 6.3, 5.90, "云南蔬菜主产区每日菜价（2023 历史档案）", "", "三年前同期"))
A(Q("2022-10-30", "香葱", "红香葱", "云南红河州泸西县（历史同期档案）", "云南", "产地收购价",
    4.7, 5.2, 4.95, "云南蔬菜主产区每日菜价（2022 历史档案）", "", "四年前同期"))

# —— 农业农村部重点农产品市场信息平台·实时成交（泸西产地→销地，2026-11-03 抓取）
A(Q("2026-11-03", "香葱", "细香葱", "江苏无锡市惠山区（泸西产地外销成交）", "江苏", "销地批发价",
   7.69, 7.69, 7.69, "农业农村部重点农产品市场信息平台（ncpscxx.moa.gov.cn）", "",
   "泸西县→无锡惠山实时成交 7.6923 元/kg（13 单位），精品净葱含物流，对应产地集散价 3.45 形成产销价差约 2.2 倍"))
A(Q("2026-11-03", "香葱", "细香葱", "江苏无锡市新吴区（泸西产地外销成交）", "江苏", "销地批发价",
   6.67, 6.67, 6.67, "农业农村部重点农产品市场信息平台（ncpscxx.moa.gov.cn）", "",
   "泸西县→无锡新吴实时成交 6.6667 元/kg（30 单位），精品净葱含物流"))

# —— 合并同仓其他自动化任务今日已采集的报价（去重）
_seen = {(q["date"], q["market"], q["variety"], round(q["mid"], 2)) for q in QUOTES}
for fn in ("gemini_2026-11-04.json", "chatgpt_2026-11-04.json",
           "grok_2026-11-04.json", "national_2026-11-04.json"):
    p = os.path.join(SRC_DIR, fn)
    if not os.path.exists(p):
        continue
    try:
        d = json.load(open(p, encoding="utf-8"))
    except Exception:
        continue
    for q in d.get("quotes", []):
        key = (q.get("date"), q.get("market"), q.get("variety"),
               round(float(q.get("mid") or 0), 2))
        if key in _seen:
            continue
        _seen.add(key)
        QUOTES.append({
            "date": q.get("date"), "item": q.get("item", "香葱"),
            "variety": q.get("variety", ""), "market": q.get("market", ""),
            "province": q.get("province", ""), "price_type": q.get("price_type", "产地收购价"),
            "unit": "元/公斤", "low": q.get("low"), "high": q.get("high"), "mid": q.get("mid"),
            "source": q.get("source", ""), "source_url": q.get("source_url", ""),
            "note": q.get("note", ""),
        })
QUOTES.sort(key=lambda q: (q["date"], q["province"], -(q["mid"] or 0)))

SUMMARY = (
    "泸西产地红香葱 11-03 报 <b>3.3-3.6、均价 3.45</b>，与 11-01 的 3.45 <b>完全持平</b>，自 11-01 起连续多日报价锁定 3.45，行情陷入<b>低位横盘僵持</b>；"
    "通海红葱同步持平至 3.3-3.6 同价，确认滇中产区红葱整体性定价。"
    "黑香葱 11-03 报 <b>2.7-3.1、均价 2.96</b>，与 11-01 的 2.96 <b>完全持平</b>——黑葱 11-01 跟跌后暂稳、连续多日报价锁定 2.96，"
    "红黑价差维持 0.49，黑葱相对红葱的溢价已彻底消失，二者均处近年低位。"
    "销地端延续低位：昆明王旗营小葱 <b>2.50</b> 与 11-01 持平，低位平台延续，成交量约 30 吨，仍低于 35 吨常态，未确认反转；合肥周谷堆小葱延续弱势。"
    "同比方面，本期取得隔年近似同日（2025-11-01）档案：泸西红香葱均价 6.20，本期 3.45 同比 <b>-44.4%</b>，为近五年同期绝对最低。"
    "气象端：未来 3 天泸西<b>暖干少雨</b>（累计 {0} mm、最高 {1}℃、距平 {2:+.1f}℃），短期供给充裕；"
    "但 <b>{3} 前后转入强降水 + 明显降温</b>——{3} 单日 {4} mm（强降水），{5} 前后最高气温降至 {6}℃、最低温回落至 {7}℃ 上下，"
    "第 2-3 周<b>采收受阻 + 洗葱损耗上升 + 霜霉/灰霉病风险</b>仍是预测上行的核心驱动。"
    "灾害预警方面：中央气象台 11-04 生效预警全网 <b>{dtot_}</b> 条、结构由<b>大雾主导</b>（大雾 60、大风 22、道路冰雪 7、暴雨 4）；"
    "涉及核心产区：<b>云南普洱江城地质灾害橙色</b>（滇南，紧邻红河州泸西外运通道），浙江杭州临安大风黄色（设施受损）；"
    "泸西本县本轮无独立生效预警，但滇南地质灾害橙色紧邻、且 {3} 本地强降水（{4} mm）仍构成采收与运输风险。"
    "六档中枢（精品净葱/集散价口径）：{8} 元/公斤。"
).format(w3.get("precip_total"), w3.get("tmax_avg"),
         (w3.get("tmax_avg") or 0) - (clim.get("tmax_mean") or 0),
         "11/8", 21.3, "11/9", 11.1, 7.3,
         " → ".join(str(f["center"]) for f in FORECASTS),
         dtot_=100)

DOC = {
    "task": "香葱行情",
    "task_id": "376dffed-c5e4-4904-a77a-29193947212a",
    "date": TODAY,
    "generated_at": GEN,
    "market_scope": "全国 / 云南 / 红河州泸西县（本期覆盖 18 省区）",
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
           ("10-30", 3.85, 3.45), ("10-31", 3.45, 3.45), ("11-01", 3.45, 3.45)]
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
           ("10-31", 2.2, 30), ("11-01", 2.5, 30)]
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
    """近五年同期（10 月末）泸西红香葱均价对比。"""
    pts = [("2022-10-30", 4.95), ("2023-10-30", 5.90), ("2024-10-29", 5.55),
           ("2025-11-01", 6.20), ("2026-11-03", 3.45)]
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
    g.append('<text x="{0}" y="{1}" font-size="11.5" fill="#1f2937">10 月末同期泸西红香葱均价（元/公斤）</text>'.format(ml + 6, mt - 14))
    g.append('<text x="{0}" y="{1}" font-size="10.5" fill="#16a34a">柱下绿色百分比 = 2026 年相对该年的同比涨跌幅</text>'.format(ml + 250, mt - 14))
    g.append("</svg>")
    return "".join(g)


def chart_luxi_spread():
    """泸西多源口径分歧。"""
    pts = [("一亩田·代收代办挂牌(6.00元/斤)", 12.00),
           ("惠农网·宾川红香葱挂牌", 8.00),
           ("惠农网·小葱包邮精装(3.18元/斤)", 6.36),
           ("国资云农·地头大宗(10-28,未刷新)", 5.00),
           ("本报告推算·地头统货大宗", 4.60),
           ("惠农网·水洗葱(1.80元/斤)", 3.60),
           ("一亩田·泸西精品40-45cm(1.80元/斤)", 3.60),
           ("泸西·集散均价 红香葱(模型基准)", 3.45),
           ("云南全省综合交易价 红香葱", 3.45),
           ("泸西·集散均价 黑香葱(11-01破位)", 2.96),
           ("云南全省综合交易价 黑香葱(11-01)", 2.96),
           ("惠农网·地头价挂牌(1.70元/斤)", 3.40),
           ("一亩田·平台行情 小葱(1.27元/斤)", 2.54),
           ("一亩田·泸西四季小葱(1.10元/斤)", 2.20),
           ("惠农网·整车吨价(2000元/吨)", 2.00)]
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

disaster_top = json.load(open(os.path.join(BASE_DIR, "data", "disaster_2026-11-04.json"), encoding="utf-8"))
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
  <div class="kpi"><div class="l">泸西模型基准（红香葱）</div><div class="v" style="color:#2563eb">{br:.2f}</div><div class="d">元/公斤 · 滇中产区集散价 · {ddate} 实测 · <b style="color:#2563eb">0.00% 持平</b></div></div>
  <div class="kpi"><div class="l">泸西黑香葱</div><div class="v" style="color:#16a34a">{bb:.2f}</div><div class="d">元/公斤 · {ddate} 实测 · <b style="color:#16a34a">与 11-01 持平（低位横盘）</b></div></div>
  <div class="kpi"><div class="l">云南全省综合（红）</div><div class="v">3.45</div><div class="d">元/公斤 · 3.3-3.6 · 连续四日持平 · <b>与泸西收敛</b></div></div>
  <div class="kpi"><div class="l">昆明王旗营小葱</div><div class="v" style="color:#2563eb">2.50</div><div class="d">元/公斤 · 与 11-01 <b style="color:#2563eb">持平</b>（低位平台） · 量 30 吨</div></div>
  <div class="kpi"><div class="l">同比（vs 2025-11-01）</div><div class="v" style="color:#16a34a">-44.4%</div><div class="d">去年同期 6.20 → 本期 3.45</div></div>
  <div class="kpi"><div class="l">20 日实测均线</div><div class="v">{ma:.2f}</div><div class="d">元/公斤 · 现价低于均线 {gap:.1f}%</div></div>
</div>

<div class="note"><b>本期核心结论：</b>{summ}</div>

<h2>一、历史长周期回顾（近 10 年）</h2>
<div class="card">{c_decade}</div>
<table><thead><tr><th>窗口</th><th>期初</th><th>期末</th><th>涨跌</th><th>均值</th><th>最低</th><th>最高</th></tr></thead>
<tbody>{wrows}</tbody></table>
<div class="note">口径：主序列为<b>通货毛葱</b>（元/公斤），精品净葱 = 主序列 × 1.66。
10 年 CAGR <b>{cagr:.1f}%</b>，长周期中枢下移。</div>
<h3>近 36 个月</h3><div class="card">{c_36}</div>
<h3>季节指数（1.00 = 年度均值）</h3><div class="card">{c_season}</div>
<div class="note">季节规律：春峰 4-5 月（1.25 / 1.16）→ 夏谷 7-8 月（0.68 / 0.72）→ 冬旺 11-1 月（1.09-1.14）。
11 月因子升至 1.121、12 月 1.140，<b>季节性本身对四季度构成上行动力</b>；
但历史同期对比显示 2026 年 10 月末已是近五年最低（见 5.1），<b>季节性上行未必能抵消同比低基数</b>。</div>

<h2>二、天气与灾害</h2>
<div class="card">{c_wx}</div>
<table><thead><tr><th>窗口</th><th>最高温均</th><th>最低温均</th><th>累计降水</th><th>雨日</th><th>大风日</th><th>主导天气</th></tr></thead><tbody>
<tr><td>未来 3 天</td><td>{w3t}</td><td>{w3t2}</td><td>{w3p} mm</td><td>{w3r}</td><td>{w3g}</td><td>{w3d}</td></tr>
<tr><td>未来 1 周</td><td>{w7t}</td><td>{w7t2}</td><td>{w7p} mm</td><td>{w7r}</td><td>{w7g}</td><td>{w7d}</td></tr>
<tr><td>第 8-15 天</td><td>{wht}</td><td>{wht2}</td><td>{whp} mm</td><td>{whr}</td><td>{whg}</td><td>{whd}</td></tr>
</tbody></table>
<div class="warn"><b>关键转折（近端暖干、中端强降水+降温）：</b>未来 3 天泸西<b>暖干少雨</b>——累计 {w3p} mm、
最高气温 {w3t}℃、较近 30 日均值距平 {ano:+.1f}℃，气温偏高加速生长，短期供给充裕；
但 <b>11/8 前后转入强降水 + 明显降温</b>——11/8 单日 <b>27.3 mm（强降水）</b>、11/9 最高气温降至 <b>13.8℃</b>、
最低温回落至约 9.9℃，第 8-15 天窗口累计降水达 <b>{whp} mm</b>、雨日 {whr} 天。
较上期修正：前期预期的「11/7-11/8 极端低温 7-11℃」未完全兑现，实际最低约 9.9℃（11/9 前后），
但<b>强降水中心落在 11/8</b>且 11/6-11/9 连阴雨（约 4 个雨日），
<b>采收受阻 + 洗葱损耗上升 + 霜霉/灰霉病风险</b>将在第 2-3 周集中兑现，供给收缩逻辑不变。</div>
<div class="warn"><b>全国层面（中央气象台 11-03 生效预警）：</b>全网生效预警 <b>{dtot}</b> 条，
结构由上期「大风主导」切回<b>大雾主导</b>——大雾 {dfog} 条、大风 {dwind} 条、
沙尘 {ddust} 条、雷电 {dthu} 条、暴雨 {drain} 条、道路冰雪 {dice} 条。
涉及香葱主产区 <b>{dprod}</b> 条，<b>本期重大变化：核心产区邻近区域上榜</b>——
<b>红河州绿春县暴雨橙色、普洱江城暴雨红色</b>（滇南强降水外溢风险），福建漳州多地大风黄色（设施受损）；
泸西本县本轮无独立生效预警，但红河州内暴雨橙色紧邻、且 11/8 本地强降水（27.3mm）仍构成采收与运输风险。
<b>注：云南本轮已有红河州绿春暴雨橙色、普洱江城暴雨红色上榜，滇南强降水外溢风险上升</b>，短期天气风险由预报降水升级为生效预警。</div>
<h3>当前生效预警（涉及香葱主产区）</h3>
<table><thead><tr><th>区域</th><th>灾种</th><th>级别</th><th>影响</th><th>发布时间</th></tr></thead><tbody>{drows}</tbody></table>
<div class="note">全网生效预警合计 <b>{dtot}</b> 条，其中涉及主产区 <b>{dprod}</b> 条。
北方已出现<b>道路结冰 / 道路冰雪 / 暴雪</b>预警（辽宁铁岭、内蒙古呼伦贝尔），
标志北方产区进入退市通道，对云南货源的<b>南菜北运需求形成季节性支撑</b>。</div>

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
<h3>5.1 五年同期对比：2026 年 10 月末为近五年最低</h3>
<div class="card">{c_yoy}</div>
<div class="warn"><b>同比腰斩：</b>本期取得隔年<b>精确同日</b>档案（2025-11-01）——
泸西红香葱均价 6.20（6.0-6.4）、黑香葱 4.35（4.1-4.6）。
本期 3.45 / 2.96 与之相比分别为 <b>-44.4%</b> 与 -31.9%。
与更早年份相比：2024-10-29 为 5.55（-37.8%）、2023-10-30 为 5.90（-41.5%）、2022-10-30 为 4.95（-30.3%）。
<b>红香葱为近五年同期绝对最低，且是唯一跌破 4 元的一年</b>；
黑香葱本期（-31.9%）跌幅虽小于红葱，但二者同步处于近五年低位，本期红黑价差<b>由去年同期的 2.09 元重新走阔至 0.49 元</b>，
反映黑葱溢价在 10 月被压缩后于 11 月初一次性回吐。</div>
<h3>5.2 本期重点：全省综合价与泸西分区价维持收敛、黑葱补跌</h3>
<div class="card">{c_div}</div>
<div class="good"><b>收敛延续、黑葱补跌：</b>上期报告提示「全省综合价 10-30 首次跌破泸西分区价 0.40 元，
泸西 3.85 存在报价黏性、真实成交重心更低」——<b>已兑现</b>，全省综合价连续三日锁在 3.45，
泸西红香葱分区价 10-31 由 3.85 下调至 3.45 后、本期（11-02）继续持平 3.45，两者持续对齐，倒挂消除。
本期（11-02）红黑均陷入<b>低位横盘</b>：泸西黑香葱 11-01 跟跌至 2.96 后暂稳，全省综合黑葱同步锁在 2.96，
红黑价差维持 0.49 元、黑葱相对红葱的溢价已彻底消失。
这也再次印证：<b>全省综合口径对泸西分区价具有约 1 个报价日的领先性</b>，应作为泸西价格的先行指标。</div>
<h3>5.3 销地背离修复：王旗营止跌反弹、周谷堆弱势</h3>
<div class="card">{c_wq}</div>
<div class="warn"><b>销地延续低位：</b>昆明王旗营小葱批发均价维持 <b>2.50</b>（与 11-01 持平），
低位平台延续，<b>上期观察到的「量先于价」回暖信号未能延续为反转</b>——
成交量维持在 30 吨（未再缩量也未回升），说明销区采购意愿<b>仍偏谨慎、仅试探性补货</b>。
绝对量仍低于 35 吨常态，<b>尚不构成趋势反转确认</b>。
合肥周谷堆小葱延续弱势（前期 7.50 → 6.75 → 5.80 三连跌后本期仍处低位），
销地端<b>区域分化</b>明显，中间环节利润仍未明显修复。</div>
<h3>5.4 泸西多源口径分歧</h3>
<div class="card">{c_spread}</div>
<div class="warn"><b>口径分歧：</b>同一日、同一产地泸西，公开报价从 <b>2.00 到 12.00 元/公斤</b>不等，
极值价差达 <b>6.0 倍</b>（上期 9.2 倍，因本期剔除部分长期未刷新的极端挂牌而收窄）。按可信度分层：
①<b>成交价层</b>——泸西红香葱集散均价 3.45（产区菜价表，模型基准）、全省综合 3.45、
黑香葱集散均价 2.96（11-01 破位）、
惠农网地头价挂牌 3.40（与官方地头价吻合，可作交叉验证）；
②<b>推算层</b>——地头统货大宗约 4.60（国资云农源断更，按历史加成率推算，已标注）；
③<b>平台行情层</b>——一亩田/惠农网行情 2.20-2.54；
④<b>挂牌/吨价层</b>——2.00-6.36，跨度极大；
⑤<b>代办层</b>——12.00（含服务费，不可用于定价）。
判断：<b>真实成交中枢落在 3.40（地头）～4.60（水洗统货大宗）之间</b>。</div>
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
本期基准<b>维持 {br:.2f}</b>（泸西分区 11-02 实测，红香葱较 11-01 持平；黑香葱 11-01 跟跌后暂稳于 2.96），
当前现价低于 20 日实测均线 {ma:.2f}（缺口 {gap:.1f}%），均值回归项为正向，
叠加 11-12 月季节因子上行（1.026 → 1.121 → 1.140）与 11/8 起强降水+降温带来的供给收缩，
{mono}：{path}。区间为情景区间，非统计置信区间。
<b>为何第 6 档不再上行：</b>3 个月档目标日为 <b>2027-01-30</b>，虽处春节前一周的备货脉冲（+12.7%），
但季节因子在 1 月末已向 2 月（0.969）插值回落至 1.036，
两者相互抵消，导致该档与 2 个月档（目标日 2026-12-31，元旦脉冲 +4.6%）几乎持平。
真正的高点窗口在 <b>2 月上旬春节当周</b>，已超出本模型 3 个月的预测边界。
<b>较上期的整体变动</b>：起算基准（红葱）仍维持 3.45 不变，故六档<b>红葱中枢与上期基本持平</b>；
黑葱因 11-01 由 3.36 破位至 2.96，各档黑葱中枢整体下移约 <b>0.40 元</b>，
红黑价差由 0.09 重新走阔至 0.49 元，<b>黑葱相对红葱的溢价于 10 月被压缩后于 11 月初一次性回吐</b>。</div>

<h2>七、风险提示</h2>
<ul>
<li><b>基准口径风险已兑现、但黏性风险仍在：</b>泸西分区价 10-31 由 3.85 一步下调至 3.45，与全省综合价收敛，
上期提示的系统性偏高已修正。但需注意泸西分区价仍呈现「长期不动、一次性跳变」的特征
（10/26 破位前连续三日 3.85，本期破位前又连续两日 3.85），
建议继续以全省综合价作为先行指标，<b>若全省综合价继续下移而泸西不动，仍应主动下修</b>。</li>
<li><b>销地延续低位、量能不足：</b>王旗营维持 2.50（11-01 由 2.20 反弹后本期持平），但成交量仍 30 吨未回升，
属<b>试探性回补而非需求反转</b>；合肥周谷堆延续弱势。若销地量能不跟进，产地供给收缩的涨价仍难顺畅传导。</li>
<li><b>黑葱补跌的惯性风险：</b>泸西黑香葱 11-01 由 3.36 一次性破位至 2.96（-11.9%），
红黑价差由 0.09 走阔至 0.49 元，说明 10 月红葱单边下跌时黑葱的「抗跌黏性」已耗尽，
需警惕红葱在横盘后亦跟随再现一次性跳变（泸西分区价历史上多次「长期不动、一次性跳变」）。</li>
<li><b>同比低基数的双刃性：</b>2026 年 11 月初红香葱同比 -44.4%，为近五年最低。
低基数有利于反弹幅度的相对表现，但也反映<b>供给过剩是结构性的</b>（泸西复种 46.7 万亩次面积高企），
不宜简单线性外推「跌得多就会涨得多」。</li>
<li><b>口径分歧：</b>泸西当日公开报价极值差达 <b>6.0 倍</b>（2.00 ~ 12.00 元/公斤），
跨平台横比严重失真。使用时务必同口径、同品种、同规格比较。</li>
<li><b>天气风险（本期强降水落点明确）：</b>强降水中心在 <b>11/8（27.3 mm）</b>，11/9 起持续低温寡照（最低温约 9.9℃）；
且<b>红河州绿春县暴雨橙色、普洱江城暴雨红色</b>（滇南强降水外溢）紧邻核心产区，
滇东产区短时强降水对采收与运输形成直接冲击。若演变为连续 3 日以上强降水则上行幅度超预期；
反之若暖干延续，季节性上行将被供给充裕抵消。</li>
<li><b>替代竞争：</b>大葱处明显低位（北京新发地 1.80-2.00、合肥周谷堆 2.40-3.40、
北京发改委批发 1.94 元/kg），对香葱消费形成替代压制，是集散价无法上修的重要需求侧原因。</li>
<li><b>数据源断更：</b>国资云农泸西地头大宗价已连续五期（10/29-11-03）未发布，最后一次为 10-28 的 5.00，
本期地头统货大宗价 4.60 为<b>推算值</b>，已在报价表与图表中标注。建议后续补充替代实地采集源。</li>
</ul>

<h2>八、情景推演</h2>
<table><thead><tr><th>情景</th><th>触发条件</th><th>3 个月中枢</th><th>概率</th></tr></thead><tbody>
<tr><td><b>A 基准</b></td><td>泸西维持 3.45，季节性上行 + 11/6 起多雨温和兑现，销地跌幅收敛</td><td>{a3:.2f} 元/公斤</td><td>50%</td></tr>
<tr><td><b>B 上修</b></td><td>11/8 强降水+11/9 低温超预期致供给明显收缩，或南菜北运提前放量、销地反弹跟涨；
基准口径上修至地头统货大宗 4.60（较现基准 +33%）</td><td>{b3:.2f} 元/公斤</td><td>20%</td></tr>
<tr><td><b>C 下修</b></td><td>全省综合价继续下移带动泸西二次下调至 3.00（较现基准 -13%），或暖干延续 + 销地反弹乏力</td><td>{c3:.2f} 元/公斤</td><td>30%</td></tr>
</tbody></table>
<div class="note">情景中枢按<b>基准价替代法</b>推演：以 A 档 3 个月中枢 {a3:.2f} 为基数，
按替代基准 / 现基准（{br:.2f}）等比缩放——B 档替代基准为地头统货大宗 4.60、C 档为再跌至 3.00。
概率维持：情景 A 50%（基准维持 + 季节性温和上行）、B 20%（泸西暴雨黄色预警若致供给收缩则上修）、
C 30%（黑葱已破位、销地反弹但量能不足、需求侧仍弱，红葱横盘后存二次跳变风险）。
注意：本期红葱基准维持 3.45 不变、黑葱基准下修至 2.96，故红葱三档中枢绝对值与上期持平、黑葱整体下移约 0.40 元，
此处概率仅反映<b>相对路径</b>的分歧。</div>

<div class="foot">
数据来源：中央气象台（nmc.cn）、Open-Meteo 预报与归档 API、农业农村部信息中心（含证券之星转载）、
国资云农每日产地采集、青岛市城阳蔬菜水产品批发市场（cncyms.cn）、北京新发地、昆明景臻王旗营（昆明市农业农村局）、
海口市菜篮子产业集团、北京市发展和改革委员会、楚雄州发展和改革委员会、合肥周谷堆、
邯郸南大堡、宁夏中卫四季鲜（宁夏发改委）、一亩田、惠农网、
云南蔬菜主产区每日菜价、云南蔬菜综合报价。<br>
本报告由自动化任务 376dffed 生成，仅供经营参考，不构成交易建议。价格单位除特别标注外均为元/公斤。
</div>
</div></body></html>"""

a3 = FRED["rows"][5]["center"]
b3 = a3 * 4.60 / BASE_RED
c3 = a3 * 3.00 / BASE_RED
_hz = dict(disaster_top.get("hazard_stats", []))

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
    a3=a3, b3=b3, c3=c3,
)

html_path = os.path.join(OUT_DIR, "香葱行情分析_{0}.html".format(TODAY))
with open(html_path, "w", encoding="utf-8") as f:
    f.write(html)
print("[OK] 报告", html_path, len(html) // 1024, "KB")
print("红葱中枢:", BASE_RED, "→", [r["center"] for r in FRED["rows"]])
print("黑葱中枢:", BASE_BLACK, "→", [r["center"] for r in FBLK["rows"]])
print("20日均线:", FRED["ma20"])
