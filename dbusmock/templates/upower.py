'''upowerd mock template

This creates the expected methods and properties of the main
org.freedesktop.UPower object, but no devices. You can specify any property
such as 'OnLowBattery' or the return value of 'SuspendAllowed',
'HibernateAllowed', and 'GetCriticalAction' in "parameters".

This provides the 0.9 D-Bus API of upower by default, but if the
DaemonVersion property (in parameters) is set to >= 0.99 it will provide the
1.0 D-Bus API instead.
'''

# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 3 of the License, or (at your option) any
# later version.  See http://www.gnu.org/copyleft/lgpl.html for the full text
# of the license.

__author__ = 'Martin Pitt'
__email__ = 'martin.pitt@ubuntu.com'
__copyright__ = '(c) 2012, 2013 Canonical Ltd.'
__license__ = 'LGPL 3+'

import dbus

from dbusmock import MOCK_IFACE, mockobject
import dbusmock

BUS_NAME = 'org.freedesktop.UPower'
MAIN_OBJ = '/org/freedesktop/UPower'
MAIN_IFACE = 'org.freedesktop.UPower'
SYSTEM_BUS = True
DEVICE_IFACE = 'org.freedesktop.UPower.Device'


def load(mock, parameters):
    mock.AddMethods(MAIN_IFACE, [
        ('EnumerateDevices', '', 'ao', 'ret = [k for k in objects.keys() '
         'if "/devices" in k and not k.endswith("/DisplayDevice")]'),
    ])

    props = dbus.Dictionary({
        'DaemonVersion': parameters.get('DaemonVersion', '0.9'),
        'OnBattery': parameters.get('OnBattery', False),
        'LidIsPresent': parameters.get('LidIsPresent', True),
        'LidIsClosed': parameters.get('LidIsClosed', False),
        'LidForceSleep': parameters.get('LidForceSleep', True),
        'IsDocked': parameters.get('IsDocked', False),
    }, signature='sv')

    mock.api1 = props['DaemonVersion'] >= '0.99'

    if mock.api1:
        mock.AddMethods(MAIN_IFACE, [
            ('GetCriticalAction', '', 's', 'ret = "%s"' % parameters.get('GetCriticalAction', 'HybridSleep')),
            ('GetDisplayDevice', '', 'o', 'ret = "/org/freedesktop/UPower/devices/DisplayDevice"')
        ])

        mock.p_display_dev = '/org/freedesktop/UPower/devices/DisplayDevice'

        # add Display device; for defined properties, see
        # http://cgit.freedesktop.org/upower/tree/src/org.freedesktop.UPower.xml
        mock.AddObject(mock.p_display_dev,
                       DEVICE_IFACE,
                       {
                           'Type': dbus.UInt32(0, variant_level=1),
                           'State': dbus.UInt32(0, variant_level=1),
                           'Percentage': dbus.Double(0.0, variant_level=1),
                           'Energy': dbus.Double(0.0, variant_level=1),
                           'EnergyFull': dbus.Double(0.0, variant_level=1),
                           'EnergyRate': dbus.Double(0.0, variant_level=1),
                           'TimeToEmpty': dbus.Int64(0, variant_level=1),
                           'TimeToFull': dbus.Int64(0, variant_level=1),
                           'IsPresent': dbus.Boolean(False, variant_level=1),
                           'IconName': dbus.String('', variant_level=1),
                           # LEVEL_NONE
                           'WarningLevel': dbus.UInt32(1, variant_level=1),
                       },
                       [
                           ('Refresh', '', '', ''),
                       ])

        mock.device_sig_type = 'o'
    else:
        props['CanSuspend'] = parameters.get('CanSuspend', True)
        props['CanHibernate'] = parameters.get('CanHibernate', True)
        props['OnLowBattery'] = parameters.get('OnLowBattery', True)

        mock.AddMethods(MAIN_IFACE, [
            ('Suspend', '', '', ''),
            ('SuspendAllowed', '', 'b', 'ret = %s' % parameters.get('SuspendAllowed', True)),
            ('HibernateAllowed', '', 'b', 'ret = %s' % parameters.get('HibernateAllowed', True)),
        ])
        mock.device_sig_type = 's'

    mock.AddProperties(MAIN_IFACE, props)


@dbus.service.method(MOCK_IFACE,
                     in_signature='ss', out_signature='s')
def AddAC(self, device_name, model_name):
    '''Convenience method to add an AC object

    You have to specify a device name which must be a valid part of an object
    path, e. g. "mock_ac", and an arbitrary model name.

    Please note that this does not set any global properties such as
    "on-battery".

    Returns the new object path.
    '''
    path = '/org/freedesktop/UPower/devices/' + device_name
    self.AddObject(path,
                   DEVICE_IFACE,
                   {
                       'PowerSupply': dbus.Boolean(True, variant_level=1),
                       'Model': dbus.String(model_name, variant_level=1),
                       'Online': dbus.Boolean(True, variant_level=1),
                   },
                   [])
    self.EmitSignal(MAIN_IFACE, 'DeviceAdded', self.device_sig_type, [path])
    return path


@dbus.service.method(MOCK_IFACE,
                     in_signature='ssdx', out_signature='s')
def AddDischargingBattery(self, device_name, model_name, percentage, seconds_to_empty):
    '''Convenience method to add a discharging battery object

    You have to specify a device name which must be a valid part of an object
    path, e. g. "mock_ac", an arbitrary model name, the charge percentage, and
    the seconds until the battery is empty.

    Please note that this does not set any global properties such as
    "on-battery".

    Returns the new object path.
    '''
    path = '/org/freedesktop/UPower/devices/' + device_name
    self.AddObject(path,
                   DEVICE_IFACE,
                   {
                       'PowerSupply': dbus.Boolean(True, variant_level=1),
                       'IsPresent': dbus.Boolean(True, variant_level=1),
                       'Model': dbus.String(model_name, variant_level=1),
                       'Percentage': dbus.Double(percentage, variant_level=1),
                       'TimeToEmpty': dbus.Int64(seconds_to_empty, variant_level=1),
                       'EnergyFull': dbus.Double(100.0, variant_level=1),
                       'Energy': dbus.Double(percentage, variant_level=1),
                       # UP_DEVICE_STATE_DISCHARGING
                       'State': dbus.UInt32(2, variant_level=1),
                       # UP_DEVICE_KIND_BATTERY
                       'Type': dbus.UInt32(2, variant_level=1),
                   },
                   [])
    self.EmitSignal(MAIN_IFACE, 'DeviceAdded', self.device_sig_type, [path])
    return path


@dbus.service.method(MOCK_IFACE,
                     in_signature='ssdx', out_signature='s')
def AddChargingBattery(self, device_name, model_name, percentage, seconds_to_full):
    '''Convenience method to add a charging battery object

    You have to specify a device name which must be a valid part of an object
    path, e. g. "mock_ac", an arbitrary model name, the charge percentage, and
    the seconds until the battery is full.

    Please note that this does not set any global properties such as
    "on-battery".

    Returns the new object path.
    '''
    path = '/org/freedesktop/UPower/devices/' + device_name
    self.AddObject(path,
                   DEVICE_IFACE,
                   {
                       'PowerSupply': dbus.Boolean(True, variant_level=1),
                       'IsPresent': dbus.Boolean(True, variant_level=1),
                       'Model': dbus.String(model_name, variant_level=1),
                       'Percentage': dbus.Double(percentage, variant_level=1),
                       'TimeToFull': dbus.Int64(seconds_to_full, variant_level=1),
                       'EnergyFull': dbus.Double(100.0, variant_level=1),
                       'Energy': dbus.Double(percentage, variant_level=1),
                       # UP_DEVICE_STATE_CHARGING
                       'State': dbus.UInt32(1, variant_level=1),
                       # UP_DEVICE_KIND_BATTERY
                       'Type': dbus.UInt32(2, variant_level=1),
                   },
                   [])
    self.EmitSignal(MAIN_IFACE, 'DeviceAdded', self.device_sig_type, [path])
    return path


@dbus.service.method(MOCK_IFACE,
                     in_signature='uuddddxxbsu', out_signature='')
def SetupDisplayDevice(self, type, state, percentage, energy, energy_full,
                       energy_rate, time_to_empty, time_to_full, is_present,
                       icon_name, warning_level):
    '''Convenience method to configure DisplayDevice properties

    This calls Set() for all properties that the DisplayDevice is defined to
    have, and is shorter if you have to completely set it up instead of
    changing just one or two properties.

    This is only available when mocking the 1.0 API.
    '''
    if not self.api1:
        raise dbus.exceptions.DBusException(
            'SetupDisplayDevice() can only be used with the 1.0 API',
            name=MOCK_IFACE + '.APIVersion')

    display_props = mockobject.objects[self.p_display_dev]
    display_props.Set(DEVICE_IFACE, 'Type',
                      dbus.UInt32(type))
    display_props.Set(DEVICE_IFACE, 'State',
                      dbus.UInt32(state))
    display_props.Set(DEVICE_IFACE, 'Percentage',
                      percentage)
    display_props.Set(DEVICE_IFACE, 'Energy', energy)
    display_props.Set(DEVICE_IFACE, 'EnergyFull',
                      energy_full)
    display_props.Set(DEVICE_IFACE, 'EnergyRate',
                      energy_rate)
    display_props.Set(DEVICE_IFACE, 'TimeToEmpty',
                      dbus.Int64(time_to_empty))
    display_props.Set(DEVICE_IFACE, 'TimeToFull',
                      dbus.Int64(time_to_full))
    display_props.Set(DEVICE_IFACE, 'IsPresent',
                      is_present)
    display_props.Set(DEVICE_IFACE, 'IconName',
                      icon_name)
    display_props.Set(DEVICE_IFACE, 'WarningLevel',
                      dbus.UInt32(warning_level))


@dbus.service.method(MOCK_IFACE, in_signature='oa{sv}', out_signature='')
def SetDeviceProperties(self, object_path, properties):
    '''Convenience method to Set a device's properties.

    object_path: the device to update
    properties: dictionary of keys to dbus variants.

    If the 1.0 API is being mocked, changing this property will trigger
    the device's PropertiesChanged signal; otherwise, the older
    org.freedesktop.UPower DeviceChanged signal will be emitted.
    '''
    device = dbusmock.get_object(object_path)

    # set the properties
    for key, value in properties.items():
        device.Set(DEVICE_IFACE, key, value)

    # notify the listeners
    if not self.api1:
        self.EmitSignal(MAIN_IFACE, 'DeviceChanged', 's', [object_path])
