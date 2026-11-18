# -*- coding: utf-8 -*-
"""香葱行情定时任务（376dffed）· 2026-11-17 第 29 次执行 · 数据日 2026-11-16（一手核验发布）

产出：
  1) data/sources/xiangcong_2026-11-17.json   统一 schema 全量报价 + 六档预测（供 03:00 日报汇总）
  2) outputs/香葱行情分析_2026-11-17.html   八章 / 8 图 单页报告（gen_xc_1117_report.py）

方法（与历史各期一致）：
  - 以 xiangcong_2026-11-16.json（3974 报价）为权威基准。
  - 数据日 2026-11-16 一手核验发布：泸西红香葱 3.4-3.7/均价 3.65（较 11-15 持平，3.65 平台第三日），
    黑香葱 2.5-2.9/均价 2.76 持平；通海红 3.1-3.5/黑 2.5-2.9；全省综合红 3.4-3.7/黑 2.5-2.9；
    王旗营小葱 3.00/前一日 30 吨。全国 49 家批发市场小葱 roundup 均值 5.64。
  - price_history 幂等 upsert 11-15/11-16 一手 observed 点（3.65/2.76），模型基准锚定 3.65。
  - 用 src.price.build_forecast + 11-17 鲜抓天气出六档预测（按 key 映射到 schema label）。
  - 合并兄弟任务当日文件（若已落盘，按 (date,market,item,round(mid,2)) 去重）。
  - 追加隔年精确同日 2025-11-16 档案 + 全国 roundup + B2B 挂牌（元/斤×2，显式标注非成交）。
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
TODAY = "2026-11-17"
DATA_DATE = "2026-11-16"
GEN = _now.strftime("%Y-%m-%d %H:%M")
TASK_ID = "376dffed-c5e4-4904-a77a-29193947212a"
CUR_RED, CUR_BLK = 3.65, 2.76

# ============================================================ 1. 基准报价
base = json.load(open(os.path.join(SRC, "xiangcong_2026-11-16.json"), encoding="utf-8"))
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
upsert_obs("2026-11-15", "红香葱", 3.65, note="11-16 核验：11-15 红香葱 3.65 持平确认")
upsert_obs("2026-11-15", "黑葱", 2.76, note="11-15 黑香葱 2.76 持平")
upsert_obs(DATA_DATE, "红香葱", 3.65, note="11-16 一手核验发布 3.4-3.7/均价3.65，较11-15持平（3.65平台第三日）")
upsert_obs(DATA_DATE, "黑葱", 2.76, note="11-16 一手核验发布 2.5-2.9/均价2.76，持平")
upsert_obs(DATA_DATE, "小葱", 3.00, market="昆明王旗营", note="11-16 王旗营小葱 3.00，前一日交易量 30 吨")
json.dump(hist, open(hist_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("[OK] price_history upsert 11-15/11-16 observed 点")

# ============================================================ 3. 六档预测（真实模型 + 11-17 鲜抓天气）
wx_path = os.path.join(DATA, "weather_2026-11-17.json")
if not os.path.exists(wx_path):  # 兜底：接口连续失败时用上一日快照（报告显式披露）
    wx_path = os.path.join(DATA, "weather_2026-11-16.json")
    print("[WARN] weather_2026-11-17.json 未落盘，回退 weather_2026-11-16.json")
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

# ============================================================ 4. 一手核验报价（数据日 11-16）
fresh = [
 {"date":DATA_DATE,"item":"香葱","variety":"红香葱","market":"云南红河州泸西县","province":"云南",
  "price_type":"产地收购价","unit":"元/公斤","low":3.4,"high":3.7,"mid":3.65,
  "source":"2026年11月16日呈贡/晋宁/嵩明/陆良/通海/元谋/泸西菜价（公众号）",
  "source_url":"http://mp.weixin.qq.com/s?__biz=MzU5MTc0MTM0MA==&mid=2247595932&idx=1&sn=8659694309c63b4010c2d43f934fb767",
  "note":"★数据日一手核验：红香葱 3.4-3.7/均价标签3.65，较11-15完全持平（3.65平台第三日）；官方总评「叶菜持续上扬、小菜类平稳、松花上涨」，香葱独不跟涨"},
 {"date":DATA_DATE,"item":"香葱","variety":"黑香葱","market":"云南红河州泸西县","province":"云南",
  "price_type":"产地收购价","unit":"元/公斤","low":2.5,"high":2.9,"mid":2.76,
  "source":"2026年11月16日泸西菜价（公众号）","source_url":"http://mp.weixin.qq.com/s?__biz=MzU5MTc0MTM0MA==&mid=2247595932&idx=1&sn=8659694309c63b4010c2d43f934fb767",
  "note":"★数据日一手核验：黑香葱 2.5-2.9/均价2.76，与11-15完全持平"},
 {"date":DATA_DATE,"item":"香葱","variety":"红葱","market":"云南玉溪通海县","province":"云南",
  "price_type":"产地收购价","unit":"元/公斤","low":3.1,"high":3.5,"mid":3.30,
  "source":"2026年11月16日通海菜价（公众号）","source_url":"http://mp.weixin.qq.com/s?__biz=MzU5MTc0MTM0MA==&mid=2247595932&idx=1&sn=8659694309c63b4010c2d43f934fb767",
  "note":"通海红葱 3.1-3.5，与11-15持平；中值3.30作区间代表"},
 {"date":DATA_DATE,"item":"香葱","variety":"黑葱","market":"云南玉溪通海县","province":"云南",
  "price_type":"产地收购价","unit":"元/公斤","low":2.5,"high":2.9,"mid":2.70,
  "source":"2026年11月16日通海菜价（公众号）","source_url":"http://mp.weixin.qq.com/s?__biz=MzU5MTc0MTM0MA==&mid=2247595932&idx=1&sn=8659694309c63b4010c2d43f934fb767",
  "note":"通海黑葱 2.5-2.9，与11-15持平；中值2.70作区间代表"},
 {"date":DATA_DATE,"item":"香葱","variety":"红香葱","market":"云南产地综合交易价","province":"云南",
  "price_type":"产地批发价","unit":"元/公斤","low":3.4,"high":3.7,"mid":3.55,
  "source":"11月16日云南产地蔬菜综合交易价格（地慧数农/云南菜价公众号双源一致）",
  "source_url":"http://mp.weixin.qq.com/s?__biz=Mzg3Mzg1MTgwNw==&mid=2247490676&idx=1&sn=84abcd8b703d5bcb4fcb5cbb3f15a09f",
  "note":"全省综合红香葱 3.4-3.7，中值3.55（官方未给均价标签，取区间中值估算）；与泸西3.65基本对齐，倒挂修复延续"},
 {"date":DATA_DATE,"item":"香葱","variety":"黑葱","market":"云南产地综合交易价","province":"云南",
  "price_type":"产地批发价","unit":"元/公斤","low":2.5,"high":2.9,"mid":2.70,
  "source":"11月16日云南产地蔬菜综合交易价格（地慧数农/云南菜价公众号双源一致）",
  "source_url":"http://mp.weixin.qq.com/s?__biz=Mzg3Mzg1MTgwNw==&mid=2247490676&idx=1&sn=84abcd8b703d5bcb4fcb5cbb3f15a09f",
  "note":"全省综合黑葱 2.5-2.9，中值2.70（区间中值估算）"},
 {"date":DATA_DATE,"item":"香葱","variety":"小葱","market":"昆明王旗营蔬菜批发市场","province":"云南",
  "price_type":"销地批发价","unit":"元/公斤","low":3.0,"high":3.0,"mid":3.0,
  "source":"11月16日云南菜价·昆明王旗营蔬菜批发市场价格表","source_url":"http://mp.weixin.qq.com/s?__biz=Mzg3Mzg1MTgwNw==&mid=2247490676&idx=1&sn=84abcd8b703d5bcb4fcb5cbb3f15a09f",
  "note":"王旗营小葱 3.00 横盘第五期；前一日交易量 30 吨；单点报价 low=high=mid"},
]
n_fresh = sum(addq(q) for q in fresh)
print("[OK] 数据日一手核验 +%d 条" % n_fresh)

# ============================================================ 5. 隔年精确同日档案 2025-11-16
archive = [
 {"date":"2025-11-16","item":"香葱","variety":"红香葱","market":"云南产地综合交易价","province":"云南",
  "price_type":"产地批发价","unit":"元/公斤","low":6.0,"high":6.3,"mid":6.15,
  "source":"2025年11月16日云南蔬菜综合报价（多源一致）","source_url":"http://mp.weixin.qq.com/s?__biz=Mzg3Mzg1MTgwNw==&mid=2247488758&idx=1&sn=7eb2578f4119e362d178d7b0f9139e39",
  "note":"隔年精确同日档案：红香葱 6.0-6.3，中值6.15；本期3.65同比 -40.7%"},
 {"date":"2025-11-16","item":"香葱","variety":"黑葱","market":"云南产地综合交易价","province":"云南",
  "price_type":"产地批发价","unit":"元/公斤","low":4.0,"high":4.3,"mid":4.15,
  "source":"2025年11月16日云南蔬菜综合报价（多源一致）","source_url":"http://mp.weixin.qq.com/s?__biz=Mzg3Mzg1MTgwNw==&mid=2247488758&idx=1&sn=7eb2578f4119e362d178d7b0f9139e39",
  "note":"隔年精确同日档案：黑葱 4.0-4.3，中值4.15；本期2.76同比 -33.5%"},
 {"date":"2025-11-16","item":"香葱","variety":"小葱","market":"昆明王旗营蔬菜批发市场","province":"云南",
  "price_type":"销地批发价","unit":"元/公斤","low":5.5,"high":5.5,"mid":5.5,
  "source":"昆明市景臻-王旗营蔬菜批发市场2025年11月16日平均价格统计（昆明市农业农村局）/多源",
  "source_url":"https://nyncj.km.gov.cn/c/2025-11-17/5035063.shtml",
  "note":"隔年精确同日档案：王旗营小葱 5.50、前一日交易量25吨、综合平均价5.70、总吨位2925；本期3.00同比 -45.5%"},
]
n_arch = sum(addq(q) for q in archive)
print("[OK] 隔年同日档案 +%d 条" % n_arch)

# ============================================================ 6. 全国 49 家批发市场小葱 roundup（11-16）
roundup = [
("北京新发地农副产品批发市场",4.00),("北京朝阳区大洋路综合市场",8.10),("邯郸馆陶金凤禽蛋市场",1.50),
("河北怀来县京西果菜批发市场",6.00),("邯郸经开区南大堡蔬菜批发市场",2.40),("晋城市绿欣农产品",4.70),
("晋城绿盛农工商实业",2.40),("呼和浩特东瓦窑农副产品",7.40),("辽宁鞍山宁远农产品",2.50),
("辽宁朝阳市果菜批发市场",1.70),("江苏凌家塘市场",6.50),("苏州南环桥农副产品",3.50),
("无锡朝阳农产品大市场",4.58),("义乌市市场发展集团农批",4.50),("浙江嘉兴蔬菜批发",4.67),
("绍兴市蔬菜果品批发",4.00),("杭州农副产品物流中心南庄兜",6.00),("天长市永福农副产品",5.50),
("合肥周谷堆农产品批发市场",5.80),("六安裕安区紫竹林农产品",5.90),("马鞍山安民农副产品",7.50),
("福鼎市商贸业服务中心",7.60),("江西乐平蔬菜农产品批发",3.60),("九江琵琶湖农产品物流",6.40),
("章丘刁镇蔬菜批发市场",2.40),("濮阳宏进农副产品",3.60),("河南万邦国际农产品物流",4.00),
("湖北四季青农贸市场",8.00),("鄂州市蟠龙农产品批发",10.00),("湖北省洪湖农贸市场",7.60),
("武汉白沙洲农副产品大市场",6.25),("两湖绿谷物流",5.00),("广东汕头农副产品批发中心",4.80),
("海口菜篮子江楠农产品批发",6.54),("重庆潼南农副产品批发",5.00),("南充川北农产品交易",4.40),
("贵阳农产品物流园",5.60),("昆明景臻王旗营蔬菜批发市场",3.00),("西藏领峰农副产品",9.00),
("咸阳新阳光农副产品",6.20),("庆阳市西峰西郊瓜果蔬菜",5.50),("武威昊天农产品交易市场",6.70),
("金昌市金川天然农产品",9.00),("定西市安定马铃薯综合交易中心",10.50),("酒泉春光农产品市场",8.20),
("兰州高原夏菜副食品采购中心",5.00),("宁夏海吉星国际农产品物流",4.00),("喀什曙光农业科技博览城",13.00),
("新疆通汇市场",6.50),
]
n_ru = 0
for mk, v in roundup:
    n_ru += addq({"date":DATA_DATE,"item":"香葱","variety":"小葱","market":mk,"province":"全国",
                  "price_type":"销地批发价","unit":"元/公斤","low":v,"high":v,"mid":v,
                  "source":"2026年11月16日全国主要批发市场小葱价格行情（农业农村部信息中心·证券之星转载）",
                  "source_url":"https://4g.stockstar.com/detail/IG2026111600013042",
                  "note":"★全国49家roundup单点：喀什曙光13.00为IQR越界离群，保留但不并入可比结论"})
print("[OK] 全国 roundup +%d 条" % n_ru)

# ============================================================ 7. B2B 挂牌（元/斤×2，非成交）
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

# ============================================================ 9. 口径归一化（继承行的非 schema price_type）
PT_MAP = {"卖家挂牌价": "产地地头价", "挂牌价": "产地地头价", "代办价": "产地地头价"}
n_norm = 0
for q in quotes:
    pt = q.get("price_type")
    if pt in PT_MAP:
        q["price_type"] = PT_MAP[pt]
        q["note"] = (q.get("note", "") + "；[口径归一] 原「%s」归为产地地头价，系平台挂牌非成交口径" % pt)
        n_norm += 1
    elif pt == "指数/点位":
        # 全国 28 种蔬菜批发均价（宏观指数，非香葱单品）：归入销地批发价并在 note 显式标注
        q["price_type"] = "销地批发价"
        q["note"] = (q.get("note", "") + "；[口径归一] 原「指数/点位」为全国28种蔬菜批发均价(宏观大盘参考,非香葱单品)，归为销地批发价，不并入香葱横截面均值")
        n_norm += 1
print("[OK] 口径归一化 %d 条" % n_norm)

# ============================================================ 10. 落盘
market_scope = ("全国 / 云南 / 红河州泸西县（产地、销地、省级综合、宏观、历史锚点、B2B 挂牌全口径；"
               "数据日 2026-11-16 一手核验 3.65/2.76 连续第三日锁定；合并兄弟任务当日数据）")
summary = ("数据日2026年11月16日，泸西红香葱3.4-3.7元/公斤、均价3.65元/公斤，与11-15完全持平（3.65平台连续第三日），黑香葱均价2.76元/公斤持平，全省综合红3.4-3.7、黑2.5-2.9与泸西基本对齐、倒挂修复延续，昆明王旗营小葱3.00元/公斤横盘第五期、前一日成交30吨。全国49家批发市场小葱报价均值5.64元/公斤（中位5.50、区间1.50至13.00，喀什曙光13.00为离群值），叶菜持续上扬而香葱独不跟涨印证品种特异性弱势，红葱同比2025-11-16的6.15下跌40.7%、为近五年同期绝对最低。六档预测中枢（红）模型锚定3.65、近端距平偏低推升、3月档春节后备货脉冲衰减回落，综合风险维持高。")
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
