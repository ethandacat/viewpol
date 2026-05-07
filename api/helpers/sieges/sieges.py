from flask import Blueprint, render_template
import requests as reqs

app = Blueprint("sieges", __name__, template_folder="")

session = reqs.Session()
session.headers.update({
    "User-Agent": "earthpol-web/1.0",
    "Accept": "application/json",
})


def load_sieges():
    return session.get("https://api.earthpol.com/astra/sieges").json()


@app.route("/sieges")
def sieges_page():
    data = load_sieges()
    sieges = data.get("sieges", [])
    active_count = data.get("activeSiegeCount", 0)
    time_till = data.get("battleSessionTimeTill", 0)
    time_remaining = data.get("battleSessionTimeRemaining", 0)
    return render_template(
        "sieges.html",
        sieges=sieges,
        active_count=active_count,
        time_till=time_till,
        time_remaining=time_remaining,
    )


@app.route("/sieges/<name>")
def siege_page(name):
    data = load_sieges()
    sieges = data.get("sieges", [])
    siege = next(
        (s for s in sieges if s.get("name", "").lower() == name.lower() or s.get("uuid", "") == name),
        None,
    )
    if siege is None:
        return "", 404
    return render_template("siege.html", siege=siege)
