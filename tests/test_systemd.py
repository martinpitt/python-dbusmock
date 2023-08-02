# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 3 of the License, or (at your option) any
# later version.  See http://www.gnu.org/copyleft/lgpl.html for the full text
# of the license.

__author__ = 'Jonas Ådahl'
__copyright__ = '''
(c) 2021 Red Hat
(c) 2017 - 2022 Martin Pitt <martin@piware.de>
'''

import subprocess
import sys
import unittest

import dbus
import dbus.mainloop.glib
from gi.repository import GLib

import dbusmock

dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)


class TestSystemd(dbusmock.DBusTestCase):
    '''Test mocking systemd'''

    @classmethod
    def setUpClass(cls):
        cls.start_session_bus()
        cls.start_system_bus()
        cls.session_bus = cls.get_dbus(False)
        cls.system_bus = cls.get_dbus(True)

    def setUp(self):
        self.p_mock = None

    def tearDown(self):
        if self.p_mock:
            self.p_mock.stdout.close()
            self.p_mock.terminate()
            self.p_mock.wait()

    def _assert_unit_property(self, unit_obj, name, expect):
        value = unit_obj.Get('org.freedesktop.systemd1.Unit', name)
        self.assertEqual(str(value), expect)

    def _test_base(self, bus, system_bus=True):
        dummy_service = 'dummy-dbusmock.service'

        (self.p_mock, obj_systemd) = self.spawn_server_template('systemd', {},
                                                                subprocess.PIPE,
                                                                system_bus=system_bus)

        systemd_mock = dbus.Interface(obj_systemd, dbusmock.MOCK_IFACE)
        systemd_mock.AddMockUnit(dummy_service)

        main_loop = GLib.MainLoop()

        removed_jobs = []

        def catch_job_removed(*args, **kwargs):
            if (kwargs['interface'] == 'org.freedesktop.systemd1.Manager' and
                    kwargs['member'] == 'JobRemoved'):
                job_path = str(args[1])
                removed_jobs.append(job_path)
                main_loop.quit()

        def wait_for_job(path):
            while True:
                main_loop.run()
                if path in removed_jobs:
                    break

        bus.add_signal_receiver(catch_job_removed,
                                interface_keyword='interface',
                                path_keyword='path',
                                member_keyword='member')

        unit_path = obj_systemd.GetUnit(dummy_service)

        unit_obj = bus.get_object('org.freedesktop.systemd1', unit_path)

        self._assert_unit_property(unit_obj, 'Id', dummy_service)
        self._assert_unit_property(unit_obj, 'LoadState', 'loaded')
        self._assert_unit_property(unit_obj, 'ActiveState', 'inactive')

        job_path = obj_systemd.StartUnit(dummy_service, 'fail')

        wait_for_job(job_path)
        self._assert_unit_property(unit_obj, 'ActiveState', 'active')

        job_path = obj_systemd.StopUnit(dummy_service, 'fail')

        wait_for_job(job_path)
        self._assert_unit_property(unit_obj, 'ActiveState', 'inactive')

        self.p_mock.stdout.close()
        self.p_mock.terminate()
        self.p_mock.wait()
        self.p_mock = None

    def test_user(self):
        self._test_base(self.session_bus, system_bus=False)

    def test_system(self):
        self._test_base(self.system_bus, system_bus=True)


if __name__ == '__main__':
    # avoid writing to stderr
    unittest.main(testRunner=unittest.TextTestRunner(stream=sys.stdout))
