import unittest

from flask import Blueprint

from flask_kit import create_app


def create_testing_app(*args, **kwargs):
    app = create_app(*args, **kwargs)
    app.config['TESTING'] = True
    client = app.test_client()
    return app, client


class TestApp(unittest.TestCase):
    def test_create(self):
        create_app()

    def test_basic(self):
        bp = Blueprint('bp', __name__)

        @bp.route('/route')
        def route():
            return 'route'

        app, client = create_testing_app(blueprints=[bp], https=False)
        resp = client.get('/route')
        self.assertEquals(resp.status_code, 200)
        self.assertEquals(resp.data, b'route')
        self.assertEquals(resp.headers.get('Access-Control-Allow-Origin'), '*')
        self.assertIn(resp.headers.get('X-Frame-Options'), ['DENY', 'SAMEORIGIN'])
        self.assertIsNotNone(resp.headers.get('Content-Security-Policy', None))

    def test_https(self):
        bp = Blueprint('bp', __name__)

        @bp.route('/')
        def route():
            return 'route'

        app, client = create_testing_app(blueprints=[bp], https=True)
        resp = client.get('/')
        self.assertIn(resp.status_code, [302, 301])
        self.assertEquals(resp.headers.get('Location'), 'https://localhost/')

