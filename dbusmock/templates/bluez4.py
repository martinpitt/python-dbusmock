# -*- coding: utf-8 -*-

'''bluetoothd mock template

This creates the expected methods and properties of the object manager
org.bluez object (/), but no adapters or devices.

This supports BlueZ 4 only.
'''

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

import dbus

from dbusmock import OBJECT_MANAGER_IFACE, mockobject

BUS_NAME = 'org.bluez'
MAIN_OBJ = '/'
SYSTEM_BUS = True
IS_OBJECT_MANAGER = True

BLUEZ_MOCK_IFACE = 'org.bluez.Mock'
AGENT_MANAGER_IFACE = 'org.bluez.Agent'
MANAGER_IFACE = 'org.bluez.Manager'
ADAPTER_IFACE = 'org.bluez.Adapter'
DEVICE_IFACE = 'org.bluez.Device'
AUDIO_IFACE = 'org.bluez.Audio'


def load(mock, parameters):
    mock.AddObject('/org/bluez', AGENT_MANAGER_IFACE, {}, [
        ('Release', '', '', ''),
    ])

    mock.AddMethods(MANAGER_IFACE, [
        ('GetProperties', '', 'a{sv}', 'ret = self.GetAll("org.bluez.Manager")'),
        ('SetProperty', 'sv', '', 'self.Set("org.bluez.Manager", args[0], args[1]); '
                                  'self.EmitSignal("org.bluez.Manager", "PropertyChanged", "sv", [args[0], args[1]])'),
    ])
    mock.AddProperties(MANAGER_IFACE, {
        'Adapters': dbus.Array([], signature='o'),
    })


@dbus.service.method(BLUEZ_MOCK_IFACE,
                     in_signature='ss', out_signature='s')
def AddAdapter(self, device_name, system_name):
    '''Convenience method to add a Bluetooth adapter

    You have to specify a device name which must be a valid part of an object
    path, e. g. "hci0", and an arbitrary system name (pretty hostname).

    Returns the new object path.
    '''
    path = '/org/bluez/' + device_name
    adapter_properties = {
        'UUIDs': dbus.Array([
            '00001000-0000-1000-8000-00805f9b34fb',
            '00001001-0000-1000-8000-00805f9b34fb',
            '0000112d-0000-1000-8000-00805f9b34fb',
            '00001112-0000-1000-8000-00805f9b34fb',
            '0000111f-0000-1000-8000-00805f9b34fb',
            '0000111e-0000-1000-8000-00805f9b34fb',
            '0000110c-0000-1000-8000-00805f9b34fb',
            '0000110e-0000-1000-8000-00805f9b34fb',
            '0000110a-0000-1000-8000-00805f9b34fb',
            '0000110b-0000-1000-8000-00805f9b34fb',
        ], variant_level=1),
        'Discoverable': dbus.Boolean(False, variant_level=1),
        'Discovering': dbus.Boolean(False, variant_level=1),
        'Pairable': dbus.Boolean(True, variant_level=1),
        'Powered': dbus.Boolean(True, variant_level=1),
        'Address': dbus.String('00:01:02:03:04:05', variant_level=1),
        'Alias': dbus.String(system_name, variant_level=1),
        'Name': dbus.String(system_name, variant_level=1),
        # Reference:
        # http://bluetooth-pentest.narod.ru/software/
        # bluetooth_class_of_device-service_generator.html
        'Class': dbus.UInt32(268, variant_level=1),  # Computer, Laptop
    }

    self.AddObject(path,
                   ADAPTER_IFACE,
                   # Properties
                   adapter_properties,
                   # Methods
                   [
                       ('GetProperties', '', 'a{sv}', 'ret = self.GetAll("org.bluez.Adapter")'),
                       ('SetProperty', 'sv', '', 'self.Set("org.bluez.Adapter", args[0], args[1]); '
                                                 'self.EmitSignal("org.bluez.Adapter", "PropertyChanged",'
                                                 ' "sv", [args[0], args[1]])'),
                   ])

    manager = mockobject.objects['/']
    manager.props[MANAGER_IFACE]['Adapters'] \
        = [dbus.ObjectPath(path, variant_level=1)]
    manager.EmitSignal(OBJECT_MANAGER_IFACE, 'InterfacesAdded',
                       'oa{sa{sv}}', [
                           dbus.ObjectPath(path, variant_level=1),
                           {ADAPTER_IFACE: adapter_properties},
                       ])

    manager.EmitSignal(MANAGER_IFACE, 'AdapterAdded',
                       'o', [dbus.ObjectPath(path, variant_level=1)])
    manager.EmitSignal(MANAGER_IFACE, 'DefaultAdapterChanged',
                       'o', [dbus.ObjectPath(path, variant_level=1)])
    manager.EmitSignal(MANAGER_IFACE, 'PropertyChanged', 'sv', [
        "Adapters",
        dbus.Array([dbus.ObjectPath(path, variant_level=1), ], variant_level=1),
    ])

    return path


@dbus.service.method(ADAPTER_IFACE,
                     in_signature='', out_signature='')
def StartDiscovery(self):
    '''Start discovery
    '''
    adapter = mockobject.objects[self.path]

    adapter.props[ADAPTER_IFACE]['Discovering'] = dbus.Boolean(True,
                                                               variant_level=1)
    adapter.EmitSignal(ADAPTER_IFACE, 'PropertyChanged', 'sv', [
        'Discovering', dbus.Boolean(True, variant_level=1),
    ])


@dbus.service.method(ADAPTER_IFACE,
                     in_signature='', out_signature='')
def StopDiscovery(self):
    '''Stop discovery
    '''
    adapter = mockobject.objects[self.path]

    adapter.props[ADAPTER_IFACE]['Discovering'] = dbus.Boolean(True,
                                                               variant_level=1)
    adapter.EmitSignal(ADAPTER_IFACE, 'PropertyChanged', 'sv', [
        'Discovering', dbus.Boolean(False, variant_level=1),
    ])


@dbus.service.method(MANAGER_IFACE,
                     in_signature='', out_signature='o')
def DefaultAdapter(self):
    '''Retrieve the default adapter
    '''
    default_adapter = None

    for obj in mockobject.objects.keys():
        if obj.startswith('/org/bluez/') and 'dev_' not in obj:
            default_adapter = obj

    if default_adapter:
        return dbus.ObjectPath(default_adapter, variant_level=1)
    else:
        raise dbus.exceptions.DBusException(
            'No such adapter.', name='org.bluez.Error.NoSuchAdapter')


@dbus.service.method(MANAGER_IFACE,
                     in_signature='', out_signature='ao')
def ListAdapters(self):
    '''List all known adapters
    '''
    adapters = []

    for obj in mockobject.objects.keys():
        if obj.startswith('/org/bluez/') and 'dev_' not in obj:
            adapters.append(dbus.ObjectPath(obj, variant_level=1))

    return dbus.Array(adapters, variant_level=1)


@dbus.service.method(ADAPTER_IFACE,
                     in_signature='s', out_signature='o')
def CreateDevice(self, device_address):
    '''Create a new device '''
    device_name = 'dev_' + device_address.replace(':', '_').upper()
    adapter_path = self.path
    path = adapter_path + '/' + device_name

    if path not in mockobject.objects:
        raise dbus.exceptions.DBusException(
            'Could not create device for %s.' % device_address,
            name='org.bluez.Error.Failed')

    adapter = mockobject.objects[self.path]
    adapter.EmitSignal(ADAPTER_IFACE, 'DeviceCreated',
                       'o', [dbus.ObjectPath(path, variant_level=1)])

    return dbus.ObjectPath(path, variant_level=1)


@dbus.service.method(BLUEZ_MOCK_IFACE,
                     in_signature='sss', out_signature='s')
def AddDevice(self, adapter_device_name, device_address, alias):
    '''Convenience method to add a Bluetooth device

    You have to specify a device address which must be a valid Bluetooth
    address (e.g. 'AA:BB:CC:DD:EE:FF'). The alias is the human-readable name
    for the device (e.g. as set on the device itself), and the adapter device
    name is the device_name passed to AddAdapter.

    This will create a new, unpaired and unconnected device.

    Returns the new object path.
    '''
    device_name = 'dev_' + device_address.replace(':', '_').upper()
    adapter_path = '/org/bluez/' + adapter_device_name
    path = adapter_path + '/' + device_name

    if adapter_path not in mockobject.objects:
        raise dbus.exceptions.DBusException(
            'No such adapter.', name='org.bluez.Error.NoSuchAdapter')

    properties = {
        'UUIDs': dbus.Array([], signature='s', variant_level=1),
        'Blocked': dbus.Boolean(False, variant_level=1),
        'Connected': dbus.Boolean(False, variant_level=1),
        'LegacyPairing': dbus.Boolean(False, variant_level=1),
        'Paired': dbus.Boolean(False, variant_level=1),
        'Trusted': dbus.Boolean(False, variant_level=1),
        'RSSI': dbus.Int16(-79, variant_level=1),  # arbitrary
        'Adapter': dbus.ObjectPath(adapter_path, variant_level=1),
        'Address': dbus.String(device_address, variant_level=1),
        'Alias': dbus.String(alias, variant_level=1),
        'Name': dbus.String(alias, variant_level=1),
        'Class': dbus.UInt32(0x240404, variant_level=1),  # Audio, headset.
        'Icon': dbus.String('audio-headset', variant_level=1),
    }

    self.AddObject(path,
                   DEVICE_IFACE,
                   # Properties
                   properties,
                   # Methods
                   [
                       ('GetProperties', '', 'a{sv}', 'ret = self.GetAll("org.bluez.Device")'),
                       ('SetProperty', 'sv', '', 'self.Set("org.bluez.Device", args[0], args[1]); '
                                                 'self.EmitSignal("org.bluez.Device", "PropertyChanged",'
                                                 ' "sv", [args[0], args[1]])'),
                   ])

    manager = mockobject.objects['/']
    manager.EmitSignal(OBJECT_MANAGER_IFACE, 'InterfacesAdded',
                       'oa{sa{sv}}', [
                           dbus.ObjectPath(path, variant_level=1),
                           {DEVICE_IFACE: properties},
                       ])

    adapter = mockobject.objects[adapter_path]
    adapter.EmitSignal(ADAPTER_IFACE, 'DeviceFound',
                       'sa{sv}', [
                           properties['Address'],
                           properties,
                       ])

    return path


@dbus.service.method(ADAPTER_IFACE,
                     in_signature='', out_signature='ao')
def ListDevices(self):
    '''List all known devices
    '''
    devices = []

    for obj in mockobject.objects.keys():
        if obj.startswith('/org/bluez/') and 'dev_' in obj:
            devices.append(dbus.ObjectPath(obj, variant_level=1))

    return dbus.Array(devices, variant_level=1)


@dbus.service.method(ADAPTER_IFACE,
                     in_signature='s', out_signature='o')
def FindDevice(self, address):
    '''Find a specific device by bluetooth address.
    '''
    for obj in mockobject.objects.keys():
        if obj.startswith('/org/bluez/') and 'dev_' in obj:
            o = mockobject.objects[obj]
            if o.props[DEVICE_IFACE]['Address'] \
                    == dbus.String(address, variant_level=1):
                return obj

    raise dbus.exceptions.DBusException('No such device.',
                                        name='org.bluez.Error.NoSuchDevice')


@dbus.service.method(ADAPTER_IFACE,
                     in_signature='sos', out_signature='o')
def CreatePairedDevice(self, device_address, agent, capability):
    '''Convenience method to mark an existing device as paired.
    '''
    device_name = 'dev_' + device_address.replace(':', '_').upper()
    device_path = DefaultAdapter(self) + '/' + device_name

    if device_path not in mockobject.objects:
        raise dbus.exceptions.DBusException('No such device.',
                                            name='org.bluez.Error.NoSuchDevice')

    device = mockobject.objects[device_path]

    # Based off pairing with a Sennheise headset.
    uuids = [
        '00001108-0000-1000-8000-00805f9b34fb',
        '0000110b-0000-1000-8000-00805f9b34fb',
        '0000110e-0000-1000-8000-00805f9b34fb',
        '0000111e-0000-1000-8000-00805f9b34fb',
    ]

    device.props[DEVICE_IFACE]['UUIDs'] = dbus.Array(uuids, variant_level=1)
    device.props[DEVICE_IFACE]['Paired'] = dbus.Boolean(True, variant_level=1)
    device.props[DEVICE_IFACE]['LegacyPairing'] = dbus.Boolean(True,
                                                               variant_level=1)
    device.props[DEVICE_IFACE]['Trusted'] = dbus.Boolean(False,
                                                         variant_level=1)
    device.props[DEVICE_IFACE]['Connected'] = dbus.Boolean(True,
                                                           variant_level=1)

    adapter = mockobject.objects[self.path]
    adapter.EmitSignal(ADAPTER_IFACE, 'DeviceCreated',
                       'o', [dbus.ObjectPath(device_path, variant_level=1)])

    for prop in device.props[DEVICE_IFACE]:
        try:
            device.EmitSignal(DEVICE_IFACE, 'PropertyChanged', 'sv', [
                prop, device.props[prop]
            ])
        except KeyError:
            pass

    return dbus.ObjectPath(device_path, variant_level=1)


@dbus.service.method(DEVICE_IFACE,
                     in_signature='s', out_signature='a{us}')
def DiscoverServices(self, pattern):

    device = mockobject.objects[self.path]

    try:
        device.AddProperties(AUDIO_IFACE,
                             {
                                 'State': dbus.String('disconnected', variant_level=1),
                             })
    except dbus.exceptions.DBusException:
        pass

    device.props[AUDIO_IFACE]['State'] = dbus.String("disconnected",
                                                     variant_level=1)

    device.AddMethods(AUDIO_IFACE, [
        ('GetProperties', '', 'a{sv}', 'ret = self.GetAll("org.bluez.Audio")'),
        ('SetProperty', 'sv', '', 'self.Set("org.bluez.Audio", args[0], args[1]); '
                                  'self.EmitSignal("org.bluez.Audio", "PropertyChanged", "sv", [args[0], args[1]])'),
    ])

    return dbus.Dictionary({0: "dummy", }, variant_level=1)


@dbus.service.method(AUDIO_IFACE,
                     in_signature='', out_signature='')
def Connect(self):
    '''Connect a device '''
    device_path = self.path

    if device_path not in mockobject.objects:
        raise dbus.exceptions.DBusException('No such device.',
                                            name='org.bluez.Error.NoSuchDevice')

    device = mockobject.objects[device_path]

    device.props[AUDIO_IFACE]['State'] = dbus.String("connected",
                                                     variant_level=1)
    device.EmitSignal(AUDIO_IFACE, 'PropertyChanged', 'sv', [
        'State', dbus.String("connected", variant_level=1),
    ])

    device.props[DEVICE_IFACE]['Connected'] = dbus.Boolean(True,
                                                           variant_level=1)
    device.EmitSignal(DEVICE_IFACE, 'PropertyChanged', 'sv', [
        'Connected', dbus.Boolean(True, variant_level=1),
    ])


@dbus.service.method(AUDIO_IFACE,
                     in_signature='', out_signature='')
def Disconnect(self):
    '''Disconnect a device '''
    device_path = self.path

    if device_path not in mockobject.objects:
        raise dbus.exceptions.DBusException('No such device.',
                                            name='org.bluez.Error.NoSuchDevice')

    device = mockobject.objects[device_path]

    try:
        device.props[AUDIO_IFACE]['State'] = dbus.String("disconnected",
                                                         variant_level=1)

        device.EmitSignal(AUDIO_IFACE, 'PropertyChanged', 'sv', [
            'State', dbus.String("disconnected", variant_level=1),
        ])
    except KeyError:
        pass

    device.props[DEVICE_IFACE]['Connected'] = dbus.Boolean(False,
                                                           variant_level=1)
    device.EmitSignal(DEVICE_IFACE, 'PropertyChanged', 'sv', [
        'Connected', dbus.Boolean(False, variant_level=1),
    ])


@dbus.service.method(ADAPTER_IFACE,
                     in_signature='o', out_signature='')
def RemoveDevice(self, object_path):
    '''Remove (forget) a device '''

    adapter = mockobject.objects[self.path]
    adapter.EmitSignal(ADAPTER_IFACE, 'DeviceRemoved',
                       'o', [object_path])
