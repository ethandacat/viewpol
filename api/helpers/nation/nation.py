from flask import Blueprint, render_template, redirect
from ..helpers.cache import nations_cache

app = Blueprint("nation", __name__, template_folder="")

@app.route("/nations/<identifier>")
def nation(identifier):
    data = nations_cache().find(identifier)
    if not data:
        return "", 404
    data_uuid = data.get("uuid", "")
    if data_uuid and data_uuid != identifier:
        return redirect(f"/nations/{data_uuid}", 301)
    return render_template("nation.html", data=data)
