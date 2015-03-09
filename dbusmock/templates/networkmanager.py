'''NetworkManager mock template

This creates the expected methods and properties of the main
org.freedesktop.NetworkManager object, but no devices. You can specify any
property such as 'NetworkingEnabled', or 'WirelessEnabled' etc. in
"parameters".
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
import uuid
import binascii

from dbusmock import MOCK_IFACE
import dbusmock

BUS_NAME = 'org.freedesktop.NetworkManager'
MAIN_OBJ = '/org/freedesktop/NetworkManager'
MAIN_IFACE = 'org.freedesktop.NetworkManager'
SETTINGS_OBJ = '/org/freedesktop/NetworkManager/Settings'
SETTINGS_IFACE = 'org.freedesktop.NetworkManager.Settings'
DEVICE_IFACE = 'org.freedesktop.NetworkManager.Device'
WIRELESS_DEVICE_IFACE = 'org.freedesktop.NetworkManager.Device.Wireless'
ACCESS_POINT_IFACE = 'org.freedesktop.NetworkManager.AccessPoint'
CSETTINGS_IFACE = 'org.freedesktop.NetworkManager.Settings.Connection'
ACTIVE_CONNECTION_IFACE = 'org.freedesktop.NetworkManager.Connection.Active'
SYSTEM_BUS = True


class InfrastructureMode:

    NM_802_11_MODE_UNKNOWN = 0
    NM_802_11_MODE_ADHOC = 1
    NM_802_11_MODE_INFRA = 2
    NM_802_11_MODE_AP = 3
    
    NAME_MAP = {
        NM_802_11_MODE_UNKNOWN: 'unknown',
        NM_802_11_MODE_ADHOC: 'adhoc',
        NM_802_11_MODE_INFRA: 'infrastructure',
        NM_802_11_MODE_AP: 'access-point',
    }


class DeviceState:
    '''Device states

    As per http://projects.gnome.org/NetworkManager/developers/api/09/spec.html#type-NM_DEVICE_STATE
    '''
    UNKNOWN = 0
    UNMANAGED = 10
    UNAVAILABLE = 20
    DISCONNECTED = 30
    PREPARE = 40
    CONFIG = 50
    NEED_AUTH = 60
    IP_CONFIG = 70
    IP_CHECK = 80
    SECONDARIES = 90
    ACTIVATED = 100
    DEACTIVATING = 110
    FAILED = 120


class NM80211ApSecurityFlags:

    NM_802_11_AP_SEC_NONE            = 0x00000000
    NM_802_11_AP_SEC_PAIR_WEP40      = 0x00000001
    NM_802_11_AP_SEC_PAIR_WEP104     = 0x00000002
    NM_802_11_AP_SEC_PAIR_TKIP       = 0x00000004
    NM_802_11_AP_SEC_PAIR_CCMP       = 0x00000008
    NM_802_11_AP_SEC_GROUP_WEP40     = 0x00000010
    NM_802_11_AP_SEC_GROUP_WEP104    = 0x00000020
    NM_802_11_AP_SEC_GROUP_TKIP      = 0x00000040
    NM_802_11_AP_SEC_GROUP_CCMP      = 0x00000080
    NM_802_11_AP_SEC_KEY_MGMT_PSK    = 0x00000100
    NM_802_11_AP_SEC_KEY_MGMT_802_1X = 0x00000200
    
    NAME_MAP = {
        NM_802_11_AP_SEC_KEY_MGMT_PSK: {
            'key-mgmt': 'wpa-psk',
            'auth-alg': 'open'
        },
    }


class NM80211ApFlags:

    NM_802_11_AP_FLAGS_NONE    = 0x00000000
    NM_802_11_AP_FLAGS_PRIVACY = 0x00000001


def load(mock, parameters):
    mock.AddMethods(MAIN_IFACE, [
        ('GetDevices', '', 'ao',
         'ret = [k for k in objects.keys() if "/Devices" in k]'),
        ('GetPermissions', '', 'a{ss}', 'ret = {}'),
        ('state', '', 'u', "ret = self.Get('%s', 'State')" % MAIN_IFACE),
        ('ActivateConnection', 'ooo', 'o', "ret = args[0]"),
        ('AddAndActivateConnection', 'a{sa{sv}}oo', 'oo',
         "ret = (dbus.ObjectPath('/org/freedesktop/NetworkManager/Settings/new'), dbus.ObjectPath('/org/freedesktop/NetworkManager/Settings/new'))"),
    ])

    mock.AddProperties('',
                       {
                           'Devices': dbus.Array([], signature='o'),
                           'NetworkingEnabled': parameters.get('NetworkingEnabled', True),
                           'State': parameters.get('State', dbus.UInt32(70)),
                           'Startup': False,
                           'Version': parameters.get('Version', '0.9.6.0'),
                           'WimaxEnabled': parameters.get('WimaxEnabled', True),
                           'WimaxHardwareEnabled': parameters.get('WimaxHardwareEnabled', True),
                           'WirelessEnabled': parameters.get('WirelessEnabled', True),
                           'WirelessHardwareEnabled': parameters.get('WirelessHardwareEnabled', True),
                           'WwanEnabled': parameters.get('WwanEnabled', False),
                           'WwanHardwareEnabled': parameters.get('WwanHardwareEnabled', True)
                       })

    settings_props = {'Hostname': 'hostname',
                      'CanModify': True,
                      'Connections': dbus.Array([], signature='o')}
    settings_methods = [('ListConnections', '', 'ao', "ret = self.Get('%s', 'Connections')" % SETTINGS_IFACE),
                        ('GetConnectionByUuid', 's', 'o', ''),
                        ('AddConnection', 'a{sa{sv}}', 'o', ''),
                        ('SaveHostname', 's', '', '')]
    mock.AddObject(SETTINGS_OBJ,
                   SETTINGS_IFACE,
                   settings_props,
                   settings_methods)


@dbus.service.method(MOCK_IFACE,
                     in_signature='sssv', out_signature='')
def SetProperty(self, path, iface, name, value):
    obj = dbusmock.get_object(path)
    obj.Set(iface, name, value)
    obj.EmitSignal(iface, 'PropertiesChanged', 'a{sv}', [{name: value}])


@dbus.service.method(MOCK_IFACE,
                     in_signature='u', out_signature='')
def SetGlobalConnectionState(self, state):
    self.SetProperty(MAIN_OBJ, MAIN_IFACE, 'State', dbus.UInt32(state, variant_level=1))
    self.EmitSignal(MAIN_IFACE, 'StateChanged', 'u', [state])


@dbus.service.method(MOCK_IFACE,
                     in_signature='ss', out_signature='')
def SetDeviceActive(self, device_path, active_connection_path):
    dev_obj = dbusmock.get_object(device_path)
    dev_obj.Set(DEVICE_IFACE, 'ActiveConnection', dbus.ObjectPath(active_connection_path))
    old_state = dev_obj.Get(DEVICE_IFACE, 'State')
    dev_obj.Set(DEVICE_IFACE, 'State', dbus.UInt32(100))

    dev_obj.EmitSignal(DEVICE_IFACE, 'StateChanged', 'uuu', [dbus.UInt32(100), old_state, dbus.UInt32(1)])


@dbus.service.method(MOCK_IFACE,
                     in_signature='ssi', out_signature='s')
def AddEthernetDevice(self, device_name, iface_name, state):
    '''Add an ethernet device.

    You have to specify device_name, device interface name (e. g. eth0), and
    state. You can use the predefined DeviceState values (e. g.
    DeviceState.ACTIVATED) or supply a numeric value. For valid state values
    please visit
    http://projects.gnome.org/NetworkManager/developers/api/09/spec.html#type-NM_DEVICE_STATE

    Please note that this does not set any global properties.

    Returns the new object path.
    '''
    path = '/org/freedesktop/NetworkManager/Devices/' + device_name
    wired_props = {'Carrier': False,
                   'HwAddress': dbus.String('78:DD:08:D2:3D:43'),
                   'PermHwAddress': dbus.String('78:DD:08:D2:3D:43'),
                   'Speed': dbus.UInt32(0)}
    self.AddObject(path,
                   'org.freedesktop.NetworkManager.Device.Wired',
                   wired_props,
                   [])

    props = {'DeviceType': dbus.UInt32(1),
             'State': dbus.UInt32(state),
             'Interface': iface_name,
             'AvailableConnections': dbus.Array([], signature='o'),
             'IpInterface': ''}

    obj = dbusmock.get_object(path)
    obj.AddProperties(DEVICE_IFACE, props)

    devices = self.Get(MAIN_IFACE, 'Devices')
    devices.append(path)
    self.Set(MAIN_IFACE, 'Devices', devices)

    self.EmitSignal('org.freedesktop.NetworkManager', 'DeviceAdded', 'o', [path])

    return path


@dbus.service.method(MOCK_IFACE,
                     in_signature='ssi', out_signature='s')
def AddWiFiDevice(self, device_name, iface_name, state):
    '''Add a WiFi Device.

    You have to specify device_name, device interface name (e. g.  wlan0) and
    state. You can use the predefined DeviceState values (e. g.
    DeviceState.ACTIVATED) or supply a numeric value. For valid state values,
    please visit
    http://projects.gnome.org/NetworkManager/developers/api/09/spec.html#type-NM_DEVICE_STATE

    Please note that this does not set any global properties.

    Returns the new object path.
    '''

    path = '/org/freedesktop/NetworkManager/Devices/' + device_name
    self.AddObject(path,
                   WIRELESS_DEVICE_IFACE,
                   {
                       'HwAddress': dbus.String('11:22:33:44:55:66'),
                       'PermHwAddress': dbus.String('11:22:33:44:55:66'),
                       'Bitrate': dbus.UInt32(5400),
                       'Mode': dbus.UInt32(2),
                       'WirelessCapabilities': dbus.UInt32(255),
                       'AccessPoints': dbus.Array([], signature='o'),
                   },
                   [
                       ('GetAccessPoints', '', 'ao',
                        'ret = self.access_points'),
                       ('GetAllAccessPoints', '', 'ao',
                        'ret = self.access_points'),
                       ('RequestScan', 'a{sv}', '', ''),
                   ])

    dev_obj = dbusmock.get_object(path)
    dev_obj.access_points = []
    dev_obj.AddProperties(DEVICE_IFACE,
                          {
                              'ActiveConnection': dbus.ObjectPath('/'),
                              'AvailableConnections': dbus.Array([], signature='o'),
                              'AutoConnect': False,
                              'Managed': True,
                              'Driver': 'dbusmock',
                              'DeviceType': dbus.UInt32(2),
                              'State': dbus.UInt32(state),
                              'Interface': iface_name,
                              'IpInterface': iface_name,
                          })

    devices = self.Get(MAIN_IFACE, 'Devices')
    devices.append(path)
    self.Set(MAIN_IFACE, 'Devices', devices)

    self.EmitSignal('org.freedesktop.NetworkManager', 'DeviceAdded', 'o', [path])

    return path


@dbus.service.method(MOCK_IFACE,
                     in_signature='ssssuuuyu', out_signature='s')
def AddAccessPoint(self, dev_path, ap_name, ssid, hw_address,
                   mode, frequency, rate, strength, security):
    '''Add an access point to an existing WiFi device.

    You have to specify WiFi Device path, Access Point object name,
    ssid, hw_address, mode, frequency, rate, strength and security.
    For valid access point property values, please visit
    http://projects.gnome.org/NetworkManager/developers/api/09/spec.html#org.freedesktop.NetworkManager.AccessPoint

    Please note that this does not set any global properties.

    Returns the new object path.
    '''
    dev_obj = dbusmock.get_object(dev_path)
    ap_path = '/org/freedesktop/NetworkManager/AccessPoint/' + ap_name
    if ap_path in dev_obj.access_points:
        raise dbus.exceptions.DBusException(
            MAIN_IFACE + '.AlreadyExists',
            'Access point %s on device %s already exists' % (ap_name, dev_path))

    flags = NM80211ApFlags.NM_802_11_AP_FLAGS_PRIVACY
    if security == NM80211ApSecurityFlags.NM_802_11_AP_SEC_NONE:
        flags = NM80211ApFlags.NM_802_11_AP_FLAGS_NONE

    self.AddObject(ap_path,
                   ACCESS_POINT_IFACE,
                   {'Ssid': dbus.ByteArray(ssid.encode('UTF-8')),
                    'HwAddress': dbus.String(hw_address),
                    'Flags': dbus.UInt32(flags),
                    'LastSeen': dbus.Int32(1),
                    'Frequency': dbus.UInt32(frequency),
                    'MaxBitrate': dbus.UInt32(rate),
                    'Mode': dbus.UInt32(mode),
                    'RsnFlags': dbus.UInt32(324),
                    'WpaFlags': dbus.UInt32(security),
                    'Strength': dbus.Byte(strength)},
                   [])

    dev_obj.access_points.append(ap_path)

    aps = dev_obj.Get(WIRELESS_DEVICE_IFACE, 'AccessPoints')
    aps.append(ap_path)
    dev_obj.Set(WIRELESS_DEVICE_IFACE, 'AccessPoints', aps)

    dev_obj.EmitSignal(WIRELESS_DEVICE_IFACE, 'AccessPointAdded', 'o', [ap_path])

    return ap_path


@dbus.service.method(MOCK_IFACE,
                     in_signature='ssss', out_signature='s')
def AddWiFiConnection(self, dev_path, connection_name, ssid_name, key_mgmt):
    dev_obj = dbusmock.get_object(dev_path)
    connection_path = '/org/freedesktop/NetworkManager/Settings/' + connection_name
    connections = dev_obj.Get(DEVICE_IFACE, 'AvailableConnections')

    settings_obj = dbusmock.get_object(SETTINGS_OBJ)
    main_connections = settings_obj.ListConnections()
    
    ssid = ssid_name.encode('UTF-8')
    
    # Find the access point by ssid
    access_point = None
    access_points = dev_obj.access_points
    for ap_path in access_points:
        ap = dbusmock.get_object(ap_path)
        if ap.Get(ACCESS_POINT_IFACE, 'Ssid') == ssid:
            access_point = ap
            break

    if not access_point:
        raise dbus.exceptions.DBusException(
            MAIN_IFACE + '.DoesNotExist',
            'Access point with SSID [%s] could not be found' % (ssid_name))

    hw_address = access_point.Get(ACCESS_POINT_IFACE, 'HwAddress');
    mode = access_point.Get(ACCESS_POINT_IFACE, 'Mode');
    security = access_point.Get(ACCESS_POINT_IFACE, 'WpaFlags');

    if connection_path in connections or connection_path in main_connections:
        raise dbus.exceptions.DBusException(
            MAIN_IFACE + '.AlreadyExists',
            'Connection %s on device %s already exists' % (connection_name, dev_path))

    # Parse mac address string into byte array
    mac_bytes = binascii.unhexlify(hw_address.replace(':', ''))

    settings = {
        '802-11-wireless': {
            'seen-bssids': [hw_address],
            'ssid': dbus.ByteArray(ssid),
            'mac-address': dbus.ByteArray(mac_bytes),
            'mode': InfrastructureMode.NAME_MAP[mode]
        },
        'connection': {
            'timestamp': dbus.UInt64(1374828522),
            'type': '802-11-wireless',
            'id': ssid_name,
            'uuid': str(uuid.uuid4())
        },
    }

    if security != NM80211ApSecurityFlags.NM_802_11_AP_SEC_NONE:
        settings['802-11-wireless']['security'] = '802-11-wireless-security'
        settings['802-11-wireless-security'] = NM80211ApSecurityFlags.NAME_MAP[security]
        
    self.AddObject(connection_path,
                   CSETTINGS_IFACE,
                   {
                       'Settings': dbus.Dictionary(settings, signature='sa{sv}'),
                       'Secrets': dbus.Dictionary({}, signature='sa{sv}'),
                   },
                   [
                       ('Delete', '', '', ''),
                       ('GetSettings', '', 'a{sa{sv}}', "ret = self.Get('%s', 'Settings')" % CSETTINGS_IFACE),
                       ('GetSecrets', 's', 'a{sa{sv}}', "ret = self.Get('%s', 'Secrets')" % CSETTINGS_IFACE),
                       ('Update', 'a{sa{sv}}', '', ''),
                   ])

    connections.append(dbus.ObjectPath(connection_path))
    dev_obj.Set(DEVICE_IFACE, 'AvailableConnections', connections)

    main_connections.append(connection_path)
    settings_obj.Set(SETTINGS_IFACE, 'Connections', main_connections)

    settings_obj.EmitSignal(SETTINGS_IFACE, 'NewConnection', 'o', [ap_path])

    return connection_path


@dbus.service.method(MOCK_IFACE,
                     in_signature='assssu', out_signature='s')
def AddActiveConnection(self, devices, connection_device, specific_object, name, state):
    active_connection_path = '/org/freedesktop/NetworkManager/ActiveConnection/' + name
    self.AddObject(active_connection_path,
                   ACTIVE_CONNECTION_IFACE,
                   {
                       'Devices': devices,
                       'Default6': False,
                       'Default': True,
                       'Vpn': False,
                       'Connection': dbus.ObjectPath(connection_device),
                       'Master': dbus.ObjectPath('/'),
                       'SpecificObject': dbus.ObjectPath(specific_object),
                       'Uuid': str(uuid.uuid4()),
                       'State': state,
                   },
                   [])

    for dev_path in devices:
        self.SetDeviceActive(dev_path, active_connection_path)

    return active_connection_path


@dbus.service.method(MOCK_IFACE,
                     in_signature='ss', out_signature='')
def RemoveAccessPoint(self, dev_path, ap_path):
    dev_obj = dbusmock.get_object(dev_path)

    aps = dev_obj.Get(WIRELESS_DEVICE_IFACE, 'AccessPoints')
    aps.remove(ap_path)
    dev_obj.Set(WIRELESS_DEVICE_IFACE, 'AccessPoints', aps)

    dev_obj.access_points.remove(ap_path)

    dev_obj.EmitSignal(WIRELESS_DEVICE_IFACE, 'AccessPointRemoved', 'o', [ap_path])

    self.RemoveObject(ap_path)


@dbus.service.method(MOCK_IFACE,
                     in_signature='ss', out_signature='')
def RemoveWifiConnection(self, dev_path, connection_path):
    dev_obj = dbusmock.get_object(dev_path)
    settings_obj = dbusmock.get_object(SETTINGS_OBJ)

    connections = dev_obj.Get(DEVICE_IFACE, 'AvailableConnections')
    connections.remove(dbus.ObjectPath(connection_path))
    dev_obj.Set(DEVICE_IFACE, 'AvailableConnections', connections)

    main_connections = settings_obj.ListConnections()
    main_connections.remove(connection_path)
    settings_obj.Set(SETTINGS_IFACE, 'Connections', main_connections)

    settings_obj.EmitSignal(SETTINGS_IFACE, 'ConnectionRemoved', 'o', [ap_path])

    self.RemoveObject(connection_path)


@dbus.service.method(MOCK_IFACE,
                     in_signature='ss', out_signature='')
def RemoveActiveConnection(self, dev_path, active_connection_path):
    dev_obj = dbusmock.get_object(dev_path)
    dev_obj.Set(DEVICE_IFACE, 'ActiveConnection', dbus.ObjectPath('/'))

    old_state = dev_obj.Get(DEVICE_IFACE, 'State')
    dev_obj.Set(DEVICE_IFACE, 'State', old_state)

    dev_obj.EmitSignal(DEVICE_IFACE, 'StateChanged', 'uuu', [old_state, old_state, dbus.UInt32(1)])

    self.RemoveObject(active_connection_path)

