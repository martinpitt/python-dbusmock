#!/usr/bin/python3

# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 3 of the License, or (at your option) any
# later version.  See http://www.gnu.org/copyleft/lgpl.html for the full text
# of the license.

__author__ = 'Martin Pitt'
__copyright__ = '(c) 2013 Canonical Ltd.'

import shutil
import subprocess
import sys
import unittest

import dbus
import dbus.mainloop.glib

import dbusmock

dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
have_pkcheck = shutil.which('pkcheck')


@unittest.skipUnless(have_pkcheck, 'pkcheck not installed')
class TestPolkit(dbusmock.DBusTestCase):
    '''Test mocking polkitd'''

    @classmethod
    def setUpClass(cls):
        cls.start_system_bus()
        cls.dbus_con = cls.get_dbus(True)

    def setUp(self):
        (self.p_mock, self.obj_polkitd) = self.spawn_server_template(
            'polkitd', {}, stdout=subprocess.PIPE)
        self.dbusmock = dbus.Interface(self.obj_polkitd, dbusmock.MOCK_IFACE)

    def tearDown(self):
        self.p_mock.stdout.close()
        self.p_mock.terminate()
        self.p_mock.wait()

    def test_default(self):
        self.check_action('org.freedesktop.test.frobnicate', False)

    def test_allow_unknown(self):
        self.dbusmock.AllowUnknown(True)
        self.check_action('org.freedesktop.test.frobnicate', True)
        self.dbusmock.AllowUnknown(False)
        self.check_action('org.freedesktop.test.frobnicate', False)

    def test_set_allowed(self):
        self.dbusmock.SetAllowed(['org.freedesktop.test.frobnicate', 'org.freedesktop.test.slap'])
        self.check_action('org.freedesktop.test.frobnicate', True)
        self.check_action('org.freedesktop.test.slap', True)
        self.check_action('org.freedesktop.test.wobble', False)

    def test_hanging_call(self):
        self.dbusmock.SimulateHang(True)
        self.assertFalse(self.dbusmock.HaveHangingCalls())
        pkcheck = self.check_action_run('org.freedesktop.test.frobnicate')
        with self.assertRaises(subprocess.TimeoutExpired):
            pkcheck.wait(0.8)

        self.assertTrue(self.dbusmock.HaveHangingCalls())
        pkcheck.stdout.close()
        pkcheck.kill()
        pkcheck.wait()

    def test_hanging_call_return(self):
        self.dbusmock.SetAllowed(['org.freedesktop.test.frobnicate'])
        self.dbusmock.SimulateHangActions(['org.freedesktop.test.frobnicate',
                                           'org.freedesktop.test.slap'])
        self.assertFalse(self.dbusmock.HaveHangingCalls())

        frobnicate_pkcheck = self.check_action_run(
            'org.freedesktop.test.frobnicate')
        slap_pkcheck = self.check_action_run('org.freedesktop.test.slap')

        with self.assertRaises(subprocess.TimeoutExpired):
            frobnicate_pkcheck.wait(0.3)
        with self.assertRaises(subprocess.TimeoutExpired):
            slap_pkcheck.wait(0.3)

        self.assertTrue(self.dbusmock.HaveHangingCalls())
        self.dbusmock.ReleaseHangingCalls()

        self.check_action_result(frobnicate_pkcheck, True)
        self.check_action_result(slap_pkcheck, False)

    def test_delayed_call(self):
        self.dbusmock.SetDelay(3)
        pkcheck = self.check_action_run('org.freedesktop.test.frobnicate')
        with self.assertRaises(subprocess.TimeoutExpired):
            pkcheck.wait(0.8)
        pkcheck.stdout.close()
        pkcheck.kill()
        pkcheck.wait()

    def test_delayed_call_return(self):
        self.dbusmock.SetDelay(1)
        self.dbusmock.SetAllowed(['org.freedesktop.test.frobnicate'])
        pkcheck = self.check_action_run('org.freedesktop.test.frobnicate')
        with self.assertRaises(subprocess.TimeoutExpired):
            pkcheck.wait(0.8)
        self.check_action_result(pkcheck, True)

    @staticmethod
    def check_action_run(action):
        # pylint: disable=consider-using-with
        return subprocess.Popen(['pkcheck', '--action-id',
                                 action, '--process', '123'],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT,
                                universal_newlines=True)

    def check_action_result(self, pkcheck, expect_allow):
        out = pkcheck.communicate()[0]
        if expect_allow:
            self.assertEqual(pkcheck.returncode, 0)
            self.assertEqual(out, 'test=test\n')
        else:
            self.assertNotEqual(pkcheck.returncode, 0)
            self.assertEqual(out, 'test=test\nNot authorized.\n')

    def check_action(self, action, expect_allow):
        self.check_action_result(self.check_action_run(action), expect_allow)


if __name__ == '__main__':
    # avoid writing to stderr
    unittest.main(testRunner=unittest.TextTestRunner(stream=sys.stdout))
