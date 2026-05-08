import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from api.index import create_app
app = create_app()
