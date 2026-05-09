"""
Disk-only data access — no in-memory cache between requests.

Every call reads fresh from disk. data_fetcher.py keeps the files
current so reads are always local (fast). Nothing persists in RAM
after the request function returns.
"""

import json, os
from pathlib import Path
from typing import Union, Optional

DATA_DIR = Path(os.environ.get("DATA_DIR", "data"))


def load(filename: str) -> Union[list, dict]:
    """Read and parse a JSON file from DATA_DIR. Returns [] on any error."""
    try:
        return json.loads((DATA_DIR / filename).read_bytes())
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
    # UUID match first (exact)
    match = next((x for x in data if x.get("uuid") == identifier), None)
    if match:
        return match
    # Name match
    return next(
        (x for x in data
         if x.get("name", "").lower() == ident_lower
         or " ".join(x.get("name", "").split("_")).lower() == ident_lower),
        None,
    )
