from flask import Blueprint, render_template, request
from ..helpers.cache import load

app = Blueprint("towns", __name__, template_folder="")

@app.route("/towns")
def towns():
    query   = request.args.get('q', '').lower()
    reqdata = load("towns.json", "towns")
    return render_template("towns.html", players=reqdata, query=query)
