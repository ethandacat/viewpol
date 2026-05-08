from flask import Blueprint, render_template, redirect
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


@app.route("/players/<identifier>")
def player(identifier):
    req = requests.post("https://api.earthpol.com/astra/players", json={"query": [identifier]})
    if req.status_code != 200 or len(req.json()) == 0:
        return "", 404
    data_uuid = req.json()[0].get("uuid", "")
    if data_uuid and data_uuid != identifier:
        return redirect(f"/players/{data_uuid}", 301)

    uuid = data_uuid
    sreq = requests.post("https://api.earthpol.com/astra/shops", json={"query": [uuid]})
    shops_raw = sreq.json() if sreq.status_code == 200 else []
    # API may return [[...]] when queried by UUID
    if shops_raw and isinstance(shops_raw[0], list):
        shops = shops_raw[0]
    else:
        shops = [s for s in shops_raw if isinstance(s, dict)]

    for n in shops:
        n["item"] = itemstack.parse(n["item"])
        n["type"] = _normalize_shop_type(n)
        qty = n["item"]["amount"]
        n["unit_price"] = n["price"] / qty if qty else float("inf")

    shops.sort(key=lambda n: n["unit_price"])

    return render_template("player.html", data=req.json()[0], shops=shops)