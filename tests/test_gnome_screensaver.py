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
import os
import sys
import subprocess
import fcntl

import dbusmock


class TestGnomeScreensaver(dbusmock.DBusTestCase):
    '''Test mocking gnome-screensaver'''

    @classmethod
    def setUpClass(klass):
        klass.start_session_bus()
        klass.dbus_con = klass.get_dbus(False)

    def setUp(self):
        (self.p_mock, self.obj_ss) = self.spawn_server_template(
            'gnome_screensaver', {}, stdout=subprocess.PIPE)
        # set log to nonblocking
        flags = fcntl.fcntl(self.p_mock.stdout, fcntl.F_GETFL)
        fcntl.fcntl(self.p_mock.stdout, fcntl.F_SETFL, flags | os.O_NONBLOCK)

    def tearDown(self):
        self.p_mock.terminate()
        self.p_mock.wait()

    def test_default_state(self):
        '''Not locked by default'''

        self.assertEqual(self.obj_ss.GetActive(), False)

    def test_lock(self):
        '''Lock()'''

        self.obj_ss.Lock()
        self.assertEqual(self.obj_ss.GetActive(), True)
        self.assertGreater(self.obj_ss.GetActiveTime(), 0)

        self.assertRegex(self.p_mock.stdout.read(),
                         b'emit org.gnome.ScreenSaver.ActiveChanged True\n')

    def test_set_active(self):
        '''SetActive()'''

        self.obj_ss.SetActive(True)
        self.assertEqual(self.obj_ss.GetActive(), True)
        self.assertRegex(self.p_mock.stdout.read(),
                         b'emit org.gnome.ScreenSaver.ActiveChanged True\n')

        self.obj_ss.SetActive(False)
        self.assertEqual(self.obj_ss.GetActive(), False)
        self.assertRegex(self.p_mock.stdout.read(),
                         b'emit org.gnome.ScreenSaver.ActiveChanged False\n')

if __name__ == '__main__':
    # avoid writing to stderr
    unittest.main(testRunner=unittest.TextTestRunner(stream=sys.stdout, verbosity=2))
