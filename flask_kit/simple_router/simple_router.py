"""
https://specs.openstack.org/openstack/api-wg/guidelines/pagination_filter_sort.html
http://json-schema.org/latest/json-schema-hypermedia.html#rfc.section.9
http://werkzeug.pocoo.org/docs/0.14/datastructures/#werkzeug.datastructures.MultiDict.getlist
"""
from functools import wraps

from cerberus import Validator
from flask import request as flask_request

from flask_kit.json_formatter import make_response


class Router(object):
    """
    Simple router wrapper to the API endpoints. Does a few things:
        - Adds a normalized 'data' argument to the route with the
             request input
        - Facilitates input validation with cerberus
        - Document the API at the root endpoint

    Example:
        router = Router(blueprint)
        things = {}
        scheme = {
            'name': {
                'type': 'string',
                'required': True,
                'nullable': False,
            },
            'value': {
                'type': ['string', 'integer'],
                'required': True,
                'nullable': True,
            },
        }
        validator = Validator(scheme)

        @router.get('something')
        def list_things(_):
            return things

        @router.post('something', validator=validator)
        def add_something(data):
            things[data['name']] = data['value']
            return {data['name']: data['value']}

    """

    valid_methods = [
        'get',
        'post',
        'put',
        'patch',
        'delete',
        'head',
        'options'
    ]

    def __init__(self, blueprint,
                 decorator=None,
                 document_routes=True,
                 request=flask_request,
                 data_key='data',
                 as_json=True):
        self.decorator = decorator
        self.blueprint = blueprint
        self.bp_name = self.blueprint.name
        self.data_key = data_key
        self.routes = {}
        self.request = request
        self.document_routes = document_routes
        self.as_json = as_json
        self.selector = Selector()
        self.max_page = 500

        if document_routes:
            self._add_documentation_route()

    def _documentation_view(self):
        return make_response(self.routes)

    def _add_documentation_route(self):
        endpoint = '%s_documentation' % self.bp_name

        self.blueprint.add_url_rule(
            rule='',
            endpoint=endpoint,
            view_func=self._documentation_view,
            methods=['GET', 'OPTIONS']
        )

    def _response_decorator(self, f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if self.as_json:
                return make_response(f(*args, **kwargs))
            return f(*args, **kwargs)

        return decorated

    def _document_route(self, view, rule, method, endpoint, cerberus_schema):
        full_rule = '/{}{}'.format(self.blueprint.url_prefix.strip('/'), rule)

        if full_rule not in self.routes.keys():
            self.routes[full_rule] = {}

        description = view.__doc__ and view.__doc__.strip()

        self.routes[full_rule][method] = {
            'description': description,
            'name': endpoint,
        }

        if cerberus_schema:
            self.routes[full_rule][method]['parameters'] = cerberus_schema

    def route(self,
              rule_path: str,
              method: str,
              validate: dict = None,
              document: bool = True):
        """
        Decorator that registers a route on the BP or app.

        :param rule_path: endpoint URL minus the API root
        :param method: the HTTP methods accepted
        :param validate: Cerberus JSON schema. Defaults to None.
                          if provided, will enforce validation using it.
        :param document: Add route to API documentation
        """

        def inner(f):
            view_name = f.__name__
            endpoint = '%s_%s' % (self.bp_name, view_name)
            rule = '/%s' % rule_path.strip('/')
            validator = Validator(validate) if validate else None

            @self._response_decorator
            def decorated_route(*args, **kwargs):
                new_kwargs = {}
                if validator:
                    input_json = get_json(self.request)
                    if not validator.validate(input_json or {}):
                        response = make_error(validator.errors)
                        return response
                    new_kwargs[self.data_key] = validator.document

                full_kwargs = {**kwargs, **new_kwargs}
                if self.decorator:
                    response = self.decorator(f, *args, **full_kwargs)
                else:
                    response = f(*args, **full_kwargs)
                return response

            self.blueprint.add_url_rule(
                rule=rule,
                endpoint=endpoint,
                view_func=decorated_route,
                methods=[method]
            )

            if document and self.document_routes:
                self._document_route(f, rule, method, endpoint, validate)

            return decorated_route

        return inner

    def __getattr__(self, item):
        if item.lower() not in self.valid_methods:
            msg = 'Invalid method %s requested from router'
            raise AttributeError(msg % item)

        def inner(*args, **kwargs):
            return self.route(*args, **kwargs, method=item.upper())

        return inner


def make_error(error, status=400):
    """Assemble an error response tuple"""
    return {
               'success': False,
               'error': error
           }, status


def get_json(request):
    res = request.get_json(silent=True, force=True)
    return res


class Selector(object):
    filter_ops = ['eq', 'in', 'nin', 'lt', 'le', 'gt', 'ge', 'ne', 'not']
    sort_dir = ['asc', 'desc']

    def __init__(self, list_obj=None, request_obj=flask_request):
        self.request = request_obj
        self.list_obj = list_obj or list

    def limit(self):
        """ Returns the limit as an integer or None """
        limit_value = self.request.args.get('limit', None)
        if is_non_neg_int(limit_value):
            return int(limit_value)
        return None

    def offset(self):
        """ Returns the offset as an integer or None """
        offset_value = self.request.args.get('offset', None)
        if is_non_neg_int(offset_value):
            return int(offset_value)
        return None

    def filter(self, only=None, mapping=None):
        """
        Returns a list of filter descriptors.

        /users?gender=male&age=23
        /products?category=in:computers,tvs&price=gt:10.00&price=lt:100.00
        """
        final_filter = self.list_obj()
        for key in self.request.args.keys():
            if not key or only is not None and key not in only:
                continue
            for arg in self.request.args.getlist(key):

                final_key = (mapping or dict()).get(key, key)
                op, value = qualified_value(arg, self.filter_ops, True, 'eq')
                if op in ['in', 'nin']:
                    value = [v.strip() for v in value.split(',') if v.strip()]
                final_filter.append({
                    'field': final_key,
                    'op': op,
                    'value': value,
                })
        return final_filter

    def sort(self, only=None, mapping=None):
        final_sorting = list()
        sort_val = self.request.args.get('sort', None)
        if not sort_val:
            return {}
        sort_keys = sort_val.split(',')
        for key in sort_keys:
            if not key or only is not None and key not in only:
                continue
            s_dir, val = qualified_value(key, self.sort_dir, False, 'desc')
            final_key = (mapping or dict()).get(val, val)
            final_sorting.append({
                'field': final_key,
                'direction': s_dir,
            })
        return final_sorting


def qualified_value(raw_value, valid, qualifier_first, default):
    """
    Given a string with one optional qualifier and a payload, both separated
    by a comma, returns both separately.
    :param raw_value: the raw string
    :param valid: a list with all valid qualifiers
    :param qualifier_first: true if the qualifier appears first
    :param default: the default value for the qualifier, should it be omitted
    :return: a tuple containing the qualifier and the value, in this order
    """
    if ':' not in raw_value:
        return default, raw_value.strip()
    part1, part2 = raw_value.split(':', 1)
    if qualifier_first:
        qualifier = part1.strip()
        value = part2.strip()
    else:
        qualifier = part2.strip()
        value = part1.strip()
    if qualifier not in valid:
        return default, raw_value.strip()
    return qualifier, value


def is_non_neg_int(value):
    """ Returns true if the value is a non-negative int """
    try:
        return int(value) >= 0
    except (ValueError, TypeError):
        return False
