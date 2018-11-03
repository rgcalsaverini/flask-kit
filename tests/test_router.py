import unittest
from unittest.mock import MagicMock

from flask_kit import Router


# TODO: Cover help route better, and individual help routes on options

class TestRouter(unittest.TestCase):
    def test_empty(self):
        blueprint = FakeBlueprint()
        Router(blueprint)
        self.assertEquals(blueprint.add_url_rule.call_count, 1)
        print()

        view_func = blueprint.add_url_rule.call_args_list[0][1]['view_func']
        rule = blueprint.add_url_rule.call_args_list[0][1]['rule']
        self.assertEquals(view_func(), {})
        self.assertEquals(rule, '')

    def test_simple_routes(self):
        blueprint = FakeBlueprint()
        router = Router(blueprint)

        @router.get('route')
        def route():
            """
            Route documentation
            """
            return 'route'

        self.assertEquals(blueprint.add_url_rule.call_count, 2)
        self.assertEquals(route(), 'route')
        call_2 = blueprint.add_url_rule.call_args_list[1][1]
        self.assertEquals(call_2['rule'], '/route')

    def test_validate_valid(self):
        blueprint = FakeBlueprint()
        router = Router(blueprint, request=FakeRequest({}))

        @router.post('/my/route', validate={
            'test': {
                'required': True,
                'type': 'float',
                'default': 0.5,
                'min': 0,
                'max': 1,
            }
        })
        def my_route(data):
            return data['test']

        res = my_route()
        self.assertEquals(res, 0.5)

    def test_validate_invalid(self):
        blueprint = FakeBlueprint()
        router = Router(blueprint, request=FakeRequest({'test': -1}))

        @router.post('/my/route', validate={
            'test': {
                'required': True,
                'type': 'float',
                'default': 0.5,
                'min': 0,
                'max': 1,
            }
        })
        def my_route(data):
            return data['test']

        res = my_route()
        self.assertIs(res[0]['success'], False)


class FakeBlueprint(object):
    def __init__(self, name='bp_name', url_prefix=''):
        self.name = name
        self.url_prefix = url_prefix
        self.add_url_rule = MagicMock()


class FakeRequest(object):
    def __init__(self, value):
        self.value = value

    def get_json(self, **_):
        return self.value
