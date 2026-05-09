#!/usr/bin/env python3
"""Hourly history poller — records balance & stats snapshots to SQLite.

Reads players/towns/nations/shops from the disk files that data_fetcher.py
keeps fresh rather than making its own live API calls. This eliminates
4 large HTTP responses per hour from this process, reducing peak RAM.

Falls back to a live fetch only if the disk file is missing or >2h stale.
KitPvP is still fetched live (no disk cache for it).
"""

import json, time, os, sqlite3, gc, requests
from pathlib import Path

try:
    import ctypes
    _libc = ctypes.cdll.LoadLibrary("libc.so.6")
    def _trim(): _libc.malloc_trim(0)
except Exception:
    def _trim(): pass

DATA_DIR  = Path(os.environ.get("DATA_DIR", "data"))
DB_PATH   = DATA_DIR / "history.db"
MAX_ROWS  = 168          # 7 days at 1h intervals per entity
INTERVAL  = 3600         # seconds
EARTHPOL  = "https://api.earthpol.com/astra"
KITPVP_LB = "https://earthpol.org/api/kitpvp/leaderboard"
STALE_SEC = 7200         # fall back to live fetch if disk file is >2h old

_http = requests.Session()
_http.headers.update({"User-Agent": "viewpol/1.0", "Accept": "application/json"})


# ── DB setup ──────────────────────────────────────────────────────────

def open_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")
    con.executescript("""
        CREATE TABLE IF NOT EXISTS player_balance (
            uuid TEXT NOT NULL, ts INTEGER NOT NULL, balance REAL NOT NULL,
            PRIMARY KEY (uuid, ts));
        CREATE TABLE IF NOT EXISTS town_balance (
            uuid TEXT NOT NULL, ts INTEGER NOT NULL, balance REAL NOT NULL,
            PRIMARY KEY (uuid, ts));
        CREATE TABLE IF NOT EXISTS nation_balance (
            uuid TEXT NOT NULL, ts INTEGER NOT NULL, balance REAL NOT NULL,
            PRIMARY KEY (uuid, ts));
        CREATE TABLE IF NOT EXISTS item_price (
            item_id TEXT NOT NULL, ts INTEGER NOT NULL,
            best_sell REAL, best_buy REAL,
            PRIMARY KEY (item_id, ts));
        CREATE TABLE IF NOT EXISTS kitpvp_stats (
            uuid TEXT NOT NULL, ts INTEGER NOT NULL,
            kills INTEGER, deaths INTEGER, assists INTEGER,
            PRIMARY KEY (uuid, ts));
    """)
    con.commit()
    return con


def prune(con: sqlite3.Connection, table: str, uuid_col: str, ts: int):
    con.execute(f"""
        DELETE FROM {table}
        WHERE rowid IN (
            SELECT rowid FROM (
                SELECT rowid,
                       ROW_NUMBER() OVER (PARTITION BY {uuid_col} ORDER BY ts DESC) AS rn
                FROM {table}
            ) WHERE rn > {MAX_ROWS}
        )
    """)


# ── Disk-first loader ─────────────────────────────────────────────────

def _load(filename: str, fallback_url: str) -> list:
    """Read from data_fetcher's disk file. Only hits the API if file is missing
    or older than STALE_SEC (means data_fetcher isn't running)."""
    path = DATA_DIR / filename
    try:
        if path.exists() and time.time() - path.stat().st_mtime < STALE_SEC:
            return json.loads(path.read_bytes())
    except Exception:
        pass
    print(f"  [warn] {filename} stale/missing — falling back to live fetch", flush=True)
    try:
        r = _http.get(fallback_url, timeout=20)
        data = r.json()
        r.close()
        return data
    except Exception as e:
        print(f"  [error] live fetch {fallback_url}: {e}", flush=True)
        return []


# ── Pollers ───────────────────────────────────────────────────────────

def poll_players(con: sqlite3.Connection, ts: int):
    try:
        data = _load("players.json", f"{EARTHPOL}/players")
        rows = [
            (p["uuid"], ts, float(p.get("stats", {}).get("balance") or 0))
            for p in data if p.get("uuid")
        ]
        del data
        con.executemany("INSERT OR IGNORE INTO player_balance VALUES (?,?,?)", rows)
        prune(con, "player_balance", "uuid", ts)
        con.commit()
        print(f"  players:  {len(rows)}", flush=True)
    except Exception as e:
        print(f"  players error: {e}", flush=True)


def poll_towns(con: sqlite3.Connection, ts: int):
    try:
        data = _load("towns.json", f"{EARTHPOL}/towns")
        rows = [
            (t["uuid"], ts, float(t.get("stats", {}).get("balance") or 0))
            for t in data if t.get("uuid")
        ]
        del data
        con.executemany("INSERT OR IGNORE INTO town_balance VALUES (?,?,?)", rows)
        prune(con, "town_balance", "uuid", ts)
        con.commit()
        print(f"  towns:    {len(rows)}", flush=True)
    except Exception as e:
        print(f"  towns error: {e}", flush=True)


def poll_nations(con: sqlite3.Connection, ts: int):
    try:
        data = _load("nations.json", f"{EARTHPOL}/nations")
        rows = [
            (n["uuid"], ts, float(n.get("stats", {}).get("balance") or 0))
            for n in data if n.get("uuid")
        ]
        del data
        con.executemany("INSERT OR IGNORE INTO nation_balance VALUES (?,?,?)", rows)
        prune(con, "nation_balance", "uuid", ts)
        con.commit()
        print(f"  nations:  {len(rows)}", flush=True)
    except Exception as e:
        print(f"  nations error: {e}", flush=True)


def poll_items(con: sqlite3.Connection, ts: int):
    try:
        # shopdata.json is raw bytes written by shops.py — parse directly
        path = DATA_DIR / "shopdata.json"
        if path.exists() and time.time() - path.stat().st_mtime < STALE_SEC:
            data = json.loads(path.read_bytes())
        else:
            print("  [warn] shopdata.json stale/missing — falling back to live fetch", flush=True)
            r = _http.get(f"{EARTHPOL}/shops", timeout=30)
            data = r.json()
            r.close()

        sell: dict = {}
        buy:  dict = {}
        for s in data:
            item   = s.get("item") or {}
            # item may be a raw string (unparsed) or a dict
            if isinstance(item, str):
                # minimal parse: extract base item name between quotes
                import re
                m = re.search(r'"item"\s*:\s*"([^"]+)"', item)
                base = m.group(1).lower() if m else ""
            else:
                base = (item.get("item") or "").lower()
            if not base:
                continue
            price  = float(s.get("price") or 0)
            amount = int((item if isinstance(item, dict) else {}).get("amount") or 1) or 1
            unit   = price / amount
            stype  = (s.get("type") or "")
            # normalise type string
            stype  = stype.split(".")[-1].split("@")[0].replace("Type", "").upper()
            stock  = int(s.get("stock") or 0)
            space  = int(s.get("space") or 0)
            if stype == "SELLING" and stock > 0:
                if base not in sell or unit < sell[base]:
                    sell[base] = unit
            elif stype == "BUYING" and space > 0:
                if base not in buy or unit > buy[base]:
                    buy[base] = unit

        del data
        all_ids = set(sell) | set(buy)
        rows = [(item_id, ts, sell.get(item_id), buy.get(item_id)) for item_id in all_ids]
        con.executemany("INSERT OR IGNORE INTO item_price VALUES (?,?,?,?)", rows)
        prune(con, "item_price", "item_id", ts)
        con.commit()
        print(f"  items:    {len(rows)}", flush=True)
    except Exception as e:
        print(f"  items error: {e}", flush=True)


def poll_kitpvp(con: sqlite3.Connection, ts: int):
    # KitPvP has no disk cache — must fetch live
    try:
        rows: list = []
        params: dict = {"sort": "kills", "order": "desc", "limit": 100}
        while True:
            r      = _http.get(KITPVP_LB, params=params, timeout=10)
            data   = r.json()
            r.close()
            items  = data.get("items", [])
            for p in items:
                uuid = p.get("uuid")
                if uuid:
                    rows.append((uuid, ts,
                                 int(p.get("kills")   or 0),
                                 int(p.get("deaths")  or 0),
                                 int(p.get("assists") or 0)))
            cursor = data.get("nextCursor")
            if not cursor:
                break
            params["cursorValue"] = cursor.get("value")
            params["cursorUuid"]  = cursor.get("uuid")
        con.executemany("INSERT OR IGNORE INTO kitpvp_stats VALUES (?,?,?,?,?)", rows)
        prune(con, "kitpvp_stats", "uuid", ts)
        con.commit()
        print(f"  kitpvp:   {len(rows)}", flush=True)
    except Exception as e:
        print(f"  kitpvp error: {e}", flush=True)


# ── Main loop ─────────────────────────────────────────────────────────

print(f"History poller started — DB: {DB_PATH.resolve()}", flush=True)
con = open_db()

while True:
    ts = int(time.time() * 1000)
    print(f"[{time.strftime('%H:%M:%S')}] Polling…", flush=True)
    poll_players(con, ts)
    poll_towns(con, ts)
    poll_nations(con, ts)
    poll_items(con, ts)
    poll_kitpvp(con, ts)
    print(f"[{time.strftime('%H:%M:%S')}] Done. Next poll in {INTERVAL//60} min.", flush=True)
    gc.collect()
    _trim()
    time.sleep(INTERVAL)
