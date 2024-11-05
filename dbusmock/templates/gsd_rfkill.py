"""gsd-rfkill mock template

This creates the expected properties of the GNOME Settings Daemon's
rfkill object. You can specify any property such as AirplaneMode in
"parameters".
"""

# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 3 of the License, or (at your option) any
# later version.  See http://www.gnu.org/copyleft/lgpl.html for the full text
# of the license.

__author__ = "Guido Günther"
__copyright__ = "2024 The Phosh Developers"

import dbus

from dbusmock import MOCK_IFACE

SYSTEM_BUS = False
BUS_NAME = "org.gnome.SettingsDaemon.Rfkill"
MAIN_OBJ = "/org/gnome/SettingsDaemon/Rfkill"
MAIN_IFACE = "org.gnome.SettingsDaemon.Rfkill"


def load(mock, parameters):
    props = dbus.Dictionary(
        {
            "AirplaneMode": parameters.get("AirplaneMode", False),
            "BluetoothAirplaneMode": parameters.get("BluetoothAirplaneMode", False),
            "BluetoothHardwareAirplaneMode": parameters.get("BluetoothHardwareAirplaneMode", False),
            "BluetoothHasAirplaneMode": parameters.get("BluetoothHasAirplanemode", True),
            "HardwareAirplaneMode": parameters.get("HardwareAirplaneMode", False),
            "HasAirplaneMode": parameters.get("HasAirplaneMode", True),
            "ShouldShowAirplaneMode": parameters.get("ShouldShowAirplaneMode", True),
            "WwanAirplaneMode": parameters.get("WwanAirplaneMode", False),
            "WwanHardwareAirplaneMode": parameters.get("WwanHardwareAirplaneMode", False),
            "WwanHasAirplaneMode": parameters.get("WwanHasAirplaneMode", True),
        },
        signature="sv",
    )
    mock.AddProperties(MAIN_IFACE, props)


@dbus.service.method(MOCK_IFACE, in_signature="b", out_signature="b")
def SetAirplaneMode(self, mode):
    """
    Convenience method to toggle airplane mode
    """
    self.props[MAIN_IFACE]["AirplaneMode"] = mode
    self.props[MAIN_IFACE]["BluetoothAirplaneMode"] = mode
    self.props[MAIN_IFACE]["WwanAirplaneMode"] = mode
    return mode
