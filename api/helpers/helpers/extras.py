from flask import Blueprint
from datetime import datetime, timezone
import gc

try:
    import ctypes
    _libc = ctypes.cdll.LoadLibrary("libc.so.6")
    def _trim(): _libc.malloc_trim(0)
except Exception:
    def _trim(): pass

UTC = timezone.utc

app = Blueprint("extras", __name__, template_folder="")

@app.app_template_filter('datetimeformat')
def datetimeformat(value):
    # value is in seconds
    dt = datetime.fromtimestamp(value, UTC)
    return dt.strftime("%B %d, %Y %I:%M %p UTC")

@app.after_app_request
def _release_memory(response):
    """Return freed Python heap pages to the OS after every request.
    Prevents RSS from climbing to peak-request watermark and staying there.
    gc.collect() catches any reference cycles; malloc_trim(0) tells glibc
    to actually hand the free pages back to the kernel (Linux only; no-op
    on other platforms via the fallback above)."""
    gc.collect()
    _trim()
    return response
