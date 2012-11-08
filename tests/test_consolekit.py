#!/usr/bin/python3

# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 3 of the License, or (at your option) any
# later version.  See http://www.gnu.org/copyleft/lgpl.html for the full text
# of the license.

__author__ = 'Martin Pitt'
__email__ = 'martin.pitt@ubuntu.com'
__copyright__ = '(c) 2012 Canonical Ltd.'
__license__ = 'LGPL 3+'

import unittest
import sys
import subprocess
import os.path

import dbus

import dbusmock


@unittest.skipUnless(os.path.exists('/usr/bin/ck-list-sessions'),
                     'ck-list-sessions not installed')
class TestConsoleKit(dbusmock.DBusTestCase):
    @classmethod
    def setUpClass(klass):
        klass.start_system_bus()
        klass.dbus_con = klass.get_dbus(True)

    def setUp(self):
        self.p_mock = self.spawn_server('org.freedesktop.ConsoleKit',
                                        '/org/freedesktop/ConsoleKit/Manager',
                                        'org.freedesktop.ConsoleKit.Manager',
                                        system_bus=True,
                                        stdout=subprocess.PIPE)

        self.dbusmock = dbus.Interface(self.dbus_con.get_object(
            'org.freedesktop.ConsoleKit', '/org/freedesktop/ConsoleKit/Manager'),
            dbusmock.MOCK_IFACE)

    def tearDown(self):
        self.p_mock.terminate()
        self.p_mock.wait()

    def test_one_active_session(self):
        self.dbusmock.AddMethods('', (
            ('GetSessions', '', 'ao', 'ret = ["/org/freedesktop/ConsoleKit/MockSession"]'),
            ('GetCurrentSession', '', 'o', 'ret = "/org/freedesktop/ConsoleKit/MockSession"'),
            ('GetSeats', '', 'ao', 'ret = ["/org/freedesktop/ConsoleKit/MockSeat"]'),
        ))

        self.dbusmock.AddObject('/org/freedesktop/ConsoleKit/MockSeat',
                                'org.freedesktop.ConsoleKit.Seat',
                                {},
                                [
                                    ('GetSessions', '', 'ao',
                                     'ret = ["/org/freedesktop/ConsoleKit/MockSession"]'),
                                ])

        self.dbusmock.AddObject('/org/freedesktop/ConsoleKit/MockSession',
                                'org.freedesktop.ConsoleKit.Session',
                                {},
                                [
                                    ('GetSeatId', '', 'o', 'ret = "/org/freedesktop/ConsoleKit/MockSeat"'),
                                    ('GetUnixUser', '', 'u', 'ret = os.geteuid()'),
                                    ('GetCreationTime', '', 's', 'ret = "2012-01-01T01:23:45.600000Z"'),
                                    ('GetIdleSinceHint', '', 's', 'ret = "2012-01-01T02:23:45.600000Z"'),
                                    ('IsLocal', '', 'b', 'ret = True'),
                                    ('IsActive', '', 'b', 'ret = True'),
                                    ('GetDisplayDevice', '', 's', 'ret = ""'),
                                    ('GetX11DisplayDevice', '', 's', 'ret = "/dev/tty7"'),
                                    ('GetX11Display', '', 's', 'ret = os.environ.get("DISPLAY", "95:0")'),
                                    ('GetRemoteHostName', '', 's', 'ret = ""'),
                                    ('GetSessionType', '', 's', 'ret = ""'),
                                    ('GetLoginSessionId', '', 's', 'ret = "12345"'),
                                ])

        out = subprocess.check_output(['ck-list-sessions'], universal_newlines=True)
        self.assertRegex(out, '^MockSession:')
        self.assertRegex(out, 'is-local = TRUE')
        self.assertRegex(out, "login-session-id = '12345'")

if __name__ == '__main__':
    # avoid writing to stderr
    unittest.main(testRunner=unittest.TextTestRunner(stream=sys.stdout, verbosity=2))
