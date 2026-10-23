# -*- coding: utf-8 -*-
"""天气数据抓取：Open-Meteo 预报 API + 历史归档 API（计算距平）。

仅依赖 Python 标准库，便于在 GitHub Actions 上零依赖运行。
"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta

from .config import CORE_REGION, OBSERVATION_POINTS

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

UA = "xiangcong-monitor/1.0 (agricultural market research)"

# WMO weather code → 中文
WMO_CN = {
    0: "晴", 1: "晴间多云", 2: "局部多云", 3: "阴",
    45: "雾", 48: "冻雾",
    51: "毛毛雨", 53: "毛毛雨", 55: "强毛毛雨",
    56: "冻毛毛雨", 57: "强冻毛毛雨",
    61: "小雨", 63: "中雨", 65: "大雨",
    66: "冻雨", 67: "强冻雨",
    71: "小雪", 73: "中雪", 75: "大雪", 77: "米雪",
    80: "阵雨", 81: "中阵雨", 82: "强阵雨",
    85: "小阵雪", 86: "大阵雪",
    95: "雷阵雨", 96: "雷阵雨伴冰雹", 99: "雷阵雨伴强冰雹",
}


def _get_json(url: str, params: dict, timeout: int = 30, retries: int = 3) -> dict | None:
    full = f"{url}?{urllib.parse.urlencode(params)}"
    for attempt in range(1, retries + 1):
        req = urllib.request.Request(full, headers={"User-Agent": UA, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            print(f"[weather] 请求失败({attempt}/{retries}): {exc}")
            if attempt < retries:
                time.sleep(1.5 * attempt)
    return None


def fetch_forecast(lat: float, lon: float, days: int = 16) -> list[dict]:
    """抓取逐日预报。"""
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,"
                 "precipitation_probability_max,weather_code,wind_speed_10m_max",
        "timezone": "Asia/Shanghai",
        "forecast_days": days,
    }
    data = _get_json(FORECAST_URL, params)
    if not data or "daily" not in data:
        return []
    d = data["daily"]
    out = []
    for i, day in enumerate(d.get("time", [])):
        code = (d.get("weather_code") or [None] * len(d["time"]))[i]
        out.append({
            "date": day,
            "tmax": (d.get("temperature_2m_max") or [None] * len(d["time"]))[i],
            "tmin": (d.get("temperature_2m_min") or [None] * len(d["time"]))[i],
            "precip": (d.get("precipitation_sum") or [None] * len(d["time"]))[i] or 0,
            "pop": (d.get("precipitation_probability_max") or [None] * len(d["time"]))[i],
            "wind": (d.get("wind_speed_10m_max") or [None] * len(d["time"]))[i] or 0,
            "code": code,
            "weather": WMO_CN.get(code, "—"),
        })
    return out


def fetch_recent_climatology(lat: float, lon: float, lookback_days: int = 30) -> dict:
    """抓取近 N 天实测，作为距平基准。失败则返回 None，由调用方使用气候态兜底。"""
    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=lookback_days)
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
        "timezone": "Asia/Shanghai",
    }
    data = _get_json(ARCHIVE_URL, params, timeout=40)
    if not data or "daily" not in data:
        return {}
    d = data["daily"]
    tmax = [x for x in (d.get("temperature_2m_max") or []) if x is not None]
    tmin = [x for x in (d.get("temperature_2m_min") or []) if x is not None]
    prcp = [x or 0 for x in (d.get("precipitation_sum") or [])]
    if not tmax:
        return {}
    return {
        "tmax_mean": sum(tmax) / len(tmax),
        "tmin_mean": sum(tmin) / len(tmin) if tmin else None,
        "precip_mean": sum(prcp) / len(prcp),
        "samples": len(tmax),
        "window": f"{start.isoformat()} ~ {end.isoformat()}",
    }


def summarize_window(days: list[dict], start_idx: int, end_idx: int) -> dict:
    """统计某个窗口（含端点）的天气特征。索引基于预报数组。"""
    seg = days[start_idx:end_idx]
    if not seg:
        return {}
    tmax = [d["tmax"] for d in seg if d["tmax"] is not None]
    tmin = [d["tmin"] for d in seg if d["tmin"] is not None]
    prcp = [d["precip"] for d in seg]
    wind = [d["wind"] for d in seg]
    rainy = [d for d in seg if (d["precip"] or 0) >= 1.0]
    heavy = [d for d in seg if (d["precip"] or 0) >= 10.0]
    gale = [d for d in seg if (d["wind"] or 0) >= 17.0]
    return {
        "tmax_avg": round(sum(tmax) / len(tmax), 1) if tmax else None,
        "tmin_avg": round(sum(tmin) / len(tmin), 1) if tmin else None,
        "precip_total": round(sum(prcp), 1),
        "rainy_days": len(rainy),
        "heavy_rain_days": len(heavy),
        "gale_days": len(gale),
        "wind_max": round(max(wind), 1) if wind else None,
        "dominant": _dominant_weather(seg),
    }


# 雾/霾属短时现象，不反映当日整体天气，统计主导天气时降权
MINOR_WEATHER = {"雾", "冻雾", "霾"}


def _dominant_weather(seg: list[dict]) -> str:
    cnt: dict[str, int] = {}
    for d in seg:
        cnt[d["weather"]] = cnt.get(d["weather"], 0) + 1
    if not cnt:
        return "—"
    major = {k: v for k, v in cnt.items() if k not in MINOR_WEATHER}
    pool = major or cnt
    return max(pool.items(), key=lambda kv: kv[1])[0]


def build_weather_snapshot() -> dict:
    """汇总核心产区与全国观测点的天气。"""
    core = fetch_forecast(CORE_REGION["lat"], CORE_REGION["lon"], days=16)
    core_clim = fetch_recent_climatology(CORE_REGION["lat"], CORE_REGION["lon"])

    # 四档窗口（索引）：3天 / 1周 / 半月(至第15天) / 剩余预报期
    windows = {}
    if core:
        windows = {
            "d3": summarize_window(core, 0, 3),
            "w1": summarize_window(core, 0, 7),
            "h1": summarize_window(core, 7, 15),
            "m1": summarize_window(core, 0, 16),
        }

    points = []
    for p in OBSERVATION_POINTS:
        fc = fetch_forecast(p["lat"], p["lon"], days=7)
        s = summarize_window(fc, 0, 7) if fc else {}
        points.append({**p, "w7": s})

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "core": {
            "name": CORE_REGION["name"],
            "daily": core,
            "climatology": core_clim,
            "windows": windows,
        },
        "points": points,
    }


if __name__ == "__main__":
    snap = build_weather_snapshot()
    print(json.dumps(snap["core"]["windows"], ensure_ascii=False, indent=2))
    print("核心产区逐日预报：")
    for d in snap["core"]["daily"][:8]:
        print(f"  {d['date']}  {d['weather']:<6} {d['tmin']}~{d['tmax']}℃  降水{d['precip']}mm")
