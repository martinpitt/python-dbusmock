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

class TestNeworkManager(dbusmock.DBusTestCase):
    '''Test mocking NetworkManager'''
    @classmethod
    def setUpClass(klass):
        klass.start_system_bus()
        klass.dbus_con = klass.get_dbus(True)
    def setUp(self):
        (self.p_mock, self.obj_networkmanager) = self.spawn_server_template(
            'networkmanager', {'NetworkingEnabled': True, 'WwanEnabled': False}, stdout=subprocess.PIPE)
        self.dbusmock = dbus.Interface(self.obj_networkmanager, dbusmock.MOCK_IFACE)
                   
    def tearDown(self):
        self.p_mock.terminate()
        self.p_mock.wait()
          
    def test_add_one_eithernet_device_disconnected(self):
        self.dbusmock.AddEthernetDevice('mock_Ethernet1', 'eth0', 30)
        out = subprocess.check_output(['nmcli', 'dev'], universal_newlines=True)
        #self.assertFalse('DEVICE' in out, out)            
        self.assertRegex(out, 'eth0.*\sdisconnected')
        #print(out)
          
    def test_add_one_eithernet_device_connected(self):    
        self.dbusmock.AddEthernetDevice('mock_Ethernet1', 'eth0', 100)
        out = subprocess.check_output(['nmcli', 'dev'], universal_newlines=True)
        self.assertRegex(out, 'eth0.*\sconnected')
        
    def test_add_two_eithernet_devices(self):
        self.dbusmock.AddEthernetDevice('mock_Ethernet1', 'eth0', 30)  
        self.dbusmock.AddEthernetDevice('mock_Ethernet2', 'eth1', 100)
        out = subprocess.check_output(['nmcli', 'dev'], universal_newlines=True)
        self.assertRegex(out, 'eth0.*\sdisconnected')
        self.assertRegex(out, 'eth1.*\sconnected')
        
    def test_add_wifi_device_without_accesspoints(self):            
        self.dbusmock.AddWiFiDevice('mock_WiFi1', 'wlan0', 100)
        out = subprocess.check_output(['nmcli', 'dev'], universal_newlines=True)
        self.assertRegex(out, 'wlan0.*\sconnected')

    
    def test_add_ethernet_and_wifi_device(self):
        self.dbusmock.AddEthernetDevice('mock_Ethernet1', 'eth0', 30)
        self.dbusmock.AddWiFiDevice('mock_WiFi1', 'wlan0', 100)
        out = subprocess.check_output(['nmcli', 'dev'], universal_newlines=True)
        self.assertRegex(out, 'eth0.*\sdisconnected')
        self.assertRegex(out, 'wlan0.*\sconnected')
          
    def test_add_two_wifi_devices_with_accesspoints(self):            
        wifi1 = self.dbusmock.AddWiFiDevice('mock_WiFi1', 'wlan0', 100)                
        wifi2 = self.dbusmock.AddWiFiDevice('mock_WiFi2', 'wlan1', 20)          
        self.dbusmock.AddAccessPoint(wifi1,'Mock_AP0', 'AP_0', '00:23:F8:7E:12:BA', 0, 2425, 5400, 82, 0x400)
        self.dbusmock.AddAccessPoint(wifi2,'Mock_AP1', 'AP_1', '00:23:F8:7E:12:BB', 1, 2425, 5400, 82, 0x100)
        self.dbusmock.AddAccessPoint(wifi2,'Mock_AP3', 'AP_2', '00:23:F8:7E:12:BC', 2, 2425, 5400, 82, 0x400)
        out = subprocess.check_output(['nmcli', 'dev'], universal_newlines=True)
        aps = subprocess.check_output(['nmcli', 'dev', 'wifi'], universal_newlines=True)
        self.assertRegex(out, 'wlan0.*\sconnected')
        self.assertRegex(out, 'wlan1.*\sunavailable')
        self.assertRegex(aps, 'AP_0.*\sUnknown')
        self.assertRegex(aps, 'AP_1.*\sAd-Hoc')
        self.assertRegex(aps, 'AP_2.*\sInfrastructure')
    
if __name__ == '__main__':
    unittest.main(testRunner=unittest.TextTestRunner(stream=sys.stdout, verbosity=2))
