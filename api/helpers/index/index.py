from flask import Blueprint, render_template

app = Blueprint("index", __name__, template_folder="")

@app.route("/")
def index():
    return render_template("index.html")