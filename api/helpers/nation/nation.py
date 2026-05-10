from flask import Blueprint, render_template, redirect
import requests as reqs
from ..helpers.cache import find

app = Blueprint("nation", __name__, template_folder="")

_http = reqs.Session()
_http.headers.update({"User-Agent": "earthpol-web/1.0", "Accept": "application/json"})


@app.route("/nations/<identifier>")
def nation(identifier):
    # Resolve name → UUID via disk cache (avoids API call just for redirects)
    cached = find("nations.json", identifier)
    if cached:
        uuid = cached.get("uuid", "")
        if uuid and uuid != identifier:
            return redirect(f"/nations/{uuid}", 301)
        identifier = uuid or identifier

    # Fetch full nation data — list endpoint only has name+uuid, need POST for details
    try:
        req    = _http.post("https://api.earthpol.com/astra/nations",
                            json={"query": [identifier]}, timeout=10)
        result = req.json(); req.close()
        if req.status_code != 200 or not result:
            return "", 404
        data = result[0]
    except Exception:
        return "", 404

    data_uuid = data.get("uuid", "")
    if data_uuid and data_uuid != identifier:
        return redirect(f"/nations/{data_uuid}", 301)

    return render_template("nation.html", data=data)
