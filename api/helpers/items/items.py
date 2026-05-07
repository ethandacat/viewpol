from flask import Blueprint, render_template
from ..shops.shops import load_shops
from ..shop.shop import get_display_name, get_name_color

app = Blueprint("items", __name__, template_folder="")


def _group_items(shops):
    items = {}
    for s in shops:
        item_id = s["item"]["item"].lower()
        if item_id not in items:
            items[item_id] = {
                "item_id": item_id,
                "display_name": get_display_name(s["item"]),
                "buying": 0,
                "selling": 0,
            }
        t = s.get("type", "UNKNOWN")
        if t == "BUYING" and s.get("space", 0) > 0:
            items[item_id]["buying"] += 1
        elif t == "SELLING" and s.get("stock", 0) > 0:
            items[item_id]["selling"] += 1
    return sorted(items.values(), key=lambda x: x["display_name"])


@app.route("/items")
def items_page():
    shops = load_shops()
    items = _group_items(shops)
    return render_template("items.html", items=items)


@app.route("/items/<item_id>")
def item_page(item_id):
    shops = load_shops()
    matched = [s for s in shops if s["item"]["item"].lower() == item_id.lower()]
    if not matched:
        return "", 404

    buying  = sorted([s for s in matched if s.get("type") == "BUYING"],
                     key=lambda x: x["unit_price"], reverse=True)
    selling = sorted([s for s in matched if s.get("type") == "SELLING"],
                     key=lambda x: x["unit_price"])

    return render_template(
        "item.html",
        item_id=item_id,
        display_name=get_display_name(matched[0]["item"]),
        name_color=get_name_color(matched[0]["item"]),
        buying=buying,
        selling=selling,
    )
