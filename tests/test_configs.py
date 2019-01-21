import json
import os
import unittest
from unittest.mock import MagicMock

from flask import Flask

from flask_kit.config import ConfigHandler, DotDict, AppConfig, get_configs
from tests.utils import FakeOpen


class TestDotDict(unittest.TestCase):
    def test_empty(self):
        dot = DotDict()
        self.assertFalse(dot)

    def test_access(self):
        dot = DotDict({'a': 1})
        self.assertEqual(dot.a, 1)

    def test_wrong_type(self):
        with self.assertRaises(TypeError):
            DotDict('wrong')
            DotDict(1)
            DotDict([1, 2])

    def test_access_deep(self):
        dot = DotDict({'a': {'b': {'c': {'d': 1}}}})
        self.assertEqual(dot.a.b.c.d, 1)


class TestConfig(unittest.TestCase):
    def test_abs_path(self):
        fake_path = '/tmp/config.json'
        fake_open = FakeOpen('{"a":1}')
        config = _create_config(path=fake_path, open=fake_open)
        config.load()
        self.assertEqual(fake_open.path, fake_path)

    def test_home_path(self):
        fake_path = 'config.json'
        fake_open = FakeOpen('{"a":1}')
        config = _create_config(path=fake_path, open=fake_open)
        config.load()
        self.assertEqual(fake_open.path, os.path.expanduser('~/' + fake_path))

    def test_current_dir_path(self):
        fake_path = 'raccoon_config_test.json'
        fake_isfile = MagicMock()
        fake_isfile.side_effect = [False, True]
        fake_open = FakeOpen('{"a":1}')
        config = _create_config(path=fake_path,
                                open=fake_open,
                                isfile=fake_isfile)
        config.load()
        self.assertEqual(fake_open.path, './' + fake_path)

    def test_add_path(self):
        fake_isfile = MagicMock()
        fake_isfile.side_effect = [False, False, True]
        fake_path = 'config.json'
        fake_open = FakeOpen('{"a":1}')
        config = _create_config(
            path=fake_path,
            open=fake_open,
            isfile=fake_isfile)
        config.add_path('/tmp')
        config.load()
        self.assertEqual(fake_open.path, '/tmp/' + fake_path)

    def test_load_defaults(self):
        defaults = {'aaa': 1}
        config = _create_config(isfile=lambda *_: False)
        self.assertDictEqual(defaults, config.load(defaults))

    def test_factory(self):
        handler = MagicMock()
        get_configs(cls=handler)
        self.assertEquals(handler.call_count, 1)


class TestFlaskConfig(unittest.TestCase):
    def test_basic(self):
        fake_path = '/tmp/config.json'
        fake_open = FakeOpen(json.dumps({
            'flask': {
                'LOREM': 'Ipsum',
            },
            'LOREM': 'NOT ipsum',
        }))
        handler = _create_config(path=fake_path, open=fake_open)
        config = handler.load()
        app = Flask(__name__)
        AppConfig(app, config)
        self.assertEquals(app.config.get('LOREM'), 'Ipsum')
        self.assertTrue(app.config.get('SECRET_KEY') is not None)
        self.assertTrue(len(app.config.get('SECRET_KEY')) > 32)
        self.assertEquals(app.config.get('SECRET_KEY'), app.secret_key)

    def test_set_secret(self):
        fake_path = '/tmp/config.json'
        fake_open = FakeOpen(json.dumps({
            'flask': {
                'SECRET_KEY': 'Oi',
            },
        }))
        handler = _create_config(path=fake_path, open=fake_open)
        config = handler.load()
        app = Flask(__name__)
        AppConfig(app, config)
        self.assertEquals(app.config.get('SECRET_KEY'), 'Oi')
        self.assertEquals(app.config.get('SECRET_KEY'), app.secret_key)


def _create_config(**kwargs):
    if 'open' not in kwargs:
        kwargs['open'] = FakeOpen()
    if 'isfile' not in kwargs:
        kwargs['isfile'] = lambda s: True
    if 'path' in kwargs:
        path = kwargs['path']
        del kwargs['path']
    else:
        path = 'path'
    return ConfigHandler(path, **kwargs)
