#!/usr/bin/env python3
"""Health check for USDT/CNY snapshot freshness and shape."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LATEST = ROOT / "data" / "latest"


def check_snapshot(path: Path, max_age_sec: int) -> tuple[bool, str]:
    if not path.exists():
        return False, f"missing file: {path.name}"

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        return False, f"invalid json: {path.name}: {e}"

    pair = str(data.get("pair") or "")
    if pair != "USDT/CNY":
        return False, f"invalid pair in {path.name}: {pair}"

    bid = data.get("bid")
    ask = data.get("ask")
    ts = data.get("asof_ts")

    if not isinstance(bid, (int, float)) or bid <= 0:
        return False, f"invalid bid in {path.name}"
    if not isinstance(ask, (int, float)) or ask <= 0:
        return False, f"invalid ask in {path.name}"
    if ask < bid:
        return False, f"ask<bid in {path.name}"
    if not isinstance(ts, int) or ts <= 0:
        return False, f"invalid asof_ts in {path.name}"

    age = int(time.time()) - ts
    if age > max_age_sec:
        return False, f"stale snapshot {path.name}: age={age}s"

    return True, f"ok: {path.name}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-age-minutes", type=int, default=240)
    args = parser.parse_args()

    max_age_sec = args.max_age_minutes * 60
    path = LATEST / "usdt_cny.json"

    ok, msg = check_snapshot(path, max_age_sec)
    print(msg)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
