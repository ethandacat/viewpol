#!/usr/bin/env python3
"""
ViewPol data fetcher — keeps all EarthPol API data fresh on disk.

Fetches endpoints one at a time with a short pause between each so
the server is never hammered all at once. Flask handlers read from
these local files instead of making live API calls on every request.

Files written to DATA_DIR (default: ./data/):
  players.json  towns.json  nations.json  sieges.json  shopdata.json
"""

import json, time, os, requests
from pathlib import Path

DATA_DIR = Path(os.environ.get("DATA_DIR", "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

EARTHPOL     = "https://api.earthpol.com/astra"
PAUSE        = 5     # seconds between each individual fetch
TIMEOUT      = 20    # seconds before giving up on a single request

_http = requests.Session()
_http.headers.update({"User-Agent": "viewpol/1.0", "Accept": "application/json"})

# Each entry: (endpoint, output filename, transform_fn or None)
# transform_fn receives the parsed list and may mutate it in place
def _fix_names(data):
    for item in data:
        item["name"] = " ".join(item["name"].split("_"))

ENDPOINTS = [
    ("players", "players.json",  None),
    ("towns",   "towns.json",    _fix_names),
    ("nations", "nations.json",  _fix_names),
    ("sieges",  "sieges.json",   None),
    ("shops",   "shopdata.json", None),   # raw bytes — shops.py handles decoding
]


def fetch_one(endpoint: str, filename: str, transform) -> bool:
    path = DATA_DIR / filename
    try:
        r = _http.get(f"{EARTHPOL}/{endpoint}", timeout=TIMEOUT)
        r.raise_for_status()

        # shops.py reads raw bytes via codecs.decode — write bytes directly
        if filename == "shopdata.json":
            tmp = path.with_suffix(".tmp")
            tmp.write_bytes(r.content)
            tmp.replace(path)
            print(f"[fetcher] {endpoint:10s} ✓  ({len(r.content)//1024} KB)", flush=True)
            return True

        data = r.json()
        if transform and isinstance(data, list):
            transform(data)

        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data), encoding="utf-8")
        tmp.replace(path)
        count = len(data) if isinstance(data, list) else "?"
        print(f"[fetcher] {endpoint:10s} ✓  ({count} items)", flush=True)
        return True

    except Exception as e:
        print(f"[fetcher] {endpoint:10s} ✗  {e}", flush=True)
        return False


print(f"[fetcher] Data fetcher started — writing to {DATA_DIR.resolve()}", flush=True)

while True:
    for endpoint, filename, transform in ENDPOINTS:
        fetch_one(endpoint, filename, transform)
        time.sleep(PAUSE)
