# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 3 of the License, or (at your option) any
# later version.  See http://www.gnu.org/copyleft/lgpl.html for the full text
# of the license.

__author__ = 'Bastien Nocera'
__copyright__ = '''
(c) 2021 Red Hat Inc.
(c) 2017 - 2022 Martin Pitt <martin@piware.de>
'''

import fcntl
import os
import shutil
import subprocess
import sys
import time
import unittest

import dbus
import dbus.mainloop.glib

import dbusmock

dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

have_powerprofilesctl = shutil.which('powerprofilesctl')


@unittest.skipUnless(have_powerprofilesctl, 'powerprofilesctl not installed')
class TestPowerProfilesDaemon(dbusmock.DBusTestCase):
    '''Test mocking power-profiles-daemon'''
    @classmethod
    def setUpClass(cls):
        cls.start_system_bus()
        cls.dbus_con = cls.get_dbus(True)

    def setUp(self):
        (self.p_mock, self.obj_ppd) = self.spawn_server_template(
            'power_profiles_daemon', {}, stdout=subprocess.PIPE)
        # set log to nonblocking
        flags = fcntl.fcntl(self.p_mock.stdout, fcntl.F_GETFL)
        fcntl.fcntl(self.p_mock.stdout, fcntl.F_SETFL, flags | os.O_NONBLOCK)
        self.dbusmock = dbus.Interface(self.obj_ppd, dbusmock.MOCK_IFACE)

    def tearDown(self):
        self.p_mock.stdout.close()
        self.p_mock.terminate()
        self.p_mock.wait()

    def test_list_profiles(self):
        '''List Profiles and check active profile'''

        out = subprocess.check_output(['powerprofilesctl'],
                                      universal_newlines=True)

        self.assertIn('performance:\n', out)
        self.assertIn('\n* balanced:\n', out)

    def test_change_profile(self):
        '''Change ActiveProfile'''

        subprocess.check_output(['powerprofilesctl', 'set', 'performance'],
                                universal_newlines=True)
        out = subprocess.check_output(['powerprofilesctl', 'get'],
                                      universal_newlines=True)
        self.assertEqual(out, 'performance\n')

    def run_powerprofilesctl_list_holds(self):
        return subprocess.check_output(['powerprofilesctl', 'list-holds'],
                                       universal_newlines=True)

    def test_list_holds(self):
        '''Test holds'''

        # No holds
        out = self.run_powerprofilesctl_list_holds()
        self.assertEqual(out, '')

        # 1 hold
        # pylint: disable=consider-using-with
        cmd = subprocess.Popen(['powerprofilesctl', 'launch', '-p',
                                'power-saver', '-r', 'g-s-d mock test',
                                '-i', 'org.gnome.SettingsDaemon.Power',
                                'sleep', '60'],
                               stdout=subprocess.PIPE)
        time.sleep(0.3)

        out = self.run_powerprofilesctl_list_holds()
        self.assertEqual(out, 'Hold:\n'
                              '  Profile:         power-saver\n'
                              '  Application ID:'
                              '  org.gnome.SettingsDaemon.Power\n'
                              '  Reason:          g-s-d mock test\n')

        # 2 holds
        # pylint: disable=consider-using-with
        cmd2 = subprocess.Popen(['powerprofilesctl', 'launch', '-p',
                                 'performance', '-r', 'running some game',
                                 '-i', 'com.game.Game', 'sleep', '60'],
                                stdout=subprocess.PIPE)
        out = None
        timeout = 2.0
        while timeout > 0:
            time.sleep(0.1)
            timeout -= 0.1
            out = self.run_powerprofilesctl_list_holds()
            if out != '':
                break
        else:
            self.fail('could not list holds')

        self.assertEqual(out, 'Hold:\n'
                              '  Profile:         power-saver\n'
                              '  Application ID:'
                              '  org.gnome.SettingsDaemon.Power\n'
                              '  Reason:          g-s-d mock test\n\n'
                              'Hold:\n'
                              '  Profile:         performance\n'
                              '  Application ID:  com.game.Game\n'
                              '  Reason:          running some game\n')

        cmd.stdout.close()
        cmd.terminate()
        cmd.wait()

        cmd2.stdout.close()
        cmd2.terminate()
        cmd2.wait()

    def test_release_hold(self):
        '''Test release holds'''

        # No holds
        out = self.run_powerprofilesctl_list_holds()
        self.assertEqual(out, '')

        # hold profile
        cookie = self.obj_ppd.HoldProfile('performance',
                                          'release test',
                                          'com.test.Test')
        out = self.run_powerprofilesctl_list_holds()
        self.assertEqual(out, 'Hold:\n'
                              '  Profile:         performance\n'
                              '  Application ID:  com.test.Test\n'
                              '  Reason:          release test\n')

        # release profile
        self.obj_ppd.ReleaseProfile(cookie)
        time.sleep(0.3)
        out = self.run_powerprofilesctl_list_holds()
        self.assertEqual(out, '')


if __name__ == '__main__':
    # avoid writing to stderr
    unittest.main(testRunner=unittest.TextTestRunner(stream=sys.stdout,
                                                     verbosity=2))
