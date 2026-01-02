from flask import Blueprint, render_template
import requests as reqs
from ..helpers import itemstack

app = Blueprint("shop", __name__, template_folder="")

requests = reqs.Session()
requests.headers.update({
    "User-Agent": "earthpol-web/1.0",
    "Accept": "application/json",
})

@app.route("/shops/<int:id>")
def shop(id):
    req = requests.post("https://api.earthpol.com/astra/shops", json={"query": [str(id)]})
    if req.status_code != 200 or len(req.json()) == 0:
        return "", 404
    reqdata = req.json()[0]
    reqdata["item"] = itemstack.parse(reqdata["item"])
    return render_template("shop.html", data = reqdata, username=requests.get(f"https://api.mojang.com/user/profile/{req.json()[0]['owner']}").json()["name"])
