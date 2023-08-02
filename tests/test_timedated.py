# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 3 of the License, or (at your option) any
# later version.  See http://www.gnu.org/copyleft/lgpl.html for the full text
# of the license.

__author__ = 'Iain Lane'
__copyright__ = '''
(c) 2013 Canonical Ltd.
(c) 2017 - 2022 Martin Pitt <martin@piware.de>
'''

import shutil
import subprocess
import sys
import unittest
from pathlib import Path

import dbusmock

# timedatectl keeps changing its CLI output
TIMEDATECTL_NTP_LABEL = '(NTP enabled|synchronized|systemd-timesyncd.service active)'

have_timedatectl = shutil.which('timedatectl')


@unittest.skipUnless(have_timedatectl, 'timedatectl not installed')
@unittest.skipUnless(Path('/run/systemd/system').exists(), '/run/systemd/system does not exist')
class TestTimedated(dbusmock.DBusTestCase):
    '''Test mocking timedated'''

    @classmethod
    def setUpClass(cls):
        cls.start_system_bus()
        cls.dbus_con = cls.get_dbus(True)

    def setUp(self):
        (self.p_mock, _) = self.spawn_server_template(
            'timedated',
            {},
            stdout=subprocess.PIPE)
        self.obj_timedated = self.dbus_con.get_object(
            'org.freedesktop.timedate1',
            '/org/freedesktop/timedate1')

    def tearDown(self):
        if self.p_mock:
            self.p_mock.stdout.close()
            self.p_mock.terminate()
            self.p_mock.wait()

    def run_timedatectl(self):
        return subprocess.check_output(['timedatectl'],
                                       universal_newlines=True)

    def test_default_timezone(self):
        out = self.run_timedatectl()
        # timedatectl doesn't get the timezone offset information over dbus so
        # we can't mock that.
        self.assertRegex(out, 'Time *zone: Etc/Utc')

    def test_changing_timezone(self):
        self.obj_timedated.SetTimezone('Africa/Johannesburg', False)
        out = self.run_timedatectl()
        # timedatectl doesn't get the timezone offset information over dbus so
        # we can't mock that.
        self.assertRegex(out, 'Time *zone: Africa/Johannesburg')

    def test_default_ntp(self):
        out = self.run_timedatectl()
        self.assertRegex(out, f'{TIMEDATECTL_NTP_LABEL}: yes')

    def test_changing_ntp(self):
        self.obj_timedated.SetNTP(False, False)
        out = self.run_timedatectl()
        self.assertRegex(out, f'{TIMEDATECTL_NTP_LABEL}: no')

    def test_default_local_rtc(self):
        out = self.run_timedatectl()
        self.assertRegex(out, 'RTC in local TZ: no')

    def test_changing_local_rtc(self):
        self.obj_timedated.SetLocalRTC(True, False, False)
        out = self.run_timedatectl()
        self.assertRegex(out, 'RTC in local TZ: yes')


if __name__ == '__main__':
    # avoid writing to stderr
    unittest.main(testRunner=unittest.TextTestRunner(
        stream=sys.stdout))
