import unittest

from flask_kit import BasicAccessControl


def assert_not_allowed(res):
    error_msg = BasicAccessControl.default_denied_response[0]['error']
    status = BasicAccessControl.default_denied_response[1]
    if isinstance(res, bool):
        assert False
    else:
        assert isinstance(res[0], dict)
        assert res[0].get('error') == error_msg
        assert res[1] == status


class TestDecorator(unittest.TestCase):
    def test_one(self):
        access = BasicAccessControl(lambda: ['see_route'])

        @access.allow(['see_route'])
        def route1():
            return True

        @access.allow(['something_else'])
        def route2():
            return True

        res = route1()
        self.assertTrue(res)

        res = route2()
        assert_not_allowed(res)

    def test_with_permissions(self):
        access = BasicAccessControl(lambda: ['perm1', 'perm2'])

        @access.allow('perm1', arg_name='permissions')
        def route1(permissions):
            assert 'perm1' in permissions
            assert 'perm2' in permissions

        @access.deny('perm3', arg_name='p')
        def route2(p):
            assert 'perm1' in p
            assert 'perm2' in p

        @access.pass_permissions()
        def route3(permissions):
            assert 'perm1' in permissions
            assert 'perm2' in permissions

        route1()
        route2()
        route3()

    def test_preserve_func(self):
        access = BasicAccessControl(lambda: [])

        @access.allow('1')
        @access.deny('2')
        def route():
            return True

        self.assertEquals(route.__name__, 'route')

    def test_deny(self):
        access = BasicAccessControl(lambda: ['allow', 'deny'])

        @access.allow('allow')
        @access.deny('deny')
        def deny_last():
            return True

        @access.deny('deny')
        @access.allow('allow')
        def deny_first():
            return True

        @access.deny('deny')
        def deny_only():
            return True

        @access.deny('nothing')
        def deny_other():
            return True

        assert_not_allowed(deny_last())
        assert_not_allowed(deny_first())
        assert_not_allowed(deny_only())
        self.assertIs(deny_other(), True)

    def test_combination(self):
        user_1 = lambda: []
        user_2 = lambda: ['enter_kitchen']
        user_3 = lambda: ['enter_kitchen', 'use_utensils']
        user_4 = lambda: ['use_utensils', 'touch_food']
        user_5 = lambda: ['enter_kitchen', 'use_utensils', 'touch_food']
        user_6 = lambda: ['touch_food']
        user_7 = lambda: ['do_anything']

        access = BasicAccessControl(user_1)

        @access.allow(
            'do_anything',
            ['enter_kitchen', 'use_utensils', 'touch_food']
        )
        def prepare_food():
            return True

        @access.allow('do_anything', ['enter_kitchen', 'use_utensils'])
        def wash_dishes():
            return True

        @access.allow('do_anything', ['touch_food', 'use_utensils'])
        def eat_properly():
            return True

        @access.allow('do_anything', 'touch_food')
        def eat_neanderthal():
            return True

        @access.allow('do_anything', ['enter_kitchen'])
        def watch_cook():
            return True

        access._get_permissions = user_1
        assert_not_allowed(prepare_food())
        assert_not_allowed(wash_dishes())
        assert_not_allowed(eat_properly())
        assert_not_allowed(eat_neanderthal())
        assert_not_allowed(watch_cook())

        access._get_permissions = user_2
        assert_not_allowed(prepare_food())
        assert_not_allowed(wash_dishes())
        assert_not_allowed(eat_properly())
        assert_not_allowed(eat_neanderthal())
        self.assertIs(watch_cook(), True)

        access._get_permissions = user_3
        assert_not_allowed(prepare_food())
        self.assertIs(wash_dishes(), True)
        assert_not_allowed(eat_properly())
        assert_not_allowed(eat_neanderthal())
        self.assertIs(watch_cook(), True)

        access._get_permissions = user_4
        assert_not_allowed(prepare_food())
        assert_not_allowed(wash_dishes())
        self.assertIs(eat_properly(), True)
        self.assertIs(eat_neanderthal(), True)
        assert_not_allowed(watch_cook())

        access._get_permissions = user_5
        self.assertIs(prepare_food(), True)
        self.assertIs(wash_dishes(), True)
        self.assertIs(eat_properly(), True)
        self.assertIs(eat_neanderthal(), True)
        self.assertIs(watch_cook(), True)

        access._get_permissions = user_6
        assert_not_allowed(prepare_food())
        assert_not_allowed(wash_dishes())
        assert_not_allowed(eat_properly())
        self.assertIs(eat_neanderthal(), True)
        assert_not_allowed(watch_cook())

        access._get_permissions = user_7
        self.assertIs(prepare_food(), True)
        self.assertIs(wash_dishes(), True)
        self.assertIs(eat_properly(), True)
        self.assertIs(eat_neanderthal(), True)
        self.assertIs(watch_cook(), True)
