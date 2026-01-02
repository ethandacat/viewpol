from flask import Blueprint, render_template, request
import requests as reqs
import math

TOWNS_PER_PAGE = 100
app = Blueprint("towns", __name__, template_folder="")

requests = reqs.Session()
requests.headers.update({
    "User-Agent": "earthpol-web/1.0",
    "Accept": "application/json",
})

@app.route("/towns")
def towns():
    page = int(request.args.get('page', 1))
    query = request.args.get('q', '').lower()

    # Fetch all players (text only)
    reqdata = requests.get("https://api.earthpol.com/astra/towns").json()

    # Filter by search query
    if query:
        reqdata = [p for p in reqdata if query in p['name'].lower().replace("_", " ")]

    # Pagination
    total_players = len(reqdata)
    total_pages = max(1, math.ceil(total_players / TOWNS_PER_PAGE))
    start = (page - 1) * TOWNS_PER_PAGE
    end = start + TOWNS_PER_PAGE
    players_page = reqdata[start:end]  # Only fetch skins for these
    for i in players_page:
        i["name"] = " ".join(i["name"].split("_"))

    return render_template(
        "towns.html",
        players=players_page,
        page=page,
        total_pages=total_pages,
        query=query
    )