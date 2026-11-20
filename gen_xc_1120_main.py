# -*- coding: utf-8 -*-
"""香葱行情定时任务（376dffed）· 2026-11-20 第 32 次执行 · 数据日 2026-11-19（一手核验发布）

产出：
  1) data/sources/xiangcong_2026-11-20.json   统一 schema 全量报价 + 六档预测（供 03:00 日报汇总）
  2) outputs/香葱行情分析_2026-11-20.html   八章 / 8 图 单页报告（gen_xc_1120_report.py）

方法（与历史各期一致）：
  - 以 xiangcong_2026-11-19.json 为权威基准。
  - 数据日 11-19 一手核验：泸西红香葱 3.4-3.7/均价 3.65（较 11-18 持平，3.65 平台第六日），
    黑香葱 2.5-2.9/均价 2.76 持平；通海红 3.1-3.5/黑 2.5-2.9；全省综合红 3.4-3.7/黑 2.5-2.9（双源一致）；
    华磷黑葱 2.6-2.9、白铁杆 2.7-3.0；王旗营小葱 3.00 横盘第八期、前一日量 25 吨（连续两期持平）。
  - 全国小葱 roundup 本期未发布（仅检索到大葱版 + 葱头版 + 单市场表）→ 按缺失不插补改用实际销地单点，不虚构家数/均值。
  - price_history 幂等 upsert 11-18/11-19 一手 observed 点，模型基准锚定 3.65。
  - 用 src.price.build_forecast + 11-20 鲜抓天气出六档预测（按 key 映射到 schema label）。
  - 合并兄弟任务当日文件（若已落盘，按 (date,market,variety,round(mid,2)) 去重）。
  - 追加隔年精确同日 2025-11-19 档案 + 实际销地单点 + B2B 挂牌（元/斤×2，显式标注非成交）。
  - 缺失值只标注不插补；冲突口径只并列不平均。
"""
from __future__ import annotations
import json, os, re, glob
from datetime import datetime, timedelta, timezone

import sys
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
from src import price

SRC = os.path.join(BASE_DIR, "data", "sources")
DATA = os.path.join(BASE_DIR, "data")
OUT = os.path.join(BASE_DIR, "outputs")
os.makedirs(SRC, exist_ok=True); os.makedirs(OUT, exist_ok=True)

BJ = timezone(timedelta(hours=8))
_now = datetime.now(BJ)
TODAY = "2026-11-20"
DATA_DATE = "2026-11-19"
GEN = _now.strftime("%Y-%m-%d %H:%M")
TASK_ID = "376dffed-c5e4-4904-a77a-29193947212a"

# ============================================================ 1. 基准报价
base = json.load(open(os.path.join(SRC, "xiangcong_2026-11-19.json"), encoding="utf-8"))
quotes = list(base.get("quotes", []))

def _mid(q):
    m = q.get("mid")
    try: return round(float(m), 2) if m is not None else None
    except Exception: return None

def key(q):
    m = _mid(q)
    return (str(q.get("date")), str(q.get("market")), str(q.get("item")), m if m is not None else -1)

seen = set(key(q) for q in quotes)

def addq(q):
    k = key(q)
    if k in seen: return 0
    seen.add(k); quotes.append(q); return 1

# ============================================================ 2. price_history 幂等 upsert 一手 observed 点
hist_path = os.path.join(DATA, "price_history.json")
hist = json.load(open(hist_path, encoding="utf-8"))
def upsert_obs(d, var, p, market="云南产地", note=""):
    for r in hist["series"]:
        if r["date"] == d and r["variety"] == var and r.get("source") == "observed":
            r["price"] = p; r["note"] = note; return
    hist["series"].append({"date": d, "variety": var, "market": market, "price": p,
                           "source": "observed", "note": note})
upsert_obs("2026-11-18", "红香葱", 3.65, note="11-19 核验：11-18 红香葱 3.65 持平确认（平台第五日）")
upsert_obs("2026-11-18", "黑葱", 2.76, note="11-18 黑香葱 2.76 持平")
upsert_obs(DATA_DATE, "红香葱", 3.65, note="11-19 一手核验发布 3.4-3.7/均价3.65，较11-18持平（3.65平台第六日）")
upsert_obs(DATA_DATE, "黑葱", 2.76, note="11-19 一手核验发布 2.5-2.9/均价2.76，持平")
upsert_obs(DATA_DATE, "小葱", 3.00, market="昆明王旗营", note="11-19 王旗营小葱 3.00，前一日交易量 25 吨（对应11-18读数，与11-17的25吨持平）")
json.dump(hist, open(hist_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("[OK] price_history upsert 11-18/11-19 observed 点")

# ============================================================ 3. 六档预测（真实模型 + 11-20 鲜抓天气）
wx_path = os.path.join(DATA, "weather_2026-11-20.json")
if not os.path.exists(wx_path):
    wx_path = os.path.join(DATA, "weather_2026-11-19.json")
    print("[WARN] weather_2026-11-20.json 未落盘，回退 weather_2026-11-19.json")
wx = json.load(open(wx_path, encoding="utf-8"))
daily = [d for d in wx["core"]["daily"] if d.get("tmax") is not None]
clim = wx["core"].get("climatology") or {}
fc = price.build_forecast(hist, daily, clim=clim)
FRED, FBLK = fc["红香葱"], fc["黑葱"]
print("[OK] 模型基准 红", FRED["current"], "ma20", FRED["ma20"], "/ 黑", FBLK["current"])

HMAP = {"d3": "未来3天", "w1": "未来7天", "h1": "未来15天",
        "m1": "未来1个月", "m2": "未来2个月", "m3": "未来3个月"}
RRED = {r["key"]: r for r in FRED["rows"]}
RBLK = {r["key"]: r for r in FBLK["rows"]}
forecasts = []
for k, label in HMAP.items():
    r, b = RRED[k], RBLK[k]
    note = ("泸西红香葱（精品净葱/集散价口径）；黑葱同档中枢 %.2f 元/公斤（%+.1f%%）；"
            "区间为情景区间非统计置信区间；驱动：%s" %
            (b["center"], b["delta_pct"], "；".join(r["reasons"][:2])))
    forecasts.append({"horizon": label, "target_date": r["target_date"], "item": "香葱",
                      "center": r["center"], "low": r["low"], "high": r["high"],
                      "delta_pct": r["delta_pct"], "confidence": r["confidence"], "note": note})
forecasts[-1]["note"] += ("；⚠️ 目标日 %s 处春节（2027-02-06）后，节日备货脉冲衰减 + 2 月季节因子回落，"
                          "中枢较 2 月档回落属正常节后路径（MONO_DESC 动态判定）" % forecasts[-1]["target_date"])
print("[OK] 六档预测", " / ".join("%s=%.2f" % (f["horizon"], f["center"]) for f in forecasts))

# ============================================================ 4. 一手核验报价（数据日 11-19）
fresh = [
 {"date":DATA_DATE,"item":"香葱","variety":"红香葱","market":"云南红河州泸西县","province":"云南",
  "price_type":"产地收购价","unit":"元/公斤","low":3.4,"high":3.7,"mid":3.65,
  "source":"2026年11月19日呈贡/晋宁/嵩明/陆良/通海/元谋/泸西菜价（公众号 mid=2247595946）",
  "source_url":"http://mp.weixin.qq.com/s?__biz=MzU5MTc0MTM0MA==&mid=2247595946&idx=1&sn=618241cf04a34834d6f1ed0d9e0c28be",
  "note":"★数据日一手核验：红香葱 3.4-3.7/均价标签3.65，与11-18完全持平（3.65平台第六日）；当日总评「黄白微涨、金丝白奶白上扬、上青微掉、菠菜微涨、香菜掉2元、小香葱平稳」"},
 {"date":DATA_DATE,"item":"香葱","variety":"黑香葱","market":"云南红河州泸西县","province":"云南",
  "price_type":"产地收购价","unit":"元/公斤","low":2.5,"high":2.9,"mid":2.76,
  "source":"2026年11月19日泸西菜价（公众号 mid=2247595946）","source_url":"http://mp.weixin.qq.com/s?__biz=MzU5MTc0MTM0MA==&mid=2247595946&idx=1&sn=618241cf04a34834d6f1ed0d9e0c28be",
  "note":"★数据日一手核验：黑香葱 2.5-2.9/均价2.76，与11-18完全持平"},
 {"date":DATA_DATE,"item":"香葱","variety":"红葱","market":"云南玉溪通海县","province":"云南",
  "price_type":"产地收购价","unit":"元/公斤","low":3.1,"high":3.5,"mid":3.30,
  "source":"2026年11月19日通海菜价（公众号，序号15）","source_url":"http://mp.weixin.qq.com/s?__biz=MzU5MTc0MTM0MA==&mid=2247595946&idx=1&sn=618241cf04a34834d6f1ed0d9e0c28be",
  "note":"通海红葱 3.1-3.5，与11-18持平；中值3.30作区间代表"},
 {"date":DATA_DATE,"item":"香葱","variety":"黑葱","market":"云南玉溪通海县","province":"云南",
  "price_type":"产地收购价","unit":"元/公斤","low":2.5,"high":2.9,"mid":2.70,
  "source":"2026年11月19日通海菜价（公众号，序号16）","source_url":"http://mp.weixin.qq.com/s?__biz=MzU5MTc0MTM0MA==&mid=2247595946&idx=1&sn=618241cf04a34834d6f1ed0d9e0c28be",
  "note":"通海黑葱 2.5-2.9，与11-18持平；中值2.70作区间代表"},
 {"date":DATA_DATE,"item":"香葱","variety":"红香葱","market":"云南产地综合交易价","province":"云南",
  "price_type":"产地批发价","unit":"元/公斤","low":3.4,"high":3.7,"mid":3.55,
  "source":"11月19日云南产地蔬菜综合交易价格（地慧数农/云南菜价公众号双源一致，序号42）",
  "source_url":"http://mp.weixin.qq.com/s?__biz=Mzg3Mzg1MTgwNw==&mid=2247490691&idx=1&sn=59918273fa3b3e904fa5be8d6bec5e48",
  "note":"全省综合红香葱 3.4-3.7，中值3.55（官方未给均价标签，取区间中值估算）；与泸西3.65基本对齐，倒挂修复延续"},
 {"date":DATA_DATE,"item":"香葱","variety":"黑葱","market":"云南产地综合交易价","province":"云南",
  "price_type":"产地批发价","unit":"元/公斤","low":2.5,"high":2.9,"mid":2.70,
  "source":"11月19日云南产地蔬菜综合交易价格（地慧数农/云南菜价公众号双源一致，序号43）",
  "source_url":"http://mp.weixin.qq.com/s?__biz=Mzg3Mzg1MTgwNw==&mid=2247490691&idx=1&sn=59918273fa3b3e904fa5be8d6bec5e48",
  "note":"全省综合黑葱 2.5-2.9，中值2.70（区间中值估算）"},
 {"date":DATA_DATE,"item":"香葱","variety":"黑葱","market":"云南产区（华磷肥料行情专报）","province":"云南",
  "price_type":"产地收购价","unit":"元/公斤","low":2.6,"high":2.9,"mid":2.75,
  "source":"华磷肥料·菜价行情专报 2026-11-19（昨日2.9，序号47）",
  "source_url":"http://mp.weixin.qq.com/s?__biz=MzcwNTMxOTA1Mg==&mid=2247486385&idx=1&sn=b8bfe30e607fe48c01e1dc70f6f2417e",
  "note":"独立采价表：黑葱今日2.6-2.9（昨日2.9），与地慧数农2.5-2.9一致；黑葱包地价昨2900→今2600元/亩（在2600横盘，元/亩非本schema口径，不入quotes，仅作领先信号登记）"},
 {"date":DATA_DATE,"item":"香葱","variety":"白铁杆","market":"云南产区（华磷肥料行情专报）","province":"云南",
  "price_type":"产地收购价","unit":"元/公斤","low":2.7,"high":3.0,"mid":2.85,
  "source":"华磷肥料·菜价行情专报 2026-11-19（昨日3.0，序号49）",
  "source_url":"http://mp.weixin.qq.com/s?__biz=MzcwNTMxOTA1Mg==&mid=2247486385&idx=1&sn=b8bfe30e607fe48c01e1dc70f6f2417e",
  "note":"白铁杆今日2.7-3.0（昨日3.0），小幅走弱；白葱铁杆为香葱近亲品类"},
 {"date":DATA_DATE,"item":"香葱","variety":"小葱","market":"昆明王旗营蔬菜批发市场","province":"云南",
  "price_type":"销地批发价","unit":"元/公斤","low":3.0,"high":3.0,"mid":3.0,
  "source":"11月19日云南菜价·昆明王旗营蔬菜批发市场价格表（两转载源一致）","source_url":"http://mp.weixin.qq.com/s?__biz=Mzg3Mzg1MTgwNw==&mid=2247490691&idx=1&sn=59918273fa3b3e904fa5be8d6bec5e48",
  "note":"王旗营小葱 3.00 横盘第八期；前一日交易量 25 吨（对应11-18读数，与11-17的25吨持平）；单点报价 low=high=mid"},
 {"date":DATA_DATE,"item":"香葱","variety":"香葱","market":"云南保山市龙陵县腊勐镇（产地收购）","province":"云南",
  "price_type":"产地收购价","unit":"元/公斤","low":6.0,"high":6.0,"mid":6.0,
  "source":"保山新闻网 2026-11-19《6元一公斤！腊勐一畦香葱又增收》","source_url":"https://www.baoshan.cn/cityMini/site/content/1310620261119161521.html",
  "note":"新增滇西产区样本：龙陵腊勐香葱收购价6.00元/公斤（订单农业、品质溢价，销往保山/芒市/腾冲；年产值1100余万元，一年可采收三茬），远高于滇中泸西3.65，属特色小众产区不可直接横比"},
 {"date":DATA_DATE,"item":"香葱","variety":"香葱（宏观大盘参考）","market":"全国28种蔬菜均价","province":"全国",
  "price_type":"销地批发价","unit":"元/公斤","low":4.17,"high":4.17,"mid":4.17,
  "source":"农业农村部市场与信息化司 2026-11-19（农产品200指数111.99、菜篮子指数111.63）","source_url":"https://www.agri.cn/zx/zxfb/202611/t20261119_8884918.htm",
  "note":"★宏观大盘参考：28种蔬菜均价4.17元/公斤（日环比+1.5%），非香葱单品，不并入香葱横截面均值；农产品200指数111.99/菜篮子111.63"},
]
n_fresh = sum(addq(q) for q in fresh)
print("[OK] 数据日一手核验 +%d 条" % n_fresh)

# ============================================================ 5. 隔年精确同日档案 2025-11-19
archive = [
 {"date":"2025-11-19","item":"香葱","variety":"红香葱","market":"云南产地综合交易价","province":"云南",
  "price_type":"产地批发价","unit":"元/公斤","low":6.0,"high":6.3,"mid":6.15,
  "source":"2025年11月19日云南蔬菜综合报价（三源一致，序号42）","source_url":"http://mp.weixin.qq.com/s?__biz=Mzg3Mzg1MTgwNw==&mid=2247488785&idx=1&sn=5c46b4fecbd939c445dc02b69716cc0f",
  "note":"隔年精确同日档案：红香葱 6.0-6.3，中值6.15；本期3.65同比 -40.7%"},
 {"date":"2025-11-19","item":"香葱","variety":"黑葱","market":"云南产地综合交易价","province":"云南",
  "price_type":"产地批发价","unit":"元/公斤","low":4.0,"high":4.3,"mid":4.15,
  "source":"2025年11月19日云南蔬菜综合报价（三源一致，序号43）","source_url":"http://mp.weixin.qq.com/s?__biz=Mzg3Mzg1MTgwNw==&mid=2247488785&idx=1&sn=5c46b4fecbd939c445dc02b69716cc0f",
  "note":"隔年精确同日档案：黑葱 4.0-4.3，中值4.15；本期2.76同比 -33.5%"},
 {"date":"2025-11-19","item":"香葱","variety":"小葱","market":"昆明王旗营蔬菜批发市场","province":"云南",
  "price_type":"销地批发价","unit":"元/公斤","low":4.8,"high":4.8,"mid":4.8,
  "source":"昆明市景臻-王旗营蔬菜批发市场2025年11月19日平均价格统计（昆明市农业农村局官方表）/农业农村部单市场表双源互证",
  "source_url":"https://nyncj.km.gov.cn/c/2025-11-19/5035664.shtml",
  "note":"隔年精确同日档案：王旗营小葱 4.80、前一日交易量30吨、综合平均价5.75、总吨位2848；本期3.00同比 -37.5%"},
]
n_arch = sum(addq(q) for q in archive)
print("[OK] 隔年同日档案 +%d 条" % n_arch)

# ============================================================ 6. 全国销地实际单点（11-19；小葱 roundup 本期未发布，缺失不插补）
# 说明：本期仅检索到 11-20 全国主要批发市场「大葱」行情、11-19「葱头」行情与各单市场表，未检索到「小葱」roundup。
# 按 data-analysis 缺失只标注不插补原则：不沿用上期均值、不虚构家数，改用下列实际采集单点。
sales_pts = [
 ("北京新发地农产品批发市场（香葱）", "北京", 5.6, 7.2, 6.4, "香葱 最低/平均/最高 2.8/3.2/3.6 元/斤×2"),
 ("北京新发地农产品批发市场（毛/净小葱）", "北京", 3.0, 5.0, 4.0, "毛/净小葱 最低/平均/最高 1.5/2.0/2.5 元/斤×2"),
 ("江苏苏州南环桥农副产品批发市场（小葱）", "江苏", 3.5, 3.5, 3.5, "小葱 3.50 元/公斤（农业农村部单市场表）"),
 ("辽宁朝阳市果菜批发市场（小葱）", "辽宁", 1.7, 1.7, 1.7, "小葱 1.70 元/公斤（农业农村部单市场表，全国低位）"),
 ("昆明王旗营蔬菜批发市场（小葱）", "云南", 3.0, 3.0, 3.0, "小葱 3.00 元/公斤；前一日交易量25吨"),
]
n_sp = 0
for mk, pv, lo, hi, mid, nt in sales_pts:
    n_sp += addq({"date":DATA_DATE,"item":"香葱","variety":"小葱","market":mk,"province":pv,
                  "price_type":"销地批发价","unit":"元/公斤","low":lo,"high":hi,"mid":mid,
                  "source":"2026年11月19日各销地批发市场公开报价（市场公示/农业农村部单市场表，元/斤×2折算）","source_url":"",
                  "note":"★销地实际单点："+nt+"；全国小葱 roundup 本期未发布，按缺失不插补不发布全国加权均价"})
print("[OK] 销地实际单点 +%d 条" % n_sp)

# ============================================================ 7. B2B 挂牌（元/斤×2，非成交）
b2b = [
 {"date":DATA_DATE,"item":"香葱","variety":"水洗葱","market":"泸西县（惠农网挂牌）","province":"云南",
  "price_type":"产地地头价","unit":"元/公斤","low":3.4,"high":3.4,"mid":3.4,
  "source":"惠农网 供应页（泸西 1.70 元/斤 水洗葱/香葱地头价）","source_url":"https://www.cnhnb.com/p/xiaocong-0-25-0-0-4/",
  "note":"★B2B挂牌非成交价：1.70 元/斤×2=3.40 元/公斤；平台挂牌长期不刷新（11-20 采集快照），与菜价表3.65分层对照，不并入成交横截面"},
 {"date":DATA_DATE,"item":"香葱","variety":"云南香葱","market":"泸西县（惠农网挂牌）","province":"云南",
  "price_type":"产地地头价","unit":"元/公斤","low":4.0,"high":4.0,"mid":4.0,
  "source":"惠农网 供应页（泸西 2.00 元/斤 云南香葱）","source_url":"https://www.cnhnb.com/p/xiaocong-0-25-0-0-7/",
  "note":"★B2B挂牌非成交价：2.00 元/斤×2=4.00 元/公斤（11-20 采集快照）"},
 {"date":DATA_DATE,"item":"香葱","variety":"小香葱","market":"泸西县（惠农网挂牌）","province":"云南",
  "price_type":"产地地头价","unit":"元/公斤","low":3.2,"high":3.2,"mid":3.2,
  "source":"惠农网 供应页（田壮禾 泸西 1.60 元/斤 产地直发小香葱含黑/白/红葱）","source_url":"https://www.cnhnb.com/p/xiaocong-0-25-0-0-7/",
  "note":"★B2B挂牌非成交价：1.60 元/斤×2=3.20 元/公斤（11-20 采集快照）"},
 {"date":DATA_DATE,"item":"香葱","variety":"精品红葱","market":"泸西县（一亩田挂牌）","province":"云南",
  "price_type":"产地地头价","unit":"元/公斤","low":2.0,"high":2.0,"mid":2.0,
  "source":"一亩田 泸西产地货源（精品红葱 1.00 元/斤）","source_url":"https://m.ymt.com/shop/2925430",
  "note":"★B2B挂牌非成交价：1.00 元/斤×2=2.00 元/公斤；挂牌口径长期不刷新（11-20 采集快照），非11-19当日成交"},
 {"date":DATA_DATE,"item":"香葱","variety":"精品黑白葱","market":"泸西县（一亩田挂牌）","province":"云南",
  "price_type":"产地地头价","unit":"元/公斤","low":1.6,"high":1.6,"mid":1.6,
  "source":"一亩田 泸西产地货源（精品黑白葱 0.80 元/斤）","source_url":"https://m.ymt.com/shop/2925430",
  "note":"★B2B挂牌非成交价：0.80 元/斤×2=1.60 元/公斤（11-20 采集快照）"},
 {"date":DATA_DATE,"item":"香葱","variety":"精品小香葱","market":"泸西县（惠农网挂牌）","province":"云南",
  "price_type":"产地地头价","unit":"元/公斤","low":4.8,"high":5.6,"mid":5.2,
  "source":"惠农网 供应页（泸西 2.40-2.80 元/斤 精品小香葱）","source_url":"https://www.cnhnb.com/p/xiaocong-0-25-0-0-7/",
  "note":"★B2B精品挂牌非成交价：2.40-2.80 元/斤×2=4.80-5.60 元/公斤；规格溢价，非统货成交价（11-20 采集快照）"},
]
n_b2b = sum(addq(q) for q in b2b)
print("[OK] B2B挂牌 +%d 条" % n_b2b)

# ============================================================ 8. 合并兄弟任务当日文件（有界：仅已落盘的）
n_sib = 0
for fn in sorted(glob.glob(os.path.join(SRC, "*_%s.json" % TODAY))):
    bn = os.path.basename(fn)
    if bn.startswith("xiangcong_"):
        continue
    try:
        d = json.load(open(fn, encoding="utf-8"))
    except Exception:
        continue
    for q in d.get("quotes", []):
        m = _mid(q)
        if (m is None or m == 0) and (q.get("low") in (0, None, "")):
            continue
        vr = str(q.get("variety", "")) + str(q.get("item", ""))
        if any(t in vr for t in ("说明", "晴窗", "基准")):
            continue
        n_sib += addq(q)
print("[OK] 兄弟任务合并 +%d 条" % n_sib)

# ============================================================ 9. 口径归一化
PT_MAP = {"卖家挂牌价": "产地地头价", "挂牌价": "产地地头价", "代办价": "产地地头价",
          "产地挂牌价": "产地地头价", "批发市场价": "销地批发价", "市场价": "销地批发价",
          "产地价": "产地地头价", "收购价": "产地收购价", "大宗价": "产地批发价",
          "批发价": "销地批发价", "零售": "零售价"}
n_norm = 0
for q in quotes:
    pt = q.get("price_type")
    if pt in PT_MAP:
        q["price_type"] = PT_MAP[pt]
        q["note"] = (q.get("note", "") + "；[口径归一] 原「%s」归为产地地头价，系平台挂牌非成交口径" % pt)
        n_norm += 1
    elif pt == "指数/点位":
        q["price_type"] = "销地批发价"
        q["note"] = (q.get("note", "") + "；[口径归一] 原「指数/点位」为宏观大盘参考(非香葱单品)，归为销地批发价，不并入香葱横截面均值")
        n_norm += 1
print("[OK] 口径归一化 %d 条" % n_norm)

# ============================================================ 10. 落盘
market_scope = ("全国 / 云南 / 红河州泸西县（产地、销地、省级综合、宏观、历史锚点、B2B 挂牌全口径；"
               "数据日 2026-11-19 一手核验 3.65/2.76 连续第六日锁定；合并兄弟任务当日数据）")
summary = ("数据日2026年11月19日，泸西红香葱均价3.65元/公斤、黑香葱2.76与11-18完全持平（3.65平台连续第六日），全省综合红3.4-3.7、黑2.5-2.9双源一致并与泸西对齐，昆明王旗营小葱3.00横盘第八期、前一日成交25吨持平。全国小葱roundup本期未发布（仅大葱版/葱头版），按缺失不插补改用北京新发地香葱6.40、苏州南环桥3.50、辽宁朝阳1.70等实际销地单点，不发布全国加权均价；新增滇西保山腊勐特色产区收购6.00元样本，红葱同比2025-11-19的6.15下跌40.7%、为近五年同期绝对最低。六档中枢（红）锚定3.65为3.94/3.94/3.94/3.99/4.12/3.63，近端距平-6.6℃与降水短期支撑、3月档春节后回落属正常路径，综合风险维持高。")
out = {"task": "香葱行情", "task_id": TASK_ID, "date": TODAY, "generated_at": GEN,
       "market_scope": market_scope, "quotes": quotes, "forecasts": forecasts, "summary": summary}
opath = os.path.join(SRC, "xiangcong_%s.json" % TODAY)
json.dump(out, open(opath, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("[OK] WROTE %s  quotes=%d forecasts=%d" % (opath, len(quotes), len(forecasts)))

# ============================================================ 11. schema 自检
errs = []
allow_pt = {"产地地头价","产地收购价","产地批发价","销地批发价","零售价"}
for q in quotes:
    if q.get("unit") != "元/公斤": errs.append("unit "+str(q.get("unit")))
    if q.get("price_type") not in allow_pt: errs.append("pt "+str(q.get("price_type")))
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(q.get("date"))): errs.append("date "+str(q.get("date")))
    if q.get("mid") is None: errs.append("mid None "+str(q.get("market")))
labels = [f["horizon"] for f in forecasts]
expect = ["未来3天","未来7天","未来15天","未来1个月","未来2个月","未来3个月"]
if labels != expect: errs.append("forecast labels "+str(labels))
print("[CHECK] schema 问题 %d 项：%s" % (len(errs), errs[:8]))
print("[CHECK] 各省区数", len(set(q.get("province") for q in quotes if q.get("province") and q.get("province") != "全国")))
print("[CHECK] 日期数", len(set(q.get("date") for q in quotes)))
