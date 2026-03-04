#!/usr/bin/env python3
"""Fetch USDT fiat benchmark snapshots for HuayuGuide transparency repo.

Primary: Binance P2P, OKX P2P
Fallback: Spot+FX synthetic benchmark
"""

from __future__ import annotations

import json
import math
import os
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

FIATS = ["CNY", "HKD", "PHP"]
BASE = "USDT"
CALC_VERSION = "rt_v2"
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
        if not s:
            return None
        if s.endswith("%"):
            s = s[:-1]
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
        s = "".join(ch for ch in v if ch.isdigit())
        if not s:
            return None
        try:
            return int(s)
        except ValueError:
            return None
    return None


def trimmed_values(values: List[float]) -> List[float]:
    if not values:
        return []
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    if n < 10:
        return sorted_vals
    trim = max(1, int(n * 0.1))
    if n - 2 * trim <= 0:
        return sorted_vals
    return sorted_vals[trim : n - trim]


def summarize_prices(prices: List[float], reliable_count: int, raw_count: int) -> Optional[Dict[str, Any]]:
    clean = [p for p in prices if p > 0 and math.isfinite(p)]
    if not clean:
        return None
    tvals = trimmed_values(clean)
    center = statistics.mean(tvals)
    median = statistics.median(tvals)
    dispersion = None
    if len(tvals) >= 2 and center > 0:
        stdev = statistics.pstdev(tvals)
        dispersion = stdev / center
    # robust center: mix mean + median
    price = (center * 0.6) + (median * 0.4)

    sample_count = len(tvals)
    reliable_ratio = (reliable_count / raw_count) if raw_count > 0 else 0.0
    disp_penalty = 0.0 if dispersion is None else min(20.0, dispersion * 200)
    quality = clamp(60.0 + min(25.0, sample_count * 1.2) + (reliable_ratio * 15.0) - disp_penalty, 40.0, 98.5)

    return {
        "price": price,
        "sample_count": sample_count,
        "raw_count": raw_count,
        "dispersion": dispersion,
        "quality": quality,
    }


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


def pick_reliable_binance_ads(items: List[Dict[str, Any]]) -> Tuple[List[float], int, int]:
    raw_prices: List[float] = []
    reliable_prices: List[float] = []

    for item in items:
        adv = item.get("adv") or {}
        advertiser = item.get("advertiser") or {}
        price = parse_float(adv.get("price"))
        if price is None or price <= 0:
            continue
        raw_prices.append(price)

        finish_rate = parse_float(advertiser.get("monthFinishRate"))
        orders = parse_int(
            advertiser.get("monthOrderCount")
            or advertiser.get("monthOrderNum")
            or advertiser.get("recentOrderNum")
        )

        is_reliable = (
            finish_rate is not None
            and finish_rate >= 98.0
            and orders is not None
            and orders >= 100
        )
        if is_reliable:
            reliable_prices.append(price)

    chosen = reliable_prices if reliable_prices else raw_prices
    return chosen, len(reliable_prices), len(raw_prices)


def fetch_binance_p2p_side(fiat: str, side: str) -> Optional[Dict[str, Any]]:
    # side=bid means user sells U -> tradeType=SELL
    # side=ask means user buys U  -> tradeType=BUY
    trade_type = "SELL" if side == "bid" else "BUY"
    url = "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search"
    payload = {
        "fiat": fiat,
        "page": 1,
        "rows": 20,
        "tradeType": trade_type,
        "asset": BASE,
        "countries": [],
        "proMerchantAds": False,
        "payTypes": [],
    }
    headers = {
        "Origin": "https://p2p.binance.com",
        "Referer": f"https://p2p.binance.com/en/trade/{trade_type.lower()}/{BASE}?fiat={fiat}",
    }

    data = http_post_json(url, payload, headers=headers)
    items = data.get("data") or []
    prices, reliable_count, raw_count = pick_reliable_binance_ads(items)
    summary = summarize_prices(prices, reliable_count, raw_count)
    if summary is None:
        return None

    return {
        "source": "binance_p2p",
        "side": side,
        "price": summary["price"],
        "sample_count": summary["sample_count"],
        "dispersion": summary["dispersion"],
        "quality": summary["quality"],
        "raw_count": summary["raw_count"],
    }


def extract_prices_generic(items: List[Dict[str, Any]]) -> Tuple[List[float], int, int]:
    raw_prices: List[float] = []
    reliable_prices: List[float] = []

    for item in items:
        price = parse_float(item.get("price") or item.get("quote") or item.get("unitPrice"))
        if price is None or price <= 0:
            continue
        raw_prices.append(price)

        finish = parse_float(item.get("completedRate") or item.get("finishRate") or item.get("completionRate"))
        orders = parse_int(item.get("completedOrderQuantity") or item.get("orderCount") or item.get("orders"))
        if finish is not None and finish <= 1.0:
            finish = finish * 100.0

        is_reliable = (
            finish is not None and finish >= 98.0 and orders is not None and orders >= 100
        )
        if is_reliable:
            reliable_prices.append(price)

    chosen = reliable_prices if reliable_prices else raw_prices
    return chosen, len(reliable_prices), len(raw_prices)


def fetch_okx_p2p_side(fiat: str, side: str) -> Optional[Dict[str, Any]]:
    # side mapping: bid=user sells U -> buyers -> side=buy
    okx_side = "buy" if side == "bid" else "sell"

    url = "https://www.okx.com/v3/c2c/tradingOrders/books"
    params = {
        "quoteCurrency": fiat,
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
    }

    data = http_get_json(url, params=params, headers={"Referer": "https://www.okx.com/"})
    rows: List[Dict[str, Any]] = []

    root_data = data.get("data")
    if isinstance(root_data, dict):
        side_rows = root_data.get(okx_side)
        if isinstance(side_rows, list):
            rows = side_rows
    elif isinstance(root_data, list):
        rows = root_data

    prices, reliable_count, raw_count = extract_prices_generic(rows)
    summary = summarize_prices(prices, reliable_count, raw_count)
    if summary is None:
        return None

    return {
        "source": "okx_p2p",
        "side": side,
        "price": summary["price"],
        "sample_count": summary["sample_count"],
        "dispersion": summary["dispersion"],
        "quality": summary["quality"],
        "raw_count": summary["raw_count"],
    }


def fetch_spot_fx_fallback(fiat: str) -> Optional[Dict[str, Any]]:
    # Free FX feed fallback. This is not primary business benchmark.
    data = http_get_json("https://open.er-api.com/v6/latest/USD")
    rates = data.get("rates") or {}
    usd_to_fiat = parse_float(rates.get(fiat))
    if usd_to_fiat is None or usd_to_fiat <= 0:
        return None

    mid = usd_to_fiat
    spread = max(mid * 0.002, 0.0001)
    bid = mid - spread
    ask = mid + spread

    return {
        "source": "spot_fx_fallback",
        "bid": bid,
        "ask": ask,
        "sample_count": 0,
        "dispersion": None,
        "quality": 74.0,
    }


def combine_quotes(fiat: str, bid_candidates: List[Dict[str, Any]], ask_candidates: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    bid_pick = max(bid_candidates, key=lambda x: x.get("quality", 0), default=None)
    ask_pick = max(ask_candidates, key=lambda x: x.get("quality", 0), default=None)
    if not bid_pick or not ask_pick:
        return None

    bid = float(bid_pick["price"])
    ask = float(ask_pick["price"])

    if ask < bid:
        ask = bid * 1.0015

    mid = (bid + ask) / 2.0
    quality = clamp((float(bid_pick.get("quality", 60)) + float(ask_pick.get("quality", 60))) / 2.0, 40.0, 99.0)
    sample_count = int(min(bid_pick.get("sample_count", 0), ask_pick.get("sample_count", 0)))

    dispersion_vals = [
        v for v in [bid_pick.get("dispersion"), ask_pick.get("dispersion")] if isinstance(v, (int, float))
    ]
    dispersion = (sum(dispersion_vals) / len(dispersion_vals)) if dispersion_vals else None

    src_bid = str(bid_pick.get("source", "unknown"))
    src_ask = str(ask_pick.get("source", "unknown"))
    source = src_bid if src_bid == src_ask else f"{src_bid}+{src_ask}"

    ts = now_ts()
    generated = now_iso(ts)
    asof_iso = now_iso(ts)

    digest = f"{BASE}/{fiat}|{bid:.8f}|{ask:.8f}|{source}|{CALC_VERSION}|{ts // 1800}"

    return {
        "pair": f"{BASE}/{fiat}",
        "bid": round(bid, 8),
        "ask": round(ask, 8),
        "mid": round(mid, 8),
        "asof_ts": ts,
        "asof_iso": asof_iso,
        "timezone": "UTC",
        "source": source,
        "source_count": len(set([src_bid, src_ask])),
        "sample_count": sample_count,
        "dispersion": None if dispersion is None else round(float(dispersion), 8),
        "quality_score": round(quality, 1),
        "calc_version": CALC_VERSION,
        "input_hash": str(abs(hash(digest))),
        "generated_at": generated,
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
    fiat = snapshot["pair"].split("/")[1].lower()
    path = month_dir / f"usdt_{fiat}.jsonl"
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

    source_health_path = STATUS_DIR / "source_health.json"
    pipeline_status_path = STATUS_DIR / "pipeline_status.json"

    source_health = load_json(source_health_path) or {"generated_at": now_iso(), "sources": {}}

    attempts: List[str] = []
    errors: List[str] = []
    produced = 0
    last_source = "none"

    for fiat in FIATS:
        bid_candidates: List[Dict[str, Any]] = []
        ask_candidates: List[Dict[str, Any]] = []

        # Binance
        binance_ok = True
        try:
            attempts.append(f"binance_p2p:{fiat}")
            b_bid = fetch_binance_p2p_side(fiat, "bid")
            b_ask = fetch_binance_p2p_side(fiat, "ask")
            if b_bid:
                bid_candidates.append(b_bid)
            if b_ask:
                ask_candidates.append(b_ask)
            if not b_bid or not b_ask:
                binance_ok = False
                raise RuntimeError("missing bid/ask from Binance P2P")
            source_health = update_source_health(source_health, "binance_p2p", True, min(b_bid["sample_count"], b_ask["sample_count"]), None)
        except Exception as e:
            binance_ok = False
            msg = f"binance_p2p:{fiat}:{e}"
            errors.append(msg)
            source_health = update_source_health(source_health, "binance_p2p", False, None, str(e))

        # OKX
        try:
            attempts.append(f"okx_p2p:{fiat}")
            o_bid = fetch_okx_p2p_side(fiat, "bid")
            o_ask = fetch_okx_p2p_side(fiat, "ask")
            if o_bid:
                bid_candidates.append(o_bid)
            if o_ask:
                ask_candidates.append(o_ask)
            if not o_bid or not o_ask:
                raise RuntimeError("missing bid/ask from OKX P2P")
            source_health = update_source_health(source_health, "okx_p2p", True, min(o_bid["sample_count"], o_ask["sample_count"]), None)
        except Exception as e:
            errors.append(f"okx_p2p:{fiat}:{e}")
            source_health = update_source_health(source_health, "okx_p2p", False, None, str(e))

        # Fallback only if one side missing
        if not bid_candidates or not ask_candidates:
            try:
                attempts.append(f"spot_fx_fallback:{fiat}")
                fb = fetch_spot_fx_fallback(fiat)
                if not fb:
                    raise RuntimeError("fallback unavailable")
                if not bid_candidates:
                    bid_candidates.append({
                        "source": fb["source"],
                        "side": "bid",
                        "price": fb["bid"],
                        "sample_count": fb["sample_count"],
                        "dispersion": fb["dispersion"],
                        "quality": fb["quality"],
                    })
                if not ask_candidates:
                    ask_candidates.append({
                        "source": fb["source"],
                        "side": "ask",
                        "price": fb["ask"],
                        "sample_count": fb["sample_count"],
                        "dispersion": fb["dispersion"],
                        "quality": fb["quality"],
                    })
                source_health = update_source_health(source_health, "spot_fx_fallback", True, 0, None)
            except Exception as e:
                errors.append(f"spot_fx_fallback:{fiat}:{e}")
                source_health = update_source_health(source_health, "spot_fx_fallback", False, None, str(e))

        snap = combine_quotes(fiat, bid_candidates, ask_candidates)
        if not snap:
            continue

        # prefer declared source for pipeline status
        last_source = snap.get("source", last_source)

        latest_path = DATA_LATEST / f"usdt_{fiat.lower()}.json"
        save_json(latest_path, snap)
        append_history(snap)
        produced += 1

    save_json(source_health_path, source_health)

    pipeline_status = {
        "generated_at": now_iso(),
        "status": "ok" if produced == len(FIATS) else ("degraded" if produced > 0 else "down"),
        "produced_pairs": produced,
        "required_pairs": len(FIATS),
        "last_source": last_source,
        "attempts": attempts,
        "errors": errors,
    }
    save_json(pipeline_status_path, pipeline_status)

    print(json.dumps(pipeline_status, ensure_ascii=False, indent=2))

    return 0 if produced > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
