#!/usr/bin/python3

# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 3 of the License, or (at your option) any
# later version.  See http://www.gnu.org/copyleft/lgpl.html for the full text
# of the license.

__author__ = 'Bastien Nocera'
__email__ = 'hadess@hadess.net'
__copyright__ = '(c) 2019 Red Hat Inc.'
__license__ = 'LGPL 3+'

import unittest
import sys
import subprocess
import dbus
import dbus.mainloop.glib
import dbusmock
import fcntl
import os

dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)


class TestLowMemoryMonitor(dbusmock.DBusTestCase):
    '''Test mocking low-memory-monitor'''

    @classmethod
    def setUpClass(klass):
        klass.start_system_bus()
        klass.dbus_con = klass.get_dbus(True)

    def setUp(self):
        (self.p_mock, self.obj_lmm) = self.spawn_server_template(
            'low_memory_monitor', {}, stdout=subprocess.PIPE)
        # set log to nonblocking
        flags = fcntl.fcntl(self.p_mock.stdout, fcntl.F_GETFL)
        fcntl.fcntl(self.p_mock.stdout, fcntl.F_SETFL, flags | os.O_NONBLOCK)
        self.last_warning = -1
        self.dbusmock = dbus.Interface(self.obj_lmm, dbusmock.MOCK_IFACE)

    def tearDown(self):
        self.p_mock.terminate()
        self.p_mock.wait()

    def test_low_memory_warning_signal(self):
        '''LowMemoryWarning signal'''

        self.dbusmock.EmitWarning(100)
        log = self.p_mock.stdout.read()
        self.assertRegex(log, b'[0-9.]+ emit .*LowMemoryWarning 100\n')

        self.dbusmock.EmitWarning(255)
        log = self.p_mock.stdout.read()
        self.assertRegex(log, b'[0-9.]+ emit .*LowMemoryWarning 255\n')


if __name__ == '__main__':
    # avoid writing to stderr
    unittest.main(testRunner=unittest.TextTestRunner(stream=sys.stdout, verbosity=2))
