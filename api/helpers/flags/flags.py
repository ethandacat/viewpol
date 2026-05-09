"""
Flags API — proxy + cache for EarthPol CDN flags.

Endpoints:
  GET /api/flag/nation/<name>   – nation flag, SVG fallback
  GET /api/flag/town/<name>     – town flag, SVG fallback
  GET /api/flag/faction/<name>  – try nation CDN, then town CDN, then SVG
                                  (used by siege pages where attacker = nation = town name)
"""
from flask import Blueprint, Response, send_file
import os, time, hashlib, requests as reqs
from pathlib import Path

app = Blueprint("flags", __name__)

DATA_DIR  = Path(os.environ.get("DATA_DIR", "data"))
CACHE_DIR = DATA_DIR / "flag_cache"
CDN_BASE  = "https://cdn.earthpol.com"

# In-memory hot cache:  url → (bytes, mimetype, fetched_at)
_mem: dict = {}
MEM_TTL   = 300     # 5 min in-memory
DISK_TTL  = 86400   # 24 h disk hit cache
MISS_TTL  = 3600    # 1 h "known 404" cache

_http = reqs.Session()
_http.headers.update({"User-Agent": "viewpol/1.0", "Accept": "image/*"})


# ── helpers ──────────────────────────────────────────────────────

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


def _try_cdn(url: str):
    """Return (bytes, mimetype) on success, None on miss/error."""
    key = _cache_key(url)

    # 1. Memory cache
    hit = _mem.get(key)
    if hit:
        data, mime, ts = hit
        if time.time() - ts < MEM_TTL:
            return data, mime
        del _mem[key]

    # 2. Disk hit cache
    hit_path = CACHE_DIR / f"{key}.png"
    if hit_path.exists():
        age = time.time() - hit_path.stat().st_mtime
        if age < DISK_TTL:
            data = hit_path.read_bytes()
            _mem[key] = (data, "image/png", time.time())
            return data, "image/png"
        hit_path.unlink(missing_ok=True)

    # 3. Disk miss cache (known 404)
    miss_path = CACHE_DIR / f"{key}.miss"
    if miss_path.exists():
        if time.time() - miss_path.stat().st_mtime < MISS_TTL:
            return None
        miss_path.unlink(missing_ok=True)

    # 4. Live CDN fetch
    try:
        r = _http.get(url, timeout=4, allow_redirects=True)
        ct = r.headers.get("Content-Type", "")
        if r.status_code == 200 and ct.startswith("image/"):
            data = r.content
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            hit_path.write_bytes(data)
            _mem[key] = (data, "image/png", time.time())
            return data, "image/png"
    except Exception:
        pass

    # Cache miss so we don't hammer CDN
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    miss_path.touch()
    return None


def _resolve(cdn_paths: list[str], fallback_name: str) -> Response:
    for path in cdn_paths:
        result = _try_cdn(f"{CDN_BASE}/{path}")
        if result:
            data, mime = result
            return Response(data, mimetype=mime,
                            headers={"Cache-Control": "public, max-age=86400"})
    return _svg_fallback(fallback_name)


# ── routes ───────────────────────────────────────────────────────

@app.route("/api/flag/nation/<name>")
def flag_nation(name: str):
    cdn = name.replace(" ", "_")
    return _resolve([f"nations/{cdn}.png"], name)


@app.route("/api/flag/town/<name>")
def flag_town(name: str):
    cdn = name.replace(" ", "_")
    return _resolve([f"towns/{cdn}.png"], name)


@app.route("/api/flag/faction/<name>")
def flag_faction(name: str):
    """Nation → town fallback (siege pages pass same name for both)."""
    cdn = name.replace(" ", "_")
    return _resolve([f"nations/{cdn}.png", f"towns/{cdn}.png"], name)
