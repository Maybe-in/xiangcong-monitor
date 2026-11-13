# -*- coding: utf-8 -*-
"""刷新今日（2026-11-13）天气与自然灾害快照并落盘。"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from src import weather, disaster  # noqa: E402

BJ = timezone(timedelta(hours=8))
DATE = "2026-11-13"
BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")


def save(name, obj):
    p = os.path.join(DATA, name)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    print("[OK] saved", name, "size", os.path.getsize(p))


# 1) 天气
try:
    wx = weather.build_weather_snapshot()
    save(f"weather_{DATE}.json", wx)
    print("weather generated_at:", wx.get("generated_at"))
except Exception as e:
    print("[WARN] weather fetch failed:", repr(e)[:300])

# 2) 灾害
try:
    dz = disaster.build_disaster_snapshot()
    save(f"disaster_{DATE}.json", dz)
    print("disaster total:", dz.get("total"), "generated_at:", dz.get("generated_at"))
except Exception as e:
    print("[WARN] disaster fetch failed:", repr(e)[:300])
