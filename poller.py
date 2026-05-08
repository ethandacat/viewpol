#!/usr/bin/env python3
"""Standalone EarthPol server status poller. Run independently of the web app.
   Usage: nohup python3 poller.py &"""

import json, time, sys, os, requests
from pathlib import Path

DATA_FILE   = Path(os.environ.get("DATA_DIR", "data")) / "server_history.json"
MAX_ENTRIES = 60480   # 7 days at 10s intervals
INTERVAL    = 10      # seconds
MC_API      = "https://api.mcsrvstat.us/3/play.earthpol.com"

session = requests.Session()
session.headers.update({"User-Agent": "earthpol-web/1.0"})

print(f"Poller started — writing to {DATA_FILE.resolve()}", flush=True)

while True:
    try:
        r    = session.get(MC_API, timeout=8)
        data = r.json()
        online  = bool(data.get("online", False))
        players = data.get("players", {}).get("online", 0) if online else 0
        maximum = data.get("players", {}).get("max",    0) if online else 0
        entry = {"ts": int(time.time() * 1000), "online": online,
                 "players": players, "max": maximum}

        try:
            history = json.loads(DATA_FILE.read_bytes())
        except Exception:
            history = []

        history.append(entry)
        if len(history) > MAX_ENTRIES:
            history = history[-MAX_ENTRIES:]

        DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        DATA_FILE.write_text(json.dumps(history), encoding="utf-8")
        print(f"[{time.strftime('%H:%M:%S')}] {'online' if online else 'offline'} — {players} players", flush=True)

    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] Error: {e}", flush=True)

    time.sleep(INTERVAL)
