#!/usr/bin/python3

# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 3 of the License, or (at your option) any
# later version.  See http://www.gnu.org/copyleft/lgpl.html for the full text
# of the license.

__author__ = 'Martin Pitt'
__copyright__ = '(c) 2012 Canonical Ltd.'

import importlib.util
import os
import unittest
import shutil
import sys
import subprocess
import tempfile
import tracemalloc

import dbus

import dbusmock


tracemalloc.start(25)
have_upower = shutil.which('upower')


class TestCLI(dbusmock.DBusTestCase):
    '''Test running dbusmock from the command line'''

    @classmethod
    def setUpClass(cls):
        cls.start_system_bus()
        cls.start_session_bus()
        cls.system_con = cls.get_dbus(True)
        cls.session_con = cls.get_dbus()

    def setUp(self):
        self.p_mock = None

    def tearDown(self):
        if self.p_mock:
            if self.p_mock.stdout:
                self.p_mock.stdout.close()
            if self.p_mock.stderr:
                self.p_mock.stdout.close()
            self.p_mock.terminate()
            self.p_mock.wait()
            self.p_mock = None

    def start_mock(self, args, wait_name, wait_path, wait_system=False):
        # pylint: disable=consider-using-with
        self.p_mock = subprocess.Popen([sys.executable, '-m', 'dbusmock'] + args,
                                       stdout=subprocess.PIPE,
                                       universal_newlines=True)
        self.wait_for_bus_object(wait_name, wait_path, wait_system)

    def test_session_bus(self):
        self.start_mock(['com.example.Test', '/', 'TestIface'],
                        'com.example.Test', '/')

    def test_system_bus(self):
        self.start_mock(['--system', 'com.example.Test', '/', 'TestIface'],
                        'com.example.Test', '/', True)

    def test_template_upower(self):
        self.start_mock(['-t', 'upower'],
                        'org.freedesktop.UPower', '/org/freedesktop/UPower', True)
        self.check_upower_running()

    def test_template_upower_explicit_path(self):
        spec = importlib.util.find_spec('dbusmock.templates.upower')
        self.assertTrue(os.path.exists(spec.origin))
        self.start_mock(['-t', spec.origin],
                        'org.freedesktop.UPower', '/org/freedesktop/UPower', True)
        self.check_upower_running()

    def check_upower_running(self):
        # check that it actually ran the template, if we have upower
        if have_upower:
            out = subprocess.check_output(['upower', '--dump'],
                                          universal_newlines=True)
            self.assertRegex(out, r'on-battery:\s+no')

            mock_out = self.p_mock.stdout.readline()
            self.assertTrue('EnumerateDevices' in mock_out or 'GetAll' in mock_out,
                            mock_out)

    def test_template_explicit_system(self):
        # --system is redundant here, but should not break
        self.start_mock(['--system', '-t', 'upower'],
                        'org.freedesktop.UPower', '/org/freedesktop/UPower', True)
        self.check_upower_running()

    def test_template_override_session(self):
        self.start_mock(['--session', '-t', 'upower'],
                        'org.freedesktop.UPower', '/org/freedesktop/UPower', False)

    def test_template_conflicting_bus(self):
        with self.assertRaises(subprocess.CalledProcessError) as cm:
            subprocess.check_output([sys.executable, '-m', 'dbusmock',
                                     '--system', '--session', '-t', 'upower'],
                                    stderr=subprocess.STDOUT,
                                    universal_newlines=True)
        err = cm.exception
        self.assertEqual(err.returncode, 2)
        self.assertRegex(err.output, '--system.*--session.*exclusive')

    def test_template_parameters(self):
        self.start_mock(['-t', 'upower', '-p', '{"DaemonVersion": "0.99.0", "OnBattery": true}'],
                        'org.freedesktop.UPower', '/org/freedesktop/UPower', True)

        # check that it actually ran the template, if we have upower
        if have_upower:
            out = subprocess.check_output(['upower', '--dump'],
                                          universal_newlines=True)
            self.assertRegex(out, r'daemon-version:\s+0\.99\.0')
            self.assertRegex(out, r'on-battery:\s+yes')

    def test_template_parameters_malformed_json(self):
        with self.assertRaises(subprocess.CalledProcessError) as cm:
            subprocess.check_output([sys.executable, '-m', 'dbusmock',
                                     '-t', 'upower', '-p',
                                     '{"DaemonVersion: "0.99.0"}'],
                                    stderr=subprocess.STDOUT,
                                    universal_newlines=True)
        err = cm.exception
        self.assertEqual(err.returncode, 2)
        self.assertRegex(err.output, 'Malformed JSON given for parameters:.* delimiter')

    def test_template_parameters_not_dict(self):
        with self.assertRaises(subprocess.CalledProcessError) as cm:
            subprocess.check_output([sys.executable, '-m', 'dbusmock',
                                     '-t', 'upower', '-p',
                                     '"banana"'],
                                    stderr=subprocess.STDOUT,
                                    universal_newlines=True)
        err = cm.exception
        self.assertEqual(err.returncode, 2)
        self.assertEqual(err.output, 'JSON parameters must be a dictionary\n')

    def test_template_local(self):
        with tempfile.NamedTemporaryFile(prefix='answer_', suffix='.py') as my_template:
            my_template.write(b'''import dbus
BUS_NAME = 'universe.Ultimate'
MAIN_OBJ = '/'
MAIN_IFACE = 'universe.Ultimate'
SYSTEM_BUS = False

def load(mock, parameters):
    mock.AddMethods(MAIN_IFACE, [('Answer', '', 'i', 'ret = 42')])
''')
            my_template.flush()
            # template specifies session bus
            self.start_mock(['-t', my_template.name],
                            'universe.Ultimate', '/', False)

        obj = self.session_con.get_object('universe.Ultimate', '/')
        if_u = dbus.Interface(obj, 'universe.Ultimate')
        self.assertEqual(if_u.Answer(), 42)

    def test_template_override_system(self):
        with tempfile.NamedTemporaryFile(prefix='answer_', suffix='.py') as my_template:
            my_template.write(b'''import dbus
BUS_NAME = 'universe.Ultimate'
MAIN_OBJ = '/'
MAIN_IFACE = 'universe.Ultimate'
SYSTEM_BUS = False

def load(mock, parameters):
    mock.AddMethods(MAIN_IFACE, [('Answer', '', 'i', 'ret = 42')])
''')
            my_template.flush()
            # template specifies session bus, but CLI overrides to system
            self.start_mock(['--system', '-t', my_template.name],
                            'universe.Ultimate', '/', True)

        obj = self.system_con.get_object('universe.Ultimate', '/')
        if_u = dbus.Interface(obj, 'universe.Ultimate')
        self.assertEqual(if_u.Answer(), 42)

    def test_object_manager(self):
        self.start_mock(['-m', 'com.example.Test', '/', 'TestIface'],
                        'com.example.Test', '/')

        obj = self.session_con.get_object('com.example.Test', '/')
        if_om = dbus.Interface(obj, dbusmock.OBJECT_MANAGER_IFACE)
        self.assertEqual(if_om.GetManagedObjects(), {})

        # add a new object, should appear
        obj.AddObject('/a/b', 'org.Test', {'name': 'foo'}, dbus.Array([], signature='(ssss)'))

        self.assertEqual(if_om.GetManagedObjects(), {'/a/b': {'org.Test': {'name': 'foo'}}})

    def test_no_args(self):
        with subprocess.Popen([sys.executable, '-m', 'dbusmock'],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              universal_newlines=True) as p:
            (out, err) = p.communicate()
            self.assertEqual(out, '')
            self.assertIn('must specify NAME', err)
            self.assertNotEqual(p.returncode, 0)

    def test_help(self):
        with subprocess.Popen([sys.executable, '-m', 'dbusmock', '--help'],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              universal_newlines=True) as p:
            (out, err) = p.communicate()
            self.assertEqual(err, '')
            self.assertIn('INTERFACE', out)
            self.assertIn('--system', out)
            self.assertEqual(p.returncode, 0)


if __name__ == '__main__':
    # avoid writing to stderr
    unittest.main(testRunner=unittest.TextTestRunner(stream=sys.stdout))
