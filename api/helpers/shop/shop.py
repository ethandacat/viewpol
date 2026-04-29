from flask import Blueprint, render_template
import requests as reqs
from ..helpers import itemstack

app = Blueprint("shop", __name__, template_folder="")

requests = reqs.Session()
requests.headers.update({
    "User-Agent": "earthpol-web/1.0",
    "Accept": "application/json",
})


# -------------------------
# TYPE NORMALIZATION LAYER
# -------------------------
def normalize_shop_type(raw) -> str:
    if raw is None:
        return "UNKNOWN"

    raw = str(raw)

    # Strip Java object noise:
    # com.xxx.SellingType@hash -> SellingType
    cleaned = raw.split(".")[-1].split("@")[0]

    cleaned_upper = cleaned.upper()

    if "SELLING" in cleaned_upper:
        return "SELLING"
    if "BUYING" in cleaned_upper:
        return "BUYING"

    return "UNKNOWN"


@app.route("/shops/<int:id>")
def shop(id):
    req = requests.post(
        "https://api.earthpol.com/astra/shops",
        json={"query": [str(id)]}
    )

    if req.status_code != 200:
        return "", 404

    data = req.json()
    if not data:
        return "", 404

    reqdata = data[0]

    # parse item safely
    reqdata["item"] = itemstack.parse(reqdata["item"])

    # normalize type ONCE, guaranteed for template
    reqdata["type"] = normalize_shop_type(reqdata.get("type"))

    # fetch owner name safely
    owner_id = reqdata.get("owner")
    username = owner_id

    try:
        mojang = requests.get(
            f"https://api.mojang.com/user/profile/{owner_id}"
        )
        if mojang.status_code == 200:
            username = mojang.json().get("name", owner_id)
    except Exception:
        pass

    return render_template(
        "shop.html",
        data=reqdata,
        username=username
    )