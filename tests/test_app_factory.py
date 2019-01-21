import unittest

from flask import Blueprint

from flask_kit import create_app

valid_frames = ['DENY', 'SAMEORIGIN']


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
        self.assertIn(resp.headers.get('X-Frame-Options'), valid_frames)
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
        self.assertIn(resp.headers.get('X-Frame-Options'), valid_frames)

    def test_hsts(self):
        bp = Blueprint('bp', __name__)

        @bp.route('/')
        def route():
            return 'route'

        app, client = create_testing_app(blueprints=[bp], https=True)
        resp = client.get('https://localhost/')
        self.assertIn('Strict-Transport-Security', resp.headers.keys())
        hsts = resp.headers['Strict-Transport-Security']
        hsts_fields = dict([(f.strip().split('=') + [None])[:2]
                            for f in hsts.split(';')])
        self.assertIn('includeSubDomains', hsts_fields.keys())
        self.assertIn('max-age', hsts_fields.keys())
        self.assertGreaterEqual(int(hsts_fields['max-age']), 31536000)

