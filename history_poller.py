#!/usr/bin/env python3
"""Hourly history poller — records balance & stats snapshots to SQLite.

Never holds data in RAM beyond one poll cycle.

Usage:
    sudo bash -c 'cd /opt/hosted-sites/viewpol && nohup python3 history_poller.py >> /tmp/hist_poller.log 2>&1 &'
"""

import json, time, os, sqlite3, requests
from pathlib import Path

DATA_DIR  = Path(os.environ.get("DATA_DIR", "data"))
DB_PATH   = DATA_DIR / "history.db"
MAX_ROWS  = 168          # 7 days at 1h intervals per entity
INTERVAL  = 3600         # seconds
EARTHPOL  = "https://api.earthpol.com/astra"
KITPVP_LB = "https://earthpol.org/api/kitpvp/leaderboard"

_http = requests.Session()
_http.headers.update({"User-Agent": "viewpol/1.0", "Accept": "application/json"})


# ── DB setup ──────────────────────────────────────────────────────

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
    """Keep only the latest MAX_ROWS rows per entity."""
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


# ── Pollers ───────────────────────────────────────────────────────

def poll_players(con: sqlite3.Connection, ts: int):
    try:
        data = _http.get(f"{EARTHPOL}/players", timeout=20).json()
        rows = [
            (p["uuid"], ts, float(p.get("stats", {}).get("balance") or 0))
            for p in data if p.get("uuid")
        ]
        con.executemany(
            "INSERT OR IGNORE INTO player_balance VALUES (?,?,?)", rows)
        prune(con, "player_balance", "uuid", ts)
        con.commit()
        print(f"  players:  {len(rows)}", flush=True)
    except Exception as e:
        print(f"  players error: {e}", flush=True)


def poll_towns(con: sqlite3.Connection, ts: int):
    try:
        data = _http.get(f"{EARTHPOL}/towns", timeout=20).json()
        rows = [
            (t["uuid"], ts, float(t.get("stats", {}).get("balance") or 0))
            for t in data if t.get("uuid")
        ]
        con.executemany(
            "INSERT OR IGNORE INTO town_balance VALUES (?,?,?)", rows)
        prune(con, "town_balance", "uuid", ts)
        con.commit()
        print(f"  towns:    {len(rows)}", flush=True)
    except Exception as e:
        print(f"  towns error: {e}", flush=True)


def poll_nations(con: sqlite3.Connection, ts: int):
    try:
        data = _http.get(f"{EARTHPOL}/nations", timeout=20).json()
        rows = [
            (n["uuid"], ts, float(n.get("stats", {}).get("balance") or 0))
            for n in data if n.get("uuid")
        ]
        con.executemany(
            "INSERT OR IGNORE INTO nation_balance VALUES (?,?,?)", rows)
        prune(con, "nation_balance", "uuid", ts)
        con.commit()
        print(f"  nations:  {len(rows)}", flush=True)
    except Exception as e:
        print(f"  nations error: {e}", flush=True)


def poll_items(con: sqlite3.Connection, ts: int):
    try:
        data  = _http.get(f"{EARTHPOL}/shops", timeout=30).json()
        sell: dict = {}   # item_id → min unit_price (best sell = cheapest)
        buy:  dict = {}   # item_id → max unit_price (best buy = highest)

        for s in data:
            item   = s.get("item") or {}
            base   = (item.get("item") or "").lower()
            if not base:
                continue
            price  = float(s.get("price") or 0)
            amount = int(item.get("amount") or 1) or 1
            unit   = price / amount
            stype  = s.get("type", "")
            stock  = int(s.get("stock") or 0)
            space  = int(s.get("space") or 0)

            if stype == "SELLING" and stock > 0:
                if base not in sell or unit < sell[base]:
                    sell[base] = unit
            elif stype == "BUYING" and space > 0:
                if base not in buy or unit > buy[base]:
                    buy[base] = unit

        all_ids = set(sell) | set(buy)
        rows = [
            (item_id, ts, sell.get(item_id), buy.get(item_id))
            for item_id in all_ids
        ]
        con.executemany(
            "INSERT OR IGNORE INTO item_price VALUES (?,?,?,?)", rows)
        prune(con, "item_price", "item_id", ts)
        con.commit()
        print(f"  items:    {len(rows)}", flush=True)
    except Exception as e:
        print(f"  items error: {e}", flush=True)


def poll_kitpvp(con: sqlite3.Connection, ts: int):
    try:
        rows  = []
        params: dict = {"sort": "kills", "order": "desc", "limit": 100}
        while True:
            data   = _http.get(KITPVP_LB, params=params, timeout=10).json()
            items  = data.get("items", [])
            for p in items:
                uuid = p.get("uuid")
                if uuid:
                    rows.append((
                        uuid, ts,
                        int(p.get("kills")   or 0),
                        int(p.get("deaths")  or 0),
                        int(p.get("assists") or 0),
                    ))
            cursor = data.get("nextCursor")
            if not cursor:
                break
            params["cursorValue"] = cursor.get("value")
            params["cursorUuid"]  = cursor.get("uuid")
        con.executemany(
            "INSERT OR IGNORE INTO kitpvp_stats VALUES (?,?,?,?,?)", rows)
        prune(con, "kitpvp_stats", "uuid", ts)
        con.commit()
        print(f"  kitpvp:   {len(rows)}", flush=True)
    except Exception as e:
        print(f"  kitpvp error: {e}", flush=True)


# ── Main loop ─────────────────────────────────────────────────────

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
    time.sleep(INTERVAL)
