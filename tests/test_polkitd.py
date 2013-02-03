#!/usr/bin/python3

# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 3 of the License, or (at your option) any
# later version.  See http://www.gnu.org/copyleft/lgpl.html for the full text
# of the license.

__author__ = 'Martin Pitt'
__email__ = 'martin.pitt@ubuntu.com'
__copyright__ = '(c) 2013 Canonical Ltd.'
__license__ = 'LGPL 3+'

import unittest
import sys
import subprocess

import dbus

import dbusmock


p = subprocess.Popen(['which', 'pkcheck'], stdout=subprocess.PIPE)
p.communicate()
have_pkcheck = (p.returncode == 0)


@unittest.skipUnless(have_pkcheck, 'pkcheck not installed')
class TestPolkit(dbusmock.DBusTestCase):
    '''Test mocking polkitd'''

    @classmethod
    def setUpClass(klass):
        klass.start_system_bus()
        klass.dbus_con = klass.get_dbus(True)

    def setUp(self):
        (self.p_mock, self.obj_polkitd) = self.spawn_server_template(
            'polkitd', {}, stdout=subprocess.PIPE)
        self.dbusmock = dbus.Interface(self.obj_polkitd, dbusmock.MOCK_IFACE)

    def tearDown(self):
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

    def check_action(self, action, expect_allow):
        pkcheck = subprocess.Popen(['pkcheck', '--action-id', action, '--process', '123'],
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT,
                                   universal_newlines=True)
        out = pkcheck.communicate()[0]
        if expect_allow:
            self.assertEqual(pkcheck.returncode, 0)
            self.assertEqual(out, 'test=test\n')
        else:
            self.assertNotEqual(pkcheck.returncode, 0)
            self.assertEqual(out, 'test=test\nNot authorized.\n')


if __name__ == '__main__':
    # avoid writing to stderr
    unittest.main(testRunner=unittest.TextTestRunner(stream=sys.stdout, verbosity=2))
