"""
Shared disk-cache reader for all Flask route handlers.

The data_fetcher.py process keeps these files continuously fresh.
If a file doesn't exist yet (first boot before fetcher runs),
we fall back to a single live request so the site still works.
"""

import json, os, requests as reqs
from pathlib import Path

DATA_DIR = Path(os.environ.get("DATA_DIR", "data"))

_http = reqs.Session()
_http.headers.update({"User-Agent": "viewpol/1.0", "Accept": "application/json"})

EARTHPOL = "https://api.earthpol.com/astra"


def load(filename: str, fallback_endpoint: str | None = None) -> list | dict:
    """
    Read JSON from a data_fetcher-maintained disk file.
    Falls back to a live GET if the file doesn't exist yet.
    """
    path = DATA_DIR / filename
    if path.exists():
        try:
            return json.loads(path.read_bytes())
        except Exception:
            pass

    # First-run fallback — file not written yet
    if fallback_endpoint:
        try:
            return _http.get(f"{EARTHPOL}/{fallback_endpoint}", timeout=20).json()
        except Exception:
            pass

    return []


def find(data: list, identifier: str) -> dict | None:
    """
    Look up a single item from a cached list by UUID (exact) or name
    (case-insensitive). Returns None if not found.
    """
    ident_lower = identifier.lower()
    # UUID match first
    match = next((x for x in data if x.get("uuid") == identifier), None)
    if match:
        return match
    # Name match
    return next((x for x in data
                 if x.get("name", "").lower() == ident_lower
                 or " ".join(x.get("name", "").split("_")).lower() == ident_lower),
                None)
