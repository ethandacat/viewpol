from flask import Blueprint, render_template, request, jsonify
import requests as reqs
from datetime import datetime, timedelta, UTC
import vercel_blob as vb
import json
from codecs import decode
from ..helpers import itemstack
from threading import Thread
import math

SHOPS_PER_PAGE = 40
app = Blueprint("shops", __name__, template_folder="")

requests = reqs.Session()
requests.headers.update({
    "User-Agent": "earthpol-web/1.0",
    "Accept": "application/json",
})

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
        qty = n["item"]["amount"]
        n["unit_price"] = n["price"] / qty if qty else float("inf")
    return reqdata

def filter_and_page(reqdata, query, stock_filter, type_filter, page):
    if query:
        reqdata = [
            n for n in reqdata
            if query in n["item"]["item"].replace("_", " ").lower()
        ]

    def passes_filters(n):
        if type_filter == "buying" and n["type"] != "BUYING":
            return False
        if type_filter == "selling" and n["type"] != "SELLING":
            return False
        if stock_filter == "hide":
            if n["type"] == "SELLING" and n.get("stock", 0) <= 0:
                return False
            if n["type"] != "SELLING" and n.get("space", 0) <= 0:
                return False
        return True

    reqdata = [n for n in reqdata if passes_filters(n)]
    reqdata.sort(key=lambda n: n["unit_price"])

    total = len(reqdata)
    total_pages = max(1, math.ceil(total / SHOPS_PER_PAGE))
    page = max(1, min(page, total_pages))
    start = (page - 1) * SHOPS_PER_PAGE
    end = start + SHOPS_PER_PAGE
    players_page = reqdata[start:end]

    return players_page, page, total_pages

@app.route("/shops")
def shops_page():
    page = int(request.args.get("page", 1))
    query = request.args.get("q", "").lower()
    stock_filter = request.args.get("stock_filter", "hide")
    type_filter = request.args.get("type_filter", "both")

    reqdata = load_shops()
    players_page, page, total_pages = filter_and_page(
        reqdata, query, stock_filter, type_filter, page
    )

    Thread(target=update_shop_cache).start()

    return render_template(
        "shops.html",
        players=players_page,
        page=page,
        total_pages=total_pages,
        query=query,
        stock_filter=stock_filter,
        type_filter=type_filter,
        SHOPS_PER_PAGE=SHOPS_PER_PAGE,
    )

@app.route("/shops/data")
def shops_data():
    page = int(request.args.get("page", 1))
    query = request.args.get("q", "").lower()
    stock_filter = request.args.get("stock_filter", "hide")
    type_filter = request.args.get("type_filter", "both")

    reqdata = load_shops()
    players_page, page, total_pages = filter_and_page(
        reqdata, query, stock_filter, type_filter, page
    )

    return jsonify({
        "page": page,
        "total_pages": total_pages,
        "players": players_page,
    })
