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
import dbusmock
import os

from dbusmock.templates.networkmanager import DeviceState


p = subprocess.Popen(['which', 'nmcli'], stdout=subprocess.PIPE)
p.communicate()
have_nmcli = (p.returncode == 0)


@unittest.skipUnless(have_nmcli, 'nmcli not installed')
class TestNeworkManager(dbusmock.DBusTestCase):
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

    def tearDown(self):
        self.p_mock.terminate()
        self.p_mock.wait()

    def test_one_eth_disconnected(self):
        self.dbusmock.AddEthernetDevice('mock_Ethernet1', 'eth0',
                                        DeviceState.DISCONNECTED)
        out = subprocess.check_output(['nmcli', '--nocheck', 'dev'],
                                      env=self.lang_env,
                                      universal_newlines=True)
        self.assertRegex(out, 'eth0.*\sdisconnected')

    def test_one_eth_connected(self):
        self.dbusmock.AddEthernetDevice('mock_Ethernet1', 'eth0',
                                        DeviceState.ACTIVATED)
        out = subprocess.check_output(['nmcli', '--nocheck', 'dev'],
                                      env=self.lang_env,
                                      universal_newlines=True)
        self.assertRegex(out, 'eth0.*\sconnected')

    def test_two_eth(self):
        # test with numeric state value
        self.dbusmock.AddEthernetDevice('mock_Ethernet1', 'eth0', 30)
        self.dbusmock.AddEthernetDevice('mock_Ethernet2', 'eth1',
                                        DeviceState.ACTIVATED)
        out = subprocess.check_output(['nmcli', '--nocheck', 'dev'],
                                      env=self.lang_env,
                                      universal_newlines=True)
        self.assertRegex(out, 'eth0.*\sdisconnected')
        self.assertRegex(out, 'eth1.*\sconnected')

    def test_wifi_without_access_points(self):
        self.dbusmock.AddWiFiDevice('mock_WiFi1', 'wlan0',
                                    DeviceState.ACTIVATED)
        out = subprocess.check_output(['nmcli', '--nocheck', 'dev'],
                                      env=self.lang_env,
                                      universal_newlines=True)
        self.assertRegex(out, 'wlan0.*\sconnected')

    def test_eth_and_wifi(self):
        self.dbusmock.AddEthernetDevice('mock_Ethernet1', 'eth0',
                                        DeviceState.DISCONNECTED)
        self.dbusmock.AddWiFiDevice('mock_WiFi1', 'wlan0',
                                    DeviceState.ACTIVATED)
        out = subprocess.check_output(['nmcli', '--nocheck', 'dev'],
                                      env=self.lang_env,
                                      universal_newlines=True)
        self.assertRegex(out, 'eth0.*\sdisconnected')
        self.assertRegex(out, 'wlan0.*\sconnected')

    def test_two_wifi_with_accesspoints(self):
        wifi1 = self.dbusmock.AddWiFiDevice('mock_WiFi1', 'wlan0',
                                            DeviceState.ACTIVATED)
        wifi2 = self.dbusmock.AddWiFiDevice('mock_WiFi2', 'wlan1',
                                            DeviceState.UNAVAILABLE)
        self.dbusmock.AddAccessPoint(wifi1, 'Mock_AP0',
                                     'AP_0', '00:23:F8:7E:12:BA',
                                     0, 2425, 5400, 82, 0x400)
        self.dbusmock.AddAccessPoint(wifi2, 'Mock_AP1', 'AP_1',
                                     '00:23:F8:7E:12:BB',
                                     1, 2425, 5400, 82, 0x100)
        self.dbusmock.AddAccessPoint(wifi2, 'Mock_AP3', 'AP_2',
                                     '00:23:F8:7E:12:BC',
                                     2, 2425, 5400, 82, 0x400)
        out = subprocess.check_output(['nmcli', '--nocheck', 'dev'],
                                      env=self.lang_env,
                                      universal_newlines=True)
        aps = subprocess.check_output(['nmcli', '--nocheck', 'dev', 'wifi'],
                                      env=self.lang_env,
                                      universal_newlines=True)
        self.assertRegex(out, 'wlan0.*\sconnected')
        self.assertRegex(out, 'wlan1.*\sunavailable')
        self.assertRegex(aps, 'AP_0.*\sUnknown')
        self.assertRegex(aps, 'AP_1.*\sAd-Hoc')
        self.assertRegex(aps, 'AP_2.*\sInfrastructure')

    def test_wifi_with_connection(self):
        wifi1 = self.dbusmock.AddWiFiDevice('mock_WiFi1', 'wlan0',
                                            DeviceState.ACTIVATED)
        con1 = self.dbusmock.AddWiFiConnection(wifi1, 'Mock_Con1', 'The_SSID',
                                               'wpa-psk')

        out = subprocess.check_output(['nmcli', '--nocheck', 'connection'],
                                      env=self.lang_env,
                                      universal_newlines=True)
        self.assertRegex(out, 'The_SSID.*\s802-11-wireless')
        self.assertEqual(con1, '/org/freedesktop/NetworkManager/Settings/Mock_Con1')

if __name__ == '__main__':
    unittest.main(testRunner=unittest.TextTestRunner(stream=sys.stdout, verbosity=2))
