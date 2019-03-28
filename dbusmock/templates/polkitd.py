'''polkitd mock template

This creates the expected methods and properties of the main
org.freedesktop.PolicyKit1 object. By default, all actions are rejected.  You
can call AllowUnknown() and SetAllowed() on the mock D-Bus interface to control
which actions are allowed.
'''

# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 3 of the License, or (at your option) any
# later version.  See http://www.gnu.org/copyleft/lgpl.html for the full text
# of the license.

__author__ = 'Martin Pitt'
__email__ = 'martin.pitt@ubuntu.com'
__copyright__ = '(c) 2013 Canonical Ltd.'
__license__ = 'LGPL 3+'

import dbus

from dbusmock import MOCK_IFACE

BUS_NAME = 'org.freedesktop.PolicyKit1'
MAIN_OBJ = '/org/freedesktop/PolicyKit1/Authority'
MAIN_IFACE = 'org.freedesktop.PolicyKit1.Authority'
SYSTEM_BUS = True


def load(mock, parameters):
    mock.AddMethod(MAIN_IFACE,
                   'CheckAuthorization',
                   '(sa{sv})sa{ss}us',
                   '(bba{ss})',
                   '''ret = (args[1] in self.allowed or self.allow_unknown, False, {'test': 'test'})''')

    mock.AddProperties(MAIN_IFACE,
                       dbus.Dictionary({
                           'BackendName': 'local',
                           'BackendVersion': '0.8.15',
                           'BackendFeatures': dbus.UInt32(1, variant_level=1),
                       }, signature='sv'))

    # default state
    mock.allow_unknown = False
    mock.allowed = []


@dbus.service.method(MOCK_IFACE, in_signature='b', out_signature='')
def AllowUnknown(self, default):
    '''Control whether unknown actions are allowed

    This controls the return value of CheckAuthorization for actions which were
    not explicitly allowed by SetAllowed().
    '''
    self.allow_unknown = default


@dbus.service.method(MOCK_IFACE, in_signature='as', out_signature='')
def SetAllowed(self, actions):
    '''Set allowed actions'''

    self.allowed = actions
