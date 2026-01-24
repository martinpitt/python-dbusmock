# SPDX-License-Identifier: LGPL-3.0-or-later

__author__ = "Martin Pitt"
__copyright__ = """
(c) 2013 Canonical Ltd.
(c) 2017 - 2022 Martin Pitt <martin@piware.de>
"""

import fcntl
import os
import subprocess
import sys
import unittest

import dbusmock


class TestGnomeScreensaver(dbusmock.DBusTestCase):
    """Test mocking gnome-screensaver"""

    @classmethod
    def setUpClass(cls):
        cls.start_session_bus()
        cls.dbus_con = cls.get_dbus(False)

    def setUp(self):
        (self.p_mock, self.obj_ss) = self.spawn_server_template("gnome_screensaver", {}, stdout=subprocess.PIPE)
        self.addCleanup(self.p_mock.wait)
        self.addCleanup(self.p_mock.terminate)
        self.addCleanup(self.p_mock.stdout.close)
        # set log to nonblocking
        flags = fcntl.fcntl(self.p_mock.stdout, fcntl.F_GETFL)
        fcntl.fcntl(self.p_mock.stdout, fcntl.F_SETFL, flags | os.O_NONBLOCK)

    def test_default_state(self):
        """Not locked by default"""

        self.assertEqual(self.obj_ss.GetActive(), False)

    def test_lock(self):
        """Lock()"""

        self.obj_ss.Lock()
        self.assertEqual(self.obj_ss.GetActive(), True)
        self.assertGreater(self.obj_ss.GetActiveTime(), 0)

        self.assertRegex(
            self.p_mock.stdout.read(), b"emit /org/gnome/ScreenSaver org.gnome.ScreenSaver.ActiveChanged True\n"
        )

    def test_set_active(self):
        """SetActive()"""

        self.obj_ss.SetActive(True)
        self.assertEqual(self.obj_ss.GetActive(), True)
        self.assertRegex(
            self.p_mock.stdout.read(), b"emit /org/gnome/ScreenSaver org.gnome.ScreenSaver.ActiveChanged True\n"
        )

        self.obj_ss.SetActive(False)
        self.assertEqual(self.obj_ss.GetActive(), False)
        self.assertRegex(
            self.p_mock.stdout.read(), b"emit /org/gnome/ScreenSaver org.gnome.ScreenSaver.ActiveChanged False\n"
        )


if __name__ == "__main__":
    # avoid writing to stderr
    unittest.main(testRunner=unittest.TextTestRunner(stream=sys.stdout))
