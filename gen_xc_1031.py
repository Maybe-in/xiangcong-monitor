# -*- coding: utf-8 -*-
"""香葱行情定时任务落盘 + 图表报告生成器（任务 376dffed）· 2026-10-31

产出：
  1) data/sources/xiangcong_2026-10-31.json  统一 schema 全量报价 + 六档预测
  2) outputs/香葱行情分析_2026-10-31.html     长周期 / 口径分歧 / 预测 图表

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

DATA_DATE = "2026-10-30"   # 最新可获取的实测报价日（当日数据次日发布）

# ============================================================ 0. 回写实测价
HIST_PATH = os.path.join(BASE_DIR, "data", "price_history.json")
hist = json.load(open(HIST_PATH, encoding="utf-8"))
hist["series"] = [s for s in hist["series"]
                  if not (s["date"] == DATA_DATE and s.get("source") == "model")]
_have = {(s["date"], s["variety"]) for s in hist["series"]}
_new = [
    {"date": DATA_DATE, "variety": "红香葱", "market": "云南产地", "price": 3.85,
     "source": "observed",
     "note": "泸西菜价红香葱 3.6-4.0 均价 3.85；较 10-29 持平，连续第三个报价日锁定 3.85"},
    {"date": DATA_DATE, "variety": "黑葱", "market": "云南产地", "price": 3.36,
     "source": "observed",
     "note": "泸西菜价黑香葱 3.1-3.6 均价 3.36；较 10-29 持平"},
    {"date": DATA_DATE, "variety": "小葱", "market": "昆明王旗营", "price": 2.50,
     "source": "observed",
     "note": "景臻·王旗营 10-30 批发均价 2.50 持平，前一日成交量回升至 30 吨（10-29 为 25 吨）"},
]
for _n in _new:
    if (_n["date"], _n["variety"]) not in _have:
        hist["series"].append(_n)
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
wx = json.load(open(os.path.join(BASE_DIR, "data", "weather_2026-10-30.json"), encoding="utf-8"))
_all = [d for d in wx["core"]["daily"] if d.get("tmax") is not None]
core_daily = [d for d in _all if d["date"] >= TODAY]      # 预测段：从今天起
if len(core_daily) < 15:                                   # 兜底
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

# 模型内部 label → 任务 schema 要求的档位名
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

WX_URL = "http://mp.weixin.qq.com/s?__biz=MzU5MTc0MTM0MA==&mid=2247595851&idx=1&sn=dbec91827d5cc2b0f30be2afdb267db0"
DH_URL = "http://mp.weixin.qq.com/s?__biz=Mzg3Mzg1MTgwNw==&mid=2247490582&idx=1&sn=a57f93fee6cc2384fd73f3ce299b1534"

# —— 泸西核心产区（10-30 实测，模型基准口径）
A(Q(DATA_DATE, "香葱", "红香葱", "云南红河州泸西县", "云南", "产地收购价",
    3.6, 4.0, 3.85, "云南蔬菜主产区每日菜价（泸西菜价表）", WX_URL,
    "本期模型基准。泸西红香葱 3.6-4.0、均价 3.85。较 10-29 持平，为 10-26 破位后连续第三个报价日锁定 3.85"))
A(Q(DATA_DATE, "香葱", "黑香葱", "云南红河州泸西县", "云南", "产地收购价",
    3.1, 3.6, 3.36, "云南蔬菜主产区每日菜价（泸西菜价表）", WX_URL,
    "泸西黑香葱 3.1-3.6、均价 3.36，与 10-29、10-26 连续三日持平"))
A(Q(DATA_DATE, "香葱", "红葱", "云南玉溪市通海县", "云南", "产地收购价",
    3.6, 4.0, 3.80, "云南蔬菜主产区每日菜价（通海菜价表）", WX_URL,
    "通海红葱 3.6-4.0，与泸西完全同区间"))
A(Q(DATA_DATE, "香葱", "黑葱", "云南玉溪市通海县", "云南", "产地收购价",
    3.1, 3.6, 3.35, "云南蔬菜主产区每日菜价（通海菜价表）", WX_URL,
    "通海黑葱 3.1-3.6"))

# —— 全省综合（本期关键：由滞后转为领跌）
A(Q(DATA_DATE, "香葱", "红香葱", "云南产地综合交易价（全省）", "云南", "产地批发价",
    3.3, 3.6, 3.45, "云南蔬菜综合报价（10-30）", DH_URL,
    "全省综合交易价红香葱 3.3-3.6，较 10-29 的 3.6-4.0 中枢下移约 9%；官方措辞明确列出「红香葱、黑葱价格下调」"))
A(Q(DATA_DATE, "香葱", "黑葱", "云南产地综合交易价（全省）", "云南", "产地批发价",
    3.1, 3.5, 3.30, "云南蔬菜综合报价（10-30）", DH_URL,
    "全省综合交易价黑葱 3.1-3.5，较 10-29 的 3.1-3.6 同步下调"))
A(Q("2026-10-29", "香葱", "红香葱", "云南产地综合交易价（全省）", "云南", "产地批发价",
    3.6, 4.0, 3.80, "云南蔬菜综合报价（10-29 档案）", "", "上期全省综合价，用于计算本次下调幅度"))
A(Q("2026-10-26", "香葱", "红香葱", "云南产地综合交易价（全省）", "云南", "产地批发价",
    4.4, 5.0, 4.70, "云南蔬菜综合报价（10-26 档案）", "",
    "10-26 全省综合报价 4.4-5.0，当时仍显著高于泸西 3.85（未同步下跌）"))

# —— 泸西地头大宗价（权威实地采集源）
A(Q("2026-10-28", "香葱", "小葱（统货）", "红河州泸西县（地头大宗价）", "云南", "产地地头价",
    4.5, 5.5, 5.00, "国资云农（云南国资云农信息团队每日产地采集）", "",
    "10-28 大宗价 5.00（区间 4.5-5.5）较 10-27 的 4.90 涨 2.0%。10-30 该源本次检索未更新，沿用 10-28 值"))
A(Q("2026-10-27", "香葱", "小葱（统货）", "红河州泸西县（地头大宗价）", "云南", "产地地头价",
    4.5, 5.5, 4.90, "国资云农", "", "10-27 大宗价 4.90，用于计算真实环比"))

# —— 全国产地横截面（一亩田全国小葱价格行情，元/斤 ×2 折算）
A(Q(DATA_DATE, "小葱", "小葱", "云南红河泸西县（平台行情）", "云南", "产地批发价",
    2.62, 2.62, 2.62, "一亩田·全国小葱价格行情参考", "https://www.ymt.com/supply/51682854",
    "挂牌 1.31 元/斤 ×2 折算，涨跌 0.0，连续持平"))
A(Q(DATA_DATE, "四季小葱", "四季小葱", "云南红河泸西县（平台行情）", "云南", "产地批发价",
    2.28, 2.28, 2.28, "一亩田·全国小葱价格行情参考", "https://www.ymt.com/supply/51682854",
    "挂牌 1.14 元/斤 ×2 折算，涨跌 0.0"))
A(Q(DATA_DATE, "四季小葱", "四季小葱", "河南平顶山汝州市", "河南", "产地批发价",
    2.38, 2.38, 2.38, "一亩田·全国小葱价格行情参考", "https://www.ymt.com/supply/51682854",
    "挂牌 1.19 元/斤 ×2 折算，涨跌 0.0"))
A(Q(DATA_DATE, "小葱", "小葱", "河南平顶山汝州市", "河南", "产地批发价",
    2.12, 2.12, 2.12, "一亩田·全国小葱价格行情参考", "https://www.ymt.com/supply/51682854",
    "挂牌 1.06 元/斤 ×2 折算"))
A(Q(DATA_DATE, "小葱", "小葱", "广西柳州柳江区", "广西", "产地批发价",
    3.00, 3.00, 3.00, "一亩田·全国小葱价格行情参考", "https://www.ymt.com/supply/51682854",
    "挂牌 1.50 元/斤 ×2 折算，涨跌 -0.01，本期全国产地中唯二走弱"))
A(Q(DATA_DATE, "四季小葱", "四季小葱", "广西柳州柳江区", "广西", "产地批发价",
    2.96, 2.96, 2.96, "一亩田·全国小葱价格行情参考", "https://www.ymt.com/supply/51682854",
    "挂牌 1.48 元/斤 ×2 折算，涨跌 -0.01"))
A(Q(DATA_DATE, "四季小葱", "四季小葱", "河南焦作武陟县", "河南", "产地批发价",
    1.80, 1.80, 1.80, "一亩田·全国小葱价格行情参考", "https://www.ymt.com/supply/51682854",
    "挂牌 0.90 元/斤 ×2 折算，全国产地最低档"))
A(Q(DATA_DATE, "小葱", "小葱", "河南焦作武陟县", "河南", "产地批发价",
    2.52, 2.52, 2.52, "一亩田·全国小葱价格行情参考", "https://www.ymt.com/supply/51682854",
    "挂牌 1.26 元/斤 ×2 折算"))
A(Q(DATA_DATE, "四季小葱", "四季小葱", "河北邯郸永年区", "河北", "产地批发价",
    2.50, 2.50, 2.50, "一亩田·全国小葱价格行情参考", "https://www.ymt.com/supply/51682854",
    "挂牌 1.25 元/斤 ×2 折算"))
A(Q(DATA_DATE, "小葱", "小葱", "河北邯郸永年区", "河北", "产地批发价",
    2.58, 2.58, 2.58, "一亩田·全国小葱价格行情参考", "https://www.ymt.com/supply/51682854",
    "挂牌 1.29 元/斤 ×2 折算"))

# —— 其他产区挂牌（非成交，仅作区间参考）
A(Q(DATA_DATE, "香葱", "黑葱/红葱/小香葱", "云南红河泸西县", "云南", "产地收购价",
    4.00, 4.00, 4.00, "惠农网产地行情（互惠果蔬）", "https://www.cnhnb.com/p/xiaocong-0-25-0-0-2/",
    "挂牌 4000 元/吨 = 4.00 元/公斤，吨价口径"))
A(Q(DATA_DATE, "香葱", "云南高质量小香葱（批发）", "云南红河泸西县", "云南", "产地收购价",
    7.00, 7.00, 7.00, "一亩田", "https://www.ymt.com/supplylist/search-25-7300/pn203",
    "挂牌 3.50 元/斤 ×2 折算，高等级"))
A(Q(DATA_DATE, "香葱", "小葱（代发代办）", "云南红河泸西县", "云南", "产地收购价",
    5.20, 5.20, 5.20, "一亩田", "https://www.ymt.com/supplylist/search-25-7300/pn203",
    "挂牌 2.60 元/斤 ×2 折算，含代办服务"))
A(Q(DATA_DATE, "四季小葱", "四季小香葱", "云南红河泸西县", "云南", "产地收购价",
    4.00, 4.00, 4.00, "一亩田", "https://www.ymt.com/supplylist/search-25-7300/pn203",
    "挂牌 2.00 元/斤 ×2 折算"))
A(Q(DATA_DATE, "小葱", "小葱（产地直供）", "云南红河泸西县", "云南", "产地收购价",
    4.00, 4.00, 4.00, "一亩田", "https://www.ymt.com/supplylist/search-25-7300/pn203",
    "挂牌 2.00 元/斤 ×2 折算"))
A(Q(DATA_DATE, "小葱", "云南小香葱", "云南红河泸西县", "云南", "产地收购价",
    11.00, 11.00, 11.00, "一亩田", "https://www.ymt.com/supplylist/search-25-7300/pn203",
    "挂牌 5.50 元/斤 ×2 折算，零星高报，离散度大"))
A(Q(DATA_DATE, "黑葱", "大量标准小黑葱（代发）", "云南红河泸西县", "云南", "产地批发价",
    2.30, 2.30, 2.30, "一亩田", "https://www.ymt.com/supplylist/search-25-7300/pn203",
    "挂牌 2.30 元/公斤"))
A(Q(DATA_DATE, "香葱", "黑葱/红葱/白葱（长期出售）", "云南红河泸西县", "云南", "产地批发价",
    3.00, 3.00, 3.00, "一亩田", "https://www.ymt.com/supplylist/search-25-7300/pn203",
    "挂牌 3.00 元/公斤"))
A(Q(DATA_DATE, "香葱", "小香葱/红葱/香葱", "云南红河泸西县", "云南", "产地地头价",
    1.60, 1.60, 1.60, "惠农网产地行情", "https://www.cnhnb.com/gongying/4510986",
    "挂牌 0.80 元/斤 ×2 折算，10000 斤起批，地头批发"))
A(Q(DATA_DATE, "四季小葱", "四季小香葱", "云南红河泸西县", "云南", "产地收购价",
    6.00, 6.00, 6.00, "惠农网产地行情", "https://www.cnhnb.com/gongying/4510986",
    "挂牌 3.00 元/斤 ×2 折算，有成交记录"))
A(Q(DATA_DATE, "香葱", "黑葱/红葱(火葱)/白葱", "云南红河泸西县", "云南", "产地收购价",
    3.80, 3.80, 3.80, "惠农网产地行情", "https://www.cnhnb.com/gongying/4510986",
    "挂牌 1.90 元/斤 ×2 折算"))
A(Q(DATA_DATE, "小葱", "小葱/黑葱", "云南红河泸西县", "云南", "产地收购价",
    1.20, 1.20, 1.20, "惠农网产地行情", "https://www.cnhnb.com/gongying/4510986",
    "挂牌 0.60 元/斤 ×2 折算"))
A(Q(DATA_DATE, "香葱", "香葱（平台行情）", "云南红河泸西县", "云南", "产地收购价",
    2.62, 2.62, 2.62, "惠农网行情中心", "https://www.cnhnb.com/hangqing/cdlist-2000478-6222-25-0-0-1/",
    "惠农网行情频道 10-27 泸西香葱 1.31 元/斤 ×2 折算"))
A(Q(DATA_DATE, "香葱", "红葱/香葱/小葱/火葱", "云南大理弥渡县", "云南", "产地批发价",
    4.80, 4.80, 4.80, "一亩田", "https://www.ymt.com/supplylist/search-25-7300/pn14",
    "挂牌 2.40 元/斤 ×2 折算，2026 年新货"))
A(Q(DATA_DATE, "香葱", "精品胭脂葱", "云南大理宾川县", "云南", "产地收购价",
    7.00, 7.00, 7.00, "惠农网产地行情", "https://www.cnhnb.com/hangqing/cdlist-2000478-6222-25-0-0-1/",
    "挂牌 3.50 元/斤 ×2 折算"))
A(Q(DATA_DATE, "香葱", "白香葱/红香葱", "云南玉溪通海县", "云南", "产地批发价",
    3.20, 3.20, 3.20, "一亩田", "https://www.ymt.com/supplylist/search-25-7300/pn14",
    "挂牌 3.20 元/公斤"))

# —— 销区批发（10-30 实测）
A(Q(DATA_DATE, "小葱", "小葱", "昆明景臻王旗营蔬菜批发市场", "云南", "销地批发价",
    2.50, 2.50, 2.50, "昆明市农业农村局 / 景臻·王旗营", "http://mp.weixin.qq.com/s?__biz=MzI2NzIyNTU1Ng==&mid=2247513912&idx=1&sn=a70f6c7a35a5cafb6be6f254c3dcbfb7",
    "10-30 批发均价 2.50 持平，但前一日成交量由 25 吨回升至 30 吨（+20%），结束缩量。综合平均价 4.22、总吨位 2770"))
A(Q(DATA_DATE, "香葱", "香葱", "青岛市城阳蔬菜水产品批发市场", "山东", "销地批发价",
    7.0, 9.0, 8.00, "青岛市城阳蔬菜水产品批发市场", "http://www.cncyms.cn/",
    "官网当日 高 9.00 / 中 8.00 / 低 7.00 元/公斤，连续多日持平，为可获取的高位销区报价"))
A(Q(DATA_DATE, "香葱", "香葱", "北京新发地农产品批发市场", "北京", "销地批发价",
    6.6, 9.0, 7.80, "北京新发地每日价格行情", "http://dir.xinfadi.com.cn/",
    "10-30 官方口径 最低 3.30 / 平均 3.90 / 最高 4.50 元/斤，×2 折算，与 10-29 完全一致"))
A(Q(DATA_DATE, "小葱", "净小葱", "北京新发地农产品批发市场", "北京", "销地批发价",
    2.6, 5.0, 3.80, "北京新发地每日价格行情", "http://dir.xinfadi.com.cn/",
    "10-30 净小葱 最低 1.30 / 平均 1.90 / 最高 2.50 元/斤，×2 折算；与香葱不同规格"))
A(Q(DATA_DATE, "小葱", "小葱", "安徽合肥周谷堆农产品批发市场", "安徽", "销地批发价",
    6.75, 6.75, 6.75, "农业农村部信息中心", "https://futures.stockstar.com/IG2026103000029057.shtml",
    "本期新增数据源，华东销区"))
A(Q(DATA_DATE, "小葱", "小葱", "浙江安吉农副产品综合批发市场", "浙江", "销地批发价",
    5.0, 7.0, 6.00, "安吉农副产品综合批发市场", "",
    "10-30 公示价 2.5-3.5 元/斤 ×2 折算，本期新增数据源"))
A(Q(DATA_DATE, "香葱", "香葱（云南货源）", "邯郸南大堡蔬菜批发市场", "河北", "销地批发价",
    6.0, 7.0, 6.40, "邯郸南大堡蔬菜批发市场官方平台", "http://mp.weixin.qq.com/s?__biz=MzI2MzI3MjAwMw==&mid=2247503271&idx=1&sn=dff5b2d53093dbc47f6c93a065080ef2",
    "10-30 报价 高 3.50 / 中 3.20 / 低 3.00 元/斤，×2 折算；产地标注「云」"))
A(Q(DATA_DATE, "小葱", "小葱（香/钢·本地货）", "邯郸南大堡蔬菜批发市场", "河北", "销地批发价",
    1.4, 2.8, 2.00, "邯郸南大堡蔬菜批发市场官方平台", "http://mp.weixin.qq.com/s?__biz=MzI2MzI3MjAwMw==&mid=2247503271&idx=1&sn=dff5b2d53093dbc47f6c93a065080ef2",
    "10-30 报价 高 1.40 / 中 1.00 / 低 0.70 元/斤，×2 折算；与云南货价差约 3.2 倍"))
A(Q(DATA_DATE, "香葱", "香葱", "宁夏中卫四季鲜农产品批发市场", "宁夏", "销地批发价",
    10.0, 12.0, 11.00, "宁夏发改委价格监测中心", "https://fzggw.nx.gov.cn/sjfb/jcsj/",
    "原始报价 5-6 元/斤 ×2 折算。西北远端销区，全国最高档（本期沿用）"))

# —— 21food 各地葱批发价（口径混杂，含大葱，仅作区域离散参考）
_TF = "食品商务网 21food 各地葱批发价（10-30，葱大类口径混杂，含大葱）"
TF_URL = "https://wap.21food.cn/price/product/861.html"
for mkt, prov, v in [
        ("新疆绿珠九鼎农产品经营管理有限公司", "新疆", 3.0),
        ("山东喜地农产品市场管理有限公司", "山东", 3.0),
        ("山东青岛黄河路农产品批发市场", "山东", 2.8),
        ("滕州市农副产品物流中心有限公司", "山东", 3.4),
        ("甘肃省定西市安定马铃薯综合交易中心", "甘肃", 3.4),
        ("甘肃邦农农产品批发市场", "甘肃", 1.5),
        ("黑龙江省华博农产品市场有限公司", "黑龙江", 1.9),
        ("新疆兵团第五师三和农副产品综合批发市场", "新疆", 5.0),
        ("龙门实业（集团）有限公司西三街市场", "重庆", 9.0)]:
    A(Q(DATA_DATE, "葱", "葱（大类）", mkt, prov, "销地批发价", v, v, v, _TF, TF_URL,
      "21food 葱大类报价，未区分香葱/大葱，离散度参考，不建议用于香葱定价"))

# —— 替代品与零售价参考
A(Q(DATA_DATE, "大葱", "大葱", "北京顺鑫石门国际农产品批发市场", "北京", "销地批发价",
    2.00, 2.00, 2.00, "农业农村部信息中心", "https://futures.stockstar.com/IG2026103000029004.shtml",
    "替代品参考，非香葱，北方大葱低位"))
A(Q(DATA_DATE, "大葱", "大葱", "安徽合肥周谷堆农产品批发市场", "安徽", "销地批发价",
    3.30, 3.30, 3.30, "农业农村部信息中心", "https://futures.stockstar.com/IG2026103000029057.shtml", "替代品参考"))
A(Q(DATA_DATE, "大葱", "大葱（本地）", "寿光本地蔬菜价格发布", "山东", "产地批发价",
    1.40, 1.40, 1.40, "寿光本地蔬菜价格发布（10-30）", "",
    "原始报价 0.70 元/斤 ×2 折算，较昨日 0.70 持平，北方大葱供给宽松"))
A(Q(DATA_DATE, "大葱", "大葱（零售·中上等）", "云南楚雄州市场", "云南", "零售价",
    12.00, 12.00, 12.00, "楚雄州发展和改革委员会", "https://fgw.cxz.gov.cn/info/1280/200036.htm",
    "零售价口径（市场中上等综合平均价），与批发价不可横比；较前日持平"))

# —— 历史同期档案（同比基准）
A(Q("2024-10-29", "香葱", "红香葱", "云南红河州泸西县（历史同期档案）", "云南", "产地收购价",
    5.1, 6.0, 5.55, "云南蔬菜主产区每日菜价（2024 档案）", "", "两年前同期：红香葱 5.1-6.0 均价 5.55，较今日 3.85 同比 -30.6%"))
A(Q("2024-10-29", "香葱", "黑香葱", "云南红河州泸西县（历史同期档案）", "云南", "产地收购价",
    7.5, 8.4, 8.00, "云南蔬菜主产区每日菜价（2024 档案）", "", "两年前同期：黑香葱 7.5-8.4 均价 8.00，较今日 3.36 同比 -58.0%"))

SUMMARY = (
    "泸西分区报价连续第三个报价日锁死在 3.85（红）/ 3.36（黑），但内部结构已变："
    "全省综合交易价红香葱由 3.6-4.0 下调至 {0}（中枢 {1}）、黑葱降至 3.1-3.5（{2}），"
    "官方措辞明确「红香葱、黑葱价格下调」，全省报价首次跌破泸西分区价（{3}），"
    "完成从 10-26 的「滞后 0.85 元」到 10-29 的「趋同」再到 10-30 的「领跌 0.40 元」的反超。"
    "与此同时销地端出现首个暖信号：昆明王旗营小葱维持 {4:.2f}，"
    "前一日成交量由 25 吨回升至 30 吨（+20%），结束连续缩量。"
    "判断为<b>产区价格滞涨、全省口径领跌、销区需求试探性回暖</b>的三重结构，"
    "泸西 3.85 的横盘更多体现为报价黏性而非真实企稳。"
    "天气上泸西未来 3 天暖干多大风（累计 {5} mm、最高 {6}℃、距平 {7:+.1f}℃），短期供给充裕；"
    "但 {8} 起转入多雨寡照——11/7 单日 {9} mm、11/8 达 {10} mm（连续两日强降水），"
    "最低气温 11/10 跌至 {11}℃，第 2-4 周供给收缩风险仍是本期预测上行的核心驱动。"
    "六档中枢（精品净葱/集散价口径）：{12} 元/公斤。"
).format("3.3-3.6", 3.45, 3.30, "低 0.40", 2.50,
         w3.get("precip_total"), w3.get("tmax_avg"),
         (w3.get("tmax_avg") or 0) - (clim.get("tmax_mean") or 0),
         "11/6", 25.2, 21.0, 9.9,
         " → ".join(str(f["center"]) for f in FORECASTS))

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
    """本期重点：全省综合价 vs 泸西分区价 分歧演化。"""
    pts = [("10-26", 3.85, 4.70), ("10-29", 3.85, 3.80), ("10-30", 3.85, 3.45)]
    ml, mr, mt, mb = 60, 130, 36, 44
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
        col = "#16a34a" if diff < 0 else "#dc2626"
        g.append('<text x="{0:.1f}" y="{1}" font-size="11" fill="{2}" font-weight="600" text-anchor="middle">差 {3:+.2f}</text>'.format(
            x, hh + 12, col, diff))
        g.append('<text x="{0:.1f}" y="{1}" font-size="11" fill="#6b7280" text-anchor="middle">{2}</text>'.format(x, hh - mb + 60, d))
    g.append('<text x="{0}" y="{1}" font-size="11.5" fill="#2563eb">━ 泸西分区价（模型基准）</text>'.format(ml + 6, mt - 14))
    g.append('<text x="{0}" y="{1}" font-size="11.5" fill="#dc2626">┅ 云南全省综合交易价</text>'.format(ml + 190, mt - 14))
    g.append("</svg>")
    return "".join(g)


def chart_wq():
    """王旗营：价格 + 成交量（双线）。"""
    pts = [("10-25", 3.5, 35), ("10-26", 3.5, 35), ("10-27", 3.0, 35),
           ("10-28", 2.5, 35), ("10-29", 2.5, 25), ("10-30", 2.5, 30)]
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


def chart_luxi_spread():
    """泸西多源口径分歧。"""
    pts = [("一亩田·云南小香葱挂牌(5.50元/斤)", 11.00),
           ("一亩田·高质量小香葱挂牌(3.50元/斤)", 7.00),
           ("惠农网·宾川精品胭脂葱(3.50元/斤)", 7.00),
           ("惠农网·四季小香葱挂牌(3.00元/斤)", 6.00),
           ("一亩田·代发代办挂牌(2.60元/斤)", 5.20),
           ("国资云农·地头大宗成交(10-28)", 5.00),
           ("一亩田·四季小香葱挂牌(2.00元/斤)", 4.00),
           ("惠农网·黑红小香葱吨价(4000元/吨)", 4.00),
           ("泸西·集散均价 红香葱(模型基准)", 3.85),
           ("惠农网·黑红白葱挂牌(1.90元/斤)", 3.80),
           ("云南全省综合交易价 红香葱", 3.45),
           ("一亩田·通海白/红香葱挂牌", 3.20),
           ("一亩田·长期出售黑红白葱", 3.00),
           ("一亩田·平台行情 小葱(1.31元/斤)", 2.62),
           ("惠农网行情·泸西香葱(1.31元/斤)", 2.62),
           ("惠农网·小葱黑葱挂牌(0.60元/斤)", 1.20)]
    pts.sort(key=lambda x: -x[1])
    ml, mt = 230, 34
    hi = max(v for _, v in pts) * 1.25
    row_h = 30
    g = ['<svg viewBox="0 0 {0} {1}" class="cv">'.format(W, mt + row_h * len(pts) + 16)]
    g.append('<rect width="{0}" height="{1}" fill="#fbfcfe"/>'.format(W, mt + row_h * len(pts) + 16))
    for i, (name, v) in enumerate(pts):
        y = mt + i * row_h
        bw = (W - ml - 90) * v / hi
        c = "#dc2626" if v >= 4.8 else ("#2563eb" if v >= 3.8 else "#16a34a")
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


base_row = ("<tr class='base'><td>当前基准（10-30 实测）</td><td>—</td><td>{0:.2f}</td>"
            "<td>—</td><td>{1:.2f}</td><td>—</td><td>—</td><td>—</td><td>基准</td></tr>").format(BASE_RED, BASE_BLACK)
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
  <div class="kpi"><div class="l">泸西模型基准（红香葱）</div><div class="v">{br:.2f}</div><div class="d">元/公斤 · 滇中产区集散价 · 10-30 实测 · 连续三日持平</div></div>
  <div class="kpi"><div class="l">泸西黑香葱</div><div class="v">{bb:.2f}</div><div class="d">元/公斤 · 10-30 实测 · 3.1-3.6 区间</div></div>
  <div class="kpi"><div class="l">云南全省综合（红）</div><div class="v" style="color:#16a34a">3.45</div><div class="d">元/公斤 · 3.3-3.6 · 较 10-29 <b>-9.2%</b></div></div>
  <div class="kpi"><div class="l">昆明王旗营小葱</div><div class="v">2.50</div><div class="d">元/公斤 · 价持平 · <b style="color:#dc2626">量 25→30 吨 +20%</b></div></div>
  <div class="kpi"><div class="l">全国销地批发（城阳）</div><div class="v">8.00</div><div class="d">元/公斤 · 青岛城阳 10-30 · 持平</div></div>
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
当前 10 月因子 1.026，11 月升至 1.121、12 月 1.140，<b>季节性本身对四季度构成上行动力</b>。</div>

<h2>二、天气与灾害</h2>
<div class="card">{c_wx}</div>
<table><thead><tr><th>窗口</th><th>最高温均</th><th>最低温均</th><th>累计降水</th><th>雨日</th><th>大风日</th><th>主导天气</th></tr></thead><tbody>
<tr><td>未来 3 天</td><td>{w3t}</td><td>{w3t2}</td><td>{w3p} mm</td><td>{w3r}</td><td>{w3g}</td><td>{w3d}</td></tr>
<tr><td>未来 1 周</td><td>{w7t}</td><td>{w7t2}</td><td>{w7p} mm</td><td>{w7r}</td><td>{w7g}</td><td>{w7d}</td></tr>
<tr><td>第 8-15 天</td><td>{wht}</td><td>{wht2}</td><td>{whp} mm</td><td>{whr}</td><td>{whg}</td><td>{whd}</td></tr>
</tbody></table>
<div class="note"><b>关键转折（较上期进一步确认）：</b>未来 3 天泸西<b>暖干、多大风</b>——累计 {w3p} mm、
最高气温 {w3t}℃、较近 30 日均值距平 {ano:+.1f}℃、8 级以上大风 {w3g} 天、最大风速 {w3wind} m/s，
气温偏高加速生长，短期供给充裕；
但 <b>11/6 起转入多雨寡照</b>——11/6 至 11/13 共 {whr} 个雨日、累计 {whp} mm，
其中 <b>11/7 单日 25.2 mm、11/8 达 21.0 mm</b>（连续两日达到强降水阈值），
并伴随剧烈降温：最高气温由 11/4 的 26.0℃ 降至 11/8 的 16.5℃（四日降幅 9.5℃），
最低气温 11/9 跌至 10.3℃、11/10 进一步降至 9.9℃。
<b>采收受阻 + 洗葱损耗上升 + 根腐/霜霉病风险</b>将在第 2-4 周集中兑现。</div>
<div class="warn"><b>全国层面（中央气象台生效预警）：</b>全网生效预警 <b>{dtot}</b> 条，
结构高度集中于<b>大雾</b>（{dfog} 条），另有大风 {dwind} 条、暴雨 {drain} 条、道路结冰 {dice} 条。
唯一暴雨预警在<b>云南临沧临翔区（橙色）</b>，位于滇西，<b>核心产区泸西（滇东）不受直接影响</b>；
但<b>云南曲靖富源县大雾橙色</b>紧邻泸西外运通道，对滇东至黔桂的陆运时效构成扰动。</div>
<h3>当前生效预警（涉及香葱主产区）</h3>
<table><thead><tr><th>区域</th><th>灾种</th><th>级别</th><th>影响</th><th>发布时间</th></tr></thead><tbody>{drows}</tbody></table>
<div class="note">全网生效预警合计 <b>{dtot}</b> 条，其中涉及主产区 <b>{dprod}</b> 条。
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
<h3>5.1 本期重点：全省综合价反超泸西分区价（由滞后转为领跌）</h3>
<div class="card">{c_div}</div>
<div class="warn"><b>结构反转：</b>全省综合交易价与泸西分区价的关系在本期完成三级跳——
<b>10-26</b> 全省 4.70 高出泸西 3.85 达 <b>+0.85 元</b>（当时泸西率先破位、全省尚未同步）；
<b>10-29</b> 全省降至 3.80，与泸西 3.85 基本<b>趋同</b>（差 -0.05）；
<b>10-30</b> 全省进一步降至 <b>3.45</b>，反而低于泸西 0.40 元，<b>首次出现倒挂</b>。
官方措辞亦由「小香葱平稳」转为明确列出「<b>红香葱、黑葱价格下调</b>」。
判断：泸西分区报价的 3.85 已出现<b>报价黏性</b>——连续三个报价日分文未动，
而更具代表性的全省综合口径持续下移，说明<b>真实成交重心低于 3.85</b>。
这对预测构成<b>下行修正压力</b>，是本期最主要的模型风险（见第八章情景 C）。</div>
<h3>5.2 销地暖信号：王旗营结束缩量</h3>
<div class="card">{c_wq}</div>
<div class="good"><b>首个需求侧暖信号：</b>昆明王旗营小葱批发均价维持 <b>2.50</b> 元/公斤（10-28 起连续三日），
但<b>前一日成交量由 25 吨回升至 30 吨（+20%）</b>，结束 10-28→10-29 的缩量（-28.6%）。
价格未创新低而量能回补，通常对应<b>销区库存去化接近尾声、采购试探性恢复</b>。
需注意：该回升仍属单日数据，且绝对水平（30 吨）仍低于 10 月中上旬的 35 吨常态，
尚不足以确认趋势反转，但已足以否定「需求持续恶化」的线性外推。</div>
<h3>5.3 泸西多源口径分歧</h3>
<div class="card">{c_spread}</div>
<div class="warn"><b>口径分歧：</b>同一日、同一产地泸西，公开报价从 <b>1.20 到 11.00 元/公斤</b>不等，
极值价差达 <b>9.2 倍</b>。按可信度分层：
①<b>成交价层</b>（可信度最高）——泸西集散均价 3.85（产区菜价表，模型基准）、
全省综合 3.45、国资云农地头大宗 5.00（10-28）；
②<b>平台行情层</b>（中等，算法汇总挂牌）——一亩田/惠农网行情 2.62，持续横置；
③<b>挂牌/吨价层</b>（非成交、长期不刷新）——1.20-11.00，跨度极大；
④<b>代办层</b>（含服务费，不可用于定价）——5.20。
判断：<b>真实成交中枢落在 3.45（全省综合）～5.00（地头大宗）之间</b>。</div>
<h3>5.4 全量报价明细（{n} 条）</h3>
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
六档呈<b>单调递增</b>：{path}。区间为情景区间，非统计置信区间。
<b>但需注意</b>：模型基准沿用泸西分区 3.85，而全省综合已跌至 3.45，
若下期泸西分区向全省收敛，本期六档中枢整体偏高约 0.40 元/公斤。</div>

<h2>七、风险提示</h2>
<ul>
<li><b>基准口径风险（本期最高）：</b>泸西分区价 3.85 连续三日未动，而全省综合价同期由 4.70 降至 3.45（累计 -26.6%），
两者已倒挂 0.40 元。若泸西分区报价存在黏性或滞后，<b>本期预测系统性偏高</b>。
建议同时跟踪全省综合口径，一旦泸西下修至 3.45 附近，六档中枢应整体下移约 0.40 元/公斤。</li>
<li><b>口径分歧（持续）：</b>泸西当日公开报价极值差达 <b>9.2 倍</b>（1.20 ~ 11.00 元/公斤），
跨平台横比严重失真。使用时务必同口径、同品种、同规格比较。</li>
<li><b>销地回暖未确认：</b>王旗营成交量单日回升 20% 但价格仍处 2.50 低位、绝对量低于 35 吨常态，
属<b>量先于价</b>的试探信号，需连续 2-3 日确认，不宜据此断言需求反转。</li>
<li><b>天气风险：</b>11/6-11/13 多雨寡照（累计 {whp} mm、含 2 个强降水日）+ 11/9 起最低温跌破 10℃。
若演变为连续 3 日以上强降水则上行幅度超预期；反之若暖干延续，季节性上行将被供给充裕抵消。</li>
<li><b>替代竞争：</b>大葱处明显低位（北京顺鑫石门 2.00、山东寿光本地 1.40、邯郸大葱钢葱 1.2-1.8），
对香葱消费形成替代压制，是集散价迟迟无法上修的重要需求侧原因。</li>
<li><b>下行风险：</b>2027 春节在 2/6，节前备货高峰前若暖冬延续、单产超预期，2 月档存在回落可能；
平台行情价长期横置在 2.62，若真实成交向其收敛则本期预测显著偏高。</li>
</ul>

<h2>八、情景推演</h2>
<table><thead><tr><th>情景</th><th>触发条件</th><th>3 个月中枢</th><th>概率</th></tr></thead><tbody>
<tr><td><b>A 基准</b></td><td>泸西分区维持 3.85，季节性上行 + 11/6 起多雨温和兑现</td><td>{a3:.2f} 元/公斤</td><td>50%</td></tr>
<tr><td><b>B 上修</b></td><td>集散价向地头大宗价收敛（上修至 5.00），或多雨超预期演变为连续强降水</td><td>{b3:.2f} 元/公斤</td><td>25%</td></tr>
<tr><td><b>C 下修</b></td><td>泸西分区向全省综合收敛（下修至 3.45），或暖干延续、销区需求走弱</td><td>{c3:.2f} 元/公斤</td><td>25%</td></tr>
</tbody></table>
<div class="note">较上期调整：情景 C 概率由 15% 上调至 25%——依据全省综合价首次跌破泸西分区价的结构反转；
情景 A 由 55% 下调至 50%；情景 B 由 30% 下调至 25%。</div>

<div class="foot">
数据来源：中央气象台（nmc.cn）、Open-Meteo 预报与归档 API、农业农村部信息中心（含证券之星转载）、
国资云农每日产地采集、青岛市城阳蔬菜水产品批发市场（cncyms.cn）、北京新发地、昆明景臻王旗营（昆明市农业农村局）、
楚雄州发展和改革委员会、合肥周谷堆、浙江安吉农批、邯郸南大堡、一亩田、惠农网、食品商务网（21food）、
云南蔬菜主产区每日菜价、云南蔬菜综合报价。<br>
本报告由自动化任务 376dffed 生成，仅供经营参考，不构成交易建议。价格单位除特别标注外均为元/公斤。
</div>
</div></body></html>"""

a3 = FRED["rows"][5]["center"]
b3 = a3 * 5.00 / BASE_RED
c3 = a3 * 3.45 / BASE_RED
_hz = dict(disaster_top.get("hazard_stats", []))

html = HTML.format(
    css=CSS, today=TODAY, gen=GEN, ddate=DATA_DATE, summ=SUMMARY, wxgen=WX_GEN,
    br=BASE_RED, bb=BASE_BLACK, ma=FRED["ma20"], gap=(FRED["ma20"] / BASE_RED - 1) * 100,
    c_decade=chart_decade(), wrows="".join(wrow(windows[m]) for m in (12, 24, 36, 60, 120)),
    cagr=windows[120]["cagr"], c_36=chart_36m(), c_season=chart_season(),
    c_wx=chart_weather(),
    w3t=w3.get("tmax_avg"), w3t2=w3.get("tmin_avg"), w3p=w3.get("precip_total"),
    w3r=w3.get("rainy_days"), w3g=w3.get("gale_days"), w3d=w3.get("dominant"),
    w3wind=w3.get("wind_max"),
    w7t=w7.get("tmax_avg"), w7t2=w7.get("tmin_avg"), w7p=w7.get("precip_total"),
    w7r=w7.get("rainy_days"), w7g=w7.get("gale_days"), w7d=w7.get("dominant"),
    wht=wh.get("tmax_avg"), wht2=wh.get("tmin_avg"), whp=wh.get("precip_total"),
    whr=wh.get("rainy_days"), whg=wh.get("gale_days"), whd=wh.get("dominant"),
    ano=(w3.get("tmax_avg") or 0) - (clim.get("tmax_mean") or 0),
    drows=d_rows, dtot=disaster_top.get("total", 0), dprod=len(prod_hits),
    dfog=_hz.get("大雾", 0), dwind=_hz.get("大风", 0), drain=_hz.get("暴雨", 0),
    dice=_hz.get("道路结冰", 0),
    varieties=varieties, cultivars=cultivars, provs=prov_html,
    c_cross=chart_cross(), c_div=chart_diverge(), c_wq=chart_wq(), c_spread=chart_luxi_spread(),
    n=len(QUOTES), qrows="".join(qrows),
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
print("20日均线:", FRED["ma20"])
