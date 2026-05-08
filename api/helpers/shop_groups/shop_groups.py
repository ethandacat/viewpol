from flask import Blueprint, render_template, request, jsonify, redirect
import json, math, secrets, time, os
import requests as reqs
import vercel_blob as vb
from ..shops.shops import load_shops
from ..helpers import itemstack

app = Blueprint("shop_groups", __name__, template_folder="")

_http = reqs.Session()
_http.headers.update({"User-Agent": "earthpol-web/1.0", "Accept": "application/json"})

# Use a separate blob key per Vercel environment so production and preview
# (rework branch) never share mall data.
_ENV = os.environ.get("VERCEL_ENV", "development")   # "production" | "preview" | "development"
BLOB_KEY = "shop_groups.json" if _ENV == "production" else f"shop_groups_{_ENV}.json"

# Module-level URL cache: survives across requests on the same warm serverless instance,
# saving the vb.list() discovery round-trip (~200–400 ms) on subsequent calls.
_blob_url: str | None = None


# ── Blob helpers ───────────────────────────────────────────────────

def _load_groups():
    global _blob_url
    nc_headers = {"Cache-Control": "no-cache", "Pragma": "no-cache"}

    # Fast path: try the cached URL directly (warm instance, saves vb.list call)
    if _blob_url:
        try:
            res = _http.get(_blob_url, headers=nc_headers)
            if res.status_code == 200:
                return json.loads(res.content)
        except Exception:
            pass
        _blob_url = None  # stale — fall through to discovery

    # Slow path: discover URL via listing
    try:
        result = vb.list(options={"prefix": BLOB_KEY, "limit": "1"})
        blobs = (result or {}).get("blobs") or []
        if not blobs:
            return []
        url = blobs[0].get("downloadUrl") or blobs[0].get("url", "")
        res = _http.get(url, headers=nc_headers)
        res.raise_for_status()
        _blob_url = url  # cache for next call on this instance
        return json.loads(res.content)
    except Exception:
        return []


def _save_groups(groups):
    global _blob_url
    result = vb.put(
        BLOB_KEY,
        json.dumps(groups).encode(),
        options={"allowOverwrite": "true", "addRandomSuffix": "false"},
    )
    # Cache the URL returned by put so the next load skips vb.list()
    _blob_url = result.get("url") or result.get("downloadUrl") or _blob_url


def _pub(g):
    return {k: v for k, v in g.items() if k != "editToken"}


def _sanitize_shops(shops):
    out = []
    for s in shops:
        s = dict(s)
        up = s.get("unit_price")
        if isinstance(up, float) and not math.isfinite(up):
            s["unit_price"] = None
        out.append(s)
    return out


def _normalize_type(raw):
    raw = str(raw)
    cleaned = raw.split(".")[-1].split("@")[0].replace("Type", "").upper()
    if cleaned in ("SELLING", "BUYING"):
        return cleaned
    if "SELLING" in raw.upper():
        return "SELLING"
    if "BUYING" in raw.upper():
        return "BUYING"
    return "UNKNOWN"


# ── Pages ──────────────────────────────────────────────────────────

@app.route("/malls")
def malls_page():
    return render_template("malls.html")


@app.route("/malls/<group_id>")
def mall_page(group_id):
    return render_template("mall.html", group_id=group_id)


# Legacy redirects
@app.route("/shop-groups")
def sg_redirect():
    return redirect("/malls", 301)

@app.route("/shop-groups/<path:rest>")
def sg_redirect_sub(rest):
    return redirect("/malls/" + rest, 301)


# ── Group CRUD ─────────────────────────────────────────────────────

@app.route("/malls/api/groups")
def sg_list():
    return jsonify([_pub(g) for g in _load_groups()])


@app.route("/malls/api/groups", methods=["POST"])
def sg_create():
    data = request.json or {}
    name = str(data.get("name", "")).strip()[:60]
    if not name:
        return jsonify({"error": "name required"}), 400
    group = {
        "id":        "sg_" + secrets.token_urlsafe(8),
        "name":      name,
        "shopIds":   list(data.get("shopIds", [])),
        "open":      bool(data.get("open", False)),
        "iconUrl":   None,
        "createdAt": int(time.time() * 1000),
        "editToken": secrets.token_urlsafe(16),
    }
    groups = _load_groups()
    groups.insert(0, group)
    _save_groups(groups)
    return jsonify(group), 201


@app.route("/malls/api/groups/<group_id>")
def sg_get(group_id):
    g = next((g for g in _load_groups() if g["id"] == group_id), None)
    if not g:
        return jsonify({"error": "not found"}), 404
    return jsonify(_pub(g))


@app.route("/malls/api/groups/<group_id>", methods=["PUT"])
def sg_update(group_id):
    data = request.json or {}
    groups = _load_groups()
    idx = next((i for i, g in enumerate(groups) if g["id"] == group_id), None)
    if idx is None:
        return jsonify({"error": "not found"}), 404
    if groups[idx].get("editToken") != data.get("editToken"):
        return jsonify({"error": "forbidden"}), 403
    if "name" in data:
        groups[idx]["name"] = str(data["name"]).strip()[:60]
    if "shopIds" in data:
        groups[idx]["shopIds"] = list(data["shopIds"])
    if "open" in data:
        groups[idx]["open"] = bool(data["open"])
    if "iconUrl" in data:
        groups[idx]["iconUrl"] = str(data["iconUrl"]).strip()[:500] if data["iconUrl"] else None
    _save_groups(groups)
    return jsonify(_pub(groups[idx]))


@app.route("/malls/api/groups/<group_id>", methods=["DELETE"])
def sg_delete(group_id):
    data = request.json or {}
    groups = _load_groups()
    idx = next((i for i, g in enumerate(groups) if g["id"] == group_id), None)
    if idx is None:
        return jsonify({"error": "not found"}), 404
    if groups[idx].get("editToken") != data.get("editToken"):
        return jsonify({"error": "forbidden"}), 403
    groups.pop(idx)
    _save_groups(groups)
    return "", 204


# ── Shop data APIs ─────────────────────────────────────────────────

@app.route("/malls/api/groups/<group_id>/shops", methods=["PATCH"])
def sg_patch_shops(group_id):
    """Add shops (anyone if open) or full replace (owner only)."""
    data = request.json or {}
    groups = _load_groups()
    idx = next((i for i, g in enumerate(groups) if g["id"] == group_id), None)
    if idx is None:
        return jsonify({"error": "not found"}), 404
    g = groups[idx]
    is_owner = data.get("editToken") == g.get("editToken")
    if not is_owner and not g.get("open"):
        return jsonify({"error": "forbidden"}), 403
    if is_owner and "shopIds" in data:
        # Full replace (dedup, preserve order)
        seen = set()
        clean = []
        for id_ in data["shopIds"]:
            s = str(id_)
            if s not in seen:
                seen.add(s)
                clean.append(s)
        g["shopIds"] = clean
    elif "addIds" in data:
        # Append only (used by open-contributors)
        existing = list(g["shopIds"])
        existing_set = set(existing)
        for id_ in data["addIds"]:
            s = str(id_)
            if s not in existing_set:
                existing.append(s)
                existing_set.add(s)
        g["shopIds"] = existing
    _save_groups(groups)
    return jsonify(_pub(g))


@app.route("/malls/api/groups/<group_id>/icon", methods=["POST"])
def sg_set_icon(group_id):
    """Owner sets mall icon via file upload or URL."""
    groups = _load_groups()
    idx = next((i for i, g in enumerate(groups) if g["id"] == group_id), None)
    if idx is None:
        return jsonify({"error": "not found"}), 404
    g = groups[idx]

    is_multipart = request.content_type and "multipart" in request.content_type
    token = request.form.get("editToken", "") if is_multipart else (request.json or {}).get("editToken", "")
    if token != g.get("editToken"):
        return jsonify({"error": "forbidden"}), 403

    if is_multipart:
        file = request.files.get("file")
        if not file:
            return jsonify({"error": "no file provided"}), 400
        ct = file.content_type or "image/png"
        key = f"mall_icons/{group_id}"
        result = vb.put(key, file.read(), options={"allowOverwrite": "true", "contentType": ct})
        icon_url = result.get("url") or result.get("downloadUrl", "")
    else:
        body = request.json or {}
        icon_url = str(body.get("iconUrl", "")).strip()[:500]
        if not icon_url:
            return jsonify({"error": "iconUrl required"}), 400

    groups[idx]["iconUrl"] = icon_url
    _save_groups(groups)
    return jsonify({"iconUrl": icon_url})


@app.route("/malls/api/by-ids")
def sg_by_ids():
    ids_param = request.args.get("ids", "")
    if not ids_param:
        return jsonify([])
    ids = {s.strip() for s in ids_param.split(",") if s.strip()}
    result = [s for s in load_shops() if str(s.get("id", "")) in ids]
    return jsonify(_sanitize_shops(result))


@app.route("/malls/api/area")
def sg_area():
    try:
        x1 = float(request.args["x1"]); z1 = float(request.args["z1"])
        x2 = float(request.args["x2"]); z2 = float(request.args["z2"])
    except (KeyError, ValueError):
        return jsonify({"error": "x1, z1, x2, z2 required"}), 400
    xmin, xmax = min(x1, x2), max(x1, x2)
    zmin, zmax = min(z1, z2), max(z1, z2)
    result = []
    for s in load_shops():
        loc = s.get("location") or {}
        if xmin <= (loc.get("x") or 0) <= xmax and zmin <= (loc.get("z") or 0) <= zmax:
            result.append(s)
    return jsonify(_sanitize_shops(result))


@app.route("/malls/api/user-shops")
def sg_user_shops():
    user = request.args.get("user", "").strip()
    if not user:
        return jsonify({"error": "user required"}), 400
    # Resolve name → UUID via players API
    p_res = _http.post("https://api.earthpol.com/astra/players", json={"query": [user]})
    if p_res.status_code != 200 or not p_res.json():
        return jsonify({"error": "Player not found"}), 404
    player   = p_res.json()[0]
    uuid     = player.get("uuid", user)
    username = player.get("name", user)
    # Fetch shops owned by this player
    s_res = _http.post("https://api.earthpol.com/astra/shops", json={"query": [uuid]})
    if s_res.status_code != 200:
        return jsonify({"username": username, "shops": []})
    raw = s_res.json()
    shops = raw[0] if raw and isinstance(raw[0], list) else [s for s in raw if isinstance(s, dict)]
    for s in shops:
        s["item"] = itemstack.parse(s["item"])
        s["type"] = _normalize_type(s.get("type", ""))
        qty = (s["item"] or {}).get("amount") or 1
        s["unit_price"] = s["price"] / qty if qty else None
    return jsonify({"username": username, "shops": _sanitize_shops(shops)})


def _compute_market_stats(item_ids):
    """Return {item_id: {count, avg, min}} for SELLING shops across all shops."""
    buckets = {}
    for s in load_shops():
        item_id = (s.get("item") or {}).get("item", "")
        if item_id not in item_ids or s.get("type") != "SELLING":
            continue
        unit = s.get("unit_price")
        if unit is None or not math.isfinite(unit) or unit <= 0:
            continue
        if item_id not in buckets:
            buckets[item_id] = {"count": 0, "total": 0.0, "min": float("inf")}
        buckets[item_id]["count"] += 1
        buckets[item_id]["total"] += unit
        if unit < buckets[item_id]["min"]:
            buckets[item_id]["min"] = unit
    result = {}
    for k, v in buckets.items():
        result[k] = {
            "count": v["count"],
            "avg":   round(v["total"] / v["count"], 4),
            "min":   round(v["min"], 4) if math.isfinite(v["min"]) else None,
        }
    return result


@app.route("/malls/api/market-stats")
def sg_market_stats():
    items_param = request.args.get("items", "")
    if not items_param:
        return jsonify({})
    item_ids = {s.strip() for s in items_param.split(",") if s.strip()}
    return jsonify(_compute_market_stats(item_ids))


@app.route("/malls/api/rankings")
def sg_rankings():
    """Rank all malls by completeness (unique items) × price competitiveness."""
    groups = _load_groups()
    if not groups:
        return jsonify([])

    shops_list = load_shops()
    shops_by_id = {str(s.get("id", "")): s for s in shops_list}

    # Gather all selling item IDs across every mall — one market pass for all
    all_item_ids = set()
    for g in groups:
        for sid in g.get("shopIds", []):
            s = shops_by_id.get(str(sid))
            if s and s.get("type") == "SELLING":
                item_id = (s.get("item") or {}).get("item", "")
                if item_id:
                    all_item_ids.add(item_id)

    mkt = _compute_market_stats(all_item_ids) if all_item_ids else {}

    results = []
    for g in groups:
        mall_shops = [shops_by_id[str(sid)] for sid in g.get("shopIds", []) if str(sid) in shops_by_id]
        selling    = [s for s in mall_shops if s.get("type") == "SELLING"]

        # Best price per item in this mall
        item_best = {}
        for s in selling:
            item_id = (s.get("item") or {}).get("item", "")
            if not item_id:
                continue
            up = s.get("unit_price")
            if up is None or not math.isfinite(up) or up <= 0:
                continue
            if item_id not in item_best or up < item_best[item_id]:
                item_best[item_id] = up

        item_count = len(item_best)
        shop_count = len(mall_shops)

        # vs-market comparison
        vs_bests, items_at_best = [], 0
        for item_id, best_price in item_best.items():
            m = mkt.get(item_id)
            if m and m.get("min") and m["min"] > 0:
                pct = (best_price - m["min"]) / m["min"] * 100
                vs_bests.append(pct)
                if pct <= 0.5:
                    items_at_best += 1

        avg_vs_best = round(sum(vs_bests) / len(vs_bests), 2) if vs_bests else None
        # price_score: EarthPol prices vary wildly, so use sqrt compression.
        # 0% above → 100,  50% → ~85,  200% → ~72,  500% → ~60,  2000% → ~45
        price_score = round(max(0.0, 100.0 - 100.0 * math.sqrt(float(avg_vs_best)) / (math.sqrt(float(avg_vs_best)) + 60.0)), 1) \
                      if avg_vs_best is not None else None

        results.append({
            "id":          g["id"],
            "name":        g["name"],
            "iconUrl":     g.get("iconUrl"),
            "open":        g.get("open", False),
            "shopCount":   shop_count,
            "itemCount":   item_count,
            "itemsAtBest": items_at_best,
            "avgVsBest":   avg_vs_best,
            "priceScore":  price_score,
            "overallScore": 0.0,
        })

    # Normalise completeness across malls, then blend 50/50 with price score
    max_items = max((r["itemCount"] for r in results), default=1) or 1
    for r in results:
        comp_pct  = r["itemCount"] / max_items * 100
        price_pct = r["priceScore"] if r["priceScore"] is not None else 0.0
        r["overallScore"] = round((comp_pct + price_pct) / 2.0, 1)

    results.sort(key=lambda x: (-x["overallScore"], -x["itemCount"]))
    return jsonify(results)
