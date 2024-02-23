"""power-profiles-daemon >= 0.20 mock template

This creates the expected methods and properties of the main
org.freedesktop.UPower.PowerProfiles object.

This provides the D-Bus API as of version 0.20.
"""

# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 3 of the License, or (at your option) any
# later version.  See http://www.gnu.org/copyleft/lgpl.html for the full text
# of the license.

__author__ = "Bastien Nocera"
__copyright__ = """
(c) 2021, Red Hat Inc.
(c) 2017 - 2024 Martin Pitt <martin@piware.de>
"""

import dbus

BUS_NAME = "org.freedesktop.UPower.PowerProfiles"
MAIN_OBJ = "/org/freedesktop/UPower/PowerProfiles"
MAIN_IFACE = "org.freedesktop.UPower.PowerProfiles"
SYSTEM_BUS = True


def hold_profile(self, profile, reason, application_id):
    self.cookie += 1
    element = {"Profile": profile, "Reason": reason, "ApplicationId": application_id}
    self.holds[self.cookie] = element
    self.props[MAIN_IFACE]["ActiveProfileHolds"] = []
    for value in self.holds.values():
        self.props[MAIN_IFACE]["ActiveProfileHolds"].append(value)
    return self.cookie


def release_profile(self, cookie):
    self.holds.pop(cookie)
    self.props[MAIN_IFACE]["ActiveProfileHolds"] = []
    for value in self.holds.values():
        self.props[MAIN_IFACE]["ActiveProfileHolds"].append(value)
    if len(self.props[MAIN_IFACE]["ActiveProfileHolds"]) == 0:
        self.props[MAIN_IFACE]["ActiveProfileHolds"] = dbus.Array([], signature="(aa{sv})")


def load(mock, parameters):
    # Loaded!
    mock.loaded = True
    mock.cookie = 0
    mock.hold_profile = hold_profile
    mock.release_profile = release_profile
    mock.holds = {}

    props = {
        "ActiveProfile": parameters.get("ActiveProfile", "balanced"),
        "PerformanceDegraded": parameters.get("PerformanceDegraded", ""),
        "Profiles": [
            dbus.Dictionary({"Profile": "power-saver", "Driver": "dbusmock"}, signature="sv"),
            dbus.Dictionary({"Profile": "balanced", "Driver": "dbusmock"}, signature="sv"),
            dbus.Dictionary({"Profile": "performance", "Driver": "dbusmock"}, signature="sv"),
        ],
        "Actions": dbus.Array([], signature="s"),
        "ActiveProfileHolds": dbus.Array([], signature="(aa{sv})"),
    }
    mock.AddProperties(MAIN_IFACE, dbus.Dictionary(props, signature="sv"))

    mock.AddMethods(
        MAIN_IFACE,
        [
            ("HoldProfile", "sss", "u", "ret = self.hold_profile(self, args[0], args[1], args[2])"),
            ("ReleaseProfile", "u", "", "self.release_profile(self, args[0])"),
        ],
    )
