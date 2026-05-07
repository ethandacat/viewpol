from flask import Blueprint, render_template, request

app = Blueprint("towns", __name__, template_folder="")

import requests as reqs
session = reqs.Session()
session.headers.update({
    "User-Agent": "earthpol-web/1.0",
    "Accept": "application/json",
})

@app.route("/towns")
def towns():
    query   = request.args.get('q', '').lower()
    reqdata = session.get("https://api.earthpol.com/astra/towns").json()
    for t in reqdata:
        t["name"] = " ".join(t["name"].split("_"))
    return render_template("towns.html", players=reqdata, query=query)