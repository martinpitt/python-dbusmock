'''NetworkManager mock template

This creates the expected methods and properties of the main
org.freedesktop.NetworkManager object, but no devices. You can specify any property
such as NetworkingEnabled, WirelessEnabled etc. in "parameters".
'''

# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 3 of the License, or (at your option) any
# later version.  See http://www.gnu.org/copyleft/lgpl.html for the full text
# of the license.

__author__ = 'Iftikhar Ahmad'
__email__ = 'iftikhar.ahmad@canonical.com'
__copyright__ = '(c) 2012 Canonical Ltd.'
__license__ = 'LGPL 3+'

import dbus

from dbusmock import MOCK_IFACE
import dbusmock

BUS_NAME = 'org.freedesktop.NetworkManager'
MAIN_OBJ = '/org/freedesktop/NetworkManager'
MAIN_IFACE = 'org.freedesktop.NetworkManager'
SYSTEM_BUS = True

#AccessPoint maping, to support multiple WiFi devices each having its own list of accesspoints.
class WiFiDevice:
    def __init__(self):
        self.accesspoints = {} 

wifi_devices = {}

def load(mock, parameters):
    mock.AddMethods(MAIN_IFACE, [
        ('GetDevices', '', 'ao', 'ret = [k for k in objects.keys() if "/Devices" in k]'),
        ('GetPermissions', '', 'a{ss}', 'ret = {}'),
    ])

    mock.AddProperties('', 
                           {                        
                         'NetworkingEnabled': parameters.get('NetworkingEnabled',True),
                         'State': parameters.get('State', dbus.UInt32(70)),
                         'Version': parameters.get('Version', '0.9.6.0'),
                         'WimaxEnabled': parameters.get('WimaxEnabled',True),
                         'WimaxHardwareEnabled': parameters.get('WimaxHardwareEnabled',True),
                         'WirelessEnabled': parameters.get('WirelessEnabled',True),
                         'WirelessHardwareEnabled': parameters.get('WirelessHardwareEnabled',True),
                         'WwanEnabled': parameters.get('WwanEnabled',False),
                         'WwanHardwareEnabled': parameters.get('WwanHardwareEnabled',True)
                         }
                      )

@dbus.service.method(MOCK_IFACE,
                     in_signature='ssi', out_signature='s')
def AddEthernetDevice(self, device_name, iface_name, state):
    '''Convenience method to add a Ethernet Device

    You have to specify device_name, device interface name e.g. eth0 and state.
    For valid state values, please visit http://projects.gnome.org/NetworkManager/developers/api/09/spec.html#type-NM_DEVICE_STATE

    Please note that this does not set any global properties.

    Returns the new object path.
    '''
    path = '/org/freedesktop/NetworkManager/Devices/' + device_name
    wired_props = { 'Carrier':dbus.Boolean(0,variant_level=1),                                  
                         'HwAddress': dbus.String("78:DD:08:D2:3D:43", variant_level=1),
                         'PermHwAddress': dbus.String("78:DD:08:D2:3D:43", variant_level=1),
                         'Speed': dbus.UInt32(0, variant_level=1)                                
                        }
    wired_methods = []
    self.count = 1
    self.AddObject(path,
                        'org.freedesktop.NetworkManager.Device.Wired',
                        wired_props,
                        wired_methods)
    props = {'DeviceType': dbus.UInt32(1, variant_level=1),
                        'State': dbus.UInt32(state, variant_level=1),
                        'Interface': dbus.String(iface_name, variant_level=1),
                        'IpInterface': dbus.String('', variant_level=1)                                          
                       }
    
    obj = dbusmock.get_object(path)
    obj.AddProperties('org.freedesktop.NetworkManager.Device', props)    
    return path

@dbus.service.method(MOCK_IFACE,
                     in_signature='ssi', out_signature='s')
def AddWiFiDevice(self, device_name, iface_name, state):
    '''Convenience method to add a WiFi Device

    You have to specify device_name, device interface name e.g. wlan0 and state.
    For valid state values, please visit http://projects.gnome.org/NetworkManager/developers/api/09/spec.html#type-NM_DEVICE_STATE

    Please note that this does not set any global properties.

    Returns the new object path.
    '''
    
    path = '/org/freedesktop/NetworkManager/Devices/' + device_name
    self.AddObject(path,
                                 'org.freedesktop.NetworkManager.Device.Wireless',
                                 {
                                  #'ActiveAccessPoint':dbus.ObjectPath("/org/freedesktop/NetworkManager/AccessPoint/0",variant_level=1),
                                  'HwAddress': dbus.String("78:DD:08:D2:3D:43", variant_level=1),
                                  'PermHwAddress': dbus.String("78:DD:08:D2:3D:43", variant_level=1),
                                  'Bitrate':dbus.UInt32(5400, variant_level=1),
                                  'Mode': dbus.UInt32(2,variant_level=1),
                                  'WirelessCapabilities': dbus.UInt32(255,variant_level=1)
                                  },
                                 [
                                     ('GetAccessPoints', '', 'ao',
                                      'ret = []'),
                                 ])
    
    dev_obj = dbusmock.get_object(path)
    dev_obj.AddProperties('org.freedesktop.NetworkManager.Device', 
                                     {                                                                            
                                    'DeviceType': dbus.UInt32(2, variant_level=1),
                                    'State': dbus.UInt32(state, variant_level=1),
                                    'Interface': dbus.String(iface_name, variant_level=1),
                                    'IpInterface': dbus.String(iface_name, variant_level=1)                                                                                                                        
                                     })
    dev_wifi = WiFiDevice()
    wifi_devices[path] = dev_wifi
    return path

@dbus.service.method(MOCK_IFACE,
                     in_signature='ssssuuuyu', out_signature='s')
def AddAccessPoint(self, dev_path, ap_name, ssid, bssid, mode, frequency, rate, strength, security):
    '''Convenience method to add a Access Point to existing WiFi Device

    You have to specify WiFi Device path, Access Point object name, ssid, bssid, mode, frequency, rate, strength and security.
    For valid access point property values, please visit http://projects.gnome.org/NetworkManager/developers/api/09/spec.html#org.freedesktop.NetworkManager.AccessPoint

    Please note that this does not set any global properties.

    Returns the new object path.
    '''
    if bssid in wifi_devices[dev_path].accesspoints:
            raise dbus.exceptions.DBusException("Access point with bssid {0} on device {1} already exists.".format( bssid, dev_path))
    ap_path = '/org/freedesktop/NetworkManager/AccessPoint/' + ap_name
    self.AddObject(ap_path,
                                 'org.freedesktop.NetworkManager.AccessPoint',
                                 {
                                  'Ssid':dbus.ByteArray(ssid.encode(),variant_level=1),                                  
                                  'HwAddress': dbus.String(bssid.encode(), variant_level=1),       
                                  'Flags':dbus.UInt32(1, variant_level=1),       
                                  'Frequency': dbus.UInt32(frequency, variant_level=1),
                                  'MaxBitrate': dbus.UInt32(rate, variant_level=1),                    
                                  'Mode': dbus.UInt32(mode,variant_level=1),
                                  'RsnFlags': dbus.UInt32(324, variant_level=1),
                                  'WpaFlags': dbus.UInt32(security, variant_level=1),
                                  'Strength': dbus.Byte(strength, variant_level=1),                                                            
                                  },
                                 [                                  
                                 ])

    wifi_devices[dev_path].accesspoints[bssid] = '\''+ap_path+'\''
    accesspoints = wifi_devices[dev_path].accesspoints.values()    
    ap_list = ','.join(accesspoints)
    ap_ret = 'ret=['+ap_list+']'
    dev_obj = dbusmock.get_object(dev_path)
    dev_obj.AddMethod('org.freedesktop.NetworkManager.Device.Wireless', 'GetAccessPoints', '', 'ao', ap_ret)
    return ap_path
