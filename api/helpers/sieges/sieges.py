from flask import Blueprint, render_template, redirect
import requests as reqs

app = Blueprint("sieges", __name__, template_folder="")

session = reqs.Session()
session.headers.update({
    "User-Agent": "earthpol-web/1.0",
    "Accept": "application/json",
})


def load_sieges():
    return session.get("https://api.earthpol.com/astra/sieges").json()


@app.route("/sieges")
def sieges_page():
    data = load_sieges()
    sieges = sorted(
        [_recalc_points(s) for s in data.get("sieges", [])],
        key=lambda s: (not s.get("isActive", False), -(s.get("endedAtMillis") or 0)),
    )
    active_count = sum(1 for s in sieges if s.get("isActive", False))
    time_till = data.get("battleSessionTimeTill", 0)
    time_remaining = data.get("battleSessionTimeRemaining", 0)
    return render_template(
        "sieges.html",
        sieges=sieges,
        active_count=active_count,
        time_till=time_till,
        time_remaining=time_remaining,
    )


def _recalc_points(siege):
    """Always recompute scores from battle session events — never trust API values."""
    att, dff = 0, 0
    for bs in siege.get("battleSessions") or []:
        for k in bs.get("kills", []):
            killer_side = k["killer"]["side"]
            victim_side = k["victim"]["side"]
            netting = _opposite(victim_side) if killer_side.upper() == "NOBODY" else killer_side.capitalize()
            pts = k.get("points", 0) or 0
            if netting == "Attacker":
                att += pts
            else:
                dff += pts
        for bc in bs.get("bannerControl", []):
            pts = bc.get("points", 0) or 0
            if bc.get("awardingSide", "").capitalize() == "Attacker":
                att += pts
            else:
                dff += pts
    siege["attackerPoints"] = att
    siege["defenderPoints"] = dff
    siege["balance"]        = att - dff
    return siege


def _opposite(side):
    return "Defender" if side.upper() == "ATTACKER" else "Attacker"


def _process_sessions(raw_sessions):
    out = []
    for bs in raw_sessions:
        events = []
        for k in bs.get("kills", []):
            killer_side = k["killer"]["side"]
            victim_side = k["victim"]["side"]
            if killer_side.upper() == "NOBODY":
                events.append({
                    "type": "kill",
                    "timestamp": k.get("timestamp", 0),
                    "text_parts": {
                        "victim": k["victim"]["name"],
                        "victim_side": victim_side.capitalize(),
                        "netting_side": _opposite(victim_side),
                        "points": k.get("points", 0),
                        "natural_death": True,
                    },
                })
            else:
                events.append({
                    "type": "kill",
                    "timestamp": k.get("timestamp", 0),
                    "text_parts": {
                        "killer": k["killer"]["name"],
                        "killer_side": killer_side.capitalize(),
                        "victim": k["victim"]["name"],
                        "netting_side": killer_side.capitalize(),
                        "points": k.get("points", 0),
                        "natural_death": False,
                    },
                })
        for bc in bs.get("bannerControl", []):
            side = bc["awardingSide"].capitalize()
            events.append({
                "type": "banner",
                "timestamp": bc.get("timestamp", 0),
                "text_parts": {
                    "side": side,
                    "controllers": bc.get("controllersCount", 0),
                    "points": bc.get("points", 0),
                },
            })
        events.sort(key=lambda e: e["timestamp"])

        # Compress consecutive banner events with the same side + controller count
        compressed = []
        for ev in events:
            if (ev["type"] == "banner" and compressed and
                    compressed[-1]["type"] == "banner" and
                    compressed[-1]["text_parts"]["side"] == ev["text_parts"]["side"] and
                    compressed[-1]["text_parts"]["controllers"] == ev["text_parts"]["controllers"]):
                compressed[-1]["text_parts"]["points"] += ev["text_parts"]["points"]
                compressed[-1]["text_parts"]["count"] += 1
            else:
                if ev["type"] == "banner":
                    ev["text_parts"]["count"] = 1
                compressed.append(ev)

        out.append({
            "sessionNumber": bs.get("sessionNumber", 0),
            "startedAtMillis": bs.get("startedAtMillis"),
            "endedAtMillis": bs.get("endedAtMillis"),
            "events": compressed,
        })
    return out


def _build_chart_data(siege):
    """Cumulative attacker/defender points over time across all sessions."""
    events = []
    for bs in siege.get("battleSessions") or []:
        for k in bs.get("kills", []):
            killer_side = k["killer"]["side"]
            victim_side = k["victim"]["side"]
            netting = _opposite(victim_side) if killer_side.upper() == "NOBODY" else killer_side.capitalize()
            events.append({"ts": k.get("timestamp", 0), "side": netting, "pts": k.get("points", 0)})
        for bc in bs.get("bannerControl", []):
            events.append({"ts": bc.get("timestamp", 0), "side": bc["awardingSide"].capitalize(), "pts": bc.get("points", 0)})

    events.sort(key=lambda e: e["ts"])

    att, deff = 0, 0
    chart = []
    for e in events:
        if e["side"] == "Attacker": att += e["pts"]
        else: deff += e["pts"]
        chart.append({"ts": e["ts"], "attacker": att, "defender": deff})

    return chart


@app.route("/sieges/<identifier>")
def siege_page(identifier):
    data = load_sieges()
    sieges = data.get("sieges", [])
    # Try UUID match first, then name match
    siege = next((s for s in sieges if s.get("uuid", "") == identifier), None)
    if siege is None:
        siege = next((s for s in sieges if s.get("name", "").lower() == identifier.lower()), None)
        if siege is None:
            return "", 404
        return redirect(f"/sieges/{siege['uuid']}", 301)
    siege = _recalc_points(siege)
    battle_sessions = _process_sessions(siege.get("battleSessions") or [])
    chart_data      = _build_chart_data(siege)
    return render_template("siege.html", siege=siege, battle_sessions=battle_sessions, chart_data=chart_data)
