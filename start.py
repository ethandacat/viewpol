#!/usr/bin/env python3
"""
ViewPol launcher — starts and babysits all three processes:
  1. Gunicorn  (Flask web app)
  2. poller.py (server-status, every 1 min)
  3. history_poller.py (balance/price/KitPvP, every 1 h)

Usage:
    python3 start.py
    python3 start.py --port 8000 --workers 1
"""

import subprocess, sys, time, signal, os, argparse
from pathlib import Path

HERE = Path(__file__).resolve().parent

# ── Config ────────────────────────────────────────────────────────────────────

parser = argparse.ArgumentParser(description="Start all ViewPol services")
parser.add_argument("--port",    default="8000",  help="Gunicorn bind port (default 8000)")
parser.add_argument("--workers", default="1",     help="Gunicorn worker count (default 1)")
parser.add_argument("--host",    default="0.0.0.0", help="Gunicorn bind host (default 0.0.0.0)")
args = parser.parse_args()

PYTHON   = sys.executable
SERVICES = [
    {
        "name": "gunicorn",
        "cmd":  ["gunicorn",
                 "-w", args.workers,
                 "-b", f"{args.host}:{args.port}",
                 "--access-logfile", "-",
                 "--max-requests", "1000",
                 "--max-requests-jitter", "100",
                 "wsgi:app"],
    },
    {
        "name": "data_fetcher",
        "cmd":  [PYTHON, "data_fetcher.py"],
    },
    {
        "name": "poller",
        "cmd":  [PYTHON, "poller.py"],
    },
    {
        "name": "history_poller",
        "cmd":  [PYTHON, "history_poller.py"],
    },
]

WATCHDOG_INTERVAL = 15   # seconds between health checks

# ── Process tracking ──────────────────────────────────────────────────────────

procs: dict[str, subprocess.Popen] = {}


def start(svc: dict) -> subprocess.Popen:
    name = svc["name"]
    p = subprocess.Popen(
        svc["cmd"],
        cwd=HERE,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
    print(f"[start.py] ▶  {name} started (pid {p.pid})", flush=True)
    return p


def stop_all():
    print("\n[start.py] Shutting down…", flush=True)
    for name, p in procs.items():
        if p.poll() is None:
            print(f"[start.py] ■  stopping {name} (pid {p.pid})", flush=True)
            p.terminate()
    # Give them a moment, then force-kill anything still alive
    time.sleep(3)
    for name, p in procs.items():
        if p.poll() is None:
            print(f"[start.py] ✕  force-killing {name} (pid {p.pid})", flush=True)
            p.kill()
    print("[start.py] All services stopped.", flush=True)


def handle_signal(sig, frame):
    stop_all()
    sys.exit(0)


signal.signal(signal.SIGINT,  handle_signal)
signal.signal(signal.SIGTERM, handle_signal)

# ── Launch all services ───────────────────────────────────────────────────────

print(f"[start.py] ViewPol starting — cwd: {HERE}", flush=True)

for svc in SERVICES:
    procs[svc["name"]] = start(svc)

# ── Watchdog loop ─────────────────────────────────────────────────────────────

svc_map = {svc["name"]: svc for svc in SERVICES}

while True:
    time.sleep(WATCHDOG_INTERVAL)
    for name, p in list(procs.items()):
        rc = p.poll()
        if rc is not None:
            print(f"[start.py] ⚠  {name} exited (code {rc}) — restarting…", flush=True)
            procs[name] = start(svc_map[name])
