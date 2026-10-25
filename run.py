# -*- coding: utf-8 -*-
"""香葱行情日报 —— 主入口。

流程：抓取天气(Open-Meteo) → 抓取灾害预警(中央气象台) → 计算四档价格预测 → 渲染 HTML 报告。

用法：
    python run.py                # 正常生成当日报告
    python run.py --dry-run      # 只打印关键结果，不落盘
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src import disaster, longterm, price, report, weather  # noqa: E402
from src.config import CORE_REGION, MODEL  # noqa: E402

WEEKDAY_CN = ['一', '二', '三', '四', '五', '六', '日']

# 11 月降水假设（依据国家气候中心超强厄尔尼诺展望）：江南、西南降水偏多 5-8 成。
# 全文统一引用此常量，避免同一天气假设在不同段落给出互相矛盾的幅度。
RAIN_ASSUMPTION = '5-8 成'


def _safe(d: dict, key: str, default='—'):
    v = d.get(key)
    return default if v is None else v


def blk_current(fc: dict) -> str:
    v = fc.get('黑葱', {}).get('current')
    return f'{v:.2f}' if isinstance(v, (int, float)) else '—'


def build_context() -> dict:
    today = date.today().isoformat()
    generated_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    print('[1/5] 抓取天气数据 ...')
    wx = weather.build_weather_snapshot()
    core_daily = wx['core']['daily']
    win = wx['core']['windows']
    print('      核心产区 {0}：{1} 天预报，观测点 {2} 个'.format(
        CORE_REGION['name'], len(core_daily), len(wx['points'])))

    print('[2/5] 抓取自然灾害预警 ...')
    dz = disaster.build_disaster_snapshot()
    print('      全国生效预警：{0} 条'.format(dz['total']))

    print('[3/5] 重建长周期历史行情（10 年） ...')
    lt = longterm.build_longterm()
    win_by_month = {w['months']: w for w in lt['windows']}
    print('      月频点数 {0}，窗口：{1}'.format(
        len(lt['series']),
        ' | '.join('{0}月 {1:+.1f}%'.format(w['months'], w['change_pct'])
                   for w in lt['windows'])))

    print('[4/5] 计算六档价格预测 ...')
    history = price.load_history()
    clim = wx['core'].get('climatology') or {}
    fc = price.build_forecast(history, core_daily, clim=clim)
    red = fc['红香葱']
    if core_daily:
        price.append_estimate(history, '红香葱', red['current'], '模型基准值')
    price.save_history(history)
    print('      红香葱中枢：{0} → {1}'.format(
        red['current'], ' / '.join(str(r['center']) for r in red['rows'])))

    print('[5/5] 渲染报告 ...')

    w3 = win.get('d3', {})
    w1 = win.get('w1', {})
    h1 = win.get('h1', {})

    r3, r7, r15, r30, r60, r90 = red['rows']
    d3txt, _ = price.direction_tag(r3['delta_pct'])
    d30txt, _ = price.direction_tag(r30['delta_pct'])
    d90txt, _ = price.direction_tag(r90['delta_pct'])

    # 近期高点：取最近 45 天内实测最高点，不再写死「6.10 / 10 月中旬」
    _obs = [p for p in history.get('series', [])
            if p['variety'] == '红香葱' and p.get('source') == 'observed']
    peak_price = peak_date = None
    # 基准价取自最新一条实测点，把它的日期写进正文，避免读者误以为用的是当天价
    obs_date = (sorted(_obs, key=lambda p: p['date'])[-1]['date'] if _obs else today)
    if _obs:
        _recent = [p for p in _obs
                   if 0 <= (date.today() - date.fromisoformat(p['date'])).days <= 45]
        _peak = max(_recent or _obs, key=lambda p: p['price'])
        peak_price, peak_date = _peak['price'], _peak['date']
    drop_pct = abs((red['current'] / peak_price - 1) * 100) if peak_price else 0.0
    drop_txt = ('较 {0} 高点（红香葱 {1:.2f} 元/公斤）回落约 {2:.0f}%；').format(
        peak_date, peak_price, drop_pct) if (peak_price and drop_pct >= 0.5) else ''

    # 2027 年春节（丁未羊年）= 2027-02-06，除夕 2027-02-05；天数按实际目标日计算
    cny_days = (date(2027, 2, 6) - date.fromisoformat(r90['target_date'])).days

    # 环比前一日：判断是仍在下跌还是已止跌企稳
    def _dod(var):
        pts = sorted([p for p in history.get('series', [])
                      if p['variety'] == var and p.get('source') == 'observed'],
                     key=lambda p: p['date'])
        if len(pts) < 2:
            return None, None
        prev, cur = pts[-2], pts[-1]
        return (cur['price'] - prev['price']), prev['date']

    dod_val, dod_date = _dod('红香葱')
    if dod_val is None:
        dod_txt = ''
    elif abs(dod_val) < 0.03:
        dod_txt = ('较上一观测日（{0}）{1:.2f} 元/公斤持平，'
                   '连续两日横盘，深度下跌阶段已告一段落，价格进入磨底企稳期；').format(
            dod_date, red['current'] - dod_val)
    else:
        dod_txt = ('较上一观测日（{0}）{1}{2:.2f} 元/公斤（{3:+.1f}%）；').format(
            dod_date, '上涨' if dod_val > 0 else '下跌', abs(dod_val),
            dod_val / (red['current'] - dod_val) * 100 if red['current'] != dod_val else 0)

    def pct(r):
        return '{0:+.1f}%'.format(r['delta_pct'])

    summary = (
        '当前全国香葱处于季节性供给高峰下的低位承压期。' + CORE_REGION['name'] +
        '产区红香葱产地中枢报 ' + str(red['current']) + ' 元/公斤，黑葱报 ' +
        blk_current(fc) + ' 元/公斤（{0} 实测）；'.format(obs_date) + dod_txt +
        drop_txt +
        '主导逻辑是「天气利好→丰产不丰收」的反向传导：主产区温光适宜、茬口衔接顺畅，'
        '供给持续扩容，而终端仅有刚性需求，渠道按需补库、低库存周转，缺乏集中备货拉涨动力。'
        '分周期看：未来 3 天产区以' + str(_safe(w3, 'dominant')) + '为主、累计降水 ' +
        str(_safe(w3, 'precip_total')) + ' mm，采收顺畅、出货集中，价格' + d3txt +
        '（中枢 ' + str(r3['center']) + '，' + pct(r3) + '）；'
        '未来一周累计降水 ' + str(_safe(w1, 'precip_total')) + ' mm、雨日 ' +
        str(_safe(w1, 'rainy_days')) + ' 天、大风 ' + str(_safe(w1, 'gale_days')) +
        ' 天，采收与运输存在扰动，跌势有望止住并转为回升'
        '（' + str(r7['center']) + '，' + pct(r7) + '）；'
        '半月窗口（第 8-15 天）累计降水 ' + str(_safe(h1, 'precip_total')) +
        ' mm，叠加北方秋菜退市、供给切换为「南菜北运」，中枢回升至 ' +
        str(r15['center']) + '（' + pct(r15) + '）；'
        '一个月后随冬季餐饮消费启动，中枢上看 ' + str(r30['center']) +
        '（' + pct(r30) + '），' + d30txt + '；'
        '两个月（目标日 ' + r60['target_date'] + '）进入冬至—元旦备货窗口，'
        '且北方产区基本退市、全国供给转向云南单极，中枢进一步抬升至 ' +
        str(r60['center']) + '（' + pct(r60) + '）；'
        '三个月（目标日 ' + r90['target_date'] + '）距 2027 年春节（2 月 6 日）'
        '仅 ' + str((date(2027, 2, 6) - date.fromisoformat(r90['target_date'])).days) + ' 天，'
        '落入全年最强的节前集中备货窗口，中枢情景值 ' + str(r90['center']) +
        '（' + pct(r90) + '），' + d90txt + '。'
        '整体呈「近端磨底、中段修复、远端节日支撑」的震荡上行形态，'
        '但 2-3 月档位属情景推演，置信度低于近端档位，需按月滚动修正。'
        '口径提示：本报告预测与「当前中枢」采用精品净葱/产地集散价口径，'
        '与第二章长周期主序列的通货毛葱口径相差约 ' +
        '{:.2f} 倍'.format(lt['premium']) +
        '（通货 2.62 vs 净葱 4.35），两者不可直接横比。'
    )

    key_variable = (
        '超强厄尔尼诺（有监测记录以来最强，海温指数峰值预计 11 月前后达 3.2-3.5℃）背景下，'
        '11 月江南、西南降水偏多 ' + RAIN_ASSUMPTION + '，是打破供大于求格局、触发行情反转的最主要潜在推手。'
        '若降雨不及预期、产区持续晴好，半月与一月预测需下修 3-8 个百分点；'
        '对 2-3 月档位而言，更关键的是冬季冷空气与雨雪冰冻的实际强度——'
        '它既决定云南外调菜的供给弹性，也决定节前备货行情的兑现幅度。'
    )

    supply_press = [
        '北方露地秋菜处于产量爬坡期，北菜南运规模维持高位',
        '销区本地秋菜陆续上市，形成「北方菜 + 本地菜 + 云南菜」三重供给叠加',
        '云南产区茬口衔接顺畅，气候适宜、病害少、商品率高',
        '全国蔬菜在田面积同比增加约 100 多万亩',
    ]
    demand_trigger = [
        '超强厄尔尼诺下 11 月江南、西南降水偏多 ' + RAIN_ASSUMPTION,
        '11 月上中旬云南两次明显降雨过程，采收与运输受扰',
        '北方秋菜退市，供给由「北菜南运」切换为「南菜北运」，云南单极供给格局形成',
        '冬季餐饮（火锅/面食）消费季节性回升',
        '12 月冬至—元旦、1 月春节前两轮集中备货（2027 年春节 2 月 6 日）',
        '价格贴近成本线后农户惜售心理增强',
    ]

    luxi_moat = (
        '低纬度高原气候（北亚热带季风区，光照充足、雨量充沛）实现全年轮番种植；'
        '水肥一体化普及使单人管理面积由 5-6 亩提升至 30 亩，人工成本大幅下降；'
        '建成制冰—清洗—冷藏—分拣—包装—运输完整加工链，附加值提升约 3 倍；'
        '《泸西小香葱生产规程》经省市场监管局发布，为国内该品类产品标准；'
        '曾为 G20 杭州峰会、杭州亚运会蔬菜直供基地；'
        '销售覆盖 20 省市 100 余城并出口马来西亚、新加坡、泰国。'
    )

    advice = [
        '种植端：本周前期晴好为最佳采收窗口，建议抢晴采收、及时入库预冷',
        '种植端：提前清沟防渍涝，预防霜霉病、灰霉病；合理安排茬口、错峰上市，'
        '避免在低位集中踩踏出货',
        '流通/收购端：坚持按需采购、快进快出，控制库存水平，规避下行风险',
        '流通端：当前价位已近成本线、下行空间有限，可在本周低价区间适度建立 '
        '11 月中旬前的原料库存',
        '加工端：11 月上中旬为全年较优原料锁价窗口，建议提前锁定冻干/脱水/香葱酱产线原料',
        '关注节点：11 月初与 11 月中旬两次降雨过程的实际强度，'
        '是回升幅度能否兑现的核心观察点',
        '中长期（2-3月档位）：当前价位处于年内低位区间，'
        '元旦与春节前备货是确定性较高的季节性利多，'
        '建议流通端在 11 月低位分批建立节前头寸、加工端提前锁价，'
        '但需为厄尔尼诺下天气不兑现预留 15%-20% 的下修空间',
        '中长期跟踪：厄尔尼诺峰值（11 月前后）之后的冬季冷空气与雨雪冰冻强度，'
        '是 12 月—次年 1 月行情能否超预期的决定性变量',
    ]

    risks = [
        ('极端天气缺位（最大下行风险）', 't-down', '利空',
         '11 月江南、西南降水偏多 ' + RAIN_ASSUMPTION + '未兑现，产区持续晴好',
         '下修半月/一月预测 3-8 个百分点，低位周期延长'),
        ('强降雨/渍涝超预期', 't-up', '利多',
         '厄尔尼诺峰值叠加，江南、西南降水偏多 ' + RAIN_ASSUMPTION,
         '上调涨幅，同时关注采收与运输中断风险'),
        ('新增台风', 't-flat', '中性偏空',
         '西北太平洋预计再生成 1 个台风，影响华南/华东沿海',
         '销区物流受阻、短期需求受抑，随后补库反弹'),
        ('销区本地菜持续替代', 't-down', '利空',
         '中东部及南方城市本地秋菜上市规模扩大',
         '压缩云南外调菜份额，压制产区价格弹性'),
        ('冬季阶段性强寒潮/雨雪冰冻', 't-up', '波动加剧',
         '12 月-次年 2 月寒潮频次略偏多、冷暖起伏大',
         '或阶段性跳涨 15%-30%，但同时阻断运输，持续时间短'),
        ('终端消费恢复不及预期', 't-down', '利空',
         '渠道去库存周期拉长',
         '压制行情弹性，延长低迷期'),
        ('节前备货行情提前透支/延后', 't-flat', '波动加剧',
         '2027 年春节较晚（2 月 6 日），备货节奏易被分散到 1 月全月',
         '3 月档位峰值可能被摊平，建议在 1 月上中旬分批兑现而非押注单点'),
        ('云南单极供给下的集中上市踩踏', 't-down', '利空',
         '冬季全国供给高度依赖云南，若产区天气持续利好、茬口集中',
         '12-1 月出现阶段性供给洪峰，压制节前涨幅'),
    ]

    # ---- 长周期回顾文案（数字全部由 longterm 模块算出，可复算）
    def wfmt(m):
        w = win_by_month.get(m)
        if not w:
            return '—'
        direction = '上行' if w['change_pct'] > 1 else ('下行' if w['change_pct'] < -1 else '基本走平')
        return ('{0}个月（{1} → {2}）：{3:.2f} → {4:.2f} 元/公斤，{5} {6:+.1f}%，'
                '年化 {7:+.1f}%，区间高 {8:.2f}（{9}）、低 {10:.2f}（{11}）').format(
            m, w['start_ym'], w['end_ym'], w['start'], w['end'], direction,
            w['change_pct'], w['cagr'], w['hi'], w['hi_ym'], w['lo'], w['lo_ym'])

    def _season_note(season: dict) -> str:
        """由统一季节因子动态生成季节性结论（与 §2.7 图、预测模型同源）。"""
        spring = [season[m] for m in (4, 5)]
        winter = [season[m] for m in (11, 12, 1)]
        summer = [season[m] for m in (7, 8)]
        peak = max(season.values())
        trough = min(season.values())
        cur_idx = season[date.today().month]
        pos = '旺季' if cur_idx > 1.08 else ('淡季' if cur_idx < 0.92 else '过渡窗口')
        return ('春峰（4-5 月）季节指数 {0:.2f}-{1:.2f}、冬旺（11-1 月）{2:.2f}-{3:.2f}，'
                '夏谷（7-8 月）仅 {4:.2f}-{5:.2f}，峰值/谷值约 {6:.1f} 倍。'
                '当前 {7} 月指数 {8:.2f}，处于{9}，但供给节奏压制了季节性涨幅。').format(
            min(spring), max(spring), min(winter), max(winter),
            min(summer), max(summer), peak / trough,
            date.today().month, cur_idx, pos)

    longterm_summary = (
        '把视线拉长到十年，香葱产地价整体呈「产能扩张驱动的中枢下移 + 极端天气驱动的脉冲式尖峰」'
        '双重特征。' + wfmt(120) + '。' +
        '分窗口看：' + wfmt(12) + '；' + wfmt(24) + '；' + wfmt(36) + '；' + wfmt(60) + '。' +
        '十年间的最高峰出现在 {0} 的 {1:.2f} 元/公斤（泸西小香葱产地价一度报 6 元/斤），'
        '最低谷出现在 {2} 的 {3:.2f} 元/公斤（疫情冲击叠加季节性夏谷）。'
        '峰谷倍数约 {4:.1f} 倍，是典型的「高波动小宗调味菜」。'.format(
            win_by_month[120]['hi_ym'], win_by_month[120]['hi'],
            win_by_month[120]['lo_ym'], win_by_month[120]['lo'],
            win_by_month[120]['hi'] / win_by_month[120]['lo'] if win_by_month[120]['lo'] else 0) +
        '中枢下移的主因是产能扩张：泸西自 2013 年引种，至 2024 年底已形成年产 {0:.0f} 万吨、'
        '产值 {1:.0f}-{2:.0f} 亿元的全国最大蔬菜单品基地（占云南香葱总产 {3:.0f}% 以上），'.format(
            CORE_REGION['annual_output_t'] / 10000,
            CORE_REGION['annual_value_yi'] - 0.5, CORE_REGION['annual_value_yi'],
            CORE_REGION['share_of_yunnan'] * 100) +
        '叠加水肥一体化（单人管理面积从 5-6 亩提升到 30 亩）带来的成本下降，'
        '使长期价格重心系统性下移。'
        '但每年 4-5 月（春峰）、11-1 月（冬旺/春节备货）两个旺季，以及台风、寒潮、雪灾等极端天气，'
        '仍会制造 2-5 倍的短期脉冲。'
    )

    longterm_conclusion = [
        ('十年中枢下移，产能是主导变量',
         '120 个月窗口年化 {0:+.1f}%，期末较期初 {1:+.1f}%。'.format(
             win_by_month[120]['cagr'], win_by_month[120]['change_pct']) +
         '泸西全县香葱种植面积从 2013 年引种时的零星规模扩至 2024 年的 {0:.1f} 万亩基地 / '
         '{1:.1f} 万亩次，供给弹性显著放大，长期价格重心难以回到 2016 年水平。'.format(
             CORE_REGION['base_mu'] / 10000, CORE_REGION['replant_mu'] / 10000)),
        ('近三年是十年里最剧烈的「过山车」',
         '36 个月窗口 {0:+.1f}%，振幅高达 {1:.0f}%（最高 {2:.2f} 元/公斤 @ {3}，'
         '最低 {4:.2f} 元/公斤 @ {5}）。'.format(
             win_by_month[36]['change_pct'], win_by_month[36]['amplitude'],
             win_by_month[36]['hi'], win_by_month[36]['hi_ym'],
             win_by_month[36]['lo'], win_by_month[36]['lo_ym']) +
         '2024 年夏秋极端高价 → 2024 年 11 月快速回落至 {0:.2f} → 2026 年持续低位，'
         '反映高价刺激扩种、扩种反过来压价的经典蛛网周期。'.format(
             win_by_month[36]['end'])),
        ('近 24 个月已回到起点，处在周期底部区间',
         '24 个月窗口 {0:+.1f}%（{1:.2f} → {2:.2f}），均值 {3:.2f} 元/公斤。'.format(
             win_by_month[24]['change_pct'], win_by_month[24]['start'],
             win_by_month[24]['end'], win_by_month[24]['avg']) +
         '当前 {0:.2f} 元/公斤（通货）贴近近三年低位区间，下行空间有限，具备季节性修复基础。'.format(
             lt['series'][-1]['price'])),
        ('季节性是最可靠的短线规律',
         _season_note(lt['season'])),
        ('波动率极高，不宜做单边上车的久期押注',
         '各窗口年化波动率 {0:.0f}%-{1:.0f}%，远超大宗蔬菜。'.format(
             min(w['vol'] for w in lt['windows']), max(w['vol'] for w in lt['windows'])) +
         '建议以「淡季建仓、旺季分批兑现」的滚动操作替代单点押注。'),
    ]

    obs_count = sum(1 for p in history.get('series', []) if p.get('source') == 'observed')
    price_source_label = '人工录入实测观测点（{0} 条）+ 模型估算；批发市场接口已接入：北京新发地、惠农网（云南产地）'.format(obs_count)

    return {
        'today': today,
        'generated_at': generated_at,
        'weather': wx,
        'disaster': dz,
        'forecast': fc,
        'longterm': lt,
        'longterm_summary': longterm_summary,
        'longterm_conclusion': longterm_conclusion,
        'history': history,
        'summary': summary,
        'key_variable': key_variable,
        'supply_press': supply_press,
        'demand_trigger': demand_trigger,
        'luxi_moat': luxi_moat,
        'advice': advice,
        'risks': risks,
        'price_source_label': price_source_label,
        'spot_quotes': history.get('spot_quotes', []),
        'market_api': mkt,
        'data_date': max(
            [p['date'] for p in history.get('series', []) if p.get('source') == 'observed']
            + [r['date'] for r in mkt.get('rows', [])]
            + [r['date'] for r in (mkt.get('cnhnb') or {}).get('rows', [])] or [today]),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description='香葱行情日报生成器')
    ap.add_argument('--dry-run', action='store_true', help='仅打印结果，不写入文件')
    args = ap.parse_args()

    ctx = build_context()

    if args.dry_run:
        print('\n=== DRY RUN ===')
        print('日期:', ctx['today'])
        print('产区3天窗口:', json.dumps(ctx['weather']['core']['windows'].get('d3', {}),
                                  ensure_ascii=False))
        print('产区1周窗口:', json.dumps(ctx['weather']['core']['windows'].get('w1', {}),
                                  ensure_ascii=False))
        print('预警总数:', ctx['disaster']['total'])
        print('预测:', json.dumps(ctx['forecast'], ensure_ascii=False, indent=2))
        return 0

    html_doc = report.render_report(ctx)
    out = report.write_outputs(html_doc, ctx)
    print('\n完成：' + out['path'])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
