from flask import Blueprint, jsonify
import json, time, os
import requests as reqs
import vercel_blob as vb

app = Blueprint("server_status", __name__)

_http = reqs.Session()
_http.headers.update({"User-Agent": "earthpol-web/1.0", "Accept": "application/json"})

HISTORY_KEY = "server_history.json"
MAX_ENTRIES = 2016   # 7 days at 5-min intervals
MC_API      = "https://api.mcsrvstat.us/3/play.earthpol.com"

_blob_url: str | None = None


# ── Blob helpers ───────────────────────────────────────────────────

def _load_history():
    global _blob_url
    nc = {"Cache-Control": "no-cache", "Pragma": "no-cache"}
    if _blob_url:
        try:
            r = _http.get(_blob_url, headers=nc)
            if r.status_code == 200:
                return json.loads(r.content)
        except Exception:
            pass
        _blob_url = None
    try:
        result = vb.list(options={"prefix": HISTORY_KEY, "limit": "1"})
        blobs = (result or {}).get("blobs") or []
        if not blobs:
            return []
        url = blobs[0].get("downloadUrl") or blobs[0].get("url", "")
        r = _http.get(url, headers=nc)
        r.raise_for_status()
        _blob_url = url
        return json.loads(r.content)
    except Exception:
        return []


def _save_history(history):
    global _blob_url
    result = vb.put(
        HISTORY_KEY,
        json.dumps(history).encode(),
        options={"allowOverwrite": "true", "addRandomSuffix": "false"},
    )
    _blob_url = result.get("url") or result.get("downloadUrl") or _blob_url


# ── Fetch from mcsrvstat ───────────────────────────────────────────

def _fetch_status():
    r = _http.get(MC_API, timeout=8)
    r.raise_for_status()
    data = r.json()
    online  = bool(data.get("online", False))
    players = data.get("players", {}).get("online", 0) if online else 0
    maximum = data.get("players", {}).get("max",    0) if online else 0
    return {"online": online, "players": players, "max": maximum}


# ── Routes ─────────────────────────────────────────────────────────

@app.route("/api/server-status/record")
def record():
    """Fetch current status and append to history (called by Vercel Cron)."""
    try:
        status = _fetch_status()
    except Exception as e:
        return jsonify({"error": str(e)}), 502

    entry = {"ts": int(time.time() * 1000), **status}

    history = _load_history()
    history.append(entry)
    if len(history) > MAX_ENTRIES:
        history = history[-MAX_ENTRIES:]
    _save_history(history)

    return jsonify(entry)


@app.route("/api/server-status/current")
def current():
    """Live proxy to mcsrvstat — no storage."""
    try:
        return jsonify(_fetch_status())
    except Exception:
        return jsonify({"online": False, "players": 0, "max": 0})


@app.route("/api/server-status/history")
def history():
    """Return full stored history array."""
    return jsonify(_load_history())
