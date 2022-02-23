# -*- coding: utf-8 -*-

'''bluetoothd mock template

This creates the expected methods and properties of the object manager
org.bluez object (/), the manager object (/org/bluez), but no adapters or
devices.

This supports BlueZ 5 only.
'''

# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 3 of the License, or (at your option) any
# later version.  See http://www.gnu.org/copyleft/lgpl.html for the full text
# of the license.

__author__ = 'Philip Withnall'
__copyright__ = '(c) 2013 Collabora Ltd.'

import os
import dbus

from dbusmock import OBJECT_MANAGER_IFACE, mockobject

BUS_NAME = 'org.bluez'
MAIN_OBJ = '/'
SYSTEM_BUS = True
IS_OBJECT_MANAGER = True

BLUEZ_MOCK_IFACE = 'org.bluez.Mock'
AGENT_MANAGER_IFACE = 'org.bluez.AgentManager1'
PROFILE_MANAGER_IFACE = 'org.bluez.ProfileManager1'
ADAPTER_IFACE = 'org.bluez.Adapter1'
MEDIA_IFACE = 'org.bluez.Media1'
NETWORK_SERVER_IFACE = 'org.bluez.Network1'
DEVICE_IFACE = 'org.bluez.Device1'


@dbus.service.method(AGENT_MANAGER_IFACE,
                     in_signature='os', out_signature='')
def RegisterAgent(manager, agent_path, capability):
    all_caps = ['DisplayOnly', 'DisplayYesNo', 'KeyboardOnly',
                'NoInputNoOutput', 'KeyboardDisplay']

    if agent_path in manager.agent_paths:
        raise dbus.exceptions.DBusException(
            'Another agent is already registered ' + manager.agent_path,
            name='org.bluez.Error.AlreadyExists')

    if capability not in all_caps:
        raise dbus.exceptions.DBusException(
            'Unsupported capability ' + capability,
            name='org.bluez.Error.InvalidArguments')

    if not manager.default_agent:
        manager.default_agent = agent_path
    manager.agent_paths += [agent_path]
    manager.capabilities[str(agent_path)] = capability


@dbus.service.method(AGENT_MANAGER_IFACE,
                     in_signature='o', out_signature='')
def UnregisterAgent(manager, agent_path):
    if agent_path not in manager.agent_paths:
        raise dbus.exceptions.DBusException(
            'Agent not registered ' + agent_path,
            name='org.bluez.Error.DoesNotExist')

    manager.agent_paths.remove(agent_path)
    del manager.capabilities[agent_path]
    if manager.default_agent == agent_path:
        if len(manager.agent_paths) > 0:
            manager.default_agent = manager.agent_paths[-1]
        else:
            manager.default_agent = None


@dbus.service.method(AGENT_MANAGER_IFACE,
                     in_signature='o', out_signature='')
def RequestDefaultAgent(manager, agent_path):
    if agent_path not in manager.agent_paths:
        raise dbus.exceptions.DBusException(
            'Agent not registered ' + agent_path,
            name='org.bluez.Error.DoesNotExist')
    manager.default_agent = agent_path


def load(mock, _parameters):
    mock.AddObject('/org/bluez', AGENT_MANAGER_IFACE, {}, [
        ('RegisterAgent', 'os', '', RegisterAgent),
        ('RequestDefaultAgent', 'o', '', RequestDefaultAgent),
        ('UnregisterAgent', 'o', '', UnregisterAgent),
    ])

    bluez = mockobject.objects['/org/bluez']
    bluez.AddMethods(PROFILE_MANAGER_IFACE, [
        ('RegisterProfile', 'osa{sv}', '', ''),
        ('UnregisterProfile', 'o', '', ''),
    ])
    bluez.agent_paths = []
    bluez.capabilities = {}
    bluez.default_agent = None


@dbus.service.method(ADAPTER_IFACE,
                     in_signature='o', out_signature='')
def RemoveDevice(adapter, path):
    adapter.RemoveObject(path)

    manager = mockobject.objects['/']
    manager.EmitSignal(OBJECT_MANAGER_IFACE, 'InterfacesRemoved',
                       'oas', [
                           dbus.ObjectPath(path),
                           [DEVICE_IFACE],
                       ])


@dbus.service.method(ADAPTER_IFACE,
                     in_signature='', out_signature='')
def StartDiscovery(adapter):
    adapter.props[ADAPTER_IFACE]['Discovering'] = True
    # NOTE: discovery filter support is minimal to mock
    # the Discoverable discovery filter
    if adapter.props[ADAPTER_IFACE]['DiscoveryFilter'] is not None:
        adapter.props[ADAPTER_IFACE]['Discoverable'] = True
    adapter.EmitSignal(dbus.PROPERTIES_IFACE, 'PropertiesChanged', 'sa{sv}as', [
        ADAPTER_IFACE,
        {
            'Discoverable': dbus.Boolean(adapter.props[ADAPTER_IFACE]['Discoverable'], variant_level=1),
            'Discovering': dbus.Boolean(adapter.props[ADAPTER_IFACE]['Discovering'], variant_level=1),
        },
        [],
    ])


@dbus.service.method(ADAPTER_IFACE,
                     in_signature='', out_signature='')
def StopDiscovery(adapter):
    adapter.props[ADAPTER_IFACE]['Discovering'] = False
    # NOTE: discovery filter support is minimal to mock
    # the Discoverable discovery filter
    if adapter.props[ADAPTER_IFACE]['DiscoveryFilter'] is not None:
        adapter.props[ADAPTER_IFACE]['Discoverable'] = False
    adapter.EmitSignal(dbus.PROPERTIES_IFACE, 'PropertiesChanged', 'sa{sv}as', [
        ADAPTER_IFACE,
        {
            'Discoverable': dbus.Boolean(adapter.props[ADAPTER_IFACE]['Discoverable'], variant_level=1),
            'Discovering': dbus.Boolean(adapter.props[ADAPTER_IFACE]['Discovering'], variant_level=1),
        },
        [],
    ])


@dbus.service.method(ADAPTER_IFACE,
                     in_signature='a{sv}', out_signature='')
def SetDiscoveryFilter(adapter, discovery_filter):
    adapter.props[ADAPTER_IFACE]['DiscoveryFilter'] = discovery_filter


@dbus.service.method(BLUEZ_MOCK_IFACE,
                     in_signature='ss', out_signature='s')
def AddAdapter(self, device_name, system_name):
    '''Convenience method to add a Bluetooth adapter

    You have to specify a device name which must be a valid part of an object
    path, e. g. "hci0", and an arbitrary system name (pretty hostname).

    Returns the new object path.
    '''
    path = '/org/bluez/' + device_name
    address_start = int(device_name[-1])
    address = f"{address_start:02d}:{address_start+1:02d}:{address_start+2:02d}:" + \
        f"{address_start+3:02d}:{address_start+4:02d}:{address_start+5:02d}"
    adapter_properties = {
        'UUIDs': dbus.Array([
            # Reference:
            # http://git.kernel.org/cgit/bluetooth/bluez.git/tree/lib/uuid.h
            # PNP
            '00001200-0000-1000-8000-00805f9b34fb',
            # Generic Access Profile
            '00001800-0000-1000-8000-00805f9b34fb',
            # Generic Attribute Profile
            '00001801-0000-1000-8000-00805f9b34fb',
            # Audio/Video Remote Control Profile (remote)
            '0000110e-0000-1000-8000-00805f9b34fb',
            # Audio/Video Remote Control Profile (target)
            '0000110c-0000-1000-8000-00805f9b34fb',
        ], variant_level=1),
        'Discoverable': dbus.Boolean(False, variant_level=1),
        'Discovering': dbus.Boolean(False, variant_level=1),
        'Pairable': dbus.Boolean(True, variant_level=1),
        'Powered': dbus.Boolean(True, variant_level=1),
        'Address': dbus.String(address, variant_level=1),
        'AddressType': dbus.String('public', variant_level=1),
        'Alias': dbus.String(system_name, variant_level=1),
        'Modalias': dbus.String('usb:v1D6Bp0245d050A', variant_level=1),
        'Name': dbus.String(system_name, variant_level=1),
        # Reference:
        # http://bluetooth-pentest.narod.ru/software/
        # bluetooth_class_of_device-service_generator.html
        'Class': dbus.UInt32(268, variant_level=1),  # Computer, Laptop
        'DiscoverableTimeout': dbus.UInt32(180, variant_level=1),
        'PairableTimeout': dbus.UInt32(0, variant_level=1),
    }

    self.AddObject(path,
                   ADAPTER_IFACE,
                   # Properties
                   adapter_properties,
                   # Methods
                   [
                       ('RemoveDevice', 'o', '', RemoveDevice),
                       ('StartDiscovery', '', '', StartDiscovery),
                       ('StopDiscovery', '', '', StopDiscovery),
                       ('SetDiscoveryFilter', 'a{sv}', '', SetDiscoveryFilter),
                   ])

    adapter = mockobject.objects[path]
    adapter.AddMethods(MEDIA_IFACE, [
        ('RegisterEndpoint', 'oa{sv}', '', ''),
        ('UnregisterEndpoint', 'o', '', ''),
    ])
    adapter.AddMethods(NETWORK_SERVER_IFACE, [
        ('Register', 'ss', '', ''),
        ('Unregister', 's', '', ''),
    ])

    manager = mockobject.objects['/']
    manager.EmitSignal(OBJECT_MANAGER_IFACE, 'InterfacesAdded',
                       'oa{sa{sv}}', [
                           dbus.ObjectPath(path),
                           {ADAPTER_IFACE: adapter_properties},
                       ])

    return path


@dbus.service.method(BLUEZ_MOCK_IFACE,
                     in_signature='s')
def RemoveAdapter(self, device_name):
    '''Convenience method to remove a Bluetooth adapter
    '''
    path = '/org/bluez/' + device_name
    # We could remove the devices related to the adapters here, but
    # when bluez crashes, the InterfacesRemoved aren't necessarily sent
    # devices first, so in effect, our laziness is testing an edge case
    # in the clients
    self.RemoveObject(path)

    manager = mockobject.objects['/']
    manager.EmitSignal(OBJECT_MANAGER_IFACE, 'InterfacesRemoved',
                       'oas', [
                           dbus.ObjectPath(path),
                           [ADAPTER_IFACE],
                       ])


@dbus.service.method(BLUEZ_MOCK_IFACE,
                     in_signature='s')
def RemoveAdapterWithDevices(self, device_name):
    '''Convenience method to remove a Bluetooth adapter and all
       the devices associated to it
    '''
    adapter_path = '/org/bluez/' + device_name
    adapter = mockobject.objects[adapter_path]
    manager = mockobject.objects['/']

    to_remove = []
    for path in mockobject.objects:
        if path.startswith(adapter_path + '/'):
            to_remove.append(path)

    for path in to_remove:
        adapter.RemoveObject(path)
        manager.EmitSignal(OBJECT_MANAGER_IFACE, 'InterfacesRemoved',
                           'oas', [
                               dbus.ObjectPath(path),
                               [DEVICE_IFACE],
                           ])

    self.RemoveObject(adapter_path)
    manager.EmitSignal(OBJECT_MANAGER_IFACE, 'InterfacesRemoved',
                       'oas', [
                           dbus.ObjectPath(adapter_path),
                           [ADAPTER_IFACE],
                       ])


@dbus.service.method(DEVICE_IFACE,
                     in_signature='', out_signature='')
def Pair(device):
    if device.paired:
        raise dbus.exceptions.DBusException(
            'Device already paired',
            name='org.bluez.Error.AlreadyExists')
    device_address = device.props[DEVICE_IFACE]['Address']
    adapter_device_name = os.path.basename(device.props[DEVICE_IFACE]['Adapter'])
    device.PairDevice(adapter_device_name, device_address)


@dbus.service.method(DEVICE_IFACE,
                     in_signature='', out_signature='')
def Connect(device):
    if device.connected:
        raise dbus.exceptions.DBusException(
            'Already Connected',
            name='org.bluez.Error.AlreadyConnected')
    device.connected = True
    device.EmitSignal(dbus.PROPERTIES_IFACE, 'PropertiesChanged', 'sa{sv}as', [
        DEVICE_IFACE,
        {
            'Connected': dbus.Boolean(device.connected, variant_level=1),
        },
        [],
    ])


@dbus.service.method(DEVICE_IFACE,
                     in_signature='', out_signature='')
def Disconnect(device):
    if not device.connected:
        raise dbus.exceptions.DBusException(
            'Not Connected',
            name='org.bluez.Error.NotConnected')
    device.connected = False
    device.EmitSignal(dbus.PROPERTIES_IFACE, 'PropertiesChanged', 'sa{sv}as', [
        DEVICE_IFACE,
        {
            'Connected': dbus.Boolean(device.connected, variant_level=1),
        },
        [],
    ])


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
            f'Adapter {adapter_device_name} does not exist.',
            name=BLUEZ_MOCK_IFACE + '.NoSuchAdapter')

    properties = {
        'Address': dbus.String(device_address, variant_level=1),
        'AddressType': dbus.String('public', variant_level=1),
        'Name': dbus.String(alias, variant_level=1),
        'Icon': dbus.String('', variant_level=1),
        'Class': dbus.UInt32(0, variant_level=1),
        'Appearance': dbus.UInt16(0, variant_level=1),
        'UUIDs': dbus.Array([], signature='s', variant_level=1),
        'Paired': dbus.Boolean(False, variant_level=1),
        'Connected': dbus.Boolean(False, variant_level=1),
        'Trusted': dbus.Boolean(False, variant_level=1),
        'Blocked': dbus.Boolean(False, variant_level=1),
        'WakeAllowed': dbus.Boolean(False, variant_level=1),
        'Alias': dbus.String(alias, variant_level=1),
        'Adapter': dbus.ObjectPath(adapter_path, variant_level=1),
        'LegacyPairing': dbus.Boolean(False, variant_level=1),
        'Modalias': dbus.String('', variant_level=1),
        'RSSI': dbus.Int16(-79, variant_level=1),  # arbitrary
        'TxPower': dbus.Int16(0, variant_level=1),
        'ManufacturerData': dbus.Array([], signature='a{qv}', variant_level=1),
        'ServiceData': dbus.Array([], signature='a{sv}', variant_level=1),
        'ServicesResolved': dbus.Boolean(False, variant_level=1),
        'AdvertisingFlags': dbus.Array([], signature='ay', variant_level=1),
        'AdvertisingData': dbus.Array([], signature='a{yv}', variant_level=1),
    }

    self.AddObject(path,
                   DEVICE_IFACE,
                   # Properties
                   properties,
                   # Methods
                   [
                       ('CancelPairing', '', '', ''),
                       ('Connect', '', '', Connect),
                       ('ConnectProfile', 's', '', ''),
                       ('Disconnect', '', '', Disconnect),
                       ('DisconnectProfile', 's', '', ''),
                       ('Pair', '', '', Pair),
                   ])
    device = mockobject.objects[path]
    device.paired = False
    device.connected = False

    manager = mockobject.objects['/']
    manager.EmitSignal(OBJECT_MANAGER_IFACE, 'InterfacesAdded',
                       'oa{sa{sv}}', [
                           dbus.ObjectPath(path),
                           {DEVICE_IFACE: properties},
                       ])

    return path


@dbus.service.method(BLUEZ_MOCK_IFACE,
                     in_signature='ssi', out_signature='')
def PairDevice(_self, adapter_device_name, device_address, class_=5898764):
    '''Convenience method to mark an existing device as paired.

    You have to specify a device address which must be a valid Bluetooth
    address (e.g. 'AA:BB:CC:DD:EE:FF'). The adapter device name is the
    device_name passed to AddAdapter.

    This unblocks the device if it was blocked.

    If the specified adapter or device don’t exist, a NoSuchAdapter or
    NoSuchDevice error will be returned on the bus.

    Returns nothing.
    '''
    device_name = 'dev_' + device_address.replace(':', '_').upper()
    adapter_path = '/org/bluez/' + adapter_device_name
    device_path = adapter_path + '/' + device_name

    if adapter_path not in mockobject.objects:
        raise dbus.exceptions.DBusException(
            f'Adapter {adapter_device_name} does not exist.',
            name=BLUEZ_MOCK_IFACE + '.NoSuchAdapter')
    if device_path not in mockobject.objects:
        raise dbus.exceptions.DBusException(f'Device {device_name} does not exist.', name=BLUEZ_MOCK_IFACE + '.NoSuchDevice')

    device = mockobject.objects[device_path]
    device.paired = True

    # Based off pairing with an Android phone.
    uuids = [
        '00001105-0000-1000-8000-00805f9b34fb',
        '0000110a-0000-1000-8000-00805f9b34fb',
        '0000110c-0000-1000-8000-00805f9b34fb',
        '00001112-0000-1000-8000-00805f9b34fb',
        '00001115-0000-1000-8000-00805f9b34fb',
        '00001116-0000-1000-8000-00805f9b34fb',
        '0000111f-0000-1000-8000-00805f9b34fb',
        '0000112f-0000-1000-8000-00805f9b34fb',
        '00001200-0000-1000-8000-00805f9b34fb',
    ]

    device.props[DEVICE_IFACE]['UUIDs'] = dbus.Array(uuids, variant_level=1)
    device.props[DEVICE_IFACE]['Paired'] = dbus.Boolean(True, variant_level=1)
    device.props[DEVICE_IFACE]['LegacyPairing'] = dbus.Boolean(True,
                                                               variant_level=1)
    device.props[DEVICE_IFACE]['Blocked'] = dbus.Boolean(False,
                                                         variant_level=1)

    try:
        device.props[DEVICE_IFACE]['Modalias']
    except KeyError:
        device.AddProperties(DEVICE_IFACE, {
            'Modalias': dbus.String('bluetooth:v000Fp1200d1436',
                                    variant_level=1),
            'Class': dbus.UInt32(class_, variant_level=1),
            'Icon': dbus.String('phone', variant_level=1),
        })

    device.EmitSignal(dbus.PROPERTIES_IFACE, 'PropertiesChanged', 'sa{sv}as', [
        DEVICE_IFACE,
        {
            'UUIDs': dbus.Array(uuids, variant_level=1),
            'Paired': dbus.Boolean(True, variant_level=1),
            'LegacyPairing': dbus.Boolean(True, variant_level=1),
            'Blocked': dbus.Boolean(False, variant_level=1),
            'Modalias': dbus.String('bluetooth:v000Fp1200d1436',
                                    variant_level=1),
            'Class': dbus.UInt32(class_, variant_level=1),
            'Icon': dbus.String('phone', variant_level=1),
        },
        [],
    ])


@dbus.service.method(BLUEZ_MOCK_IFACE,
                     in_signature='ss', out_signature='')
def BlockDevice(_self, adapter_device_name, device_address):
    '''Convenience method to mark an existing device as blocked.

    You have to specify a device address which must be a valid Bluetooth
    address (e.g. 'AA:BB:CC:DD:EE:FF'). The adapter device name is the
    device_name passed to AddAdapter.

    This disconnects the device if it was connected.

    If the specified adapter or device don’t exist, a NoSuchAdapter or
    NoSuchDevice error will be returned on the bus.

    Returns nothing.
    '''
    device_name = 'dev_' + device_address.replace(':', '_').upper()
    adapter_path = '/org/bluez/' + adapter_device_name
    device_path = adapter_path + '/' + device_name

    if adapter_path not in mockobject.objects:
        raise dbus.exceptions.DBusException(
            f'Adapter {adapter_device_name} does not exist.',
            name=BLUEZ_MOCK_IFACE + '.NoSuchAdapter')
    if device_path not in mockobject.objects:
        raise dbus.exceptions.DBusException(f'Device {device_name} does not exist.', name=BLUEZ_MOCK_IFACE + '.NoSuchDevice')

    device = mockobject.objects[device_path]

    device.props[DEVICE_IFACE]['Blocked'] = dbus.Boolean(True, variant_level=1)
    device.props[DEVICE_IFACE]['Connected'] = dbus.Boolean(False,
                                                           variant_level=1)

    device.EmitSignal(dbus.PROPERTIES_IFACE, 'PropertiesChanged', 'sa{sv}as', [
        DEVICE_IFACE,
        {
            'Blocked': dbus.Boolean(True, variant_level=1),
            'Connected': dbus.Boolean(False, variant_level=1),
        },
        [],
    ])


@dbus.service.method(BLUEZ_MOCK_IFACE,
                     in_signature='ss', out_signature='')
def ConnectDevice(_self, adapter_device_name, device_address):
    '''Convenience method to mark an existing device as connected.

    You have to specify a device address which must be a valid Bluetooth
    address (e.g. 'AA:BB:CC:DD:EE:FF'). The adapter device name is the
    device_name passed to AddAdapter.

    This unblocks the device if it was blocked.

    If the specified adapter or device don’t exist, a NoSuchAdapter or
    NoSuchDevice error will be returned on the bus.

    Returns nothing.
    '''
    device_name = 'dev_' + device_address.replace(':', '_').upper()
    adapter_path = '/org/bluez/' + adapter_device_name
    device_path = adapter_path + '/' + device_name

    if adapter_path not in mockobject.objects:
        raise dbus.exceptions.DBusException(
            f'Adapter {adapter_device_name} does not exist.',
            name=BLUEZ_MOCK_IFACE + '.NoSuchAdapter')
    if device_path not in mockobject.objects:
        raise dbus.exceptions.DBusException(
            f'Device {device_name} does not exist.',
            name=BLUEZ_MOCK_IFACE + '.NoSuchDevice')

    device = mockobject.objects[device_path]

    device.props[DEVICE_IFACE]['Blocked'] = dbus.Boolean(False,
                                                         variant_level=1)
    device.props[DEVICE_IFACE]['Connected'] = dbus.Boolean(True,
                                                           variant_level=1)

    device.EmitSignal(dbus.PROPERTIES_IFACE, 'PropertiesChanged', 'sa{sv}as', [
        DEVICE_IFACE,
        {
            'Blocked': dbus.Boolean(False, variant_level=1),
            'Connected': dbus.Boolean(True, variant_level=1),
        },
        [],
    ])


@dbus.service.method(BLUEZ_MOCK_IFACE,
                     in_signature='ss', out_signature='')
def DisconnectDevice(_self, adapter_device_name, device_address):
    '''Convenience method to mark an existing device as disconnected.

    You have to specify a device address which must be a valid Bluetooth
    address (e.g. 'AA:BB:CC:DD:EE:FF'). The adapter device name is the
    device_name passed to AddAdapter.

    This does not change the device’s blocked status.

    If the specified adapter or device don’t exist, a NoSuchAdapter or
    NoSuchDevice error will be returned on the bus.

    Returns nothing.
    '''
    device_name = 'dev_' + device_address.replace(':', '_').upper()
    adapter_path = '/org/bluez/' + adapter_device_name
    device_path = adapter_path + '/' + device_name

    if adapter_path not in mockobject.objects:
        raise dbus.exceptions.DBusException(
            f'Adapter {adapter_device_name} does not exist.',
            name=BLUEZ_MOCK_IFACE + '.NoSuchAdapter')
    if device_path not in mockobject.objects:
        raise dbus.exceptions.DBusException(
            f'Device {device_name} does not exist.',
            name=BLUEZ_MOCK_IFACE + '.NoSuchDevice')

    device = mockobject.objects[device_path]

    device.props[DEVICE_IFACE]['Connected'] = dbus.Boolean(False,
                                                           variant_level=1)

    device.EmitSignal(dbus.PROPERTIES_IFACE, 'PropertiesChanged', 'sa{sv}as', [
        DEVICE_IFACE,
        {
            'Connected': dbus.Boolean(False, variant_level=1),
        },
        [],
    ])
