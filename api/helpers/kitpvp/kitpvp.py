from flask import Blueprint, render_template, request
import requests as reqs
import time
from threading import Lock

app = Blueprint("kitpvp", __name__, template_folder="")

session = reqs.Session()
session.headers.update({
    "User-Agent": "earthpol-web/1.0",
    "Accept": "application/json",
})

ALL_SORTS = {"kills", "deaths", "assists", "damage", "damage_taken",
             "best_killstreak", "current_killstreak", "bow_shots", "bow_hits", "kd"}
PER_PAGE  = 50
CACHE_TTL = 300  # seconds

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
    sort  = request.args.get("sort", "kills")
    order = request.args.get("order", "desc")
    page  = max(1, int(request.args.get("page", 1)))

    if sort  not in ALL_SORTS:      sort  = "kills"
    if order not in ("asc", "desc"): order = "desc"

    players = _get_players()
    reverse = (order == "desc")
    sorted_players = sorted(players, key=lambda p: p.get(sort, 0), reverse=reverse)

    offset   = (page - 1) * PER_PAGE
    page_items = sorted_players[offset : offset + PER_PAGE]
    has_next   = offset + PER_PAGE < len(sorted_players)

    for i, p in enumerate(page_items):
        p["rank"] = offset + i + 1

    return render_template(
        "kitpvp.html",
        items=page_items,
        sort=sort,
        order=order,
        page=page,
        has_next=has_next,
    )
