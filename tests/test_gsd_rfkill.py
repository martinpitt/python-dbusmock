# SPDX-License-Identifier: LGPL-3.0-or-later

__author__ = "Guido Günther"
__copyright__ = "2024 The Phosh Developers"

import fcntl
import os
import subprocess
import sys
import unittest

import dbus

import dbusmock


class TestGsdRfkill(dbusmock.DBusTestCase):
    """Test mocked GNOME Settings Daemon Rfkill"""

    @classmethod
    def setUpClass(cls):
        cls.start_session_bus()
        cls.dbus_con = cls.get_dbus()

    def setUp(self):
        (self.p_mock, self.p_obj) = self.spawn_server_template("gsd_rfkill", {}, stdout=subprocess.PIPE)
        self.addCleanup(self.p_mock.wait)
        self.addCleanup(self.p_mock.terminate)
        self.addCleanup(self.p_mock.stdout.close)
        # set log to nonblocking
        flags = fcntl.fcntl(self.p_mock.stdout, fcntl.F_GETFL)
        fcntl.fcntl(self.p_mock.stdout, fcntl.F_SETFL, flags | os.O_NONBLOCK)

    def test_mainobject(self):
        propiface = dbus.Interface(self.p_obj, dbus.PROPERTIES_IFACE)

        mode = propiface.Get("org.gnome.SettingsDaemon.Rfkill", "AirplaneMode")
        self.assertEqual(mode, False)
        mode = propiface.Get("org.gnome.SettingsDaemon.Rfkill", "HasAirplaneMode")
        self.assertEqual(mode, True)

    def test_airplane_mode(self):
        propiface = dbus.Interface(self.p_obj, dbus.PROPERTIES_IFACE)

        self.p_obj.SetAirplaneMode(True)

        mode = propiface.Get("org.gnome.SettingsDaemon.Rfkill", "AirplaneMode")
        self.assertEqual(mode, True)
        mode = propiface.Get("org.gnome.SettingsDaemon.Rfkill", "BluetoothAirplaneMode")
        self.assertEqual(mode, True)
        mode = propiface.Get("org.gnome.SettingsDaemon.Rfkill", "WwanAirplaneMode")
        self.assertEqual(mode, True)


if __name__ == "__main__":
    # avoid writing to stderr
    unittest.main(testRunner=unittest.TextTestRunner(stream=sys.stdout))
