# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 3 of the License, or (at your option) any
# later version.  See http://www.gnu.org/copyleft/lgpl.html for the full text
# of the license.

__author__ = "Guido Günther"
__copyright__ = """
(c) 2024 The Phosh Developers
"""

import shutil
import subprocess
import sys
import unittest

import dbus
import dbus.mainloop.glib

import dbusmock

dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

mmcli_has_cbm_support = False
have_mmcli = shutil.which("mmcli")
if have_mmcli:
    out = subprocess.run(["mmcli", "--help"], capture_output=True, text=True)  # pylint: disable=subprocess-run-check
    mmcli_has_cbm_support = "--help-cell-broadcast" in out.stdout


class TestModemManagerBase(dbusmock.DBusTestCase):
    """Test mocking ModemManager"""

    dbus_interface = ""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.start_system_bus()
        cls.dbus_con = cls.get_dbus(True)

    def setUp(self):
        super().setUp()
        (self.p_mock, self.p_obj) = self.spawn_server_template("modemmanager", {}, stdout=subprocess.PIPE)

    def tearDown(self):
        if self.p_mock:
            self.p_mock.stdout.close()
            self.p_mock.terminate()
            self.p_mock.wait()

        super().tearDown()

    def get_property(self, name):
        return self.p_obj.Get(self.dbus_interface, name, dbus_interface=dbus.PROPERTIES_IFACE)


@unittest.skipUnless(have_mmcli, "mmcli utility not available")
class TestModemManagerMmcliBase(TestModemManagerBase):
    """Base ModemManager interface tests using mmcli"""

    ret = None

    def run_mmcli(self, args):
        self.assertIsNone(self.ret)
        self.ret = subprocess.run(  # pylint: disable=subprocess-run-check
            ["mmcli", *args], capture_output=True, text=True
        )

    def assertOutputEquals(self, expected_lines):
        self.assertIsNotNone(self.ret)
        lines = self.ret.stdout.split("\n")
        self.assertEqual(len(lines), len(expected_lines))
        for expected, line in zip(expected_lines, lines):
            self.assertEqual(expected, line)

    def assertOutputContainsLine(self, expected_line, ret=0):
        self.assertEqual(self.ret.returncode, ret)
        self.assertIn(expected_line, self.ret.stdout)


class TestModemManagerModemMmcli(TestModemManagerMmcliBase):
    """main ModemManager interface tests using mmcli"""

    def test_no_modems(self):
        self.run_mmcli(["-m", "any"])
        self.assertEqual(self.ret.returncode, 1)
        self.assertIn("error: couldn't find modem", self.ret.stderr)

    def test_modem(self):
        self.p_obj.AddSimpleModem()
        self.run_mmcli(["-m", "any"])
        self.assertOutputEquals(
            [
                "  -----------------------------",
                "  General  |              path: /org/freedesktop/ModemManager1/Modems/8",
                "  -----------------------------",
                "  Hardware |             model: E1750",
                "           | firmware revision: 11.126.08.01.00",
                "  -----------------------------",
                "  Status   |             state: enabled",
                "           |       power state: on",
                "           |       access tech: lte",
                "           |    signal quality: 70% (recent)",
                "  -----------------------------",
                "  Modes    |         supported: allowed: 4g; preferred: 4g",
                "           |                    allowed: 2g, 3g; preferred: 3g",
                "           |           current: allowed: 4g; preferred: 4g",
                "  -----------------------------",
                "  3GPP     |              imei: doesnotmatter",
                "           |       operator id: 00101",
                "           |     operator name: TheOperator",
                "           |      registration: idle",
                "  -----------------------------",
                "  SIM      |  primary sim path: /org/freedesktop/ModemManager1/SIM/2",
                "",
            ]
        )

    def test_sim(self):
        self.p_obj.AddSimpleModem()
        self.run_mmcli(["-i", "any"])
        self.assertOutputEquals(
            [
                "  --------------------",
                "  General    |   path: /org/freedesktop/ModemManager1/SIM/2",
                "  --------------------",
                "  Properties | active: yes",
                "             |   imsi: doesnotmatter",
                "",
            ]
        )

    def test_voice_call_list(self):
        self.p_obj.AddSimpleModem()
        self.run_mmcli(["-m", "any", "--voice-list-calls"])
        self.assertOutputContainsLine("No calls were found\n")

    def test_voice_status(self):
        self.p_obj.AddSimpleModem()
        self.run_mmcli(["-m", "any", "--voice-status"])
        self.assertOutputContainsLine("emergency only: no\n")

    @unittest.skipUnless(mmcli_has_cbm_support, "mmcli has no CBM suppot")
    def test_cbm(self):
        self.p_obj.AddSimpleModem()
        self.p_obj.AddCbm(2, 4383, "This is a test")
        self.run_mmcli(["-m", "any", "--cell-broadcast-list-cbm"])
        self.assertOutputEquals(
            [
                "    /org/freedesktop/ModemManager1/Cbm/1 (received)",
                "",
            ]
        )


if __name__ == "__main__":
    # avoid writing to stderr
    unittest.main(testRunner=unittest.TextTestRunner(stream=sys.stdout))
