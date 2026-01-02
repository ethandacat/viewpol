from flask import Blueprint, render_template
import requests as reqs

app = Blueprint("town", __name__, template_folder="")

requests = reqs.Session()
requests.headers.update({
    "User-Agent": "earthpol-web/1.0",
    "Accept": "application/json",
})

@app.route("/towns/<uuid>")
def town(uuid):
    req = requests.post("https://api.earthpol.com/astra/towns", json={"query": [uuid]})
    if req.status_code != 200 or len(req.json()) == 0:
        return "", 404
    return render_template("town.html", data = req.json()[0])