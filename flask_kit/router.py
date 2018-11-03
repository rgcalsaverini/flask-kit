from cerberus import Validator
from flask import request as flask_request


def make_error(error, status=400):
    """Assemble an error response tuple"""
    return {
               'success': False,
               'error': error
           }, status


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
                 data_key='data'):
        self.decorator = decorator
        self.blueprint = blueprint
        self.bp_name = self.blueprint.name
        self.data_key = data_key
        self.routes = {}
        self.request = request
        self.document_routes = document_routes

        if document_routes:
            self._add_documentation_route()

    def _documentation_view(self):
        return self.routes

    def _add_documentation_route(self):
        endpoint = '%s_documentation' % self.bp_name

        self.blueprint.add_url_rule(
            rule='',
            endpoint=endpoint,
            view_func=self._documentation_view,
            methods=['GET', 'OPTIONS']
        )

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

            def decorated(*args, **kwargs):
                new_kwargs = {}
                if validator:
                    input_json = self.request.get_json(silent=True, force=True)
                    if not validator.validate(input_json or {}):
                        return make_error(validator.errors)
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
                view_func=decorated,
                methods=[method]
            )

            if document and self.document_routes:
                self._document_route(f, rule, method, endpoint, validate)

            return decorated

        return inner

    def __getattr__(self, item):
        if item.lower() not in self.valid_methods:
            msg = 'Invalid method %s requested from router'
            raise AttributeError(msg % item)

        def inner(*args, **kwargs):
            return self.route(*args, **kwargs, method=item.upper())

        return inner
