from flask import Blueprint, render_template, request
from ..helpers.cache import load

app = Blueprint("nations", __name__, template_folder="")

@app.route("/nations")
def nations():
    query   = request.args.get('q', '').lower()
    reqdata = load("nations.json")
    return render_template("nations.html", players=reqdata, query=query)
