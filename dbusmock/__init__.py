"""Mock D-Bus objects for test suites."""

# SPDX-License-Identifier: LGPL-3.0-or-later

from dbusmock.mockobject import MOCK_IFACE, OBJECT_MANAGER_IFACE, DBusMockObject, get_object, get_objects
from dbusmock.testcase import BusType, DBusTestCase, PrivateDBus, SpawnedMock

try:  # noqa: RUF067
    # created by setuptools_scm
    from dbusmock._version import __version__
except ImportError:
    __version__ = "0.git"


__all__ = [
    "MOCK_IFACE",
    "OBJECT_MANAGER_IFACE",
    "BusType",
    "DBusMockObject",
    "DBusTestCase",
    "PrivateDBus",
    "SpawnedMock",
    "get_object",
    "get_objects",
]
