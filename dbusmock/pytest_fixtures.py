"""pytest fixtures for DBusMock"""

# SPDX-License-Identifier: LGPL-3.0-or-later

__author__ = "Martin Pitt"
__copyright__ = "(c) 2023 Martin Pitt <martin@piware.de>"

from typing import Iterator

import pytest

from dbusmock.testcase import BusType, PrivateDBus


@pytest.fixture(scope="session")
def dbusmock_system() -> Iterator[PrivateDBus]:
    """Export the whole DBusTestCase as a fixture, with the system bus started"""

    with PrivateDBus(BusType.SYSTEM) as bus:
        yield bus


@pytest.fixture(scope="session")
def dbusmock_session() -> Iterator[PrivateDBus]:
    """Export the whole DBusTestCase as a fixture, with the session bus started"""

    with PrivateDBus(BusType.SESSION) as bus:
        yield bus
