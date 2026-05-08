from flask import Blueprint, jsonify
import json, time, os
import requests as reqs
from pathlib import Path

app = Blueprint("server_status", __name__)

_http = reqs.Session()
_http.headers.update({"User-Agent": "earthpol-web/1.0", "Accept": "application/json"})

DATA_DIR     = Path(os.environ.get("DATA_DIR", "data"))
HISTORY_FILE = DATA_DIR / "server_history.json"
MC_API       = "https://api.mcsrvstat.us/3/play.earthpol.com"


def _load_history():
    try:
        return json.loads(HISTORY_FILE.read_bytes())
    except FileNotFoundError:
        return []
    except Exception:
        return []


def _fetch_status():
    r = _http.get(MC_API, timeout=8)
    r.raise_for_status()
    data    = r.json()
    online  = bool(data.get("online", False))
    players = data.get("players", {}).get("online", 0) if online else 0
    maximum = data.get("players", {}).get("max",    0) if online else 0
    return {"online": online, "players": players, "max": maximum}


@app.route("/api/server-status/current")
def current():
    """Latest entry from history, or live fetch if history is empty."""
    history = _load_history()
    if history:
        return jsonify(history[-1])
    try:
        return jsonify(_fetch_status())
    except Exception:
        return jsonify({"online": False, "players": 0, "max": 0})


@app.route("/api/server-status/history")
def history():
    return jsonify(_load_history())


@app.route("/api/server-status/record")
def record():
    """Manual trigger for testing."""
    try:
        status = _fetch_status()
    except Exception as e:
        return jsonify({"error": str(e)}), 502
    entry   = {"ts": int(time.time() * 1000), **status}
    history = _load_history()
    history.append(entry)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    HISTORY_FILE.write_text(json.dumps(history), encoding="utf-8")
    return jsonify(entry)
