from flask import Blueprint, render_template, request
import requests as reqs
import math

PLAYERS_PER_PAGE = 50
app = Blueprint("players", __name__, template_folder="")

requests = reqs.Session()
requests.headers.update({
    "User-Agent": "earthpol-web/1.0",
    "Accept": "application/json",
})

@app.route("/players")
def players():
    page = int(request.args.get('page', 1))
    query = request.args.get('q', '').lower()

    # Fetch all players (text only)
    reqdata = requests.get("https://api.earthpol.com/astra/players").json()

    # Filter by search query
    if query:
        reqdata = [p for p in reqdata if query in p['name'].lower()]

    # Pagination
    total_players = len(reqdata)
    total_pages = max(1, math.ceil(total_players / PLAYERS_PER_PAGE))
    start = (page - 1) * PLAYERS_PER_PAGE
    end = start + PLAYERS_PER_PAGE
    players_page = reqdata[start:end]  # Only fetch skins for these

    return render_template(
        "players.html",
        players=players_page,
        page=page,
        total_pages=total_pages,
        query=query
    )