from flask import Blueprint, render_template
import requests as reqs
from ..helpers import itemstack

app = Blueprint("player", __name__, template_folder="")

requests = reqs.Session()
requests.headers.update({
    "User-Agent": "earthpol-web/1.0",
    "Accept": "application/json",
})


def _normalize_shop_type(n):
    raw = str(n.get("type", ""))
    cleaned = raw.split(".")[-1].split("@")[0].replace("Type", "").upper()
    if cleaned in ("SELLING", "BUYING"):
        return cleaned
    if "SellingType" in raw:
        return "SELLING"
    if "BuyingType" in raw:
        return "BUYING"
    return "UNKNOWN"


@app.route("/players/<uuid>")
def player(uuid):
    req = requests.post("https://api.earthpol.com/astra/players", json={"query": [uuid]})
    if req.status_code != 200 or len(req.json()) == 0:
        return "", 404
    return render_template("player.html", data=req.json()[0])


@app.route("/players/<uuid>/shops")
def player_shops(uuid):
    preq = requests.post("https://api.earthpol.com/astra/players", json={"query": [uuid]})
    if preq.status_code != 200 or len(preq.json()) == 0:
        return "", 404
    player_data = preq.json()[0]

    sreq = requests.post("https://api.earthpol.com/astra/shops", json={"query": [uuid]})
    shops = sreq.json() if sreq.status_code == 200 else []

    for n in shops:
        n["item"] = itemstack.parse(n["item"])
        n["type"] = _normalize_shop_type(n)
        qty = n["item"]["amount"]
        n["unit_price"] = n["price"] / qty if qty else float("inf")

    shops.sort(key=lambda n: n["unit_price"])

    return render_template("player_shops.html", player=player_data, shops=shops)