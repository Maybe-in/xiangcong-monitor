# -*- coding: utf-8 -*-
"""从 gen_xc_1125_main.py 精确派生 gen_xc_1126_main.py（第 38 次执行）。"""
import io, os, re
BASE = os.path.dirname(os.path.abspath(__file__))
src = os.path.join(BASE, "gen_xc_1125_main.py")
s = io.open(src, encoding="utf-8").read()

def rep(old, new, expect=1):
    global s
    n = s.count(old)
    if n != expect:
        raise SystemExit("MATCH FAIL %d != %d : %s" % (n, expect, old[:120]))
    s = s.replace(old, new)
    print("[rep] ok x%d" % n)

# 1) docstring
m = re.search(r'"""香葱行情定时任务.*?"""', s, re.S)
assert m, "docstring not found"
newdoc = '''"""香葱行情定时任务（376dffed）· 2026-11-26 第 38 次执行 · 数据日 2026-11-25（一手核验发布）

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
"""'''
rep(m.group(0), newdoc)

# 2) dates & base
rep('TODAY = "2026-11-25"', 'TODAY = "2026-11-26"')
rep('DATA_DATE = "2026-11-24"', 'DATA_DATE = "2026-11-25"')
rep('"xiangcong_2026-11-24.json"', '"xiangcong_2026-11-25.json"')

# 3) history upserts
old = '''upsert_obs("2026-11-23", "红香葱", 3.65, note="11-24 复核：11-23 红香葱 3.65 持平确认（平台第十日）")
upsert_obs("2026-11-23", "黑葱", 2.76, note="11-23 黑香葱 2.76 持平")
upsert_obs(DATA_DATE, "红香葱", 3.65, note="11-24 一手核验发布 3.4-3.7/均价3.65，较11-23持平（3.65平台第十一日）")
upsert_obs(DATA_DATE, "黑葱", 2.76, note="11-24 一手核验发布 2.5-2.9/均价2.76，持平")
upsert_obs(DATA_DATE, "小葱", 2.00, market="昆明王旗营",
           note="11-24 王旗营小葱 1.80→2.00 触底反弹 +11.1%（省级表 mid=2247490732 单点），前一日交易量 25 吨；全国roundup本期未发布无双源")
json.dump(hist, open(hist_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("[OK] price_history upsert 11-23/11-24 observed 点")'''
new = '''upsert_obs("2026-11-24", "红香葱", 3.65, note="11-25 复核：11-24 红香葱 3.65 持平确认（平台第十一日）")
upsert_obs("2026-11-24", "黑葱", 2.76, note="11-24 黑香葱 2.76 持平")
upsert_obs(DATA_DATE, "红香葱", 3.65, note="11-25 一手核验发布 3.4-3.7/均价3.65，较11-24持平（3.65平台第十二日）")
upsert_obs(DATA_DATE, "黑葱", 2.76, note="11-25 一手核验发布 2.5-2.9/均价2.76，持平")
upsert_obs(DATA_DATE, "小葱", 3.50, market="昆明王旗营",
           note="11-25 王旗营小葱 2.00→3.50 强势反弹 +75.0%（省级表 mid=2247490736，两个转载号同文、非独立双源），前一日交易量 25→50 吨翻倍；单点待复核，未参与产地中枢")
json.dump(hist, open(hist_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("[OK] price_history upsert 11-24/11-25 observed 点")'''
rep(old, new)

# 4) weather path
rep('wx_path = os.path.join(DATA, "weather_2026-11-25.json")', 'wx_path = os.path.join(DATA, "weather_2026-11-26.json")')
rep('if not os.path.exists(wx_path):\n    wx_path = os.path.join(DATA, "weather_2026-11-24.json")\n    print("[WARN] weather_2026-11-25.json 未落盘，回退 weather_2026-11-24.json")',
    'if not os.path.exists(wx_path):\n    wx_path = os.path.join(DATA, "weather_2026-11-25.json")\n    print("[WARN] weather_2026-11-26.json 未落盘，回退 weather_2026-11-25.json")')
rep('# ============================================================ 3. 六档预测（真实模型 + 11-25 鲜抓天气）',
    '# ============================================================ 3. 六档预测（真实模型 + 11-26 鲜抓天气）')

# 5) fresh quotes block
fresh_start = s.index('fresh = [')
fresh_end = s.index(']\nn_fresh = sum(addq(q) for q in fresh)', fresh_start) + 1
newfresh = '''fresh = [
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
]'''
s = s[:fresh_start] + newfresh + s[fresh_end:]

# 6) archive block
a_start = s.index('archive = [')
a_end = s.index(']\nn_arch = sum(addq(q) for q in archive)', a_start) + 1
newarch = '''archive = [
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
]'''
s = s[:a_start] + newarch + s[a_end:]

# 7) single markets
old_sp = '''sp = [
 ("合肥周谷堆农产品批发市场","安徽",4.80,"证券之星 IG2026112400018612（小葱4.80）"),
 ("辽宁朝阳市果菜批发市场","辽宁",1.70,"证券之星 IG2026112400018744（小葱1.70）"),
 ("北京朝阳区大洋路综合市场","北京",8.30,"证券之星 IG2026112400018582（小葱8.30）"),
]'''
new_sp = '''sp = [
 ("新疆兵团第五师三和农副产品综合批发市场","新疆",8.00,"证券之星 IG2026112500020642（小葱8.00）"),
]'''
rep(old_sp, new_sp)
rep('"source_url":"https://futures.stockstar.com/IG2026112400018612.shtml"',
    '"source_url":"https://futures.stockstar.com/IG2026112500020642.shtml"')
rep('# ============================================================ 6. 全国小葱销地单点（11-24 roundup 未发布，只用实际命中）',
    '# ============================================================ 6. 全国小葱销地单点（11-25 roundup 未发布，只用实际命中）')

# 8) B2B snapshot notes
s = s.replace('（11-24 采集快照）', '（11-25 采集快照）')
s = s.replace('非11-24当日成交', '非11-25当日成交')

# 9) scope & summary
old_scope = '''market_scope = ("全国 / 云南 / 红河州泸西县（产地、销地、省级综合、宏观、历史锚点、B2B 挂牌全口径；"
               "数据日 2026-11-24 一手核验 3.65/2.76 连续第十一日锁定、王旗营小葱 1.80→2.00 触底反弹；合并兄弟任务当日数据）")'''
new_scope = '''market_scope = ("全国 / 云南 / 红河州泸西县（产地、销地、省级综合、宏观、历史锚点、B2B 挂牌全口径；"
               "数据日 2026-11-25 一手核验 3.65/2.76 连续第十二日锁定、王旗营小葱 2.00→3.50 量价齐升；合并兄弟任务当日数据）")'''
rep(old_scope, new_scope)
old_sum = [l for l in s.split('\n') if l.startswith('summary = (')][0]
new_sum = ('summary = ("数据日2026年11月25日，泸西红香葱均价3.65元/公斤、黑香葱2.76与11-24完全持平（3.65平台连续第十二日），'
           '全省综合双源同文红3.4-3.7、黑2.5-2.9与泸西对齐，官方总评「小香葱平淡平稳」。头号变化在需求侧：昆明王旗营小葱由2.00大幅反弹至3.50（+75.0%，省级表；两个转载号同文非独立双源、待复核），'
           '前一日交易量25→50吨翻倍，销地价已反超产地0.15元/公斤，产地横盘与销地急升形成明显背离。宏观28种蔬菜均价4.20较11-24微升0.5%（200指数113.01/菜篮子112.84）；'
           '天气16天累计降水仅0.1mm、无霜冻无强降水，冷空气影响偏北方（大风59条、云南0条）；六档中枢锚定3.65并用11-26鲜抓天气重算，综合风险维持高，同比2025-11-25泸西5.75下跌36.5%、为近五年同期绝对最低。")')
rep(old_sum, new_sum)

out = os.path.join(BASE, "gen_xc_1126_main.py")
io.open(out, "w", encoding="utf-8").write(s)
print("[OK] wrote", out, len(s))
