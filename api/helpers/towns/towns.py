from flask import Blueprint, render_template, request
from ..helpers.cache import towns_cache

app = Blueprint("towns", __name__, template_folder="")

@app.route("/towns")
def towns():
    query   = request.args.get('q', '').lower()
    reqdata = towns_cache().all()
    return render_template("towns.html", players=reqdata, query=query)
