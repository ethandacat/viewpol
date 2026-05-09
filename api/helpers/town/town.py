from flask import Blueprint, render_template, redirect
import requests as reqs
from ..helpers.cache import find

app = Blueprint("town", __name__, template_folder="")

_http = reqs.Session()
_http.headers.update({"User-Agent": "earthpol-web/1.0", "Accept": "application/json"})


@app.route("/towns/<identifier>")
def town(identifier):
    # Resolve name → UUID via disk cache (avoids API call just for redirects)
    cached = find("towns.json", identifier)
    if cached:
        uuid = cached.get("uuid", "")
        if uuid and uuid != identifier:
            return redirect(f"/towns/{uuid}", 301)
        identifier = uuid or identifier

    # Fetch full town data — list endpoint only has name+uuid, need POST for details
    try:
        req = _http.post("https://api.earthpol.com/astra/towns",
                         json={"query": [identifier]}, timeout=10)
        if req.status_code != 200 or not req.json():
            return "", 404
        data = req.json()[0]
    except Exception:
        return "", 404

    data_uuid = data.get("uuid", "")
    if data_uuid and data_uuid != identifier:
        return redirect(f"/towns/{data_uuid}", 301)

    return render_template("town.html", data=data)
