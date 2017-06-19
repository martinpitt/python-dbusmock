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

import dbusmock


p = subprocess.Popen(['which', 'loginctl'], stdout=subprocess.PIPE)
p.communicate()
have_loginctl = (p.returncode == 0)


@unittest.skipUnless(have_loginctl, 'loginctl not installed')
class TestLogind(dbusmock.DBusTestCase):
    '''Test mocking logind'''

    @classmethod
    def setUpClass(klass):
        klass.start_system_bus()
        klass.dbus_con = klass.get_dbus(True)

        if have_loginctl:
            out = subprocess.check_output(['loginctl', '--version'],
                                          universal_newlines=True)
            klass.version = out.splitlines()[0].split()[-1]

    def setUp(self):
        self.p_mock = None

    def tearDown(self):
        if self.p_mock:
            self.p_mock.terminate()
            self.p_mock.wait()

    def test_empty(self):
        (self.p_mock, _) = self.spawn_server_template('logind', {}, stdout=subprocess.PIPE)
        cmd = ['loginctl']
        if self.version >= '209':
            cmd.append('--no-legend')
        out = subprocess.check_output(cmd + ['list-sessions'],
                                      universal_newlines=True)
        self.assertEqual(out, '')

        out = subprocess.check_output(cmd + ['list-seats'],
                                      universal_newlines=True)
        self.assertEqual(out, '')

        out = subprocess.check_output(cmd + ['list-users'],
                                      universal_newlines=True)
        self.assertEqual(out, '')

    def test_session(self):
        (self.p_mock, obj_logind) = self.spawn_server_template('logind', {}, stdout=subprocess.PIPE)

        obj_logind.AddSession('c1', 'seat0', 500, 'joe', True)

        out = subprocess.check_output(['loginctl', 'list-seats'],
                                      universal_newlines=True)
        self.assertRegex(out, r'(^|\n)seat0\s+')

        out = subprocess.check_output(['loginctl', 'show-seat', 'seat0'],
                                      universal_newlines=True)
        self.assertRegex(out, 'Id=seat0')
        if self.version <= '208':
            self.assertRegex(out, 'ActiveSession=c1')
            self.assertRegex(out, 'Sessions=c1')

        out = subprocess.check_output(['loginctl', 'list-users'],
                                      universal_newlines=True)
        self.assertRegex(out, '(^|\n) +500 +joe +($|\n)')

        # note, this does an actual getpwnam() in the client, so we cannot call
        # this with hardcoded user names; get from actual user in the system
        # out = subprocess.check_output(['loginctl', 'show-user', 'joe'],
        #                               universal_newlines=True)
        # self.assertRegex(out, 'UID=500')
        # self.assertRegex(out, 'GID=500')
        # self.assertRegex(out, 'Name=joe')
        # self.assertRegex(out, 'Sessions=c1')
        # self.assertRegex(out, 'State=active')

        out = subprocess.check_output(['loginctl', 'list-sessions'],
                                      universal_newlines=True)
        self.assertRegex(out, 'c1 +500 +joe +seat0')

        out = subprocess.check_output(['loginctl', 'show-session', 'c1'],
                                      universal_newlines=True)
        self.assertRegex(out, 'Id=c1')
        self.assertRegex(out, 'Class=user')
        self.assertRegex(out, 'Active=yes')
        self.assertRegex(out, 'State=active')
        self.assertRegex(out, 'Name=joe')

    def test_properties(self):
        (self.p_mock, obj_logind) = self.spawn_server_template('logind', {}, stdout=subprocess.PIPE)
        props = obj_logind.GetAll('org.freedesktop.login1.Manager',
                                  interface='org.freedesktop.DBus.Properties')
        self.assertEqual(props['PreparingForSleep'], False)
        self.assertEqual(props['IdleSinceHint'], 0)


if __name__ == '__main__':
    # avoid writing to stderr
    unittest.main(testRunner=unittest.TextTestRunner(stream=sys.stdout, verbosity=2))
