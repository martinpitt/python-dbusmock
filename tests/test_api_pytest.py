#!/usr/bin/python3

# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 3 of the License, or (at your option) any
# later version.  See http://www.gnu.org/copyleft/lgpl.html for the full text
# of the license.

from pathlib import Path
import dbus
import dbusmock
import re
import tempfile

try:
    from dbusmock.pytest import session_mock
    import pytest

    @pytest.fixture
    def mock(session_mock):
        # pylint: disable=consider-using-with
        session_mock.mock_log = tempfile.NamedTemporaryFile()
        session_mock.p_mock = session_mock.spawn_server('org.freedesktop.Test',
                                        '/',
                                        'org.freedesktop.Test.Main',
                                        stdout=session_mock.mock_log)

        session_mock.obj_test = session_mock.dbus_con.get_object('org.freedesktop.Test', '/')
        session_mock.dbus_test = dbus.Interface(session_mock.obj_test, 'org.freedesktop.Test.Main')
        session_mock.dbus_mock = dbus.Interface(session_mock.obj_test, dbusmock.MOCK_IFACE)
        session_mock.dbus_props = dbus.Interface(session_mock.obj_test, dbus.PROPERTIES_IFACE)
        yield session_mock

        if session_mock.p_mock.stdout:
            session_mock.p_mock.stdout.close()
        session_mock.p_mock.terminate()
        session_mock.p_mock.wait()


    class TestPytestAPI:
        def test_noarg_noret(self, mock):
            '''no arguments, no return value'''

            mock.dbus_mock.AddMethod('', 'Do', '', '', '')
            assert mock.dbus_test.Do() == None

            # check that it's logged correctly
            log = Path(mock.mock_log.name,).read_bytes()
            assert re.match(rb'^[0-9.]+ Do$', log)

except ImportError:
    pass
