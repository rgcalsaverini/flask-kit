from flask import Flask
from flask_cors import CORS
from flask_talisman import Talisman, DENY

from .config import AppConfig


def create_app(configs=None, blueprints=None, allow_credentials=False, https=True):
    """
    Flask app factory
    """
    app = Flask(__name__)

    if configs:
        AppConfig(app, configs)
    Talisman(app, frame_options=DENY, force_https=https,
             session_cookie_secure=https, )

    if allow_credentials:
        cors_headers = ["Content-Type", "Authorization",
                        "Access-Control-Allow-Credentials",
                        "Access-Control-Allow-Methods"]
        CORS(app, allow_headers=cors_headers, supports_credentials=True)
    else:
        CORS(app)

    for bp in blueprints or []:
        app.register_blueprint(bp)
    return app
