'''low-memory-monitor mock template

This creates the expected methods and properties of the main
org.freedesktop.LowMemoryMonitor object.

This provides only the 2.0 D-Bus API of low-memory-monitor.
'''

# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 3 of the License, or (at your option) any
# later version.  See http://www.gnu.org/copyleft/lgpl.html for the full text
# of the license.

__author__ = 'Bastien Nocera'
__email__ = 'hadess@hadess.net'
__copyright__ = '(c) 2019, Red Hat Inc.'
__license__ = 'LGPL 3+'

import dbus

from dbusmock import MOCK_IFACE

BUS_NAME = 'org.freedesktop.LowMemoryMonitor'
MAIN_OBJ = '/org/freedesktop/LowMemoryMonitor'
MAIN_IFACE = 'org.freedesktop.LowMemoryMonitor'
SYSTEM_BUS = True


def load(mock, parameters):
    # Loaded!
    mock.loaded = True


@dbus.service.method(MOCK_IFACE,
                     in_signature='y', out_signature='')
def EmitWarning(self, state):
    self.EmitSignal(MAIN_IFACE, 'LowMemoryWarning', 'y', [dbus.Byte(state)])
