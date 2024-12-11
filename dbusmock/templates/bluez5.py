"""bluetoothd mock template

This creates the expected methods and properties of the object manager
org.bluez object (/), the manager object (/org/bluez), but no adapters or
devices.

This supports BlueZ 5 only.
"""

# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 3 of the License, or (at your option) any
# later version.  See http://www.gnu.org/copyleft/lgpl.html for the full text
# of the license.

__author__ = "Philip Withnall"
__copyright__ = """
(c) 2013 Collabora Ltd.
(c) 2017 - 2022 Martin Pitt <martin@piware.de>
"""

from pathlib import Path

import dbus

from dbusmock import OBJECT_MANAGER_IFACE, mockobject

BUS_NAME = "org.bluez"
MAIN_OBJ = "/"
SYSTEM_BUS = True
IS_OBJECT_MANAGER = True

BLUEZ_MOCK_IFACE = "org.bluez.Mock"
AGENT_MANAGER_IFACE = "org.bluez.AgentManager1"
PROFILE_MANAGER_IFACE = "org.bluez.ProfileManager1"
ADAPTER_IFACE = "org.bluez.Adapter1"
MEDIA_IFACE = "org.bluez.Media1"
NETWORK_SERVER_IFACE = "org.bluez.Network1"
DEVICE_IFACE = "org.bluez.Device1"

LE_ADVERTISING_MANAGER_IFACE = "org.bluez.LEAdvertisingManager1"
LE_ADVERTISEMENT_IFACE = "org.bluez.LEAdvertisement1"
ADVERTISEMENT_MONITOR_MANAGER_IFACE = "org.bluez.AdvertisementMonitorManager1"
ADVERTISEMENT_MONITOR_IFACE = "org.bluez.AdvertisementMonitor1"

# The device class of some arbitrary Android phone.
MOCK_PHONE_CLASS = 5898764

# Maximum number of BLE advertisements supported per adapter.
MAX_ADVERTISEMENT_INSTANCES = 5


@dbus.service.method(AGENT_MANAGER_IFACE, in_signature="os", out_signature="")
def RegisterAgent(manager, agent_path, capability):
    all_caps = ["DisplayOnly", "DisplayYesNo", "KeyboardOnly", "NoInputNoOutput", "KeyboardDisplay"]

    if agent_path in manager.agent_paths:
        raise dbus.exceptions.DBusException(
            "Another agent is already registered " + agent_path, name="org.bluez.Error.AlreadyExists"
        )

    # Fallback to "KeyboardDisplay" as per BlueZ spec
    if not capability:
        capability = "KeyboardDisplay"

    if capability not in all_caps:
        raise dbus.exceptions.DBusException(
            "Unsupported capability " + capability, name="org.bluez.Error.InvalidArguments"
        )

    if not manager.default_agent:
        manager.default_agent = agent_path
    manager.agent_paths += [agent_path]
    manager.capabilities[str(agent_path)] = capability


@dbus.service.method(AGENT_MANAGER_IFACE, in_signature="o", out_signature="")
def UnregisterAgent(manager, agent_path):
    if agent_path not in manager.agent_paths:
        raise dbus.exceptions.DBusException("Agent not registered " + agent_path, name="org.bluez.Error.DoesNotExist")

    manager.agent_paths.remove(agent_path)
    del manager.capabilities[agent_path]
    if manager.default_agent == agent_path:
        if len(manager.agent_paths) > 0:
            manager.default_agent = manager.agent_paths[-1]
        else:
            manager.default_agent = None


@dbus.service.method(AGENT_MANAGER_IFACE, in_signature="o", out_signature="")
def RequestDefaultAgent(manager, agent_path):
    if agent_path not in manager.agent_paths:
        raise dbus.exceptions.DBusException("Agent not registered " + agent_path, name="org.bluez.Error.DoesNotExist")
    manager.default_agent = agent_path


def load(mock, parameters):
    mock.AddObject(
        "/org/bluez",
        AGENT_MANAGER_IFACE,
        {},
        [
            ("RegisterAgent", "os", "", RegisterAgent),
            ("RequestDefaultAgent", "o", "", RequestDefaultAgent),
            ("UnregisterAgent", "o", "", UnregisterAgent),
        ],
    )

    bluez = mockobject.objects["/org/bluez"]
    bluez.AddMethods(
        PROFILE_MANAGER_IFACE,
        [
            ("RegisterProfile", "osa{sv}", "", ""),
            ("UnregisterProfile", "o", "", ""),
        ],
    )
    bluez.agent_paths = []
    bluez.capabilities = {}
    bluez.default_agent = None

    # whether to expose the LEAdvertisingManager1 interface on adapters (BLE advertising)
    bluez.enable_advertise_api = parameters.get("enable_advertise_api", True)
    # whether to expose the AdvertisementMonitorManager1 interface on adapters (Passive scanning)
    bluez.enable_monitor_api = parameters.get("enable_monitor_api", True)


@dbus.service.method(ADAPTER_IFACE, in_signature="o", out_signature="")
def RemoveDevice(adapter, path):
    adapter.RemoveObject(path)

    manager = mockobject.objects["/"]
    manager.EmitSignal(
        OBJECT_MANAGER_IFACE,
        "InterfacesRemoved",
        "oas",
        [
            dbus.ObjectPath(path),
            [DEVICE_IFACE],
        ],
    )


@dbus.service.method(ADAPTER_IFACE, in_signature="", out_signature="")
def StartDiscovery(adapter):
    adapter.props[ADAPTER_IFACE]["Discovering"] = True
    # NOTE: discovery filter support is minimal to mock
    # the Discoverable discovery filter
    if adapter.props[ADAPTER_IFACE]["DiscoveryFilter"] is not None:
        adapter.props[ADAPTER_IFACE]["Discoverable"] = True
    adapter.EmitSignal(
        dbus.PROPERTIES_IFACE,
        "PropertiesChanged",
        "sa{sv}as",
        [
            ADAPTER_IFACE,
            {
                "Discoverable": dbus.Boolean(adapter.props[ADAPTER_IFACE]["Discoverable"]),
                "Discovering": dbus.Boolean(adapter.props[ADAPTER_IFACE]["Discovering"]),
            },
            [],
        ],
    )


@dbus.service.method(ADAPTER_IFACE, in_signature="", out_signature="")
def StopDiscovery(adapter):
    adapter.props[ADAPTER_IFACE]["Discovering"] = False
    # NOTE: discovery filter support is minimal to mock
    # the Discoverable discovery filter
    if adapter.props[ADAPTER_IFACE]["DiscoveryFilter"] is not None:
        adapter.props[ADAPTER_IFACE]["Discoverable"] = False
    adapter.EmitSignal(
        dbus.PROPERTIES_IFACE,
        "PropertiesChanged",
        "sa{sv}as",
        [
            ADAPTER_IFACE,
            {
                "Discoverable": dbus.Boolean(adapter.props[ADAPTER_IFACE]["Discoverable"]),
                "Discovering": dbus.Boolean(adapter.props[ADAPTER_IFACE]["Discovering"]),
            },
            [],
        ],
    )


@dbus.service.method(ADAPTER_IFACE, in_signature="a{sv}", out_signature="")
def SetDiscoveryFilter(adapter, discovery_filter):
    adapter.props[ADAPTER_IFACE]["DiscoveryFilter"] = discovery_filter


@dbus.service.method(BLUEZ_MOCK_IFACE, in_signature="ss", out_signature="s")
def AddAdapter(self, device_name, system_name):
    """Convenience method to add a Bluetooth adapter

    You have to specify a device name which must be a valid part of an object
    path, e. g. "hci0", and an arbitrary system name (pretty hostname).

    Returns the new object path.
    """
    path = "/org/bluez/" + device_name
    address_start = int(device_name[-1])
    address = (
        f"{address_start:02d}:{address_start + 1:02d}:{address_start + 2:02d}:"
        f"{address_start + 3:02d}:{address_start + 4:02d}:{address_start + 5:02d}"
    )
    adapter_properties = {
        "UUIDs": dbus.Array(
            [
                # Reference:
                # http://git.kernel.org/cgit/bluetooth/bluez.git/tree/lib/uuid.h
                # PNP
                "00001200-0000-1000-8000-00805f9b34fb",
                # Generic Access Profile
                "00001800-0000-1000-8000-00805f9b34fb",
                # Generic Attribute Profile
                "00001801-0000-1000-8000-00805f9b34fb",
                # Audio/Video Remote Control Profile (remote)
                "0000110e-0000-1000-8000-00805f9b34fb",
                # Audio/Video Remote Control Profile (target)
                "0000110c-0000-1000-8000-00805f9b34fb",
            ],
        ),
        "Discoverable": dbus.Boolean(False),
        "Discovering": dbus.Boolean(False),
        "Pairable": dbus.Boolean(True),
        "Powered": dbus.Boolean(True),
        "Address": dbus.String(address),
        "AddressType": dbus.String("public"),
        "Alias": dbus.String(system_name),
        "Modalias": dbus.String("usb:v1D6Bp0245d050A"),
        "Name": dbus.String(system_name),
        # Reference:
        # http://bluetooth-pentest.narod.ru/software/
        # bluetooth_class_of_device-service_generator.html
        "Class": dbus.UInt32(268),  # Computer, Laptop
        "DiscoverableTimeout": dbus.UInt32(180),
        "PairableTimeout": dbus.UInt32(0),
        "Roles": dbus.Array(["central", "peripheral"]),
    }

    self.AddObject(
        path,
        ADAPTER_IFACE,
        # Properties
        adapter_properties,
        # Methods
        [
            ("RemoveDevice", "o", "", RemoveDevice),
            ("StartDiscovery", "", "", StartDiscovery),
            ("StopDiscovery", "", "", StopDiscovery),
            ("SetDiscoveryFilter", "a{sv}", "", SetDiscoveryFilter),
        ],
    )

    adapter = mockobject.objects[path]
    adapter.AddMethods(
        MEDIA_IFACE,
        [
            ("RegisterEndpoint", "oa{sv}", "", ""),
            ("UnregisterEndpoint", "o", "", ""),
        ],
    )
    adapter.AddMethods(
        NETWORK_SERVER_IFACE,
        [
            ("Register", "ss", "", ""),
            ("Unregister", "s", "", ""),
        ],
    )

    bluez = mockobject.objects["/org/bluez"]

    # Advertising Manager
    if bluez.enable_advertise_api:
        # Example values below from an Intel AX200 adapter
        advertising_manager_properties = {
            "ActiveInstances": dbus.Byte(0),
            "SupportedInstances": dbus.Byte(MAX_ADVERTISEMENT_INSTANCES),
            "SupportedIncludes": dbus.Array(["tx-power", "appearance", "local-name", "rssi"]),
            "SupportedSecondaryChannels": dbus.Array(["1M", "2M", "Coded"]),
            "SupportedCapabilities": dbus.Dictionary(
                {
                    "MaxAdvLen": dbus.Byte(251),
                    "MaxScnRspLen": dbus.Byte(251),
                    "MinTxPower": dbus.Int16(-34),
                    "MaxTxPower": dbus.Int16(7),
                },
                signature="sv",
            ),
            "SupportedFeatures": dbus.Array(
                [
                    "CanSetTxPower",
                    "HardwareOffload",
                ],
            ),
        }
        adapter.AddProperties(LE_ADVERTISING_MANAGER_IFACE, advertising_manager_properties)
        adapter.AddMethods(
            LE_ADVERTISING_MANAGER_IFACE,
            [
                ("RegisterAdvertisement", "oa{sv}", "", RegisterAdvertisement),
                ("UnregisterAdvertisement", "o", "", UnregisterAdvertisement),
            ],
        )

        # Track advertisements per adapter
        adapter.advertisements = []

    # Advertisement Monitor Manager
    if bluez.enable_monitor_api:
        advertisement_monitor_manager_properties = {
            "SupportedMonitorTypes": dbus.Array(["or_patterns"]),
        }
        adapter.AddProperties(ADVERTISEMENT_MONITOR_MANAGER_IFACE, advertisement_monitor_manager_properties)
        adapter.AddMethods(
            ADVERTISEMENT_MONITOR_MANAGER_IFACE,
            [
                ("RegisterMonitor", "o", "", RegisterMonitor),
                ("UnregisterMonitor", "o", "", UnregisterMonitor),
            ],
        )

        # Track advertisement monitors per adapter
        adapter.monitors = []

    manager = mockobject.objects["/"]
    manager.EmitSignal(
        OBJECT_MANAGER_IFACE,
        "InterfacesAdded",
        "oa{sa{sv}}",
        [
            dbus.ObjectPath(path),
            {ADAPTER_IFACE: adapter_properties},
        ],
    )

    return path


@dbus.service.method(BLUEZ_MOCK_IFACE, in_signature="s")
def RemoveAdapter(self, device_name):
    """Convenience method to remove a Bluetooth adapter"""
    path = "/org/bluez/" + device_name
    # We could remove the devices related to the adapters here, but
    # when bluez crashes, the InterfacesRemoved aren't necessarily sent
    # devices first, so in effect, our laziness is testing an edge case
    # in the clients
    self.RemoveObject(path)

    manager = mockobject.objects["/"]
    manager.EmitSignal(
        OBJECT_MANAGER_IFACE,
        "InterfacesRemoved",
        "oas",
        [
            dbus.ObjectPath(path),
            [ADAPTER_IFACE],
        ],
    )


@dbus.service.method(BLUEZ_MOCK_IFACE, in_signature="s")
def RemoveAdapterWithDevices(self, device_name):
    """Convenience method to remove a Bluetooth adapter and all
    the devices associated to it
    """
    adapter_path = "/org/bluez/" + device_name
    adapter = mockobject.objects[adapter_path]
    manager = mockobject.objects["/"]

    to_remove = []
    for path in mockobject.objects:
        if path.startswith(adapter_path + "/"):
            to_remove.append(path)

    for path in to_remove:
        adapter.RemoveObject(path)
        manager.EmitSignal(
            OBJECT_MANAGER_IFACE,
            "InterfacesRemoved",
            "oas",
            [
                dbus.ObjectPath(path),
                [DEVICE_IFACE],
            ],
        )

    self.RemoveObject(adapter_path)
    manager.EmitSignal(
        OBJECT_MANAGER_IFACE,
        "InterfacesRemoved",
        "oas",
        [
            dbus.ObjectPath(adapter_path),
            [ADAPTER_IFACE],
        ],
    )


@dbus.service.method(DEVICE_IFACE, in_signature="", out_signature="")
def Pair(device):
    if device.paired:
        raise dbus.exceptions.DBusException("Device already paired", name="org.bluez.Error.AlreadyExists")
    device_address = device.props[DEVICE_IFACE]["Address"]
    adapter_device_name = Path(device.props[DEVICE_IFACE]["Adapter"]).name
    device.PairDevice(adapter_device_name, device_address)


@dbus.service.method(DEVICE_IFACE, in_signature="", out_signature="")
def Connect(device):
    if device.connected:
        raise dbus.exceptions.DBusException("Already Connected", name="org.bluez.Error.AlreadyConnected")
    device.connected = True
    device.EmitSignal(
        dbus.PROPERTIES_IFACE,
        "PropertiesChanged",
        "sa{sv}as",
        [
            DEVICE_IFACE,
            {
                "Connected": dbus.Boolean(device.connected),
            },
            [],
        ],
    )


@dbus.service.method(DEVICE_IFACE, in_signature="", out_signature="")
def Disconnect(device):
    if not device.connected:
        raise dbus.exceptions.DBusException("Not Connected", name="org.bluez.Error.NotConnected")
    device.connected = False
    device.EmitSignal(
        dbus.PROPERTIES_IFACE,
        "PropertiesChanged",
        "sa{sv}as",
        [
            DEVICE_IFACE,
            {
                "Connected": dbus.Boolean(device.connected),
            },
            [],
        ],
    )


@dbus.service.method(BLUEZ_MOCK_IFACE, in_signature="sss", out_signature="s")
def AddDevice(self, adapter_device_name, device_address, alias):
    """Convenience method to add a Bluetooth device

    You have to specify a device address which must be a valid Bluetooth
    address (e.g. 'AA:BB:CC:DD:EE:FF'). The alias is the human-readable name
    for the device (e.g. as set on the device itself), and the adapter device
    name is the device_name passed to AddAdapter.

    This will create a new, unpaired and unconnected device with some default properties
    like MOCK_PHONE_CLASS "Class" and a static "Modalias". Especially when working with more
    than one device, you may want to change these after creation.

    Returns the new object path.
    """
    device_name = "dev_" + device_address.replace(":", "_").upper()
    adapter_path = "/org/bluez/" + adapter_device_name
    path = adapter_path + "/" + device_name

    if adapter_path not in mockobject.objects:
        raise dbus.exceptions.DBusException(
            f"Adapter {adapter_device_name} does not exist.", name=BLUEZ_MOCK_IFACE + ".NoSuchAdapter"
        )

    properties = {
        "Address": dbus.String(device_address),
        "AddressType": dbus.String("public"),
        "Name": dbus.String(alias),
        "Icon": dbus.String("phone"),
        "Class": dbus.UInt32(MOCK_PHONE_CLASS),
        "Appearance": dbus.UInt16(0),
        "UUIDs": dbus.Array([], signature="s"),
        "Paired": dbus.Boolean(False),
        "Connected": dbus.Boolean(False),
        "Trusted": dbus.Boolean(False),
        "Blocked": dbus.Boolean(False),
        "WakeAllowed": dbus.Boolean(False),
        "Alias": dbus.String(alias),
        "Adapter": dbus.ObjectPath(adapter_path),
        "LegacyPairing": dbus.Boolean(False),
        "Modalias": dbus.String("bluetooth:v000Fp1200d1436"),
        "RSSI": dbus.Int16(-79),  # arbitrary
        "TxPower": dbus.Int16(0),
        "ManufacturerData": dbus.Array([], signature="a{qv}"),
        "ServiceData": dbus.Array([], signature="a{sv}"),
        "ServicesResolved": dbus.Boolean(False),
        "AdvertisingFlags": dbus.Array([], signature="ay"),
        "AdvertisingData": dbus.Array([], signature="a{yv}"),
    }

    self.AddObject(
        path,
        DEVICE_IFACE,
        # Properties
        properties,
        # Methods
        [
            ("CancelPairing", "", "", ""),
            ("Connect", "", "", Connect),
            ("ConnectProfile", "s", "", ""),
            ("Disconnect", "", "", Disconnect),
            ("DisconnectProfile", "s", "", ""),
            ("Pair", "", "", Pair),
        ],
    )
    device = mockobject.objects[path]
    device.paired = False
    device.connected = False

    manager = mockobject.objects["/"]
    manager.EmitSignal(
        OBJECT_MANAGER_IFACE,
        "InterfacesAdded",
        "oa{sa{sv}}",
        [
            dbus.ObjectPath(path),
            {DEVICE_IFACE: properties},
        ],
    )

    return path


@dbus.service.method(BLUEZ_MOCK_IFACE, in_signature="ss", out_signature="")
def PairDevice(_self, adapter_device_name, device_address):
    """Convenience method to mark an existing device as paired.

    You have to specify a device address which must be a valid Bluetooth
    address (e.g. 'AA:BB:CC:DD:EE:FF'). The adapter device name is the
    device_name passed to AddAdapter.

    This unblocks the device if it was blocked.

    If the specified adapter or device doesn't exist, a NoSuchAdapter or
    NoSuchDevice error will be returned on the bus.

    Returns nothing.
    """
    device_name = "dev_" + device_address.replace(":", "_").upper()
    adapter_path = "/org/bluez/" + adapter_device_name
    device_path = adapter_path + "/" + device_name

    if adapter_path not in mockobject.objects:
        raise dbus.exceptions.DBusException(
            f"Adapter {adapter_device_name} does not exist.", name=BLUEZ_MOCK_IFACE + ".NoSuchAdapter"
        )
    if device_path not in mockobject.objects:
        raise dbus.exceptions.DBusException(
            f"Device {device_name} does not exist.", name=BLUEZ_MOCK_IFACE + ".NoSuchDevice"
        )

    device = mockobject.objects[device_path]
    device.paired = True

    # Based off pairing with an Android phone.
    uuids = [
        "00001105-0000-1000-8000-00805f9b34fb",
        "0000110a-0000-1000-8000-00805f9b34fb",
        "0000110c-0000-1000-8000-00805f9b34fb",
        "00001112-0000-1000-8000-00805f9b34fb",
        "00001115-0000-1000-8000-00805f9b34fb",
        "00001116-0000-1000-8000-00805f9b34fb",
        "0000111f-0000-1000-8000-00805f9b34fb",
        "0000112f-0000-1000-8000-00805f9b34fb",
        "00001200-0000-1000-8000-00805f9b34fb",
    ]

    device.UpdateProperties(
        DEVICE_IFACE,
        {
            "UUIDs": dbus.Array(uuids),
            "Paired": dbus.Boolean(True),
            "LegacyPairing": dbus.Boolean(True),
            "Blocked": dbus.Boolean(False),
        },
    )


@dbus.service.method(BLUEZ_MOCK_IFACE, in_signature="ss", out_signature="")
def BlockDevice(_self, adapter_device_name, device_address):
    """Convenience method to mark an existing device as blocked.

    You have to specify a device address which must be a valid Bluetooth
    address (e.g. 'AA:BB:CC:DD:EE:FF'). The adapter device name is the
    device_name passed to AddAdapter.

    This disconnects the device if it was connected.

    If the specified adapter or device doesn't exist, a NoSuchAdapter or
    NoSuchDevice error will be returned on the bus.

    Returns nothing.
    """
    device_name = "dev_" + device_address.replace(":", "_").upper()
    adapter_path = "/org/bluez/" + adapter_device_name
    device_path = adapter_path + "/" + device_name

    if adapter_path not in mockobject.objects:
        raise dbus.exceptions.DBusException(
            f"Adapter {adapter_device_name} does not exist.", name=BLUEZ_MOCK_IFACE + ".NoSuchAdapter"
        )
    if device_path not in mockobject.objects:
        raise dbus.exceptions.DBusException(
            f"Device {device_name} does not exist.", name=BLUEZ_MOCK_IFACE + ".NoSuchDevice"
        )

    device = mockobject.objects[device_path]

    device.props[DEVICE_IFACE]["Blocked"] = dbus.Boolean(True)
    device.props[DEVICE_IFACE]["Connected"] = dbus.Boolean(False)

    device.EmitSignal(
        dbus.PROPERTIES_IFACE,
        "PropertiesChanged",
        "sa{sv}as",
        [
            DEVICE_IFACE,
            {
                "Blocked": dbus.Boolean(True),
                "Connected": dbus.Boolean(False),
            },
            [],
        ],
    )


@dbus.service.method(BLUEZ_MOCK_IFACE, in_signature="ss", out_signature="")
def ConnectDevice(_self, adapter_device_name, device_address):
    """Convenience method to mark an existing device as connected.

    You have to specify a device address which must be a valid Bluetooth
    address (e.g. 'AA:BB:CC:DD:EE:FF'). The adapter device name is the
    device_name passed to AddAdapter.

    This unblocks the device if it was blocked.

    If the specified adapter or device doesn't exist, a NoSuchAdapter or
    NoSuchDevice error will be returned on the bus.

    Returns nothing.
    """
    device_name = "dev_" + device_address.replace(":", "_").upper()
    adapter_path = "/org/bluez/" + adapter_device_name
    device_path = adapter_path + "/" + device_name

    if adapter_path not in mockobject.objects:
        raise dbus.exceptions.DBusException(
            f"Adapter {adapter_device_name} does not exist.", name=BLUEZ_MOCK_IFACE + ".NoSuchAdapter"
        )
    if device_path not in mockobject.objects:
        raise dbus.exceptions.DBusException(
            f"Device {device_name} does not exist.", name=BLUEZ_MOCK_IFACE + ".NoSuchDevice"
        )

    device = mockobject.objects[device_path]

    device.props[DEVICE_IFACE]["Blocked"] = dbus.Boolean(False)
    device.props[DEVICE_IFACE]["Connected"] = dbus.Boolean(True)

    device.EmitSignal(
        dbus.PROPERTIES_IFACE,
        "PropertiesChanged",
        "sa{sv}as",
        [
            DEVICE_IFACE,
            {
                "Blocked": dbus.Boolean(False),
                "Connected": dbus.Boolean(True),
            },
            [],
        ],
    )


@dbus.service.method(BLUEZ_MOCK_IFACE, in_signature="ss", out_signature="")
def DisconnectDevice(_self, adapter_device_name, device_address):
    """Convenience method to mark an existing device as disconnected.

    You have to specify a device address which must be a valid Bluetooth
    address (e.g. 'AA:BB:CC:DD:EE:FF'). The adapter device name is the
    device_name passed to AddAdapter.

    This does not change the device's blocked status.

    If the specified adapter or device doesn't exist, a NoSuchAdapter or
    NoSuchDevice error will be returned on the bus.

    Returns nothing.
    """
    device_name = "dev_" + device_address.replace(":", "_").upper()
    adapter_path = "/org/bluez/" + adapter_device_name
    device_path = adapter_path + "/" + device_name

    if adapter_path not in mockobject.objects:
        raise dbus.exceptions.DBusException(
            f"Adapter {adapter_device_name} does not exist.", name=BLUEZ_MOCK_IFACE + ".NoSuchAdapter"
        )
    if device_path not in mockobject.objects:
        raise dbus.exceptions.DBusException(
            f"Device {device_name} does not exist.", name=BLUEZ_MOCK_IFACE + ".NoSuchDevice"
        )

    device = mockobject.objects[device_path]

    device.props[DEVICE_IFACE]["Connected"] = dbus.Boolean(False)

    device.EmitSignal(
        dbus.PROPERTIES_IFACE,
        "PropertiesChanged",
        "sa{sv}as",
        [
            DEVICE_IFACE,
            {
                "Connected": dbus.Boolean(False),
            },
            [],
        ],
    )


def RegisterAdvertisement(manager, adv_path, options):  # pylint: disable=unused-argument
    if adv_path in manager.advertisements:
        raise dbus.exceptions.DBusException("Already registered: " + adv_path, name="org.bluez.Error.AlreadyExists")

    if len(manager.advertisements) >= MAX_ADVERTISEMENT_INSTANCES:
        raise dbus.exceptions.DBusException(
            f"Maximum number of advertisements reached: {MAX_ADVERTISEMENT_INSTANCES}",
            name="org.bluez.Error.NotPermitted",
        )

    manager.advertisements.append(adv_path)

    manager.UpdateProperties(
        LE_ADVERTISING_MANAGER_IFACE,
        {
            "ActiveInstances": dbus.Byte(len(manager.advertisements)),
            "SupportedInstances": dbus.Byte(MAX_ADVERTISEMENT_INSTANCES - len(manager.advertisements)),
        },
    )


def UnregisterAdvertisement(manager, adv_path):
    try:
        manager.advertisements.remove(adv_path)
    except ValueError:
        raise dbus.exceptions.DBusException(
            "Unknown advertisement: " + adv_path, name="org.bluez.Error.DoesNotExist"
        ) from None

    manager.UpdateProperties(
        LE_ADVERTISING_MANAGER_IFACE,
        {
            "ActiveInstances": dbus.Byte(len(manager.advertisements)),
            "SupportedInstances": dbus.Byte(MAX_ADVERTISEMENT_INSTANCES - len(manager.advertisements)),
        },
    )


@dbus.service.method(BLUEZ_MOCK_IFACE, in_signature="s", out_signature="s")
def AddAdvertisement(self, adv_name):
    """Convenience method to add an Advertisement object

    Creates a simple broadcast advertisement with some manufacturer data.

    Returns the new object path.
    """
    path = "/org/dbusmock/bluez/advertisement/" + adv_name

    adv_properties = {
        "Type": dbus.String("broadcast"),
        "ManufacturerData": dbus.Dictionary(
            # 0xFFFF is the Bluetooth Company Identifier reserved for internal use and testing.
            {dbus.UInt16(0xFFFF): dbus.Array([0x00, 0x01])},
            signature="qv",
        ),
        "Includes": dbus.Array(["local-name"]),
    }

    self.AddObject(
        path,
        LE_ADVERTISEMENT_IFACE,
        adv_properties,
        [
            ("Release", "", "", ""),
        ],
    )

    return path


@dbus.service.method(BLUEZ_MOCK_IFACE, in_signature="s", out_signature="s")
def AddMonitor(self, monitor_name):
    """Convenience method to add an Advertisement Monitor

    Returns the new object path.
    """
    path = "/org/dbusmock/bluez/monitor/" + monitor_name

    monitor_properties = {
        "Type": dbus.String("or_patterns"),
        # Example pattern that could be used to scan for an advertisement created by AddAdvertisement()
        "Patterns": dbus.Struct(
            (
                # Start position: 0
                dbus.Byte(0),
                # AD data type: Manufacturer data
                dbus.Byte(0xFF),
                # Vaue of the pattern: 0xFFFF (company identifier), followed by 0x01
                dbus.Array(
                    [
                        dbus.UInt16(0xFFFF),
                        dbus.Byte(0x01),
                    ]
                ),
            ),
            signature="yyay",
        ),
    }

    self.AddObject(
        path,
        ADVERTISEMENT_MONITOR_IFACE,
        monitor_properties,
        [
            ("Release", "", "", ""),
            ("Activate", "", "", ""),
            ("DeviceFound", "o", "", ""),
            ("DeviceLost", "o", "", ""),
        ],
    )

    return path


def RegisterMonitor(manager, monitor_path):
    if monitor_path in manager.monitors:
        raise dbus.exceptions.DBusException(
            "Already registered: " + monitor_path, name="org.bluez.Error.AlreadyExists"
        )

    manager.monitors.append(monitor_path)


def UnregisterMonitor(manager, monitor_path):
    try:
        manager.monitors.remove(monitor_path)
    except ValueError:
        raise dbus.exceptions.DBusException(
            "Unknown monitor: " + monitor_path, name="org.bluez.Error.DoesNotExist"
        ) from None
