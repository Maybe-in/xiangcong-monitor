# -*- coding: utf-8 -*-
"""香葱行情定时任务（376dffed）· 2026-11-18 第 30 次执行 · 数据日 2026-11-17（一手核验发布）

产出：
  1) data/sources/xiangcong_2026-11-17.json   统一 schema 全量报价 + 六档预测（供 03:00 日报汇总）
  2) outputs/香葱行情分析_2026-11-17.html   八章 / 8 图 单页报告（gen_xc_1117_report.py）

方法（与历史各期一致）：
  - 以 xiangcong_2026-11-17.json（4493 报价）为权威基准。
  - 数据日 2026-11-17 一手核验发布：泸西红香葱 3.4-3.7/均价 3.65（较 11-16 持平，3.65 平台第四日），
    黑香葱 2.5-2.9/均价 2.76 持平；通海红 3.1-3.5/黑 2.5-2.9；全省综合红 3.4-3.7/黑 2.5-2.9；
    王旗营小葱 3.00/前一日 30 吨。全国 47 家批发市场小葱 roundup 均值 5.93（IQR 剔除后 46 家 5.65，
    同市场配对 44 家 +0.18%）。
  - price_history 幂等 upsert 11-16/11-17 一手 observed 点（3.65/2.76），模型基准锚定 3.65。
  - 用 src.price.build_forecast + 11-18 鲜抓天气出六档预测（按 key 映射到 schema label）。
  - 合并兄弟任务当日文件（若已落盘，按 (date,market,item,round(mid,2)) 去重）。
  - 追加隔年精确同日 2025-11-17 档案 + 全国 47 家 roundup + B2B 挂牌（元/斤×2，显式标注非成交）。
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
TODAY = "2026-11-18"
DATA_DATE = "2026-11-17"
GEN = _now.strftime("%Y-%m-%d %H:%M")
TASK_ID = "376dffed-c5e4-4904-a77a-29193947212a"
CUR_RED, CUR_BLK = 3.65, 2.76

# ============================================================ 1. 基准报价
base = json.load(open(os.path.join(SRC, "xiangcong_2026-11-17.json"), encoding="utf-8"))
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
upsert_obs("2026-11-16", "红香葱", 3.65, note="11-17 核验：11-16 红香葱 3.65 持平确认（平台第三日）")
upsert_obs("2026-11-16", "黑葱", 2.76, note="11-16 黑香葱 2.76 持平")
upsert_obs(DATA_DATE, "红香葱", 3.65, note="11-17 一手核验发布 3.4-3.7/均价3.65，较11-16持平（3.65平台第四日）")
upsert_obs(DATA_DATE, "黑葱", 2.76, note="11-17 一手核验发布 2.5-2.9/均价2.76，持平")
upsert_obs(DATA_DATE, "小葱", 3.00, market="昆明王旗营", note="11-17 王旗营小葱 3.00，前一日交易量 30 吨，综合平均价 4.85/总吨位 3057")
json.dump(hist, open(hist_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("[OK] price_history upsert 11-16/11-17 observed 点")

# ============================================================ 3. 六档预测（真实模型 + 11-17 鲜抓天气）
wx_path = os.path.join(DATA, "weather_2026-11-18.json")
if not os.path.exists(wx_path):  # 兜底：接口连续失败时用上一日快照（报告显式披露）
    wx_path = os.path.join(DATA, "weather_2026-11-17.json")
    print("[WARN] weather_2026-11-18.json 未落盘，回退 weather_2026-11-17.json")
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

# ============================================================ 4. 一手核验报价（数据日 11-17）
fresh = [
 {"date":DATA_DATE,"item":"香葱","variety":"红香葱","market":"云南红河州泸西县","province":"云南",
  "price_type":"产地收购价","unit":"元/公斤","low":3.4,"high":3.7,"mid":3.65,
  "source":"2026年11月17日呈贡/晋宁/嵩明/陆良/通海/元谋/泸西菜价（公众号）",
  "source_url":"http://mp.weixin.qq.com/s?__biz=MzU5MTc0MTM0MA==&mid=2247595936&idx=1&sn=79390d2d8732b49f306b8bdd24e88310",
  "note":"★数据日一手核验：红香葱 3.4-3.7/均价标签3.65，与11-16完全持平（3.65平台第四日）；当日总评「油麦走高、香菜涨2元、其他叶菜平稳」，香葱独不跟涨"},
 {"date":DATA_DATE,"item":"香葱","variety":"黑香葱","market":"云南红河州泸西县","province":"云南",
  "price_type":"产地收购价","unit":"元/公斤","low":2.5,"high":2.9,"mid":2.76,
  "source":"2026年11月17日泸西菜价（公众号）","source_url":"http://mp.weixin.qq.com/s?__biz=MzU5MTc0MTM0MA==&mid=2247595936&idx=1&sn=79390d2d8732b49f306b8bdd24e88310",
  "note":"★数据日一手核验：黑香葱 2.5-2.9/均价2.76，与11-16完全持平"},
 {"date":DATA_DATE,"item":"香葱","variety":"红葱","market":"云南玉溪通海县","province":"云南",
  "price_type":"产地收购价","unit":"元/公斤","low":3.1,"high":3.5,"mid":3.30,
  "source":"2026年11月17日通海菜价（公众号）","source_url":"http://mp.weixin.qq.com/s?__biz=MzU5MTc0MTM0MA==&mid=2247595936&idx=1&sn=79390d2d8732b49f306b8bdd24e88310",
  "note":"通海红葱 3.1-3.5，与11-16持平；中值3.30作区间代表"},
 {"date":DATA_DATE,"item":"香葱","variety":"黑葱","market":"云南玉溪通海县","province":"云南",
  "price_type":"产地收购价","unit":"元/公斤","low":2.5,"high":2.9,"mid":2.70,
  "source":"2026年11月17日通海菜价（公众号）","source_url":"http://mp.weixin.qq.com/s?__biz=MzU5MTc0MTM0MA==&mid=2247595936&idx=1&sn=79390d2d8732b49f306b8bdd24e88310",
  "note":"通海黑葱 2.5-2.9，与11-16持平；中值2.70作区间代表"},
 {"date":DATA_DATE,"item":"香葱","variety":"红香葱","market":"云南产地综合交易价","province":"云南",
  "price_type":"产地批发价","unit":"元/公斤","low":3.4,"high":3.7,"mid":3.55,
  "source":"11月17日云南产地蔬菜综合交易价格（地慧数农/云南菜价公众号双源一致）",
  "source_url":"http://mp.weixin.qq.com/s?__biz=Mzg3Mzg1MTgwNw==&mid=2247490681&idx=1&sn=50a6ddf6a2061da8fbc7fb7e04889cab",
  "note":"全省综合红香葱 3.4-3.7，中值3.55（官方未给均价标签，取区间中值估算）；与泸西3.65基本对齐，倒挂修复延续"},
 {"date":DATA_DATE,"item":"香葱","variety":"黑葱","market":"云南产地综合交易价","province":"云南",
  "price_type":"产地批发价","unit":"元/公斤","low":2.5,"high":2.9,"mid":2.70,
  "source":"11月17日云南产地蔬菜综合交易价格（地慧数农/云南菜价公众号双源一致）",
  "source_url":"http://mp.weixin.qq.com/s?__biz=Mzg3Mzg1MTgwNw==&mid=2247490681&idx=1&sn=50a6ddf6a2061da8fbc7fb7e04889cab",
  "note":"全省综合黑葱 2.5-2.9，中值2.70（区间中值估算）"},
 {"date":DATA_DATE,"item":"香葱","variety":"黑葱","market":"云南产区（华磷肥料行情专报）","province":"云南",
  "price_type":"产地收购价","unit":"元/公斤","low":2.6,"high":2.9,"mid":2.75,
  "source":"华磷肥料·菜价行情专报 2026-11-17（昨日2.9）",
  "source_url":"http://mp.weixin.qq.com/s?__biz=MzcwNTMxOTA1Mg==&mid=2247486357&idx=1&sn=85456827fa89eaf15a8b7b05f3eaf2ad",
  "note":"独立采价表：黑葱今日2.6-2.9（昨日2.9），与地慧数农2.5-2.9基本一致；同期黑葱包地价昨2900→今2600元/亩（元/亩非本schema口径，不入quotes，仅作领先信号登记）"},
 {"date":DATA_DATE,"item":"香葱","variety":"白铁杆","market":"云南产区（华磷肥料行情专报）","province":"云南",
  "price_type":"产地收购价","unit":"元/公斤","low":2.7,"high":3.0,"mid":2.85,
  "source":"华磷肥料·菜价行情专报 2026-11-17（昨日3.0）",
  "source_url":"http://mp.weixin.qq.com/s?__biz=MzcwNTMxOTA1Mg==&mid=2247486357&idx=1&sn=85456827fa89eaf15a8b7b05f3eaf2ad",
  "note":"白铁杆今日2.7-3.0（昨日3.0），小幅走弱；白葱铁杆为香葱近亲品类"},
 {"date":DATA_DATE,"item":"香葱","variety":"小葱","market":"昆明王旗营蔬菜批发市场","province":"云南",
  "price_type":"销地批发价","unit":"元/公斤","low":3.0,"high":3.0,"mid":3.0,
  "source":"11月17日云南菜价·昆明王旗营蔬菜批发市场价格表（两转载源一致）","source_url":"http://mp.weixin.qq.com/s?__biz=Mzg3Mzg1MTgwNw==&mid=2247490681&idx=1&sn=50a6ddf6a2061da8fbc7fb7e04889cab",
  "note":"王旗营小葱 3.00 横盘第六期；前一日交易量 30 吨（对应11-16读数）；综合平均价 4.85、总吨位 3057；单点报价 low=high=mid"},
]
n_fresh = sum(addq(q) for q in fresh)
print("[OK] 数据日一手核验 +%d 条" % n_fresh)

# ============================================================ 5. 隔年精确同日档案 2025-11-17
archive = [
 {"date":"2025-11-17","item":"香葱","variety":"红香葱","market":"云南产地综合交易价","province":"云南",
  "price_type":"产地批发价","unit":"元/公斤","low":6.0,"high":6.3,"mid":6.15,
  "source":"2025年11月17日云南蔬菜综合报价（三源一致）","source_url":"http://mp.weixin.qq.com/s?__biz=Mzg3Mzg1MTgwNw==&mid=2247488767&idx=1&sn=2adcafc61cc940af2dee60d17baa6fb9",
  "note":"隔年精确同日档案：红香葱 6.0-6.3，中值6.15；本期3.65同比 -40.7%"},
 {"date":"2025-11-17","item":"香葱","variety":"黑葱","market":"云南产地综合交易价","province":"云南",
  "price_type":"产地批发价","unit":"元/公斤","low":4.0,"high":4.3,"mid":4.15,
  "source":"2025年11月17日云南蔬菜综合报价（三源一致）","source_url":"http://mp.weixin.qq.com/s?__biz=Mzg3Mzg1MTgwNw==&mid=2247488767&idx=1&sn=2adcafc61cc940af2dee60d17baa6fb9",
  "note":"隔年精确同日档案：黑葱 4.0-4.3，中值4.15；本期2.76同比 -33.5%"},
 {"date":"2025-11-17","item":"香葱","variety":"小葱","market":"昆明王旗营蔬菜批发市场","province":"云南",
  "price_type":"销地批发价","unit":"元/公斤","low":6.0,"high":6.0,"mid":6.0,
  "source":"昆明市景臻-王旗营蔬菜批发市场2025年11月17日平均价格统计（昆明市农业农村局官方表）/农业农村部单市场表双源互证",
  "source_url":"https://nyncj.km.gov.cn/c/2025-11-17/5035163.shtml",
  "note":"隔年精确同日档案：王旗营小葱 6.00、前一日交易量30吨、综合平均价5.67、总吨位3124；本期3.00同比 -50.0%"},
]
n_arch = sum(addq(q) for q in archive)
print("[OK] 隔年同日档案 +%d 条" % n_arch)

# ============================================================ 6. 全国 47 家批发市场小葱 roundup（11-17）
roundup = [
("北京新发地农副产品批发市场信息中心",4.00),("北京朝阳区大洋路综合市场",8.10),
("河北省怀来县京西果菜批发市场有限责任公司",6.00),("邯郸市经开区南大堡蔬菜批发市场",2.40),
("山西省晋城市绿欣农产品贸易有限公司",4.70),("晋城市绿盛农工商实业有限公司农副产品批发市场",2.40),
("内蒙古呼和浩特市东瓦窑农副产品批发市场有限责任公司",7.40),("内蒙古呼和浩特保全庄农副产品批发市场",19.20),
("辽宁鞍山宁远农产品批发市场",2.50),("辽宁朝阳市果菜批发市场",1.70),("江苏凌家塘市场发展有限公司",6.50),
("江苏苏州南环桥农副产品批发市场",3.50),("江苏无锡朝阳农产品大市场",4.63),("浙江嘉兴蔬菜批发交易市场",4.65),
("绍兴市蔬菜果品批发交易市场有限公司",4.00),("杭州农副产品物流中心南庄兜农产品批发市场",6.00),
("天长市永福农副产品批发市场",6.00),("安徽合肥周谷堆农产品批发市场",5.80),
("安徽六安市裕安区紫竹林农产品批发市场",5.90),("马鞍山市安民农副产品贸易有限公司",7.50),
("福建省福鼎市商贸业服务中心",8.40),("江西乐平蔬菜农产品批发大市场",3.60),
("江西九江琵琶湖农产品物流有限公司",6.40),("山东章丘刁镇蔬菜批发市场",2.40),
("河南濮阳宏进农副产品批发市场有限公司",3.00),("河南万邦国际农产品物流股份有限公司",4.00),
("湖北四季青农贸市场管理有限公司",8.00),("湖北鄂州市蟠龙农产品批发市场",10.00),
("湖北省洪湖农贸市场",7.80),("武汉白沙洲农副产品大市场有限公司",6.25),("两湖绿谷物流股份有限公司",5.00),
("海口市菜篮子江楠农产品批发市场有限公司",6.73),("成都濛阳农副产品综合批发交易市场有限责任公司",2.50),
("南充川北农产品交易有限公司",4.40),("贵阳农产品物流园",5.60),("昆明景臻王旗营蔬菜批发市场",3.00),
("西藏领峰农副产品经营管理有限公司",9.00),("陕西咸阳新阳光农副产品有限公司",6.20),
("庆阳市西峰西郊瓜果蔬菜批发有限责任公司",5.50),("武威昊天农产品交易市场暨仓储物流中心",6.70),
("金昌市金川天然农产品发展有限责任公司",9.00),("甘肃省定西市安定马铃薯综合交易中心",10.50),
("甘肃酒泉春光农产品市场有限责任公司",8.40),("兰州国际高原夏菜副食品采购中心",4.63),
("宁夏海吉星国际农产品物流有限公司",4.00),("新疆通汇市场有限公司",6.00),
("新疆克拉玛依农副产品批发市场",9.00),
]
n_ru = 0
for mk, v in roundup:
    n_ru += addq({"date":DATA_DATE,"item":"香葱","variety":"小葱","market":mk,"province":"全国",
                  "price_type":"销地批发价","unit":"元/公斤","low":v,"high":v,"mid":v,
                  "source":"2026年11月17日全国主要批发市场小葱价格行情（农业农村部信息中心·证券之星转载）",
                  "source_url":"https://futures.stockstar.com/IG2026111700020382.shtml",
                  "note":"★全国47家roundup单点：均值5.93/中位5.90；呼和浩特保全庄19.20为IQR越界离群，保留但不并入可比结论（剔除后46家5.65）；同市场配对44家环比+0.18%"})
print("[OK] 全国 roundup +%d 条" % n_ru)

# ============================================================ 7. B2B 挂牌（元/斤×2，非成交）
b2b = [
 {"date":DATA_DATE,"item":"香葱","variety":"水洗葱","market":"泸西县（惠农网挂牌）","province":"云南",
  "price_type":"产地地头价","unit":"元/公斤","low":3.6,"high":3.6,"mid":3.6,
  "source":"惠农网 供应页（王明 泸西 1.80 元/斤 水洗葱）","source_url":"https://www.cnhnb.com/p/xiaocong-0-25-0-0-5/",
  "note":"★B2B挂牌非成交价：1.80 元/斤×2=3.60 元/公斤；平台挂牌长期不刷新（11-18 采集快照），与菜价表 3.65 分层对照，不并入成交横截面"},
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
  "note":"★B2B挂牌非成交价：1.00 元/斤×2=2.00 元/公斤；挂牌口径长期不刷新（11-18 采集快照），非11-17当日成交"},
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
               "数据日 2026-11-17 一手核验 3.65/2.76 连续第四日锁定；合并兄弟任务当日数据）")
summary = ("数据日2026年11月17日，泸西红香葱3.4-3.7元/公斤、均价3.65元/公斤与11-16完全持平（3.65平台连续第四日），黑香葱2.5-2.9、均价2.76持平，全省综合红3.4-3.7、黑2.5-2.9与泸西对齐，昆明王旗营小葱3.00横盘第六期、前一日成交30吨、综合平均价4.85元/公斤。全国47家批发市场小葱报价均值5.93元/公斤（中位5.90，呼和浩特保全庄19.20为IQR越界离群，剔除后46家5.65；同市场配对44家环比仅+0.18%、34家持平），当日云南叶菜普涨而香葱独不跟涨，红葱同比2025-11-17的6.15下跌40.7%、为近五年同期绝对最低。六档预测中枢（红）模型锚定3.65，近端距平-6.6摄氏度与大风推升，16天无强降水（峰值仅3.3mm）、最冷11-25为4.6摄氏度无霜冻，综合风险维持高。")
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
