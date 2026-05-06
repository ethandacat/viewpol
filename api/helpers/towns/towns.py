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
    page = int(request.args.get('page', 1))
    query = request.args.get('q', '').lower()

    reqdata = session.get("https://api.earthpol.com/astra/towns").json()

    if query:
        reqdata = [p for p in reqdata if query in p['name'].lower().replace("_", " ")]

    for i in reqdata:
        i["name"] = " ".join(i["name"].split("_"))

    return render_template(
        "towns.html",
        players=reqdata,
        page=page,
        query=query
    )