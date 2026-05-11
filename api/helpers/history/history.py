"""
History API — read-only access to the SQLite history database.
Never caches anything in RAM; opens a fresh connection per request.

Endpoints:
  GET /api/history/player/<uuid>   → [{ts, balance}]
  GET /api/history/town/<uuid>     → [{ts, balance}]
  GET /api/history/nation/<uuid>   → [{ts, balance}]
  GET /api/history/item/<item_id>  → [{ts, best_sell, best_buy}]
  GET /api/history/kitpvp/<uuid>   → [{ts, kills, deaths, assists}]
"""
from flask import Blueprint, jsonify
import sqlite3, os
from pathlib import Path

app     = Blueprint("history", __name__)
DATA_DIR = Path(os.environ.get("DATA_DIR", "data"))
DB_PATH  = DATA_DIR / "history.db"


def _query(sql: str, params: tuple) -> list:
    if not DB_PATH.exists():
        return []
    con = None
    try:
        con = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        con.execute("PRAGMA journal_mode=WAL")
        return con.execute(sql, params).fetchall()
    except Exception:
        return []
    finally:
        if con:
            con.close()


@app.route("/api/history/player/<uuid>")
def player_history(uuid: str):
    rows = _query(
        "SELECT ts, balance FROM player_balance WHERE uuid=? ORDER BY ts",
        (uuid,))
    return jsonify([{"ts": r[0], "balance": r[1]} for r in rows])


@app.route("/api/history/town/<uuid>")
def town_history(uuid: str):
    rows = _query(
        "SELECT ts, balance FROM town_balance WHERE uuid=? ORDER BY ts",
        (uuid,))
    return jsonify([{"ts": r[0], "balance": r[1]} for r in rows])


@app.route("/api/history/nation/<uuid>")
def nation_history(uuid: str):
    rows = _query(
        "SELECT ts, balance FROM nation_balance WHERE uuid=? ORDER BY ts",
        (uuid,))
    return jsonify([{"ts": r[0], "balance": r[1]} for r in rows])


@app.route("/api/history/item/<path:item_id>")
def item_history(item_id: str):
    rows = _query(
        "SELECT ts, best_sell, best_buy FROM item_price WHERE item_id=? ORDER BY ts",
        (item_id.lower(),))
    return jsonify([{"ts": r[0], "best_sell": r[1], "best_buy": r[2]} for r in rows])


@app.route("/api/history/kitpvp/<uuid>")
def kitpvp_history(uuid: str):
    rows = _query(
        "SELECT ts, kills, deaths, assists FROM kitpvp_stats WHERE uuid=? ORDER BY ts",
        (uuid,))
    return jsonify([
        {"ts": r[0], "kills": r[1], "deaths": r[2], "assists": r[3]}
        for r in rows
    ])
