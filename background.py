#!/usr/bin/env python3
"""
ViewPol background worker — all polling tasks in one process, each on its
own thread. Replaces the three separate data_fetcher / poller /
history_poller processes, saving two full Python interpreter instances.

  Thread 1 — data_fetcher  : keeps players/towns/nations/sieges fresh on disk
  Thread 2 — status_poller : server online/player-count, every 60 s
  Thread 3 — history_poller: balance/price/KitPvP snapshots to SQLite, every 1 h
"""

import gc, json, re, sqlite3, time, os, requests, threading
from pathlib import Path

try:
    import ctypes
    _libc = ctypes.cdll.LoadLibrary("libc.so.6")
    def _gc_callback(phase, info):
        if phase == "stop":
            _libc.malloc_trim(0)
    if _gc_callback not in gc.callbacks:
        gc.callbacks.append(_gc_callback)
except Exception:
    pass

DATA_DIR = Path(os.environ.get("DATA_DIR", "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

EARTHPOL  = "https://api.earthpol.com/astra"
KITPVP_LB = "https://earthpol.org/api/kitpvp/leaderboard"
MC_API    = "https://api.mcsrvstat.us/3/play.earthpol.com"

DB_PATH   = DATA_DIR / "history.db"
HIST_FILE = DATA_DIR / "server_history.json"

MAX_HIST_ENTRIES = 10080   # 7 days × 1 min
MAX_DB_ROWS      = 168     # 7 days × 1 h
STALE_SEC        = 7200

_HEADERS = {"User-Agent": "viewpol/1.0", "Accept": "application/json"}

def _new_session() -> requests.Session:
    """Each thread gets its own Session — requests.Session is not thread-safe."""
    s = requests.Session()
    s.headers.update(_HEADERS)
    return s


# ── SQLite ────────────────────────────────────────────────────────────────────

def _open_db() -> sqlite3.Connection:
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


def _prune(con, table, uuid_col):
    con.execute(f"""
        DELETE FROM {table} WHERE rowid IN (
            SELECT rowid FROM (
                SELECT rowid,
                       ROW_NUMBER() OVER (PARTITION BY {uuid_col} ORDER BY ts DESC) rn
                FROM {table}
            ) WHERE rn > {MAX_DB_ROWS}
        )
    """)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_disk(filename, fallback_url, http):
    path = DATA_DIR / filename
    try:
        if path.exists() and time.time() - path.stat().st_mtime < STALE_SEC:
            return json.loads(path.read_bytes())
    except Exception:
        pass
    print(f"[bg] {filename} stale — live fetch", flush=True)
    try:
        r = http.get(fallback_url, timeout=20)
        data = r.json(); r.close(); return data
    except Exception as e:
        print(f"[bg] live fetch error {fallback_url}: {e}", flush=True)
        return []


def _balance_rows(data, ts):
    rows = []
    for item in data:
        uuid  = item.get("uuid")
        stats = item.get("stats")
        if not uuid or stats is None:
            continue
        bal = stats.get("balance")
        if bal is not None:
            rows.append((uuid, ts, float(bal)))
    return rows


# ── Thread 1: data fetcher ────────────────────────────────────────────────────

def _fix_names(data):
    for item in data:
        item["name"] = " ".join(item["name"].split("_"))

ENDPOINTS = [
    ("players", "players.json",  None),
    ("towns",   "towns.json",    _fix_names),
    ("nations", "nations.json",  _fix_names),
    ("sieges",  "sieges.json",   None),
]

def _run_data_fetcher():
    http = _new_session()
    print("[bg/fetcher] started", flush=True)
    while True:
        for endpoint, filename, transform in ENDPOINTS:
            path = DATA_DIR / filename
            try:
                r = http.get(f"{EARTHPOL}/{endpoint}", timeout=20)
                r.raise_for_status()
                raw = r.content; r.close()
                if transform:
                    # Parse only when a transform is needed (towns/nations name fix)
                    data = json.loads(raw); del raw
                    if isinstance(data, list):
                        transform(data)
                    raw = json.dumps(data).encode(); del data
                tmp = path.with_suffix(".tmp")
                tmp.write_bytes(raw); del raw
                tmp.replace(path)
                print(f"[bg/fetcher] {endpoint} ✓", flush=True)
            except Exception as e:
                print(f"[bg/fetcher] {endpoint} ✗ {e}", flush=True)
            time.sleep(5)
        gc.collect()


# ── Thread 2: server status poller ───────────────────────────────────────────

def _run_status_poller():
    http = _new_session()
    # Load history once into memory — append in place to avoid repeated alloc/free
    try:
        history = json.loads(HIST_FILE.read_bytes())
    except Exception:
        history = []
    print("[bg/status] started", flush=True)
    while True:
        try:
            r    = http.get(MC_API, timeout=8)
            data = r.json(); r.close()
            online  = bool(data.get("online", False))
            players = data.get("players", {}).get("online", 0) if online else 0
            maximum = data.get("players", {}).get("max",    0) if online else 0
            history.append({"ts": int(time.time() * 1000), "online": online,
                            "players": players, "max": maximum})
            if len(history) > MAX_HIST_ENTRIES:
                del history[:-MAX_HIST_ENTRIES]   # trim in place, no new list
            HIST_FILE.write_text(json.dumps(history), encoding="utf-8")
            print(f"[bg/status] {'online' if online else 'offline'} — {players} players", flush=True)
        except Exception as e:
            print(f"[bg/status] error: {e}", flush=True)
        time.sleep(60)


# ── Thread 3: history poller ──────────────────────────────────────────────────

def _run_history_poller(con):
    http = _new_session()
    print("[bg/history] started", flush=True)
    while True:
        ts = int(time.time() * 1000)
        print(f"[bg/history] polling…", flush=True)

        # Balance snapshots
        for filename, url, table in [
            ("players.json", f"{EARTHPOL}/players", "player_balance"),
            ("towns.json",   f"{EARTHPOL}/towns",   "town_balance"),
            ("nations.json", f"{EARTHPOL}/nations",  "nation_balance"),
        ]:
            try:
                rows = _balance_rows(_load_disk(filename, url, http), ts)
                con.executemany(f"INSERT OR IGNORE INTO {table} VALUES (?,?,?)", rows)
                _prune(con, table, "uuid")
                con.commit()
                print(f"[bg/history] {table}: {len(rows)}", flush=True)
            except Exception as e:
                print(f"[bg/history] {table} error: {e}", flush=True)

        # Item prices
        try:
            path = DATA_DIR / "shopdata.json"
            if path.exists() and time.time() - path.stat().st_mtime < STALE_SEC:
                data = json.loads(path.read_bytes())
            else:
                r = http.get(f"{EARTHPOL}/shops", timeout=30)
                data = r.json(); r.close()

            sell_active: dict = {}; sell_inactive: dict = {}
            buy_active:  dict = {}; buy_inactive:  dict = {}
            for s in data:
                item  = s.get("item") or {}
                if isinstance(item, str):
                    m = re.search(r'"item"\s*:\s*"([^"]+)"', item)
                    base = m.group(1).lower() if m else ""
                else:
                    base = (item.get("item") or "").lower()
                if not base: continue
                price  = float(s.get("price") or 0)
                amount = int((item if isinstance(item, dict) else {}).get("amount") or 1) or 1
                unit   = price / amount
                stype  = (s.get("type") or "").split(".")[-1].split("@")[0].replace("Type", "").upper()
                stock  = int(s.get("stock") or 0)
                space  = int(s.get("space") or 0)
                if stype == "SELLING":
                    b = sell_active if stock > 0 else sell_inactive
                    if base not in b or unit < b[base]: b[base] = unit
                elif stype == "BUYING":
                    b = buy_active if space > 0 else buy_inactive
                    if base not in b or unit > b[base]: b[base] = unit
            del data
            sell = {**sell_inactive, **sell_active}
            buy  = {**buy_inactive,  **buy_active}
            rows = [(k, ts, sell.get(k), buy.get(k)) for k in set(sell) | set(buy)]
            con.executemany("INSERT OR IGNORE INTO item_price VALUES (?,?,?,?)", rows)
            _prune(con, "item_price", "item_id")
            con.commit()
            print(f"[bg/history] item_price: {len(rows)}", flush=True)
        except Exception as e:
            print(f"[bg/history] item_price error: {e}", flush=True)

        # KitPvP
        try:
            rows = []
            params = {"sort": "kills", "order": "desc", "limit": 100}
            while True:
                r    = http.get(KITPVP_LB, params=params, timeout=10)
                data = r.json(); r.close()
                for p in data.get("items", []):
                    uuid = p.get("uuid")
                    if uuid:
                        rows.append((uuid, ts, int(p.get("kills") or 0),
                                     int(p.get("deaths") or 0), int(p.get("assists") or 0)))
                cursor = data.get("nextCursor")
                if not cursor: break
                params["cursorValue"] = cursor.get("value")
                params["cursorUuid"]  = cursor.get("uuid")
            con.executemany("INSERT OR IGNORE INTO kitpvp_stats VALUES (?,?,?,?,?)", rows)
            _prune(con, "kitpvp_stats", "uuid")
            con.commit()
            print(f"[bg/history] kitpvp_stats: {len(rows)}", flush=True)
        except Exception as e:
            print(f"[bg/history] kitpvp error: {e}", flush=True)

        # Explicitly free all large locals before the 1-hour sleep so the
        # OS can reclaim those pages rather than holding them for an hour.
        try:
            del sell_active, sell_inactive, buy_active, buy_inactive, sell, buy
        except NameError:
            pass
        try:
            del rows
        except NameError:
            pass
        print(f"[bg/history] done. next in 1h.", flush=True)
        gc.collect()
        time.sleep(3600)


# ── Main ──────────────────────────────────────────────────────────────────────

print(f"[bg] ViewPol background worker starting — data: {DATA_DIR.resolve()}", flush=True)

con = _open_db()

for fn, kwargs in [
    (_run_data_fetcher,  {}),
    (_run_status_poller, {}),
    (_run_history_poller, {"con": con}),
]:
    t = threading.Thread(target=fn, kwargs=kwargs, daemon=True)
    t.start()

# Keep main thread alive — daemon threads die with the process
threading.Event().wait()
