'''Accounts Service D-Bus mock template'''

# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 3 of the License, or (at your option) any
# later version.  See http://www.gnu.org/copyleft/lgpl.html for the full text
# of the license.

__author__ = 'Marco Trevisan'
__email__ = 'marco.trevisan@canonical.com'
__copyright__ = '(c) 2021 Canonical Ltd.'
__license__ = 'LGPL 3+'

import sys
import time

import dbus
from dbusmock import MOCK_IFACE, mockobject

BUS_NAME = 'org.freedesktop.Accounts'
MAIN_OBJ = '/org/freedesktop/Accounts'
MAIN_IFACE = 'org.freedesktop.Accounts'
USER_IFACE = MAIN_IFACE + '.User'
SYSTEM_BUS = True

DEFAULT_USER_PASSWORD = 'Pa$$wo0rd'


def get_user_path(uid):
    return f'/org/freedesktop/Accounts/User{uid}'


def load(mock, parameters=None):
    parameters = parameters if parameters else {}
    mock.mock_users = {}
    mock.cached_users = []
    mock.automatic_login_users = set()
    mock.users_auto_uids = 2000

    mock.AddProperties(MAIN_IFACE, mock.GetAll(MAIN_IFACE))

    for uid, name in parameters.get('users', {}).items():
        mock.AddUser(uid, name)


def emit_properties_changed(mock, interface=MAIN_IFACE, properties=None):
    if properties is None:
        properties = mock.GetAll(interface)
    elif isinstance(properties, str):
        properties = [properties]

    if isinstance(properties, (list, set)):
        properties = {p: mock.Get(interface, p) for p in properties}
    elif not isinstance(properties, dict):
        raise TypeError('Unsupported properties type')

    mock.EmitSignal(dbus.PROPERTIES_IFACE, 'PropertiesChanged', 'sa{sv}as', (
        interface, properties, []))


@dbus.service.method(MOCK_IFACE, in_signature='xssa{sv}a{sv}',
                     out_signature='o')
def AddUser(self, uid, username, password=DEFAULT_USER_PASSWORD,
            overrides=None, password_policy_overrides=None):
    '''Add user via uid and username and optionally overriding properties

    Returns the new object path.
   '''
    path = get_user_path(uid)
    default_props = {
        'Uid': dbus.UInt64(uid),
        'UserName': username,
        'RealName': username[0].upper() + username[1:] + ' Fake',
        'AccountType': dbus.Int32(1),
        'AutomaticLogin': False,
        'BackgroundFile': '',
        'Email': f'{username}@python-dbusmock.org',
        'FormatsLocale': 'C',
        'HomeDirectory': f'/nonexisting/mock-home/{username}',
        'IconFile': '',
        'InputSources': dbus.Array([], signature='a{ss}'),
        'Language': 'C',
        'LocalAccount': True,
        'Location': '',
        'Locked': False,
        'LoginFrequency': dbus.UInt64(0),
        'LoginHistory': dbus.Array([], signature='(xxa{sv})'),
        'LoginTime': dbus.Int64(0),
        'PasswordHint': 'Remember it, come on!',
        'PasswordMode': 0,
        'Session': 'mock-session',
        'SessionType': 'wayland',
        'Shell': '/usr/bin/zsh',
        'SystemAccount': False,
        'XHasMessages': False,
        'XKeyboardLayouts': dbus.Array([], signature='s'),
        'XSession': 'mock-xsession',
    }
    default_props.update(overrides if overrides else {})
    self.AddObject(path, USER_IFACE, default_props, [])

    had_users = len(self.mock_users) != 0
    had_multiple_users = len(self.mock_users) > 1
    user = mockobject.objects[path]
    user.password = password
    user.properties = default_props
    user.pwd_expiration_policy = {
        'expiration_time': sys.maxsize,
        'last_change_time': int(time.time()),
        'min_days_between_changes': 0,
        'max_days_between_changes': 0,
        'days_to_warn': 0,
        'days_after_expiration_until_lock': 0,
    }
    user.pwd_expiration_policy.update(
        password_policy_overrides if password_policy_overrides else {})
    self.mock_users[uid] = default_props

    self.EmitSignal(MAIN_IFACE, 'UserAdded', 'o', [path])

    if not had_users:
        emit_properties_changed(self, MAIN_IFACE, 'HasNoUsers')
    elif not had_multiple_users and len(self.mock_users) > 1:
        emit_properties_changed(self, MAIN_IFACE, 'HasMultipleUsers')

    return path


@dbus.service.method(MOCK_IFACE, in_signature='', out_signature='ao')
def ListMockUsers(self):
    """ List the mock users that have been created """
    return [get_user_path(uid) for uid in self.mock_users.keys()]


@dbus.service.method(MOCK_IFACE, in_signature='s', out_signature='o')
def AddAutoLoginUser(self, username):
    """ Enable autologin for an user """
    path = self.FindUserByName(username)
    self.automatic_login_users.add(path)
    user = mockobject.objects[path]
    set_user_property(user, 'AutomaticLogin', True)
    emit_properties_changed(self, MAIN_IFACE, 'AutomaticLoginUsers')
    return path


@dbus.service.method(MOCK_IFACE, in_signature='s', out_signature='o')
def RemoveAutoLoginUser(self, username):
    """ Disables autologin for an user """
    path = self.FindUserByName(username)
    self.automatic_login_users.remove(path)
    user = mockobject.objects[path]
    set_user_property(user, 'AutomaticLogin', False)
    emit_properties_changed(self, MAIN_IFACE, 'AutomaticLoginUsers')
    return path


@dbus.service.method(MAIN_IFACE, in_signature='ssi', out_signature='o')
def CreateUser(self, name, fullname, account_type):
    """ Creates an user using the default API """
    try:
        self.FindUserByName(name)
        found = True
    except dbus.exceptions.DBusException:
        found = False

    if found:
        raise dbus.exceptions.DBusException(f'User {name} already exists', name='org.freedesktop.Accounts.Error.Failed')

    self.users_auto_uids += 1

    return self.AddUser(self.users_auto_uids, name, DEFAULT_USER_PASSWORD, {
        'RealName': fullname, 'AccountType': account_type})


@dbus.service.method(MAIN_IFACE, in_signature='xb')
def DeleteUser(self, uid, _remove_files):
    """ Removes a created user """
    path = self.FindUserById(uid)

    had_multiple_users = len(self.mock_users) > 1
    self.RemoveObject(path)
    self.mock_users.pop(uid)
    self.automatic_login_users.discard(path)

    self.EmitSignal(MAIN_IFACE, 'UserDeleted', 'o', [path])

    if len(self.mock_users) == 0:
        emit_properties_changed(self, MAIN_IFACE, 'HasNoUsers')
    elif had_multiple_users and len(self.mock_users) < 2:
        emit_properties_changed(self, MAIN_IFACE, 'HasMultipleUsers')


@dbus.service.method(MAIN_IFACE, in_signature='s', out_signature='o')
def CacheUser(self, username):
    """ Cache an user """
    path = self.FindUserByName(username)
    self.cached_users.append(path)
    return path


@dbus.service.method(MAIN_IFACE, in_signature='s')
def UncacheUser(self, username):
    """ Removes an user from the cache """
    path = self.FindUserByName(username)
    self.cached_users.remove(path)


@dbus.service.method(MAIN_IFACE, in_signature='', out_signature='ao')
def ListCachedUsers(self):
    """ Lists the cached users """
    return self.cached_users


@dbus.service.method(MAIN_IFACE, in_signature='x', out_signature='o')
def FindUserById(_self, uid):
    """ Finds an user by its user id """
    user = mockobject.objects.get(get_user_path(uid), None)
    if not user:
        raise dbus.exceptions.DBusException(
            'No such user exists',
            name='org.freedesktop.Accounts.Error.Failed')
    return get_user_path(uid)


@dbus.service.method(MAIN_IFACE, in_signature='s', out_signature='o')
def FindUserByName(self, username):
    """ Finds an user form its name """
    try:
        [user_id] = [uid for uid, props in self.mock_users.items()
                     if props['UserName'] == username]
    except ValueError as e:
        raise dbus.exceptions.DBusException(f'No such user exists: {e}', name='org.freedesktop.Accounts.Error.Failed')
    return get_user_path(user_id)


@dbus.service.method(dbus.PROPERTIES_IFACE, in_signature='s',
                     out_signature='a{sv}')
def GetAll(self, interface):
    """ Implements the GetAll dbus properties interface method.

    This allows to override the getters using dynamic values.
    """
    if interface == MAIN_IFACE:
        return {
            'DaemonVersion': 'dbus-mock-0.1',
            'HasNoUsers': len(self.mock_users) == 0,
            'HasMultipleUsers': len(self.mock_users) > 1,
            'AutomaticLoginUsers': dbus.Array(self.automatic_login_users,
                                              signature='o'),
        }
    if interface == USER_IFACE:
        return self.properties
    return dbus.Dictionary({}, signature='sv')


@dbus.service.method(dbus.PROPERTIES_IFACE, in_signature='ss',
                     out_signature='v')
def Get(self, interface, prop):
    """ Implements the Get dbus properties interface method.

    This allows to override the getters using dynamic values, via GetAll.
    """
    return self.GetAll(interface)[prop]


def set_user_property(user, property_name, value):
    """ Set an user property and emits the relative signals """
    if user.properties[property_name] == value:
        return
    user.properties[property_name] = value
    emit_properties_changed(user, USER_IFACE, property_name)
    user.EmitSignal(USER_IFACE, 'Changed', '', [])


@dbus.service.method(USER_IFACE, in_signature='s')
def SetUserName(self, user_name):
    set_user_property(self, 'UserName', user_name)


@dbus.service.method(USER_IFACE, in_signature='s')
def SetRealName(self, real_name):
    set_user_property(self, 'RealName', real_name)


@dbus.service.method(USER_IFACE, in_signature='s')
def SetEmail(self, email):
    set_user_property(self, 'Email', email)


@dbus.service.method(USER_IFACE, in_signature='s')
def SetLanguage(self, language):
    set_user_property(self, 'Language', language)


@dbus.service.method(USER_IFACE, in_signature='s')
def SetXSession(self, x_session):
    set_user_property(self, 'XSession', x_session)


@dbus.service.method(USER_IFACE, in_signature='s')
def SetSession(self, session):
    set_user_property(self, 'Session', session)


@dbus.service.method(USER_IFACE, in_signature='s')
def SetSessionType(self, session_type):
    set_user_property(self, 'SessionType', session_type)


@dbus.service.method(USER_IFACE, in_signature='s')
def SetLocation(self, location):
    set_user_property(self, 'Location', location)


@dbus.service.method(USER_IFACE, in_signature='s')
def SetHomeDirectory(self, home_directory):
    set_user_property(self, 'HomeDirectory', home_directory)


@dbus.service.method(USER_IFACE, in_signature='s')
def SetShell(self, shell):
    set_user_property(self, 'Shell', shell)


@dbus.service.method(USER_IFACE, in_signature='s')
def SetIconFile(self, icon_file):
    set_user_property(self, 'IconFile', icon_file)


@dbus.service.method(USER_IFACE, in_signature='s')
def SetLocked(self, locked):
    set_user_property(self, 'Locked', locked)


@dbus.service.method(USER_IFACE, in_signature='i')
def SetAccountType(self, account_type):
    set_user_property(self, 'AccountType', account_type)


@dbus.service.method(USER_IFACE, in_signature='i')
def SetPasswordMode(self, password_mode):
    set_user_property(self, 'PasswordMode', password_mode)


@dbus.service.method(USER_IFACE, in_signature='s')
def SetPasswordHint(self, hint):
    set_user_property(self, 'PasswordHint', hint)


@dbus.service.method(USER_IFACE, in_signature='ss')
def SetPassword(self, password, hint):
    self.password = password
    self.SetPasswordHint(hint)


@dbus.service.method(USER_IFACE, in_signature='b')
def SetAutomaticLogin(self, automatic_login):
    manager = mockobject.objects[MAIN_OBJ]
    if automatic_login:
        manager.AddAutoLoginUser(self.properties['UserName'])
    else:
        manager.RemoveAutoLoginUser(self.properties['UserName'])


@dbus.service.method(MOCK_IFACE, in_signature='xxxxxxx')
def SetUserPasswordExpirationPolicy(self, uid, expiration_time,
                                    last_change_time, min_days_between_changes,
                                    max_days_between_changes, days_to_warn,
                                    days_after_expiration_until_lock):
    user = mockobject.objects[self.FindUserById(uid)]
    user.pwd_expiration_policy = {
        'expiration_time': expiration_time,
        'last_change_time': last_change_time,
        'min_days_between_changes': min_days_between_changes,
        'max_days_between_changes': max_days_between_changes,
        'days_to_warn': days_to_warn,
        'days_after_expiration_until_lock': days_after_expiration_until_lock,
    }
    user.EmitSignal(USER_IFACE, 'Changed', '', [])


@dbus.service.method(USER_IFACE, in_signature='', out_signature='xxxxxx')
def GetPasswordExpirationPolicy(self):
    return tuple(self.pwd_expiration_policy.values())
