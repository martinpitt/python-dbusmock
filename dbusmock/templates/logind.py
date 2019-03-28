'''systemd logind mock template

This creates the expected methods and properties of the main
org.freedesktop.login1.Manager object. You can specify D-Bus property values
like "CanSuspend" or the return value of Inhibit() in "parameters".
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
import os

from dbusmock import MOCK_IFACE, mockobject

BUS_NAME = 'org.freedesktop.login1'
MAIN_OBJ = '/org/freedesktop/login1'
MAIN_IFACE = 'org.freedesktop.login1.Manager'
SYSTEM_BUS = True


def load(mock, parameters):
    mock.AddMethods(MAIN_IFACE, [
        ('PowerOff', 'b', '', ''),
        ('Reboot', 'b', '', ''),
        ('Suspend', 'b', '', ''),
        ('Hibernate', 'b', '', ''),
        ('HybridSleep', 'b', '', ''),
        ('SuspendThenHibernate', 'b', '', ''),
        ('CanPowerOff', '', 's', 'ret = "%s"' % parameters.get('CanPowerOff', 'yes')),
        ('CanReboot', '', 's', 'ret = "%s"' % parameters.get('CanReboot', 'yes')),
        ('CanSuspend', '', 's', 'ret = "%s"' % parameters.get('CanSuspend', 'yes')),
        ('CanHibernate', '', 's', 'ret = "%s"' % parameters.get('CanHibernate', 'yes')),
        ('CanHybridSleep', '', 's', 'ret = "%s"' % parameters.get('CanHybridSleep', 'yes')),
        ('CanSuspendThenHibernate', '', 's', 'ret = "%s"' % parameters.get('CanSuspendThenHibernate', 'yes')),

        ('GetSession', 's', 'o', 'ret = "/org/freedesktop/login1/session/" + args[0]'),
        ('ActivateSession', 's', '', ''),
        ('ActivateSessionOnSeat', 'ss', '', ''),
        ('KillSession', 'sss', '', ''),
        ('LockSession', 's', '', ''),
        ('LockSessions', '', '', ''),
        ('ReleaseSession', 's', '', ''),
        ('TerminateSession', 's', '', ''),
        ('UnlockSession', 's', '', ''),
        ('UnlockSessions', '', '', ''),

        ('GetSeat', 's', 'o', 'ret = "/org/freedesktop/login1/seat/" + args[0]'),
        ('ListSeats', '', 'a(so)', 'ret = [(k.split("/")[-1], k) for k in objects.keys() if "/seat/" in k]'),
        ('TerminateSeat', 's', '', ''),

        ('GetUser', 'u', 'o', 'ret = "/org/freedesktop/login1/user/%u" % args[0]'),
        ('KillUser', 'us', '', ''),
        ('TerminateUser', 'u', '', ''),

        ('Inhibit', 'ssss', 'h', 'ret = %i' % parameters.get('Inhibit_fd', 3)),
        ('ListInhibitors', '', 'a(ssssuu)', 'ret = []'),
    ])

    mock.AddProperties(MAIN_IFACE,
                       dbus.Dictionary({
                           'IdleHint': parameters.get('IdleHint', False),
                           'IdleAction': parameters.get('IdleAction', 'ignore'),
                           'IdleSinceHint': dbus.UInt64(parameters.get('IdleSinceHint', 0)),
                           'IdleSinceHintMonotonic': dbus.UInt64(parameters.get('IdleSinceHintMonotonic', 0)),
                           'IdleActionUSec': dbus.UInt64(parameters.get('IdleActionUSec', 1)),
                           'PreparingForShutdown': parameters.get('PreparingForShutdown', False),
                           'PreparingForSleep': parameters.get('PreparingForSleep', False),
                       }, signature='sv'))


#
# logind methods which are too big for squeezing into AddMethod()
#

@dbus.service.method(MAIN_IFACE,
                     in_signature='',
                     out_signature='a(uso)')
def ListUsers(self):
    users = []
    for k, obj in mockobject.objects.items():
        if '/user/' in k:
            uid = dbus.UInt32(int(k.split("/")[-1]))
            users.append((uid, obj.Get('org.freedesktop.login1.User', 'Name'), k))
    return users


@dbus.service.method(MAIN_IFACE,
                     in_signature='',
                     out_signature='a(susso)')
def ListSessions(self):
    sessions = []
    for k, obj in mockobject.objects.items():
        if '/session/' in k:
            session_id = k.split("/")[-1]
            uid = obj.Get('org.freedesktop.login1.Session', 'User')[0]
            username = obj.Get('org.freedesktop.login1.Session', 'Name')
            seat = obj.Get('org.freedesktop.login1.Session', 'Seat')[0]
            sessions.append((session_id, uid, username, seat, k))
    return sessions

#
# Convenience methods on the mock
#


@dbus.service.method(MOCK_IFACE,
                     in_signature='s', out_signature='s')
def AddSeat(self, seat):
    '''Convenience method to add a seat.

    Return the object path of the new seat.
    '''
    seat_path = '/org/freedesktop/login1/seat/' + seat
    if seat_path in mockobject.objects:
        raise dbus.exceptions.DBusException('Seat %s already exists' % seat,
                                            name=MOCK_IFACE + '.SeatExists')

    self.AddObject(seat_path,
                   'org.freedesktop.login1.Seat',
                   {
                       'Sessions': dbus.Array([], signature='(so)'),
                       'CanGraphical': False,
                       'CanMultiSession': True,
                       'CanTTY': False,
                       'IdleHint': False,
                       'ActiveSession': ('', dbus.ObjectPath('/')),
                       'Id': seat,
                       'IdleSinceHint': dbus.UInt64(0),
                       'IdleSinceHintMonotonic': dbus.UInt64(0),
                   },
                   [
                       ('ActivateSession', 's', '', ''),
                       ('Terminate', '', '', '')
                   ])

    return seat_path


@dbus.service.method(MOCK_IFACE,
                     in_signature='usb', out_signature='s')
def AddUser(self, uid, username, active):
    '''Convenience method to add a user.

    Return the object path of the new user.
    '''
    user_path = '/org/freedesktop/login1/user/%i' % uid
    if user_path in mockobject.objects:
        raise dbus.exceptions.DBusException('User %i already exists' % uid,
                                            name=MOCK_IFACE + '.UserExists')

    self.AddObject(user_path,
                   'org.freedesktop.login1.User',
                   {
                       'Sessions': dbus.Array([], signature='(so)'),
                       'IdleHint': False,
                       'DefaultControlGroup': 'systemd:/user/' + username,
                       'Name': username,
                       'RuntimePath': '/run/user/%i' % uid,
                       'Service': '',
                       'State': (active and 'active' or 'online'),
                       'Display': ('', dbus.ObjectPath('/')),
                       'UID': dbus.UInt32(uid),
                       'GID': dbus.UInt32(uid),
                       'IdleSinceHint': dbus.UInt64(0),
                       'IdleSinceHintMonotonic': dbus.UInt64(0),
                       'Timestamp': dbus.UInt64(42),
                       'TimestampMonotonic': dbus.UInt64(42),
                   },
                   [
                       ('Kill', 's', '', ''),
                       ('Terminate', '', '', ''),
                   ])

    return user_path


@dbus.service.method(MOCK_IFACE,
                     in_signature='ssusb', out_signature='s')
def AddSession(self, session_id, seat, uid, username, active):
    '''Convenience method to add a session.

    If the given seat and/or user do not exit, they will be created.

    Return the object path of the new session.
    '''
    seat_path = dbus.ObjectPath('/org/freedesktop/login1/seat/' + seat)
    if seat_path not in mockobject.objects:
        self.AddSeat(seat)

    user_path = dbus.ObjectPath('/org/freedesktop/login1/user/%i' % uid)
    if user_path not in mockobject.objects:
        self.AddUser(uid, username, active)

    session_path = dbus.ObjectPath('/org/freedesktop/login1/session/' + session_id)
    if session_path in mockobject.objects:
        raise dbus.exceptions.DBusException('Session %s already exists' % session_id,
                                            name=MOCK_IFACE + '.SessionExists')

    self.AddObject(session_path,
                   'org.freedesktop.login1.Session',
                   {
                       'Controllers': dbus.Array([], signature='s'),
                       'ResetControllers': dbus.Array([], signature='s'),
                       'Active': active,
                       'IdleHint': False,
                       'KillProcesses': False,
                       'Remote': False,
                       'Class': 'user',
                       'DefaultControlGroup': 'systemd:/user/%s/%s' % (username, session_id),
                       'Display': os.getenv('DISPLAY', ''),
                       'Id': session_id,
                       'Name': username,
                       'RemoteHost': '',
                       'RemoteUser': '',
                       'Service': 'dbusmock',
                       'State': (active and 'active' or 'online'),
                       'TTY': '',
                       'Type': 'test',
                       'Seat': (seat, seat_path),
                       'User': (dbus.UInt32(uid), user_path),
                       'Audit': dbus.UInt32(0),
                       'Leader': dbus.UInt32(1),
                       'VTNr': dbus.UInt32(1),
                       'IdleSinceHint': dbus.UInt64(0),
                       'IdleSinceHintMonotonic': dbus.UInt64(0),
                       'Timestamp': dbus.UInt64(42),
                       'TimestampMonotonic': dbus.UInt64(42),
                   },
                   [
                       ('Activate', '', '', ''),
                       ('Kill', 'ss', '', ''),
                       ('Lock', '', '', ''),
                       ('SetIdleHint', 'b', '', ''),
                       ('Terminate', '', '', ''),
                       ('Unlock', '', '', ''),
                   ])

    # add session to seat
    obj_seat = mockobject.objects[seat_path]
    cur_sessions = obj_seat.Get('org.freedesktop.login1.Seat', 'Sessions')
    cur_sessions.append((session_id, session_path))
    obj_seat.Set('org.freedesktop.login1.Seat', 'Sessions', cur_sessions)
    obj_seat.Set('org.freedesktop.login1.Seat', 'ActiveSession', (session_id, session_path))

    # add session to user
    obj_user = mockobject.objects[user_path]
    cur_sessions = obj_user.Get('org.freedesktop.login1.User', 'Sessions')
    cur_sessions.append((session_id, session_path))
    obj_user.Set('org.freedesktop.login1.User', 'Sessions', cur_sessions)

    return session_path
