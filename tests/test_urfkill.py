#!/usr/bin/python3

# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 3 of the License, or (at your option) any
# later version.  See http://www.gnu.org/copyleft/lgpl.html for the full text
# of the license.

__author__ = 'Jussi Pakkanen'
__email__ = 'jussi.pakkanen@canonical.com'
__copyright__ = '(c) 2015 Canonical Ltd.'
__license__ = 'LGPL 3+'

import unittest
import sys
import subprocess
import os
import fcntl

import dbus

import dbusmock


class TestURfkill(dbusmock.DBusTestCase):
    '''Test mocked URfkill'''

    @classmethod
    def setUpClass(klass):
        klass.start_system_bus()
        klass.dbus_con = klass.get_dbus(True)

    def setUp(self):
        (self.p_mock, self.obj_urfkill) = self.spawn_server_template(
            'urfkill', {},
            stdout=subprocess.PIPE)
        # set log to nonblocking
        flags = fcntl.fcntl(self.p_mock.stdout, fcntl.F_GETFL)
        fcntl.fcntl(self.p_mock.stdout, fcntl.F_SETFL, flags | os.O_NONBLOCK)
        self.dbusmock = dbus.Interface(self.obj_urfkill, dbusmock.MOCK_IFACE)

    def tearDown(self):
        self.p_mock.terminate()
        self.p_mock.wait()

    def get_urfkill_objects(self):
        bus = dbus.SystemBus()
        remote_object = bus.get_object('org.freedesktop.URfkill', '/org/freedesktop/URfkill')
        iface = dbus.Interface(remote_object, 'org.freedesktop.URfkill')
        return (remote_object, iface)

    def test_mainobject(self):
        (remote_object, iface) = self.get_urfkill_objects()
        self.assertFalse(iface.IsFlightMode())
        propiface = dbus.Interface(remote_object, 'org.freedesktop.DBus.Properties')
        version = propiface.Get('org.freedesktop.URfkill', 'DaemonVersion')
        self.assertEqual(version, '0.6.0')

    def test_subobjects(self):
        bus = dbus.SystemBus()
        individual_objects = ['BLUETOOTH', 'FM', 'GPS', 'NFC', 'UWB', 'WIMAX', 'WLAN', 'WWAN']
        for i in individual_objects:
            path = '/org/freedesktop/URfkill/' + i
            remote_object = bus.get_object('org.freedesktop.URfkill', path)
            propiface = dbus.Interface(remote_object, 'org.freedesktop.DBus.Properties')
            state = propiface.Get('org.freedesktop.URfkill.Killswitch', 'state')
            self.assertEqual(state, 0)

    def test_block(self):
        bus = dbus.SystemBus()
        (remote_object, iface) = self.get_urfkill_objects()

        property_object = bus.get_object('org.freedesktop.URfkill', '/org/freedesktop/URfkill/WLAN')
        propiface = dbus.Interface(property_object, 'org.freedesktop.DBus.Properties')
        self.assertEqual(propiface.Get('org.freedesktop.URfkill.Killswitch', 'state'), 0)

        self.assertTrue(iface.Block(1, True))
        self.assertEqual(propiface.Get('org.freedesktop.URfkill.Killswitch', 'state'), 1)

        self.assertTrue(iface.Block(1, False))
        self.assertEqual(propiface.Get('org.freedesktop.URfkill.Killswitch', 'state'), 0)

        # 99 is an unknown type to the mock, so it should return false.
        self.assertFalse(iface.Block(99, False))

    def test_flightmode(self):
        bus = dbus.SystemBus()
        (remote_object, iface) = self.get_urfkill_objects()

        property_object = bus.get_object('org.freedesktop.URfkill', '/org/freedesktop/URfkill/WLAN')
        propiface = dbus.Interface(property_object, 'org.freedesktop.DBus.Properties')

        self.assertFalse(iface.IsFlightMode())
        self.assertEqual(propiface.Get('org.freedesktop.URfkill.Killswitch', 'state'), 0)
        iface.FlightMode(True)
        self.assertTrue(iface.IsFlightMode())
        self.assertEqual(propiface.Get('org.freedesktop.URfkill.Killswitch', 'state'), 1)
        iface.FlightMode(False)
        self.assertFalse(iface.IsFlightMode())
        self.assertEqual(propiface.Get('org.freedesktop.URfkill.Killswitch', 'state'), 0)

    def test_flightmode_restore(self):
        # An interface that was blocked remains blocked once flightmode is removed.
        bus = dbus.SystemBus()
        (remote_object, iface) = self.get_urfkill_objects()

        property_object = bus.get_object('org.freedesktop.URfkill', '/org/freedesktop/URfkill/WLAN')
        propiface = dbus.Interface(property_object, 'org.freedesktop.DBus.Properties')

        self.assertFalse(iface.IsFlightMode())
        self.assertEqual(propiface.Get('org.freedesktop.URfkill.Killswitch', 'state'), 0)
        iface.Block(1, True)
        self.assertEqual(propiface.Get('org.freedesktop.URfkill.Killswitch', 'state'), 1)
        iface.FlightMode(True)
        self.assertTrue(iface.IsFlightMode())
        self.assertEqual(propiface.Get('org.freedesktop.URfkill.Killswitch', 'state'), 1)
        iface.FlightMode(False)
        self.assertFalse(iface.IsFlightMode())
        self.assertEqual(propiface.Get('org.freedesktop.URfkill.Killswitch', 'state'), 1)


if __name__ == '__main__':
    # avoid writing to stderr
    unittest.main(testRunner=unittest.TextTestRunner(stream=sys.stdout, verbosity=2))
