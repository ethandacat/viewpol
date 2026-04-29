import requests as reqs
import itemstack
import json
from pathlib import Path
from rich.console import Console
from rich.table import Table

console = Console()

# === EarthPol API setup ===
requests = reqs.Session()
requests.headers.update(
    {
        "User-Agent": "earthpol-web/1.0",
        "Accept": "application/json",
    }
)

SHOP_API_URL = "https://api.earthpol.com/astra/shops"

def get_all_shops():
    resp = requests.get(SHOP_API_URL)
    resp.raise_for_status()
    data = resp.json()

    for shop in data:
        shop["item"] = itemstack.parse(shop["item"])
        qty = int(shop["item"].get("amount", 0))
        price = float(round(float(shop["price"])))
        shop["unit_price"] = price / qty if qty > 0 else float("inf")
    return data

# === Profitable EarthPol trades ===
def get_profitable_trades():
    shops = get_all_shops()
    selling = [s for s in shops if s["type"] == "SELLING"]
    buying = [b for b in shops if b["type"] == "BUYING" and b.get("space", 0) > 0]

    opportunities = []
    for sell in selling:
        for buy in buying:
            if sell["item"] != buy["item"]:
                continue
            if sell["unit_price"] >= buy["unit_price"]:
                continue

            sell_stacks = sell.get("stock", 0)
            buy_space = buy.get("space", 0)
            units_per_stack = int(sell["item"].get("amount", 0))
            max_stacks = min(sell_stacks, buy_space)
            total_units = max_stacks * units_per_stack
            if total_units <= 0:
                continue

            total_profit = total_units * (buy["unit_price"] - sell["unit_price"])
            opportunities.append({
                "item": sell["item"],
                "buy_from": sell,
                "sell_to": buy,
                "stacks_traded": max_stacks,
                "total_profit": total_profit,
            })

    opportunities.sort(key=lambda x: x["total_profit"], reverse=True)
    return opportunities

# === Print simplified arbitrage results ===
def print_arbitrage(opportunities):
    if not opportunities:
        console.print("[bold yellow]No profitable trades found.[/bold yellow]")
        return

    table = Table(title="EarthPol Profitable Trades", header_style="bold cyan")
    table.add_column("Item", overflow="fold")
    table.add_column("Buy From", style="green")
    table.add_column("Sell To", style="blue")
    table.add_column("Profit %", justify="right")
    table.add_column("Total Profit", justify="right", style="bold green")

    for trade in opportunities:
        buy_price = trade["buy_from"]["unit_price"]
        sell_price = trade["sell_to"]["unit_price"]
        profit_percent = ((sell_price - buy_price) / buy_price) * 100

        table.add_row(
            json.dumps(trade["item"], ensure_ascii=False),
            trade["buy_from"].get("owner", "unknown"),
            trade["sell_to"].get("owner", "unknown"),
            f"{profit_percent:.2f}%",
            f"{trade['total_profit']:.2f}"
        )

    console.print(table)

# === Load custom Minecraft recipes ===
RECIPES_PATH = Path("minecraft_recipes.json")  # single JSON file in your format

def load_recipes():
    with open(RECIPES_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    normalized = []
    for r in data:
        result_name, result_count = r["give"]
        ingredients = []
        # flatten 2D grid into list of (item_name, count) tuples
        for row in r["have"]:
            for item in row:
                if item != "null":
                    ingredients.append((item, 1))
        normalized.append({
            "result": result_name,
            "count": result_count,
            "ingredients": ingredients,
        })
    return normalized

# === Compute crafting profit ===
def compute_crafting_profit(recipes, shops):
    price_map = {}
    for s in shops:
        item = s["item"].get("id") if isinstance(s["item"], dict) else None
        if item:
            price_map.setdefault(item, []).append(s["unit_price"])
        else:
            # fallback: match by name string
            name = s["item"].get("name")
            if name:
                price_map.setdefault(name, []).append(s["unit_price"])

    craft_profits = []
    for r in recipes:
        rid = r["result"]
        total_cost = 0
        valid = True
        for iid, needed in r["ingredients"]:
            if iid not in price_map:
                valid = False
                break
            total_cost += min(price_map[iid]) * needed
        if not valid or rid not in price_map:
            continue
        revenue = max(price_map[rid]) * r["count"]
        profit = revenue - total_cost
        if profit > 0:
            craft_profits.append({
                "recipe": rid,
                "profit_per_craft": profit,
                "cost": total_cost,
                "revenue": revenue,
                "ingredients": r["ingredients"]
            })

    craft_profits.sort(key=lambda x: x["profit_per_craft"], reverse=True)
    return craft_profits

# === Print crafting profit table ===
def print_crafting(craft_profits):
    if not craft_profits:
        console.print("[bold yellow]No profitable crafting recipes found.[/bold yellow]")
        return

    table = Table(title="Profitable Crafting Recipes", header_style="bold magenta")
    table.add_column("Item", overflow="fold")
    table.add_column("Profit %", justify="right")
    table.add_column("Profit", justify="right", style="bold green")
    table.add_column("Cost", justify="right")
    table.add_column("Revenue", justify="right")

    for c in craft_profits[:20]:  # top 20
        profit_percent = ((c["revenue"] - c["cost"]) / c["cost"]) * 100 if c["cost"] > 0 else 0
        table.add_row(
            c["recipe"],
            f"{profit_percent:.2f}%",
            f"{c['profit_per_craft']:.2f}",
            f"{c['cost']:.2f}",
            f"{c['revenue']:.2f}"
        )

    console.print(table)

# === Main execution ===
if __name__ == "__main__":
    shops = get_all_shops()

    console.print("\n[bold underline]EarthPol Arbitrage Opportunities[/bold underline]")
    arbitrage = get_profitable_trades()
    print_arbitrage(arbitrage)

    console.print("\n[bold underline]Minecraft Crafting Profit Opportunities[/bold underline]")
    recipes = load_recipes()
    craft_profits = compute_crafting_profit(recipes, shops)
    print_crafting(craft_profits)
