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

import pytest

import dbusmock


def test_dbusmock_test(dbusmock_session):
    assert dbusmock_session
    test_iface = 'org.freedesktop.Test.Main'

    with dbusmock.SpawnedMock.spawn_for_name('org.freedesktop.Test', '/', test_iface) as server:
        obj_test = server.obj
        obj_test.AddMethod('', 'Upper', 's', 's', 'ret = args[0].upper()', interface_name=dbusmock.MOCK_IFACE)
        assert obj_test.Upper('hello', interface=test_iface) == 'HELLO'


@pytest.fixture(name='upower_mock')
def fixture_upower_mock(dbusmock_system):
    assert dbusmock_system
    with dbusmock.SpawnedMock.spawn_with_template('upower') as server:
        yield server.obj


def test_dbusmock_test_template(upower_mock):
    assert upower_mock
    out = subprocess.check_output(['upower', '--dump'], universal_newlines=True)
    assert 'version:' in out
    assert '0.99' in out
