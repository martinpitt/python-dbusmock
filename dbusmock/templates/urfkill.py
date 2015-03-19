'''urfkill mock template

This creates the expected methods and properties of the main
urfkill object, but no devices. You can specify any property
such as urfkill in "parameters".
'''

# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 3 of the License, or (at your option) any
# later version.  See http://www.gnu.org/copyleft/lgpl.html for the full text
# of the license.

__author__ = 'Jussi Pakkanen'
__email__ = 'jussi.pakkanen@canonical.com'
__copyright__ = '(C) 2015 Canonical ltd'
__license__ = 'LGPL 3+'

import dbus

import dbusmock

SYSTEM_BUS = True
BUS_NAME = 'org.freedesktop.URfkill'
MAIN_OBJ = '/org/freedesktop/URfkill'

MAIN_IFACE = 'org.freedesktop.URfkill'

individual_objects = ['BLUETOOTH', 'FM', 'GPS', 'NFC', 'UWB', 'WIMAX', 'WLAN', 'WWAN']
type2objectname = {
    1: 'WLAN',
    2: 'BLUETOOTH',
    3: 'UWB',
    4: 'WIMAX',
    5: 'WWAN',
    6: 'GPS',
    7: 'FM',
}

KS_NOTAVAILABLE = -1
KS_UNBLOCKED = 0
KS_SOFTBLOCKED = 1
KS_HARDBLOCKED = 2


def toggle_flight_mode(self, new_block_state):
    new_block_state = bool(new_block_state)
    if self.flight_mode == new_block_state:
        return True
    self.flight_mode = new_block_state
    for i in individual_objects:
        old_value = self.internal_states[i]
        if old_value == 1:
            continue  # It was already blocked so we don't need to do anything
        path = '/org/freedesktop/URfkill/' + i
        obj = dbusmock.get_object(path)
        if new_block_state:
            obj.Set('org.freedesktop.URfkill.Killswitch', 'state', 1)
            obj.EmitSignal('org.freedesktop.URfkill.Killswitch', 'StateChanged', '', [])
        else:
            obj.Set('org.freedesktop.URfkill.Killswitch', 'state', 0)
            obj.EmitSignal('org.freedesktop.URfkill.Killswitch', 'StateChanged', '', [])
    self.EmitSignal(MAIN_IFACE, 'FlightModeChanged', 'b', [self.flight_mode])
    return True


def block(self, index, should_block):
    should_block = bool(should_block)
    if index not in type2objectname:
        return False
    objname = type2objectname[index]
    if should_block:
        new_block_state = 1
    else:
        new_block_state = 0
    if self.internal_states[objname] != new_block_state:
        path = '/org/freedesktop/URfkill/' + objname
        obj = dbusmock.get_object(path)
        self.internal_states[objname] = new_block_state
        obj.Set('org.freedesktop.URfkill.Killswitch', 'state', new_block_state)
        obj.EmitSignal('org.freedesktop.URfkill.Killswitch', 'StateChanged', '', [])
    return True


def load(mock, parameters):
    mock.toggle_flight_mode = toggle_flight_mode
    mock.block = block
    mock.flight_mode = False
    mock.internal_states = {}
    for oname in individual_objects:
        mock.internal_states[oname] = KS_UNBLOCKED

    # First we create the main urfkill object.
    mock.AddMethods(MAIN_IFACE, [
        ('IsFlightMode', '', 'b', 'ret = self.flight_mode'),
        ('FlightMode', 'b', 'b', 'ret = self.toggle_flight_mode(self, args[0])'),
        ('Block', 'ub', 'b', 'ret = self.block(self, args[0], args[1])'),
    ])

    mock.AddProperties(MAIN_IFACE,
                       dbus.Dictionary({
                           'DaemonVersion': parameters.get('DaemonVersion', '0.6.0'),
                           'KeyControl': parameters.get('KeyControl', True)
                       }, signature='sv'))

    for i in individual_objects:
        path = '/org/freedesktop/URfkill/' + i
        mock.AddObject(path, 'org.freedesktop.URfkill.Killswitch', {'state': mock.internal_states[i]}, [])
