#!/usr/bin/python3

# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 3 of the License, or (at your option) any
# later version.  See http://www.gnu.org/copyleft/lgpl.html for the full text
# of the license.

__author__ = 'Martin Pitt'
__email__ = 'martin.pitt@ubuntu.com'
__copyright__ = '(c) 2012 Canonical Ltd.'
__license__ = 'LGPL 3+'

import unittest
import sys
import subprocess
import time
import os
import fcntl

import dbus

import dbusmock

UP_DEVICE_LEVEL_UNKNOWN = 0
UP_DEVICE_LEVEL_NONE = 1

p = subprocess.Popen(['which', 'upower'], stdout=subprocess.PIPE)
p.communicate()
have_upower = (p.returncode == 0)

if have_upower:
    p = subprocess.Popen(['upower', '--version'], stdout=subprocess.PIPE,
                         universal_newlines=True)
    out = p.communicate()[0]
    try:
        upower_client_version = out.splitlines()[0].split()[-1]
        assert p.returncode == 0
    except IndexError:
        # FIXME: this happens in environments without a system D-BUS; upower
        # 0.9 still prints the client version, 0.99 just crashes
        upower_client_version = '0.99'
else:
    upower_client_version = '0'


@unittest.skipUnless(have_upower, 'upower not installed')
class TestUPower(dbusmock.DBusTestCase):
    '''Test mocking upowerd'''

    @classmethod
    def setUpClass(klass):
        klass.start_system_bus()
        klass.dbus_con = klass.get_dbus(True)

    def setUp(self):
        (self.p_mock, self.obj_upower) = self.spawn_server_template(
            'upower', {
                'OnBattery': True,
                'HibernateAllowed': False,
                'DaemonVersion': upower_client_version
            },
            stdout=subprocess.PIPE)
        # set log to nonblocking
        flags = fcntl.fcntl(self.p_mock.stdout, fcntl.F_GETFL)
        fcntl.fcntl(self.p_mock.stdout, fcntl.F_SETFL, flags | os.O_NONBLOCK)
        self.dbusmock = dbus.Interface(self.obj_upower, dbusmock.MOCK_IFACE)

    def tearDown(self):
        self.p_mock.terminate()
        self.p_mock.wait()

    def test_no_devices(self):
        out = subprocess.check_output(['upower', '--dump'],
                                      universal_newlines=True)
        # upower 1.0 has a "DisplayDevice" which is always there, ignore that
        # one
        for line in out.splitlines():
            if line.endswith('/DisplayDevice'):
                continue
            self.assertFalse('Device' in line, out)
        self.assertRegex(out, 'on-battery:\\s+yes')
        self.assertRegex(out, 'lid-is-present:\\s+yes')

    def test_one_ac(self):
        path = self.dbusmock.AddAC('mock_AC', 'Mock AC')
        self.assertEqual(path, '/org/freedesktop/UPower/devices/mock_AC')

        self.assertRegex(self.p_mock.stdout.read(),
                         b'emit org.freedesktop.UPower.DeviceAdded '
                         b'"/org/freedesktop/UPower/devices/mock_AC"\n')

        out = subprocess.check_output(['upower', '--dump'],
                                      universal_newlines=True)
        self.assertRegex(out, 'Device: ' + path)
        # note, Add* is not magic: this just adds an object, not change
        # properties
        self.assertRegex(out, 'on-battery:\\s+yes')
        self.assertRegex(out, 'lid-is-present:\\s+yes')
        # print('--------- out --------\n%s\n------------' % out)

        mon = subprocess.Popen(['upower', '--monitor-detail'],
                               stdout=subprocess.PIPE,
                               universal_newlines=True)

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
                         b'emit org.freedesktop.UPower.DeviceAdded '
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
                         b'emit org.freedesktop.UPower.DeviceAdded '
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


@unittest.skipUnless(have_upower, 'upower not installed')
@unittest.skipUnless(upower_client_version < '0.99', 'pre-0.99 client API specific test')
class TestUPower0(dbusmock.DBusTestCase):
    '''Test mocking upowerd with 0.x API'''

    @classmethod
    def setUpClass(klass):
        klass.start_system_bus()
        klass.dbus_con = klass.get_dbus(True)

    def setUp(self):
        (self.p_mock, self.obj_upower) = self.spawn_server_template(
            'upower', {
                'OnBattery': True,
                'HibernateAllowed': False,
                'DaemonVersion': '0.9'
            },
            stdout=subprocess.PIPE)
        # set log to nonblocking
        flags = fcntl.fcntl(self.p_mock.stdout, fcntl.F_GETFL)
        fcntl.fcntl(self.p_mock.stdout, fcntl.F_SETFL, flags | os.O_NONBLOCK)
        self.dbusmock = dbus.Interface(self.obj_upower, dbusmock.MOCK_IFACE)

    def tearDown(self):
        self.p_mock.terminate()
        self.p_mock.wait()

    def test_suspend(self):
        '''0.9 API specific Suspend signal'''

        self.obj_upower.Suspend(dbus_interface='org.freedesktop.UPower')
        self.assertRegex(self.p_mock.stdout.readline(), b'^[0-9.]+ Suspend$')

    def test_09_properties(self):
        '''0.9 API specific properties'''

        out = subprocess.check_output(['upower', '--dump'],
                                      universal_newlines=True)
        self.assertRegex(out, 'daemon-version:\\s+0.9')
        self.assertRegex(out, 'can-suspend:\\s+yes')
        self.assertRegex(out, 'can-hibernate:?\\s+no')
        self.assertNotIn('critical-action:', out)

    def test_no_display_device(self):
        '''0.9 API has no display device'''

        self.assertRaises(dbus.exceptions.DBusException,
                          self.obj_upower.GetDisplayDevice)

        self.assertRaises(dbus.exceptions.DBusException,
                          self.dbusmock.SetupDisplayDevice,
                          2, 1, 50.0, 40.0, 80.0, 2.5, 3600, 1800, True,
                          'half-battery', 3)

        display_dev = self.dbus_con.get_object(
            'org.freedesktop.UPower',
            '/org/freedesktop/UPower/devices/DisplayDevice')
        self.assertRaises(dbus.exceptions.DBusException,
                          display_dev.GetAll, '')


@unittest.skipUnless(have_upower, 'upower not installed')
@unittest.skipUnless(upower_client_version >= '0.99', '1.0 client API specific test')
class TestUPower1(dbusmock.DBusTestCase):
    '''Test mocking upowerd with 1.0 API'''

    @classmethod
    def setUpClass(klass):
        klass.start_system_bus()
        klass.dbus_con = klass.get_dbus(True)

    def setUp(self):
        (self.p_mock, self.obj_upower) = self.spawn_server_template(
            'upower',
            {'OnBattery': True, 'DaemonVersion': '1.0', 'GetCriticalAction': 'Suspend'},
            stdout=subprocess.PIPE)
        self.dbusmock = dbus.Interface(self.obj_upower, dbusmock.MOCK_IFACE)

    def tearDown(self):
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
            self.assertFalse('Device' in line, out)
        self.assertRegex(out, 'on-battery:\\s+yes')
        self.assertRegex(out, 'lid-is-present:\\s+yes')

    def test_properties(self):
        '''1.0 API specific properties'''

        out = subprocess.check_output(['upower', '--dump'],
                                      universal_newlines=True)
        self.assertRegex(out, 'daemon-version:\\s+1.0')
        self.assertRegex(out, 'critical-action:\\s+Suspend')
        self.assertNotIn('can-suspend', out)

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
            set(['Type', 'State', 'Percentage', 'Energy', 'EnergyFull',
                 'EnergyRate', 'TimeToEmpty', 'TimeToFull', 'IsPresent',
                 'IconName', 'WarningLevel']))

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
        self.assertRegex(out, 'state:\\s+charging')
        self.assertRegex(out, 'percentage:\\s+50%')
        self.assertRegex(out, 'energy:\\s+40 Wh')
        self.assertRegex(out, 'energy-full:\\s+80 Wh')
        self.assertRegex(out, 'energy-rate:\\s+2.5 W')
        self.assertRegex(out, 'time to empty:\\s+1\.0 hours')
        self.assertRegex(out, 'time to full:\\s+30\.0 minutes')
        self.assertRegex(out, 'present:\\s+yes')
        self.assertRegex(out, "icon-name:\\s+'half-battery'")
        self.assertRegex(out, 'warning-level:\\s+low')


if __name__ == '__main__':
    # avoid writing to stderr
    unittest.main(testRunner=unittest.TextTestRunner(stream=sys.stdout, verbosity=2))
