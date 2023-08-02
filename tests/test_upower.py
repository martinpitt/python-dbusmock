# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 3 of the License, or (at your option) any
# later version.  See http://www.gnu.org/copyleft/lgpl.html for the full text
# of the license.

__author__ = 'Martin Pitt'
__copyright__ = '''
(c) 2012 Canonical Ltd.
(c) 2017 - 2022 Martin Pitt <martin@piware.de>
'''

import fcntl
import os
import shutil
import subprocess
import sys
import time
import tracemalloc
import unittest

import dbus

import dbusmock

UP_DEVICE_LEVEL_UNKNOWN = 0
UP_DEVICE_LEVEL_NONE = 1

tracemalloc.start(25)
have_upower = shutil.which('upower')


@unittest.skipUnless(have_upower, 'upower not installed')
class TestUPower(dbusmock.DBusTestCase):
    '''Test mocking upowerd'''

    @classmethod
    def setUpClass(cls):
        cls.start_system_bus()
        cls.dbus_con = cls.get_dbus(True)

    def setUp(self):
        (self.p_mock, self.obj_upower) = self.spawn_server_template(
            'upower', {
                'OnBattery': True,
                'HibernateAllowed': False,
                'GetCriticalAction': 'Suspend',
            },
            stdout=subprocess.PIPE)
        # set log to nonblocking
        flags = fcntl.fcntl(self.p_mock.stdout, fcntl.F_GETFL)
        fcntl.fcntl(self.p_mock.stdout, fcntl.F_SETFL, flags | os.O_NONBLOCK)
        self.dbusmock = dbus.Interface(self.obj_upower, dbusmock.MOCK_IFACE)

    def tearDown(self):
        self.p_mock.stdout.close()
        self.p_mock.terminate()
        self.p_mock.wait()

    def test_no_devices(self):
        out = subprocess.check_output(['upower', '--dump'],
                                      universal_newlines=True)
        self.assertIn('/DisplayDevice\n', out)
        # should not have any other device
        for line in out.splitlines():
            if line.endswith('/DisplayDevice'):
                continue
            self.assertNotIn('Device', line)
        self.assertRegex(out, 'on-battery:\\s+yes')
        self.assertRegex(out, 'lid-is-present:\\s+yes')
        self.assertRegex(out, 'daemon-version:\\s+0.99')
        self.assertRegex(out, 'critical-action:\\s+Suspend')
        self.assertNotIn('can-suspend', out)

    def test_one_ac(self):
        path = self.dbusmock.AddAC('mock_AC', 'Mock AC')
        self.assertEqual(path, '/org/freedesktop/UPower/devices/mock_AC')

        self.assertRegex(self.p_mock.stdout.read(),
                         b'emit /org/freedesktop/UPower org.freedesktop.UPower.DeviceAdded '
                         b'"/org/freedesktop/UPower/devices/mock_AC"\n')

        out = subprocess.check_output(['upower', '--dump'],
                                      universal_newlines=True)
        self.assertRegex(out, 'Device: ' + path)
        # note, Add* is not magic: this just adds an object, not change
        # properties
        self.assertRegex(out, 'on-battery:\\s+yes')
        self.assertRegex(out, 'lid-is-present:\\s+yes')
        # print('--------- out --------\n%s\n------------' % out)

        with subprocess.Popen(['upower', '--monitor-detail'],
                              stdout=subprocess.PIPE,
                              universal_newlines=True) as mon:
            time.sleep(0.3)
            self.dbusmock.SetDeviceProperties(path, {
                'PowerSupply': dbus.Boolean(True, variant_level=1)
            })
            time.sleep(0.2)

            mon.terminate()
            out = mon.communicate()[0]
            self.assertRegex(out, 'device changed:\\s+' + path)
            # print('--------- monitor out --------\n%s\n------------' % out)

    def test_discharging_battery(self):
        path = self.dbusmock.AddDischargingBattery('mock_BAT', 'Mock Battery', 30.0, 1200)
        self.assertEqual(path, '/org/freedesktop/UPower/devices/mock_BAT')

        self.assertRegex(self.p_mock.stdout.read(),
                         b'emit /org/freedesktop/UPower org.freedesktop.UPower.DeviceAdded '
                         b'"/org/freedesktop/UPower/devices/mock_BAT"\n')

        out = subprocess.check_output(['upower', '--dump'],
                                      universal_newlines=True)
        self.assertRegex(out, 'Device: ' + path)
        # note, Add* is not magic: this just adds an object, not change
        # properties
        self.assertRegex(out, 'on-battery:\\s+yes')
        self.assertRegex(out, 'lid-is-present:\\s+yes')
        self.assertRegex(out, ' present:\\s+yes')
        self.assertRegex(out, ' percentage:\\s+30%')
        self.assertRegex(out, ' time to empty:\\s+20.0 min')
        self.assertRegex(out, ' state:\\s+discharging')

    def test_charging_battery(self):
        path = self.dbusmock.AddChargingBattery('mock_BAT', 'Mock Battery', 30.0, 1200)
        self.assertEqual(path, '/org/freedesktop/UPower/devices/mock_BAT')

        self.assertRegex(self.p_mock.stdout.read(),
                         b'emit /org/freedesktop/UPower org.freedesktop.UPower.DeviceAdded '
                         b'"/org/freedesktop/UPower/devices/mock_BAT"\n')

        out = subprocess.check_output(['upower', '--dump'],
                                      universal_newlines=True)
        self.assertRegex(out, 'Device: ' + path)
        # note, Add* is not magic: this just adds an object, not change
        # properties
        self.assertRegex(out, 'on-battery:\\s+yes')
        self.assertRegex(out, 'lid-is-present:\\s+yes')
        self.assertRegex(out, ' present:\\s+yes')
        self.assertRegex(out, ' percentage:\\s+30%')
        self.assertRegex(out, ' time to full:\\s+20.0 min')
        self.assertRegex(out, ' state:\\s+charging')

    def test_enumerate(self):
        self.dbusmock.AddAC('mock_AC', 'Mock AC')
        self.assertEqual(self.obj_upower.EnumerateDevices(),
                         ['/org/freedesktop/UPower/devices/mock_AC'])

    def test_display_device_default(self):
        path = self.obj_upower.GetDisplayDevice()
        self.assertEqual(path, '/org/freedesktop/UPower/devices/DisplayDevice')
        display_dev = self.dbus_con.get_object('org.freedesktop.UPower', path)
        props = display_dev.GetAll('org.freedesktop.UPower.Device')

        # http://cgit.freedesktop.org/upower/tree/src/org.freedesktop.UPower.xml
        # defines the properties which are defined
        self.assertEqual(
            set(props.keys()),
            {'Type', 'State', 'Percentage', 'Energy', 'EnergyFull',
             'EnergyRate', 'TimeToEmpty', 'TimeToFull', 'IsPresent',
             'IconName', 'WarningLevel'})

        # not set up by default, so should not present
        self.assertEqual(props['IsPresent'], False)
        self.assertEqual(props['IconName'], '')
        self.assertEqual(props['WarningLevel'], UP_DEVICE_LEVEL_NONE)

    def test_setup_display_device(self):
        self.dbusmock.SetupDisplayDevice(2, 1, 50.0, 40.0, 80.0, 2.5, 3600,
                                         1800, True, 'half-battery', 3)

        path = self.obj_upower.GetDisplayDevice()
        display_dev = self.dbus_con.get_object('org.freedesktop.UPower', path)
        props = display_dev.GetAll('org.freedesktop.UPower.Device')

        # just some spot-checks, check all the values from upower -d
        self.assertEqual(props['Type'], 2)
        self.assertEqual(props['Percentage'], 50.0)
        self.assertEqual(props['WarningLevel'], 3)

        env = os.environ.copy()
        env['LC_ALL'] = 'C'
        try:
            del env['LANGUAGE']
        except KeyError:
            pass

        out = subprocess.check_output(['upower', '--dump'],
                                      universal_newlines=True, env=env)
        self.assertIn('/DisplayDevice\n', out)
        self.assertIn('  battery\n', out)  # type
        self.assertRegex(out, r'state:\s+charging')
        self.assertRegex(out, r'percentage:\s+50%')
        self.assertRegex(out, r'energy:\s+40 Wh')
        self.assertRegex(out, r'energy-full:\s+80 Wh')
        self.assertRegex(out, r'energy-rate:\s+2.5 W')
        self.assertRegex(out, r'time to empty:\s+1\.0 hours')
        self.assertRegex(out, r'time to full:\s+30\.0 minutes')
        self.assertRegex(out, r'present:\s+yes')
        self.assertRegex(out, r"icon-name:\s+'half-battery'")
        self.assertRegex(out, r'warning-level:\s+low')


if __name__ == '__main__':
    # avoid writing to stderr
    unittest.main(testRunner=unittest.TextTestRunner(stream=sys.stdout))
