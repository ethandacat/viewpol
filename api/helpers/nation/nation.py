from flask import Blueprint, render_template, redirect
import requests as reqs

app = Blueprint("nation", __name__, template_folder="")

requests = reqs.Session()
requests.headers.update({
    "User-Agent": "earthpol-web/1.0",
    "Accept": "application/json",
})

@app.route("/nations/<identifier>")
def nation(identifier):
    req = requests.post("https://api.earthpol.com/astra/nations", json={"query": [identifier]})
    if req.status_code != 200 or len(req.json()) == 0:
        return "", 404
    data = req.json()[0]
    data_uuid = data.get("uuid", "")
    if data_uuid and data_uuid != identifier:
        return redirect(f"/nations/{data_uuid}", 301)
    return render_template("nation.html", data=data)