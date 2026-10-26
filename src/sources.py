# -*- coding: utf-8 -*-
"""多定时任务行情数据汇总（data/sources/）。

背景：除本仓库的日报流水线外，还有若干「行情生成」定时任务（Gemini / ChatGPT /
全国监测 / grok / 香葱行情 等）在各自的自动化里采集行情。它们按统一 schema
把当日结果落到 `data/sources/<slug>_YYYY-MM-DD.json`，由本模块扫描、容错解析、
统计，供日报的「多源行情汇总」区块**全量**展示，并随仓库一起推送到 GitHub。

统一 schema（生成方写入，字段缺失时由本模块补全为 —）：
{
  "task": "任务名",
  "task_id": "自动化任务ID",
  "date": "YYYY-MM-DD",
  "generated_at": "YYYY-MM-DD HH:MM",
  "market_scope": "全国 / 云南 / 泸西县",
  "quotes": [
    {"date": "YYYY-MM-DD", "item": "香葱", "variety": "", "market": "北京新发地",
     "province": "北京", "price_type": "销地批发价", "unit": "元/公斤",
     "low": 4.0, "high": 6.0, "mid": 5.0, "source": "新发地",
     "source_url": "", "note": ""}
  ],
  "forecasts": [
    {"horizon": "未来3天", "target_date": "YYYY-MM-DD", "item": "香葱",
     "center": 4.49, "low": 4.2, "high": 4.8, "delta_pct": 3.2, "confidence": "高"}
  ],
  "summary": "本期结论"
}

设计原则：任何单个文件损坏/字段异常都不影响主流程，最多降级为空列表。
"""

from __future__ import annotations

import glob
import json
import os
import re
from datetime import date, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCES_DIR = os.path.join(ROOT, "data", "sources")

# 汇总窗口（天）：覆盖「当日 + 前 N-1 天」，防止某个生成任务当天漏跑导致数据缺席
DEFAULT_WINDOW_DAYS = 3


def _f(v):
    """宽松转 float，失败返回 None。"""
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _s(v, default="—"):
    t = str(v).strip() if v is not None else ""
    return t or default


def _norm_quote(q: dict, src_name: str) -> dict | None:
    """规范单条报价行。"""
    if not isinstance(q, dict):
        return None
    mid = _f(q.get("mid"))
    if mid is None:
        mid = _f(q.get("price"))
    if mid is None:
        low, high = _f(q.get("low")), _f(q.get("high"))
        mid = (low + high) / 2 if (low is not None and high is not None) else None
    return {
        "date": _s(q.get("date"), ""),
        "item": _s(q.get("item") or q.get("variety")),
        "market": _s(q.get("market")),
        "province": _s(q.get("province"), ""),
        "price_type": _s(q.get("price_type"), ""),
        "unit": _s(q.get("unit"), "元/公斤"),
        "low": _f(q.get("low")),
        "high": _f(q.get("high")),
        "mid": mid,
        "source": _s(q.get("source"), src_name),
        "note": _s(q.get("note"), ""),
    }


def _norm_forecast(f: dict) -> dict | None:
    """规范单条预测行。"""
    if not isinstance(f, dict):
        return None
    return {
        "horizon": _s(f.get("horizon") or f.get("label")),
        "target_date": _s(f.get("target_date"), ""),
        "item": _s(f.get("item")),
        "center": _f(f.get("center")),
        "low": _f(f.get("low")),
        "high": _f(f.get("high")),
        "delta_pct": _f(f.get("delta_pct")),
        "confidence": _s(f.get("confidence"), ""),
    }


def _slug_from_filename(fname: str) -> str:
    """从落盘文件名取任务 slug，与 report._task_slug 口径一致。

    gemini_2026-10-26.json -> gemini；无日期后缀时整体作为 slug。
    """
    base = (fname or "").rsplit(".", 1)[0]
    head, _, tail = base.rpartition("_")
    if head and len(tail) == 10 and tail[4] == "-":
        base = head
    base = re.sub(r"[^\w\u4e00-\u9fff-]", "-", base).strip("-")
    return base or "task"


def _read_one(path: str) -> dict | None:
    """读取单个源文件并规范化；损坏文件返回 None（不影响其他文件）。"""
    try:
        with open(path, encoding="utf-8") as fh:
            obj = json.load(fh)
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(obj, dict):
        return None

    name = _s(obj.get("task") or os.path.basename(path))
    quotes = [_norm_quote(q, name) for q in (obj.get("quotes") or [])]
    quotes = [q for q in quotes if q]
    forecasts = [_norm_forecast(f) for f in (obj.get("forecasts") or [])]
    forecasts = [f for f in forecasts if f]
    return {
        "task": name,
        "task_id": _s(obj.get("task_id"), ""),
        "date": _s(obj.get("date"), "")[:10],
        "generated_at": _s(obj.get("generated_at"), ""),
        "market_scope": _s(obj.get("market_scope"), ""),
        "file": os.path.basename(path),
        "quotes": quotes,
        "forecasts": forecasts,
        "summary": _s(obj.get("summary"), ""),
    }


def load_sources(window_days: int = DEFAULT_WINDOW_DAYS) -> dict:
    """扫描 data/sources/*.json，返回汇总结果。

    返回：
      {'ok': bool, 'items': [...], 'total_quotes': int, 'total_forecasts': int,
       'task_count': int, 'window_days': int, 'files_scanned': int}
    """
    os.makedirs(SOURCES_DIR, exist_ok=True)
    cutoff = (date.today() - timedelta(days=max(1, window_days) - 1)).isoformat()

    items: list[dict] = []
    scanned = 0
    for path in sorted(glob.glob(os.path.join(SOURCES_DIR, "*.json"))):
        scanned += 1
        one = _read_one(path)
        if not one:
            continue
        # 无日期或日期在窗口外的文件跳过（避免历史文件无限堆积撑爆报告）
        if one["date"] and one["date"] < cutoff:
            continue
        items.append(one)

    items.sort(key=lambda x: (x["date"], x["task"]), reverse=True)

    # 每个任务只保留窗口内最新一期：数据 dated D+N 的生成任务每天落一个新文件，
    # 若不去重，同一任务会按天重复出现在卡片墙、任务页与归档统计里（份数虚高）。
    # 保留「当天漏跑可回退到窗口内前几天」的设计初衷，但每个任务仅计一份。
    seen: set[str] = set()
    latest: list[dict] = []
    for it in items:
        slug = _slug_from_filename(it["file"])
        if slug in seen:
            continue
        seen.add(slug)
        latest.append(it)
    items = latest

    return {
        "ok": bool(items),
        "items": items,
        "total_quotes": sum(len(i["quotes"]) for i in items),
        "total_forecasts": sum(len(i["forecasts"]) for i in items),
        "task_count": len({i["task"] for i in items}),
        "window_days": window_days,
        "files_scanned": scanned,
        "dir": SOURCES_DIR,
    }


if __name__ == "__main__":
    s = load_sources()
    print("任务数:", s["task_count"], "报价条数:", s["total_quotes"],
          "预测条数:", s["total_forecasts"], "扫描文件:", s["files_scanned"])
    for i in s["items"]:
        print(" -", i["date"], i["task"], "quotes=", len(i["quotes"]))
