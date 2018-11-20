import json
import unittest
from unittest.mock import MagicMock

from werkzeug.datastructures import ImmutableMultiDict
from werkzeug.urls import url_decode

from flask_kit import Router
from flask_kit.simple_router import Selector


# TODO: Cover help route better, and individual help routes on options
# TODO: Test if routes are always encoded JSON

class RouterTestCase(unittest.TestCase):
    def assertIsJson(self, value):
        self.assertIsInstance(value, str)
        try:
            json.loads(value)
        except ValueError as e:
            self.fail('Invalid JSON: %s' % str(e))


class TestSelector(unittest.TestCase):
    def test_empty(self):
        s = Selector(FakeRequest())
        self.assertEquals(s.filter(), [])
        self.assertEquals(s.sort(), {})
        self.assertIsNone(s.limit())
        # self.assertIsNone(s.marker())

    def test_limit(self):
        limits = {
            'limit=0': 0,
            'limit=1': 1,
            'limit=10': 10,
            'limit=12345678': 12345678,
            'limit=-1': None,
            'limit=a': None,
            'limit=': None,
            'limit=TEST': None,
        }

        for lim, res in limits.items():
            s = Selector(FakeRequest(args=lim))
            self.assertEquals(s.limit(), res)

    # def test_marker(self):
    #     markers = {
    #         'marker=': None,
    #         'marker=%20': None,
    #         'marker=%20%20': None,
    #         'marker=TEST': 'TEST',
    #         'marker=1': '1',
    #         'marker=0fb6300ac4a': '0fb6300ac4a',
    #     }
    #
    #     for marker, res in markers.items():
    #         s = Selector(FakeRequest(args=marker))
    #         self.assertEquals(s.marker(), res)

    def test_filter(self):  # todo add not a qualifier
        filters = [
            (
                'key_1=1&key_2=%202&key_3=3%20&key_4=%204%20&key_5= eq :  5  ',
                [
                    {'field': 'key_1', 'op': 'eq', 'value': '1'},
                    {'field': 'key_2', 'op': 'eq', 'value': '2'},
                    {'field': 'key_3', 'op': 'eq', 'value': '3'},
                    {'field': 'key_4', 'op': 'eq', 'value': '4'},
                    {'field': 'key_5', 'op': 'eq', 'value': '5'},
                ]
            ),
            (
                'time=ge:10:30&time=le:14:30',
                [
                    {'field': 'time', 'op': 'le', 'value': '14:30'},
                    {'field': 'time', 'op': 'ge', 'value': '10:30'},
                ]
            ),
            (
                'a=:a&b=b:b&c=invalid:c',
                [
                    {'field': 'a', 'op': 'eq', 'value': ':a'},
                    {'field': 'b', 'op': 'eq', 'value': 'b:b'},
                    {'field': 'c', 'op': 'eq', 'value': 'invalid:c'},
                ]
            ),
            (
                'eq1=eq:eq1&eq2=eq2&le=le:le&lt=lt:lt&gt=gt:gt&ge=ge:ge&ne=ne:ne',
                [
                    {'field': 'eq1', 'op': 'eq', 'value': 'eq1'},
                    {'field': 'eq2', 'op': 'eq', 'value': 'eq2'},
                    {'field': 'le', 'op': 'le', 'value': 'le'},
                    {'field': 'lt', 'op': 'lt', 'value': 'lt'},
                    {'field': 'gt', 'op': 'gt', 'value': 'gt'},
                    {'field': 'ge', 'op': 'ge', 'value': 'ge'},
                    {'field': 'ne', 'op': 'ne', 'value': 'ne'},
                ]
            ),
            (
                'a=in:1&b=in:1,&c=in:1,2&d=in:1,2,3&e=in: 1,%20 2 ,%203&f=in:',
                [
                    {'field': 'a', 'op': 'in', 'value': ['1']},
                    {'field': 'b', 'op': 'in', 'value': ['1']},
                    {'field': 'c', 'op': 'in', 'value': ['1', '2']},
                    {'field': 'd', 'op': 'in', 'value': ['1', '2', '3']},
                    {'field': 'e', 'op': 'in', 'value': ['1', '2', '3']},
                    {'field': 'f', 'op': 'in', 'value': []},
                ]
            ),
        ]

        def sort_filter_list(el):
            if isinstance(el['value'], list):
                value = ','.join(sorted(el['value']))
            else:
                value = el['value']
            return '{}{}{}'.format(el['field'], el['op'], value)

        for filt, res in filters:
            print(filt)
            s = Selector(FakeRequest(args=filt))
            self.assertListEqual(
                sorted(s.filter(), key=sort_filter_list),
                sorted(res, key=sort_filter_list)
            )


class TestRouter(RouterTestCase):
    def test_no_routes(self):
        blueprint = FakeBlueprint()
        Router(blueprint)
        self.assertEquals(blueprint.add_url_rule.call_count, 1)
        print()

        view_func = blueprint.add_url_rule.call_args_list[0][1]['view_func']
        rule = blueprint.add_url_rule.call_args_list[0][1]['rule']
        res = view_func()
        self.assertIsJson(res[0])
        self.assertEquals(json.loads(res[0]), {})
        self.assertEquals(rule, '')

    def test_simple_routes(self):
        blueprint = FakeBlueprint()
        router = Router(blueprint, as_json=False)

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
        router = Router(blueprint, request=FakeRequest({}), as_json=False)

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
        router = Router(blueprint,
                        request=FakeRequest({'test': -1}),
                        as_json=False)

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
        self.assertIs(res[0]['success'], False, res)


class FakeBlueprint(object):
    def __init__(self, name='bp_name', url_prefix=''):
        self.name = name
        self.url_prefix = url_prefix
        self.add_url_rule = MagicMock()


class FakeRequest(object):
    def __init__(self, value=None, args=None):
        self.value = value
        if args is not None:
            self.args = url_decode(args, 'utf-8', cls=ImmutableMultiDict)
        else:
            self.args = ImmutableMultiDict()

    def get_json(self, **_):
        return self.value
