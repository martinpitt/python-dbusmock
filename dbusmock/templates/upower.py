'''upowerd mock template

This creates the expected methods and properties of the main
org.freedesktop.UPower object, but no devices. You can specify any property
such as 'OnLowBattery' or the return value of 'SuspendAllowed' and
'HibernateAllowed' in "parameters".
'''

# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 3 of the License, or (at your option) any
# later version.  See http://www.gnu.org/copyleft/lgpl.html for the full text
# of the license.

__author__ = 'Martin Pitt'
__email__ = 'martin.pitt@ubuntu.com'
__copyright__ = '(c) 2012 Canonical Ltd.'
__license__ = 'LGPL 3+'

import dbus


def load(mock, parameters):
    mock.AddMethods('', [
        ('Suspend', '', '', ''),
        ('SuspendAllowed', '', 'b', 'ret = %s' % parameters.get('SuspendAllowed', True)),
        ('HibernateAllowed', '', 'b', 'ret = %s' % parameters.get('HibernateAllowed', True)),
        ('EnumerateDevices', '', 'ao', 'ret = [k for k in objects.keys() if "/devices" in k]'),
    ])

    mock.AddProperties('org.freedesktop.UPower',
                       dbus.Dictionary({
                           'DaemonVersion': parameters.get('DaemonVersion', '0.8.15'),
                           'CanSuspend': parameters.get('CanSuspend', True),
                           'CanHibernate': parameters.get('CanHibernate', True),
                           'OnBattery': parameters.get('OnBattery', False),
                           'OnLowBattery': parameters.get('OnLowBattery', True),
                           'LidIsPresent': parameters.get('LidIsPresent', True),
                           'LidIsClosed': parameters.get('LidIsClosed', True),
                           'LidForceSleep': parameters.get('LidForceSleep', True),
                           'IsDocked': parameters.get('IsDocked', False),
                       }, signature='sv'))
