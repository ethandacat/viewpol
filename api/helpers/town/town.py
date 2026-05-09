from flask import Blueprint, render_template, redirect
from ..helpers.cache import load, find

app = Blueprint("town", __name__, template_folder="")

@app.route("/towns/<identifier>")
def town(identifier):
    data = find(load("towns.json", "towns"), identifier)
    if not data:
        return "", 404
    data_uuid = data.get("uuid", "")
    if data_uuid and data_uuid != identifier:
        return redirect(f"/towns/{data_uuid}", 301)
    return render_template("town.html", data=data)
