#!/usr/bin/env python3
"""Fetch USDT/CNY snapshot only (minimal production pipeline)."""

from __future__ import annotations

import json
import math
import hashlib
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

ROOT = Path(__file__).resolve().parents[1]
DATA_LATEST = ROOT / "data" / "latest"
DATA_HISTORY = ROOT / "data" / "history"
STATUS_DIR = ROOT / "status"

BASE = "USDT"
FIAT = "CNY"
CALC_VERSION = "rt_v3_usdt_cny"
TIMEOUT = 12
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)


def now_ts() -> int:
    return int(time.time())


def now_iso(ts: Optional[int] = None) -> str:
    if ts is None:
        ts = now_ts()
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def parse_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        f = float(v)
        return f if math.isfinite(f) else None
    if isinstance(v, str):
        s = v.strip().replace(",", "")
        if s.endswith("%"):
            s = s[:-1]
        if not s:
            return None
        try:
            f = float(s)
            return f if math.isfinite(f) else None
        except ValueError:
            return None
    return None


def parse_int(v: Any) -> Optional[int]:
    if v is None:
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, float) and math.isfinite(v):
        return int(v)
    if isinstance(v, str):
        digits = "".join(ch for ch in v if ch.isdigit())
        if not digits:
            return None
        try:
            return int(digits)
        except ValueError:
            return None
    return None


def http_get_json(url: str, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    h = {
        "User-Agent": UA,
        "Accept": "application/json, text/plain, */*",
    }
    if headers:
        h.update(headers)
    resp = requests.get(url, headers=h, params=params, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def http_post_json(url: str, payload: Dict[str, Any], headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    h = {
        "User-Agent": UA,
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
    }
    if headers:
        h.update(headers)
    resp = requests.post(url, headers=h, json=payload, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def trimmed(values: List[float]) -> List[float]:
    vals = sorted(v for v in values if v > 0 and math.isfinite(v))
    if len(vals) < 10:
        return vals
    k = max(1, int(len(vals) * 0.1))
    if len(vals) - 2 * k <= 2:
        return vals
    return vals[k:-k]


def summarize(values: List[float], reliable_count: int, raw_count: int) -> Optional[Dict[str, Any]]:
    vals = trimmed(values)
    if not vals:
        return None
    mean = statistics.mean(vals)
    median = statistics.median(vals)
    center = (mean * 0.6) + (median * 0.4)
    dispersion = None
    if len(vals) >= 2 and center > 0:
        dispersion = statistics.pstdev(vals) / center

    reliable_ratio = (reliable_count / raw_count) if raw_count > 0 else 0.0
    disp_penalty = 0.0 if dispersion is None else min(20.0, dispersion * 220.0)
    quality = clamp(62.0 + min(20.0, len(vals) * 1.1) + (reliable_ratio * 14.0) - disp_penalty, 35.0, 98.5)

    return {
        "price": center,
        "sample_count": len(vals),
        "dispersion": dispersion,
        "quality": quality,
    }


def pick_binance_ads(rows: List[Dict[str, Any]]) -> Tuple[List[float], int, int]:
    raw_prices: List[float] = []
    reliable_prices: List[float] = []

    for row in rows:
        adv = row.get("adv") or {}
        advertiser = row.get("advertiser") or {}
        price = parse_float(adv.get("price"))
        if price is None or price <= 0:
            continue
        raw_prices.append(price)

        finish_rate = parse_float(advertiser.get("monthFinishRate"))
        order_count = parse_int(advertiser.get("monthOrderCount") or advertiser.get("monthOrderNum"))

        if finish_rate is not None and finish_rate >= 98.0 and order_count is not None and order_count >= 100:
            reliable_prices.append(price)

    chosen = reliable_prices if reliable_prices else raw_prices
    return chosen, len(reliable_prices), len(raw_prices)


def pick_okx_ads(rows: List[Dict[str, Any]]) -> Tuple[List[float], int, int]:
    raw_prices: List[float] = []
    reliable_prices: List[float] = []

    for row in rows:
        price = parse_float(row.get("price"))
        if price is None or price <= 0:
            continue
        raw_prices.append(price)

        finish_rate = parse_float(row.get("completedRate"))
        if finish_rate is not None and finish_rate <= 1.0:
            finish_rate *= 100.0
        order_count = parse_int(row.get("completedOrderQuantity"))

        if finish_rate is not None and finish_rate >= 98.0 and order_count is not None and order_count >= 100:
            reliable_prices.append(price)

    chosen = reliable_prices if reliable_prices else raw_prices
    return chosen, len(reliable_prices), len(raw_prices)


def fetch_binance_side(side: str) -> Optional[Dict[str, Any]]:
    trade_type = "SELL" if side == "bid" else "BUY"
    payload = {
        "fiat": FIAT,
        "page": 1,
        "rows": 20,
        "tradeType": trade_type,
        "asset": BASE,
        "countries": [],
        "proMerchantAds": False,
        "payTypes": [],
    }
    data = http_post_json(
        "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search",
        payload,
        headers={"Origin": "https://p2p.binance.com", "Referer": "https://p2p.binance.com/"},
    )
    rows = data.get("data") or []
    prices, reliable_count, raw_count = pick_binance_ads(rows)
    summary = summarize(prices, reliable_count, raw_count)
    if summary is None:
        return None
    return {
        "source": "binance_p2p",
        "side": side,
        "price": summary["price"],
        "sample_count": summary["sample_count"],
        "dispersion": summary["dispersion"],
        "quality": summary["quality"],
    }


def fetch_okx_side(side: str) -> Optional[Dict[str, Any]]:
    okx_side = "buy" if side == "bid" else "sell"
    data = http_get_json(
        "https://www.okx.com/v3/c2c/tradingOrders/books",
        params={
            "quoteCurrency": FIAT,
            "baseCurrency": BASE,
            "side": okx_side,
            "paymentMethod": "all",
            "userType": "all",
            "showTrade": "false",
            "showFollow": "false",
            "showAlreadyTraded": "false",
            "isAbleFilter": "false",
            "quoteMinAmountPerOrder": "0",
            "quoteMaxAmountPerOrder": "0",
            "quoteAmountPerOrder": "0",
            "isOverseasEx": "true",
            "enabledOnly": "true",
            "isDirect": "false",
            "sortType": "price_asc",
            "pageNum": "1",
            "pageSize": "20",
        },
        headers={"Referer": "https://www.okx.com/"},
    )

    rows: List[Dict[str, Any]] = []
    d = data.get("data")
    if isinstance(d, dict):
        arr = d.get(okx_side)
        if isinstance(arr, list):
            rows = arr
    elif isinstance(d, list):
        rows = d

    prices, reliable_count, raw_count = pick_okx_ads(rows)
    summary = summarize(prices, reliable_count, raw_count)
    if summary is None:
        return None

    return {
        "source": "okx_p2p",
        "side": side,
        "price": summary["price"],
        "sample_count": summary["sample_count"],
        "dispersion": summary["dispersion"],
        "quality": summary["quality"],
    }


def choose_best(candidates: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not candidates:
        return None
    return max(candidates, key=lambda x: float(x.get("quality", 0.0)))


def build_snapshot(bid_pick: Dict[str, Any], ask_pick: Dict[str, Any]) -> Dict[str, Any]:
    bid = float(bid_pick["price"])
    ask = float(ask_pick["price"])
    if ask < bid:
        ask = bid * 1.0015

    mid = (bid + ask) / 2.0
    ts = now_ts()
    src_bid = str(bid_pick.get("source", "unknown"))
    src_ask = str(ask_pick.get("source", "unknown"))
    source = src_bid if src_bid == src_ask else f"{src_bid}+{src_ask}"

    disp_vals = [v for v in [bid_pick.get("dispersion"), ask_pick.get("dispersion")] if isinstance(v, (int, float))]
    dispersion = (sum(disp_vals) / len(disp_vals)) if disp_vals else None

    quality = clamp((float(bid_pick.get("quality", 60.0)) + float(ask_pick.get("quality", 60.0))) / 2.0, 35.0, 99.0)
    sample_count = int(min(int(bid_pick.get("sample_count", 0)), int(ask_pick.get("sample_count", 0))))

    # 审计可复现：使用稳定哈希（禁用 Python 内置 hash 的随机盐特性）
    hash_payload = {
        "pair": f"{BASE}/{FIAT}",
        "bid": round(bid, 8),
        "ask": round(ask, 8),
        "source": source,
        "calc_version": CALC_VERSION,
        "bucket_30m": ts // 1800,
    }
    digest = json.dumps(hash_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    stable_hash = hashlib.sha256(digest.encode("utf-8")).hexdigest()

    return {
        "pair": f"{BASE}/{FIAT}",
        "bid": round(bid, 8),
        "ask": round(ask, 8),
        "mid": round(mid, 8),
        "asof_ts": ts,
        "asof_iso": now_iso(ts),
        "timezone": "UTC",
        "source": source,
        "source_count": len(set([src_bid, src_ask])),
        "sample_count": sample_count,
        "dispersion": None if dispersion is None else round(float(dispersion), 8),
        "quality_score": round(quality, 1),
        "calc_version": CALC_VERSION,
        "input_hash": stable_hash,
        "generated_at": now_iso(ts),
    }


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def append_history(snapshot: Dict[str, Any]) -> None:
    ts = int(snapshot["asof_ts"])
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    month_dir = DATA_HISTORY / f"{dt.year:04d}-{dt.month:02d}"
    month_dir.mkdir(parents=True, exist_ok=True)
    path = month_dir / "usdt_cny.jsonl"
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")) + "\n")


def update_source_health(prev: Dict[str, Any], source: str, ok: bool, sample_count: Optional[int], error: Optional[str]) -> Dict[str, Any]:
    sources = prev.setdefault("sources", {})
    rec = sources.get(source) or {
        "status": "unknown",
        "last_ok_ts": None,
        "last_err_ts": None,
        "fail_streak": 0,
        "last_error": None,
        "last_sample_count": None,
    }

    ts = now_ts()
    if ok:
        rec["last_ok_ts"] = ts
        rec["fail_streak"] = 0
        rec["last_error"] = None
        rec["status"] = "ok" if (sample_count or 0) > 0 else "degraded"
        rec["last_sample_count"] = sample_count if sample_count is not None else rec.get("last_sample_count")
    else:
        rec["last_err_ts"] = ts
        rec["fail_streak"] = int(rec.get("fail_streak") or 0) + 1
        rec["last_error"] = error or "unknown error"
        rec["status"] = "down" if rec["fail_streak"] >= 3 else "degraded"

    sources[source] = rec
    prev["generated_at"] = now_iso(ts)
    return prev


def main() -> int:
    DATA_LATEST.mkdir(parents=True, exist_ok=True)
    STATUS_DIR.mkdir(parents=True, exist_ok=True)

    latest_path = DATA_LATEST / "usdt_cny.json"
    source_health_path = STATUS_DIR / "source_health.json"
    pipeline_status_path = STATUS_DIR / "pipeline_status.json"

    source_health = load_json(source_health_path) or {"generated_at": now_iso(), "sources": {}}
    prev_snapshot = load_json(latest_path)

    attempts: List[str] = []
    errors: List[str] = []
    bid_candidates: List[Dict[str, Any]] = []
    ask_candidates: List[Dict[str, Any]] = []

    # Binance
    try:
        attempts.append("binance_p2p:CNY")
        b_bid = fetch_binance_side("bid")
        b_ask = fetch_binance_side("ask")
        if b_bid:
            bid_candidates.append(b_bid)
        if b_ask:
            ask_candidates.append(b_ask)
        if not b_bid or not b_ask:
            raise RuntimeError("missing bid/ask")
        source_health = update_source_health(source_health, "binance_p2p", True, min(b_bid["sample_count"], b_ask["sample_count"]), None)
    except Exception as e:
        errors.append(f"binance_p2p:CNY:{e}")
        source_health = update_source_health(source_health, "binance_p2p", False, None, str(e))

    # OKX
    try:
        attempts.append("okx_p2p:CNY")
        o_bid = fetch_okx_side("bid")
        o_ask = fetch_okx_side("ask")
        if o_bid:
            bid_candidates.append(o_bid)
        if o_ask:
            ask_candidates.append(o_ask)
        if not o_bid or not o_ask:
            raise RuntimeError("missing bid/ask")
        source_health = update_source_health(source_health, "okx_p2p", True, min(o_bid["sample_count"], o_ask["sample_count"]), None)
    except Exception as e:
        errors.append(f"okx_p2p:CNY:{e}")
        source_health = update_source_health(source_health, "okx_p2p", False, None, str(e))

    bid_pick = choose_best(bid_candidates)
    ask_pick = choose_best(ask_candidates)

    status = "down"
    produced_pairs = 0
    last_source = "none"

    if bid_pick and ask_pick:
        snap = build_snapshot(bid_pick, ask_pick)
        save_json(latest_path, snap)
        append_history(snap)
        produced_pairs = 1
        status = "ok"
        last_source = str(snap.get("source", "unknown"))
    elif prev_snapshot.get("pair") == "USDT/CNY" and parse_float(prev_snapshot.get("mid") or prev_snapshot.get("bid")):
        produced_pairs = 1
        status = "degraded"
        last_source = str(prev_snapshot.get("source", "stale_snapshot"))
        attempts.append("stale_snapshot_reuse")
        errors.append("live sources unavailable; reused latest usdt_cny.json")
    else:
        status = "down"

    save_json(source_health_path, source_health)

    pipeline_status = {
        "generated_at": now_iso(),
        "status": status,
        "produced_pairs": produced_pairs,
        "required_pairs": 1,
        "last_source": last_source,
        "attempts": attempts,
        "errors": errors,
    }
    save_json(pipeline_status_path, pipeline_status)
    print(json.dumps(pipeline_status, ensure_ascii=False, indent=2))

    return 0 if produced_pairs > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
