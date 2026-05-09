from flask import Blueprint
from datetime import datetime, timezone
import gc

# Register malloc_trim as a GC callback — fires automatically after every
# collection, returning freed heap pages to the OS on Linux.
try:
    import ctypes
    _libc = ctypes.cdll.LoadLibrary("libc.so.6")
    def _gc_callback(phase, info):
        if phase == "stop":
            _libc.malloc_trim(0)
    gc.callbacks.append(_gc_callback)
except Exception:
    pass

UTC = timezone.utc

app = Blueprint("extras", __name__, template_folder="")

@app.app_template_filter('datetimeformat')
def datetimeformat(value):
    # value is in seconds
    dt = datetime.fromtimestamp(value, UTC)
    return dt.strftime("%B %d, %Y %I:%M %p UTC")

@app.after_app_request
def _release_memory(response):
    """Trigger a GC cycle after every request. The registered gc.callback
    will call malloc_trim(0) automatically when collection finishes."""
    gc.collect()
    return response
