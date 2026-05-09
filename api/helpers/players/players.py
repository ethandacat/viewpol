from flask import Blueprint, render_template, request
from ..helpers.cache import players_cache

app = Blueprint("players", __name__, template_folder="")

@app.route("/players")
def players():
    query   = request.args.get('q', '').lower()
    reqdata = players_cache().all()
    return render_template("players.html", players=reqdata, query=query)
