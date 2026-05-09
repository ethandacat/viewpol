#!/usr/bin/env python3
"""
ViewPol data fetcher — keeps EarthPol API data fresh on disk.

Fetches one endpoint at a time with a short pause between each.
Flask handlers read from these local files via LookupCache (mtime-gated,
one copy in memory) so pages never wait on a live API call.

NOTE: shops are intentionally excluded here — shops.py manages its own
      disk cache (shopdata.json) with a 300s TTL.

Files written to DATA_DIR (default: ./data/):
  players.json  towns.json  nations.json  sieges.json
"""

import json, gc, time, os, requests
from pathlib import Path

DATA_DIR = Path(os.environ.get("DATA_DIR", "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

EARTHPOL = "https://api.earthpol.com/astra"
PAUSE    = 5      # seconds between each individual fetch
TIMEOUT  = 20     # seconds before giving up on one request

_http = requests.Session()
_http.headers.update({"User-Agent": "viewpol/1.0", "Accept": "application/json"})

# Register malloc_trim as a GC callback — fires automatically after every
# collection cycle, returning freed heap pages to the OS on Linux.
try:
    import ctypes
    _libc = ctypes.cdll.LoadLibrary("libc.so.6")
    def _gc_callback(phase, info):
        if phase == "stop":
            _libc.malloc_trim(0)
    gc.callbacks.append(_gc_callback)
except Exception:
    pass


def _fix_names(data: list):
    for item in data:
        item["name"] = " ".join(item["name"].split("_"))


ENDPOINTS = [
    ("players", "players.json",  None),
    ("towns",   "towns.json",    _fix_names),
    ("nations", "nations.json",  _fix_names),
    ("sieges",  "sieges.json",   None),
]


def fetch_one(endpoint: str, filename: str, transform) -> bool:
    path = DATA_DIR / filename
    try:
        r = _http.get(f"{EARTHPOL}/{endpoint}", timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json()
        r.close()                           # release urllib3 connection promptly

        if transform and isinstance(data, list):
            transform(data)

        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data), encoding="utf-8")
        tmp.replace(path)

        count = len(data) if isinstance(data, list) else "?"
        print(f"[fetcher] {endpoint:10s} ✓  ({count} items)", flush=True)
        del data                            # help GC before sleep
        return True

    except Exception as e:
        print(f"[fetcher] {endpoint:10s} ✗  {e}", flush=True)
        return False


print(f"[fetcher] Started — writing to {DATA_DIR.resolve()}", flush=True)

while True:
    for endpoint, filename, transform in ENDPOINTS:
        fetch_one(endpoint, filename, transform)
        time.sleep(PAUSE)

