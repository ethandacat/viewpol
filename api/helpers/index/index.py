from flask import Blueprint, render_template, jsonify
from ..helpers.cache import load
from ..shops.shops import shop_count

app = Blueprint("index", __name__, template_folder="")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/stats")
def stats():
    counts = {}
    for key, filename in (
        ("nations", "nations.json"),
        ("towns",   "towns.json"),
        ("players", "players.json"),
        ("sieges",  "sieges.json"),
    ):
        try:
            data = load(filename)
            if key == "sieges":
                sieges_list = data.get("sieges", []) if isinstance(data, dict) else []
                counts[key] = sum(1 for s in sieges_list if s.get("isActive", False))
            else:
                counts[key] = len(data) if isinstance(data, list) else 0
        except Exception:
            counts[key] = None
    try:
        counts["shops"] = shop_count()
    except Exception:
        counts["shops"] = None
    return jsonify(counts)
