#!/usr/bin/python3
""" Tests for accounts service """

# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 3 of the License, or (at your option) any
# later version.  See http://www.gnu.org/copyleft/lgpl.html for the full text
# of the license.

__author__ = 'Marco Trevisan'
__copyright__ = '(c) 2021 Canonical Ltd.'

import subprocess
import sys
import time
import unittest

import dbus
import dbusmock

try:
    import gi  # type: ignore
    gi.require_version('AccountsService', '1.0')
    from gi.repository import AccountsService, GLib
    have_accounts_service = True
except (ImportError, ValueError):
    have_accounts_service = False


@unittest.skipUnless(have_accounts_service,
                     'AccountsService gi introspection not available')
class TestAccountsService(dbusmock.DBusTestCase):
    '''Test mocking AccountsService'''

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.start_system_bus()
        cls.dbus_con = cls.get_dbus(True)
        cls.ctx = GLib.main_context_default()

    def setUp(self):
        super().setUp()
        (self.p_mock, self.p_obj) = self.spawn_server_template(
            'accounts_service', {}, stdout=subprocess.PIPE)
        self.p_manager = AccountsService.UserManager.get_default()
        while not self.p_manager.props.is_loaded:
            self.ctx.iteration(True)
        self.assertFalse(self.p_manager.no_service())
        self.assertTrue(self.p_manager.props.is_loaded)

    def get_property(self, name):
        return self.p_obj.Get('org.freedesktop.Accounts', name,
                              dbus_interface=dbus.PROPERTIES_IFACE)

    def tearDown(self):
        for user in self.p_manager.list_users():
            self.p_manager.delete_user(user, False)

        while self.p_manager.list_users():
            self.ctx.iteration(True)

        if self.p_mock:
            self.p_mock.stdout.close()
            self.p_mock.terminate()
            self.p_mock.wait()

        while self.p_manager.props.is_loaded:
            self.ctx.iteration(True)

        self.assertFalse(self.p_manager.props.is_loaded)
        del self.p_manager
        super().tearDown()

    def wait_changed(self, user):
        changed = False

        def on_changed(u):
            nonlocal changed
            changed = u is user
        conn_id = user.connect('changed', on_changed)
        while not changed:
            self.ctx.iteration(True)
        user.disconnect(conn_id)

    def test_empty(self):
        self.assertTrue(self.p_manager.props.is_loaded)
        self.assertFalse(self.p_manager.list_users())
        self.assertFalse(self.p_manager.props.has_multiple_users)
        self.assertFalse(self.p_obj.ListMockUsers())
        self.assertTrue(self.get_property('HasNoUsers'))
        self.assertFalse(self.get_property('HasMultipleUsers'))
        self.assertFalse(self.get_property('AutomaticLoginUsers'))
        self.assertEqual(self.get_property('DaemonVersion'), 'dbus-mock-0.1')

    def test_create_users(self):
        self.p_manager.create_user(
            'pizza', 'I Love Pizza',
            AccountsService.UserAccountType.ADMINISTRATOR)
        creation_time = int(time.time())
        self.assertFalse(self.p_manager.props.has_multiple_users)
        self.assertFalse(self.get_property('HasNoUsers'))

        [user] = self.p_manager.list_users()
        self.assertEqual([user.get_object_path()], self.p_obj.ListMockUsers())
        self.assertEqual(user.get_account_type(),
                         AccountsService.UserAccountType.ADMINISTRATOR)
        self.assertFalse(user.get_automatic_login())
        self.assertEqual(user.get_email(), 'pizza@python-dbusmock.org')
        self.assertEqual(user.get_home_dir(), '/nonexisting/mock-home/pizza')
        self.assertEqual(user.get_icon_file(), '')
        self.assertEqual(user.get_language(), 'C')
        self.assertEqual(user.get_location(), '')
        self.assertFalse(user.get_locked())
        self.assertEqual(user.get_login_frequency(), 0)
        self.assertEqual(user.get_login_history().unpack(), [])
        self.assertEqual(user.get_login_time(), 0)
        self.assertEqual(user.get_num_sessions(), 0)
        self.assertEqual(user.get_num_sessions_anywhere(), 0)
        self.assertEqual(user.get_object_path(),
                         '/org/freedesktop/Accounts/User2001')
        self.assertEqual(user.get_password_expiration_policy(),
                         (sys.maxsize, creation_time, 0, 0, 0, 0))
        self.assertEqual(user.get_password_hint(), 'Remember it, come on!')
        self.assertEqual(user.get_password_mode(),
                         AccountsService.UserPasswordMode.REGULAR)
        self.assertIsNone(user.get_primary_session_id())
        self.assertEqual(user.get_real_name(), 'I Love Pizza')
        self.assertFalse(user.get_saved())
        self.assertEqual(user.get_session(), 'mock-session')
        self.assertEqual(user.get_session_type(), 'wayland')
        self.assertEqual(user.get_shell(), '/usr/bin/zsh')
        self.assertEqual(user.get_uid(), 2001)
        self.assertEqual(user.get_user_name(), 'pizza')
        self.assertEqual(user.get_x_session(), 'mock-xsession')
        self.assertTrue(user.is_loaded())
        self.assertTrue(user.is_local_account())
        self.assertFalse(user.is_logged_in())
        self.assertFalse(user.is_logged_in_anywhere())
        self.assertFalse(user.is_nonexistent())
        self.assertFalse(user.is_system_account())

        other = self.p_manager.create_user(
            'schiacciata', 'I Love Schiacciata too',
            AccountsService.UserAccountType.STANDARD)

        while not self.p_manager.props.has_multiple_users:
            self.ctx.iteration(True)

        self.assertTrue(self.p_manager.props.has_multiple_users)
        self.assertFalse(self.get_property('HasNoUsers'))

        self.assertIn(other, self.p_manager.list_users())
        self.assertEqual(other.get_uid(), 2002)
        self.assertEqual(other.get_user_name(), 'schiacciata')
        self.assertEqual(other.get_real_name(), 'I Love Schiacciata too')
        self.assertEqual(other.get_account_type(),
                         AccountsService.UserAccountType.STANDARD)

        self.assertEqual(
            [u.get_object_path()
             for u in self.p_manager.list_users()], self.p_obj.ListMockUsers())

    def test_recreate_user(self):
        self.p_manager.create_user(
            'pizza', 'I Love Pizza',
            AccountsService.UserAccountType.ADMINISTRATOR)
        self.assertFalse(self.p_manager.props.has_multiple_users)
        self.assertFalse(self.get_property('HasNoUsers'))

        with self.assertRaises(GLib.Error) as error:
            self.p_manager.create_user(
                'pizza', 'More and more',
                AccountsService.UserAccountType.STANDARD)
        self.assertTrue(error.exception.matches(
            AccountsService.UserManagerError.quark(),
            AccountsService.UserManagerError.FAILED))
        self.assertFalse(self.p_manager.props.has_multiple_users)

    def test_set_user_properties(self):
        # pylint: disable=too-many-statements
        user = self.p_manager.create_user(
            'test-user', 'I am a Test user',
            AccountsService.UserAccountType.STANDARD)

        user.set_account_type(
            AccountsService.UserAccountType.ADMINISTRATOR)
        self.wait_changed(user)
        self.assertEqual(user.get_account_type(),
                         AccountsService.UserAccountType.ADMINISTRATOR)

        user.set_account_type(
            AccountsService.UserAccountType.STANDARD)
        self.wait_changed(user)
        self.assertEqual(user.get_account_type(),
                         AccountsService.UserAccountType.STANDARD)

        user.set_automatic_login(True)
        self.wait_changed(user)
        self.assertTrue(user.get_automatic_login())

        user.set_automatic_login(False)
        self.wait_changed(user)
        self.assertFalse(user.get_automatic_login())

        user.set_email('test@email.org')
        self.wait_changed(user)
        self.assertEqual(user.get_email(), 'test@email.org')

        user.set_icon_file('/nonexistant/home/icon.png')
        self.wait_changed(user)
        self.assertEqual(user.get_icon_file(), '/nonexistant/home/icon.png')

        user.set_language('Test Language')
        self.wait_changed(user)
        self.assertEqual(user.get_language(), 'Test Language')

        user.set_location('Test Location')
        self.wait_changed(user)
        self.assertEqual(user.get_location(), 'Test Location')

        user.set_locked(True)
        self.wait_changed(user)
        self.assertTrue(user.get_locked())

        user.set_locked(False)
        self.wait_changed(user)
        self.assertFalse(user.get_locked())

        user.set_password('Test Password', 'Test PasswordHint')
        self.wait_changed(user)
        self.assertEqual(user.get_password_hint(), 'Test PasswordHint')

        user.set_password_mode(AccountsService.UserPasswordMode.NONE)
        self.wait_changed(user)
        self.assertEqual(user.get_password_mode(),
                         AccountsService.UserPasswordMode.NONE)

        user.set_password_mode(AccountsService.UserPasswordMode.REGULAR)
        self.wait_changed(user)
        self.assertEqual(user.get_password_mode(),
                         AccountsService.UserPasswordMode.REGULAR)

        user.set_password_mode(AccountsService.UserPasswordMode.SET_AT_LOGIN)
        self.wait_changed(user)
        self.assertEqual(user.get_password_mode(),
                         AccountsService.UserPasswordMode.SET_AT_LOGIN)

        user.set_real_name('Test RealName')
        self.wait_changed(user)
        self.assertEqual(user.get_real_name(), 'Test RealName')

        user.set_session('Test Session')
        self.wait_changed(user)
        self.assertEqual(user.get_session(), 'Test Session')

        user.set_session_type('Test SessionType')
        self.wait_changed(user)
        self.assertEqual(user.get_session_type(), 'Test SessionType')

        user.set_user_name('new-test-user')
        self.wait_changed(user)
        self.assertEqual(user.get_user_name(), 'new-test-user')

        user.set_x_session('Test XSession')
        self.wait_changed(user)
        self.assertEqual(user.get_x_session(), 'Test XSession')

    def test_automatic_login_users(self):
        user = self.p_manager.create_user(
            'test-user', 'I am a Test user',
            AccountsService.UserAccountType.STANDARD)

        user.set_automatic_login(True)
        self.wait_changed(user)
        self.assertTrue(user.get_automatic_login())
        self.assertEqual(
            [user.get_object_path()],
            self.get_property('AutomaticLoginUsers'))
        self.assertCountEqual(self.p_obj.ListMockUsers(),
                              self.get_property('AutomaticLoginUsers'))

        user2 = self.p_manager.create_user(
            'another-test-user', 'I am another Test user',
            AccountsService.UserAccountType.STANDARD)
        self.assertNotIn(user2.get_object_path(),
                         self.get_property('AutomaticLoginUsers'))

        user2.set_automatic_login(True)
        self.assertIn(user2.get_object_path(),
                      self.get_property('AutomaticLoginUsers'))
        self.assertEqual(len(self.get_property('AutomaticLoginUsers')), 2)
        self.assertCountEqual(self.p_obj.ListMockUsers(),
                              self.get_property('AutomaticLoginUsers'))

        user.set_automatic_login(False)
        self.wait_changed(user)
        self.assertFalse(user.get_automatic_login())
        self.assertNotIn(user.get_object_path(),
                         self.get_property('AutomaticLoginUsers'))
        self.assertEqual(len(self.get_property('AutomaticLoginUsers')), 1)

        self.p_manager.delete_user(user2, False)
        while user2 in self.p_manager.list_users():
            self.ctx.iteration(True)
        self.assertFalse(self.get_property('AutomaticLoginUsers'))

    def test_automatic_login_users_via_mock(self):
        with self.assertRaises(dbus.exceptions.DBusException):
            self.p_obj.AddAutoLoginUser('non-existant')

        with self.assertRaises(dbus.exceptions.DBusException):
            self.p_obj.RemoveAutoLoginUser('non-existant')

        user = self.p_manager.create_user(
            'test-user', 'I am a Test user',
            AccountsService.UserAccountType.STANDARD)

        self.p_obj.AddAutoLoginUser(user.get_user_name())
        self.wait_changed(user)
        self.assertTrue(user.get_automatic_login())
        self.assertIn(user.get_object_path(),
                      self.get_property('AutomaticLoginUsers'))

        #  Adding again to check we don't get confused!
        self.p_obj.AddAutoLoginUser(user.get_user_name())
        self.assertTrue(user.get_automatic_login())
        self.assertCountEqual([user.get_object_path()],
                              self.get_property('AutomaticLoginUsers'))

        self.p_obj.RemoveAutoLoginUser(user.get_user_name())
        self.wait_changed(user)
        self.assertFalse(user.get_automatic_login())
        self.assertNotIn(user.get_object_path(),
                         self.get_property('AutomaticLoginUsers'))


if __name__ == '__main__':
    # avoid writing to stderr
    unittest.main(testRunner=unittest.TextTestRunner(
        stream=sys.stdout))
