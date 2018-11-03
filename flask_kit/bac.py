from functools import wraps


class BasicAccessControl(object):
    """
        :param get_permissions: Should provide a method that returns a list
            with the valid activities of of the accessing user.
    """
    default_denied_response = {'error': 'access_denied'}, 403

    def __init__(self, get_permissions, denied=None):
        self._get_permissions = get_permissions
        self._custom_denied = denied

    def _denied(self):
        if self._custom_denied:
            return self._custom_denied()
        return BasicAccessControl.default_denied_response

    def _check_permissions(self, permissions, match, no_match):
        user_perm = self._get_permissions()
        for perm in permissions:
            perm_list = perm if isinstance(perm, list) else [perm]
            common = [p in user_perm for p in perm_list]
            if all(common):
                return match()
        return no_match()

    def _f_with_perm(self, f, args, kwargs, arg_name):
        def with_permissions():
            if not arg_name:
                return f(*args, **kwargs)
            user_perm = self._get_permissions()
            return f(*args, **{**kwargs, arg_name: user_perm})

        return with_permissions

    def allow(self, *permissions, arg_name=None):
        def inner(f):
            @wraps(f)
            def decorated(*args, **kwargs):
                return self._check_permissions(
                    permissions,
                    match=self._f_with_perm(f, args, kwargs, arg_name),
                    no_match=self._denied,
                )

            return decorated

        return inner

    def deny(self, *permissions, arg_name=None):
        def inner(f):
            @wraps(f)
            def decorated(*args, **kwargs):
                return self._check_permissions(
                    permissions,
                    match=self._denied,
                    no_match=self._f_with_perm(f, args, kwargs, arg_name),
                )

            return decorated

        return inner

    def pass_permissions(self, arg_name='permissions'):
        def inner(f):
            @wraps(f)
            def decorated(*args, **kwargs):
                return self._f_with_perm(f, args, kwargs, arg_name)()

            return decorated

        return inner
