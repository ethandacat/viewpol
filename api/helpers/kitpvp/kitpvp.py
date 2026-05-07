from flask import Blueprint, render_template, jsonify, request
import requests as reqs

app = Blueprint("kitpvp", __name__, template_folder="")

session = reqs.Session()
session.headers.update({
    "User-Agent": "earthpol-web/1.0",
    "Accept": "application/json",
})


@app.route("/kitpvp")
def kitpvp_page():
    return render_template("kitpvp.html")


@app.route("/kitpvp/data")
def kitpvp_data():
    params = {"sort": "kills", "order": "desc", "limit": 100}
    cursor_value = request.args.get("cursorValue")
    cursor_uuid  = request.args.get("cursorUuid")
    if cursor_value and cursor_uuid:
        params["cursorValue"] = cursor_value
        params["cursorUuid"]  = cursor_uuid

    resp = session.get(
        "https://earthpol.org/api/kitpvp/leaderboard",
        params=params,
        timeout=10,
    )
    data  = resp.json()
    items = data.get("items", [])
    for p in items:
        d       = p.get("deaths", 0)
        p["kd"] = round(p["kills"] / d, 2) if d else float(p["kills"])
    return jsonify({
        "items":      items,
        "nextCursor": data.get("nextCursor"),
    })
