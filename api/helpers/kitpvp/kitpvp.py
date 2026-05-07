from flask import Blueprint, render_template, request
import requests as reqs

app = Blueprint("kitpvp", __name__, template_folder="")

session = reqs.Session()
session.headers.update({
    "User-Agent": "earthpol-web/1.0",
    "Accept": "application/json",
})

VALID_SORTS = {"kills", "deaths", "assists", "damage", "damage_taken",
               "best_killstreak", "current_killstreak", "bow_shots", "bow_hits"}
PER_PAGE = 50


@app.route("/kitpvp")
def kitpvp_page():
    sort  = request.args.get("sort", "kills")
    order = request.args.get("order", "desc")
    page  = max(1, int(request.args.get("page", 1)))

    if sort not in VALID_SORTS:
        sort = "kills"
    if order not in ("asc", "desc"):
        order = "desc"

    offset = (page - 1) * PER_PAGE
    resp = session.get(
        "https://earthpol.org/api/kitpvp/leaderboard",
        params={"sort": sort, "order": order, "limit": PER_PAGE, "offset": offset},
    )
    data = resp.json()
    items = data.get("items", [])
    has_next = bool(data.get("nextCursor"))

    for i, p in enumerate(items):
        d = p.get("deaths", 0)
        p["kd"] = round(p["kills"] / d, 2) if d else float(p["kills"])
        p["rank"] = offset + i + 1

    return render_template(
        "kitpvp.html",
        items=items,
        sort=sort,
        order=order,
        page=page,
        has_next=has_next,
    )
