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
def _title_case(s: str) -> str:
    """Matches shops.html titleCase: lowercase then capitalize each word."""
    return s.lower().replace("_", " ").title()


def get_display_name(item: dict) -> str:
    """Exact equivalent of shops.html createCard display name logic."""
    raw_item_id = item.get("item") if isinstance(item.get("item"), str) else "unknown"
    meta = item.get("meta")
    raw_name = None
    if meta:
        dn = meta.get("display-name")
        if isinstance(dn, dict):
            extra = dn.get("extra") or []
            if extra and isinstance(extra[0], dict) and isinstance(extra[0].get("text"), str):
                raw_name = extra[0]["text"]
    if not raw_name:
        raw_name = raw_item_id.replace("_", " ")
    return _title_case(raw_name or "Unknown Item")


def get_name_color(item: dict) -> str:
    meta = item.get("meta")
    if not meta:
        return "#FFFFFF"
    dn = meta.get("display-name")
    if isinstance(dn, dict):
        extra = dn.get("extra") or []
        if extra and isinstance(extra[0], dict) and extra[0].get("text"):
            return "#FF55FF"
    if meta.get("enchants") or meta.get("stored-enchants"):
        return "#55FFFF"
    return "#FFFFFF"


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

    display_name = get_display_name(reqdata["item"])
    name_color   = get_name_color(reqdata["item"])

    return render_template(
        "shop.html",
        data=reqdata,
        username=username,
        display_name=display_name,
        name_color=name_color,
    )