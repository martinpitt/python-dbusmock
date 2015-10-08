'''notification-daemon mock template

This creates the expected methods and properties of the notification-daemon
services, but no devices. You can specify non-default capabilities in
"parameters".
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

BUS_NAME = 'org.freedesktop.Notifications'
MAIN_OBJ = '/org/freedesktop/Notifications'
MAIN_IFACE = 'org.freedesktop.Notifications'
SYSTEM_BUS = False

# default capabilities, can be modified with "capabilities" parameter
default_caps = ['body', 'body-markup', 'icon-static', 'image/svg+xml',
                'private-synchronous', 'append', 'private-icon-only',
                'truncation']


def load(mock, parameters):
    if 'capabilities' in parameters:
        caps = parameters['capabilities'].split()
    else:
        caps = default_caps

    # next notification ID
    mock.next_id = 1

    mock.AddMethods(MAIN_IFACE, [
        ('GetCapabilities', '', 'as', 'ret = %s' % repr(caps)),
        ('CloseNotification', 'i', '', 'if args[0] < self.next_id: self.EmitSignal('
                                       '"", "NotificationClosed", "uu", [args[0], 1])'),
        ('GetServerInformation', '', 'ssss', 'ret = ("mock-notify", "test vendor", "1.0", "1.1")'),
        ('Notify', 'susssasa{sv}i', 'u', '''if args[1]:
    ret = args[1]
else:
    ret = self.next_id
    self.next_id += 1
'''),
    ])
