# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 3 of the License, or (at your option) any
# later version.  See http://www.gnu.org/copyleft/lgpl.html for the full text
# of the license.

__author__ = 'Martin Pitt'
__copyright__ = '''
(c) 2023 Martin Pitt <martin@piware.de>
'''

import subprocess
import tempfile

import pytest

import dbusmock


def test_dbusmock_test_spawn_server(dbusmock_session):
    test_iface = 'org.freedesktop.Test.Main'

    p_mock = dbusmock_session.spawn_server(
        'org.freedesktop.Test', '/', test_iface, stdout=tempfile.TemporaryFile())

    obj_test = dbusmock_session.get_dbus().get_object('org.freedesktop.Test', '/')

    obj_test.AddMethod('', 'Upper', 's', 's', 'ret = args[0].upper()', interface_name=dbusmock.MOCK_IFACE)
    assert obj_test.Upper('hello', interface=test_iface) == 'HELLO'

    p_mock.terminate()
    p_mock.wait()


@pytest.fixture(name='upower_mock')
def fixture_upower_mock(dbusmock_system):
    p_mock, obj = dbusmock_system.spawn_server_template('upower', stdout=subprocess.DEVNULL)
    yield obj
    p_mock.terminate()
    p_mock.wait()


def test_dbusmock_test_spawn_system_template(upower_mock):
    assert upower_mock
    out = subprocess.check_output(['upower', '--dump'], universal_newlines=True)
    assert 'version:' in out
    assert '0.99' in out
