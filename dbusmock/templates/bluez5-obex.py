'''obexd mock template

This creates the expected methods and properties of the object manager
org.bluez.obex object (/), the manager object (/org/bluez/obex), but no agents
or clients.

This supports BlueZ 5 only.
'''

# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 3 of the License, or (at your option) any
# later version.  See http://www.gnu.org/copyleft/lgpl.html for the full text
# of the license.

__author__ = 'Philip Withnall'
__email__ = 'philip.withnall@collabora.co.uk'
__copyright__ = '(c) 2013 Collabora Ltd.'
__license__ = 'LGPL 3+'

import dbus

from dbusmock import OBJECT_MANAGER_IFACE, mockobject

BUS_NAME = 'org.bluez.obex'
MAIN_OBJ = '/'
SYSTEM_BUS = False
IS_OBJECT_MANAGER = True

OBEX_MOCK_IFACE = 'org.bluez.obex.Mock'
AGENT_MANAGER_IFACE = 'org.bluez.AgentManager1'
CLIENT_IFACE = 'org.bluez.obex.Client1'
SESSION_IFACE = 'org.bluez.obex.Session1'
PHONEBOOK_ACCESS_IFACE = 'org.bluez.obex.PhonebookAccess1'
TRANSFER_IFACE = 'org.bluez.obex.Transfer1'
TRANSFER_MOCK_IFACE = 'org.bluez.obex.transfer1.Mock'


def load(mock, parameters):
    mock.AddObject('/org/bluez/obex', AGENT_MANAGER_IFACE, {}, [
        ('RegisterAgent', 'os', '', ''),
        ('UnregisterAgent', 'o', '', ''),
    ])

    obex = mockobject.objects['/org/bluez/obex']
    obex.AddMethods (CLIENT_IFACE, [
        ('CreateSession', 'sa{sv}', 'o', CreateSession),
        ('RemoveSession', 'o', '', RemoveSession),
    ])


@dbus.service.method(CLIENT_IFACE,
                     in_signature='sa{sv}', out_signature='o')
def CreateSession(self, destination, args):
    '''OBEX method to create a new transfer session.

    The destination must be the address of the destination Bluetooth device. The
    given arguments must be a map from well-known keys to values, containing at
    least the ‘Target’ key, whose value must be ‘PBAP’ (other keys and values
    are accepted by the real daemon, but not by this mock daemon at the moment).
    If the target is missing or incorrect, an Unsupported error is returned on
    the bus.

    Returns the path of a new Session object.
    '''

    if 'Target' not in args or args['Target'].upper() != 'PBAP':
        raise dbus.exceptions.DBusException(OBEX_MOCK_IFACE + '.Unsupported',
                                            'Non-PBAP targets are not ' +
                                            'currently supported by this ' +
                                            'python-dbusmock template.')

    # Find the first unused session ID.
    client_path = '/org/bluez/obex/client'
    session_id = 0
    while client_path + '/session' + str(session_id) in mockobject.objects:
        session_id += 1

    path = client_path + '/session' + str(session_id)
    properties = {
        'Source': dbus.String('FIXME', variant_level=1),
        'Destination': dbus.String(destination, variant_level=1),
        'Channel': dbus.Byte(0, variant_level=1),
        'Target': dbus.String('FIXME', variant_level=1),
        'Root': dbus.String('FIXME', variant_level=1),
    }

    self.AddObject(path,
                   SESSION_IFACE,
                   # Properties
                   properties,
                   # Methods
                   [
                       ('GetCapabilities', '', 's', ''),  # Currently a no-op
                   ])

    session = mockobject.objects[path]
    session.AddMethods(PHONEBOOK_ACCESS_IFACE, [
        ('Select', 'ss', '', ''),  # Currently a no-op
        ('List', 'a{sv}', 'a(ss)', ''),  # Currently a no-op
        ('ListFilterFields', '', 'as', ''),  # Currently a no-op
        ('PullAll', 'sa{sv}', 'sa{sv}', PullAll),
    ])

    manager = mockobject.objects['/']
    manager.EmitSignal(OBJECT_MANAGER_IFACE, 'InterfacesAdded',
        'oa{sa{sv}}', [
            dbus.ObjectPath(path),
            { SESSION_IFACE: properties },
        ])

    return path


@dbus.service.method(CLIENT_IFACE,
                     in_signature='o', out_signature='')
def RemoveSession(self, session_path):
    '''OBEX method to remove an existing transfer session.

    This takes the path of the transfer Session object and removes it.
    '''

    manager = mockobject.objects['/']

    # Remove all the session's transfers.
    transfer_id = 0
    while session_path + '/transfer' + str(transfer_id) in mockobject.objects:
        transfer_path = session_path + '/transfer' + str(transfer_id)
        transfer_id += 1

        self.RemoveObject(transfer_path)

        manager.EmitSignal(OBJECT_MANAGER_IFACE, 'InterfacesRemoved',
            'oas', [
                dbus.ObjectPath(transfer_path),
                [ TRANSFER_IFACE ],
            ])

    # Remove the session itself.
    self.RemoveObject(session_path)

    manager.EmitSignal(OBJECT_MANAGER_IFACE, 'InterfacesRemoved',
        'oas', [
            dbus.ObjectPath(session_path),
            [ SESSION_IFACE, PHONEBOOK_ACCESS_IFACE ],
        ])


@dbus.service.method(PHONEBOOK_ACCESS_IFACE,
                     in_signature='sa{sv}', out_signature='sa{sv}')
def PullAll(self, target_file, filters):
    '''OBEX method to start a pull transfer of a phone book.

    This doesn't complete the transfer; code to mock up activating and
    completing the transfer must be provided by the test driver, as it’s
    too complex and test-specific to put here.

    The target_file is the absolute path for a file which will have zero or more
    vCards, separated by new-line characters, written to it if the method is
    successful (and the transfer is completed). This target_file is actually
    emitted in a TransferCreated signal, which is a special part of the mock
    interface designed to be handled by the test driver, which should then
    populate that file and call Activate and Create on the Session.

    The filters parameter is a map of filters to be applied to the results
    device-side before transmitting them back to the adapter.

    Returns a tuple containing the path for a new Transfer D-Bus object
    representing the transfer, and a map of the initial properties of that
    Transfer object.
    '''

    # Find the first unused session ID.
    session_path = self.path
    transfer_id = 0
    while session_path + '/transfer' + str(transfer_id) in mockobject.objects:
        transfer_id += 1

    transfer_path = session_path + '/transfer' + str(transfer_id)
    props = {
        'Status': dbus.String('queued', variant_level=1),
        'Session': dbus.ObjectPath(session_path,
                                   variant_level=1),
        'Name': dbus.String(target_file, variant_level=1),
    }

    self.AddObject(transfer_path,
                   TRANSFER_IFACE,
                   # Properties
                   props,
                   # Methods
                   [
                       ('Cancel', '', '', ''),  # Currently a no-op
                   ])

    transfer = mockobject.objects[transfer_path]
    transfer.AddMethods (TRANSFER_MOCK_IFACE, [
        ('Activate', '', '', Activate),
        ('Complete', 's', '', Complete),
    ])

    manager = mockobject.objects['/']
    manager.EmitSignal(OBJECT_MANAGER_IFACE, 'InterfacesAdded',
        'oa{sa{sv}}', [
            dbus.ObjectPath(transfer_path),
            { TRANSFER_IFACE: props },
        ])

    # Emit a behind-the-scenes signal that a new transfer has been created.
    manager.EmitSignal(OBEX_MOCK_IFACE, 'TransferCreated', 'sa{sv}',
                       [transfer_path, filters])

    return (transfer_path, props)


@dbus.service.signal(OBEX_MOCK_IFACE, signature='sa{sv}')
def TransferCreated(self, path, filters):
    '''Mock signal emitted when a new Transfer object is created.

    This is not part of the BlueZ OBEX interface; it is purely for use by test
    driver code. It is emitted by the PullAll method, and is intended to be
    used as a signal to call Activate and Complete on the newly created Transfer
    (potentially after a timeout).

    The path is of the new Transfer object, and the filters are as provided to
    PullAll.
    '''
    pass


@dbus.service.method(TRANSFER_MOCK_IFACE,
                     in_signature='', out_signature='')
def Activate(self):
    '''Mock method to activate the transfer.

    This marks the transfer as active, and sets it as having an arbitrary
    number of bytes transferred already.
    '''
    self.Set(TRANSFER_IFACE, 'Status', dbus.String('active', variant_level=1))
    self.AddProperty(TRANSFER_IFACE, 'Transferred',
                     dbus.UInt64(123, variant_level=1))

    self.EmitSignal(dbus.PROPERTIES_IFACE, 'PropertiesChanged', 'sa{sv}as', [
        TRANSFER_IFACE,
        {
            'Status': dbus.String('active', variant_level=1),
            'Transferred': dbus.UInt64(123, variant_level=1),
        },
        [],
    ])


@dbus.service.method(TRANSFER_MOCK_IFACE,
                     in_signature='s', out_signature='')
def Complete(self, filename):
    '''Mock method to complete the transfer.

    This marks the transfer as complete, and sets it as having a larger number
    of bytes transferred than Active does.

    The given filename is set as the Transfer’s Filename property, and should
    have already been created by the test driver code with zero or more vCards,
    separated by new-line characters.
    '''
    self.Set(TRANSFER_IFACE, 'Status', dbus.String('complete', variant_level=1))
    self.AddProperties(TRANSFER_IFACE, {
        'Transferred': dbus.UInt64(999, variant_level=1),
        'Filename': dbus.String(filename, variant_level=1),
    })

    self.EmitSignal(dbus.PROPERTIES_IFACE, 'PropertiesChanged', 'sa{sv}as', [
        TRANSFER_IFACE,
        {
            'Status': dbus.String('complete', variant_level=1),
            'Transferred': dbus.UInt64(999, variant_level=1),
            'Filename': dbus.String(filename, variant_level=1),
        },
        [],
    ])

