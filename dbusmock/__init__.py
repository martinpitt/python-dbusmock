"""Mock D-Bus objects for test suites."""

# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 3 of the License, or (at your option) any
# later version.  See http://www.gnu.org/copyleft/lgpl.html for the full text
# of the license.

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
