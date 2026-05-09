from flask import Blueprint, render_template, redirect
import requests as reqs
from ..helpers import itemstack
from ..helpers.cache import load, find

app = Blueprint("player", __name__, template_folder="")

_http = reqs.Session()
_http.headers.update({"User-Agent": "earthpol-web/1.0", "Accept": "application/json"})


def _normalize_shop_type(n):
    raw     = str(n.get("type", ""))
    cleaned = raw.split(".")[-1].split("@")[0].replace("Type", "").upper()
    if cleaned in ("SELLING", "BUYING"):
        return cleaned
    if "SellingType" in raw:
        return "SELLING"
    if "BuyingType" in raw:
        return "BUYING"
    return "UNKNOWN"


@app.route("/players/<identifier>")
def player(identifier):
    # ── Player data from disk cache ───────────────────────────────
    data = find(load("players.json", "players"), identifier)

    # If not found by name/uuid, try a live lookup (handles edge cases)
    if not data:
        req = _http.post("https://api.earthpol.com/astra/players",
                         json={"query": [identifier]}, timeout=10)
        if req.status_code != 200 or not req.json():
            return "", 404
        data = req.json()[0]

    data_uuid = data.get("uuid", "")
    if data_uuid and data_uuid != identifier:
        return redirect(f"/players/{data_uuid}", 301)

    # ── Shops still fetched live (per-player, not bulk-cacheable) ─
    uuid = data_uuid or identifier
    try:
        sreq      = _http.post("https://api.earthpol.com/astra/shops",
                               json={"query": [uuid]}, timeout=10)
        shops_raw = sreq.json() if sreq.status_code == 200 else []
    except Exception:
        shops_raw = []

    if shops_raw and isinstance(shops_raw[0], list):
        shops = shops_raw[0]
    else:
        shops = [s for s in shops_raw if isinstance(s, dict)]

    for n in shops:
        n["item"]       = itemstack.parse(n["item"])
        n["type"]       = _normalize_shop_type(n)
        qty             = n["item"]["amount"]
        n["unit_price"] = n["price"] / qty if qty else float("inf")

    shops.sort(key=lambda n: n["unit_price"])

    return render_template("player.html", data=data, shops=shops)
