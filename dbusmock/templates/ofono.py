'''ofonod D-Bus mock template'''

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

import dbusmock

BUS_NAME = 'org.ofono'
MAIN_OBJ = '/'
MAIN_IFACE = 'org.ofono.Manager'
SYSTEM_BUS = True

NOT_IMPLEMENTED = 'raise dbus.exceptions.DBusException("not implemented", name="org.ofono.Error.NotImplemented")'


#  interface org.ofono.Manager {
#    methods:
#      GetModems(out a(oa{sv}) modems);
#    signals:
#      ModemAdded(o path,
#                 a{sv} properties);
#      ModemRemoved(o path);
#  };

_parameters = {}


def load(mock, parameters):
    global _parameters
    mock.modems = []  # object paths
    mock.modem_serial_counter = 0
    mock.imsi_counter = 0
    mock.iccid_counter = 0
    _parameters = parameters
    mock.AddMethod(MAIN_IFACE, 'GetModems', '', 'a(oa{sv})',
                   'ret = [(m, objects[m].GetAll("org.ofono.Modem")) for m in self.modems]')

    if not parameters.get('no_modem', False):
        mock.AddModem(parameters.get('ModemName', 'ril_0'), {})


#  interface org.ofono.Modem {
#    methods:
#      GetProperties(out a{sv} properties);
#      SetProperty(in  s property,
#                  in  v value);
#    signals:
#      PropertyChanged(s name,
#                      v value);
#  };

@dbus.service.method(dbusmock.MOCK_IFACE,
                     in_signature='sa{sv}', out_signature='s')
def AddModem(self, name, properties):
    '''Convenience method to add a modem

    You have to specify a device name which must be a valid part of an object
    path, e. g. "mock_ac". For future extensions you can specify a "properties"
    array, but no extra properties are supported for now.

    Returns the new object path.
    '''
    path = '/' + name
    self.AddObject(path,
                   'org.ofono.Modem',
                   {
                       'Online': dbus.Boolean(True, variant_level=1),
                       'Powered': dbus.Boolean(True, variant_level=1),
                       'Lockdown': dbus.Boolean(False, variant_level=1),
                       'Emergency': dbus.Boolean(False, variant_level=1),
                       'Manufacturer': dbus.String('Fakesys', variant_level=1),
                       'Model': dbus.String('Mock Modem', variant_level=1),
                       'Revision': dbus.String('0815.42', variant_level=1),
                       'Serial': dbus.String(new_modem_serial(self), variant_level=1),
                       'Type': dbus.String('hardware', variant_level=1),
                       'Interfaces': ['org.ofono.CallVolume',
                                      'org.ofono.VoiceCallManager',
                                      'org.ofono.NetworkRegistration',
                                      'org.ofono.SimManager',
                                      # 'org.ofono.MessageManager',
                                      'org.ofono.ConnectionManager',
                                      # 'org.ofono.NetworkTime'
                                     ],
                       # 'Features': ['sms', 'net', 'gprs', 'sim']
                       'Features': ['gprs', 'net'],
                   },
                   [
                       ('GetProperties', '', 'a{sv}', 'ret = self.GetAll("org.ofono.Modem")'),
                       ('SetProperty', 'sv', '', 'self.Set("org.ofono.Modem", args[0], args[1]); '
                                                 'self.EmitSignal("org.ofono.Modem", "PropertyChanged",'
                                                 ' "sv", [args[0], args[1]])'),
                   ]
                  )
    obj = dbusmock.mockobject.objects[path]
    obj.name = name
    add_voice_call_api(obj)
    add_netreg_api(obj)
    add_simmanager_api(self, obj)
    add_connectionmanager_api(obj)
    self.modems.append(path)
    props = obj.GetAll('org.ofono.Modem', dbus_interface=dbus.PROPERTIES_IFACE)
    self.EmitSignal(MAIN_IFACE, 'ModemAdded', 'oa{sv}', [path, props])
    return path


# Generate a new modem serial number so each modem we add gets a unique one.
# Use a counter so that the result is predictable for tests.
def new_modem_serial(mock):
    serial = '12345678-1234-1234-1234-' + ('%012d' % mock.modem_serial_counter)
    mock.modem_serial_counter += 1
    return serial


# Generate a new unique IMSI (start with USA/AT&T 310/150 to match the MCC/MNC SIM properties)
# Use a counter so that the result is predictable for tests.
def new_imsi(mock):
    imsi = '310150' + ('%09d' % mock.imsi_counter)
    mock.imsi_counter += 1
    return imsi


# Generate a new unique ICCID
# Use a counter so that the result is predictable for tests.
def new_iccid(mock):
    iccid = '893581234' + ('%012d' % mock.iccid_counter)
    mock.iccid_counter += 1
    return iccid

#  interface org.ofono.VoiceCallManager {
#    methods:
#      GetProperties(out a{sv} properties);
#      Dial(in  s number,
#           in  s hide_callerid,
#           out o path);
#      Transfer();
#      SwapCalls();
#      ReleaseAndAnswer();
#      ReleaseAndSwap();
#      HoldAndAnswer();
#      HangupAll();
#      PrivateChat(in  o call,
#                  out ao calls);
#      CreateMultiparty(out o calls);
#      HangupMultiparty();
#      SendTones(in  s SendTones);
#      GetCalls(out a(oa{sv}) calls_with_properties);
#    signals:
#      Forwarded(s type);
#      BarringActive(s type);
#      PropertyChanged(s name,
#                      v value);
#      CallAdded(o path,
#                a{sv} properties);
#      CallRemoved(o path);
#  };


def add_voice_call_api(mock):
    '''Add org.ofono.VoiceCallManager API to a mock'''

    # also add an emergency number which is not a real one, in case one runs a
    # test case against a production ofono :-)
    mock.AddProperty('org.ofono.VoiceCallManager', 'EmergencyNumbers', ['911', '13373'])

    mock.calls = []  # object paths

    mock.AddMethods('org.ofono.VoiceCallManager', [
        ('GetProperties', '', 'a{sv}', 'ret = self.GetAll("org.ofono.VoiceCallManager")'),
        ('Transfer', '', '', ''),
        ('SwapCalls', '', '', ''),
        ('ReleaseAndAnswer', '', '', ''),
        ('ReleaseAndSwap', '', '', ''),
        ('HoldAndAnswer', '', '', ''),
        ('SendTones', 's', '', ''),
        ('PrivateChat', 'o', 'ao', NOT_IMPLEMENTED),
        ('CreateMultiparty', '', 'o', NOT_IMPLEMENTED),
        ('HangupMultiparty', '', '', NOT_IMPLEMENTED),
        ('GetCalls', '', 'a(oa{sv})', 'ret = [(c, objects[c].GetAll("org.ofono.VoiceCall")) for c in self.calls]')
    ])


@dbus.service.method('org.ofono.VoiceCallManager',
                     in_signature='ss', out_signature='s')
def Dial(self, number, hide_callerid):
    path = self._object_path + '/voicecall%02i' % (len(self.calls) + 1)
    self.AddObject(path, 'org.ofono.VoiceCall',
                   {
                       'State': dbus.String('dialing', variant_level=1),
                       'LineIdentification': dbus.String(number, variant_level=1),
                       'Name': dbus.String('', variant_level=1),
                       'Multiparty': dbus.Boolean(False, variant_level=1),
                       'RemoteHeld': dbus.Boolean(False, variant_level=1),
                       'RemoteMultiparty': dbus.Boolean(False, variant_level=1),
                       'Emergency': dbus.Boolean(False, variant_level=1),
                   },
                   [
                       ('GetProperties', '', 'a{sv}', 'ret = self.GetAll("org.ofono.VoiceCall")'),
                       ('Deflect', 's', '', NOT_IMPLEMENTED),
                       ('Hangup', '', '', 'self.parent.calls.remove(self._object_path);'
                        'self.parent.RemoveObject(self._object_path);'
                        'self.EmitSignal("org.ofono.VoiceCallManager", "CallRemoved", "o", [self._object_path])'),
                       ('Answer', '', '', NOT_IMPLEMENTED),
                   ]
                  )
    obj = dbusmock.mockobject.objects[path]
    obj.parent = self
    self.calls.append(path)
    self.EmitSignal('org.ofono.VoiceCallManager', 'CallAdded', 'oa{sv}',
                    [path, obj.GetProperties()])
    return path


@dbus.service.method('org.ofono.VoiceCallManager',
                     in_signature='', out_signature='')
def HangupAll(self):
    print('XXX HangupAll', self.calls)
    for c in list(self.calls):  # needs a copy
        dbusmock.mockobject.objects[c].Hangup()
    assert self.calls == []


#  interface org.ofono.NetworkRegistration {
#    methods:
#      GetProperties(out a{sv} properties);
#      SetProperty(in s property,
#                  in v value);
#      Register();
#      GetOperators(out a(oa{sv}) operators_with_properties);
#      Scan(out a(oa{sv}) operators_with_properties);
#    signals:
#      PropertyChanged(s name,
#                      v value);
#  };
#
#  for /<modem>/operator/<CountryCode><NetworkCode>:
#  interface org.ofono.NetworkOperator {
#          methods:
#            GetProperties(out a{sv} properties);
#            Register();
#          signals:
#            PropertyChanged(s name,
#                                                  v value);
#          properties:
#        };

def get_all_operators(mock):
    return 'ret = [(m, objects[m].GetAll("org.ofono.NetworkOperator")) ' \
           'for m in objects if "%s/operator/" in m]' % mock.name


def add_netreg_api(mock):
    '''Add org.ofono.NetworkRegistration API to a mock'''

    # also add an emergency number which is not a real one, in case one runs a
    # test case against a production ofono :-)
    mock.AddProperties('org.ofono.NetworkRegistration', {
        'Mode': 'auto',
        'Status': 'registered',
        'LocationAreaCode': _parameters.get('LocationAreaCode', 987),
        'CellId': _parameters.get('CellId', 10203),
        'MobileCountryCode': _parameters.get('MobileCountryCode', '777'),
        'MobileNetworkCode': _parameters.get('MobileNetworkCode', '11'),
        'Technology': _parameters.get('Technology', 'gsm'),
        'Name': _parameters.get('Name', 'fake.tel'),
        'Strength': _parameters.get('Strength', dbus.Byte(80)),
        'BaseStation': _parameters.get('BaseStation', ''),
    })

    mock.AddObject('/%s/operator/op1' % mock.name,
                   'org.ofono.NetworkOperator',
                   {
                       'Name': _parameters.get('Name', 'fake.tel'),
                       'Status': 'current',
                       'MobileCountryCode': _parameters.get('MobileCountryCode', '777'),
                       'MobileNetworkCode': _parameters.get('MobileNetworkCode', '11'),
                       'Technologies': [_parameters.get('Technology', 'gsm')],
                   },
                   [
                       ('GetProperties', '', 'a{sv}', 'ret = self.GetAll("org.ofono.NetworkOperator")'),
                       ('Register', '', '', ''),
                   ]  # noqa: silly pep8 error here about hanging indent
                  )

    mock.AddMethods('org.ofono.NetworkRegistration', [
        ('GetProperties', '', 'a{sv}', 'ret = self.GetAll("org.ofono.NetworkRegistration")'),
        ('SetProperty', 'sv', '', 'self.Set("%(i)s", args[0], args[1]); '
         'self.EmitSignal("%(i)s", "PropertyChanged", "sv", [args[0], args[1]])' % {'i': 'org.ofono.NetworkRegistration'}),
        ('Register', '', '', ''),
        ('GetOperators', '', 'a(oa{sv})', get_all_operators(mock)),
        ('Scan', '', 'a(oa{sv})', get_all_operators(mock)),
    ])


#  interface org.ofono.SimManager {
#    methods:
#      GetProperties(out a{sv} properties);
#      SetProperty(in  s property,
#                  in  v value);
#      ChangePin(in  s type,
#                in  s oldpin,
#                in  s newpin);
#      EnterPin(in  s type,
#               in  s pin);
#      ResetPin(in  s type,
#               in  s puk,
#               in  s newpin);
#      LockPin(in  s type,
#              in  s pin);
#      UnlockPin(in  s type,
#                in  s pin);
#      GetIcon(in  y id,
#              out ay icon);
#    signals:
#      PropertyChanged(s name,
#                      v value);
#  };

def add_simmanager_api(self, mock):
    '''Add org.ofono.SimManager API to a mock'''

    iface = 'org.ofono.SimManager'
    mock.AddProperties(iface, {
        'BarredDialing': _parameters.get('BarredDialing', False),
        'CardIdentifier': _parameters.get('CardIdentifier', new_iccid(self)),
        'FixedDialing': _parameters.get('FixedDialing', False),
        'LockedPins': _parameters.get('LockedPins', dbus.Array([], signature='s')),
        'MobileCountryCode': _parameters.get('MobileCountryCode', '310'),
        'MobileNetworkCode': _parameters.get('MobileNetworkCode', '150'),
        'PreferredLanguages': _parameters.get('PreferredLanguages', ['en']),
        'Present': _parameters.get('Present', dbus.Boolean(True)),
        'Retries': _parameters.get('Retries', dbus.Dictionary([["pin", dbus.Byte(3)], ["puk", dbus.Byte(10)]])),
        'PinRequired': _parameters.get('PinRequired', "none"),
        'SubscriberNumbers': _parameters.get('SubscriberNumbers', ['123456789', '234567890']),
        'SubscriberIdentity': _parameters.get('SubscriberIdentity', new_imsi(self)),
    })
    mock.AddMethods(iface, [
        ('GetProperties', '', 'a{sv}', 'ret = self.GetAll("%s")' % iface),
        ('SetProperty', 'sv', '', 'self.Set("%(i)s", args[0], args[1]); '
         'self.EmitSignal("%(i)s", "PropertyChanged", "sv", [args[0], args[1]])' % {'i': iface}),
        ('ChangePin', 'sss', '', ''),

        ('EnterPin', 'ss', '',
         'correctPin = "1234"\n'
         'newRetries = self.Get("%(i)s", "Retries")\n'
         'if args[0] == "pin" and args[1] != correctPin:\n'
         '    newRetries["pin"] = dbus.Byte(newRetries["pin"] - 1)\n'
         'elif args[0] == "pin":\n'
         '    newRetries["pin"] = dbus.Byte(3)\n'

         'self.Set("%(i)s", "Retries", newRetries)\n'
         'self.EmitSignal("%(i)s", "PropertyChanged", "sv", ["Retries", newRetries])\n'

         'if args[0] == "pin" and args[1] != correctPin:\n'
         '    class Failed(dbus.exceptions.DBusException):\n'
         '        _dbus_error_name = "org.ofono.Error.Failed"\n'
         '    raise Failed("Operation failed")' % {'i': iface}),

        ('ResetPin', 'sss', '',
         'correctPuk = "12345678"\n'
         'newRetries = self.Get("%(i)s", "Retries")\n'
         'if args[0] == "puk" and args[1] != correctPuk:\n'
         '    newRetries["puk"] = dbus.Byte(newRetries["puk"] - 1)\n'
         'elif args[0] == "puk":\n'
         '    newRetries["pin"] = dbus.Byte(3)\n'
         '    newRetries["puk"] = dbus.Byte(10)\n'

         'self.Set("%(i)s", "Retries", newRetries)\n'
         'self.EmitSignal("%(i)s", "PropertyChanged", "sv", ["Retries", newRetries])\n'

         'if args[0] == "puk" and args[1] != correctPuk:\n'
         '    class Failed(dbus.exceptions.DBusException):\n'
         '        _dbus_error_name = "org.ofono.Error.Failed"\n'
         '    raise Failed("Operation failed")' % {'i': iface}),

        ('LockPin', 'ss', '', ''),
        ('UnlockPin', 'ss', '', ''),
    ])


#  interface org.ofono.ConnectionManager {
#    methods:
#      GetProperties(out a{sv} properties);
#      SetProperty(in  s property,
#                  in  v value);
#      AddContext(in  s type,
#                 out o path);
#      RemoveContext(in  o path);
#      DeactivateAll();
#      GetContexts(out a(oa{sv}) contexts_with_properties);
#    signals:
#      PropertyChanged(s name,
#                      v value);
#      ContextAdded(o path,
#                   v properties);
#      ContextRemoved(o path);
#  };
def add_connectionmanager_api(mock):
    '''Add org.ofono.ConnectionManager API to a mock'''

    iface = 'org.ofono.ConnectionManager'
    mock.AddProperties(iface, {
        'Attached': _parameters.get('Attached', True),
        'Bearer': _parameters.get('Bearer', 'gprs'),
        'RoamingAllowed': _parameters.get('RoamingAllowed', False),
        'Powered': _parameters.get('ConnectionPowered', True),
    })
    mock.AddMethods(iface, [
        ('GetProperties', '', 'a{sv}', 'ret = self.GetAll("%s")' % iface),
        ('SetProperty', 'sv', '', 'self.Set("%(i)s", args[0], args[1]); '
         'self.EmitSignal("%(i)s", "PropertyChanged", "sv", [args[0], args[1]])' % {'i': iface}),
        ('AddContext', 's', 'o', 'ret = "/"'),
        ('RemoveContext', 'o', '', ''),
        ('DeactivateAll', '', '', ''),
        ('GetContexts', '', 'a(oa{sv})', 'ret = dbus.Array([])'),
    ])

# unimplemented Modem object interfaces:
#
#  interface org.ofono.NetworkTime {
#    methods:
#      GetNetworkTime(out a{sv} time);
#    signals:
#      NetworkTimeChanged(a{sv} time);
#    properties:
#  };
#  interface org.ofono.MessageManager {
#    methods:
#      GetProperties(out a{sv} properties);
#      SetProperty(in  s property,
#                  in  v value);
#      SendMessage(in  s to,
#                  in  s text,
#                  out o path);
#      GetMessages(out a(oa{sv}) messages);
#    signals:
#      PropertyChanged(s name,
#                      v value);
#      IncomingMessage(s message,
#                      a{sv} info);
#      ImmediateMessage(s message,
#                       a{sv} info);
#      MessageAdded(o path,
#                   a{sv} properties);
#      MessageRemoved(o path);
#  };
#  interface org.ofono.CallVolume {
#    methods:
#      GetProperties(out a{sv} properties);
#      SetProperty(in  s property,
#                  in  v value);
#    signals:
#      PropertyChanged(s property,
#                      v value);
#  };
