#!/usr/bin/python3
# -*- coding: utf-8 -*-

# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 3 of the License, or (at your option) any
# later version.  See http://www.gnu.org/copyleft/lgpl.html for the full text
# of the license.

__author__ = 'Philip Withnall'
__email__ = 'philip.withnall@collabora.co.uk'
__copyright__ = '(c) 2013 Collabora Ltd.'
__license__ = 'LGPL 3+'

import unittest
import sys
import subprocess
import time
import os

import dbus
import dbus.mainloop.glib

import dbusmock

from gi.repository import GLib

dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

p = subprocess.Popen(['which', 'bluetoothctl'], stdout=subprocess.PIPE)
p.communicate()
have_bluetoothctl = (p.returncode == 0)

p = subprocess.Popen(['which', 'pbap-client'], stdout=subprocess.PIPE)
p.communicate()
have_pbap_client = (p.returncode == 0)


def _run_bluetoothctl(command):
    '''Run bluetoothctl with the given command.

    Return its output as a list of lines, with the command prompt removed
    from each, and empty lines eliminated.

    If bluetoothctl returns a non-zero exit code, raise an Exception.
    '''
    process = subprocess.Popen(['bluetoothctl'], stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE,
                               universal_newlines=True)

    time.sleep(0.5)  # give it time to query the bus
    out, err = process.communicate(input='list\n' + command + '\nquit\n')

    # Ignore output on stderr unless bluetoothctl dies.
    if process.returncode != 0:
        raise Exception('bluetoothctl died with status ' +
                        str(process.returncode) + ' and errors: ' +
                        (err or ""))

    # Strip the prompt from the start of every line, then remove empty
    # lines.
    #
    # The prompt looks like ‘[bluetooth]# ’, potentially containing command
    # line colour control codes. Split at the first space.
    #
    # Sometimes we end up with the final line being ‘\x1b[K’ (partial
    # control code), which we need to ignore.
    def remove_prefix(line):
        if line.startswith('[bluetooth]#') or line.startswith('\x1b'):
            parts = line.split(' ', 1)
            try:
                return parts[1].strip()
            except IndexError:
                return ''
        return line.strip()

    lines = out.split('\n')
    lines = map(remove_prefix, lines)
    lines = filter(lambda l: l != '', lines)

    # Filter out the echoed commands. (bluetoothctl uses readline.)
    lines = filter(lambda l: l not in ['list', command, 'quit'], lines)
    lines = list(lines)

    return lines


@unittest.skipUnless(have_bluetoothctl, 'bluetoothctl not installed')
class TestBlueZ5(dbusmock.DBusTestCase):
    '''Test mocking bluetoothd'''

    @classmethod
    def setUpClass(klass):
        klass.start_system_bus()
        klass.dbus_con = klass.get_dbus(True)
        (klass.p_mock, klass.obj_bluez) = klass.spawn_server_template(
            'bluez5', {}, stdout=subprocess.PIPE)

    def setUp(self):
        self.obj_bluez.Reset()
        self.dbusmock = dbus.Interface(self.obj_bluez, dbusmock.MOCK_IFACE)
        self.dbusmock_bluez = dbus.Interface(self.obj_bluez, 'org.bluez.Mock')

    def test_no_adapters(self):
        # Check for adapters.
        out = _run_bluetoothctl('list')
        for line in out:
            self.assertNotRegex(line, '^Controller ')

    def test_one_adapter(self):
        # Chosen parameters.
        adapter_name = 'hci0'
        system_name = 'my-computer'

        # Add an adapter
        path = self.dbusmock_bluez.AddAdapter(adapter_name, system_name)
        self.assertEqual(path, '/org/bluez/' + adapter_name)

        adapter = self.dbus_con.get_object('org.bluez', path)
        address = adapter.Get('org.bluez.Adapter1', 'Address')

        # Check for the adapter.
        out = _run_bluetoothctl('list')
        self.assertIn('Controller ' + address + ' ' + system_name +
                      ' [default]', out)

        out = _run_bluetoothctl('show ' + address)
        self.assertIn('Controller ' + address, out)
        self.assertIn('Name: ' + system_name, out)
        self.assertIn('Alias: ' + system_name, out)
        self.assertIn('Powered: yes', out)
        self.assertIn('Discoverable: yes', out)
        self.assertIn('Pairable: yes', out)
        self.assertIn('Discovering: yes', out)

    def test_no_devices(self):
        # Add an adapter.
        adapter_name = 'hci0'
        path = self.dbusmock_bluez.AddAdapter(adapter_name, 'my-computer')
        self.assertEqual(path, '/org/bluez/' + adapter_name)

        # Check for devices.
        out = _run_bluetoothctl('devices')
        self.assertIn('Controller 00:01:02:03:04:05 my-computer [default]',
                      out)

    @unittest.skip('flaky test')
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
        out = _run_bluetoothctl('devices')
        self.assertIn('Device ' + address + ' ' + alias, out)

        # Check the device’s properties.
        out = '\n'.join(_run_bluetoothctl('info ' + address))
        self.assertIn('Device ' + address, out)
        self.assertIn('Name: ' + alias, out)
        self.assertIn('Alias: ' + alias, out)
        self.assertIn('Paired: no', out)
        self.assertIn('Trusted: no', out)
        self.assertIn('Blocked: no', out)
        self.assertIn('Connected: no', out)

    @unittest.skip('flaky test')
    def test_pairing_device(self):
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

        # Pair with the device.
        self.dbusmock_bluez.PairDevice(adapter_name, address)

        # Check the device’s properties.
        out = '\n'.join(_run_bluetoothctl('info ' + address))
        self.assertIn('Device ' + address, out)
        self.assertIn('Paired: yes', out)


@unittest.skipUnless(have_pbap_client,
                     'pbap-client not installed (copy it from bluez/test)')
class TestBlueZObex(dbusmock.DBusTestCase):
    '''Test mocking obexd'''

    @classmethod
    def setUpClass(klass):
        klass.start_session_bus()
        klass.start_system_bus()
        klass.dbus_con = klass.get_dbus(True)

    def setUp(self):
        # bluetoothd
        (self.p_mock, self.obj_bluez) = self.spawn_server_template(
            'bluez5', {}, stdout=subprocess.PIPE)
        self.dbusmock_bluez = dbus.Interface(self.obj_bluez, 'org.bluez.Mock')

        # obexd
        (self.p_mock, self.obj_obex) = self.spawn_server_template(
            'bluez5-obex', {}, stdout=subprocess.PIPE)
        self.dbusmock = dbus.Interface(self.obj_obex, dbusmock.MOCK_IFACE)
        self.dbusmock_obex = dbus.Interface(self.obj_obex,
                                            'org.bluez.obex.Mock')

    def tearDown(self):
        self.p_mock.terminate()
        self.p_mock.wait()

    def test_everything(self):
        # Set up an adapter and device.
        adapter_name = 'hci0'
        device_address = '11:22:33:44:55:66'
        device_alias = 'My Phone'

        ml = GLib.MainLoop()

        self.dbusmock_bluez.AddAdapter(adapter_name, 'my-computer')
        self.dbusmock_bluez.AddDevice(adapter_name, device_address,
                                      device_alias)
        self.dbusmock_bluez.PairDevice(adapter_name, device_address)

        transferred_files = []

        def _transfer_created_cb(path, params, transfer_filename):
            bus = self.get_dbus(False)
            obj = bus.get_object('org.bluez.obex', path)
            transfer = dbus.Interface(obj, 'org.bluez.obex.transfer1.Mock')

            with open(transfer_filename, 'w') as f:
                f.write(
                    'BEGIN:VCARD\r\n' +
                    'VERSION:3.0\r\n' +
                    'FN:Forrest Gump\r\n' +
                    'TEL;TYPE=WORK,VOICE:(111) 555-1212\r\n' +
                    'TEL;TYPE=HOME,VOICE:(404) 555-1212\r\n' +
                    'EMAIL;TYPE=PREF,INTERNET:forrestgump@example.com\r\n' +
                    'EMAIL:test@example.com\r\n' +
                    'URL;TYPE=HOME:http://example.com/\r\n' +
                    'URL:http://forest.com/\r\n' +
                    'URL:https://test.com/\r\n' +
                    'END:VCARD\r\n'
                )

            transfer.UpdateStatus(True)
            transferred_files.append(transfer_filename)

        self.dbusmock_obex.connect_to_signal('TransferCreated',
                                             _transfer_created_cb)

        # Run pbap-client, then run the GLib main loop. The main loop will quit
        # after a timeout, at which point the code handles output from
        # pbap-client and waits for it to terminate. Integrating
        # process.communicate() with the GLib main loop to avoid the timeout is
        # too difficult.
        process = subprocess.Popen(['pbap-client', device_address],
                                   stdout=subprocess.PIPE,
                                   stderr=sys.stderr,
                                   universal_newlines=True)

        GLib.timeout_add(5000, ml.quit)
        ml.run()

        out, err = process.communicate()

        lines = out.split('\n')
        lines = filter(lambda l: l != '', lines)
        lines = list(lines)

        # Clean up the transferred files.
        for f in transferred_files:
            try:
                os.remove(f)
            except:
                pass

        # See what pbap-client sees.
        self.assertIn('Creating Session', lines)
        self.assertIn('--- Select Phonebook PB ---', lines)
        self.assertIn('--- GetSize ---', lines)
        self.assertIn('Size = 0', lines)
        self.assertIn('--- List vCard ---', lines)
        self.assertIn(
            'Transfer /org/bluez/obex/client/session0/transfer0 complete',
            lines)
        self.assertIn(
            'Transfer /org/bluez/obex/client/session0/transfer1 complete',
            lines)
        self.assertIn(
            'Transfer /org/bluez/obex/client/session0/transfer2 complete',
            lines)
        self.assertIn(
            'Transfer /org/bluez/obex/client/session0/transfer3 complete',
            lines)
        self.assertIn('FINISHED', lines)

        self.assertNotIn('ERROR', lines)


if __name__ == '__main__':
    # avoid writing to stderr
    unittest.main(testRunner=unittest.TextTestRunner(stream=sys.stdout,
                                                     verbosity=2))
