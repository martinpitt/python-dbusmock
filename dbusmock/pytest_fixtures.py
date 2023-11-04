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

import dbusmock.testcase


@pytest.fixture(name='dbusmock_test', scope='session')
def fixture_dbusmock_test() -> Iterator[dbusmock.testcase.DBusTestCase]:
    '''Export the whole DBusTestCase as a fixture.'''

    class _MockFixture(dbusmock.testcase.DBusTestCase):
        pass

    testcase = _MockFixture()
    testcase.setUp()
    yield testcase
    testcase.tearDown()
    testcase.tearDownClass()


@pytest.fixture(scope='session')
def dbusmock_system(dbusmock_test) -> dbusmock.testcase.DBusTestCase:
    '''Export the whole DBusTestCase as a fixture, with the system bus started'''

    dbusmock_test.start_system_bus()
    return dbusmock_test


@pytest.fixture(scope='session')
def dbusmock_session(dbusmock_test) -> dbusmock.testcase.DBusTestCase:
    '''Export the whole DBusTestCase as a fixture, with the session bus started'''

    dbusmock_test.start_session_bus()
    return dbusmock_test
