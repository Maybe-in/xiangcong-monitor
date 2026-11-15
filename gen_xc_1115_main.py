# -*- coding: utf-8 -*-
"""香葱行情定时任务（376dffed）· 2026-11-15 第 27 次执行 · 数据日 2026-11-14（T 日一手实测沿用）

产出：
  1) data/sources/xiangcong_2026-11-15.json   统一 schema 全量报价 + 六档预测（供 03:00 日报汇总）
  2) data/weather_2026-11-15.json / data/disaster_2026-11-15.json   当日天气/灾害快照（11-14 窗口按 11-15 起算切片）
  3) outputs/香葱行情分析_2026-11-15.html    八章 / 多图 单页报告

方法（与历史各期一致）：
  - 以 xiangcong_2026-11-14.json 为权威基准（含全量历史报价 + 六档预测）。
  - 合并兄弟任务当日文件 grok_/chatgpt_/gemini_2026-11-15.json（按 (date,market,item,round(mid,2)) 去重）。
  - 预测六档 target_date 顺延 1 天，中枢/区间/涨跌/置信度沿用（无新确认价信号，沿用 3.65 基准）。
  - 追加 11-15 联网新采 B2B 挂牌报价（元/斤换算，显式标注非成交）。
  - 缺失值只标注不插补；冲突口径只并列不平均。
"""
from __future__ import annotations
import json, os, re, glob
from datetime import datetime, timedelta, timezone

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(BASE_DIR, "data", "sources")
DATA = os.path.join(BASE_DIR, "data")
OUT = os.path.join(BASE_DIR, "outputs")
os.makedirs(SRC, exist_ok=True)
os.makedirs(OUT, exist_ok=True)

BJ = timezone(timedelta(hours=8))
_now = datetime.now(BJ)
TODAY = "2026-11-15"
GEN = _now.strftime("%Y-%m-%d %H:%M")
TASK_ID = "376dffed-c5e4-4904-a77a-29193947212a"
CUR_MID = 3.65   # 泸西 红香葱 11-14 一手核验均价（最新确认成交价）

# ============================================================ 1. 载入基准
base = json.load(open(os.path.join(SRC, "xiangcong_2026-11-14.json"), encoding="utf-8"))
quotes = list(base.get("quotes", []))
forecasts = list(base.get("forecasts", []))

def _mid(q):
    m = q.get("mid")
    try:
        return round(float(m), 2) if m is not None else None
    except Exception:
        return None

def key(q):
    m = _mid(q)
    return (str(q.get("date")), str(q.get("market")), str(q.get("item")), m if m is not None else -1)

seen = set(key(q) for q in quotes)
n_before = len(quotes)

# ============================================================ 2. 合并兄弟任务当日文件
siblings = ["grok_2026-11-15.json", "chatgpt_2026-11-15.json", "gemini_2026-11-15.json"]
n_sib = 0
for fn in siblings:
    p = os.path.join(SRC, fn)
    if not os.path.exists(p):
        continue
    d = json.load(open(p, encoding="utf-8"))
    for q in d.get("quotes", []):
        m = _mid(q)
        # 跳过纯占位/非价格行（mid 与 low 均为 0/空）——宏观指数占位行与口径说明行
        if (m is None or m == 0) and (q.get("low") in (0, None, "") ):
            continue
        k = key(q)
        if k in seen:
            continue
        seen.add(k)
        quotes.append(q)
        n_sib += 1
print("[OK] 兄弟任务合并 +%d 条（grok/chatgpt/gemini）" % n_sib)

# ============================================================ 3. 追加 11-15 联网新采 B2B 挂牌（非成交，显式标注）
# 来源：WebSearch 惠农网/一亩田 泸西小香葱供应页（挂牌价，非成交价，口径分层对照）
b2b = [
    {"date": TODAY, "item": "香葱", "variety": "黑葱", "market": "泸西县（惠农网挂牌）", "province": "云南",
     "price_type": "产地地头价", "unit": "元/公斤", "low": 1.6, "high": 1.6, "mid": 1.6,
     "source": "惠农网 供应页（黑葱 0.80 元/斤）", "source_url": "https://www.cnhnb.com/p/xiaocong-0-25-0-0-12/",
     "note": "★11-15 联网新采·B2B 挂牌非成交价：黑葱 0.80 元/斤 ×2 = 1.60 元/公斤；平台挂牌口径，与同日泸西菜价表 2.76 分属不同采价层，仅作口径分层对照，不并入成交横截面"},
    {"date": TODAY, "item": "香葱", "variety": "红香葱", "market": "泸西县（一亩田挂牌）", "province": "云南",
     "price_type": "产地地头价", "unit": "元/公斤", "low": 1.0, "high": 2.0, "mid": 1.5,
     "source": "一亩田 供应页（红葱/小香葱 0.50-1.00 元/斤）", "source_url": "https://www.ymt.com/supplylist/li-1-0-7886",
     "note": "★11-15 联网新采·B2B 挂牌非成交价：红葱/小香葱 0.50-1.00 元/斤 ×2 = 1.00-2.00 元/公斤；挂牌口径，大量上市「大掉价」描述印证供给宽松，非成交价"},
    {"date": TODAY, "item": "香葱", "variety": "黑葱", "market": "泸西县（一亩田挂牌）", "province": "云南",
     "price_type": "产地地头价", "unit": "元/公斤", "low": 1.4, "high": 1.8, "mid": 1.6,
     "source": "一亩田 供应页（黑葱 0.70-0.90 元/斤，标注产地大掉价）", "source_url": "https://www.ymt.com/supplylist/dadou-0-7300/pn3",
     "note": "★11-15 联网新采·B2B 挂牌非成交价：黑葱 0.70-0.90 元/斤 ×2 = 1.40-1.80 元/公斤；挂牌口径非成交，与菜价表 2.76 分层对照"},
    {"date": TODAY, "item": "香葱", "variety": "精品小香葱", "market": "泸西县（惠农网精品挂牌）", "province": "云南",
     "price_type": "产地地头价", "unit": "元/公斤", "low": 4.8, "high": 5.6, "mid": 5.2,
     "source": "惠农网 供应页（精品小香葱 2.40-2.80 元/斤）", "source_url": "https://www.cnhnb.com/p/xiaocong-0-25-0-0-12/",
     "note": "★11-15 联网新采·B2B 精品挂牌非成交价：2.40-2.80 元/斤 ×2 = 4.80-5.60 元/公斤；精品规格挂牌，高于统货成交价，印证规格价差"},
]
n_b2b = 0
for q in b2b:
    k = key(q)
    if k in seen:
        continue
    seen.add(k); quotes.append(q); n_b2b += 1
print("[OK] 11-15 联网新采 B2B 挂牌 +%d 条" % n_b2b)

# ============================================================ 4. 预测六档顺延 1 天（中枢/区间/涨跌/置信度沿用）
def shift1(dstr):
    try:
        d = datetime.strptime(dstr, "%Y-%m-%d").date()
        return (d + timedelta(days=1)).isoformat()
    except Exception:
        return dstr

for f in forecasts:
    f["target_date"] = shift1(f.get("target_date", ""))
    f["note"] = "【11-15 沿用 11-14 基准 3.65，target_date 顺延 1 天】" + f.get("note", "")
print("[OK] 预测六档 target_date 顺延完成，共 %d 档" % len(forecasts))

# ============================================================ 5. 天气/灾害当日快照（11-14 窗口按 11-15 起算切片）
# 5.1 天气：从 weather_2026-11-14.json 切出 date>=2026-11-15
wx_src = os.path.join(DATA, "weather_2026-11-14.json")
if os.path.exists(wx_src):
    wx = json.load(open(wx_src, encoding="utf-8"))
    daily = [d for d in wx.get("core", {}).get("daily", []) if d.get("date") and d["date"] >= TODAY and d.get("tmax") is not None]
    wx_out = dict(wx)
    wx_out["core"] = dict(wx.get("core", {}))
    wx_out["core"]["daily"] = daily
    wx_out["generated_at"] = GEN + "（由 11-14 快照按 11-15 起算切片，中央气象台/Open-Meteo 窗口）"
    json.dump(wx_out, open(os.path.join(DATA, "weather_2026-11-15.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("[OK] weather_2026-11-15.json 切片 %d 天" % len(daily))
# 5.2 灾害：沿用 11-14 中央气象台快照（total=100，大雾主导，红河州/泸西 0 条），更新生成时间
dz_src = os.path.join(DATA, "disaster_2026-11-14.json")
if os.path.exists(dz_src):
    dz = json.load(open(dz_src, encoding="utf-8"))
    dz["generated_at"] = GEN + "（沿用 11-14 18 时中央气象台快照；11-15 未见泸西/红河州新增独立预警）"
    json.dump(dz, open(os.path.join(DATA, "disaster_2026-11-15.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("[OK] disaster_2026-11-15.json 沿用快照 total=%s" % dz.get("total"))

# ============================================================ 6. 组装并落盘 xiangcong_2026-11-15.json
market_scope = ("全国 / 云南 / 红河州泸西县（产地、销地、省级综合、宏观、历史锚点、B2B 挂牌全口径；"
               "数据日 2026-11-14 一手核验 3.65/2.76，11-15 菜价表未发布沿用；合并 grok/chatgpt/gemini 兄弟任务当日数据）")

summary = ("本期数据日 2026-11-14：泸西红香葱 3.4-3.7/均价 3.65（较 11-13 的 3.45 +5.8%，结束连续 13 个报价日锁定），黑香葱 2.5-2.9/均价 2.76 持平，红低于 5.0 成本线 27%、黑低 46%。"
          "11-15 泸西菜价表尚未发布（通常约 10:30），价格沿用 11-14 核验值；天气两股冷空气 11/14-18 南下、云南大部晴、泸西无霜冻，北方退市支撑南菜北运但本地无直接影响；中央气象台 11-14 大雾橙警、红河州与泸西本县 0 条独立预警。"
          "六档预测中枢（红）3.61/3.77/3.81/3.88/4.02/3.72 元/公斤，target_date 顺延 1 天，综合风险维持「高」（价格+需求侧双高主导）。")

out = {
    "task": "香葱行情",
    "task_id": TASK_ID,
    "date": TODAY,
    "generated_at": GEN,
    "market_scope": market_scope,
    "quotes": quotes,
    "forecasts": forecasts,
    "summary": summary,
}
opath = os.path.join(SRC, "xiangcong_2026-11-15.json")
json.dump(out, open(opath, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("[OK] WROTE %s  quotes=%d forecasts=%d" % (opath, len(quotes), len(forecasts)))

# 供报告生成复用
json.dump(out, open(os.path.join(DATA, "_xc1115_main.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
