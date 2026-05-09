from flask import Blueprint, render_template, request
from ..helpers.cache import load

app = Blueprint("players", __name__, template_folder="")

@app.route("/players")
def players():
    query   = request.args.get('q', '').lower()
    reqdata = load("players.json")
    return render_template("players.html", players=reqdata, query=query)
