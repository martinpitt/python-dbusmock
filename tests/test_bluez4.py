#!/usr/bin/python3
# -*- coding: utf-8 -*-

# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 3 of the License, or (at your option) any
# later version.  See http://www.gnu.org/copyleft/lgpl.html for the full text
# of the license.

__authors__ = ['Mathieu Trudel-Lapierre <mathieu.trudel-lapierre@canonical.com>',
               'Philip Withnall <philip.withnall@collabora.co.uk>']
__copyright__ = '(c) 2013 Collabora Ltd.'
__copyright__ = '(c) 2014 Canonical Ltd.'
__license__ = 'LGPL 3+'

import unittest
import sys
import subprocess

import dbus
import dbus.mainloop.glib

import dbusmock

dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

p = subprocess.Popen(['which', 'bluez-test-adapter'], stdout=subprocess.PIPE)
p.communicate()
have_test_adapter = (p.returncode == 0)

p = subprocess.Popen(['which', 'bluez-test-device'], stdout=subprocess.PIPE)
p.communicate()
have_test_device = (p.returncode == 0)


def _run_test_command(prog, command):
    '''Run bluez-test command with the given command.

    Return its output as a list of lines.

    If bluez-test-adapter returns a non-zero exit code, raise an Exception.
    '''
    cmd = []
    cmd.append(prog)

    if type(command) is str:
        cmd.append(command)
    else:
        cmd.extend(command)

    process = subprocess.Popen(cmd, stdin=None,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE,
                               universal_newlines=True)

    out, err = process.communicate()

    lines = out.split('\n')
    lines = filter(lambda line: line != '', lines)
    lines = list(lines)

    errlines = err.split('\n')
    errlines = filter(lambda line: line != '', errlines)
    errlines = list(errlines)

    return (lines, errlines)


@unittest.skipUnless(have_test_adapter and have_test_device,
                     'bluez 4 not installed')
class TestBlueZ4(dbusmock.DBusTestCase):
    '''Test mocking bluetoothd'''

    @classmethod
    def setUpClass(klass):
        klass.start_system_bus()
        klass.dbus_con = klass.get_dbus(True)
        (klass.p_mock, klass.obj_bluez) = klass.spawn_server_template(
            'bluez4', {}, stdout=subprocess.PIPE)

    def setUp(self):
        self.obj_bluez.Reset()
        self.dbusmock = dbus.Interface(self.obj_bluez, dbusmock.MOCK_IFACE)
        self.dbusmock_bluez = dbus.Interface(self.obj_bluez, 'org.bluez.Mock')

    def test_no_adapters(self):
        # Check for adapters.
        out, err = _run_test_command('bluez-test-adapter', 'list')
        expected = "dbus.exceptions.DBusException: " \
            + "org.bluez.Error.NoSuchAdapter: No such adapter."
        self.assertIn(expected, err)

    def test_one_adapter(self):
        # Chosen parameters.
        adapter_name = 'hci0'
        system_name = 'my-computer'

        # Add an adapter
        path = self.dbusmock_bluez.AddAdapter(adapter_name, system_name)
        self.assertEqual(path, '/org/bluez/' + adapter_name)

        adapter = self.dbus_con.get_object('org.bluez', path)
        address = adapter.Get('org.bluez.Adapter', 'Address')
        self.assertEqual(str(address), '00:01:02:03:04:05')

        # Check for the adapter.
        out, err = _run_test_command('bluez-test-adapter', 'list')
        self.assertIn('    Name = ' + system_name, out)
        self.assertIn('    Alias = ' + system_name, out)
        self.assertIn('    Powered = 1', out)
        self.assertIn('    Pairable = 1', out)
        self.assertIn('    Discovering = 0', out)

    def test_no_devices(self):
        # Add an adapter.
        adapter_name = 'hci0'
        path = self.dbusmock_bluez.AddAdapter(adapter_name, 'my-computer')
        self.assertEqual(path, '/org/bluez/' + adapter_name)

        # Check for devices.
        out, err = _run_test_command('bluez-test-device', 'list')
        self.assertListEqual([], out)

    def test_one_device(self):
        # Add an adapter.
        adapter_name = 'hci0'
        path = self.dbusmock_bluez.AddAdapter(adapter_name, 'my-computer')
        self.assertEqual(path, '/org/bluez/' + adapter_name)

        # Add a device.
        address = '11:22:33:44:55:66'
        alias = 'My Phone'

        path = self.dbusmock_bluez.AddDevice(adapter_name, address, alias)
        self.assertEqual(path,
                         '/org/bluez/' + adapter_name + '/dev_' +
                         address.replace(':', '_'))

        # Check for the device.
        out, err = _run_test_command('bluez-test-device', 'list')
        self.assertIn(address + ' ' + alias, out)

        out, err = _run_test_command('bluez-test-device', ['name', address])
        self.assertIn(alias, out)

        device = self.dbus_con.get_object('org.bluez', path)
        dev_name = device.Get('org.bluez.Device', 'Name')
        self.assertEqual(str(dev_name), alias)
        dev_address = device.Get('org.bluez.Device', 'Address')
        self.assertEqual(str(dev_address), address)
        dev_class = device.Get('org.bluez.Device', 'Class')
        self.assertNotEqual(dev_class, 0)
        dev_conn = device.Get('org.bluez.Device', 'Connected')
        self.assertEqual(dev_conn, 0)

    def test_connect_disconnect(self):
        # Add an adapter.
        adapter_name = 'hci0'
        path = self.dbusmock_bluez.AddAdapter(adapter_name, 'my-computer')
        self.assertEqual(path, '/org/bluez/' + adapter_name)

        # Add a device.
        address = '11:22:33:44:55:66'
        alias = 'My Phone'

        path = self.dbusmock_bluez.AddDevice(adapter_name, address, alias)
        self.assertEqual(path,
                         '/org/bluez/' + adapter_name + '/dev_' + address.replace(':', '_'))

        # Force a service discovery so the audio interface appears.
        device = self.dbus_con.get_object('org.bluez', path)
        bluez_dev = dbus.Interface(device, 'org.bluez.Device')
        bluez_dev.DiscoverServices("")

        # Test the connection prior
        dev_state = device.Get('org.bluez.Audio', 'State')
        self.assertEqual(str(dev_state), "disconnected")
        dev_conn = device.Get('org.bluez.Device', 'Connected')
        self.assertEqual(dev_conn, 0)

        # Connect the audio interface.
        bluez_audio = dbus.Interface(device, 'org.bluez.Audio')
        bluez_audio.Connect()

        # Test the connection after connecting
        dev_state = device.Get('org.bluez.Audio', 'State')
        self.assertEqual(str(dev_state), "connected")
        dev_conn = device.Get('org.bluez.Device', 'Connected')
        self.assertEqual(dev_conn, 1)

        # Disconnect audio
        bluez_audio.Disconnect()

        # Test the connection after connecting
        dev_state = device.Get('org.bluez.Audio', 'State')
        self.assertEqual(str(dev_state), "disconnected")
        dev_conn = device.Get('org.bluez.Device', 'Connected')
        self.assertEqual(dev_conn, 0)


if __name__ == '__main__':
    # avoid writing to stderr
    unittest.main(testRunner=unittest.TextTestRunner(stream=sys.stdout,
                                                     verbosity=2))
