from flask import Blueprint, jsonify
import json, time, os, threading
import requests as reqs
from pathlib import Path

app = Blueprint("server_status", __name__)

_http = reqs.Session()
_http.headers.update({"User-Agent": "earthpol-web/1.0", "Accept": "application/json"})

DATA_DIR      = Path(os.environ.get("DATA_DIR", "data"))
HISTORY_FILE  = DATA_DIR / "server_history.json"
POLL_INTERVAL = 10      # seconds between pings
FLUSH_EVERY   = 6       # flush to disk every N polls (every ~60s)
MAX_ENTRIES   = 60480   # 7 days at 10s intervals
MC_API        = "https://api.mcsrvstat.us/3/play.earthpol.com"

_lock    = threading.Lock()
_history = []           # in-memory, loaded once at startup
_dirty   = False


# ── Disk I/O ───────────────────────────────────────────────────────

def _load_from_disk():
    try:
        return json.loads(HISTORY_FILE.read_bytes())
    except FileNotFoundError:
        return []
    except Exception:
        return []


def _flush_to_disk():
    with _lock:
        snapshot = list(_history)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    HISTORY_FILE.write_text(json.dumps(snapshot), encoding="utf-8")


# ── Fetch ──────────────────────────────────────────────────────────

def _fetch_status():
    r = _http.get(MC_API, timeout=8)
    r.raise_for_status()
    data    = r.json()
    online  = bool(data.get("online", False))
    players = data.get("players", {}).get("online", 0) if online else 0
    maximum = data.get("players", {}).get("max",    0) if online else 0
    return {"online": online, "players": players, "max": maximum}


# ── Background polling thread ──────────────────────────────────────

def _poll_loop():
    global _dirty
    flush_counter = 0
    while True:
        try:
            status = _fetch_status()
            entry  = {"ts": int(time.time() * 1000), **status}
            with _lock:
                _history.append(entry)
                if len(_history) > MAX_ENTRIES:
                    del _history[:len(_history) - MAX_ENTRIES]
                _dirty = True
            flush_counter += 1
            if flush_counter >= FLUSH_EVERY:
                _flush_to_disk()
                flush_counter = 0
        except Exception:
            pass
        time.sleep(POLL_INTERVAL)


# Load history from disk at import time
_history.extend(_load_from_disk())

# Start polling thread lazily on first request so it runs inside the
# gunicorn worker process (threads don't survive gunicorn's fork).
_poll_started = False
_start_lock   = threading.Lock()

@app.before_request
def _ensure_poll_thread():
    global _poll_started
    if not _poll_started:
        with _start_lock:
            if not _poll_started:
                threading.Thread(target=_poll_loop, daemon=True).start()
                _poll_started = True


# ── Routes ─────────────────────────────────────────────────────────

@app.route("/api/server-status/current")
def current():
    """Latest recorded entry, or live fetch if history is empty."""
    with _lock:
        if _history:
            return jsonify(_history[-1])
    try:
        return jsonify(_fetch_status())
    except Exception:
        return jsonify({"online": False, "players": 0, "max": 0})


@app.route("/api/server-status/history")
def history():
    with _lock:
        data = list(_history)
    return jsonify(data)


@app.route("/api/server-status/record")
def record():
    """Manual trigger — useful for testing."""
    try:
        status = _fetch_status()
    except Exception as e:
        return jsonify({"error": str(e)}), 502
    entry = {"ts": int(time.time() * 1000), **status}
    with _lock:
        _history.append(entry)
        if len(_history) > MAX_ENTRIES:
            del _history[:len(_history) - MAX_ENTRIES]
    _flush_to_disk()
    return jsonify(entry)
