import os, signal, threading, time, random

# Recycle each worker after this many seconds regardless of request count.
# Caps RSS growth from pymalloc arena fragmentation that accumulates over time.
WORKER_LIFETIME = 300   # 5 minutes — tune down if RSS still climbs

def post_fork(server, worker):
    def _recycle():
        # Jitter ±30 s so two workers started together don't both restart at once
        delay = WORKER_LIFETIME + random.uniform(-30, 30)
        time.sleep(max(60, delay))
        os.kill(os.getpid(), signal.SIGTERM)
    t = threading.Thread(target=_recycle, daemon=True)
    t.start()
