import datetime
import json
import unittest
from unittest.mock import MagicMock

from dateutil import parser as date_parser

from flask_kit.json_formatter import make_response, JsonFormatter


class IsSerializable(object):
    custom = '{"custom_serialization": ["yeah", 1]}'

    def to_json(self):
        return self.custom


class IsAlsoSerializable(object):
    custom = {'custom_serialization': ['yeah', 1]}

    def to_dict(self):
        return self.custom


class NotSerializable(object):
    pass


def sec_diff(d1, d2):
    return abs((d1 - d2).total_seconds())


class ResponseCase(unittest.TestCase):
    def assertHeader(self, response, header, value):
        self.assertEquals(type(response), tuple)
        self.assertEquals(len(response), 3)
        self.assertEquals(response[2].get(header), value)

    def assertContentType(self, response, content_type):
        self.assertHeader(response, 'Content-Type', content_type)

    def assertStatus(self, response, status):
        self.assertEquals(type(response), tuple)
        self.assertEquals(len(response), 3)
        self.assertEquals(response[1], status)

    def assertDataEquals(self, response, data):
        self.assertEquals(type(response), tuple)
        self.assertEquals(len(response), 3)
        if isinstance(data, str):
            self.assertEquals(response[0], data)
        elif isinstance(data, dict):
            self.assertDictEqual(json.loads(response[0]), data)
        else:
            self.fail()


class FakeApp():
    def __init__(self, *args, **kwargs):
        pass

    after_request = MagicMock()


class TestExtension(unittest.TestCase):
    def test_register(self):
        app = FakeApp()
        JsonFormatter(app)
        app.after_request.assert_called_once_with(make_response)


class TestDecorator(ResponseCase):
    def test_plain(self):
        resp = make_response('text')
        self.assertContentType(resp, 'text/plain')
        self.assertStatus(resp, 200)
        self.assertDataEquals(resp, 'text')

    def test_json(self):
        payload = {'test': {'test': 1}, 'other': [1, True, 2.2]}
        resp = make_response(payload)
        self.assertContentType(resp, 'application/json')
        self.assertStatus(resp, 200)
        self.assertDataEquals(resp, payload)

    def test_empty(self):
        resp1 = make_response()
        resp2 = make_response('')

        self.assertContentType(resp1, 'text/plain')
        self.assertStatus(resp1, 204)
        self.assertDataEquals(resp1, '')
        self.assertContentType(resp2, 'text/plain')
        self.assertStatus(resp2, 204)
        self.assertDataEquals(resp2, '')

    def test_status(self):
        resp = make_response(('', 123))
        self.assertStatus(resp, 123)
        resp = make_response(('A', 123))
        self.assertStatus(resp, 123)
        resp = make_response((None, 123))
        self.assertStatus(resp, 123)
        resp = make_response(({'a': 1}, 123))
        self.assertStatus(resp, 123)

    def test_header(self):
        resp = make_response(('', 200, {'X-My-Header': 'Foobar'}))
        self.assertHeader(resp, 'X-My-Header', 'Foobar')

    def test_custom_json(self):
        resp = make_response(IsSerializable())
        self.assertDataEquals(resp, IsSerializable.custom)
        resp = make_response(IsAlsoSerializable())
        self.assertDataEquals(resp, IsAlsoSerializable.custom)

    def test_not_serializable(self):
        with self.assertRaises(TypeError):
            make_response(NotSerializable())

    def test_datetime(self):
        dt = datetime.datetime.now()
        resp = make_response({'datetime': dt})
        date_resp = json.loads(resp[0]).get('datetime', {})
        self.assertAlmostEqual(dt, date_parser.parse(date_resp['iso']))
        self.assertLess(sec_diff(
            dt, datetime.datetime(*date_resp['tuple'])
        ), 1)
        self.assertLess(sec_diff(
            dt, datetime.datetime.utcfromtimestamp(date_resp['unix'])
        ), 1, [dt, datetime.datetime.utcfromtimestamp(date_resp['unix'])])
        self.assertIs(date_resp['with_time'], True)

    def test_date(self):
        date = datetime.date.today()
        dt = datetime.datetime(*date.timetuple()[:3], 0, 0, 0)
        resp = make_response({'date': date})
        date_resp = json.loads(resp[0]).get('date', {})
        self.assertAlmostEqual(dt, date_parser.parse(date_resp['iso']))
        self.assertLess(sec_diff(
            dt, datetime.datetime(*date_resp['tuple'])
        ), 1)
        self.assertLess(sec_diff(
            dt, datetime.datetime.utcfromtimestamp(date_resp['unix'])
        ), 1, [dt, datetime.datetime.utcfromtimestamp(date_resp['unix'])])
        self.assertIs(date_resp['with_time'], False)
