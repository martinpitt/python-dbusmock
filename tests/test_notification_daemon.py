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
import fcntl
import os
import dbus

import dbusmock

try:
    notify_send_version = subprocess.check_output(['notify-send', '--version'],
                                                  universal_newlines=True)
    notify_send_version = notify_send_version.split()[-1]
except (OSError, subprocess.CalledProcessError):
    notify_send_version = ''


@unittest.skipUnless(notify_send_version, 'notify-send not installed')
class TestNotificationDaemon(dbusmock.DBusTestCase):
    '''Test mocking notification-daemon'''

    @classmethod
    def setUpClass(klass):
        klass.start_session_bus()
        klass.dbus_con = klass.get_dbus(False)

    def setUp(self):
        (self.p_mock, self.obj_daemon) = self.spawn_server_template(
            'notification_daemon', {}, stdout=subprocess.PIPE)
        # set log to nonblocking
        flags = fcntl.fcntl(self.p_mock.stdout, fcntl.F_GETFL)
        fcntl.fcntl(self.p_mock.stdout, fcntl.F_SETFL, flags | os.O_NONBLOCK)

    def tearDown(self):
        self.p_mock.terminate()
        self.p_mock.wait()

    def test_no_options(self):
        '''notify-send with no options'''

        subprocess.check_call(['notify-send', 'title', 'my text'])
        log = self.p_mock.stdout.read()
        self.assertRegex(log, b'[0-9.]+ Notify "notify-send" 0 "" "title" "my text" \\[\\]')

    @unittest.skipIf(notify_send_version < '0.7.5', 'this requires libnotify >= 0.7.5')
    def test_options(self):
        '''notify-send with some options'''

        subprocess.check_call(['notify-send', '-t', '27', '-a', 'fooApp',
                               '-i', 'warning_icon', 'title', 'my text'])
        log = self.p_mock.stdout.read()
        self.assertRegex(log, b'[0-9.]+ Notify "fooApp" 0 "warning_icon" "title" "my text" \\[\\] {"urgency": 1} 27\n')

    def test_id(self):
        '''ID handling'''

        notify_proxy = dbus.Interface(
            self.dbus_con.get_object('org.freedesktop.Notifications', '/org/freedesktop/Notifications'),
            'org.freedesktop.Notifications')

        # with input ID 0 it should generate new IDs
        id = notify_proxy.Notify('test', 0, '', 'summary', 'body', [], {}, -1)
        self.assertEqual(id, 1)
        id = notify_proxy.Notify('test', 0, '', 'summary', 'body', [], {}, -1)
        self.assertEqual(id, 2)

        # an existing ID should just be bounced back
        id = notify_proxy.Notify('test', 4, '', 'summary', 'body', [], {}, -1)
        self.assertEqual(id, 4)
        id = notify_proxy.Notify('test', 1, '', 'summary', 'body', [], {}, -1)
        self.assertEqual(id, 1)

        # the previous doesn't forget the counter
        id = notify_proxy.Notify('test', 0, '', 'summary', 'body', [], {}, -1)
        self.assertEqual(id, 3)

    def test_close(self):
        '''CloseNotification() and NotificationClosed() signal'''

        notify_proxy = dbus.Interface(
            self.dbus_con.get_object('org.freedesktop.Notifications', '/org/freedesktop/Notifications'),
            'org.freedesktop.Notifications')

        id = notify_proxy.Notify('test', 0, '', 'summary', 'body', [], {}, -1)
        self.assertEqual(id, 1)

        # known notification, should send a signal
        notify_proxy.CloseNotification(id)
        log = self.p_mock.stdout.read()
        self.assertRegex(log, b'[0-9.]+ emit .*NotificationClosed 1 1\n')

        # unknown notification, don't send a signal
        notify_proxy.CloseNotification(id + 1)
        log = self.p_mock.stdout.read()
        self.assertNotIn(b'NotificationClosed', log)


if __name__ == '__main__':
    # avoid writing to stderr
    unittest.main(testRunner=unittest.TextTestRunner(stream=sys.stdout, verbosity=2))
