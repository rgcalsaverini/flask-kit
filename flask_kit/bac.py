from functools import wraps


def _check_permissions(permissions, match, no_match, user_perm):
    for perm in permissions:
        perm_list = perm if isinstance(perm, list) else [perm]
        common = [p in user_perm for p in perm_list]
        if all(common):
            return match()
    return no_match()


def _f_perm(f, args, kwargs, arg_name, user_perm):
    """ Function f with added permissions argument, if provided """
    def with_permissions():
        if not arg_name:
            return f(*args, **kwargs)
        return f(*args, **{**kwargs, arg_name: user_perm})

    return with_permissions


class BasicAccessControl(object):
    """
    Provides basic access control functionality.

    :param get_permissions: a callback that returns a list of permission flags
                            for the current user
    :param denied: custom response on access denied. Optional.

    Example usage:
    >>> access = BasicAccessControl(get_user_permissions)
    >>>
    >>> @access.allow('admin')
    >>> def admin():
    >>>     return 'Hi admin'
    >>>
    >>> @access.allow(['HR', 'manager'], 'admin', 'director')
    >>> def manage_salaries():
    >>>     return 'salaries'
    >>>
    >>> @access.deny('external')
    >>> def route():
    >>>     return 'route'
    """

    default_denied_response = {'error': 'access_denied'}, 403

    def __init__(self, get_permissions, denied=None):
        self._get_permissions = get_permissions
        self._custom_denied = denied

    def allow(self, *permissions, arg_name=None):
        def inner(f):
            @wraps(f)
            def decorated(*args, **kwargs):
                user_perm = self._get_permissions()
                return _check_permissions(
                    permissions,
                    match=_f_perm(f, args, kwargs, arg_name, user_perm),
                    no_match=self._denied,
                    user_perm=user_perm
                )

            return decorated

        return inner

    def deny(self, *permissions, arg_name=None):
        def inner(f):
            @wraps(f)
            def decorated(*args, **kwargs):
                user_perm = self._get_permissions()
                return _check_permissions(
                    permissions,
                    match=self._denied,
                    no_match=_f_perm(f, args, kwargs, arg_name, user_perm),
                    user_perm=user_perm
                )

            return decorated

        return inner

    def pass_permissions(self, arg_name='permissions'):
        def inner(f):
            @wraps(f)
            def decorated(*args, **kwargs):
                user_perm = self._get_permissions()
                return _f_perm(f, args, kwargs, arg_name, user_perm)()

            return decorated

        return inner

    def _denied(self):
        if self._custom_denied:
            return self._custom_denied()
        return BasicAccessControl.default_denied_response
