#!/usr/bin/env python3
"""One-time backfill: merge earthpol.org hourly history into server_history.json.

Keeps the last 18 minutes of live data already in the file, then prepends
the 7-day hourly history from earthpol.org to fill the gap.

Usage (run on the server):
    python3 backfill.py
    # or with a custom data dir:
    DATA_DIR=/opt/data python3 backfill.py
"""

import json, os, time, requests
from pathlib import Path
from datetime import datetime, timezone

DATA_FILE = Path(os.environ.get("DATA_DIR", "data")) / "server_history.json"
SOURCE    = "https://earthpol.org/api/players/onlineHistory"
def main():
    now_ms = int(time.time() * 1000)

    # ── 1. Load existing live history ─────────────────────────────
    try:
        existing = json.loads(DATA_FILE.read_bytes())
    except Exception:
        existing = []

    print(f"Found {len(existing)} existing entries in history file")

    # ── 2. Fetch earthpol.org history ─────────────────────────────
    print(f"Fetching {SOURCE} …")
    r = requests.get(SOURCE, timeout=15)
    r.raise_for_status()
    data    = r.json()
    buckets = data.get("current", [])
    print(f"Got {len(buckets)} hourly buckets "
          f"(generated at {data.get('generatedAt', '?')})")

    # ── 3. Convert to our format ───────────────────────────────────
    historical = []
    for b in buckets:
        ts = int(datetime.fromisoformat(
                     b["t"].replace("Z", "+00:00")
                 ).timestamp() * 1000)
        players = int(b.get("y", 0))
        historical.append({
            "ts":      ts,
            "online":  players > 0,
            "players": players,
            "max":     0,          # not available in hourly data
        })

    # ── 4. Merge: historical fills the past, live data picks up after ─
    # Keep all existing entries that come after the last historical bucket
    hist_end   = historical[-1]["ts"] if historical else 0
    live_tail  = [e for e in existing if e["ts"] > hist_end]
    historical = [e for e in historical if e["ts"] < (existing[0]["ts"] if existing else now_ms)]

    merged = sorted(historical + live_tail, key=lambda e: e["ts"])
    print(f"Merged total: {len(merged)} entries  "
          f"({len(historical)} historical + {len(live_tail)} live)")

    # ── 5. Write back ──────────────────────────────────────────────
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(merged), encoding="utf-8")
    print(f"Written to {DATA_FILE.resolve()}")

    if merged:
        first = datetime.fromtimestamp(merged[0]["ts"]  / 1000, timezone.utc)
        last  = datetime.fromtimestamp(merged[-1]["ts"] / 1000, timezone.utc)
        print(f"Range: {first.strftime('%Y-%m-%d %H:%M UTC')} → "
              f"{last.strftime('%Y-%m-%d %H:%M UTC')}")


if __name__ == "__main__":
    main()
