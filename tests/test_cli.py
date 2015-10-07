#!/usr/bin/python3

# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 3 of the License, or (at your option) any
# later version.  See http://www.gnu.org/copyleft/lgpl.html for the full text
# of the license.

__author__ = 'Martin Pitt'
__email__ = 'martin.pitt@ubuntu.com'
__copyright__ = '(c) 2012 Canonical Ltd.'
__license__ = 'LGPL 3+'

import unittest
import sys
import subprocess

import dbus

import dbusmock


p = subprocess.Popen(['which', 'upower'], stdout=subprocess.PIPE)
p.communicate()
have_upower = (p.returncode == 0)


class TestCLI(dbusmock.DBusTestCase):
    '''Test running dbusmock from the command line'''

    @classmethod
    def setUpClass(klass):
        klass.start_system_bus()
        klass.start_session_bus()
        klass.system_con = klass.get_dbus(True)
        klass.session_con = klass.get_dbus()

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

    def test_session_bus(self):
        self.p_mock = subprocess.Popen([sys.executable, '-m', 'dbusmock',
                                        'com.example.Test', '/', 'TestIface'])
        self.wait_for_bus_object('com.example.Test', '/')

    def test_system_bus(self):
        self.p_mock = subprocess.Popen([sys.executable, '-m', 'dbusmock',
                                        '--system', 'com.example.Test', '/', 'TestIface'])
        self.wait_for_bus_object('com.example.Test', '/', True)

    def test_template_system(self):
        self.p_mock = subprocess.Popen([sys.executable, '-m', 'dbusmock',
                                        '--system', '-t', 'upower'],
                                       stdout=subprocess.PIPE,
                                       universal_newlines=True)
        self.wait_for_bus_object('org.freedesktop.UPower', '/org/freedesktop/UPower', True)

        # check that it actually ran the template, if we have upower
        if have_upower:
            out = subprocess.check_output(['upower', '--dump'],
                                          universal_newlines=True)
            self.assertRegex(out, 'on-battery:\s+no')

            mock_out = self.p_mock.stdout.readline()
            self.assertTrue('EnumerateDevices' in mock_out or 'GetAll' in mock_out,
                            mock_out)

    def test_template_parameters(self):
        self.p_mock = subprocess.Popen([sys.executable, '-m', 'dbusmock',
                                        '--system', '-t', 'upower',
                                        '-p', '{"DaemonVersion": "0.99.0", "OnBattery": true}'],
                                       stdout=subprocess.PIPE,
                                       universal_newlines=True)
        self.wait_for_bus_object('org.freedesktop.UPower', '/org/freedesktop/UPower', True)

        # check that it actually ran the template, if we have upower
        if have_upower:
            out = subprocess.check_output(['upower', '--dump'],
                                          universal_newlines=True)
            self.assertRegex(out, 'daemon-version:\s+0\\.99\\.0')
            self.assertRegex(out, 'on-battery:\s+yes')

    def test_template_parameters_malformed_json(self):
        with self.assertRaises(subprocess.CalledProcessError) as cm:
            subprocess.check_output([sys.executable, '-m', 'dbusmock',
                                     '--system', '-t', 'upower', '-p',
                                     '{"DaemonVersion: "0.99.0"}'],
                                    stderr=subprocess.STDOUT,
                                    universal_newlines=True)
        err = cm.exception
        self.assertEqual(err.returncode, 2)
        self.assertRegex(err.output, 'Malformed JSON given for parameters:.* delimiter')

    def test_template_parameters_not_dict(self):
        with self.assertRaises(subprocess.CalledProcessError) as cm:
            subprocess.check_output([sys.executable, '-m', 'dbusmock',
                                     '--system', '-t', 'upower', '-p',
                                     '"banana"'],
                                    stderr=subprocess.STDOUT,
                                    universal_newlines=True)
        err = cm.exception
        self.assertEqual(err.returncode, 2)
        self.assertEqual(err.output, 'JSON parameters must be a dictionary\n')

    def test_object_manager(self):
        self.p_mock = subprocess.Popen([sys.executable, '-m', 'dbusmock',
                                        '-m', 'com.example.Test', '/', 'TestIface'],
                                       stdout=subprocess.PIPE)
        self.wait_for_bus_object('com.example.Test', '/')

        obj = self.session_con.get_object('com.example.Test', '/')
        if_om = dbus.Interface(obj, dbusmock.OBJECT_MANAGER_IFACE)
        self.assertEqual(if_om.GetManagedObjects(), {})

        # add a new object, should appear
        obj.AddObject('/a/b', 'org.Test', {'name': 'foo'}, dbus.Array([], signature='(ssss)'))

        self.assertEqual(if_om.GetManagedObjects(), {'/a/b': {'org.Test': {'name': 'foo'}}})

    def test_no_args(self):
        p = subprocess.Popen([sys.executable, '-m', 'dbusmock'],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             universal_newlines=True)
        (out, err) = p.communicate()
        self.assertEqual(out, '')
        self.assertTrue('must specify NAME' in err, err)
        self.assertNotEqual(p.returncode, 0)

    def test_help(self):
        p = subprocess.Popen([sys.executable, '-m', 'dbusmock', '--help'],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             universal_newlines=True)
        (out, err) = p.communicate()
        self.assertEqual(err, '')
        self.assertTrue('INTERFACE' in out, out)
        self.assertTrue('--system' in out, out)
        self.assertEqual(p.returncode, 0)


if __name__ == '__main__':
    # avoid writing to stderr
    unittest.main(testRunner=unittest.TextTestRunner(stream=sys.stdout, verbosity=2))
