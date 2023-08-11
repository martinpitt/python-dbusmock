'''pytest convenience methods for DBusMocks'''

# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 3 of the License, or (at your option) any
# later version.  See http://www.gnu.org/copyleft/lgpl.html for the full text
# of the license.

import pytest
from typing import Iterator, Optional

import pytest
import dbus
import dbusmock


class BusMock(dbusmock.DBusTestCase):
    def __init__(self):
        super().__init__()
        self._dbus_con: Optional[dbus.Bus] = None

    @property
    def dbus_con(self) -> "dbus.Bus":
        '''
        Returns the dbus.bus.BusConnection() for this object. This returns either
        the session bus connection or the system bus connection, depending on the
        object.
        '''
        assert self._dbus_con is not None
        return self._dbus_con


@pytest.fixture(scope='session')
def session_mock() -> Iterator[BusMock]:
    '''
    Fixture to yield a DBusTestCase with a started session bus.
    '''
    bus = BusMock()
    bus.setUp()
    bus.start_session_bus()
    bus._dbus_con = bus.get_dbus(system_bus=False)
    yield bus
    bus.tearDown()
    bus.tearDownClass()


@pytest.fixture(scope='session')
def system_mock() -> Iterator[BusMock]:
    '''
    Fixture to yield a DBusTestCase with a started session bus.
    '''
    bus = BusMock()
    bus.setUp()
    bus.start_system_bus()
    bus._dbus_con = bus.get_dbus(system_bus=True)
    yield bus
    bus.tearDown()
    bus.tearDownClass()
