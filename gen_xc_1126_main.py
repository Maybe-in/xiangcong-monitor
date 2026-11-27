# -*- coding: utf-8 -*-
"""香葱行情定时任务（376dffed）· 2026-11-26 第 38 次执行 · 数据日 2026-11-25（一手核验发布）

产出：
  1) data/sources/xiangcong_2026-11-26.json   统一 schema 全量报价 + 六档预测（供 03:00 日报汇总）
  2) outputs/香葱行情分析_2026-11-26.html   八章 / 8 图 单页报告（gen_xc_1126_report.py）

本期要点：
  - 数据日 11-25 一手核验：泸西红 3.4-3.7/均价 3.65（平台第十二日）、黑 2.5-2.9/2.76 持平；
    通海红 3.1-3.5/黑 2.5-2.9；全省综合双源一致红 3.4-3.7/黑 2.5-2.9。官方总评「小香葱平淡平稳」。
  - ★头号变化：昆明王旗营小葱 2.00 → 3.50 强势反弹 +75.0%（省级表 mid=2247490736，前一日量 25→50 吨翻倍），
    两个转载号同文、非独立双源，仍需复核；产地横盘而销地大幅上移，价差由 1.65 扩至 0.15（销地反超产地）。
  - 华磷：黑葱 2.8-3.1（昨 3.1）、白铁杆 2.7-3.0（昨 3.0）、红香葱 3.4-3.7（昨 3.7）；
    黑葱包地价 3400-3700 元/亩（昨中值 3700）小幅回落，领先信号与现货背离延续。
  - 全国小葱 roundup 本期未发布（仅命中大葱全表与单市场表）→ 按 data-analysis 缺失只标注不插补：
    不沿用上期家数/均值，改用实际命中销地单点 + 兄弟任务当日批次，不发布全国加权均价。
  - 宏观：11-25 28 种蔬菜均价 4.20（+0.5%），200 指数 113.01 / 菜篮子 112.84（农业农村部官网）。
  - price_history 幂等 upsert 11-24/11-25 一手 observed 点，模型基准锚定 3.65；
    用 src.price.build_forecast + 11-26 鲜抓天气出六档。
  - 合并兄弟任务当日文件（若已落盘，按 (date,market,item,round(mid,2)) 去重）。
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
TODAY = "2026-11-26"
DATA_DATE = "2026-11-25"
GEN = _now.strftime("%Y-%m-%d %H:%M")
TASK_ID = "376dffed-c5e4-4904-a77a-29193947212a"

# ============================================================ 1. 基准报价
base = json.load(open(os.path.join(SRC, "xiangcong_2026-11-25.json"), encoding="utf-8"))
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
upsert_obs("2026-11-24", "红香葱", 3.65, note="11-25 复核：11-24 红香葱 3.65 持平确认（平台第十一日）")
upsert_obs("2026-11-24", "黑葱", 2.76, note="11-24 黑香葱 2.76 持平")
upsert_obs(DATA_DATE, "红香葱", 3.65, note="11-25 一手核验发布 3.4-3.7/均价3.65，较11-24持平（3.65平台第十二日）")
upsert_obs(DATA_DATE, "黑葱", 2.76, note="11-25 一手核验发布 2.5-2.9/均价2.76，持平")
upsert_obs(DATA_DATE, "小葱", 3.50, market="昆明王旗营",
           note="11-25 王旗营小葱 2.00→3.50 强势反弹 +75.0%（省级表 mid=2247490736，两个转载号同文、非独立双源），前一日交易量 25→50 吨翻倍；单点待复核，未参与产地中枢")
json.dump(hist, open(hist_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("[OK] price_history upsert 11-24/11-25 observed 点")

# ============================================================ 3. 六档预测（真实模型 + 11-26 鲜抓天气）
wx_path = os.path.join(DATA, "weather_2026-11-26.json")
if not os.path.exists(wx_path):
    wx_path = os.path.join(DATA, "weather_2026-11-25.json")
    print("[WARN] weather_2026-11-26.json 未落盘，回退 weather_2026-11-25.json")
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

# ============================================================ 4. 一手核验报价（数据日 11-24）
fresh = [
 {"date":DATA_DATE,"item":"香葱","variety":"红香葱","market":"云南红河州泸西县","province":"云南",
  "price_type":"产地收购价","unit":"元/公斤","low":3.4,"high":3.7,"mid":3.65,
  "source":"2026年11月25日呈贡/晋宁/嵩明/陆良/通海/元谋/泸西菜价（公众号 mid=2247595975）",
  "source_url":"http://mp.weixin.qq.com/s?__biz=MzU5MTc0MTM0MA==&mid=2247595975&idx=1&sn=b97c49f00fe88d0aa11a065b682b0304",
  "note":"★数据日一手核验：红香葱 3.4-3.7/均价标签3.65，与11-24完全持平（3.65平台连续第十二日）；当日总评「上青持续下滑、团生菜上涨、其他叶菜平稳、菠菜涨1元、花菜平稳、夹豆微掉、小香葱平淡平稳」"},
 {"date":DATA_DATE,"item":"香葱","variety":"黑香葱","market":"云南红河州泸西县","province":"云南",
  "price_type":"产地收购价","unit":"元/公斤","low":2.5,"high":2.9,"mid":2.76,
  "source":"2026年11月25日泸西菜价（公众号 mid=2247595975）","source_url":"http://mp.weixin.qq.com/s?__biz=MzU5MTc0MTM0MA==&mid=2247595975&idx=1&sn=b97c49f00fe88d0aa11a065b682b0304",
  "note":"★数据日一手核验：黑香葱 2.5-2.9/均价2.76，与11-24完全持平"},
 {"date":DATA_DATE,"item":"香葱","variety":"红葱","market":"云南玉溪通海县","province":"云南",
  "price_type":"产地收购价","unit":"元/公斤","low":3.1,"high":3.5,"mid":3.30,
  "source":"2026年11月25日通海菜价（公众号 mid=2247595975，序号15）","source_url":"http://mp.weixin.qq.com/s?__biz=MzU5MTc0MTM0MA==&mid=2247595975&idx=1&sn=b97c49f00fe88d0aa11a065b682b0304",
  "note":"通海红葱 3.1-3.5，与11-24持平；中值3.30作区间代表"},
 {"date":DATA_DATE,"item":"香葱","variety":"黑葱","market":"云南玉溪通海县","province":"云南",
  "price_type":"产地收购价","unit":"元/公斤","low":2.5,"high":2.9,"mid":2.70,
  "source":"2026年11月25日通海菜价（公众号 mid=2247595975，序号16）","source_url":"http://mp.weixin.qq.com/s?__biz=MzU5MTc0MTM0MA==&mid=2247595975&idx=1&sn=b97c49f00fe88d0aa11a065b682b0304",
  "note":"通海黑葱 2.5-2.9，与11-24持平；中值2.70作区间代表"},
 {"date":DATA_DATE,"item":"香葱","variety":"红香葱","market":"云南产地综合交易价","province":"云南",
  "price_type":"产地批发价","unit":"元/公斤","low":3.4,"high":3.7,"mid":3.55,
  "source":"11月25日云南产地蔬菜综合交易价格（地慧数农 mid=2247490736 / 云南菜价公众号 mid=2653645927 双源同文，序号42）",
  "source_url":"http://mp.weixin.qq.com/s?__biz=Mzg3Mzg1MTgwNw==&mid=2247490736&idx=1&sn=42a7301c7b9615284510b309be77d8f8",
  "note":"全省综合红香葱 3.4-3.7，中值3.55（官方未给均价标签，取区间中值估算）；与泸西3.65对齐"},
 {"date":DATA_DATE,"item":"香葱","variety":"黑葱","market":"云南产地综合交易价","province":"云南",
  "price_type":"产地批发价","unit":"元/公斤","low":2.5,"high":2.9,"mid":2.70,
  "source":"11月25日云南产地蔬菜综合交易价格（地慧数农/云南菜价公众号双源同文，序号43）",
  "source_url":"http://mp.weixin.qq.com/s?__biz=Mzg3Mzg1MTgwNw==&mid=2247490736&idx=1&sn=42a7301c7b9615284510b309be77d8f8",
  "note":"全省综合黑葱 2.5-2.9，中值2.70（区间中值估算）"},
 {"date":DATA_DATE,"item":"香葱","variety":"黑葱","market":"云南产区（华磷肥料行情专报）","province":"云南",
  "price_type":"产地收购价","unit":"元/公斤","low":2.8,"high":3.1,"mid":2.95,
  "source":"华磷肥料·菜价行情专报 2026-11-25（昨日3.1，序号47）",
  "source_url":"http://mp.weixin.qq.com/s?__biz=MzcwNTMxOTA1Mg==&mid=2247486481&idx=1&sn=3ac054b0092ff41639ab843e7fb313f3",
  "note":"独立采价表：黑葱今日2.8-3.1（昨日3.1，↓0.1），较地慧数农2.5-2.9略高（精品口径）；黑葱包地价今日3400-3700元/亩（昨中值3700、OCR读数有歧义）小幅回落，元/亩非本schema口径不入quotes，仅作领先信号登记——与产地现货横盘背离延续"},
 {"date":DATA_DATE,"item":"香葱","variety":"白铁杆","market":"云南产区（华磷肥料行情专报）","province":"云南",
  "price_type":"产地收购价","unit":"元/公斤","low":2.7,"high":3.0,"mid":2.85,
  "source":"华磷肥料·菜价行情专报 2026-11-25（昨日3.0，序号49）",
  "source_url":"http://mp.weixin.qq.com/s?__biz=MzcwNTMxOTA1Mg==&mid=2247486481&idx=1&sn=3ac054b0092ff41639ab843e7fb313f3",
  "note":"白铁杆今日2.7-3.0（昨日3.0），小幅走弱；白葱铁杆为香葱近亲品类"},
 {"date":DATA_DATE,"item":"香葱","variety":"红香葱","market":"云南产区（华磷肥料行情专报）","province":"云南",
  "price_type":"产地收购价","unit":"元/公斤","low":3.4,"high":3.7,"mid":3.55,
  "source":"华磷肥料·菜价行情专报 2026-11-25（昨日3.7，序号51）",
  "source_url":"http://mp.weixin.qq.com/s?__biz=MzcwNTMxOTA1Mg==&mid=2247486481&idx=1&sn=3ac054b0092ff41639ab843e7fb313f3",
  "note":"华磷表红香葱今日3.4-3.7（昨日3.7），区间上沿3.7与泸西一致；独立采价源对照"},
 {"date":DATA_DATE,"item":"香葱","variety":"小葱","market":"昆明王旗营蔬菜批发市场","province":"云南",
  "price_type":"销地批发价","unit":"元/公斤","low":3.5,"high":3.5,"mid":3.5,
  "source":"11月25日云南菜价·昆明王旗营蔬菜批发市场价格表（地慧数农省级表 mid=2247490736，小葱3.5元/公斤、前一日量50吨）",
  "source_url":"http://mp.weixin.qq.com/s?__biz=Mzg3Mzg1MTgwNw==&mid=2247490736&idx=1&sn=42a7301c7b9615284510b309be77d8f8",
  "note":"★本期头号变化：王旗营小葱 2.00→3.50 强势反弹 +75.0%（结束11-20的3.00破位与11-23的1.80二次破位及11-24的2.00企稳）；前一日交易量 25→50 吨翻倍，量价齐升；两个公众号转载号同文、非独立双源，仍需下一交易日复核；全国小葱roundup本期未发布，单点报价 low=high=mid"},
 {"date":DATA_DATE,"item":"香葱","variety":"香葱（宏观大盘参考）","market":"全国28种蔬菜均价","province":"全国",
  "price_type":"销地批发价","unit":"元/公斤","low":4.20,"high":4.20,"mid":4.20,
  "source":"农业农村部市场与信息化司 2026-11-25（28种蔬菜全国批发均价4.20、+0.5%；200指数113.01/菜篮子112.84）",
  "source_url":"https://www.agri.cn/zx/zxfb/202611/t20261125_8886358.htm",
  "note":"★宏观大盘参考：11-25 的 28 种蔬菜均价 4.20 元/公斤（日环比 +0.5%，较 11-24 的 4.18 微升）；非香葱单品，不并入香葱横截面均值"},
]
n_fresh = sum(addq(q) for q in fresh)
print("[OK] 数据日一手核验 +%d 条" % n_fresh)

# ============================================================ 5. 隔年精确同日档案 2025-11-24
archive = [
 {"date":"2025-11-25","item":"香葱","variety":"红香葱","market":"云南红河州泸西县","province":"云南",
  "price_type":"产地收购价","unit":"元/公斤","low":5.4,"high":5.9,"mid":5.75,
  "source":"2025年11月25日呈贡/通海/泸西菜价（公众号 mid=2247592861，泸西序号1 均价标签5.75）","source_url":"http://mp.weixin.qq.com/s?__biz=MzU5MTc0MTM0MA==&mid=2247592861&idx=1&sn=91071900833e27205e2994963f460d31",
  "note":"隔年精确同日档案：泸西红香葱 5.4-5.9/均价5.75；本期3.65同比 -36.5%"},
 {"date":"2025-11-25","item":"香葱","variety":"黑香葱","market":"云南红河州泸西县","province":"云南",
  "price_type":"产地收购价","unit":"元/公斤","low":3.4,"high":3.7,"mid":3.66,
  "source":"2025年11月25日泸西菜价（公众号 mid=2247592861，序号2 均价标签3.66）","source_url":"http://mp.weixin.qq.com/s?__biz=MzU5MTc0MTM0MA==&mid=2247592861&idx=1&sn=91071900833e27205e2994963f460d31",
  "note":"隔年精确同日档案：泸西黑香葱 3.4-3.7/均价3.66；本期2.76同比 -24.6%"},
 {"date":"2025-11-25","item":"香葱","variety":"红葱","market":"云南玉溪通海县","province":"云南",
  "price_type":"产地收购价","unit":"元/公斤","low":5.4,"high":5.9,"mid":5.65,
  "source":"2025年11月25日通海菜价（公众号 mid=2247592861，序号15）","source_url":"http://mp.weixin.qq.com/s?__biz=MzU5MTc0MTM0MA==&mid=2247592861&idx=1&sn=91071900833e27205e2994963f460d31",
  "note":"隔年精确同日档案：通海红葱 5.4-5.9，中值5.65"},
 {"date":"2025-11-25","item":"香葱","variety":"黑葱","market":"云南玉溪通海县","province":"云南",
  "price_type":"产地收购价","unit":"元/公斤","low":3.4,"high":3.7,"mid":3.55,
  "source":"2025年11月25日通海菜价（公众号 mid=2247592861，序号16）","source_url":"http://mp.weixin.qq.com/s?__biz=MzU5MTc0MTM0MA==&mid=2247592861&idx=1&sn=91071900833e27205e2994963f460d31",
  "note":"隔年精确同日档案：通海黑葱 3.4-3.7，中值3.55"},
 {"date":"2025-11-25","item":"香葱","variety":"小葱","market":"昆明王旗营蔬菜批发市场","province":"云南",
  "price_type":"销地批发价","unit":"元/公斤","low":4.5,"high":4.5,"mid":4.5,
  "source":"昆明市景臻-王旗营蔬菜批发市场2025年11月25日平均价格统计（昆明农业农村局官方表 nyncj.km.gov.cn/c/2025-11-25/5036963 + 证券之星 IG2025112500016410 双源）","source_url":"https://nyncj.km.gov.cn/c/2025-11-25/5036963.shtml",
  "note":"隔年精确同日档案：王旗营小葱 4.50、前一日交易量35吨、综合平均价5.75、总吨位2822；本期3.50同比 -22.2%"},
]
n_arch = sum(addq(q) for q in archive)
print("[OK] 隔年同日档案 +%d 条" % n_arch)

# ============================================================ 6. 全国小葱销地单点（11-25 roundup 未发布，只用实际命中）
# data-analysis 红线：缺失只标注不插补 → 不沿用上期家数/均值，不发布全国加权均价
sp = [
 ("新疆兵团第五师三和农副产品综合批发市场","新疆",8.00,"证券之星 IG2026112500020642（小葱8.00）"),
]
n_sp = 0
for mk, pv, p, srcn in sp:
    n_sp += addq({"date":DATA_DATE,"item":"香葱","variety":"小葱","market":mk,"province":pv,
                  "price_type":"销地批发价","unit":"元/公斤","low":p,"high":p,"mid":p,
                  "source":"2026年11月24日单市场行情（农业农村部信息中心·证券之星，%s）" % srcn,
                  "source_url":"https://futures.stockstar.com/IG2026112500020642.shtml",
                  "note":"★全国小葱roundup本期未发布（仅命中葱头全表与各单市场表），按缺失只标注不插补：本条为实际命中销地单点，非全国样本，不发布全国加权均价"})
print("[OK] 全国销地单点 +%d 条（roundup 未发布，不虚构家数）" % n_sp)

# ============================================================ 7. B2B 挂牌（元/斤×2，非成交）
b2b = [
 {"date":DATA_DATE,"item":"香葱","variety":"水洗葱","market":"泸西县（惠农网挂牌）","province":"云南",
  "price_type":"产地地头价","unit":"元/公斤","low":3.4,"high":3.4,"mid":3.4,
  "source":"惠农网 供应页（泸西 1.70 元/斤 水洗葱/香葱地头价）","source_url":"https://www.cnhnb.com/p/xiaocong-0-25-0-0-4/",
  "note":"★B2B挂牌非成交价：1.70 元/斤×2=3.40 元/公斤；平台挂牌长期不刷新（11-25 采集快照），与菜价表3.65分层对照，不并入成交横截面"},
 {"date":DATA_DATE,"item":"香葱","variety":"云南香葱","market":"泸西县（惠农网挂牌）","province":"云南",
  "price_type":"产地地头价","unit":"元/公斤","low":4.0,"high":4.0,"mid":4.0,
  "source":"惠农网 供应页（泸西 2.00 元/斤 云南香葱）","source_url":"https://www.cnhnb.com/p/xiaocong-0-25-0-0-7/",
  "note":"★B2B挂牌非成交价：2.00 元/斤×2=4.00 元/公斤（11-25 采集快照）"},
 {"date":DATA_DATE,"item":"香葱","variety":"小香葱","market":"泸西县（惠农网挂牌）","province":"云南",
  "price_type":"产地地头价","unit":"元/公斤","low":3.2,"high":3.2,"mid":3.2,
  "source":"惠农网 供应页（田壮禾 泸西 1.60 元/斤 产地直发小香葱含黑/白/红葱）","source_url":"https://www.cnhnb.com/p/xiaocong-0-25-0-0-7/",
  "note":"★B2B挂牌非成交价：1.60 元/斤×2=3.20 元/公斤（11-25 采集快照）"},
 {"date":DATA_DATE,"item":"香葱","variety":"精品红葱","market":"泸西县（一亩田挂牌）","province":"云南",
  "price_type":"产地地头价","unit":"元/公斤","low":2.0,"high":2.0,"mid":2.0,
  "source":"一亩田 泸西产地货源（精品红葱 1.00 元/斤）","source_url":"https://m.ymt.com/shop/2925430",
  "note":"★B2B挂牌非成交价：1.00 元/斤×2=2.00 元/公斤；挂牌口径长期不刷新（11-25 采集快照），非11-25当日成交"},
 {"date":DATA_DATE,"item":"香葱","variety":"精品黑白葱","market":"泸西县（一亩田挂牌）","province":"云南",
  "price_type":"产地地头价","unit":"元/公斤","low":1.6,"high":1.6,"mid":1.6,
  "source":"一亩田 泸西产地货源（精品黑白葱 0.80 元/斤）","source_url":"https://m.ymt.com/shop/2925430",
  "note":"★B2B挂牌非成交价：0.80 元/斤×2=1.60 元/公斤（11-25 采集快照）"},
 {"date":DATA_DATE,"item":"香葱","variety":"小红葱","market":"泸西县（一亩田挂牌）","province":"云南",
  "price_type":"产地地头价","unit":"元/公斤","low":2.4,"high":2.4,"mid":2.4,
  "source":"一亩田 供应页（小红葱 1.20 元/斤 云南红河泸西县，40-45规格）","source_url":"https://www.ymt.com/supply/59212963",
  "note":"★B2B挂牌非成交价：1.20 元/斤×2=2.40 元/公斤（11-25 采集快照）"},
 {"date":DATA_DATE,"item":"香葱","variety":"精品小香葱","market":"泸西县（惠农网挂牌）","province":"云南",
  "price_type":"产地地头价","unit":"元/公斤","low":4.8,"high":5.6,"mid":5.2,
  "source":"惠农网 供应页（泸西 2.40-2.80 元/斤 精品小香葱）","source_url":"https://www.cnhnb.com/p/xiaocong-0-25-0-0-7/",
  "note":"★B2B精品挂牌非成交价：2.40-2.80 元/斤×2=4.80-5.60 元/公斤；规格溢价，非统货成交价（11-25 采集快照）"},
]
n_b2b = sum(addq(q) for q in b2b)
print("[OK] B2B挂牌 +%d 条" % n_b2b)

# ============================================================ 8. 合并兄弟任务文件（本期含数据日 11-25 的迟到落盘文件）
n_sib = 0
_sib_files = []
for _d in (TODAY, DATA_DATE):
    for fn in sorted(glob.glob(os.path.join(SRC, "*_%s.json" % _d))):
        if fn not in _sib_files:
            _sib_files.append(fn)
for fn in _sib_files:
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
# 兄弟任务迟到文件的分层口径二次归一（统一到 schema 五档，保留原口径于 note）
_ALLOW_PT = {"产地地头价","产地收购价","产地批发价","销地批发价","零售价"}
def _norm_pt(pt):
    t = str(pt)
    if "B2B" in t or "挂牌" in t: return "产地地头价"
    if "宏观" in t or "大盘" in t or "非香葱" in t or "周均" in t or "批发均价" in t or t == "销地综合批发价(非香葱)": return "销地批发价"
    if t.startswith("产地收购价"): return "产地收购价"
    if t.startswith("销地批发价"): return "销地批发价"
    if t.startswith("产地"): return "产地批发价"
    if "批发" in t: return "销地批发价"
    return None
for q in quotes:
    pt = q.get("price_type")
    if pt in _ALLOW_PT: continue
    np = _norm_pt(pt)
    if np:
        q["price_type"] = np
        q["note"] = (q.get("note", "") + "；[口径归一] 原「%s」→「%s」，原口径保留于本注，宏观/非香葱单品不并入香葱横截面" % (pt, np))
        n_norm += 1
print("[OK] 口径归一化 %d 条" % n_norm)

# ============================================================ 10. 落盘
market_scope = ("全国 / 云南 / 红河州泸西县（产地、销地、省级综合、宏观、历史锚点、B2B 挂牌全口径；"
               "数据日 2026-11-25 一手核验 3.65/2.76 连续第十二日锁定、王旗营小葱 2.00→3.50 量价齐升；合并兄弟任务当日数据）")
summary = ("数据日2026年11月25日，泸西红香葱均价3.65元/公斤、黑香葱2.76与11-24完全持平（3.65平台连续第十二日），全省综合双源同文红3.4-3.7、黑2.5-2.9与泸西对齐，官方总评「小香葱平淡平稳」。头号变化在需求侧：昆明王旗营小葱由2.00大幅反弹至3.50（+75.0%，省级表；两个转载号同文非独立双源、待复核），前一日交易量25→50吨翻倍，销地价已反超产地0.15元/公斤，产地横盘与销地急升形成明显背离。宏观28种蔬菜均价4.20较11-24微升0.5%（200指数113.01/菜篮子112.84）；天气16天累计降水仅0.1mm、无霜冻无强降水，冷空气影响偏北方（大风59条、云南0条）；六档中枢锚定3.65并用11-26鲜抓天气重算，综合风险维持高，同比2025-11-25泸西5.75下跌36.5%、为近五年同期绝对最低。")
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
