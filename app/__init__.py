from flask import Flask

from .routes import bp
from .storage import init_storage


def create_app():
    app = Flask(__name__)
    app.json.ensure_ascii = False

    init_storage()
    app.register_blueprint(bp)

    return app
