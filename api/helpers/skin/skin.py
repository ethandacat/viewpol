from flask import Blueprint, Response
import requests

app = Blueprint('skin', __name__)
_cache = {}

@app.route('/skin/<path:username>')
def get_skin(username):
    if username not in _cache:
        try:
            r = requests.get(f'https://api.mcheads.org/skin/{username}', timeout=6)
            if r.ok:
                _cache[username] = (r.content, r.headers.get('Content-Type', 'image/png'))
            else:
                return Response(status=r.status_code)
        except Exception:
            return Response(status=503)
    data, ct = _cache[username]
    return Response(data, mimetype=ct, headers={'Cache-Control': 'public, max-age=3600'})
