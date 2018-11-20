"""
https://specs.openstack.org/openstack/api-wg/guidelines/pagination_filter_sort.html
http://json-schema.org/latest/json-schema-hypermedia.html#rfc.section.9
http://werkzeug.pocoo.org/docs/0.14/datastructures/#werkzeug.datastructures.MultiDict.getlist
"""
from functools import wraps

from cerberus import Validator
from flask import request as flask_request
from mongoengine import Document
from mongoengine.queryset import QuerySet

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

    def doc_read(self, document, rule):
        def inner(f):
            def common():
                if self.decorator:
                    res = self.decorator(f)
                else:
                    res = f()
                if res is None:
                    return {}
                return res

            def view_list():
                limit = max(1, min(self.max_page, self.selector.limit()))
                offset = max(0, self.selector.offset())
                filters = self.selector.filter()
                extra_filters = common()

                query = filters.apply_mongo(document).object(**extra_filters)
                res = query.limit(limit).skip(offset).all()

                return {
                    'items': res,
                    'links': {}
                }

            def view_details(doc_id):
                extra_filters = common()
                res = document.object(id=doc_id, **extra_filters).first()
                if not res:
                    msg = "entry with id '{}' not found on '{}'"
                    return make_error(msg.format(doc_id, document.__name__))
                return res

            view_name = f.__name__
            list_endpoint = '%s_%s_list' % (self.bp_name, view_name)
            detail_endpoint = '%s_%s_detail' % (self.bp_name, view_name)

            self.blueprint.add_url_rule(
                rule=rule,
                endpoint=list_endpoint,
                view_func=view_list,
                methods=['GET']
            )
            self.blueprint.add_url_rule(
                rule='%s/<doc_id>' % rule,
                endpoint=detail_endpoint,
                view_func=view_details,
                methods=['GET']
            )

            if document and self.document_routes:
                self._document_route(f, rule, ['GET'], list_endpoint, None)
                self._document_route(f, rule, ['GET'], detail_endpoint, None)

        return inner

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
                        if self.as_json:
                            return response
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


class FilterList(list):
    def apply_mongo(self, doc_or_query, doc_cls=Document, query_cls=QuerySet):
        """
        Apply filter to a mongo document (creating a query) or to
        a queryset (filtering it). Returns the queryset
        """
        mongo_kwargs = dict()
        mongo_ops = {
            'eq': '',
            'ne': '__ne',
            'lt': '__lt',
            'gt': '__gt',
            'ge': '__gte',
            'le': '__lte',
            'not': '__not',
            'in': '__in',
            'nin': '__nin',
        }

        if isinstance(doc_or_query, doc_cls):
            document = doc_or_query
        elif isinstance(doc_or_query, query_cls):
            document = doc_or_query._document
        else:
            raise TypeError()

        for item in self:
            doc_field = getattr(document, item['field'])
            if doc_field:
                value = doc_field.to_python(item['value'])
            else:
                value = item['value']
            arg = '{}{}'.format(item['field'], mongo_ops[item['op']])
            mongo_kwargs[arg] = value
        if isinstance(doc_or_query, doc_cls):
            return doc_or_query.objects(**mongo_kwargs)
        return doc_or_query.filter(**mongo_kwargs)


class Selector(object):
    filter_ops = ['eq', 'in', 'nin', 'lt', 'le', 'gt', 'ge', 'ne', 'not']
    sort_dir = ['asc', 'desc']

    def __init__(self, request_obj=flask_request):
        self.request = request_obj

    def limit(self):
        """ Returns the limit as an integer or None """
        limit_value = self.request.args.get('limit', None)
        if is_non_neg_int(limit_value):
            return int(limit_value)
        return None

    def offset(self):
        """ Returns the offset as an integer or None """
        marker_value = self.request.args.get('marker', '')
        if is_non_neg_int(marker_value):
            return int(marker_value)
        return None

    def filter(self, only=None, mapping=None):
        """
        Returns a list of filter descriptors.

        /users?gender=male&age=23
        /products?category=in:computers,tvs&price=gt:10.00&price=lt:100.00
        """
        final_filter = FilterList()
        for key in self.request.args.keys():
            for arg in self.request.args.getlist(key):
                if only is not None and key not in only:
                    continue
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
        final_sorting = dict()
        sort_val = self.request.args.get('sort', None)
        if not sort_val:
            return {}
        sort_keys = sort_val.split(',')
        for key in sort_keys:
            if only is not None and key not in only:
                continue
            final_key = (mapping or dict()).get(key, key)
            s_dir, val = qualified_value(key, self.sort_dir, False, 'desc')
            final_sorting[final_key] = {
                'direction': s_dir,
                'value': val,
            }
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
