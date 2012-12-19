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

import dbusmock


p = subprocess.Popen(['which', 'notify-send'], stdout=subprocess.PIPE)
p.communicate()
have_notify_send = (p.returncode == 0)


@unittest.skipUnless(have_notify_send, 'notify-send not installed')
class TestNotificationDaemon(dbusmock.DBusTestCase):
    '''Test mocking notification-daemon'''

    @classmethod
    def setUpClass(klass):
        klass.start_session_bus()

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
        self.assertRegex(log, b'[0-9.]+ Notify "notify-send" 0 "" "title" "my text" \[\]')

    def test_options(self):
        '''notify-send with some options'''

        subprocess.check_call(['notify-send', '-t', '27', '-a', 'fooApp',
                               '-i', 'warning_icon', 'title', 'my text'])
        log = self.p_mock.stdout.read()
        self.assertRegex(log, b'[0-9.]+ Notify "fooApp" 0 "warning_icon" "title" "my text" \[\] {"urgency": 1} 27\n')

if __name__ == '__main__':
    # avoid writing to stderr
    unittest.main(testRunner=unittest.TextTestRunner(stream=sys.stdout, verbosity=2))
