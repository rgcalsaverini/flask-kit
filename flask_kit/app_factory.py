from flask import Flask
from flask_cors import CORS
from flask_talisman import Talisman, DENY

from .config import AppConfig

two_years = 63072000


def create_app(configs=None, blueprints=None, https=True, hsts_age=two_years,
               hsts_preload=False):
    """
    Flask app factory
    :param configs: Dict-like object with flask configs
    :param blueprints: optional list of blueprints to register
    :param https: Force https
    :param hsts_age: Max age for HSTS header
    :param hsts_preload: Set preload for HSTS header
    :return:
    """
    app = Flask(__name__)

    if configs:
        AppConfig(app, configs)

    if https:
        Talisman(app,
                 frame_options=DENY,
                 force_https=https,
                 session_cookie_secure=https,
                 strict_transport_security=True,
                 strict_transport_security_preload=hsts_preload,
                 strict_transport_security_include_subdomains=True,
                 strict_transport_security_max_age=hsts_age)
    else:
        Talisman(app,
                 frame_options=DENY,
                 force_https=False,
                 session_cookie_secure=False)

    CORS(app)

    for bp in blueprints or []:
        app.register_blueprint(bp)
    return app
