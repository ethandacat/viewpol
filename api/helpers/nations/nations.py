from flask import Blueprint, render_template, request
import requests as reqs

app = Blueprint("nations", __name__, template_folder="")

session = reqs.Session()
session.headers.update({
    "User-Agent": "earthpol-web/1.0",
    "Accept": "application/json",
})

@app.route("/nations")
def nations():
    query   = request.args.get('q', '').lower()
    reqdata = session.get("https://api.earthpol.com/astra/nations").json()
    for n in reqdata:
        n["name"] = " ".join(n["name"].split("_"))
    return render_template("nations.html", players=reqdata, query=query)
