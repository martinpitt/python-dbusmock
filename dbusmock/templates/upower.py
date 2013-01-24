'''upowerd mock template

This creates the expected methods and properties of the main
org.freedesktop.UPower object, but no devices. You can specify any property
such as 'OnLowBattery' or the return value of 'SuspendAllowed' and
'HibernateAllowed' in "parameters".
'''

# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 3 of the License, or (at your option) any
# later version.  See http://www.gnu.org/copyleft/lgpl.html for the full text
# of the license.

__author__ = 'Martin Pitt'
__email__ = 'martin.pitt@ubuntu.com'
__copyright__ = '(c) 2012 Canonical Ltd.'
__license__ = 'LGPL 3+'

import dbus

from dbusmock import MOCK_IFACE

BUS_NAME = 'org.freedesktop.UPower'
MAIN_OBJ = '/org/freedesktop/UPower'
MAIN_IFACE = 'org.freedesktop.UPower'
SYSTEM_BUS = True


def load(mock, parameters):
    mock.AddMethods(MAIN_IFACE, [
        ('Suspend', '', '', ''),
        ('SuspendAllowed', '', 'b', 'ret = %s' % parameters.get('SuspendAllowed', True)),
        ('HibernateAllowed', '', 'b', 'ret = %s' % parameters.get('HibernateAllowed', True)),
        ('EnumerateDevices', '', 'ao', 'ret = [k for k in objects.keys() if "/devices" in k]'),
    ])

    mock.AddProperties(MAIN_IFACE,
                       dbus.Dictionary({
                           'DaemonVersion': parameters.get('DaemonVersion', '0.8.15'),
                           'CanSuspend': parameters.get('CanSuspend', True),
                           'CanHibernate': parameters.get('CanHibernate', True),
                           'OnBattery': parameters.get('OnBattery', False),
                           'OnLowBattery': parameters.get('OnLowBattery', True),
                           'LidIsPresent': parameters.get('LidIsPresent', True),
                           'LidIsClosed': parameters.get('LidIsClosed', False),
                           'LidForceSleep': parameters.get('LidForceSleep', True),
                           'IsDocked': parameters.get('IsDocked', False),
                       }, signature='sv'))


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
                   'org.freedesktop.UPower.Device',
                   {
                       'PowerSupply': dbus.Boolean(True, variant_level=1),
                       'Model': dbus.String(model_name, variant_level=1),
                   },
                   [])
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
                   'org.freedesktop.UPower.Device',
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
                   'org.freedesktop.UPower.Device',
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
    return path
