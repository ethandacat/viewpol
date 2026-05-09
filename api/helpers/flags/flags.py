"""
Flags API — proxy + cache for EarthPol CDN flags.

Image bytes are NEVER loaded into Python RAM.
Disk hits are served via send_file() — the OS page cache handles it.
The old in-memory (_mem) dict has been removed: it stored raw PNG bytes
per flag and never evicted entries that stopped being requested (e.g.
after a siege ended), causing unbounded RAM growth.

Endpoints:
  GET /api/flag/nation/<name>  – nation flag, SVG fallback
  GET /api/flag/town/<name>    – town flag, SVG fallback
"""
from flask import Blueprint, Response, send_file
import os, time, hashlib, requests as reqs
from pathlib import Path

app = Blueprint("flags", __name__)

DATA_DIR  = Path(os.environ.get("DATA_DIR", "data"))
CACHE_DIR = DATA_DIR / "flag_cache"
CDN_BASE  = "https://cdn.earthpol.com"

DISK_TTL  = 86400   # 24 h — keep cached PNGs on disk
MISS_TTL  = 3600    # 1 h  — remember known 404s

_http = reqs.Session()
_http.headers.update({"User-Agent": "viewpol/1.0", "Accept": "image/*"})


# ── helpers ──────────────────────────────────────────────────────────

def _svg_fallback(name: str) -> Response:
    label = (name.replace("&", "&amp;")
                 .replace("<", "&lt;")
                 .replace(">", "&gt;")
                 .upper())
    size = 10 if len(name) > 18 else 13 if len(name) > 12 else 15
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 100">'
        f'<rect width="200" height="100" fill="#272727"/>'
        f'<text x="100" y="50" font-family="Inter,Arial,sans-serif" font-size="{size}"'
        f' font-weight="600" fill="rgba(255,255,255,0.45)" text-anchor="middle"'
        f' dominant-baseline="middle" letter-spacing="2">{label}</text>'
        f'</svg>'
    )
    return Response(svg, mimetype="image/svg+xml",
                    headers={"Cache-Control": "public, max-age=86400"})


def _cache_key(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()


def _try_cdn(url: str) -> Path | None:
    """
    Returns a Path to the cached PNG file on success, None on miss/error.
    No image bytes ever enter Python RAM — callers use send_file().
    """
    key       = _cache_key(url)
    hit_path  = CACHE_DIR / f"{key}.png"
    miss_path = CACHE_DIR / f"{key}.miss"

    # 1. Disk hit cache
    if hit_path.exists():
        age = time.time() - hit_path.stat().st_mtime
        if age < DISK_TTL:
            return hit_path
        hit_path.unlink(missing_ok=True)

    # 2. Disk miss cache (known 404 — don't hammer CDN)
    if miss_path.exists():
        if time.time() - miss_path.stat().st_mtime < MISS_TTL:
            return None
        miss_path.unlink(missing_ok=True)

    # 3. Live CDN fetch
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        r  = _http.get(url, timeout=1, allow_redirects=True)
        ct = r.headers.get("Content-Type", "")
        if r.status_code == 200 and ct.startswith("image/"):
            hit_path.write_bytes(r.content)
            r.close()
            return hit_path
        r.close()
    except Exception:
        pass

    miss_path.touch()
    return None


def _resolve(cdn_paths: list[str], fallback_name: str) -> Response:
    for path in cdn_paths:
        disk_path = _try_cdn(f"{CDN_BASE}/{path}")
        if disk_path:
            return send_file(str(disk_path), mimetype="image/png",
                             max_age=86400, conditional=True)
    return _svg_fallback(fallback_name)


# ── routes ────────────────────────────────────────────────────────────

@app.route("/api/flag/nation/<name>")
def flag_nation(name: str):
    cdn = name.replace(" ", "_")
    return _resolve([f"nations/{cdn}.png"], name)


@app.route("/api/flag/town/<name>")
def flag_town(name: str):
    cdn = name.replace(" ", "_")
    return _resolve([f"towns/{cdn}.png"], name)
