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
__copyright__ = '''
(c) 2013-2021 Canonical Ltd.
(c) 2017 - 2022 Martin Pitt <martin@piware.de>
'''

import time

import dbus

from dbusmock import MOCK_IFACE

BUS_NAME = 'org.freedesktop.PolicyKit1'
MAIN_OBJ = '/org/freedesktop/PolicyKit1/Authority'
MAIN_IFACE = 'org.freedesktop.PolicyKit1.Authority'
SYSTEM_BUS = True


def load(mock, _parameters):
    mock.AddProperties(MAIN_IFACE,
                       dbus.Dictionary({
                           'BackendName': 'local',
                           'BackendVersion': '0.8.15',
                           'BackendFeatures': dbus.UInt32(1, variant_level=1),
                       }, signature='sv'))

    # default state
    mock.allow_unknown = False
    mock.allowed = []
    mock.delay = 0
    mock.simulate_hang = False
    mock.hanging_actions = []
    mock.hanging_calls = []


@dbus.service.method(MAIN_IFACE,
                     in_signature='(sa{sv})sa{ss}us',
                     out_signature='(bba{ss})',
                     async_callbacks=('ok_cb', '_err_cb'))
def CheckAuthorization(self, _subject, action_id, _details, _flags,
                       _cancellation_id, ok_cb, _err_cb):
    time.sleep(self.delay)
    allowed = action_id in self.allowed or self.allow_unknown
    ret = (allowed, False, {'test': 'test'})

    if self.simulate_hang or action_id in self.hanging_actions:
        self.hanging_calls.append((ok_cb, ret))
    else:
        ok_cb(ret)


@dbus.service.method(MAIN_IFACE, in_signature='(sa{sv})ss')
def RegisterAuthenticationAgent(_self, _subject, _locale, _object_path):
    pass


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


@dbus.service.method(MOCK_IFACE, in_signature='d', out_signature='')
def SetDelay(self, delay):
    '''Makes the CheckAuthorization() method to delay'''
    self.delay = delay


@dbus.service.method(MOCK_IFACE, in_signature='b', out_signature='')
def SimulateHang(self, hang):
    '''Makes the CheckAuthorization() method to hang'''
    self.simulate_hang = hang


@dbus.service.method(MOCK_IFACE, in_signature='as', out_signature='')
def SimulateHangActions(self, actions):
    '''Makes the CheckAuthorization() method to hang on such actions'''
    self.hanging_actions = actions


@dbus.service.method(MOCK_IFACE, in_signature='', out_signature='')
def ReleaseHangingCalls(self):
    '''Calls all the hanging callbacks'''
    for (cb, ret) in self.hanging_calls:
        cb(ret)
    self.hanging_calls = []


@dbus.service.method(MOCK_IFACE, in_signature='', out_signature='b')
def HaveHangingCalls(self):
    '''Check if we've hangling calls'''
    return len(self.hanging_calls)
