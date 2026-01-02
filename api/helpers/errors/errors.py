from flask import Blueprint, render_template

app = Blueprint("errors", __name__, template_folder="")

@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404
