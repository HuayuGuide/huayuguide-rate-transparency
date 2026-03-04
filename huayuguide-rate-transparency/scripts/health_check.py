#!/usr/bin/env python3
"""Health check for latest snapshot freshness and shape."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LATEST = ROOT / "data" / "latest"


def check_pair(path: Path, max_age_sec: int) -> tuple[bool, str]:
    if not path.exists():
        return False, f"missing file: {path.name}"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        return False, f"invalid json: {path.name}: {e}"

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
    parser.add_argument("--max-age-minutes", type=int, default=180)
    args = parser.parse_args()

    files = [LATEST / "usdt_cny.json", LATEST / "usdt_hkd.json", LATEST / "usdt_php.json"]
    max_age_sec = args.max_age_minutes * 60

    ok = True
    for p in files:
        status, msg = check_pair(p, max_age_sec)
        print(msg)
        ok = ok and status

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
