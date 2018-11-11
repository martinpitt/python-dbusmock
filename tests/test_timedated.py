#!/usr/bin/python3

# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 3 of the License, or (at your option) any
# later version.  See http://www.gnu.org/copyleft/lgpl.html for the full text
# of the license.

__author__ = 'Iain Lane'
__email__ = 'iain.lane@canonical.com'
__copyright__ = '(c) 2013 Canonical Ltd.'
__license__ = 'LGPL 3+'

import unittest
import os
import sys
import subprocess

import dbusmock

# timedatectl keeps changing its CLI output
TIMEDATECTL_NTP_LABEL = '(NTP enabled|synchronized|systemd-timesyncd.service active)'

p = subprocess.Popen(['which', 'timedatectl'], stdout=subprocess.PIPE)
p.communicate()
have_timedatectl = (p.returncode == 0)


@unittest.skipUnless(have_timedatectl, 'timedatectl not installed')
@unittest.skipUnless(os.path.exists('/run/systemd/system'), '/run/systemd/system does not exist')
class TestTimedated(dbusmock.DBusTestCase):
    '''Test mocking timedated'''

    @classmethod
    def setUpClass(klass):
        klass.start_system_bus()
        klass.dbus_con = klass.get_dbus(True)

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
        self.assertRegex(out, '%s: yes' % TIMEDATECTL_NTP_LABEL)

    def test_changing_ntp(self):
        self.obj_timedated.SetNTP(False, False)
        out = self.run_timedatectl()
        self.assertRegex(out, '%s: no' % TIMEDATECTL_NTP_LABEL)

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
        stream=sys.stdout, verbosity=2))
