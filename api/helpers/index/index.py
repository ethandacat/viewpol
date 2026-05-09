from flask import Blueprint, render_template, jsonify
import requests, time

app = Blueprint("index", __name__, template_folder="")

_stats_cache = None
_stats_ts    = 0.0
_STATS_TTL   = 120   # 2-minute cache

EARTHPOL = "https://api.earthpol.com/astra"
_http = requests.Session()
_http.headers.update({"User-Agent": "viewpol/1.0", "Accept": "application/json"})


def _fetch_stats():
    global _stats_cache, _stats_ts
    counts = {}
    for key in ("nations", "towns", "players", "shops", "sieges"):
        try:
            r = _http.get(f"{EARTHPOL}/{key}", timeout=10)
            r.raise_for_status()
            data = r.json()
            counts[key] = len(data) if isinstance(data, list) else 0
        except Exception:
            counts[key] = None
    _stats_cache = counts
    _stats_ts    = time.time()
    return counts


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/stats")
def stats():
    global _stats_cache, _stats_ts
    now = time.time()
    if _stats_cache is not None and now - _stats_ts < _STATS_TTL:
        return jsonify(_stats_cache)
    try:
        return jsonify(_fetch_stats())
    except Exception as e:
        return jsonify({"error": str(e)}), 502
