'''pytest fixtures for DBusMock'''

# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 3 of the License, or (at your option) any
# later version.  See http://www.gnu.org/copyleft/lgpl.html for the full text
# of the license.

__author__ = 'Martin Pitt'
__copyright__ = '(c) 2023 Martin Pitt <martin@piware.de>'

from typing import Iterator

import pytest

from dbusmock.testcase import BusType, PrivateDBus


@pytest.fixture(scope='session')
def dbusmock_system() -> Iterator[PrivateDBus]:
    '''Export the whole DBusTestCase as a fixture, with the system bus started'''

    with PrivateDBus(BusType.SYSTEM) as bus:
        yield bus


@pytest.fixture(scope='session')
def dbusmock_session() -> Iterator[PrivateDBus]:
    '''Export the whole DBusTestCase as a fixture, with the session bus started'''

    with PrivateDBus(BusType.SESSION) as bus:
        yield bus
