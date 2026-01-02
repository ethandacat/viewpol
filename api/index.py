from flask import Flask
from pathlib import Path

from api.helpers.helpers import extras
from api.helpers.index import index
from api.helpers.nation import nation
from api.helpers.nations import nations
from api.helpers.player import player
from api.helpers.players import players
from api.helpers.shop import shop
from api.helpers.shops import shops
from api.helpers.town import town
from api.helpers.towns import towns
from api.helpers.errors import errors


app = Flask(__name__, static_folder = "assets")

app.register_blueprint(extras.app)
app.register_blueprint(index.app)
app.register_blueprint(nation.app)
app.register_blueprint(nations.app)
app.register_blueprint(player.app)
app.register_blueprint(players.app)
app.register_blueprint(shop.app)
app.register_blueprint(shops.app)
app.register_blueprint(town.app)
app.register_blueprint(towns.app)
app.register_blueprint(errors.app)