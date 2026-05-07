from flask import Blueprint, render_template, jsonify
import requests as reqs
import time
from threading import Lock

app = Blueprint("kitpvp", __name__, template_folder="")

session = reqs.Session()
session.headers.update({
    "User-Agent": "earthpol-web/1.0",
    "Accept": "application/json",
})

CACHE_TTL = 300
_cache = {"players": [], "ts": 0}
_lock  = Lock()


def _fetch_all():
    players = []
    offset  = 0
    while True:
        resp = session.get(
            "https://earthpol.org/api/kitpvp/leaderboard",
            params={"sort": "kills", "order": "desc", "limit": 100, "offset": offset},
            timeout=10,
        )
        data  = resp.json()
        items = data.get("items", [])
        players.extend(items)
        if not items or not data.get("nextCursor"):
            break
        offset += 100
    for p in players:
        d       = p.get("deaths", 0)
        p["kd"] = round(p["kills"] / d, 2) if d else float(p["kills"])
    return players


def _get_players():
    with _lock:
        if time.time() - _cache["ts"] > CACHE_TTL:
            _cache["players"] = _fetch_all()
            _cache["ts"]      = time.time()
        return _cache["players"]


@app.route("/kitpvp")
def kitpvp_page():
    return render_template("kitpvp.html")


@app.route("/kitpvp/data")
def kitpvp_data():
    return jsonify(_get_players())
