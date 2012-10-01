#!/usr/bin/python3

# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 3 of the License, or (at your option) any
# later version.  See http://www.gnu.org/copyleft/lgpl.html for the full text
# of the license.

__author__ = 'Martin Pitt'
__email__  = 'martin.pitt@ubuntu.com'
__copyright__ = '(c) 2012 Canonical Ltd.'
__license__ = 'LGPL 3+'

import unittest
import sys
import tempfile

import dbus

import dbusmock

class TestAPI(dbusmock.DBusTestCase):
    '''Test dbus-mock API'''

    @classmethod
    def setUpClass(klass):
        klass.start_session_bus()
        klass.dbus_con = klass.get_dbus()

    def setUp(self):
        self.mock_log = tempfile.NamedTemporaryFile()
        self.p_mock = self.spawn_server('org.freedesktop.Test',
                                        '/',
                                        'org.freedesktop.Test.Main',
                                        stdout=self.mock_log)

        self.obj_test = self.dbus_con.get_object('org.freedesktop.Test', '/')
        self.dbus_test = dbus.Interface(self.obj_test, 'org.freedesktop.Test.Main')
        self.dbusmock = dbus.Interface(self.obj_test, 'org.freedesktop.DBus.Mock')
        self.dbus_props = dbus.Interface(self.obj_test, dbus.PROPERTIES_IFACE)

    def tearDown(self):
        self.p_mock.terminate()
        self.p_mock.wait()

    def test_noarg_noret(self):
        '''no arguments, no return value'''

        self.dbusmock.AddMethod('', 'Do', '', '', '')
        self.assertEqual(self.dbus_test.Do(), None)

        # check that it's logged correctly
        with open(self.mock_log.name) as f:
            self.assertRegex(f.read(), '^[0-9.]+ Do$')

    def test_onearg_noret(self):
        '''one argument, no return value'''

        self.dbusmock.AddMethod('', 'Do', 's', '', '')
        self.assertEqual(self.dbus_test.Do('Hello'), None)

    def test_onearg_ret(self):
        '''one argument, code for return value'''

        self.dbusmock.AddMethod('', 'Do', 's', 's', 'ret = args[0]')
        self.assertEqual(self.dbus_test.Do('Hello'), 'Hello')

    def test_twoarg_ret(self):
        '''two arguments, code for return value'''

        self.dbusmock.AddMethod('', 'Do', 'si', 's', 'ret = args[0] * args[1]')
        self.assertEqual(self.dbus_test.Do('foo', 3), 'foofoofoo')

    def test_methods_on_other_interfaces(self):
        '''methods on other interfaces'''

        self.dbusmock.AddMethod('org.freedesktop.Test.Other', 'OtherDo', '', '', '')
        self.dbusmock.AddMethods('org.freedesktop.Test.Other', 
                                 [('OtherDo2', '', '', ''),
                                  ('OtherDo3', 'i', 'i', 'ret = args[0]'),
                                 ])

        # should not be on the main interface
        self.assertRaises(dbus.exceptions.DBusException,
                          self.dbus_test.OtherDo)

        # should be on the other interface
        self.assertEqual(self.obj_test.OtherDo(dbus_interface='org.freedesktop.Test.Other'), None)
        self.assertEqual(self.obj_test.OtherDo2(dbus_interface='org.freedesktop.Test.Other'), None)
        self.assertEqual(self.obj_test.OtherDo3(42, dbus_interface='org.freedesktop.Test.Other'), 42)

        # check that it's logged correctly
        with open(self.mock_log.name) as f:
            self.assertRegex(f.read(), '^[0-9.]+ OtherDo\n[0-9.]+ OtherDo2\n[0-9.]+ OtherDo3$')

    def test_add_object(self):
        '''add a new object'''

        self.dbusmock.AddObject('/obj1',
                                 'org.freedesktop.Test.Sub',
                                 {
                                     'state': dbus.String('online', variant_level=1),
                                     'cute': dbus.Boolean(True, variant_level=1),
                                 },
                                 [])

        obj1 = self.dbus_con.get_object('org.freedesktop.Test', '/obj1')
        dbus_sub = dbus.Interface(obj1, 'org.freedesktop.Test.Sub')
        dbus_props = dbus.Interface(obj1, dbus.PROPERTIES_IFACE)
        dbusmock = dbus.Interface(obj1, 'org.freedesktop.DBus.Mock')

        # check properties
        self.assertEqual(dbus_props.Get('org.freedesktop.Test.Sub', 'state'), 'online')
        self.assertEqual(dbus_props.Get('org.freedesktop.Test.Sub', 'cute'), True)
        self.assertEqual(dbus_props.GetAll('org.freedesktop.Test.Sub'),
                         {'state': 'online', 'cute': True})

        # add new method
        dbusmock.AddMethod('', 'Do', '', 's', 'ret = "hello"')
        self.assertEqual(dbus_sub.Do(), 'hello')

    def test_add_object_with_methods(self):
        '''add a new object with methods'''

        self.dbusmock.AddObject('/obj1',
                                 'org.freedesktop.Test.Sub',
                                 {
                                     'state': dbus.String('online', variant_level=1),
                                     'cute': dbus.Boolean(True, variant_level=1),
                                 },
                                 [
                                     ('Do0', '', 'i', 'ret = 42'),
                                     ('Do1', 'i', 'i', 'ret = 31337'),
                                 ])

        obj1 = self.dbus_con.get_object('org.freedesktop.Test', '/obj1')

        self.assertEqual(obj1.Do0(), 42)
        self.assertEqual(obj1.Do1(), 31337)
        self.assertRaises(dbus.exceptions.DBusException,
                          obj1.Do2, 31337)

    def test_properties(self):
        '''add and change properties'''

        # no properties by default
        self.assertEqual(self.dbus_props.GetAll('org.freedesktop.Test.Main'), {})

        # no such property
        self.assertRaises(dbus.exceptions.DBusException,
                          self.dbus_props.Get,
                          'org.freedesktop.Test.Main',
                          'version')
        self.assertRaises(dbus.exceptions.DBusException,
                          self.dbus_props.Set,
                          'org.freedesktop.Test.Main',
                          'version',
                          dbus.Int32(2, variant_level=1))

        self.dbusmock.AddProperty('org.freedesktop.Test.Main',
                                  'version',
                                  dbus.Int32(2, variant_level=1))
        # once again on default interface
        self.dbusmock.AddProperty('',
                                  'connected',
                                  dbus.Boolean(True, variant_level=1))

        self.assertEqual(self.dbus_props.Get('org.freedesktop.Test.Main', 'version'), 2)
        self.assertEqual(self.dbus_props.Get('org.freedesktop.Test.Main', 'connected'), True)

        self.assertEqual(self.dbus_props.GetAll('org.freedesktop.Test.Main'),
                         {'version': 2, 'connected': True})

        # change property
        self.dbus_props.Set('org.freedesktop.Test.Main', 'version',
                            dbus.Int32(4, variant_level=1))
        self.assertEqual(self.dbus_props.Get('org.freedesktop.Test.Main', 'version'), 4)

        # add property to different interface
        self.dbusmock.AddProperty('org.freedesktop.Test.Other',
                                  'color',
                                  dbus.String('yellow', variant_level=1))

        self.assertEqual(self.dbus_props.GetAll('org.freedesktop.Test.Main'),
                         {'version': 4, 'connected': True})
        self.assertEqual(self.dbus_props.GetAll('org.freedesktop.Test.Other'),
                         {'color': 'yellow'})
        self.assertEqual(self.dbus_props.Get('org.freedesktop.Test.Other', 'color'),
                         'yellow')

    def test_introspection_methods(self):
        '''dynamically added methods appear in introspection'''

        dbus_introspect = dbus.Interface(self.obj_test, dbus.INTROSPECTABLE_IFACE)

        xml_empty = dbus_introspect.Introspect()
        self.assertTrue('<interface name="org.freedesktop.DBus.Mock">' in xml_empty, xml_empty)
        self.assertTrue('<method name="AddMethod">' in xml_empty, xml_empty)

        self.dbusmock.AddMethod('', 'Do', 'saiv', 'i', 'ret = 42')

        xml_method = dbus_introspect.Introspect()
        self.assertFalse(xml_empty == xml_method, 'No change from empty XML')
        self.assertTrue('<interface name="org.freedesktop.Test.Main">' in xml_method, xml_method)
        self.assertTrue('''<method name="Do">
      <arg direction="in"  type="s" name="arg1" />
      <arg direction="in"  type="ai" name="arg2" />
      <arg direction="in"  type="v" name="arg3" />
      <arg direction="out" type="i" />
    </method>''' in xml_method, xml_method)


if __name__ == '__main__':
    # avoid writing to stderr
    unittest.main(testRunner=unittest.TextTestRunner(stream=sys.stdout, verbosity=2))
