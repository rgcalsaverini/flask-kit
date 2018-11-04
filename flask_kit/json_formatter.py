import datetime
import json
from itertools import zip_longest

_json_mime = 'application/json'
_text_mime = 'text/plain'
_default_headers = {}


def encode_datetime(obj, with_time):
    return {
        'with_time': with_time,
        'iso': obj.isoformat(),
        'unix': obj.replace(tzinfo=datetime.timezone.utc).timestamp(),
        'tuple': obj.timetuple()[:6],
        'tz': obj.tzname() if getattr(obj, 'tzname') else None,
    }


class Encoder(json.JSONEncoder):
    def default(self, obj):
        to_json = getattr(obj.__class__, "to_json", None)
        if to_json:
            return json.loads(obj.to_json())
        to_dict = getattr(obj.__class__, "to_dict", None)
        if to_dict:
            return obj.to_dict()
        if isinstance(obj, datetime.datetime):
            return encode_datetime(obj, True)
        if isinstance(obj, datetime.date):
            dt = datetime.datetime(*obj.timetuple()[:3], 0, 0, 0)
            print(dt)
            return encode_datetime(dt, False)
        return super(Encoder, self).default(obj)


def merge_tuples(defaults, values):
    """
    Returns a merge of two tuples, where values have precedence over defaults.
    """
    if not isinstance(values, tuple):
        values = (values,)
    return tuple(
        value if value is not None else default
        for default, value
        in zip_longest(defaults, values)
    )


def make_response(resp=None):
    """
    Correctly format the route response
    """
    body, status, headers = merge_tuples(('', 200, {}), resp)
    content_type = _text_mime
    has_status = isinstance(resp, tuple) and len(resp) >= 2

    if resp is None or (body == '' and not has_status):
        status = 204

    if not isinstance(body, str):
        body = json.dumps(body, cls=Encoder)
        content_type = _json_mime

    return body, status, {
        **_default_headers,
        'Content-Type': content_type,
        **headers,
    }
