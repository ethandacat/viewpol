from flask import Blueprint
from datetime import datetime, UTC

app = Blueprint("extras", __name__, template_folder="")

@app.app_template_filter('datetimeformat')
def datetimeformat(value):
    # value is in seconds
    dt = datetime.fromtimestamp(value, UTC)
    return dt.strftime("%B %d, %Y %I:%M %p UTC")