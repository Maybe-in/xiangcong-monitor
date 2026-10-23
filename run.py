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

from src import disaster, price, report, weather  # noqa: E402
from src.config import CORE_REGION, MODEL  # noqa: E402

WEEKDAY_CN = ['一', '二', '三', '四', '五', '六', '日']


def _safe(d: dict, key: str, default='—'):
    v = d.get(key)
    return default if v is None else v


def blk_current(fc: dict) -> str:
    v = fc.get('黑葱', {}).get('current')
    return f'{v:.2f}' if isinstance(v, (int, float)) else '—'


def build_context() -> dict:
    today = date.today().isoformat()
    generated_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    print('[1/4] 抓取天气数据 ...')
    wx = weather.build_weather_snapshot()
    core_daily = wx['core']['daily']
    win = wx['core']['windows']
    print('      核心产区 {0}：{1} 天预报，观测点 {2} 个'.format(
        CORE_REGION['name'], len(core_daily), len(wx['points'])))

    print('[2/4] 抓取自然灾害预警 ...')
    dz = disaster.build_disaster_snapshot()
    print('      全国生效预警：{0} 条'.format(dz['total']))

    print('[3/4] 计算四档价格预测 ...')
    history = price.load_history()
    clim = wx['core'].get('climatology') or {}
    fc = price.build_forecast(history, core_daily, clim=clim)
    red = fc['红香葱']
    if core_daily:
        price.append_estimate(history, '红香葱', red['current'], '模型基准值')
    price.save_history(history)
    print('      红香葱中枢：{0} → {1}'.format(
        red['current'], ' / '.join(str(r['center']) for r in red['rows'])))

    print('[4/4] 渲染报告 ...')

    w3 = win.get('d3', {})
    w1 = win.get('w1', {})
    h1 = win.get('h1', {})

    r3, r7, r15, r30 = red['rows']
    d3txt, _ = price.direction_tag(r3['delta_pct'])
    d30txt, _ = price.direction_tag(r30['delta_pct'])

    drop_pct = abs((red['current'] / 6.10 - 1) * 100)

    summary = (
        '当前全国香葱处于季节性供给高峰下的低位承压期。' + CORE_REGION['name'] +
        '产区红香葱产地中枢报 ' + str(red['current']) + ' 元/公斤，黑葱报 ' +
        blk_current(fc) + ' 元/公斤；较 10 月中旬高点（红香葱 6.10 元/公斤）回落约 ' +
        '{0:.0f}%。'.format(drop_pct) +
        '主导逻辑是「天气利好→丰产不丰收」的反向传导：主产区温光适宜、茬口衔接顺畅，'
        '供给持续扩容，而终端仅有刚性需求，渠道按需补库、低库存周转，缺乏集中备货拉涨动力。'
        '未来 3 天产区以' + str(_safe(w3, 'dominant')) + '为主、累计降水 ' +
        str(_safe(w3, 'precip_total')) + ' mm，采收顺畅、出货集中，价格' + d3txt + '；'
        '未来一周累计降水升至 ' + str(_safe(w1, 'precip_total')) + ' mm、雨日 ' +
        str(_safe(w1, 'rainy_days')) + ' 天，后半周起采收与运输受扰，跌势有望止住；'
        '半月窗口（第 8-15 天）累计降水 ' + str(_safe(h1, 'precip_total')) +
        ' mm，叠加北方秋菜退市、供给切换为「南菜北运」，预计中枢回升至 ' +
        str(r15['center']) + ' 元/公斤（' + '{0:+.1f}%'.format(r15['delta_pct']) + '）；'
        '一个月后随冬季餐饮消费与元旦前备货启动，中枢上看 ' + str(r30['center']) +
        ' 元/公斤（' + '{0:+.1f}%'.format(r30['delta_pct']) + '），精品分级货溢价将进一步拉大。'
    )

    key_variable = (
        '超强厄尔尼诺（有监测记录以来最强，海温指数峰值预计 11 月前后达 3.2-3.5℃）背景下，'
        '11 月江南、西南降水偏多 5-8 成，是打破供大于求格局、触发行情反转的最主要潜在推手。'
        '若降雨不及预期、产区持续晴好，半月与一月预测需下修 3-8 个百分点。'
    )

    supply_press = [
        '北方露地秋菜处于产量爬坡期，北菜南运规模维持高位',
        '销区本地秋菜陆续上市，形成「北方菜 + 本地菜 + 云南菜」三重供给叠加',
        '云南产区茬口衔接顺畅，气候适宜、病害少、商品率高',
        '全国蔬菜在田面积同比增加约 100 多万亩',
    ]
    demand_trigger = [
        '超强厄尔尼诺下 11 月江南、西南降水偏多 5-8 成',
        '11 月上中旬云南两次明显降雨过程，采收与运输受扰',
        '北方秋菜退市，供给由「北菜南运」切换为「南菜北运」',
        '冬季餐饮（火锅/面食）与元旦前备货需求季节性回升',
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
    ]

    risks = [
        ('极端天气缺位（最大下行风险）', 't-down', '利空',
         '11 月云南降雨偏多 10%-20% 未兑现，产区持续晴好',
         '下修半月/一月预测 3-8 个百分点，低位周期延长'),
        ('强降雨/渍涝超预期', 't-up', '利多',
         '厄尔尼诺峰值叠加，江南、西南降水偏多 5-8 成',
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
    ]

    obs_count = sum(1 for p in history.get('series', []) if p.get('source') == 'observed')
    price_source_label = '人工录入实测观测点（{0} 条）+ 模型估算（公开行情接口未接入）'.format(obs_count)

    return {
        'today': today,
        'generated_at': generated_at,
        'weather': wx,
        'disaster': dz,
        'forecast': fc,
        'history': history,
        'summary': summary,
        'key_variable': key_variable,
        'supply_press': supply_press,
        'demand_trigger': demand_trigger,
        'luxi_moat': luxi_moat,
        'advice': advice,
        'risks': risks,
        'price_source_label': price_source_label,
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
