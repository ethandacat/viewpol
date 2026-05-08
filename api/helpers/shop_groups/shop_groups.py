from flask import Blueprint, render_template, request, jsonify
import math
from ..shops.shops import load_shops

app = Blueprint("shop_groups", __name__, template_folder="")


def _sanitize(shops):
    """Replace non-JSON-safe floats and return a clean list."""
    out = []
    for s in shops:
        s = dict(s)
        up = s.get("unit_price")
        if isinstance(up, float) and not math.isfinite(up):
            s["unit_price"] = None
        out.append(s)
    return out


@app.route("/shop-groups")
def shop_groups_page():
    return render_template("shop_groups.html")


@app.route("/shop-groups/<group_id>")
def shop_group_page(group_id):
    return render_template("shop_group.html", group_id=group_id)


@app.route("/shop-groups/api/by-ids")
def sg_by_ids():
    ids_param = request.args.get("ids", "")
    if not ids_param:
        return jsonify([])
    ids = {s.strip() for s in ids_param.split(",") if s.strip()}
    result = [s for s in load_shops() if str(s.get("id", "")) in ids]
    return jsonify(_sanitize(result))


@app.route("/shop-groups/api/area")
def sg_area():
    try:
        x1 = float(request.args["x1"])
        z1 = float(request.args["z1"])
        x2 = float(request.args["x2"])
        z2 = float(request.args["z2"])
    except (KeyError, ValueError):
        return jsonify({"error": "x1, z1, x2, z2 required"}), 400
    xmin, xmax = min(x1, x2), max(x1, x2)
    zmin, zmax = min(z1, z2), max(z1, z2)
    result = []
    for s in load_shops():
        loc = s.get("location") or {}
        x = loc.get("x") or 0
        z = loc.get("z") or 0
        if xmin <= x <= xmax and zmin <= z <= zmax:
            result.append(s)
    return jsonify(_sanitize(result))


@app.route("/shop-groups/api/market-stats")
def sg_market_stats():
    items_param = request.args.get("items", "")
    if not items_param:
        return jsonify({})
    item_ids = {s.strip() for s in items_param.split(",") if s.strip()}
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
    return jsonify(result)
