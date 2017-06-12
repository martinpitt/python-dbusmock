#!/usr/bin/python3

# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 3 of the License, or (at your option) any
# later version.  See http://www.gnu.org/copyleft/lgpl.html for the full text
# of the license.

__author__ = 'Iftikhar Ahmad'
__email__ = 'iftikhar.ahmad@canonical.com'
__copyright__ = '(c) 2012 Canonical Ltd.'
__license__ = 'LGPL 3+'

import unittest
import sys
import subprocess
import dbus
import dbus.mainloop.glib
import dbusmock
import os
import re

from gi.repository import GLib

from dbusmock.templates.networkmanager import DeviceState
from dbusmock.templates.networkmanager import NM80211ApSecurityFlags
from dbusmock.templates.networkmanager import InfrastructureMode
from dbusmock.templates.networkmanager import NMActiveConnectionState
from dbusmock.templates.networkmanager import NMState
from dbusmock.templates.networkmanager import NMConnectivityState
from dbusmock.templates.networkmanager import (CSETTINGS_IFACE, MANAGER_IFACE,
                                               SETTINGS_OBJ, SETTINGS_IFACE)

dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

p = subprocess.Popen(['which', 'nmcli'], stdout=subprocess.PIPE)
p.communicate()
have_nmcli = (p.returncode == 0)


@unittest.skipUnless(have_nmcli, 'nmcli not installed')
class TestNetworkManager(dbusmock.DBusTestCase):
    '''Test mocking NetworkManager'''

    @classmethod
    def setUpClass(klass):
        klass.start_system_bus()
        klass.dbus_con = klass.get_dbus(True)

        # prepare environment which avoids translations
        klass.lang_env = os.environ.copy()
        try:
            del klass.lang_env['LANG']
        except KeyError:
            pass
        try:
            del klass.lang_env['LANGUAGE']
        except KeyError:
            pass
        klass.lang_env['LC_MESSAGES'] = 'C'

    def setUp(self):
        (self.p_mock, self.obj_networkmanager) = self.spawn_server_template(
            'networkmanager',
            {'NetworkingEnabled': True, 'WwanEnabled': False},
            stdout=subprocess.PIPE)
        self.dbusmock = dbus.Interface(self.obj_networkmanager,
                                       dbusmock.MOCK_IFACE)
        self.settings = dbus.Interface(
            self.dbus_con.get_object(MANAGER_IFACE, SETTINGS_OBJ),
            SETTINGS_IFACE)

    def tearDown(self):
        self.p_mock.terminate()
        self.p_mock.wait()

    def read_general(self):
        return subprocess.check_output(['nmcli', '--nocheck', 'general'],
                                       env=self.lang_env,
                                       universal_newlines=True)

    def read_connection(self):
        return subprocess.check_output(['nmcli', '--nocheck', 'connection'],
                                       env=self.lang_env,
                                       universal_newlines=True)

    def read_active_connection(self):
        return subprocess.check_output(['nmcli', '--nocheck', 'connection',
                                        'show', '--active'],
                                       env=self.lang_env,
                                       universal_newlines=True)

    def read_device(self):
        return subprocess.check_output(['nmcli', '--nocheck', 'dev'],
                                       env=self.lang_env,
                                       universal_newlines=True)

    def read_device_wifi(self):
        return subprocess.check_output(['nmcli', '--nocheck', 'dev', 'wifi'],
                                       env=self.lang_env,
                                       universal_newlines=True)

    def test_one_eth_disconnected(self):
        self.dbusmock.AddEthernetDevice('mock_Ethernet1', 'eth0',
                                        DeviceState.DISCONNECTED)
        out = self.read_device()
        self.assertRegex(out, r'eth0.*\sdisconnected')

    def test_one_eth_connected(self):
        self.dbusmock.AddEthernetDevice('mock_Ethernet1', 'eth0',
                                        DeviceState.ACTIVATED)
        out = self.read_device()
        self.assertRegex(out, r'eth0.*\sconnected')

    def test_two_eth(self):
        # test with numeric state value
        self.dbusmock.AddEthernetDevice('mock_Ethernet1', 'eth0', 30)
        self.dbusmock.AddEthernetDevice('mock_Ethernet2', 'eth1',
                                        DeviceState.ACTIVATED)
        out = self.read_device()
        self.assertRegex(out, r'eth0.*\sdisconnected')
        self.assertRegex(out, r'eth1.*\sconnected')

    def test_wifi_without_access_points(self):
        self.dbusmock.AddWiFiDevice('mock_WiFi1', 'wlan0',
                                    DeviceState.ACTIVATED)
        out = self.read_device()
        self.assertRegex(out, r'wlan0.*\sconnected')

    def test_eth_and_wifi(self):
        self.dbusmock.AddEthernetDevice('mock_Ethernet1', 'eth0',
                                        DeviceState.DISCONNECTED)
        self.dbusmock.AddWiFiDevice('mock_WiFi1', 'wlan0',
                                    DeviceState.ACTIVATED)
        out = self.read_device()
        self.assertRegex(out, r'eth0.*\sdisconnected')
        self.assertRegex(out, r'wlan0.*\sconnected')

    def test_one_wifi_with_accesspoints(self):
        wifi = self.dbusmock.AddWiFiDevice('mock_WiFi2', 'wlan0',
                                           DeviceState.ACTIVATED)
        self.dbusmock.AddAccessPoint(wifi, 'Mock_AP1', 'AP_1',
                                     '00:23:F8:7E:12:BB',
                                     InfrastructureMode.NM_802_11_MODE_ADHOC,
                                     2425, 5400, 82,
                                     NM80211ApSecurityFlags.NM_802_11_AP_SEC_KEY_MGMT_PSK)
        self.dbusmock.AddAccessPoint(wifi, 'Mock_AP3', 'AP_3',
                                     '00:23:F8:7E:12:BC',
                                     InfrastructureMode.NM_802_11_MODE_INFRA,
                                     2425, 5400, 82, 0x400)
        out = self.read_device()
        aps = self.read_device_wifi()
        self.assertRegex(out, r'wlan0.*\sconnected')
        self.assertRegex(aps, r'AP_1.*\sAd-Hoc')
        self.assertRegex(aps, r'AP_3.*\sInfra')

    def test_two_wifi_with_accesspoints(self):
        wifi1 = self.dbusmock.AddWiFiDevice('mock_WiFi1', 'wlan0',
                                            DeviceState.ACTIVATED)
        wifi2 = self.dbusmock.AddWiFiDevice('mock_WiFi2', 'wlan1',
                                            DeviceState.UNAVAILABLE)
        self.dbusmock.AddAccessPoint(wifi1, 'Mock_AP0',
                                     'AP_0', '00:23:F8:7E:12:BA',
                                     InfrastructureMode.NM_802_11_MODE_UNKNOWN,
                                     2425, 5400, 82, 0x400)
        self.dbusmock.AddAccessPoint(wifi2, 'Mock_AP1', 'AP_1',
                                     '00:23:F8:7E:12:BB',
                                     InfrastructureMode.NM_802_11_MODE_ADHOC,
                                     2425, 5400, 82,
                                     NM80211ApSecurityFlags.NM_802_11_AP_SEC_KEY_MGMT_PSK)
        self.dbusmock.AddAccessPoint(wifi2, 'Mock_AP3', 'AP_2',
                                     '00:23:F8:7E:12:BC',
                                     InfrastructureMode.NM_802_11_MODE_INFRA,
                                     2425, 5400, 82, 0x400)
        out = self.read_device()
        aps = self.read_device_wifi()
        self.assertRegex(out, r'wlan0.*\sconnected')
        self.assertRegex(out, r'wlan1.*\sunavailable')
        self.assertRegex(aps, r'AP_0.*\s(Unknown|N/A)')
        self.assertRegex(aps, r'AP_1.*\sAd-Hoc')
        self.assertRegex(aps, r'AP_2.*\sInfra')

    def test_wifi_with_connection(self):
        wifi1 = self.dbusmock.AddWiFiDevice('mock_WiFi1', 'wlan0',
                                            DeviceState.ACTIVATED)
        ap1 = self.dbusmock.AddAccessPoint(
            wifi1, 'Mock_AP1', 'The_SSID', '00:23:F8:7E:12:BB',
            InfrastructureMode.NM_802_11_MODE_ADHOC, 2425, 5400, 82,
            NM80211ApSecurityFlags.NM_802_11_AP_SEC_KEY_MGMT_PSK)
        con1 = self.dbusmock.AddWiFiConnection(wifi1, 'Mock_Con1', 'The_SSID',
                                               'wpa-psk')

        self.assertRegex(self.read_connection(), r'The_SSID.*\s802-11-wireless')
        self.assertEqual(ap1, '/org/freedesktop/NetworkManager/AccessPoint/Mock_AP1')
        self.assertEqual(con1, '/org/freedesktop/NetworkManager/Settings/Mock_Con1')

    def test_global_state(self):
        self.dbusmock.SetGlobalConnectionState(NMState.NM_STATE_CONNECTED_GLOBAL)
        self.assertRegex(self.read_general(), r'connected.*\sfull')

        self.dbusmock.SetGlobalConnectionState(NMState.NM_STATE_CONNECTED_SITE)
        self.assertRegex(self.read_general(), r'connected \(site only\).*\sfull')

        self.dbusmock.SetGlobalConnectionState(NMState.NM_STATE_CONNECTED_LOCAL)
        self.assertRegex(self.read_general(), r'connected \(local only\).*\sfull')

        self.dbusmock.SetGlobalConnectionState(NMState.NM_STATE_CONNECTING)
        self.assertRegex(self.read_general(), r'connecting.*\sfull')

        self.dbusmock.SetGlobalConnectionState(NMState.NM_STATE_DISCONNECTING)
        self.assertRegex(self.read_general(), r'disconnecting.*\sfull')

        self.dbusmock.SetGlobalConnectionState(NMState.NM_STATE_DISCONNECTED)
        self.assertRegex(self.read_general(), r'disconnected.*\sfull')

        self.dbusmock.SetGlobalConnectionState(NMState.NM_STATE_ASLEEP)
        self.assertRegex(self.read_general(), r'asleep.*\sfull')

    def test_connectivity_state(self):
        self.dbusmock.SetConnectivity(NMConnectivityState.NM_CONNECTIVITY_FULL)
        self.assertRegex(self.read_general(), r'connected.*\sfull')

        self.dbusmock.SetConnectivity(NMConnectivityState.NM_CONNECTIVITY_LIMITED)
        self.assertRegex(self.read_general(), r'connected.*\slimited')

        self.dbusmock.SetConnectivity(NMConnectivityState.NM_CONNECTIVITY_PORTAL)
        self.assertRegex(self.read_general(), r'connected.*\sportal')

        self.dbusmock.SetConnectivity(NMConnectivityState.NM_CONNECTIVITY_NONE)
        self.assertRegex(self.read_general(), r'connected.*\snone')

    def test_wifi_with_active_connection(self):
        wifi1 = self.dbusmock.AddWiFiDevice('mock_WiFi1', 'wlan0',
                                            DeviceState.ACTIVATED)
        ap1 = self.dbusmock.AddAccessPoint(
            wifi1, 'Mock_AP1', 'The_SSID', '00:23:F8:7E:12:BB',
            InfrastructureMode.NM_802_11_MODE_INFRA, 2425, 5400, 82,
            NM80211ApSecurityFlags.NM_802_11_AP_SEC_KEY_MGMT_PSK)
        con1 = self.dbusmock.AddWiFiConnection(wifi1, 'Mock_Con1', 'The_SSID', '')
        active_con1 = self.dbusmock.AddActiveConnection(
            [wifi1], con1, ap1, 'Mock_Active1',
            NMActiveConnectionState.NM_ACTIVE_CONNECTION_STATE_ACTIVATED)

        self.assertEqual(ap1, '/org/freedesktop/NetworkManager/AccessPoint/Mock_AP1')
        self.assertEqual(con1, '/org/freedesktop/NetworkManager/Settings/Mock_Con1')
        self.assertEqual(active_con1, '/org/freedesktop/NetworkManager/ActiveConnection/Mock_Active1')

        self.assertRegex(self.read_general(), r'connected.*\sfull')
        self.assertRegex(self.read_connection(), r'The_SSID.*\s802-11-wireless')
        self.assertRegex(self.read_active_connection(), r'The_SSID.*\s802-11-wireless')
        self.assertRegex(self.read_device_wifi(), 'The_SSID')

        self.dbusmock.RemoveActiveConnection(wifi1, active_con1)

        self.assertRegex(self.read_connection(), r'The_SSID.*\s802-11-wireless')
        self.assertFalse(re.compile(r'The_SSID.*\s802-11-wireless').search(self.read_active_connection()))
        self.assertRegex(self.read_device_wifi(), 'The_SSID')

        self.dbusmock.RemoveWifiConnection(wifi1, con1)

        self.assertFalse(re.compile(r'The_SSID.*\s802-11-wireless').search(self.read_connection()))
        self.assertRegex(self.read_device_wifi(), 'The_SSID')

        self.dbusmock.RemoveAccessPoint(wifi1, ap1)
        self.assertFalse(re.compile('The_SSID').search(self.read_device_wifi()))

    def test_add_connection(self):
        self.dbusmock.AddWiFiDevice('mock_WiFi1', 'wlan0', DeviceState.ACTIVATED)
        uuid = '11111111-1111-1111-1111-111111111111'
        settings = dbus.Dictionary({
            'connection': dbus.Dictionary({
                'id': 'test connection',
                'uuid': uuid,
                'type': '802-11-wireless'}, signature='sv'),
            '802-11-wireless': dbus.Dictionary({
                'ssid': dbus.ByteArray('The_SSID'.encode('UTF-8'))}, signature='sv')
        }, signature='sa{sv}')
        con1 = self.settings.AddConnection(settings)

        self.assertEqual(con1, '/org/freedesktop/NetworkManager/Settings/0')
        self.assertRegex(self.read_connection(),
                         r'%s.*\s802-11-wireless' % uuid)

        # Use the same settings, but this one will autoconnect.
        uuid2 = '22222222-2222-2222-2222-222222222222'
        settings['connection']['autoconnect'] = dbus.Boolean(
            True, variant_level=1)
        settings['connection']['uuid'] = uuid2

        con2 = self.settings.AddConnection(settings)
        self.assertEqual(con2, '/org/freedesktop/NetworkManager/Settings/1')

        self.assertRegex(self.read_general(), r'connected.*\sfull')
        self.assertRegex(self.read_connection(),
                         r'%s.*\s802-11-wireless' % uuid2)
        self.assertRegex(self.read_active_connection(),
                         r'%s.*\s802-11-wireless' % uuid2)

    def test_update_connection(self):
        uuid = '133d8eb9-6de6-444f-8b37-f40bf9e33226'
        settings = dbus.Dictionary({
            'connection': dbus.Dictionary({
                'id': 'test wireless',
                'uuid': uuid,
                'type': '802-11-wireless'}, signature='sv'),
            '802-11-wireless': dbus.Dictionary({
                'ssid': dbus.ByteArray('The_SSID'.encode('UTF-8'))}, signature='sv')
        }, signature='sa{sv}')

        con1 = self.settings.AddConnection(settings)
        con1_iface = dbus.Interface(
            self.dbus_con.get_object(MANAGER_IFACE, con1),
            CSETTINGS_IFACE)

        self.assertEqual(con1, '/org/freedesktop/NetworkManager/Settings/0')
        self.assertRegex(self.read_connection(), r'%s.*\s802-11-wireless' % uuid)

        new_settings = dbus.Dictionary({
            'connection': dbus.Dictionary({
                'id': 'test wired',
                'type': '802-3-ethernet'}, signature='sv'),
            '802-3-ethernet': dbus.Dictionary({
                'name': '802-3-ethernet'
            }, signature='sv')}, signature='sa{sv}')

        con1_iface.Update(new_settings)
        self.assertRegex(self.read_connection(), r'%s.*\s802-3-ethernet' % uuid)

    def test_remove_connection(self):
        wifi1 = self.dbusmock.AddWiFiDevice('mock_WiFi1', 'wlan0',
                                            DeviceState.ACTIVATED)
        ap1 = self.dbusmock.AddAccessPoint(
            wifi1, 'Mock_AP1', 'The_SSID', '00:23:F8:7E:12:BB',
            InfrastructureMode.NM_802_11_MODE_INFRA, 2425, 5400, 82,
            NM80211ApSecurityFlags.NM_802_11_AP_SEC_KEY_MGMT_PSK)
        con1 = self.dbusmock.AddWiFiConnection(wifi1, 'Mock_Con1', 'The_SSID', '')
        self.dbusmock.AddActiveConnection(
            [wifi1], con1, ap1, 'Mock_Active1',
            NMActiveConnectionState.NM_ACTIVE_CONNECTION_STATE_ACTIVATED)

        con1_i = dbus.Interface(
            self.dbus_con.get_object(MANAGER_IFACE, con1), CSETTINGS_IFACE)
        con1_i.Delete()

        self.assertRegex(self.read_general(), r'disconnected.*\sfull')
        self.assertFalse(re.compile(r'The_SSID.*\s802-11-wireless').search(self.read_active_connection()))
        self.assertRegex(self.read_device(), r'wlan0.*\sdisconnected')

    def test_add_remove_settings(self):
        connection = {
            'connection': {
                'timestamp': 1441979296,
                'type': 'vpn',
                'id': 'a',
                'uuid': '11111111-1111-1111-1111-111111111111'
            },
            'vpn': {
                'service-type': 'org.freedesktop.NetworkManager.openvpn',
                'data': {
                    'connection-type': 'tls'
                }
            },
            'ipv4': {
                'routes': dbus.Array([], signature='o'),
                'never-default': True,
                'addresses': dbus.Array([], signature='o'),
                'dns': dbus.Array([], signature='o'),
                'method': 'auto'
            },
            'ipv6': {
                'addresses': dbus.Array([], signature='o'),
                'ip6-privacy': 0,
                'dns': dbus.Array([], signature='o'),
                'never-default': True,
                'routes': dbus.Array([], signature='o'),
                'method': 'auto'
            }
        }

        connectionA = self.settings.AddConnection(connection)
        connection['connection']['id'] = 'b'
        connection['connection']['uuid'] = '11111111-1111-1111-1111-111111111112'
        connectionB = self.settings.AddConnection(connection)
        self.assertEqual(self.settings.ListConnections(), [connectionA, connectionB])

        connectionA_i = dbus.Interface(
            self.dbus_con.get_object(MANAGER_IFACE, connectionA), CSETTINGS_IFACE)
        connectionA_i.Delete()
        self.assertEqual(self.settings.ListConnections(), [connectionB])

        connection['connection']['id'] = 'c'
        connection['connection']['uuid'] = '11111111-1111-1111-1111-111111111113'
        connectionC = self.settings.AddConnection(connection)
        self.assertEqual(self.settings.ListConnections(), [connectionB, connectionC])

    def test_add_update_settings(self):
        connection = {
            'connection': {
                'timestamp': 1441979296,
                'type': 'vpn',
                'id': 'a',
                'uuid': '11111111-1111-1111-1111-111111111111'
            },
            'vpn': {
                'service-type': 'org.freedesktop.NetworkManager.openvpn',
                'data': dbus.Dictionary({
                    'connection-type': 'tls'
                }, signature='ss')
            },
            'ipv4': {
                'routes': dbus.Array([], signature='o'),
                'never-default': True,
                'addresses': dbus.Array([], signature='o'),
                'dns': dbus.Array([], signature='o'),
                'method': 'auto'
            },
            'ipv6': {
                'addresses': dbus.Array([], signature='o'),
                'ip6-privacy': 0,
                'dns': dbus.Array([], signature='o'),
                'never-default': True,
                'routes': dbus.Array([], signature='o'),
                'method': 'auto'
            }
        }

        connectionA = self.settings.AddConnection(connection)
        self.assertEqual(self.settings.ListConnections(), [connectionA])

        connectionA_i = dbus.Interface(
            self.dbus_con.get_object(MANAGER_IFACE, connectionA), CSETTINGS_IFACE)
        connection['connection']['id'] = 'b'

        def do_update():
            connectionA_i.Update(connection)

        caught = []
        ml = GLib.MainLoop()

        def catch(*args, **kwargs):
            if (kwargs['interface'] == 'org.freedesktop.NetworkManager.Settings.Connection' and
                    kwargs['member'] == 'Updated'):
                caught.append(kwargs['path'])
                ml.quit()

        self.dbus_con.add_signal_receiver(catch,
                                          interface_keyword='interface',
                                          path_keyword='path',
                                          member_keyword='member')

        GLib.timeout_add(200, do_update)
        # ensure that the loop quits even when we don't catch anything
        GLib.timeout_add(3000, ml.quit)
        ml.run()

        self.assertEqual(connectionA_i.GetSettings(), connection)
        self.assertEqual(caught, [connectionA])

    def test_settings_secrets(self):
        secrets = dbus.Dictionary({
            'cert-pass': 'certificate password',
            'password': 'the password',
        }, signature='ss')

        connection = {
            'connection': {
                'timestamp': 1441979296,
                'type': 'vpn',
                'id': 'a',
                'uuid': '11111111-1111-1111-1111-111111111111'
            },
            'vpn': {
                'service-type': 'org.freedesktop.NetworkManager.openvpn',
                'data': dbus.Dictionary({
                    'connection-type': 'password-tls',
                    'remote': 'remotey',
                    'ca': '/my/ca.crt',
                    'cert': '/my/cert.crt',
                    'cert-pass-flags': '1',
                    'key': '/my/key.key',
                    'password-flags': "1",
                }, signature='ss'),
                'secrets': secrets
            },
            'ipv4': {
                'routes': dbus.Array([], signature='o'),
                'never-default': True,
                'addresses': dbus.Array([], signature='o'),
                'dns': dbus.Array([], signature='o'),
                'method': 'auto'
            },
            'ipv6': {
                'addresses': dbus.Array([], signature='o'),
                'ip6-privacy': 0,
                'dns': dbus.Array([], signature='o'),
                'never-default': True,
                'routes': dbus.Array([], signature='o'),
                'method': 'auto'
            }
        }

        connectionPath = self.settings.AddConnection(connection)
        self.assertEqual(self.settings.ListConnections(), [connectionPath])

        connection_i = dbus.Interface(
            self.dbus_con.get_object(MANAGER_IFACE, connectionPath), CSETTINGS_IFACE)

        # We expect there to be no secrets in the normal settings dict
        del connection['vpn']['secrets']
        self.assertEqual(connection_i.GetSettings(), connection)

        # Secrets request should contain just vpn section with the secrets in
        self.assertEqual(connection_i.GetSecrets('vpn'), {'vpn': {'secrets': secrets}})

if __name__ == '__main__':
    unittest.main(testRunner=unittest.TextTestRunner(stream=sys.stdout, verbosity=2))
