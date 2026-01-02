from flask import Blueprint, render_template, request
import requests as reqs
import math

NATIONS_PER_PAGE = 50
app = Blueprint("nations", __name__, template_folder="")

session = reqs.Session()
session.headers.update({
    "User-Agent": "earthpol-web/1.0",
    "Accept": "application/json",
})

@app.route("/nations")
def nations():
    page = int(request.args.get('page', 1))
    query = request.args.get('q', '').lower()

    # Fetch all nations
    reqdata = session.get("https://api.earthpol.com/astra/nations").json()

    # Filter by search query
    if query:
        reqdata = [p for p in reqdata if query in p['name'].lower().replace("_", " ")]

    players_page = reqdata

    # Normalize names for display
    for i in players_page:
        i["name"] = " ".join(i["name"].split("_"))

    return render_template(
        "nations.html",
        players=players_page,
        page=page,
        query=query
    )
