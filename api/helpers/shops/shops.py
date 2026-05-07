from flask import Blueprint, render_template, request, jsonify
import requests as reqs
from datetime import datetime, timedelta, UTC
import vercel_blob as vb
import json
from codecs import decode
from ..helpers import itemstack
from threading import Thread

app = Blueprint("shops", __name__, template_folder="")

requests = reqs.Session()
requests.headers.update({
    "User-Agent": "earthpol-web/1.0",
    "Accept": "application/json",
})


# --- type normalization (because backend hates you) ---
def get_shop_type(n):
    raw = str(n.get("type", ""))

    # try clean extraction first
    cleaned = raw.split(".")[-1].split("@")[0].replace("Type", "").upper()
    if cleaned in ("SELLING", "BUYING"):
        return cleaned

    # fallback paranoia
    if "SellingType" in raw:
        return "SELLING"
    if "BuyingType" in raw:
        return "BUYING"

    return "UNKNOWN"


def update_shop_cache():
    metadata = vb.head("shopdata.json")
    uploaded = datetime.fromisoformat(metadata["uploadedAt"].replace("Z", "+00:00"))

    if datetime.now(UTC) - uploaded > timedelta(minutes=5):
        fresh_data = requests.get("https://api.earthpol.com/astra/shops").content
        vb.put("shopdata.json", fresh_data, options={"allowOverwrite": "true"})


def load_shops():
    try:
        metadata = vb.head("shopdata.json")
        req = requests.get(metadata["downloadUrl"])
        reqdata = json.loads(decode(req.content))

    except BaseException as e:
        if "not_found" in str(e):
            req = requests.get("https://api.earthpol.com/astra/shops")
            vb.put("shopdata.json", req.content, options={"allowOverwrite": "true"})
            reqdata = json.loads(decode(req.content))
        else:
            raise

    for n in reqdata:
        n["item"] = itemstack.parse(n["item"])

        # IMPORTANT: overwrite raw java garbage so templates stay unchanged
        n["type"] = get_shop_type(n)

        qty = n["item"]["amount"]
        n["unit_price"] = n["price"] / qty if qty else float("inf")

    return reqdata


def filter_shops(reqdata, query, stock_filter, type_filter):
    if query:
        reqdata = [n for n in reqdata if query in n["item"]["item"].replace("_", " ").lower()]

    def passes(n):
        t = n.get("type", "UNKNOWN")
        if type_filter == "buying"  and t != "BUYING":  return False
        if type_filter == "selling" and t != "SELLING": return False
        if stock_filter == "hide":
            if t == "SELLING" and n.get("stock", 0) <= 0: return False
            if t == "BUYING"  and n.get("space", 0) <= 0: return False
        return True

    reqdata = [n for n in reqdata if passes(n)]
    reqdata.sort(key=lambda n: n["unit_price"])
    return reqdata


@app.route("/shops")
def shops_page():
    query        = request.args.get("q", "").lower()
    stock_filter = request.args.get("stock_filter", "hide")
    type_filter  = request.args.get("type_filter",  "both")
    Thread(target=update_shop_cache).start()
    return render_template("shops.html", query=query, stock_filter=stock_filter, type_filter=type_filter)


SHOPS_PER_PAGE = 40

@app.route("/shops/data")
def shops_data():
    page         = max(1, int(request.args.get("page", 1)))
    query        = request.args.get("q", "").lower()
    stock_filter = request.args.get("stock_filter", "hide")
    type_filter  = request.args.get("type_filter",  "both")

    reqdata = filter_shops(load_shops(), query, stock_filter, type_filter)
    start   = (page - 1) * SHOPS_PER_PAGE
    return jsonify({
        "players":  reqdata[start : start + SHOPS_PER_PAGE],
        "has_more": start + SHOPS_PER_PAGE < len(reqdata),
    })