import logging
import os
from os.path import isfile

import yaml
from cytoolz.dicttoolz import merge


def get_configs(defaults=None, filename='configs.yaml'):
    """
    Get configs
    """
    handler = ConfigHandler(filename)
    config = handler.load(defaults)
    return config


class ConfigHandler(object):
    def __init__(self, config_path, open=open, isfile=isfile, logger=logging):
        self.config_path = config_path
        self.open = open
        self.isfile = isfile
        self.logger = logger
        self.default_paths = [
            os.environ.get('HOME'),
            '.',
        ]

    def add_path(self, path):
        self.default_paths.append(path)

    def _join_path(self, path):
        return path and os.path.join(path, self.config_path)

    def load(self, defaults=None):
        config = defaults or {}

        if os.path.isabs(self.config_path):
            search_paths = [self.config_path]
        else:
            search_paths = map(self._join_path, self.default_paths)

        try:
            valid_paths = filter(lambda p: p and self.isfile(p), search_paths)
            file_path = next(valid_paths)
            with self.open(file_path, 'r') as f:
                loaded = yaml.load(f.read())
                config = merge(config, loaded)
        except Exception:
            self.logger.error(
                'Error parsing config file "{}"'.format(self.config_path))
            pass

        return DotDict(config)


class DotDict(dict):
    def __init__(self, value=None):
        if value is None:
            pass
        elif isinstance(value, dict):
            for key in value:
                self.__setitem__(key, value[key])
        else:
            raise TypeError('Expected dict')

    def __setitem__(self, key, value):
        if isinstance(value, dict) and not isinstance(value, DotDict):
            value = DotDict(value)
        super(DotDict, self).__setitem__(key, value)

    def __getattr__(self, key):
        return self[key]

    __setattr__ = __setitem__


def random_secret_key():
    return os.urandom(1000).decode('utf-16', 'ignore')[:128]


class AppConfig(object):
    """
    Flask extension for setting flask configs.
    """

    def __init__(self, app, configs):
        self.configs = configs
        if app:
            self.init_app(app)

    def init_app(self, app):
        app.config.update(self.configs.get('flask', {}))
        if app.config.get('SECRET_KEY', None) is None:
            app.config['SECRET_KEY'] = random_secret_key()

