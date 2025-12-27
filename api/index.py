from flask import Flask, request, render_template
import requests
from datetime import datetime, UTC
import math

app = Flask(__name__)

PLAYERS_PER_PAGE = 50
TOWNS_PER_PAGE = 100
NATIONS_PER_PAGE = 50

@app.template_filter('datetimeformat')
def datetimeformat(value):
    # value is in seconds
    dt = datetime.fromtimestamp(value, UTC)
    return dt.strftime("%B %d, %Y %I:%M %p UTC")

@app.route("/")
def index():
    return render_template("index.html")

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

@app.route("/players/<uuid>")
def player(uuid):
    req = requests.post("https://api.earthpol.com/astra/players", data=f'{{"query":[{uuid}]}}')
    if req.status_code != 200 or len(req.json()) == 0:
        return render_template("404.html")
    return render_template("player.html", data = req.json()[0])

@app.route("/towns")
def towns():
    page = int(request.args.get('page', 1))
    query = request.args.get('q', '').lower()

    # Fetch all players (text only)
    reqdata = requests.get("https://api.earthpol.com/astra/towns").json()

    # Filter by search query
    if query:
        reqdata = [p for p in reqdata if query in p['name'].lower()]

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

@app.route("/town/<uuid>")
def town(uuid):
    req = requests.post("https://api.earthpol.com/astra/towns", data=f'{{"query":[{uuid}]}}')
    print(req.json())
    if req.status_code != 200 or len(req.json()) == 0:
        return render_template("404.html")
    return render_template("town.html", data = req.json()[0])

@app.route("/nations")
def nations():
    page = int(request.args.get('page', 1))
    query = request.args.get('q', '').lower()

    # Fetch all players (text only)
    reqdata = requests.get("https://api.earthpol.com/astra/nations")
    print(reqdata.status_code, reqdata.text)
    reqdata = reqdata.json()

    # Filter by search query
    if query:
        reqdata = [p for p in reqdata if query in p['name'].lower()]

    # Pagination
    total_players = len(reqdata)
    total_pages = max(1, math.ceil(total_players / NATIONS_PER_PAGE))
    start = (page - 1) * NATIONS_PER_PAGE
    end = start + NATIONS_PER_PAGE
    players_page = reqdata[start:end]  # Only fetch skins for these
    for i in players_page:
        i["name"] = " ".join(i["name"].split("_"))

    return render_template(
        "nations.html",
        players=players_page,
        page=page,
        total_pages=total_pages,
        query=query
    )

@app.route("/nation/<uuid>")
def nation(uuid):
    req = requests.post("https://api.earthpol.com/astra/nations", data=f'{{"query":[{uuid}]}}')
    print(req.json())
    if req.status_code != 200 or len(req.json()) == 0:
        return render_template("404.html")
    return render_template("nation.html", data = req.json()[0])

if __name__ == "__main__":
    app.run("127.0.0.1", port=8000)
