"""
Disk-backed lookup cache for all Flask route handlers.

LookupCache watches a file's mtime and rebuilds only when the file
actually changes. Subsequent requests hit an in-memory dict — O(1)
by UUID or name, zero I/O, zero re-parsing.

data_fetcher.py writes fresh JSON; mtime changes; next request
triggers a single rebuild. Memory stays at one copy per dataset.
"""

import json, os, gc
from pathlib import Path

DATA_DIR = Path(os.environ.get("DATA_DIR", "data"))


class LookupCache:
    """One instance per JSON file. Thread-safe for reads (GIL); rebuilds are
    rare (file-mtime gated) so the brief window where old data is replaced is fine."""

    __slots__ = ("_path", "_mtime", "_all", "_by_uuid", "_by_name")

    def __init__(self, filename: str):
        self._path    = DATA_DIR / filename
        self._mtime   = -1.0
        self._all     = []
        self._by_uuid: dict = {}
        self._by_name: dict = {}

    def _refresh(self):
        try:
            mtime = self._path.stat().st_mtime
        except FileNotFoundError:
            return
        if mtime == self._mtime:
            return                          # file unchanged — nothing to do

        try:
            data = json.loads(self._path.read_bytes())
        except Exception:
            return

        by_uuid: dict = {}
        by_name: dict = {}
        for item in (data if isinstance(data, list) else []):
            uuid = item.get("uuid", "")
            name = item.get("name", "")
            if uuid:
                by_uuid[uuid] = item
            if name:
                by_name[name.lower()] = item
                # also index underscore variant
                spaced = " ".join(name.split("_"))
                if spaced != name:
                    by_name[spaced.lower()] = item

        # Replace atomically so readers always see a consistent snapshot
        self._all     = data if isinstance(data, list) else []
        self._by_uuid = by_uuid
        self._by_name = by_name
        self._mtime   = mtime
        gc.collect()                        # free the old dicts promptly

    # ── Public API ────────────────────────────────────────────────────

    def all(self) -> list:
        self._refresh()
        return self._all

    def find(self, identifier: str) -> dict | None:
        self._refresh()
        return (self._by_uuid.get(identifier)
                or self._by_name.get(identifier.lower()))

    def raw(self) -> bytes | None:
        """Return raw file bytes (used by shops.py which needs codecs.decode)."""
        try:
            return self._path.read_bytes()
        except Exception:
            return None


# ── Module-level singletons ───────────────────────────────────────────

_players  = LookupCache("players.json")
_towns    = LookupCache("towns.json")
_nations  = LookupCache("nations.json")
# NOTE: sieges.json is a dict {sieges:[...], battleSessionTimeTill:..., ...}
# so it cannot go through LookupCache (which only stores lists). Read it
# directly from disk in load_sieges() / load("sieges.json").


def players_cache()  -> LookupCache: return _players
def towns_cache()    -> LookupCache: return _towns
def nations_cache()  -> LookupCache: return _nations


# ── Convenience wrappers (keep backward compat with old load/find API) ─

def load(filename: str, fallback_endpoint: str | None = None) -> list | dict:
    """Legacy: used by index.py for counts. Returns the cached list."""
    # Map to a singleton if we have one (list-structured files only)
    _map = {
        "players.json": _players,
        "towns.json":   _towns,
        "nations.json": _nations,
    }
    if filename in _map:
        return _map[filename].all()

    # Unmanaged or dict-structured file — just read from disk
    path = DATA_DIR / filename
    try:
        return json.loads(path.read_bytes())
    except Exception:
        return []


def find(data: list, identifier: str) -> dict | None:
    """Legacy: linear scan fallback (used when caller already has the list)."""
    ident_lower = identifier.lower()
    match = next((x for x in data if x.get("uuid") == identifier), None)
    if match:
        return match
    return next((x for x in data
                 if x.get("name", "").lower() == ident_lower
                 or " ".join(x.get("name", "").split("_")).lower() == ident_lower),
                None)
