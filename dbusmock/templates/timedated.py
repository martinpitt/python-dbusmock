'''systemd timedated mock template

This creates the expected methods and properties of the main
org.freedesktop.timedate object. You can specify D-BUS property values like
"Timezone" or "NTP" in "parameters".
'''

# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 3 of the License, or (at your option) any
# later version.  See http://www.gnu.org/copyleft/lgpl.html for the full text
# of the license.

__author__ = 'Iain Lane'
__email__ = 'iain.lane@canonical.com'
__copyright__ = '(c) 2013 Canonical Ltd.'
__license__ = 'LGPL 3+'

import dbus

BUS_NAME = 'org.freedesktop.timedate1'
MAIN_OBJ = '/org/freedesktop/timedate1'
MAIN_IFACE = 'org.freedesktop.timedate1'
SYSTEM_BUS = True


def setProperty(prop):
    return 'self.Set("%s", "%s", args[0])' % (MAIN_IFACE, prop)


def load(mock, parameters):
    mock.AddMethods(MAIN_IFACE, [
        # There's nothing this can usefully do, but provide it for compatibility
        ('SetTime', 'xbb', '', ''),
        ('SetTimezone', 'sb', '', setProperty('Timezone')),
        ('SetLocalRTC', 'bbb', '', setProperty('LocalRTC')),
        ('SetNTP', 'bb', '', setProperty('NTP') + '; ' + setProperty('NTPSynchronized'))
    ])

    mock.AddProperties(MAIN_IFACE,
                       dbus.Dictionary({
                           'Timezone': parameters.get('Timezone', 'Etc/Utc'),
                           'LocalRTC': parameters.get('LocalRTC', False),
                           'NTP': parameters.get('NTP', True),
                           'NTPSynchronized': parameters.get('NTP', True),
                           'CanNTP': parameters.get('CanNTP', True)
                       }, signature='sv'))
