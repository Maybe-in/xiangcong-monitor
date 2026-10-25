# -*- coding: utf-8 -*-
"""自然灾害数据：中央气象台全国气象预警接口（nmc.cn/rest/findAlarm）。

对预警按"香葱产业链影响"做二次分级：
  - 产区影响（云南/广西/广东等主产区）：直接冲击采收、运输、品质
  - 销区影响（华东/华南沿海等主销城市）：冲击物流与短期需求
"""

from __future__ import annotations

import json
import re
import urllib.request
from collections import Counter
from datetime import datetime, timezone, timedelta

# 统一北京时间（UTC+8）：本地与 GitHub CI(UTC 服务器) 运行结果一致
BJ_TZ = timezone(timedelta(hours=8))
def bjnow():
    return datetime.now(BJ_TZ)

ALARM_URL = ("http://www.nmc.cn/rest/findAlarm"
             "?pageNo=1&pageSize=100&signaltype=&signallevel=&province=")
UA = "xiangcong-monitor/1.0 (agricultural market research)"

LEVEL_RANK = {"红色": 4, "橙色": 3, "黄色": 2, "蓝色": 1}

# 灾种 → 对香葱产业链的影响描述与权重
HAZARD_PROFILE = {
    "台风":   {"weight": 4, "impact": "大风+强降水，设施受损、采收中断、物流受阻"},
    "暴雨":   {"weight": 4, "impact": "田间渍涝、采收受阻、损耗与病害风险上升"},
    "暴雪":   {"weight": 3, "impact": "运输中断、设施受压"},
    "寒潮":   {"weight": 3, "impact": "生长停滞，但常推高菜价（双刃剑）"},
    "霜冻":   {"weight": 3, "impact": "叶片冻伤，商品率下降"},
    "低温":   {"weight": 2, "impact": "生长放缓，供给延后"},
    "冰雹":   {"weight": 4, "impact": "直接物理损伤，局部绝收"},
    "大风":   {"weight": 2, "impact": "设施受损、蒸腾加剧"},
    "干旱":   {"weight": 2, "impact": "灌溉成本上升、单产下降"},
    "高温":   {"weight": 2, "impact": "品质下降、货架期缩短"},
    "雷电":   {"weight": 1, "impact": "作业安全，短时影响采收"},
    "大雾":   {"weight": 1, "impact": "高速封路，运输延迟"},
    "沙尘暴": {"weight": 1, "impact": "品质与物流轻微影响"},
    "霾":     {"weight": 1, "impact": "影响轻微"},
    "道路结冰": {"weight": 2, "impact": "运输受阻"},
    "持续低温": {"weight": 2, "impact": "生长放缓"},
}

# 核心产区所在省份（用于区分产区/销区影响）
PRODUCTION_PROVINCES = {"云南", "广西", "广东", "福建", "江苏", "四川", "山东", "浙江"}

TITLE_RE = re.compile(r"^(.*?)气象台(?:发布|继续发布)(.*?)(红色|橙色|黄色|蓝色)预警")


def _fetch_raw() -> list[dict]:
    req = urllib.request.Request(ALARM_URL, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data.get("data", {}).get("page", {}).get("list", []) or []
    except Exception as exc:  # noqa: BLE001
        print(f"[disaster] 请求失败: {exc}")
        return []


def parse_title(title: str) -> dict:
    m = TITLE_RE.match(title or "")
    if not m:
        return {"region": title or "—", "hazard": "其他", "level": "—", "rank": 0}
    org, hazard, level = m.group(1), m.group(2), m.group(3)
    # 机构名通常形如 "浙江省绍兴市新昌县"
    prov, city = "—", "—"
    for key in ("省", "自治区", "市"):
        pass
    if org.startswith(("黑龙江", "内蒙古")):
        prov = org[:3]
    else:
        prov = org[:2] if len(org) >= 2 else org
    rest = org[len(prov):]
    if rest:
        city = rest.split("县")[0].split("区")[0].split("市")[0] or rest
    return {
        "region": org,
        "province": prov,
        "city": city,
        "hazard": hazard.strip() or "其他",
        "level": level,
        "rank": LEVEL_RANK.get(level, 0),
    }


def build_disaster_snapshot() -> dict:
    raw = _fetch_raw()
    items = []
    for it in raw:
        info = parse_title(it.get("title", ""))
        prof = HAZARD_PROFILE.get(info["hazard"], {"weight": 1, "impact": "影响轻微"})
        info.update({
            "issuetime": it.get("issuetime", ""),
            "url": f"http://www.nmc.cn{it.get('url', '')}" if it.get("url") else "",
            "weight": prof["weight"],
            "impact": prof["impact"],
            "is_production_area": info.get("province") in PRODUCTION_PROVINCES,
            "risk_score": prof["weight"] * LEVEL_RANK.get(info["level"], 0),
        })
        items.append(info)

    items.sort(key=lambda x: (-x["risk_score"], x["region"]))

    hazard_counter = Counter(i["hazard"] for i in items)
    province_counter = Counter(i.get("province", "—") for i in items)
    prod_items = [i for i in items if i["is_production_area"]]
    sale_items = [i for i in items if not i["is_production_area"]]

    return {
        "generated_at": bjnow().strftime("%Y-%m-%d %H:%M:%S"),
        "total": len(items),
        "top": items[:20],
        "production_area": prod_items[:10],
        "sales_area": sale_items[:10],
        "hazard_stats": hazard_counter.most_common(),
        "province_stats": province_counter.most_common(10),
        "red_orange": [i for i in items if i["rank"] >= 3][:10],
    }


if __name__ == "__main__":
    s = build_disaster_snapshot()
    print(f"全国生效预警总数: {s['total']}")
    print("灾种分布:", s["hazard_stats"])
    print("红色/橙色预警:")
    for i in s["red_orange"]:
        print(f"  {i['region']} · {i['hazard']}{i['level']} · {i['issuetime']}")
