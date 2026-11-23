# -*- coding: utf-8 -*-
"""香葱行情定时任务（376dffed）· 2026-11-23 第 35 次执行 · 数据日 2026-11-22（一手核验发布）

产出：
  1) data/sources/xiangcong_2026-11-23.json   统一 schema 全量报价 + 六档预测（供 03:00 日报汇总）
  2) outputs/香葱行情分析_2026-11-23.html   八章 / 8 图 单页报告（gen_xc_1123_report.py）

方法（与历史各期一致）：
  - 以 xiangcong_2026-11-22.json 为权威基准。
  - 数据日 11-22 一手核验：泸西红香葱 3.4-3.7/均价 3.65（较 11-21 持平，3.65 平台第九日），
    黑香葱 2.5-2.9/均价 2.76 持平；通海红 3.1-3.5/黑 2.5-2.9；全省综合两源一致红 3.4-3.7/黑 2.5-2.9；
    华磷黑葱 2.8-3.0、白铁杆 2.7-3.0、红香葱 3.4-3.7、黑葱包地价 3000 元/亩（上修）。
  - 价格横盘延续、需求侧王旗营小葱 2.00 低位企稳（前一日量 30 吨，与 11-21 持平）；官方总评「油麦连续下滑、包芥掉价、奶白金丝白涨2毛、香菜掉1元」，小香葱平稳。
  - 全国小葱 roundup 本期发布（农业农村部信息中心 41 家，均值 5.58/中位 5.50，区间 1.70~10.00，无喀什曙光离群值），
    全量入库；按 data-analysis 红线用同市场配对 37 家（vs 11-21）得 -0.82%，不直接比两组均值。
  - price_history 幂等 upsert 11-21/11-22 一手 observed 点，模型基准锚定 3.65。
  - 用 src.price.build_forecast + 11-23 鲜抓天气出六档预测（按 key 映射到 schema label）。
  - 合并兄弟任务当日文件（若已落盘，按 (date,market,variety,round(mid,2)) 去重）。
  - 追加隔年精确同日 2025-11-22 档案 + B2B 挂牌（元/斤×2，显式标注非成交）。
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
TODAY = "2026-11-23"
DATA_DATE = "2026-11-22"
GEN = _now.strftime("%Y-%m-%d %H:%M")
TASK_ID = "376dffed-c5e4-4904-a77a-29193947212a"

# ============================================================ 1. 基准报价
base = json.load(open(os.path.join(SRC, "xiangcong_2026-11-22.json"), encoding="utf-8"))
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
upsert_obs("2026-11-21", "红香葱", 3.65, note="11-22 核验：11-21 红香葱 3.65 持平确认（平台第八日）")
upsert_obs("2026-11-21", "黑葱", 2.76, note="11-21 黑香葱 2.76 持平")
upsert_obs(DATA_DATE, "红香葱", 3.65, note="11-22 一手核验发布 3.4-3.7/均价3.65，较11-21持平（3.65平台第九日）")
upsert_obs(DATA_DATE, "黑葱", 2.76, note="11-22 一手核验发布 2.5-2.9/均价2.76，持平")
upsert_obs(DATA_DATE, "小葱", 2.00, market="昆明王旗营", note="11-22 王旗营小葱 2.00 低位企稳（省级表+全国roundup双源互证），前一日交易量30吨，与11-21持平")
json.dump(hist, open(hist_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("[OK] price_history upsert 11-20/11-21 observed 点")

# ============================================================ 3. 六档预测（真实模型 + 11-21 鲜抓天气）
wx_path = os.path.join(DATA, "weather_2026-11-23.json")
if not os.path.exists(wx_path):
    wx_path = os.path.join(DATA, "weather_2026-11-22.json")
    print("[WARN] weather_2026-11-23.json 未落盘，回退 weather_2026-11-22.json")
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

# ============================================================ 4. 一手核验报价（数据日 11-21）
fresh = [
 {"date":DATA_DATE,"item":"香葱","variety":"红香葱","market":"云南红河州泸西县","province":"云南",
  "price_type":"产地收购价","unit":"元/公斤","low":3.4,"high":3.7,"mid":3.65,
  "source":"2026年11月22日呈贡/晋宁/嵩明/陆良/通海/元谋/泸西菜价（公众号 mid=2247595963）",
  "source_url":"http://mp.weixin.qq.com/s?__biz=MzU5MTc0MTM0MA==&mid=2247595963&idx=1&sn=6169ed4b81b4e523c040ce961f0ac00a",
  "note":"★数据日一手核验：红香葱 3.4-3.7/均价标签3.65，与11-21完全持平（3.65平台第九日）；当日总评「油麦连续下滑、包芥掉价、奶白金丝白涨2毛、香菜掉1元、花菜平稳、豆类平稳、小香葱平稳」"},
 {"date":DATA_DATE,"item":"香葱","variety":"黑香葱","market":"云南红河州泸西县","province":"云南",
  "price_type":"产地收购价","unit":"元/公斤","low":2.5,"high":2.9,"mid":2.76,
  "source":"2026年11月22日泸西菜价（公众号 mid=2247595963）","source_url":"http://mp.weixin.qq.com/s?__biz=MzU5MTc0MTM0MA==&mid=2247595963&idx=1&sn=6169ed4b81b4e523c040ce961f0ac00a",
  "note":"★数据日一手核验：黑香葱 2.5-2.9/均价2.76，与11-21完全持平"},
 {"date":DATA_DATE,"item":"香葱","variety":"红葱","market":"云南玉溪通海县","province":"云南",
  "price_type":"产地收购价","unit":"元/公斤","low":3.1,"high":3.5,"mid":3.30,
  "source":"2026年11月22日通海菜价（公众号，序号15）","source_url":"http://mp.weixin.qq.com/s?__biz=MzU5MTc0MTM0MA==&mid=2247595963&idx=1&sn=6169ed4b81b4e523c040ce961f0ac00a",
  "note":"通海红葱 3.1-3.5，与11-21持平；中值3.30作区间代表"},
 {"date":DATA_DATE,"item":"香葱","variety":"黑葱","market":"云南玉溪通海县","province":"云南",
  "price_type":"产地收购价","unit":"元/公斤","low":2.5,"high":2.9,"mid":2.70,
  "source":"2026年11月22日通海菜价（公众号，序号16）","source_url":"http://mp.weixin.qq.com/s?__biz=MzU5MTc0MTM0MA==&mid=2247595963&idx=1&sn=6169ed4b81b4e523c040ce961f0ac00a",
  "note":"通海黑葱 2.5-2.9，与11-21持平；中值2.70作区间代表"},
 {"date":DATA_DATE,"item":"香葱","variety":"红香葱","market":"云南产地综合交易价","province":"云南",
  "price_type":"产地批发价","unit":"元/公斤","low":3.4,"high":3.7,"mid":3.55,
  "source":"11月22日云南产地蔬菜综合交易价格（地慧数农 mid=2247490714 / 云南菜价公众号 mid=2653645907 两源一致，序号42）",
  "source_url":"http://mp.weixin.qq.com/s?__biz=Mzg3Mzg1MTgwNw==&mid=2247490714&idx=1&sn=5ff8cf22561af8dc7b38ab3bf2c2a544",
  "note":"全省综合红香葱 3.4-3.7，中值3.55（官方未给均价标签，取区间中值估算）；与泸西3.65对齐"},
 {"date":DATA_DATE,"item":"香葱","variety":"黑葱","market":"云南产地综合交易价","province":"云南",
  "price_type":"产地批发价","unit":"元/公斤","low":2.5,"high":2.9,"mid":2.70,
  "source":"11月22日云南产地蔬菜综合交易价格（地慧数农/云南菜价公众号两源一致，序号43）",
  "source_url":"http://mp.weixin.qq.com/s?__biz=Mzg3Mzg1MTgwNw==&mid=2247490714&idx=1&sn=5ff8cf22561af8dc7b38ab3bf2c2a544",
  "note":"全省综合黑葱 2.5-2.9，中值2.70（区间中值估算）"},
 {"date":DATA_DATE,"item":"香葱","variety":"黑葱","market":"云南产区（华磷肥料行情专报）","province":"云南",
  "price_type":"产地收购价","unit":"元/公斤","low":2.8,"high":3.0,"mid":2.90,
  "source":"华磷肥料·菜价行情专报 2026-11-22（昨日2.9，序号47）",
  "source_url":"http://mp.weixin.qq.com/s?__biz=MzcwNTMxOTA1Mg==&mid=2247486447&idx=1&sn=a4780d82f56bc7a2cb0f9640ad6bb657",
  "note":"独立采价表：黑葱今日2.8-3.0（昨日2.9），较地慧数农2.5-2.9略高（精品口径）；黑葱包地价昨2900→今3000元/亩（↑约300，元/亩非本schema口径，不入quotes，仅作领先信号登记——结束此前2600横盘，向上修正）"},
 {"date":DATA_DATE,"item":"香葱","variety":"白铁杆","market":"云南产区（华磷肥料行情专报）","province":"云南",
  "price_type":"产地收购价","unit":"元/公斤","low":2.7,"high":3.0,"mid":2.85,
  "source":"华磷肥料·菜价行情专报 2026-11-22（昨日3.0，序号49）",
  "source_url":"http://mp.weixin.qq.com/s?__biz=MzcwNTMxOTA1Mg==&mid=2247486447&idx=1&sn=a4780d82f56bc7a2cb0f9640ad6bb657",
  "note":"白铁杆今日2.7-3.0（昨日3.0），小幅走弱；白葱铁杆为香葱近亲品类"},
 {"date":DATA_DATE,"item":"香葱","variety":"红香葱","market":"云南产区（华磷肥料行情专报）","province":"云南",
  "price_type":"产地收购价","unit":"元/公斤","low":3.4,"high":3.7,"mid":3.55,
  "source":"华磷肥料·菜价行情专报 2026-11-22（昨日3.7，序号51）",
  "source_url":"http://mp.weixin.qq.com/s?__biz=MzcwNTMxOTA1Mg==&mid=2247486447&idx=1&sn=a4780d82f56bc7a2cb0f9640ad6bb657",
  "note":"华磷表红香葱今日3.4-3.7（昨日3.7），区间上沿3.7与泸西一致；独立采价源对照"},
 {"date":DATA_DATE,"item":"香葱","variety":"小葱","market":"昆明王旗营蔬菜批发市场","province":"云南",
  "price_type":"销地批发价","unit":"元/公斤","low":2.0,"high":2.0,"mid":2.0,
  "source":"11月22日云南菜价·昆明王旗营蔬菜批发市场价格表（地慧数农省级表 + 全国roundup第31条 昆明景臻王旗营 2.00 双源互证）","source_url":"http://mp.weixin.qq.com/s?__biz=Mzg3Mzg1MTgwNw==&mid=2247490714&idx=1&sn=5ff8cf22561af8dc7b38ab3bf2c2a544",
  "note":"王旗营小葱 2.00 低位企稳（11-20 破位后连续第三日持平），省级表与全国41家roundup双源互证；前一日交易量 30 吨（与11-21持平）；单点报价 low=high=mid"},
 {"date":DATA_DATE,"item":"香葱","variety":"香葱（宏观大盘参考）","market":"全国28种蔬菜均价","province":"全国",
  "price_type":"销地批发价","unit":"元/公斤","low":4.02,"high":4.02,"mid":4.02,
  "source":"农业农村部市场与信息化司 2026-11-22（28种蔬菜全国批发均价4.02、日环比-1.2%；蔬菜报公众号 mid=2247484959 / 2247485402 转载）","source_url":"https://pfsc.agri.cn/#/priceExponent",
  "note":"★宏观大盘参考：本期取得 11-22 的 28 种蔬菜均价 4.02 元/公斤（日环比-1.2%，较 11-19 的 4.17 继续回落）；转载源另列「农产品200指数126.14/菜篮子128.36」标注日期为 11-26（晚于本报告生成日），日期存疑故不采信；非香葱单品，不并入香葱横截面均值"},
]
n_fresh = sum(addq(q) for q in fresh)
print("[OK] 数据日一手核验 +%d 条" % n_fresh)

# ============================================================ 5. 隔年精确同日档案 2025-11-22
archive = [
 {"date":"2025-11-22","item":"香葱","variety":"红香葱","market":"云南产地综合交易价","province":"云南",
  "price_type":"产地批发价","unit":"元/公斤","low":5.4,"high":5.9,"mid":5.65,
  "source":"2025年11月22日云南菜价·云南产地蔬菜综合交易价格（公众号 mid=2247488803 / 2653643300 双源，序号42）","source_url":"http://mp.weixin.qq.com/s?__biz=Mzg3Mzg1MTgwNw==&mid=2247488803&idx=1&sn=d941fede1d9699f871d601edc842b390",
  "note":"隔年精确同日档案：红香葱 5.4-5.9，中值5.65；本期3.65同比 -35.4%"},
 {"date":"2025-11-22","item":"香葱","variety":"黑葱","market":"云南产地综合交易价","province":"云南",
  "price_type":"产地批发价","unit":"元/公斤","low":3.6,"high":4.1,"mid":3.85,
  "source":"2025年11月22日云南菜价·云南产地蔬菜综合交易价格（序号43）","source_url":"http://mp.weixin.qq.com/s?__biz=Mzg3Mzg1MTgwNw==&mid=2247488803&idx=1&sn=d941fede1d9699f871d601edc842b390",
  "note":"隔年精确同日档案：黑葱 3.6-4.1，中值3.85；本期2.76同比 -28.3%"},
 {"date":"2025-11-22","item":"香葱","variety":"小葱","market":"昆明王旗营蔬菜批发市场","province":"云南",
  "price_type":"销地批发价","unit":"元/公斤","low":4.0,"high":4.0,"mid":4.0,
  "source":"昆明市景臻-王旗营蔬菜批发市场2025年11月22日平均价格统计（昆明市农业农村局官方表 nyncj.km.gov.cn/c/2025-11-24/5036463.shtml）","source_url":"https://nyncj.km.gov.cn/c/2025-11-24/5036463.shtml",
  "note":"隔年精确同日档案：王旗营小葱 4.00、前一日交易量45吨、综合平均价5.87、总吨位2995；本期2.00同比 -50.0%"},
 {"date":"2025-11-22","item":"香葱","variety":"香葱头","market":"云南弥渡县（报告大厅）","province":"云南",
  "price_type":"产地收购价","unit":"元/公斤","low":7.3,"high":7.3,"mid":7.3,
  "source":"中国报告大厅 2025-11-22 葱头价格行情（云南弥渡 3.65 元/斤）","source_url":"https://www.chinabgao.com/jiage/82023553.html",
  "note":"隔年精确同日档案：香葱头（鳞茎/种用，非鲜食小香葱）3.65元/斤×2=7.30元/公斤，仅作葱类价格参考，不与鲜食香葱横比"},
]
n_arch = sum(addq(q) for q in archive)
print("[OK] 隔年同日档案 +%d 条" % n_arch)

# ============================================================ 6. 全国小葱 roundup 全量入库（11-22 发布，41 家）
roundup = [
 ("北京朝阳区大洋路综合市场","北京",8.00),("河北省怀来县京西果菜批发市场有限责任公司","河北",6.00),
 ("邯郸市经开区南大堡蔬菜批发市场","河北",2.60),("山西省晋城市绿欣农产品贸易有限公司","山西",4.90),
 ("晋城市绿盛农工商实业有限公司农副产品批发市场","山西",2.40),("内蒙古呼和浩特市东瓦窑农副产品批发市场有限责任公司","内蒙古",8.60),
 ("辽宁鞍山宁远农产品批发市场","辽宁",2.50),("辽宁朝阳市果菜批发市场","辽宁",1.70),
 ("江苏凌家塘市场发展有限公司","江苏",6.50),("江苏苏州南环桥农副产品批发市场","江苏",3.50),
 ("江苏无锡朝阳农产品大市场","江苏",6.44),("义乌市市场发展集团有限公司农批管理分公司","浙江",4.00),
 ("浙江嘉兴蔬菜批发交易市场","浙江",4.58),("绍兴市蔬菜果品批发交易市场有限公司","浙江",4.00),
 ("安徽合肥周谷堆农产品批发市场","安徽",5.80),("安徽六安市裕安区紫竹林农产品批发市场","安徽",6.00),
 ("马鞍山市安民农副产品贸易有限公司","安徽",5.80),("福建省福鼎市商贸业服务中心","福建",5.30),
 ("江西乐平蔬菜农产品批发大市场","江西",4.00),("山东章丘刁镇蔬菜批发市场","山东",2.40),
 ("河南万邦国际农产品物流股份有限公司","河南",4.80),("湖北四季青农贸市场管理有限公司","湖北",8.00),
 ("湖北鄂州市蟠龙农产品批发市场","湖北",10.00),("湖北省洪湖农贸市场","湖北",7.60),
 ("武汉白沙洲农副产品大市场有限公司","湖北",6.50),("两湖绿谷物流股份有限公司","湖北",5.00),
 ("广东汕头农副产品批发中心市场","广东",4.90),("海口市菜篮子江楠农产品批发市场有限公司","海南",6.76),
 ("南充川北农产品交易有限公司","四川",4.40),("贵阳农产品物流园","贵州",5.60),
 ("昆明景臻王旗营蔬菜批发市场","云南",2.00),("西藏领峰农副产品经营管理有限公司","西藏",9.00),
 ("陕西咸阳新阳光农副产品有限公司","陕西",6.30),("庆阳市西峰西郊瓜果蔬菜批发有限责任公司","甘肃",3.50),
 ("武威昊天农产品交易市场暨仓储物流中心","甘肃",6.70),("金昌市金川天然农产品发展有限责任公司","甘肃",9.00),
 ("甘肃省定西市安定马铃薯综合交易中心","甘肃",9.50),("甘肃酒泉春光农产品市场有限责任公司","甘肃",8.80),
 ("兰州国际高原夏菜副食品采购中心","甘肃",4.82),("宁夏海吉星国际农产品物流有限公司","宁夏",5.50),
 ("新疆通汇市场有限公司","新疆",5.00),
]
n_ru = 0
for mk, pv, p in roundup:
    extra = "；★全国roundup第31条双源互证王旗营2.00低位企稳（连续第三日）" if "王旗营" in mk else ""
    n_ru += addq({"date":DATA_DATE,"item":"香葱","variety":"小葱","market":mk,"province":pv,
                  "price_type":"销地批发价","unit":"元/公斤","low":p,"high":p,"mid":p,
                  "source":"2026年11月22日全国主要批发市场小葱价格行情（农业农村部信息中心·证券之星 IG2026112200001290，41家）","source_url":"https://futures.stockstar.com/IG2026112200001290.shtml",
                  "note":"★全国小葱roundup全量入库：%s %.2f 元/公斤（n=41，均值5.58/中位5.50/区间1.70~10.00，本期无喀什曙光离群值）%s" % (pv,p,extra)})
print("[OK] 全国小葱roundup +%d 条" % n_ru)

# ============================================================ 7. B2B 挂牌（元/斤×2，非成交）
b2b = [
 {"date":DATA_DATE,"item":"香葱","variety":"水洗葱","market":"泸西县（惠农网挂牌）","province":"云南",
  "price_type":"产地地头价","unit":"元/公斤","low":3.4,"high":3.4,"mid":3.4,
  "source":"惠农网 供应页（泸西 1.70 元/斤 水洗葱/香葱地头价）","source_url":"https://www.cnhnb.com/p/xiaocong-0-25-0-0-4/",
  "note":"★B2B挂牌非成交价：1.70 元/斤×2=3.40 元/公斤；平台挂牌长期不刷新（11-22 采集快照），与菜价表3.65分层对照，不并入成交横截面"},
 {"date":DATA_DATE,"item":"香葱","variety":"云南香葱","market":"泸西县（惠农网挂牌）","province":"云南",
  "price_type":"产地地头价","unit":"元/公斤","low":4.0,"high":4.0,"mid":4.0,
  "source":"惠农网 供应页（泸西 2.00 元/斤 云南香葱）","source_url":"https://www.cnhnb.com/p/xiaocong-0-25-0-0-7/",
  "note":"★B2B挂牌非成交价：2.00 元/斤×2=4.00 元/公斤（11-22 采集快照）"},
 {"date":DATA_DATE,"item":"香葱","variety":"小香葱","market":"泸西县（惠农网挂牌）","province":"云南",
  "price_type":"产地地头价","unit":"元/公斤","low":3.2,"high":3.2,"mid":3.2,
  "source":"惠农网 供应页（田壮禾 泸西 1.60 元/斤 产地直发小香葱含黑/白/红葱）","source_url":"https://www.cnhnb.com/p/xiaocong-0-25-0-0-7/",
  "note":"★B2B挂牌非成交价：1.60 元/斤×2=3.20 元/公斤（11-22 采集快照）"},
 {"date":DATA_DATE,"item":"香葱","variety":"精品红葱","market":"泸西县（一亩田挂牌）","province":"云南",
  "price_type":"产地地头价","unit":"元/公斤","low":2.0,"high":2.0,"mid":2.0,
  "source":"一亩田 泸西产地货源（精品红葱 1.00 元/斤）","source_url":"https://m.ymt.com/shop/2925430",
  "note":"★B2B挂牌非成交价：1.00 元/斤×2=2.00 元/公斤；挂牌口径长期不刷新（11-22 采集快照），非11-21当日成交"},
 {"date":DATA_DATE,"item":"香葱","variety":"精品黑白葱","market":"泸西县（一亩田挂牌）","province":"云南",
  "price_type":"产地地头价","unit":"元/公斤","low":1.6,"high":1.6,"mid":1.6,
  "source":"一亩田 泸西产地货源（精品黑白葱 0.80 元/斤）","source_url":"https://m.ymt.com/shop/2925430",
  "note":"★B2B挂牌非成交价：0.80 元/斤×2=1.60 元/公斤（11-22 采集快照）"},
 {"date":DATA_DATE,"item":"香葱","variety":"小红葱","market":"泸西县（一亩田挂牌）","province":"云南",
  "price_type":"产地地头价","unit":"元/公斤","low":2.4,"high":2.4,"mid":2.4,
  "source":"一亩田 供应页（小红葱 1.20 元/斤 云南红河泸西县，40-45规格）","source_url":"https://www.ymt.com/supply/59212963",
  "note":"★B2B挂牌非成交价：1.20 元/斤×2=2.40 元/公斤（11-22 采集快照）"},
 {"date":DATA_DATE,"item":"香葱","variety":"精品小香葱","market":"泸西县（惠农网挂牌）","province":"云南",
  "price_type":"产地地头价","unit":"元/公斤","low":4.8,"high":5.6,"mid":5.2,
  "source":"惠农网 供应页（泸西 2.40-2.80 元/斤 精品小香葱）","source_url":"https://www.cnhnb.com/p/xiaocong-0-25-0-0-7/",
  "note":"★B2B精品挂牌非成交价：2.40-2.80 元/斤×2=4.80-5.60 元/公斤；规格溢价，非统货成交价（11-22 采集快照）"},
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
        u = str(q.get("unit", ""))
        if "斤" in u and "公斤" not in u:
            continue
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(q.get("date"))):
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
               "数据日 2026-11-22 一手核验 3.65/2.76 连续第九日锁定、王旗营小葱 2.00 低位企稳连续第三日；合并兄弟任务当日数据）")
summary = ("数据日2026年11月22日，泸西红香葱均价3.65元/公斤、黑香葱2.76与11-21完全持平（3.65平台连续第九日），全省综合两源一致红3.4-3.7、黑2.5-2.9与泸西对齐，王旗营小葱2.00低位企稳连续第三日、前一日成交30吨持平。全国小葱roundup本期发布（41家均值5.58、中位5.50、区间1.70~10.00，无喀什离群值），按同市场配对37家较11-21微跌0.82%、近乎持平。六档中枢（红）锚定3.65、近端距平-5.5℃且11/24-25短时降温降水，产地横盘叠加销地低位，综合风险维持高；同比2025-11-22的5.65下跌35.4%、为近五年同期绝对最低。")
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
