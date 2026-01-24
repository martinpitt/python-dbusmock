"""low-memory-monitor mock template

This creates the expected methods and properties of the main
org.freedesktop.LowMemoryMonitor object.

This provides only the 2.0 D-Bus API of low-memory-monitor.
"""

# SPDX-License-Identifier: LGPL-3.0-or-later

__author__ = "Bastien Nocera"
__copyright__ = """
(c) 2019, Red Hat Inc.
(c) 2017 - 2022 Martin Pitt <martin@piware.de>
"""

import dbus

from dbusmock import MOCK_IFACE

BUS_NAME = "org.freedesktop.LowMemoryMonitor"
MAIN_OBJ = "/org/freedesktop/LowMemoryMonitor"
MAIN_IFACE = "org.freedesktop.LowMemoryMonitor"
SYSTEM_BUS = True


def load(mock, _parameters):
    # Loaded!
    mock.loaded = True


@dbus.service.method(MOCK_IFACE, in_signature="y", out_signature="")
def EmitWarning(self, state):
    self.EmitSignal(MAIN_IFACE, "LowMemoryWarning", "y", [dbus.Byte(state)])
