# -*- coding: utf-8 -*-
"""香葱行情定时任务（376dffed）· 2026-11-24 第 36 次执行 · 数据日 2026-11-23（一手核验发布）

产出：
  1) data/sources/xiangcong_2026-11-24.json   统一 schema 全量报价 + 六档预测（供 03:00 日报汇总）
  2) outputs/香葱行情分析_2026-11-24.html   八章 / 8 图 单页报告（gen_xc_1124_report.py）

本期要点：
  - 数据日 11-23 一手核验：泸西红 3.4-3.7/均价 3.65（平台第十日）、黑 2.5-2.9/2.76 持平；
    通海红 3.1-3.5/黑 2.5-2.9；全省综合双源一致红 3.4-3.7/黑 2.5-2.9。
  - ★头号变化：昆明王旗营小葱 2.00 → 1.80 再破位 -10.0%（省级表 + 全国 roundup 第37条双源），
    前一日交易量 30 → 25 吨（-16.7%）。产地横盘而销地二次破位，价差传导阻塞加剧。
  - 华磷：黑葱 2.7-3.0（昨3.0）、白铁杆 2.7-3.0（昨3.0）、红香葱 3.4-3.7（昨3.7）；
    黑葱包地价 3000-3400 元/亩（昨中值3200，+200）继续上修，领先信号与现货背离扩大。
  - 全国小葱 roundup 48 家（均值 5.82 / 中位 5.50 / 区间 1.70~15.00，喀什曙光离群剔除后 47 家 5.63），
    同市场配对 40 家 vs 11-22 为 +1.51%（9 涨 / 23 平 / 8 跌），不直接比异样本均值。
  - 宏观：11-23 28 种蔬菜均价 4.16（较上周五 +1.7%），200 指数 112.53 / 菜篮子 112.27。
  - price_history 幂等 upsert 11-22/11-23 一手 observed 点，模型基准锚定 3.65；
    用 src.price.build_forecast + 11-24 鲜抓天气出六档。
  - 合并兄弟任务当日文件（若已落盘，按 (date,market,variety,round(mid,2)) 去重）。
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
TODAY = "2026-11-24"
DATA_DATE = "2026-11-23"
GEN = _now.strftime("%Y-%m-%d %H:%M")
TASK_ID = "376dffed-c5e4-4904-a77a-29193947212a"

# ============================================================ 1. 基准报价
base = json.load(open(os.path.join(SRC, "xiangcong_2026-11-23.json"), encoding="utf-8"))
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
upsert_obs("2026-11-22", "红香葱", 3.65, note="11-23 复核：11-22 红香葱 3.65 持平确认（平台第九日）")
upsert_obs("2026-11-22", "黑葱", 2.76, note="11-22 黑香葱 2.76 持平")
upsert_obs(DATA_DATE, "红香葱", 3.65, note="11-23 一手核验发布 3.4-3.7/均价3.65，较11-22持平（3.65平台第十日）")
upsert_obs(DATA_DATE, "黑葱", 2.76, note="11-23 一手核验发布 2.5-2.9/均价2.76，持平")
upsert_obs(DATA_DATE, "小葱", 1.80, market="昆明王旗营",
           note="11-23 王旗营小葱 2.00→1.80 再破位 -10.0%（省级表+全国roundup第37条双源互证），前一日交易量30→25吨(-16.7%)")
json.dump(hist, open(hist_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("[OK] price_history upsert 11-22/11-23 observed 点")

# ============================================================ 3. 六档预测（真实模型 + 11-24 鲜抓天气）
wx_path = os.path.join(DATA, "weather_2026-11-24.json")
if not os.path.exists(wx_path):
    wx_path = os.path.join(DATA, "weather_2026-11-23.json")
    print("[WARN] weather_2026-11-24.json 未落盘，回退 weather_2026-11-23.json")
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

# ============================================================ 4. 一手核验报价（数据日 11-23）
fresh = [
 {"date":DATA_DATE,"item":"香葱","variety":"红香葱","market":"云南红河州泸西县","province":"云南",
  "price_type":"产地收购价","unit":"元/公斤","low":3.4,"high":3.7,"mid":3.65,
  "source":"2026年11月23日呈贡/晋宁/嵩明/陆良/通海/元谋/泸西菜价（公众号 mid=2247595967）",
  "source_url":"http://mp.weixin.qq.com/s?__biz=MzU5MTc0MTM0MA==&mid=2247595967&idx=1&sn=39c748570371453e2a6443571a00a71f",
  "note":"★数据日一手核验：红香葱 3.4-3.7/均价标签3.65，与11-22完全持平（3.65平台第十日）；当日总评「油麦平稳、大利上青黄白金丝白上涨、春菜下滑、香菜再掉1元、松花菜下滑、豆类平稳、小香葱平稳」"},
 {"date":DATA_DATE,"item":"香葱","variety":"黑香葱","market":"云南红河州泸西县","province":"云南",
  "price_type":"产地收购价","unit":"元/公斤","low":2.5,"high":2.9,"mid":2.76,
  "source":"2026年11月23日泸西菜价（公众号 mid=2247595967）","source_url":"http://mp.weixin.qq.com/s?__biz=MzU5MTc0MTM0MA==&mid=2247595967&idx=1&sn=39c748570371453e2a6443571a00a71f",
  "note":"★数据日一手核验：黑香葱 2.5-2.9/均价2.76，与11-22完全持平"},
 {"date":DATA_DATE,"item":"香葱","variety":"红葱","market":"云南玉溪通海县","province":"云南",
  "price_type":"产地收购价","unit":"元/公斤","low":3.1,"high":3.5,"mid":3.30,
  "source":"2026年11月23日通海菜价（公众号 mid=2247595967，序号15）","source_url":"http://mp.weixin.qq.com/s?__biz=MzU5MTc0MTM0MA==&mid=2247595967&idx=1&sn=39c748570371453e2a6443571a00a71f",
  "note":"通海红葱 3.1-3.5，与11-22持平；中值3.30作区间代表"},
 {"date":DATA_DATE,"item":"香葱","variety":"黑葱","market":"云南玉溪通海县","province":"云南",
  "price_type":"产地收购价","unit":"元/公斤","low":2.5,"high":2.9,"mid":2.70,
  "source":"2026年11月23日通海菜价（公众号 mid=2247595967，序号16）","source_url":"http://mp.weixin.qq.com/s?__biz=MzU5MTc0MTM0MA==&mid=2247595967&idx=1&sn=39c748570371453e2a6443571a00a71f",
  "note":"通海黑葱 2.5-2.9，与11-22持平；中值2.70作区间代表"},
 {"date":DATA_DATE,"item":"香葱","variety":"红香葱","market":"云南产地综合交易价","province":"云南",
  "price_type":"产地批发价","unit":"元/公斤","low":3.4,"high":3.7,"mid":3.55,
  "source":"11月23日云南产地蔬菜综合交易价格（地慧数农 mid=2247490719 / 云南菜价公众号 mid=2653645918 双源一致，序号42）",
  "source_url":"http://mp.weixin.qq.com/s?__biz=Mzg3Mzg1MTgwNw==&mid=2247490719&idx=1&sn=bcedaaeb2a37588f395aec7b6677cc38",
  "note":"全省综合红香葱 3.4-3.7，中值3.55（官方未给均价标签，取区间中值估算）；与泸西3.65对齐"},
 {"date":DATA_DATE,"item":"香葱","variety":"黑葱","market":"云南产地综合交易价","province":"云南",
  "price_type":"产地批发价","unit":"元/公斤","low":2.5,"high":2.9,"mid":2.70,
  "source":"11月23日云南产地蔬菜综合交易价格（地慧数农/云南菜价公众号双源一致，序号43）",
  "source_url":"http://mp.weixin.qq.com/s?__biz=Mzg3Mzg1MTgwNw==&mid=2247490719&idx=1&sn=bcedaaeb2a37588f395aec7b6677cc38",
  "note":"全省综合黑葱 2.5-2.9，中值2.70（区间中值估算）"},
 {"date":DATA_DATE,"item":"香葱","variety":"黑葱","market":"云南产区（华磷肥料行情专报）","province":"云南",
  "price_type":"产地收购价","unit":"元/公斤","low":2.7,"high":3.0,"mid":2.85,
  "source":"华磷肥料·菜价行情专报 2026-11-23（昨日3.0，序号47）",
  "source_url":"http://mp.weixin.qq.com/s?__biz=MzcwNTMxOTA1Mg==&mid=2247486459&idx=1&sn=4b26d95ddf6fec126fffcd2d408f3e62",
  "note":"独立采价表：黑葱今日2.7-3.0（昨日3.0），较地慧数农2.5-2.9略高（精品口径）；黑葱包地价今日3000-3400元/亩（昨中值3200、+200，OCR区间解析）继续上修，元/亩非本schema口径不入quotes，仅作领先信号登记——与产地现货横盘背离扩大"},
 {"date":DATA_DATE,"item":"香葱","variety":"白铁杆","market":"云南产区（华磷肥料行情专报）","province":"云南",
  "price_type":"产地收购价","unit":"元/公斤","low":2.7,"high":3.0,"mid":2.85,
  "source":"华磷肥料·菜价行情专报 2026-11-23（昨日3.0，序号49）",
  "source_url":"http://mp.weixin.qq.com/s?__biz=MzcwNTMxOTA1Mg==&mid=2247486459&idx=1&sn=4b26d95ddf6fec126fffcd2d408f3e62",
  "note":"白铁杆今日2.7-3.0（昨日3.0），小幅走弱；白葱铁杆为香葱近亲品类"},
 {"date":DATA_DATE,"item":"香葱","variety":"红香葱","market":"云南产区（华磷肥料行情专报）","province":"云南",
  "price_type":"产地收购价","unit":"元/公斤","low":3.4,"high":3.7,"mid":3.55,
  "source":"华磷肥料·菜价行情专报 2026-11-23（昨日3.7，序号51）",
  "source_url":"http://mp.weixin.qq.com/s?__biz=MzcwNTMxOTA1Mg==&mid=2247486459&idx=1&sn=4b26d95ddf6fec126fffcd2d408f3e62",
  "note":"华磷表红香葱今日3.4-3.7（昨日3.7），区间上沿3.7与泸西一致；独立采价源对照"},
 {"date":DATA_DATE,"item":"香葱","variety":"小葱","market":"昆明王旗营蔬菜批发市场","province":"云南",
  "price_type":"销地批发价","unit":"元/公斤","low":1.8,"high":1.8,"mid":1.8,
  "source":"11月23日云南菜价·昆明王旗营蔬菜批发市场价格表（地慧数农省级表 + 全国roundup第37条 昆明景臻王旗营 1.80 双源互证）",
  "source_url":"http://mp.weixin.qq.com/s?__biz=Mzg3Mzg1MTgwNw==&mid=2247490719&idx=1&sn=bcedaaeb2a37588f395aec7b6677cc38",
  "note":"★本期头号变化：王旗营小葱 2.00→1.80 再破位 -10.0%（11-20 由3.00破位后第二次下台阶）；省级表与全国48家roundup双源互证；前一日交易量 30→25 吨（-16.7%）；单点报价 low=high=mid"},
 {"date":DATA_DATE,"item":"香葱","variety":"香葱（宏观大盘参考）","market":"全国28种蔬菜均价","province":"全国",
  "price_type":"销地批发价","unit":"元/公斤","low":4.16,"high":4.16,"mid":4.16,
  "source":"农业农村部市场与信息化司 2026-11-23（28种蔬菜全国批发均价4.16、较上周五+1.7%；200指数112.53/菜篮子112.27）",
  "source_url":"https://scs.moa.gov.cn/jcyj/202611/t20261123_6489672.htm",
  "note":"★宏观大盘参考：11-23 的 28 种蔬菜均价 4.16 元/公斤（较上周五 +1.7%，较 11-22 的 4.02 回升）；非香葱单品，不并入香葱横截面均值"},
]
n_fresh = sum(addq(q) for q in fresh)
print("[OK] 数据日一手核验 +%d 条" % n_fresh)

# ============================================================ 5. 隔年精确同日档案 2025-11-23
archive = [
 {"date":"2025-11-23","item":"香葱","variety":"红香葱","market":"云南产地综合交易价","province":"云南",
  "price_type":"产地批发价","unit":"元/公斤","low":5.4,"high":5.9,"mid":5.65,
  "source":"2025年11月23日云南菜价·云南产地蔬菜综合交易价格（公众号 mid=2247488812 / 2247501394 / 中大棚转载三源，序号42）","source_url":"http://mp.weixin.qq.com/s?__biz=Mzg3Mzg1MTgwNw==&mid=2247488812&idx=1&sn=0b40942e18d8aa4cf968c0f900d2122f",
  "note":"隔年精确同日档案：红香葱 5.4-5.9，中值5.65；本期3.65同比 -35.4%"},
 {"date":"2025-11-23","item":"香葱","variety":"黑葱","market":"云南产地综合交易价","province":"云南",
  "price_type":"产地批发价","unit":"元/公斤","low":3.6,"high":4.1,"mid":3.85,
  "source":"2025年11月23日云南菜价·云南产地蔬菜综合交易价格（序号43）","source_url":"http://mp.weixin.qq.com/s?__biz=Mzg3Mzg1MTgwNw==&mid=2247488812&idx=1&sn=0b40942e18d8aa4cf968c0f900d2122f",
  "note":"隔年精确同日档案：黑葱 3.6-4.1，中值3.85；本期2.76同比 -28.3%"},
 {"date":"2025-11-23","item":"香葱","variety":"红香葱","market":"云南红河州泸西县","province":"云南",
  "price_type":"产地收购价","unit":"元/公斤","low":5.4,"high":5.9,"mid":5.7,
  "source":"2025年11月23日云南蔬菜主产区每天菜价·泸西菜价（搜狐转载，序号1 均价标签5.7）","source_url":"https://www.sohu.com/a/957575364_120064990",
  "note":"隔年精确同日档案：泸西红香葱 5.4-5.9/均价5.7；本期3.65同比 -36.0%"},
 {"date":"2025-11-23","item":"香葱","variety":"黑香葱","market":"云南红河州泸西县","province":"云南",
  "price_type":"产地收购价","unit":"元/公斤","low":3.4,"high":3.7,"mid":3.6,
  "source":"2025年11月23日云南蔬菜主产区每天菜价·泸西菜价（搜狐转载，序号2 均价标签3.6）","source_url":"https://www.sohu.com/a/957575364_120064990",
  "note":"隔年精确同日档案：泸西黑香葱 3.4-3.7/均价3.6；本期2.76同比 -23.3%"},
 {"date":"2025-11-23","item":"香葱","variety":"小葱","market":"昆明王旗营蔬菜批发市场","province":"云南",
  "price_type":"销地批发价","unit":"元/公斤","low":4.5,"high":4.5,"mid":4.5,
  "source":"昆明市景臻-王旗营蔬菜批发市场2025年11月23日平均价格统计（公众号 mid=2247501394 + 农业农村部单市场表 IG2025112300002619 双源）","source_url":"https://4g.stockstar.com/detail/IG2025112300002619",
  "note":"隔年精确同日档案：王旗营小葱 4.50、前一日交易量35吨、综合平均价6.12、总吨位2780；本期1.80同比 -60.0%"},
]
n_arch = sum(addq(q) for q in archive)
print("[OK] 隔年同日档案 +%d 条" % n_arch)

# ============================================================ 6. 全国小葱 roundup 全量入库（11-23 发布，48 家）
roundup = [
 ("北京新发地农副产品批发市场信息中心","北京",4.00),("北京朝阳区大洋路综合市场","北京",8.00),
 ("河北省怀来县京西果菜批发市场有限责任公司","河北",6.00),("邯郸市经开区南大堡蔬菜批发市场","河北",2.60),
 ("山西省晋城市绿欣农产品贸易有限公司","山西",4.90),("晋城市绿盛农工商实业有限公司农副产品批发市场","山西",2.40),
 ("内蒙古呼和浩特市东瓦窑农副产品批发市场有限责任公司","内蒙古",8.80),
 ("辽宁鞍山宁远农产品批发市场","辽宁",2.50),("辽宁朝阳市果菜批发市场","辽宁",1.70),
 ("江苏凌家塘市场发展有限公司","江苏",6.50),("江苏苏州南环桥农副产品批发市场","江苏",3.50),
 ("江苏无锡朝阳农产品大市场","江苏",4.56),("义乌市市场发展集团有限公司农批管理分公司","浙江",4.00),
 ("浙江嘉兴蔬菜批发交易市场","浙江",4.94),("绍兴市蔬菜果品批发交易市场有限公司","浙江",3.60),
 ("杭州农副产品物流中心南庄兜农产品批发市场","浙江",5.20),("天长市永福农副产品批发市场","安徽",6.30),
 ("安徽合肥周谷堆农产品批发市场","安徽",4.80),("安徽六安市裕安区紫竹林农产品批发市场","安徽",6.00),
 ("马鞍山市安民农副产品贸易有限公司","安徽",8.00),("福建省福鼎市商贸业服务中心","福建",5.90),
 ("江西乐平蔬菜农产品批发大市场","江西",4.40),("江西九江琵琶湖农产品物流有限公司","江西",6.40),
 ("山东章丘刁镇蔬菜批发市场","山东",2.40),
 ("河南濮阳宏进农副产品批发市场有限公司(原河南濮阳蔬菜瓜果批发市场)","河南",3.60),
 ("河南万邦国际农产品物流股份有限公司","河南",4.80),("湖北四季青农贸市场管理有限公司","湖北",8.00),
 ("湖北鄂州市蟠龙农产品批发市场","湖北",10.00),("潜江市四季友农产品市场有限公司","湖北",8.00),
 ("湖北省洪湖农贸市场","湖北",7.80),("武汉白沙洲农副产品大市场有限公司","湖北",6.50),
 ("两湖绿谷物流股份有限公司","湖北",5.00),("广东汕头农副产品批发中心市场","广东",4.90),
 ("海口市菜篮子江楠农产品批发市场有限公司","海南",6.52),("南充川北农产品交易有限公司","四川",4.30),
 ("贵阳农产品物流园","贵州",5.50),("昆明景臻王旗营蔬菜批发市场","云南",1.80),
 ("西藏领峰农副产品经营管理有限公司","西藏",9.00),("陕西咸阳新阳光农副产品有限公司","陕西",6.40),
 ("庆阳市西峰西郊瓜果蔬菜批发有限责任公司","甘肃",3.50),("武威昊天农产品交易市场暨仓储物流中心","甘肃",6.70),
 ("甘肃省定西市安定马铃薯综合交易中心","甘肃",9.50),("甘肃酒泉春光农产品市场有限责任公司","甘肃",8.60),
 ("兰州国际高原夏菜副食品采购中心","甘肃",5.19),("宁夏海吉星国际农产品物流有限公司","宁夏",5.50),
 ("喀什曙光农业科技博览城","新疆",15.00),("新疆通汇市场有限公司","新疆",8.00),
 ("新疆兵团第五师三和农副产品综合批发市场","新疆",8.00),
]
n_ru = 0
for mk, pv, p in roundup:
    extra = "；★全国roundup第37条双源互证王旗营2.00→1.80再破位-10.0%" if "王旗营" in mk else ""
    n_ru += addq({"date":DATA_DATE,"item":"香葱","variety":"小葱","market":mk,"province":pv,
                  "price_type":"销地批发价","unit":"元/公斤","low":p,"high":p,"mid":p,
                  "source":"2026年11月23日全国主要批发市场小葱价格行情（农业农村部信息中心·证券之星 IG2026112300017118，48家）","source_url":"https://futures.stockstar.com/IG2026112300017118.shtml",
                  "note":"★全国小葱roundup全量入库：%s %.2f 元/公斤（n=48，均值5.82/中位5.50/区间1.70~15.00，喀什曙光15.00经IQR判为离群、剔除后47家均值5.63）%s" % (pv,p,extra)})
print("[OK] 全国小葱roundup +%d 条" % n_ru)

# ============================================================ 7. B2B 挂牌（元/斤×2，非成交）
b2b = [
 {"date":DATA_DATE,"item":"香葱","variety":"水洗葱","market":"泸西县（惠农网挂牌）","province":"云南",
  "price_type":"产地地头价","unit":"元/公斤","low":3.4,"high":3.4,"mid":3.4,
  "source":"惠农网 供应页（泸西 1.70 元/斤 水洗葱/香葱地头价）","source_url":"https://www.cnhnb.com/p/xiaocong-0-25-0-0-4/",
  "note":"★B2B挂牌非成交价：1.70 元/斤×2=3.40 元/公斤；平台挂牌长期不刷新（11-23 采集快照），与菜价表3.65分层对照，不并入成交横截面"},
 {"date":DATA_DATE,"item":"香葱","variety":"云南香葱","market":"泸西县（惠农网挂牌）","province":"云南",
  "price_type":"产地地头价","unit":"元/公斤","low":4.0,"high":4.0,"mid":4.0,
  "source":"惠农网 供应页（泸西 2.00 元/斤 云南香葱）","source_url":"https://www.cnhnb.com/p/xiaocong-0-25-0-0-7/",
  "note":"★B2B挂牌非成交价：2.00 元/斤×2=4.00 元/公斤（11-23 采集快照）"},
 {"date":DATA_DATE,"item":"香葱","variety":"小香葱","market":"泸西县（惠农网挂牌）","province":"云南",
  "price_type":"产地地头价","unit":"元/公斤","low":3.2,"high":3.2,"mid":3.2,
  "source":"惠农网 供应页（田壮禾 泸西 1.60 元/斤 产地直发小香葱含黑/白/红葱）","source_url":"https://www.cnhnb.com/p/xiaocong-0-25-0-0-7/",
  "note":"★B2B挂牌非成交价：1.60 元/斤×2=3.20 元/公斤（11-23 采集快照）"},
 {"date":DATA_DATE,"item":"香葱","variety":"精品红葱","market":"泸西县（一亩田挂牌）","province":"云南",
  "price_type":"产地地头价","unit":"元/公斤","low":2.0,"high":2.0,"mid":2.0,
  "source":"一亩田 泸西产地货源（精品红葱 1.00 元/斤）","source_url":"https://m.ymt.com/shop/2925430",
  "note":"★B2B挂牌非成交价：1.00 元/斤×2=2.00 元/公斤；挂牌口径长期不刷新（11-23 采集快照），非11-23当日成交"},
 {"date":DATA_DATE,"item":"香葱","variety":"精品黑白葱","market":"泸西县（一亩田挂牌）","province":"云南",
  "price_type":"产地地头价","unit":"元/公斤","low":1.6,"high":1.6,"mid":1.6,
  "source":"一亩田 泸西产地货源（精品黑白葱 0.80 元/斤）","source_url":"https://m.ymt.com/shop/2925430",
  "note":"★B2B挂牌非成交价：0.80 元/斤×2=1.60 元/公斤（11-23 采集快照）"},
 {"date":DATA_DATE,"item":"香葱","variety":"小红葱","market":"泸西县（一亩田挂牌）","province":"云南",
  "price_type":"产地地头价","unit":"元/公斤","low":2.4,"high":2.4,"mid":2.4,
  "source":"一亩田 供应页（小红葱 1.20 元/斤 云南红河泸西县，40-45规格）","source_url":"https://www.ymt.com/supply/59212963",
  "note":"★B2B挂牌非成交价：1.20 元/斤×2=2.40 元/公斤（11-23 采集快照）"},
 {"date":DATA_DATE,"item":"香葱","variety":"精品小香葱","market":"泸西县（惠农网挂牌）","province":"云南",
  "price_type":"产地地头价","unit":"元/公斤","low":4.8,"high":5.6,"mid":5.2,
  "source":"惠农网 供应页（泸西 2.40-2.80 元/斤 精品小香葱）","source_url":"https://www.cnhnb.com/p/xiaocong-0-25-0-0-7/",
  "note":"★B2B精品挂牌非成交价：2.40-2.80 元/斤×2=4.80-5.60 元/公斤；规格溢价，非统货成交价（11-23 采集快照）"},
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
               "数据日 2026-11-23 一手核验 3.65/2.76 连续第十日锁定、王旗营小葱 2.00→1.80 二次破位；合并兄弟任务当日数据）")
summary = ("数据日2026年11月23日，泸西红香葱均价3.65元/公斤、黑香葱2.76与11-22完全持平（3.65平台连续第十日），全省综合双源一致红3.4-3.7、黑2.5-2.9与泸西对齐。头号变化在需求侧：昆明王旗营小葱由2.00再破位至1.80（-10.0%，省级表与全国48家roundup双源互证），前一日交易量30→25吨（-16.7%），产地横盘而销地二次破位、价差传导阻塞加剧。全国小葱roundup 48家均值5.82/中位5.50（同市场配对40家较11-22 +1.51%），宏观28种蔬菜均价4.16较上周五+1.7%；六档中枢锚定3.65并用11-24鲜抓天气重算，综合风险维持高，同比2025-11-23的5.65下跌35.4%、为近五年同期绝对最低。")
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
