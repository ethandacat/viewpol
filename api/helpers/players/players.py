from flask import Blueprint, render_template, request
import requests as reqs

app = Blueprint("players", __name__, template_folder="")

requests = reqs.Session()
requests.headers.update({
    "User-Agent": "earthpol-web/1.0",
    "Accept": "application/json",
})

@app.route("/players")
def players():
    query = request.args.get('q', '').lower()
    reqdata = requests.get("https://api.earthpol.com/astra/players").json()
    return render_template("players.html", players=reqdata, query=query)
