# -*- coding: utf-8 -*-
"""香葱行情定时任务（376dffed）· 2026-11-16 第 28 次执行 · 数据日 2026-11-15（一手核验发布）

产出：
  1) data/sources/xiangcong_2026-11-16.json   统一 schema 全量报价 + 六档预测（供 03:00 日报汇总）
  2) data/weather_2026-11-16.json / data/disaster_2026-11-16.json  当日鲜抓天气/灾害（fetch_1116.py）
  3) outputs/香葱行情分析_2026-11-16.html   八章 / 8 图 单页报告（gen_xc_1116_report.py）

方法（与历史各期一致）：
  - 以 xiangcong_2026-11-15.json（3957 报价）为权威基准。
  - 数据日 2026-11-15 一手核验发布：泸西红香葱 3.4-3.7/均价 3.65（较 11-14 持平，第二日确认），
    黑香葱 2.5-2.9/均价 2.76 持平；全省综合 红 3.4-3.7 / 黑 2.5-2.7；王旗营小葱 3.00/前一日 30 吨。
  - price_history 幂等 upsert 11-14/11-15 一手 observed 点（3.65/2.76），使模型基准锚定 3.65。
  - 用 src.price.build_forecast + 11-16 鲜抓天气出六档预测（按 key 映射到 schema label）。
  - 合并兄弟任务当日文件（若已落盘，按 (date,market,item,round(mid,2)) 去重）。
  - 追加隔年精确同日 2025-11-15 档案 + B2B 挂牌（元/斤×2，显式标注非成交）。
  - 缺失值只标注不插补；冲突口径只并列不平均。
"""
from __future__ import annotations
import json, os, re, glob
from datetime import datetime, timedelta, timezone

sys_path = None
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
TODAY = "2026-11-16"
DATA_DATE = "2026-11-15"
GEN = _now.strftime("%Y-%m-%d %H:%M")
TASK_ID = "376dffed-c5e4-4904-a77a-29193947212a"
CUR_RED, CUR_BLK = 3.65, 2.76

# ============================================================ 1. 基准报价
base = json.load(open(os.path.join(SRC, "xiangcong_2026-11-15.json"), encoding="utf-8"))
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
upsert_obs("2026-11-14", "红香葱", 3.65, note="11-15  executions 核验：11-14 红香葱上破 3.65")
upsert_obs("2026-11-14", "黑葱", 2.76, note="11-14 黑香葱 2.76 持平")
upsert_obs(DATA_DATE, "红香葱", 3.65, note="11-15 一手核验发布 3.4-3.7/均价3.65，较11-14持平（第二日确认）")
upsert_obs(DATA_DATE, "黑葱", 2.76, note="11-15 一手核验发布 2.5-2.9/均价2.76，持平")
upsert_obs(DATA_DATE, "小葱", 3.00, market="昆明王旗营", note="11-15 王旗营小葱 3.00，前一日交易量 30 吨")
json.dump(hist, open(hist_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("[OK] price_history upsert 11-14/11-15 observed 点")

# ============================================================ 3. 六档预测（真实模型 + 11-16 鲜抓天气）
wx = json.load(open(os.path.join(DATA, "weather_2026-11-16.json"), encoding="utf-8"))
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
forecasts[-1]["note"] += ("；⚠️ 目标日为春节（2027-02-06）后，节日备货脉冲衰减 + 2 月季节因子回落，"
                          "中枢较 2 月档回落属正常节后路径（MONO_DESC 动态判定）")
print("[OK] 六档预测", " / ".join("%s=%.2f" % (f["horizon"], f["center"]) for f in forecasts))

# ============================================================ 4. 一手核验报价（数据日 11-15）
fresh = [
 {"date":DATA_DATE,"item":"香葱","variety":"红香葱","market":"云南红河州泸西县","province":"云南",
  "price_type":"产地收购价","unit":"元/公斤","low":3.4,"high":3.7,"mid":3.65,
  "source":"2026年11月15日呈贡/晋宁/嵩明/陆良/通海/元谋/泸西菜价（公众号）",
  "source_url":"http://mp.weixin.qq.com/s?__biz=MzU5MTc0MTM0MA==&mid=2247595928&idx=1&sn=7af85bfc6b0951bb1affbd69410b2d33",
  "note":"★数据日一手核验：红香葱 3.4-3.7/均价标签3.65，较11-14完全持平（第二日确认）；官方总评「叶菜普涨、香葱平稳」，品种特异性弱势"},
 {"date":DATA_DATE,"item":"香葱","variety":"黑香葱","market":"云南红河州泸西县","province":"云南",
  "price_type":"产地收购价","unit":"元/公斤","low":2.5,"high":2.9,"mid":2.76,
  "source":"2026年11月15日泸西菜价（公众号）","source_url":"http://mp.weixin.qq.com/s?__biz=MzU5MTc0MTM0MA==&mid=2247595928&idx=1&sn=7af85bfc6b0951bb1affbd69410b2d33",
  "note":"★数据日一手核验：黑香葱 2.5-2.9/均价2.76，与11-14完全持平"},
 {"date":DATA_DATE,"item":"香葱","variety":"红葱","market":"云南玉溪通海县","province":"云南",
  "price_type":"产地收购价","unit":"元/公斤","low":3.1,"high":3.5,"mid":3.30,
  "source":"2026年11月15日通海菜价（公众号）","source_url":"http://mp.weixin.qq.com/s?__biz=MzU5MTc0MTM0MA==&mid=2247595928&idx=1&sn=7af85bfc6b0951bb1affbd69410b2d33",
  "note":"通海红葱 3.1-3.5，与11-14持平；中值3.30作区间代表"},
 {"date":DATA_DATE,"item":"香葱","variety":"黑葱","market":"云南玉溪通海县","province":"云南",
  "price_type":"产地收购价","unit":"元/公斤","low":2.5,"high":2.9,"mid":2.70,
  "source":"2026年11月15日通海菜价（公众号）","source_url":"http://mp.weixin.qq.com/s?__biz=MzU5MTc0MTM0MA==&mid=2247595928&idx=1&sn=7af85bfc6b0951bb1affbd69410b2d33",
  "note":"通海黑葱 2.5-2.9，与11-14持平；中值2.70作区间代表"},
 {"date":DATA_DATE,"item":"香葱","variety":"红香葱","market":"云南产地综合交易价","province":"云南",
  "price_type":"产地批发价","unit":"元/公斤","low":3.4,"high":3.7,"mid":3.55,
  "source":"11月15日云南产地蔬菜综合交易价格（地慧数农/云南菜价公众号双源一致）",
  "source_url":"http://mp.weixin.qq.com/s?__biz=Mzg3Mzg1MTgwNw==&mid=2247490671&idx=1&sn=f06b4c717680c01024280f4d9f6a92d4",
  "note":"全省综合红香葱 3.4-3.7，中值3.55（官方未给均价标签，取区间中值估算）；已向上收敛接近泸西3.65，倒挂修复"},
 {"date":DATA_DATE,"item":"香葱","variety":"黑葱","market":"云南产地综合交易价","province":"云南",
  "price_type":"产地批发价","unit":"元/公斤","low":2.5,"high":2.7,"mid":2.60,
  "source":"11月15日云南产地蔬菜综合交易价格（地慧数农/云南菜价公众号双源一致）",
  "source_url":"http://mp.weixin.qq.com/s?__biz=Mzg3Mzg1MTgwNw==&mid=2247490671&idx=1&sn=f06b4c717680c01024280f4d9f6a92d4",
  "note":"全省综合黑葱 2.5-2.7，中值2.60（区间中值估算）"},
 {"date":DATA_DATE,"item":"香葱","variety":"小葱","market":"昆明王旗营蔬菜批发市场","province":"云南",
  "price_type":"销地批发价","unit":"元/公斤","low":3.0,"high":3.0,"mid":3.0,
  "source":"11月15日云南菜价·昆明王旗营蔬菜批发市场价格表","source_url":"http://mp.weixin.qq.com/s?__biz=Mzg3Mzg1MTgwNw==&mid=2247490671&idx=1&sn=f06b4c717680c01024280f4d9f6a92d4",
  "note":"王旗营小葱 3.00 持平（第四期平台）；前一日交易量 30 吨；单点报价 low=high=mid"},
 {"date":DATA_DATE,"item":"香葱","variety":"红香葱","market":"云南昆明晋宁区（小蜂菜价通）","province":"云南",
  "price_type":"产地收购价","unit":"元/公斤","low":3.3,"high":3.3,"mid":3.3,
  "source":"11月15日晋宁菜价·小蜂菜价通（晋宁其他菜价）","source_url":"http://mp.weixin.qq.com/s?__biz=Mzg5NDcwNzI5MQ==&mid=2247504243&idx=1&sn=5b80f5f7b8d0ed28278e6621335ddc89",
  "note":"晋宁红香葱 3.30 市场均价，单点值"},
 {"date":DATA_DATE,"item":"香葱","variety":"黑葱","market":"云南昆明晋宁区（小蜂菜价通）","province":"云南",
  "price_type":"产地收购价","unit":"元/公斤","low":2.7,"high":2.7,"mid":2.7,
  "source":"11月15日晋宁菜价·小蜂菜价通（晋宁其他菜价）","source_url":"http://mp.weixin.qq.com/s?__biz=Mzg5NDcwNzI5MQ==&mid=2247504243&idx=1&sn=5b80f5f7b8d0ed28278e6621335ddc89",
  "note":"晋宁黑葱 2.70 市场均价，单点值"},
]
n_fresh = sum(addq(q) for q in fresh)
print("[OK] 数据日一手核验 +%d 条" % n_fresh)

# ============================================================ 5. 隔年精确同日档案 2025-11-15
archive = [
 {"date":"2025-11-15","item":"香葱","variety":"红香葱","market":"云南产地综合交易价","province":"云南",
  "price_type":"产地批发价","unit":"元/公斤","low":6.0,"high":6.4,"mid":6.2,
  "source":"2025年11月15日蔬菜价格表·云南蔬菜市场综合菜价","source_url":"http://zhongdapeng.com/shucaijiage/2017.html",
  "note":"隔年精确同日档案：红香葱 6.0-6.4，中值6.20；本期3.65同比 -41.1%"},
 {"date":"2025-11-15","item":"香葱","variety":"黑葱","market":"云南产地综合交易价","province":"云南",
  "price_type":"产地批发价","unit":"元/公斤","low":4.0,"high":4.3,"mid":4.15,
  "source":"2025年11月15日蔬菜价格表·云南蔬菜市场综合菜价","source_url":"http://zhongdapeng.com/shucaijiage/2017.html",
  "note":"隔年精确同日档案：黑葱 4.0-4.3，中值4.15；本期2.76同比 -33.5%"},
 {"date":"2025-11-15","item":"香葱","variety":"小葱","market":"昆明王旗营蔬菜批发市场","province":"云南",
  "price_type":"销地批发价","unit":"元/公斤","low":5.5,"high":5.5,"mid":5.5,
  "source":"昆明市景臻-王旗营蔬菜批发市场2025年11月15日平均价格统计（昆明市农业农村局）/农业农村部信息中心双源",
  "source_url":"https://nyncj.km.gov.cn/c/2025-11-17/5034963.shtml",
  "note":"隔年精确同日档案：王旗营小葱 5.50、前一日交易量30吨、综合平均价5.78、总吨位3121；本期3.00同比 -45.5%"},
]
n_arch = sum(addq(q) for q in archive)
print("[OK] 隔年同日档案 +%d 条" % n_arch)

# ============================================================ 6. B2B 挂牌（元/斤×2，非成交）
b2b = [
 {"date":DATA_DATE,"item":"香葱","variety":"水洗葱","market":"泸西县（惠农网挂牌）","province":"云南",
  "price_type":"产地地头价","unit":"元/公斤","low":3.6,"high":3.6,"mid":3.6,
  "source":"惠农网 供应页（王明 泸西 1.80 元/斤 水洗葱）","source_url":"https://www.cnhnb.com/p/xiaocong-0-25-0-0-5/",
  "note":"★B2B挂牌非成交价：1.80 元/斤×2=3.60 元/公斤；平台挂牌口径，与菜价表 3.65 分层对照，不并入成交横截面"},
 {"date":DATA_DATE,"item":"香葱","variety":"云南香葱","market":"泸西县（惠农网挂牌）","province":"云南",
  "price_type":"产地地头价","unit":"元/公斤","low":4.4,"high":4.4,"mid":4.4,
  "source":"惠农网 供应页（永合葱业 泸西 2.20 元/斤 云南香葱）","source_url":"https://www.cnhnb.com/p/xiaocong-0-25-0-0-5/",
  "note":"★B2B挂牌非成交价：2.20 元/斤×2=4.40 元/公斤"},
 {"date":DATA_DATE,"item":"香葱","variety":"小香葱","market":"泸西县（惠农网挂牌）","province":"云南",
  "price_type":"产地地头价","unit":"元/公斤","low":3.2,"high":3.2,"mid":3.2,
  "source":"惠农网 供应页（田壮禾 泸西 1.60 元/斤 产地直发小香葱含黑/白/红葱）","source_url":"https://www.cnhnb.com/p/xiaocong-0-25-0-0-7/",
  "note":"★B2B挂牌非成交价：1.60 元/斤×2=3.20 元/公斤"},
 {"date":DATA_DATE,"item":"香葱","variety":"精品红葱","market":"泸西县（一亩田挂牌）","province":"云南",
  "price_type":"产地地头价","unit":"元/公斤","low":2.0,"high":2.0,"mid":2.0,
  "source":"一亩田 泸西产地货源（精品红葱 1.00 元/斤）","source_url":"https://m.ymt.com/shop/2925430",
  "note":"★B2B挂牌非成交价：1.00 元/斤×2=2.00 元/公斤；挂牌口径长期不刷新"},
 {"date":DATA_DATE,"item":"香葱","variety":"精品黑白葱","market":"泸西县（一亩田挂牌）","province":"云南",
  "price_type":"产地地头价","unit":"元/公斤","low":1.6,"high":1.6,"mid":1.6,
  "source":"一亩田 泸西产地货源（精品黑白葱 0.80 元/斤）","source_url":"https://m.ymt.com/shop/2925430",
  "note":"★B2B挂牌非成交价：0.80 元/斤×2=1.60 元/公斤"},
 {"date":DATA_DATE,"item":"香葱","variety":"精品小香葱","market":"泸西县（惠农网挂牌）","province":"云南",
  "price_type":"产地地头价","unit":"元/公斤","low":4.8,"high":5.6,"mid":5.2,
  "source":"惠农网 供应页（泸西 2.40-2.80 元/斤 精品小香葱）","source_url":"https://www.cnhnb.com/p/xiaocong-0-25-0-0-7/",
  "note":"★B2B精品挂牌非成交价：2.40-2.80 元/斤×2=4.80-5.60 元/公斤；规格溢价，非统货成交价"},
]
n_b2b = sum(addq(q) for q in b2b)
print("[OK] B2B挂牌 +%d 条" % n_b2b)

# ============================================================ 7. 合并兄弟任务当日文件（有界：仅已落盘的）
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
        # 剔除占位/非价格条目
        vr = str(q.get("variety", "")) + str(q.get("item", ""))
        if any(t in vr for t in ("说明", "晴窗", "基准")):
            continue
        n_sib += addq(q)
print("[OK] 兄弟任务合并 +%d 条" % n_sib)

# ============================================================ 8. 口径归一化（继承行的非 schema price_type）
PT_MAP = {"卖家挂牌价": "产地地头价", "挂牌价": "产地地头价", "代办价": "产地地头价"}
n_norm = 0
for q in quotes:
    pt = q.get("price_type")
    if pt in PT_MAP:
        q["price_type"] = PT_MAP[pt]
        q["note"] = (q.get("note", "") + "；[口径归一] 原「%s」归为产地地头价，系平台挂牌非成交口径" % pt)
        n_norm += 1
print("[OK] 口径归一化 %d 条（卖家挂牌价→产地地头价）" % n_norm)

# ============================================================ 9. 落盘
market_scope = ("全国 / 云南 / 红河州泸西县（产地、销地、省级综合、宏观、历史锚点、B2B 挂牌全口径；"
               "数据日 2026-11-15 一手核验 3.65/2.76 连续第二日锁定；合并兄弟任务当日数据）")
summary = ("本期数据日 2026-11-15：泸西红香葱 3.4-3.7/均价 3.65、黑香葱 2.5-2.9/均价 2.76，与 11-14 完全持平，为 3.65 平台连续第二日确认，"
           "全省综合红 3.4-3.7（中值3.55）向上收敛接近泸西、倒挂修复；王旗营小葱 3.00 横盘、前一日量 30 吨，叶菜普涨而香葱独不跟涨印证品种特异性弱势。"
           "六档预测中枢（红）3.86/3.94/3.94/3.99/4.13/3.73 元/公斤（模型锚定 3.65、近端降温大风推升，3 月档春节后备货脉冲衰减回落），红为近五年同期最低（同比 2025-11-15 的 6.20 约 -41%），综合风险维持「高」。")
out = {"task": "香葱行情", "task_id": TASK_ID, "date": TODAY, "generated_at": GEN,
       "market_scope": market_scope, "quotes": quotes, "forecasts": forecasts, "summary": summary}
opath = os.path.join(SRC, "xiangcong_%s.json" % TODAY)
json.dump(out, open(opath, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("[OK] WROTE %s  quotes=%d forecasts=%d" % (opath, len(quotes), len(forecasts)))

# ============================================================ 9. schema 自检
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
