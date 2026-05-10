from flask import Blueprint, render_template, request, jsonify
import json, time, os
from pathlib import Path
from threading import Thread, Lock
from ..helpers import itemstack

app = Blueprint("shops", __name__, template_folder="")

import requests as reqs
_http = reqs.Session()
_http.headers.update({
    "User-Agent": "earthpol-web/1.0",
    "Accept": "application/json",
})

DATA_DIR  = Path(os.environ.get("DATA_DIR", "data"))
SHOP_FILE = DATA_DIR / "shopdata.json"
SHOP_TTL  = 300   # seconds — trigger background refresh if stale

_shop_cache: dict = {}   # {"mtime": float, "raw": bytes}  — bytes not parsed dicts
_cache_lock  = Lock()
_refresh_lock = Lock()   # ensures only one refresh thread runs at a time


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


# ── Item parsing ───────────────────────────────────────────────────

def _process(shops):
    for n in shops:
        if isinstance(n.get("item"), str):
            n["item"] = itemstack.parse(n["item"])
        n["type"]       = get_shop_type(n)
        qty             = n["item"]["amount"]
        n["unit_price"] = n["price"] / qty if qty else float("inf")


# ── Mtime-gated in-memory cache ───────────────────────────────────

def _load_raw() -> bytes:
    """Return raw shopdata bytes, reloading from disk only when the file changes."""
    mtime = SHOP_FILE.stat().st_mtime
    with _cache_lock:
        if _shop_cache.get("mtime") == mtime and "raw" in _shop_cache:
            return _shop_cache["raw"]
    raw = SHOP_FILE.read_bytes()
    with _cache_lock:
        _shop_cache["mtime"] = mtime
        _shop_cache["raw"]   = raw
        _shop_cache.pop("count", None)   # invalidate stale count
    return raw


def load_shops() -> list:
    """Return shop list. Parses JSON per-call from the bytes cache (~3 MB) so the
    full parsed list (~15-20 MB of Python objects) is never held in RAM at rest."""
    try:
        shops = json.loads(_load_raw())
        _process(shops)
        with _cache_lock:
            if "count" not in _shop_cache:
                _shop_cache["count"] = len(shops)
        return shops
    except Exception:
        return []


def shop_count() -> int:
    """Return the number of shops without keeping a parsed list in memory.
    Warms the raw-bytes cache as a side-effect so load_shops() hits are cheaper."""
    try:
        mtime = SHOP_FILE.stat().st_mtime
        with _cache_lock:
            if _shop_cache.get("mtime") == mtime and "count" in _shop_cache:
                return _shop_cache["count"]
        raw   = _load_raw()
        count = len(json.loads(raw))
        with _cache_lock:
            _shop_cache["count"] = count
        return count
    except Exception:
        return 0


def _refresh_disk():
    """Background thread: re-fetch from EarthPol API and overwrite shopdata.json."""
    try:
        raw = _http.get("https://api.earthpol.com/astra/shops", timeout=30).content
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        tmp = SHOP_FILE.with_suffix(".tmp")
        tmp.write_bytes(raw)
        tmp.replace(SHOP_FILE)
    except Exception:
        pass
    finally:
        _refresh_lock.release()


def _maybe_refresh():
    """Kick off a background refresh if stale — at most one thread at a time."""
    try:
        if not SHOP_FILE.exists() or time.time() - SHOP_FILE.stat().st_mtime > SHOP_TTL:
            if _refresh_lock.acquire(blocking=False):
                Thread(target=_refresh_disk, daemon=True).start()
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
    _maybe_refresh()
    return render_template("shops.html", query=query, stock_filter=stock_filter, type_filter=type_filter)


SHOPS_PER_PAGE = 40

@app.route("/shops/data")
def shops_data():
    page         = max(1, int(request.args.get("page", 1)))
    query        = request.args.get("q", "").lower()
    stock_filter = request.args.get("stock_filter", "hide")
    type_filter  = request.args.get("type_filter",  "both")
    _maybe_refresh()

    reqdata = filter_shops(load_shops(), query, stock_filter, type_filter)
    start   = (page - 1) * SHOPS_PER_PAGE
    return jsonify({
        "players":  reqdata[start : start + SHOPS_PER_PAGE],
        "has_more": start + SHOPS_PER_PAGE < len(reqdata),
    })
