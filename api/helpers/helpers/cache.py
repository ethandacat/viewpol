"""
Mtime-gated in-memory cache — one copy per file, refreshed only when
data_fetcher.py writes a new version (~every 20s). Between refreshes,
all requests share the same deserialized object at zero cost.

Files larger than MAX_CACHE_BYTES are NOT stored in the cache; they are
read and parsed fresh on every miss. Set CACHE_MAX_BYTES in the environment
to tune the threshold (default 4 MB). The cache currently holds at most 4
files (players, towns, nations, sieges), so it is bounded by design.
"""

import json, os
from pathlib import Path
from threading import Lock
from typing import Union, Optional

DATA_DIR = Path(os.environ.get("DATA_DIR", "data"))

# Files larger than this will not be held in RAM — parsed fresh on every miss.
_MAX_CACHE_BYTES = int(os.environ.get("CACHE_MAX_BYTES", 4_000_000))  # 4 MB default

_store: dict = {}   # filename -> (mtime, data)
_lock  = Lock()


def load(filename: str) -> Union[list, dict]:
    """Return cached data if the file hasn't changed; otherwise reload from disk."""
    path = DATA_DIR / filename
    try:
        mtime = path.stat().st_mtime
        with _lock:
            entry = _store.get(filename)
            if entry and entry[0] == mtime:
                return entry[1]
        # File changed (or first load) — read outside the lock to avoid blocking
        raw  = path.read_bytes()
        data = json.loads(raw)
        if len(raw) <= _MAX_CACHE_BYTES:
            with _lock:
                _store[filename] = (mtime, data)
        return data
    except Exception:
        return []


def find(filename: str, identifier: str) -> Optional[dict]:
    """
    Load a list file and look up one item by UUID (exact) or name
    (case-insensitive, underscore-tolerant). Returns None if not found.
    """
    data = load(filename)
    if not isinstance(data, list):
        return None
    ident_lower = identifier.lower()
    match = next((x for x in data if x.get("uuid") == identifier), None)
    if match:
        return match
    return next(
        (x for x in data
         if x.get("name", "").lower() == ident_lower
         or " ".join(x.get("name", "").split("_")).lower() == ident_lower),
        None,
    )
