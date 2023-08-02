# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 3 of the License, or (at your option) any
# later version.  See http://www.gnu.org/copyleft/lgpl.html for the full text
# of the license.

__author__ = 'Martin Pitt'
__copyright__ = '''
(c) 2013 Canonical Ltd.
(c) 2017 - 2022 Martin Pitt <martin@piware.de>
'''

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
have_loginctl = shutil.which('loginctl')


@unittest.skipUnless(have_loginctl, 'loginctl not installed')
@unittest.skipUnless(Path('/run/systemd/system').exists(), '/run/systemd/system does not exist')
class TestLogind(dbusmock.DBusTestCase):
    '''Test mocking logind'''

    @classmethod
    def setUpClass(cls):
        cls.start_system_bus()
        cls.dbus_con = cls.get_dbus(True)

        if have_loginctl:
            out = subprocess.check_output(['loginctl', '--version'],
                                          universal_newlines=True)
            cls.version = re.search(r'(\d+)', out.splitlines()[0]).group(1)

    def setUp(self):
        self.p_mock = None

    def tearDown(self):
        if self.p_mock:
            self.p_mock.stdout.close()
            self.p_mock.terminate()
            self.p_mock.wait()

    def test_empty(self):
        (self.p_mock, _) = self.spawn_server_template('logind', {}, stdout=subprocess.PIPE)
        cmd = ['loginctl']
        if self.version >= '209':
            cmd.append('--no-legend')
        out = subprocess.check_output([*cmd, 'list-sessions'],
                                      universal_newlines=True)
        self.assertEqual(out, '')

        out = subprocess.check_output([*cmd, 'list-seats'],
                                      universal_newlines=True)
        self.assertEqual(out, '')

        out = subprocess.check_output([*cmd, 'list-users'],
                                      universal_newlines=True)
        self.assertEqual(out, '')

    def test_session(self):
        (self.p_mock, obj_logind) = self.spawn_server_template('logind', {}, stdout=subprocess.PIPE)

        obj_logind.AddSession('c1', 'seat0', 500, 'joe', True)

        out = subprocess.check_output(['loginctl', 'list-seats'],
                                      universal_newlines=True)
        self.assertRegex(out, r'(^|\n)seat0\s+')

        out = subprocess.check_output(['loginctl', 'show-seat', 'seat0'],
                                      universal_newlines=True)
        self.assertRegex(out, 'Id=seat0')
        if self.version <= '208':
            self.assertRegex(out, 'ActiveSession=c1')
            self.assertRegex(out, 'Sessions=c1')

        out = subprocess.check_output(['loginctl', 'list-users'],
                                      universal_newlines=True)
        self.assertRegex(out, r'(^|\n)\s*500\s+joe\s*')

        # note, this does an actual getpwnam() in the client, so we cannot call
        # this with hardcoded user names; get from actual user in the system
        # out = subprocess.check_output(['loginctl', 'show-user', 'joe'],
        #                               universal_newlines=True)
        # self.assertRegex(out, 'UID=500')
        # self.assertRegex(out, 'GID=500')
        # self.assertRegex(out, 'Name=joe')
        # self.assertRegex(out, 'Sessions=c1')
        # self.assertRegex(out, 'State=active')

        out = subprocess.check_output(['loginctl', 'list-sessions'],
                                      universal_newlines=True)
        self.assertRegex(out, 'c1 +500 +joe +seat0')

        out = subprocess.check_output(['loginctl', 'show-session', 'c1'],
                                      universal_newlines=True)
        self.assertRegex(out, 'Id=c1')
        self.assertRegex(out, 'Class=user')
        self.assertRegex(out, 'Active=yes')
        self.assertRegex(out, 'State=active')
        self.assertRegex(out, 'Name=joe')
        self.assertRegex(out, 'LockedHint=no')

        session_mock = dbus.Interface(self.dbus_con.get_object(
            'org.freedesktop.login1', '/org/freedesktop/login1/session/c1'),
            'org.freedesktop.login1.Session')
        session_mock.SetLockedHint(True)

        out = subprocess.check_output(['loginctl', 'show-session', 'c1'],
                                      universal_newlines=True)
        self.assertRegex(out, 'Id=c1')
        self.assertRegex(out, 'LockedHint=yes')

    def test_properties(self):
        (self.p_mock, obj_logind) = self.spawn_server_template('logind', {}, stdout=subprocess.PIPE)
        props = obj_logind.GetAll('org.freedesktop.login1.Manager',
                                  interface='org.freedesktop.DBus.Properties')
        self.assertEqual(props['PreparingForSleep'], False)
        self.assertEqual(props['IdleSinceHint'], 0)

    def test_inhibit(self):
        (self.p_mock, obj_logind) = self.spawn_server_template('logind', {}, stdout=subprocess.PIPE)

        # what, who, why, mode
        fd = obj_logind.Inhibit('suspend', 'testcode', 'purpose', 'delay')

        # Our inhibitor is held
        out = subprocess.check_output(['systemd-inhibit'],
                                      universal_newlines=True)
        self.assertRegex(
            out.replace('\n', ' '),
            '(testcode +[0-9]+ +[^ ]* +[0-9]+ +[^ ]* +suspend purpose delay)|'
            '(Who: testcode.*What: suspend.*Why: purpose.*Mode: delay.*)')

        del fd
        # No inhibitor is held
        out = subprocess.check_output(['systemd-inhibit'],
                                      universal_newlines=True)
        self.assertRegex(out, 'No inhibitors|0 inhibitors listed')


if __name__ == '__main__':
    # avoid writing to stderr
    unittest.main(testRunner=unittest.TextTestRunner(stream=sys.stdout))
