# SPDX-License-Identifier: LGPL-3.0-or-later

__author__ = "Martin Pitt"
__copyright__ = """
(c) 2013 Canonical Ltd.
(c) 2017 - 2025 Martin Pitt <martin@piware.de>
"""

import fcntl
import os
import re
import shutil
import subprocess
import sys
import tracemalloc
import unittest
from pathlib import Path

import dbus

import dbusmock

tracemalloc.start(25)
have_loginctl = shutil.which("loginctl")


@unittest.skipUnless(have_loginctl, "loginctl not installed")
@unittest.skipUnless(Path("/run/systemd/system").exists(), "/run/systemd/system does not exist")
class TestLogind(dbusmock.DBusTestCase):
    """Test mocking logind"""

    @classmethod
    def setUpClass(cls):
        cls.start_system_bus()
        cls.dbus_con = cls.get_dbus(True)

        if have_loginctl:
            out = subprocess.check_output(["loginctl", "--version"], text=True)
            cls.version = re.search(r"(\d+)", out.splitlines()[0]).group(1)

    def setUp(self):
        (self.p_mock, self.obj_logind) = self.spawn_server_template("logind", {}, stdout=subprocess.PIPE)
        self.addCleanup(self.p_mock.wait)
        self.addCleanup(self.p_mock.terminate)
        self.addCleanup(self.p_mock.stdout.close)

        flags = fcntl.fcntl(self.p_mock.stdout, fcntl.F_GETFL)
        fcntl.fcntl(self.p_mock.stdout, fcntl.F_SETFL, flags | os.O_NONBLOCK)

    def test_empty(self):
        cmd = ["loginctl"]
        if self.version >= "209":
            cmd.append("--no-legend")
        out = subprocess.check_output([*cmd, "list-sessions"], text=True)
        self.assertEqual(out, "")

        out = subprocess.check_output([*cmd, "list-seats"], text=True)
        self.assertEqual(out, "")

        out = subprocess.check_output([*cmd, "list-users"], text=True)
        self.assertEqual(out, "")

    def test_session(self):
        self.obj_logind.AddSession("c1", "seat0", 500, "joe", True)

        out = subprocess.check_output(["loginctl", "list-seats"], text=True)
        self.assertRegex(out, r"(^|\n)seat0\s+")

        out = subprocess.check_output(["loginctl", "show-seat", "seat0"], text=True)
        self.assertRegex(out, "Id=seat0")
        if self.version <= "208":
            self.assertRegex(out, "ActiveSession=c1")
            self.assertRegex(out, "Sessions=c1")

        out = subprocess.check_output(["loginctl", "list-users"], text=True)
        self.assertRegex(out, r"(^|\n)\s*500\s+joe\s*")

        # note, this does an actual getpwnam() in the client, so we cannot call
        # this with hardcoded user names; get from actual user in the system
        # out = subprocess.check_output(['loginctl', 'show-user', 'joe'],
        #                               universal_newlines=True)
        # self.assertRegex(out, 'UID=500')
        # self.assertRegex(out, 'GID=500')
        # self.assertRegex(out, 'Name=joe')
        # self.assertRegex(out, 'Sessions=c1')
        # self.assertRegex(out, 'State=active')

        out = subprocess.check_output(["loginctl", "list-sessions"], text=True)
        self.assertRegex(out, "c1 +500 +joe +seat0")

        out = subprocess.check_output(["loginctl", "show-session", "c1"], text=True)
        self.assertRegex(out, "Id=c1")
        self.assertRegex(out, "Class=user")
        self.assertRegex(out, "Active=yes")
        self.assertRegex(out, "State=active")
        self.assertRegex(out, "Name=joe")
        self.assertRegex(out, "LockedHint=no")

        session_mock = dbus.Interface(
            self.dbus_con.get_object("org.freedesktop.login1", "/org/freedesktop/login1/session/c1"),
            "org.freedesktop.login1.Session",
        )
        session_mock.SetLockedHint(True)

        out = subprocess.check_output(["loginctl", "show-session", "c1"], text=True)
        self.assertRegex(out, "Id=c1")
        self.assertRegex(out, "LockedHint=yes")

    def test_properties(self):
        props = self.obj_logind.GetAll("org.freedesktop.login1.Manager", interface=dbus.PROPERTIES_IFACE)
        self.assertEqual(props["PreparingForSleep"], False)
        self.assertEqual(props["IdleSinceHint"], 0)

    def test_inhibit(self):
        # what, who, why, mode
        fd = self.obj_logind.Inhibit("suspend", "testcode", "purpose", "delay")

        # Our inhibitor is held
        out = subprocess.check_output(["systemd-inhibit"], text=True)
        self.assertRegex(
            out.replace("\n", " "),
            "(testcode +[0-9]+ +[^ ]* +[0-9]+ +[^ ]* +suspend purpose delay)|"
            "(Who: testcode.*What: suspend.*Why: purpose.*Mode: delay.*)",
        )

        del fd
        # No inhibitor is held
        out = subprocess.check_output(["systemd-inhibit"], text=True)
        self.assertRegex(out, "No inhibitors|0 inhibitors listed")

    def test_suspend(self):
        (p_mock_polkit, _obj_polkitd) = self.spawn_server_template("polkitd", {}, stdout=subprocess.DEVNULL)
        self.addCleanup(p_mock_polkit.wait)
        self.addCleanup(p_mock_polkit.terminate)

        subprocess.check_call(["systemctl", "suspend"])

        log = self.p_mock.stdout.read().decode()
        self.assertIn('SetWallMessage "" True', log)
        self.assertIn("Suspend True", log)


if __name__ == "__main__":
    # avoid writing to stderr
    unittest.main(testRunner=unittest.TextTestRunner(stream=sys.stdout))
