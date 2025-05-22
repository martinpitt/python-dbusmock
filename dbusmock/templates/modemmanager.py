"""ModemManager mock template

This creates the expected methods and properties of the main
ModemManager object, but no devices. You can specify any property
such as DaemonVersion in "parameters".
"""

# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 3 of the License, or (at your option) any
# later version.  See http://www.gnu.org/copyleft/lgpl.html for the full text
# of the license.

__author__ = "Guido Günther"
__copyright__ = "2024 The Phosh Developers"

import dbus

from dbusmock import MOCK_IFACE, OBJECT_MANAGER_IFACE, mockobject

BUS_NAME = "org.freedesktop.ModemManager1"
MAIN_OBJ = "/org/freedesktop/ModemManager1"
MAIN_IFACE = "org.freedesktop.ModemManager1"
SYSTEM_BUS = True
IS_OBJECT_MANAGER = False
MODEM_IFACE = "org.freedesktop.ModemManager1.Modem"
MODEM_3GPP_IFACE = "org.freedesktop.ModemManager1.Modem.Modem3gpp"
MODEM_CELL_BROADCAST_IFACE = "org.freedesktop.ModemManager1.Modem.CellBroadcast"
MODEM_VOICE_IFACE = "org.freedesktop.ModemManager1.Modem.Voice"
SIM_IFACE = "org.freedesktop.ModemManager1.Sim"
CBM_IFACE = "org.freedesktop.ModemManager1.Cbm"
SIMPLE_MODEM_PATH = "/org/freedesktop/ModemManager1/Modems/8"


class MMModemMode:
    """
    See
    https://www.freedesktop.org/software/ModemManager/doc/latest/ModemManager/ModemManager-Flags-and-Enumerations.html#MMModemMode
    """

    MODE_NONE = 0
    MODE_CS = 1 << 0
    MODE_2G = 1 << 1
    MODE_3G = 1 << 2
    MODE_4G = 1 << 3
    MODE_5G = 1 << 4


class MMModemState:
    """
    See
    https://www.freedesktop.org/software/ModemManager/doc/latest/ModemManager/ModemManager-Flags-and-Enumerations.html#MMModemState
    """

    STATE_FAILED = -1
    STATE_UNKNOWN = 0
    STATE_INITIALIZING = 1
    STATE_LOCKED = 2
    STATE_DISABLED = 3
    STATE_DISABLING = 4
    STATE_ENABLING = 5
    STATE_ENABLED = 6
    STATE_SEARCHING = 7
    STATE_REGISTERED = 8
    STATE_DISCONNECTING = 9
    STATE_CONNECTING = 10
    STATE_CONNECTED = 11


class MMModemPowerState:
    """
    See
    https://www.freedesktop.org/software/ModemManager/doc/latest/ModemManager/ModemManager-Flags-and-Enumerations.html#MMModemPowerState
    """

    POWER_STATE_UNKNOWN = 0
    POWER_STATE_OFF = 1
    POWER_STATE_LOW = 2
    POWER_STATE_ON = 3


class MMModemAccesssTechnology:
    """
    See
    https://www.freedesktop.org/software/ModemManager/doc/latest/ModemManager/ModemManager-Flags-and-Enumerations.html#MMModemAccessTechnology
    """

    ACCESS_TECHNOLOGY_UNKNOWN = 0
    ACCESS_TECHNOLOGY_POTS = 1 << 0
    ACCESS_TECHNOLOGY_GSM = 1 << 1
    ACCESS_TECHNOLOGY_GSM_COMPACT = 1 << 2
    ACCESS_TECHNOLOGY_GPRS = 1 << 3
    ACCESS_TECHNOLOGY_EDGE = 1 << 4
    ACCESS_TECHNOLOGY_UMTS = 1 << 5
    ACCESS_TECHNOLOGY_HSDPA = 1 << 6
    ACCESS_TECHNOLOGY_HSUPA = 1 << 7
    ACCESS_TECHNOLOGY_HSPA = 1 << 8
    ACCESS_TECHNOLOGY_HSPA_PLUS = 1 << 9
    ACCESS_TECHNOLOGY_1XRTT = 1 << 10
    ACCESS_TECHNOLOGY_EVDO0 = 1 << 11
    ACCESS_TECHNOLOGY_EVDOA = 1 << 12
    ACCESS_TECHNOLOGY_EVDOB = 1 << 13
    ACCESS_TECHNOLOGY_LTE = 1 << 14
    ACCESS_TECHNOLOGY_5GNR = 1 << 15
    ACCESS_TECHNOLOGY_LTE_CAT_M = 1 << 16
    ACCESS_TECHNOLOGY_LTE_NB_IOT = 1 << 17


def load(mock, parameters):
    methods = [
        ("ScanDevices", "", "", ""),
    ]

    props = dbus.Dictionary(
        {
            "Version": parameters.get("DaemonVersion", "1.22"),
        },
        signature="sv",
    )

    mock.AddMethods(MAIN_IFACE, methods)
    mock.AddProperties(MAIN_IFACE, props)

    cond = "k != '/'" if mock.path == "/" else f"k.startswith('{mock.path}/Modems/')"
    code = f"ret = {{dbus.ObjectPath(k): objects[k].props for k in objects.keys() if {cond} }}"
    mock.AddMethod(OBJECT_MANAGER_IFACE, "GetManagedObjects", "", "a{oa{sa{sv}}}", code)


def listCbm(_):
    paths = []
    for path in mockobject.objects:
        if path.startswith("/org/freedesktop/ModemManager1/Cbm/"):
            paths.append(dbus.ObjectPath(path))
    return paths


def deleteCbm(self, cbm_path):
    obj = mockobject.objects.get(cbm_path)
    if obj is None:
        return

    modem_obj = mockobject.objects[SIMPLE_MODEM_PATH]
    self.RemoveObject(cbm_path)
    modem_obj.EmitSignal(
        MODEM_CELL_BROADCAST_IFACE,
        "Deleted",
        "o",
        [
            cbm_path,
        ],
    )


def setChannels(_self, channels):
    modem_obj = mockobject.objects[SIMPLE_MODEM_PATH]

    modem_obj.UpdateProperties(
        MODEM_CELL_BROADCAST_IFACE,
        {
            "Channels": dbus.Array(channels),
        },
    )


@dbus.service.method(MOCK_IFACE, in_signature="", out_signature="ss")
def AddSimpleModem(self):
    """Convenience method to add a simple Modem object

    Please note that this does not set any global properties.

    Returns the new object path.
    """
    modem_path = SIMPLE_MODEM_PATH
    sim_path = "/org/freedesktop/ModemManager1/SIM/2"
    manager = mockobject.objects[MAIN_OBJ]

    modem_props = {
        "State": dbus.Int32(MMModemState.STATE_ENABLED),
        "Model": dbus.String("E1750"),
        "Revision": dbus.String("11.126.08.01.00"),
        "AccessTechnologies": dbus.UInt32(MMModemAccesssTechnology.ACCESS_TECHNOLOGY_LTE),
        "PowerState": dbus.UInt32(MMModemPowerState.POWER_STATE_ON),
        "UnlockRequired": dbus.UInt32(0),
        "UnlockRetries": dbus.Dictionary([], signature="uu"),
        "CurrentModes": dbus.Struct(
            (dbus.UInt32(MMModemMode.MODE_4G), dbus.UInt32(MMModemMode.MODE_4G)), signature="(uu)"
        ),
        "SignalQuality": dbus.Struct(
            (dbus.UInt32(70), dbus.Boolean(True)),
        ),
        "Sim": dbus.ObjectPath(sim_path),
        "SupportedModes": [
            (dbus.UInt32(MMModemMode.MODE_4G), dbus.UInt32(MMModemMode.MODE_4G)),
            (dbus.UInt32(MMModemMode.MODE_3G | MMModemMode.MODE_2G), dbus.UInt32(MMModemMode.MODE_3G)),
        ],
        "SupportedBands": [dbus.UInt32(0)],
    }
    self.AddObject(modem_path, MODEM_IFACE, modem_props, [])

    modem_3gpp_props = {
        "Imei": dbus.String("doesnotmatter"),
        "OperatorName": dbus.String("TheOperator"),
        "OperatorCode": dbus.String("00101"),
        "Pco": dbus.Array([], signature="(ubay)"),
    }
    modem = mockobject.objects[modem_path]
    modem.AddProperties(MODEM_3GPP_IFACE, modem_3gpp_props)

    modem_cell_broadcast_props = {
        "Channels": dbus.Array([], signature="(uu)"),
        "CellBroadcasts": dbus.Array([], signature="o"),
    }
    modem_cell_broadcast_methods = [
        ("List", "", "ao", listCbm),
        ("Delete", "o", "", deleteCbm),
        ("SetChannels", "a(uu)", "", setChannels),
    ]
    modem.AddProperties(MODEM_CELL_BROADCAST_IFACE, modem_cell_broadcast_props)
    modem.AddMethods(MODEM_CELL_BROADCAST_IFACE, modem_cell_broadcast_methods)

    modem_voice_props = {
        "Calls": dbus.Array([], signature="o"),
        "EmergencyOnly": False,
    }

    modem.call_waiting = False
    modem_voice_methods = [
        ("CallWaitingQuery", "", "b", "ret = self.call_waiting"),
        ("CallWaitingSetup", "b", "", "self.call_waiting = args[0]"),
    ]
    modem.AddProperties(MODEM_VOICE_IFACE, modem_voice_props)
    modem.AddMethods(MODEM_VOICE_IFACE, modem_voice_methods)

    manager.EmitSignal(
        OBJECT_MANAGER_IFACE,
        "InterfacesAdded",
        "oa{sa{sv}}",
        [
            dbus.ObjectPath(modem_path),
            {
                MODEM_IFACE: modem_props,
                MODEM_3GPP_IFACE: modem_3gpp_props,
                MODEM_CELL_BROADCAST_IFACE: modem_cell_broadcast_props,
                MODEM_VOICE_IFACE: modem_voice_props,
            },
        ],
    )

    sim_props = {
        "Active": dbus.Boolean(True),
        "Imsi": dbus.String("doesnotmatter"),
        "PreferredNetworks": dbus.Array([], signature="(su)"),
    }
    self.AddObject(sim_path, SIM_IFACE, sim_props, [])

    return (modem_path, sim_path)


@dbus.service.method(MOCK_IFACE, in_signature="uus", out_signature="s")
def AddCbm(self, state, channel, text):
    """Convenience method to add a cell broadcast message

    Returns the new object path.
    """
    n = 1
    while mockobject.objects.get(f"/org/freedesktop/ModemManager1/Cbm/{n}") is not None:
        n += 1
    cbm_path = f"/org/freedesktop/ModemManager1/Cbm/{n}"

    cbm_props = {
        "State": dbus.UInt32(state),
        "Channel": dbus.UInt32(channel),
        "Text": dbus.String(text),
        "MessageCode": dbus.UInt32(0),
        "Update": dbus.UInt32(0),
    }
    self.AddObject(cbm_path, CBM_IFACE, cbm_props, [])

    modem_obj = mockobject.objects[SIMPLE_MODEM_PATH]
    paths = listCbm(self)
    modem_obj.UpdateProperties(
        MODEM_CELL_BROADCAST_IFACE,
        {
            "CellBroadcasts": dbus.Array(paths),
        },
    )

    modem_obj.EmitSignal(
        MODEM_CELL_BROADCAST_IFACE,
        "Added",
        "o",
        [
            dbus.ObjectPath(cbm_path),
        ],
    )

    return cbm_path
