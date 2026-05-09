from flask import Blueprint, Response, send_file
import requests, os, time, hashlib
from pathlib import Path

app = Blueprint('skin', __name__)

DATA_DIR  = Path(os.environ.get("DATA_DIR", "data"))
SKIN_DIR  = DATA_DIR / "skin_cache"
DISK_TTL  = 3600   # 1 h — re-fetch after this
MISS_TTL  = 300    # 5 min — remember known misses

_http = requests.Session()
_http.headers.update({"User-Agent": "viewpol/1.0"})


def _cache_paths(username: str):
    key = hashlib.md5(username.lower().encode()).hexdigest()
    return SKIN_DIR / f"{key}.png", SKIN_DIR / f"{key}.miss"


@app.route('/skin/<path:username>')
def get_skin(username):
    hit_path, miss_path = _cache_paths(username)

    # 1. Disk hit
    if hit_path.exists() and time.time() - hit_path.stat().st_mtime < DISK_TTL:
        return send_file(str(hit_path), mimetype="image/png",
                         max_age=3600, conditional=True)

    # 2. Known miss
    if miss_path.exists() and time.time() - miss_path.stat().st_mtime < MISS_TTL:
        return Response(status=404)

    # 3. Live fetch
    SKIN_DIR.mkdir(parents=True, exist_ok=True)
    try:
        r = _http.get(f'https://api.mcheads.org/skin/{username}', timeout=6)
        if r.ok:
            hit_path.write_bytes(r.content)
            miss_path.unlink(missing_ok=True)
            r.close()
            return send_file(str(hit_path), mimetype="image/png",
                             max_age=3600, conditional=True)
        r.close()
    except Exception:
        pass

    miss_path.touch()
    return Response(status=503)
