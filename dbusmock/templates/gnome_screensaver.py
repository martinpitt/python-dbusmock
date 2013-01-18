'''gnome-shell screensaver mock template

This creates the expected methods and properties of the
org.gnome.ScreenSaver object.
'''

# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 3 of the License, or (at your option) any
# later version.  See http://www.gnu.org/copyleft/lgpl.html for the full text
# of the license.

__author__ = 'Bastien Nocera'
__email__ = 'hadess@hadess.net'
__copyright__ = '(c) 2013 Red Hat Inc.'
__license__ = 'LGPL 3+'

BUS_NAME = 'org.gnome.ScreenSaver'
MAIN_OBJ = '/org/gnome/ScreenSaver'
MAIN_IFACE = 'org.gnome.ScreenSaver'
SYSTEM_BUS = False


def load(mock, parameters):
    mock.AddMethods(MAIN_IFACE, [
        ('GetActive', '', 'b', 'ret = self.is_active'),
        ('GetActiveTime', '', 'u', 'ret = 1'),
        ('SetActive', 'b', '', 'self.is_active = args[0]; self.EmitSignal('
                               '"", "ActiveChanged", "b", [self.is_active])'),
        ('Lock', '', '', 'time.sleep(1); self.SetActive(True)'),
        ('ShowMessage', 'sss', '', ''),
        ('SimulateUserActivity', '', '', ''),
    ])

    # default state
    mock.is_active = False
