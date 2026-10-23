# -*- coding: utf-8 -*-
"""香葱价格数据 + 四档预测模型。

价格数据分三层（透明度优先，报告中会标注实际使用的数据层）：
  1. live   —— 公开批发市场价格接口实时抓取（可能不可用）
  2. observed —— 人工录入的实测成交价（data/price_history.json，source=observed）
  3. model  —— 基于季节性 + 天气冲击 + 动量的模型估算（兜底）

预测模型：
    P(h) = P0 × SeasonRatio(target_month, current_month)
               × (1 + Σ weather_impact over [0, h))
               × (1 + momentum × (MA / P0 − 1))
"""

from __future__ import annotations

import json
import os
from collections.abc import Sequence
from datetime import date, datetime, timedelta

from .config import MODEL

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
HISTORY_PATH = os.path.join(DATA_DIR, "price_history.json")

# 默认历史（实测观测点，来源见 source 字段）
DEFAULT_HISTORY = {
    "unit": "元/公斤（云南产地综合交易价，非净重口径）",
    "series": [
        {"date": "2026-10-07", "variety": "小葱", "market": "昆明王旗营", "price": 6.00,
         "source": "observed", "note": "昆明市农业农村局批发均价统计"},
        {"date": "2026-10-14", "variety": "红香葱", "market": "云南产地", "price": 6.10,
         "source": "observed", "note": "云南产地蔬菜综合交易价 5.9-6.3"},
        {"date": "2026-10-14", "variety": "黑葱", "market": "云南产地", "price": 5.70,
         "source": "observed", "note": "云南产地蔬菜综合交易价 5.5-5.9"},
        {"date": "2026-10-23", "variety": "红香葱", "market": "云南产地", "price": 4.70,
         "source": "observed", "note": "云南产地蔬菜综合交易价 4.4-5.0"},
        {"date": "2026-10-23", "variety": "黑葱", "market": "云南产地", "price": 4.15,
         "source": "observed", "note": "云南产地蔬菜综合交易价 3.9-4.4"},
        {"date": "2026-10-23", "variety": "小葱", "market": "昆明王旗营", "price": 3.50,
         "source": "observed", "note": "王旗营批发市场"},
    ],
}


# ------------------------------------------------------------------ 历史数据
def load_history() -> dict:
    if os.path.exists(HISTORY_PATH):
        try:
            with open(HISTORY_PATH, encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:  # noqa: BLE001
            print(f"[price] 读取历史失败({exc})，使用默认基线")
    return json.loads(json.dumps(DEFAULT_HISTORY))


def save_history(history: dict) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def latest_price(history: dict, variety: str, market: str | None = None) -> float | None:
    """最新实测价。默认只取 observed 点，避免模型估算值自我强化。"""
    pts = [p for p in history.get("series", [])
           if p["variety"] == variety
           and p.get("source") == "observed"
           and (market is None or p["market"] == market)]
    if not pts:
        return None
    pts.sort(key=lambda p: p["date"])
    return float(pts[-1]["price"])


def moving_average(history: dict, variety: str, days: int = 20) -> float | None:
    """实测价移动均线（仅 observed 点）。"""
    pts = [p for p in history.get("series", [])
           if p["variety"] == variety and p.get("source") == "observed"]
    if not pts:
        return None
    pts.sort(key=lambda p: p["date"])
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    window = [p["price"] for p in pts if p["date"] >= cutoff]
    pool = window or [p["price"] for p in pts][-5:]
    return sum(pool) / len(pool)


# ------------------------------------------------------------------ 季节性
def _day_of_year(d: date) -> int:
    return d.timetuple().tm_yday


def _month_center_doy(year: int, month: int) -> float:
    """月中心日对应的年内日序（用于相邻月之间线性插值）。"""
    if month == 12:
        nxt = date(year + 1, 1, 1)
    else:
        nxt = date(year, month + 1, 1)
    cur = date(year, month, 1)
    return _day_of_year(cur) + (nxt - cur).days / 2.0


def seasonal_factor(d: date) -> float:
    """按日插值的季节性因子（避免跨月阶跃）。"""
    s = MODEL["seasonality"]
    doy = float(_day_of_year(d))
    y = d.year

    centers = [(m, _month_center_doy(y, m)) for m in range(1, 13)]
    # 定位当前日落在哪两个相邻月中心之间
    if doy <= centers[0][1]:          # 年初，在去年12月与今年1月之间
        m0, m1 = 12, 1
        c0 = _month_center_doy(y - 1, 12) - 365.0
        c1 = centers[0][1]
    elif doy >= centers[-1][1]:       # 年末，在12月与次年1月之间
        m0, m1 = 12, 1
        c0 = centers[11][1]
        c1 = _month_center_doy(y + 1, 1) + 365.0
    else:
        m0, m1, c0, c1 = 1, 2, centers[0][1], centers[1][1]
        for i in range(len(centers) - 1):
            mm0, cc0 = centers[i]
            mm1, cc1 = centers[i + 1]
            if cc0 <= doy <= cc1:
                m0, m1, c0, c1 = mm0, mm1, cc0, cc1
                break

    f0, f1 = s[m0], s[m1]
    if c1 == c0:
        return f0
    w = (doy - c0) / (c1 - c0)
    return f0 + (f1 - f0) * w


def seasonal_ratio(target: date, base: date) -> float:
    f_t = seasonal_factor(target)
    f_b = seasonal_factor(base)
    return f_t / f_b if f_b else 1.0


# ------------------------------------------------------------------ 天气冲击
def weather_impact(daily: Sequence[dict], start: int, end: int,
                   clim: dict | None = None, ref_month: int | None = None
                   ) -> tuple[float, list[str]]:
    """计算某窗口内天气对价格的净冲击（正=推高价格）。

    clim 提供近 30 天实测气温均值作为距平基准（优先），
    否则退回月气候态（MODEL['month_ref_tmax']）。
    """
    seg = list(daily[start:end])
    if not seg:
        return 0.0, []
    heavy = sum(1 for d in seg if (d.get("precip") or 0) >= MODEL["heavy_rain_mm"])
    gale = sum(1 for d in seg if (d.get("wind") or 0) >= MODEL["wind_threshold_ms"])

    tmax_list = [d["tmax"] for d in seg if d.get("tmax") is not None]
    tmax_avg = (sum(tmax_list) / len(tmax_list)) if tmax_list else None

    if tmax_avg is None:
        temp_anom = 0.0
    else:
        ref = None
        if clim:
            ref = clim.get("tmax_mean")
        if ref is None and ref_month:
            ref = MODEL["month_ref_tmax"].get(ref_month)
        if ref is None:
            ref = tmax_avg
        temp_anom = tmax_avg - ref

    impact = (heavy * MODEL["heavy_rain_impact"]
              + gale * MODEL["wind_impact"]
              + temp_anom * MODEL["temp_anomaly_impact"])
    impact = max(MODEL["impact_floor"], min(MODEL["impact_cap"], impact))

    reasons = []
    if heavy:
        reasons.append("强降水(≥{0:.0f}mm){1}天，采收受阻".format(MODEL["heavy_rain_mm"], heavy))
    if gale:
        reasons.append("大风(≥8级){0}天".format(gale))
    if abs(temp_anom) >= 1.0:
        reasons.append("气温较常年{0}{1:.1f}℃，{2}".format(
            '偏高' if temp_anom > 0 else '偏低', abs(temp_anom),
            '加速生长供给增' if temp_anom > 0 else '生长放缓供给延后'))
    return impact, reasons


# ------------------------------------------------------------------ 主预测
FORECAST_HORIZONS = [
    {"key": "d3",  "label": "未来3天",  "days": 3},
    {"key": "w1",  "label": "未来1周",  "days": 7},
    {"key": "h1",  "label": "未来半月", "days": 15},
    {"key": "m1",  "label": "未来1月",  "days": 30},
]


def build_forecast(history: dict, daily: Sequence[dict], horizons=None,
                   clim: dict | None = None) -> dict:
    """生成四档预测。daily 为产区逐日预报（最多16天）。

    预测式：
        P(h) = P₀ × SeasonalRatio(target, today)
                  × (1 + WeatherImpact[0, min(h, len(daily))))
                  × (1 + Momentum(h))
                  × (1 + BeyondForecastAdj)    # 仅当 h > 预报天数
    """
    horizons = horizons or FORECAST_HORIZONS
    today = date.today()
    n_forecast = len(daily)

    results = {}
    for var in ("红香葱", "黑葱"):
        p0 = latest_price(history, var) or MODEL["base_price"]
        ma = moving_average(history, var, MODEL["mean_reversion_days"]) or p0
        rows = []
        for h in horizons:
            days = h["days"]
            target = today + timedelta(days=days)
            ref_month = target.month

            end = min(days, n_forecast)
            wi, reasons = weather_impact(daily, 0, end, clim=clim, ref_month=ref_month)

            sr = seasonal_ratio(target, today)

            # 均值回归强度随时间递增（越远越向均值靠拢）
            strength = MODEL["momentum"] * min(1.0, days / float(MODEL["mean_reversion_days"]))
            momentum = 1.0 + strength * (ma / p0 - 1.0)

            # 超出预报覆盖范围的时段，用气候态修正
            beyond = 0.0
            if days > n_forecast:
                beyond = MODEL["beyond_forecast_adj"]
                reasons = reasons + ["超出逐日预报范围，叠加厄尔尼诺背景下"
                                      "11 月云南降水偏多 10%-20% 的气候态预期"]

            center = p0 * sr * (1.0 + wi) * momentum * (1.0 + beyond)
            band = center * MODEL["band_pct"]
            rows.append({
                "key": h["key"],
                "label": h["label"],
                "target_date": target.isoformat(),
                "low": round(center - band, 2),
                "high": round(center + band, 2),
                "center": round(center, 2),
                "delta_pct": round((center / p0 - 1.0) * 100, 1),
                "reasons": reasons or ["天气条件平稳，供给节奏正常，价格以季节性驱动为主"],
            })
        results[var] = {"current": round(p0, 2), "ma20": round(ma, 2), "rows": rows}
    return results


def direction_tag(delta_pct: float) -> tuple[str, str]:
    """返回 (文案, 样式类)。"""
    if delta_pct <= -3:
        return "偏弱下行", "t-down"
    if delta_pct >= 3:
        return "偏强上行", "t-up"
    return "横盘僵持", "t-flat"


def append_estimate(history: dict, variety: str, price: float, note: str = "") -> None:
    """把当日模型估算值写入历史（用于次日对比与回测）。"""
    today = date.today().isoformat()
    history.setdefault("series", [])
    history["series"] = [p for p in history["series"]
                         if not (p["date"] == today and p["variety"] == variety
                                 and p.get("source") == "model")]
    history["series"].append({
        "date": today, "variety": variety, "market": "云南产地（模型估算）",
        "price": round(price, 2), "source": "model", "note": note,
    })


if __name__ == "__main__":
    h = load_history()
    print(h["unit"], "| 序列点数:", len(h["series"]))
    for v in ("红香葱", "黑葱"):
        print(f"{v}: 最新={latest_price(h, v)} MA20={moving_average(h, v)}")
