# -*- coding: utf-8 -*-
"""批发市场行情接口抓取（真实数据源，自动更新）。

当前接入：
  1. 北京新发地农产品批发市场（xinfadi.com.cn）——公开日度行情接口，
     品种覆盖 香葱/小葱/大葱/葱头，单位 元/斤（内部统一换算为 元/公斤）。

设计原则：
  - 抓取失败一律降级（返回 ok=False + error），主流程不得因接口故障中断；
  - 每次抓取结果归档到 data/market_quotes.json，形成可用于回测的历史序列；
  - 产地等级盘口（泸西 A货/包地/期货吨盘）目前无公开接口，报告中如实标注「待接入」，
    禁止用推算值冒充接口数据。
"""

from __future__ import annotations

import json
import os
import re
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

XINFADI_URL = "http://www.xinfadi.com.cn/getPriceData.html"
JIN_PER_KG = 2.0  # 新发地单位为元/斤
MARKET_PATH = os.path.join(DATA_DIR, "market_quotes.json")

# 关注的葱类品种（新发地实际存在的品名）
TRACK_VARIETIES = ["香葱", "小葱", "大葱"]

# 惠农网（cnhnb.com）产地行情公开页——覆盖泸西等产区葱类报价，单位 元/斤
# 首选云南频道（含香葱/小葱/四季葱/火葱等多品种），缺数据时回退泸西县频道。
CNHNB_URLS = [
    "https://www.cnhnb.com/hangqing/q-2000478-0-0-25/",
    "https://m.cnhnb.com/hangqing/cd-2000478-0-0-4556/",
]


def _http_json(prod_name: str, limit: int = 80, timeout: int = 25) -> dict:
    body = urllib.parse.urlencode(
        {"limit": limit, "current": 1, "prodName": prod_name}).encode()
    req = urllib.request.Request(
        XINFADI_URL, data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded",
                 "User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _f(v) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def fetch_xinfadi(days: int = 6) -> dict:
    """抓取新发地葱类近 N 天行情。返回 {'rows': [...], 'ok': bool, 'error': str}。

    row: {item, date, low, high, avg, places, unit:'元/公斤', source:'xinfadi'}
    同一品种同日多条（不同产地）聚合为一条：区间取全体低/高，中枢取均价的均值。
    """
    rows: list[dict] = []
    errors = []
    for prod in TRACK_VARIETIES:
        try:
            data = _http_json(prod)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{prod}: {exc}")
            continue
        raw = data.get("list") or []
        cutoff = None
        # 以抓到的最新日期为基准取近 N 天
        all_dates = sorted({str(r.get("pubDate", ""))[:10] for r in raw if r.get("pubDate")})
        if not all_dates:
            errors.append(f"{prod}: 无数据")
            continue
        latest = date.fromisoformat(all_dates[-1])
        cutoff = (latest - timedelta(days=days - 1)).isoformat()

        buckets: dict[str, list[dict]] = {}
        for r in raw:
            d = str(r.get("pubDate", ""))[:10]
            if d < cutoff:
                continue
            lo, hi, avg = _f(r.get("lowPrice")), _f(r.get("highPrice")), _f(r.get("avgPrice"))
            if lo is None or hi is None:
                continue
            buckets.setdefault(d, []).append(
                {"lo": lo * JIN_PER_KG, "hi": hi * JIN_PER_KG,
                 "avg": (avg if avg is not None else (lo + hi) / 2) * JIN_PER_KG,
                 "place": r.get("place") or ""})
        for d, items in sorted(buckets.items()):
            rows.append({
                "item": prod,
                "date": d,
                "low": round(min(x["lo"] for x in items), 2),
                "high": round(max(x["hi"] for x in items), 2),
                "mid": round(sum(x["avg"] for x in items) / len(items), 2),
                "places": "、".join(sorted({x["place"] for x in items if x["place"]})),
                "unit": "元/公斤",
                "source": "xinfadi",
            })
    return {"rows": rows, "ok": bool(rows), "error": "；".join(errors)}


def _http_get(url: str, timeout: int = 20, mobile: bool = False) -> str:
    ua = ("Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
          "AppleWebKit/605.1.15") if mobile else "Mozilla/5.0"
    req = urllib.request.Request(
        url, headers={"User-Agent": ua, "Accept": "text/html,application/xhtml+xml"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "ignore")


def _clean_tags(s: str) -> str:
    return re.sub(r"<[^>]+>", " ", s)


def _parse_cnhnb(text: str) -> list[dict]:
    """从行情页文本解析葱类产地报价。

    返回 [{item, date, origin, price_jin}, ...]，origin 形如
    “云南红河哈尼族彝族自治州泸西县”。
    """
    plain = _clean_tags(text)
    out: list[dict] = []
    pat = re.compile(r"(\d{4}-\d{2}-\d{2})(.*?)([\d.]+)\s*元/斤", re.S)
    for m in pat.finditer(plain):
        d, mid, price = m.group(1), m.group(2).strip(), m.group(3)
        seg = re.sub(r"\s+", " ", mid).strip()
        if "云南" not in seg:        # 只取云南产区（含泸西/通海/宾川等）
            continue
        prod, origin = seg.split("云南", 1)
        origin, prod = "云南" + origin.strip(), prod.strip()
        if not prod or not origin:
            continue
        try:
            pj = float(price)
        except ValueError:
            continue
        out.append({"item": prod, "date": d, "origin": origin, "price_jin": pj})
    return out


def fetch_cnhnb() -> dict:
    """抓取惠农网云南葱类产地行情。返回 {'rows': [...], 'ok': bool, 'error': str}。

    row: {item, date, origin, low, high, mid, ton, unit, unit_ton, source:'cnhnb'}
    元/斤 → 元/公斤 ×2；元/吨 = 元/公斤 ×1000。
    """
    rows: list[dict] = []
    errors: list[str] = []
    for url in CNHNB_URLS:
        try:
            text = _http_get(url, mobile=url.startswith("https://m."))
            parsed = _parse_cnhnb(text)
            if parsed:
                rows.extend(parsed)
                break
            errors.append(f"{url}: 无解析结果")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{url}: {exc}")
    # 同 产地+品种+日期 去重，保留首条
    seen: set[tuple] = set()
    uniq: list[dict] = []
    for r in rows:
        k = (r["origin"], r["item"], r["date"])
        if k not in seen:
            seen.add(k)
            uniq.append(r)
    std: list[dict] = []
    for r in uniq:
        pj = r["price_jin"]
        std.append({
            "item": r["item"], "date": r["date"], "origin": r["origin"],
            "low": round(pj * 2, 2), "high": round(pj * 2, 2), "mid": round(pj * 2, 2),
            "ton": round(pj * 2000),
            "unit": "元/公斤", "unit_ton": "元/吨", "source": "cnhnb",
        })
    return {"rows": std, "ok": bool(std), "error": "；".join(errors),
            "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "market": "惠农网（cnhnb.com）云南产地行情"}


def load_archive() -> dict:
    if os.path.exists(MARKET_PATH):
        try:
            with open(MARKET_PATH, encoding="utf-8") as f:
                return json.load(f)
        except Exception:  # noqa: BLE001
            pass
    return {"unit": "元/公斤（新发地接口，元/斤 ×2 换算）", "history": []}


def save_archive(archive: dict) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(MARKET_PATH, "w", encoding="utf-8") as f:
        json.dump(archive, f, ensure_ascii=False, indent=2)


def build_snapshot(days: int = 6, archive: bool = True) -> dict:
    """抓取 + 归档。返回 snapshot 供 run.py 使用。

    返回结构新增 cnhnb 字段：惠农网云南产地行情（泸西等产区葱类报价）。
    """
    snap = fetch_xinfadi(days=days)
    snap["fetched_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    snap["market"] = "北京新发地农产品批发市场"
    # 惠农网产地行情（独立接口，失败不影响主流程）
    try:
        cnhnb = fetch_cnhnb()
    except Exception as exc:  # noqa: BLE001
        cnhnb = {"rows": [], "ok": False, "error": str(exc)}
    snap["cnhnb"] = cnhnb
    if archive and snap["ok"]:
        try:
            arch = load_archive()
            seen = {(r["item"], r["date"]) for r in arch.get("history", [])}
            for r in snap["rows"]:
                key = (r["item"], r["date"])
                if key not in seen:
                    arch.setdefault("history", []).append(r)
                    seen.add(key)
            arch["history"] = sorted(
                arch["history"], key=lambda r: (r["date"], r["item"]))[-4000:]
            save_archive(arch)
        except Exception:  # noqa: BLE001
            pass  # 归档失败不影响报告生成
    return snap


def prev_today(snap: dict, item: str) -> tuple[dict | None, dict | None]:
    """取某品种最近两个交易日聚合行（昨日 / 今日）。"""
    rows = sorted([r for r in snap.get("rows", []) if r["item"] == item],
                  key=lambda r: r["date"])
    if len(rows) >= 2:
        return rows[-2], rows[-1]
    if len(rows) == 1:
        return None, rows[-1]
    return None, None


if __name__ == "__main__":
    s = build_snapshot()
    print("ok:", s["ok"], "rows:", len(s["rows"]), "error:", s.get("error", ""))
    for r in s["rows"][-9:]:
        print(r["date"], r["item"], r["low"], "-", r["high"], "中枢", r["mid"], r["places"])
