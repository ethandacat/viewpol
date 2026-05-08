from flask import Blueprint, render_template, request, jsonify
import requests as reqs
import json, time, os
from codecs import decode
from pathlib import Path
from threading import Thread
from ..helpers import itemstack

app = Blueprint("shops", __name__, template_folder="")

requests = reqs.Session()
requests.headers.update({
    "User-Agent": "earthpol-web/1.0",
    "Accept": "application/json",
})

DATA_DIR       = Path(os.environ.get("DATA_DIR", "data"))
SHOP_FILE      = DATA_DIR / "shopdata.json"
SHOP_TTL       = 300   # seconds before re-fetching from EarthPol API

_cache         = None
_cache_ts      = 0.0


# ── Type normalisation ─────────────────────────────────────────────

def get_shop_type(n):
    raw     = str(n.get("type", ""))
    cleaned = raw.split(".")[-1].split("@")[0].replace("Type", "").upper()
    if cleaned in ("SELLING", "BUYING"):
        return cleaned
    if "SellingType" in raw:
        return "SELLING"
    if "BuyingType" in raw:
        return "BUYING"
    return "UNKNOWN"


# ── Item parsing (mutates list in place) ───────────────────────────

def _process(shops):
    for n in shops:
        if isinstance(n.get("item"), str):
            n["item"] = itemstack.parse(n["item"])
        n["type"]       = get_shop_type(n)
        qty             = n["item"]["amount"]
        n["unit_price"] = n["price"] / qty if qty else float("inf")


# ── Cache + fetch ──────────────────────────────────────────────────

def load_shops():
    global _cache, _cache_ts
    now = time.time()

    # 1. Hot in-memory cache (free, no I/O)
    if _cache is not None and now - _cache_ts < SHOP_TTL:
        return _cache

    # 2. Warm disk cache (avoid hitting EarthPol API if file is fresh)
    try:
        if SHOP_FILE.exists() and now - SHOP_FILE.stat().st_mtime < SHOP_TTL:
            shops = json.loads(decode(SHOP_FILE.read_bytes()))
            _process(shops)
            _cache, _cache_ts = shops, now
            return _cache
    except Exception:
        pass

    # 3. Fetch fresh from EarthPol
    raw = requests.get("https://api.earthpol.com/astra/shops").content
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SHOP_FILE.write_bytes(raw)
    shops = json.loads(decode(raw))
    _process(shops)
    _cache, _cache_ts = shops, now
    return _cache


def update_shop_cache():
    """Background refresh: re-fetch only when disk file is stale."""
    try:
        if not SHOP_FILE.exists() or time.time() - SHOP_FILE.stat().st_mtime > SHOP_TTL:
            raw = requests.get("https://api.earthpol.com/astra/shops").content
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            SHOP_FILE.write_bytes(raw)
            # Invalidate in-memory cache so next request picks up fresh data
            global _cache, _cache_ts
            _cache, _cache_ts = None, 0.0
    except Exception:
        pass


# ── Filtering ──────────────────────────────────────────────────────

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


# ── Routes ─────────────────────────────────────────────────────────

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
