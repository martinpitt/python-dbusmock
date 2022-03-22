#!/usr/bin/python3

# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 3 of the License, or (at your option) any
# later version.  See http://www.gnu.org/copyleft/lgpl.html for the full text
# of the license.

__author__ = 'Martin Pitt'
__copyright__ = '(c) 2012 Canonical Ltd.'

import unittest
import sys
import os
import tempfile
import subprocess
import shutil
import time
import importlib.util
import tracemalloc

import dbus
import dbus.mainloop.glib

from gi.repository import GLib

import dbusmock

tracemalloc.start(25)
dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

# "a <heart> b" in py2/3 compatible unicode
UNICODE = b'a\xe2\x99\xa5b'.decode('UTF-8')


class TestAPI(dbusmock.DBusTestCase):
    '''Test dbus-mock API'''

    @classmethod
    def setUpClass(cls):
        cls.start_session_bus()
        cls.dbus_con = cls.get_dbus()

    def setUp(self):
        # pylint: disable=consider-using-with
        self.mock_log = tempfile.NamedTemporaryFile()
        self.p_mock = self.spawn_server('org.freedesktop.Test',
                                        '/',
                                        'org.freedesktop.Test.Main',
                                        stdout=self.mock_log)

        self.obj_test = self.dbus_con.get_object('org.freedesktop.Test', '/')
        self.dbus_test = dbus.Interface(self.obj_test, 'org.freedesktop.Test.Main')
        self.dbus_mock = dbus.Interface(self.obj_test, dbusmock.MOCK_IFACE)
        self.dbus_props = dbus.Interface(self.obj_test, dbus.PROPERTIES_IFACE)

    def assertLog(self, regex):
        with open(self.mock_log.name, "rb") as f:
            self.assertRegex(f.read(), regex)

    def tearDown(self):
        if self.p_mock.stdout:
            self.p_mock.stdout.close()
        self.p_mock.terminate()
        self.p_mock.wait()

    def test_noarg_noret(self):
        '''no arguments, no return value'''

        self.dbus_mock.AddMethod('', 'Do', '', '', '')
        self.assertEqual(self.dbus_test.Do(), None)

        # check that it's logged correctly
        self.assertLog(b'^[0-9.]+ Do$')

    def test_onearg_noret(self):
        '''one argument, no return value'''

        self.dbus_mock.AddMethod('', 'Do', 's', '', '')
        self.assertEqual(self.dbus_test.Do('Hello'), None)

        # check that it's logged correctly
        self.assertLog(b'^[0-9.]+ Do "Hello"$')

    def test_onearg_ret(self):
        '''one argument, code for return value'''

        self.dbus_mock.AddMethod('', 'Do', 's', 's', 'ret = args[0]')
        self.assertEqual(self.dbus_test.Do('Hello'), 'Hello')

    def test_unicode_str(self):
        '''unicode string roundtrip'''

        self.dbus_mock.AddMethod('', 'Do', 's', 's', 'ret = args[0] * 2')
        self.assertEqual(self.dbus_test.Do(UNICODE), dbus.String(UNICODE * 2))

    def test_twoarg_ret(self):
        '''two arguments, code for return value'''

        self.dbus_mock.AddMethod('', 'Do', 'si', 's', 'ret = args[0] * args[1]')
        self.assertEqual(self.dbus_test.Do('foo', 3), 'foofoofoo')

        # check that it's logged correctly
        self.assertLog(b'^[0-9.]+ Do "foo" 3$')

    def test_array_arg(self):
        '''array argument'''

        self.dbus_mock.AddMethod('', 'Do', 'iaous', '',
                                 f'''assert len(args) == 4
assert args[0] == -1;
assert args[1] == ['/foo']
assert type(args[1]) == dbus.Array
assert type(args[1][0]) == dbus.ObjectPath
assert args[2] == 5
assert args[3] == {repr(UNICODE)}
''')
        self.assertEqual(self.dbus_test.Do(-1, ['/foo'], 5, UNICODE), None)

        # check that it's logged correctly
        self.assertLog(b'^[0-9.]+ Do -1 \\["/foo"\\] 5 "a\\xe2\\x99\\xa5b"$')

    def test_dict_arg(self):
        '''dictionary argument'''

        self.dbus_mock.AddMethod('', 'Do', 'ia{si}u', '',
                                 '''assert len(args) == 3
assert args[0] == -1;
assert args[1] == {'foo': 42}
assert type(args[1]) == dbus.Dictionary
assert args[2] == 5
''')
        self.assertEqual(self.dbus_test.Do(-1, {'foo': 42}, 5), None)

        # check that it's logged correctly
        self.assertLog(b'^[0-9.]+ Do -1 {"foo": 42} 5$')

    def test_exception(self):
        '''raise a D-Bus exception'''

        self.dbus_mock.AddMethod('', 'Do', '', 'i',
                                 'raise dbus.exceptions.DBusException("no good", name="com.example.Error.NoGood")')
        with self.assertRaises(dbus.exceptions.DBusException) as cm:
            self.dbus_test.Do()
        self.assertEqual(cm.exception.get_dbus_name(), 'com.example.Error.NoGood')
        self.assertEqual(cm.exception.get_dbus_message(), 'no good')
        self.assertLog(b'\n[0-9.]+ Do raised: com.example.Error.NoGood:.*\n')

    def test_methods_on_other_interfaces(self):
        '''methods on other interfaces'''

        self.dbus_mock.AddMethod('org.freedesktop.Test.Other', 'OtherDo', '', '', '')
        self.dbus_mock.AddMethods('org.freedesktop.Test.Other',
                                  [('OtherDo2', '', '', ''),
                                   ('OtherDo3', 'i', 'i', 'ret = args[0]')])

        # should not be on the main interface
        self.assertRaises(dbus.exceptions.DBusException,
                          self.dbus_test.OtherDo)

        # should be on the other interface
        self.assertEqual(self.obj_test.OtherDo(dbus_interface='org.freedesktop.Test.Other'), None)
        self.assertEqual(self.obj_test.OtherDo2(dbus_interface='org.freedesktop.Test.Other'), None)
        self.assertEqual(self.obj_test.OtherDo3(42, dbus_interface='org.freedesktop.Test.Other'), 42)

        # check that it's logged correctly
        self.assertLog(b'^[0-9.]+ OtherDo\n[0-9.]+ OtherDo2\n[0-9.]+ OtherDo3 42$')

    def test_methods_same_name(self):
        '''methods with same name on different interfaces'''

        self.dbus_mock.AddMethod('org.iface1', 'Do', 'i', 'i', 'ret = args[0] + 2')
        self.dbus_mock.AddMethod('org.iface2', 'Do', 'i', 'i', 'ret = args[0] + 3')

        # should not be on the main interface
        self.assertRaises(dbus.exceptions.DBusException,
                          self.dbus_test.Do)

        # should be on the other interface
        self.assertEqual(self.obj_test.Do(10, dbus_interface='org.iface1'), 12)
        self.assertEqual(self.obj_test.Do(11, dbus_interface='org.iface2'), 14)

        # check that it's logged correctly
        self.assertLog(b'^[0-9.]+ Do 10\n[0-9.]+ Do 11$')

        # now add it to the primary interface, too
        self.dbus_mock.AddMethod('', 'Do', 'i', 'i', 'ret = args[0] + 1')
        self.assertEqual(self.obj_test.Do(9, dbus_interface='org.freedesktop.Test.Main'), 10)
        self.assertEqual(self.obj_test.Do(10, dbus_interface='org.iface1'), 12)
        self.assertEqual(self.obj_test.Do(11, dbus_interface='org.iface2'), 14)

    def test_methods_type_mismatch(self):
        '''calling methods with wrong arguments'''

        def check(signature, args, err):
            self.dbus_mock.AddMethod('', 'Do', signature, '', '')
            try:
                self.dbus_test.Do(*args)
                self.fail(f'method call did not raise an error for signature "{signature}" and arguments {args}')
            except dbus.exceptions.DBusException as e:
                self.assertEqual(e.get_dbus_name(), 'org.freedesktop.DBus.Error.InvalidArgs')
                self.assertIn(err, str(e))

        # not enough arguments
        check('i', [], 'More items found')
        check('is', [1], 'More items found')

        # too many arguments
        check('', [1], 'Fewer items found')
        check('i', [1, 'hello'], 'Fewer items found')

        # type mismatch
        check('u', [-1], 'convert negative value to unsigned')
        check('i', ['hello'], 'dbus.String')
        check('i', ['hello'], 'integer')
        check('s', [1], 'Expected a string')

    def test_add_object(self):
        '''add a new object'''

        self.dbus_mock.AddObject('/obj1',
                                 'org.freedesktop.Test.Sub',
                                 {
                                     'state': dbus.String('online', variant_level=1),
                                     'cute': dbus.Boolean(True, variant_level=1),
                                 },
                                 [])

        obj1 = self.dbus_con.get_object('org.freedesktop.Test', '/obj1')
        dbus_sub = dbus.Interface(obj1, 'org.freedesktop.Test.Sub')
        dbus_props = dbus.Interface(obj1, dbus.PROPERTIES_IFACE)

        # check properties
        self.assertEqual(dbus_props.Get('org.freedesktop.Test.Sub', 'state'), 'online')
        self.assertEqual(dbus_props.Get('org.freedesktop.Test.Sub', 'cute'), True)
        self.assertEqual(dbus_props.GetAll('org.freedesktop.Test.Sub'),
                         {'state': 'online', 'cute': True})

        # add new method
        obj1.AddMethod('', 'Do', '', 's', 'ret = "hello"',
                       dbus_interface=dbusmock.MOCK_IFACE)
        self.assertEqual(dbus_sub.Do(), 'hello')

    def test_add_object_existing(self):
        '''try to add an existing object'''

        self.dbus_mock.AddObject('/obj1', 'org.freedesktop.Test.Sub', {}, [])

        self.assertRaises(dbus.exceptions.DBusException,
                          self.dbus_mock.AddObject,
                          '/obj1',
                          'org.freedesktop.Test.Sub',
                          {},
                          [])

        # try to add the main object again
        self.assertRaises(dbus.exceptions.DBusException,
                          self.dbus_mock.AddObject,
                          '/',
                          'org.freedesktop.Test.Other',
                          {},
                          [])

    def test_add_object_with_methods(self):
        '''add a new object with methods'''

        self.dbus_mock.AddObject('/obj1',
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
        self.assertEqual(obj1.Do1(1), 31337)
        self.assertRaises(dbus.exceptions.DBusException,
                          obj1.Do2, 31337)

    def test_properties(self):
        '''add and change properties'''

        # no properties by default
        self.assertEqual(self.dbus_props.GetAll('org.freedesktop.Test.Main'), {})

        # no such property
        with self.assertRaises(dbus.exceptions.DBusException) as ctx:
            self.dbus_props.Get('org.freedesktop.Test.Main', 'version')
        self.assertEqual(ctx.exception.get_dbus_name(),
                         'org.freedesktop.Test.Main.UnknownProperty')
        self.assertEqual(ctx.exception.get_dbus_message(),
                         'no such property version')

        self.assertRaises(dbus.exceptions.DBusException,
                          self.dbus_props.Set,
                          'org.freedesktop.Test.Main',
                          'version',
                          dbus.Int32(2, variant_level=1))

        self.dbus_mock.AddProperty('org.freedesktop.Test.Main',
                                   'version',
                                   dbus.Int32(2, variant_level=1))
        # once again on default interface
        self.dbus_mock.AddProperty('',
                                   'connected',
                                   dbus.Boolean(True, variant_level=1))

        self.assertEqual(self.dbus_props.Get('org.freedesktop.Test.Main', 'version'), 2)
        self.assertEqual(self.dbus_props.Get('org.freedesktop.Test.Main', 'connected'), True)

        self.assertEqual(self.dbus_props.GetAll('org.freedesktop.Test.Main'),
                         {'version': 2, 'connected': True})

        with self.assertRaises(dbus.exceptions.DBusException) as ctx:
            self.dbus_props.GetAll('org.freedesktop.Test.Bogus')
        self.assertEqual(ctx.exception.get_dbus_name(),
                         'org.freedesktop.Test.Main.UnknownInterface')
        self.assertEqual(ctx.exception.get_dbus_message(),
                         'no such interface org.freedesktop.Test.Bogus')

        # change property
        self.dbus_props.Set('org.freedesktop.Test.Main', 'version',
                            dbus.Int32(4, variant_level=1))
        self.assertEqual(self.dbus_props.Get('org.freedesktop.Test.Main', 'version'), 4)

        # check that the Get/Set calls get logged
        with open(self.mock_log.name, encoding="UTF-8") as f:
            contents = f.read()
            self.assertRegex(contents, '\n[0-9.]+ Get / org.freedesktop.Test.Main.version\n')
            self.assertRegex(contents, '\n[0-9.]+ Get / org.freedesktop.Test.Main.connected\n')
            self.assertRegex(contents, '\n[0-9.]+ GetAll / org.freedesktop.Test.Main\n')
            self.assertRegex(contents, '\n[0-9.]+ Set / org.freedesktop.Test.Main.version 4\n')

        # add property to different interface
        self.dbus_mock.AddProperty('org.freedesktop.Test.Other',
                                   'color',
                                   dbus.String('yellow', variant_level=1))

        self.assertEqual(self.dbus_props.GetAll('org.freedesktop.Test.Main'),
                         {'version': 4, 'connected': True})
        self.assertEqual(self.dbus_props.GetAll('org.freedesktop.Test.Other'),
                         {'color': 'yellow'})
        self.assertEqual(self.dbus_props.Get('org.freedesktop.Test.Other', 'color'),
                         'yellow')

        changed_props = []
        ml = GLib.MainLoop()

        def catch(*args, **kwargs):
            if kwargs['interface'] != 'org.freedesktop.DBus.Properties':
                return

            self.assertEqual(kwargs['interface'], 'org.freedesktop.DBus.Properties')
            self.assertEqual(kwargs['member'], 'PropertiesChanged')

            [iface, changed, _invalidated] = args
            self.assertEqual(iface, 'org.freedesktop.Test.Main')

            changed_props.append(changed)
            ml.quit()

        match = self.dbus_con.add_signal_receiver(catch,
                                                  interface_keyword='interface',
                                                  path_keyword='path',
                                                  member_keyword='member')

        # change property using mock helper
        self.dbus_mock.UpdateProperties('org.freedesktop.Test.Main', {
            'version': 5,
            'connected': False,
        })

        GLib.timeout_add(3000, ml.quit)
        ml.run()

        match.remove()

        self.assertEqual(self.dbus_props.GetAll('org.freedesktop.Test.Main'),
                         {'version': 5, 'connected': False})
        self.assertEqual(changed_props,
                         [{'version': 5, 'connected': False}])

        # test adding properties with the array type
        self.dbus_mock.AddProperty('org.freedesktop.Test.Main',
                                   'array',
                                   dbus.Array(['first'], signature='s'))
        self.assertEqual(self.dbus_props.Get('org.freedesktop.Test.Main', 'array'),
                         ['first'])

        # test updating properties with the array type
        self.dbus_mock.UpdateProperties('org.freedesktop.Test.Main',
                                        {'array': dbus.Array(['second', 'third'],
                                                             signature='s')})
        self.assertEqual(self.dbus_props.Get('org.freedesktop.Test.Main', 'array'),
                         ['second', 'third'])

    def test_introspection_methods(self):
        '''dynamically added methods appear in introspection'''

        dbus_introspect = dbus.Interface(self.obj_test, dbus.INTROSPECTABLE_IFACE)

        xml_empty = dbus_introspect.Introspect()
        self.assertIn('<interface name="org.freedesktop.DBus.Mock">', xml_empty)
        self.assertIn('<method name="AddMethod">', xml_empty)

        self.dbus_mock.AddMethod('', 'Do', 'saiv', 'i', 'ret = 42')

        xml_method = dbus_introspect.Introspect()
        self.assertNotEqual(xml_empty, xml_method)
        self.assertIn('<interface name="org.freedesktop.Test.Main">', xml_method)
        # various Python versions use different name vs. type ordering
        expected1 = '''<method name="Do">
      <arg direction="in" name="arg1" type="s" />
      <arg direction="in" name="arg2" type="ai" />
      <arg direction="in" name="arg3" type="v" />
      <arg direction="out" type="i" />
    </method>'''
        expected2 = '''<method name="Do">
      <arg direction="in" type="s" name="arg1" />
      <arg direction="in" type="ai" name="arg2" />
      <arg direction="in" type="v" name="arg3" />
      <arg direction="out" type="i" />
    </method>'''
        self.assertTrue(expected1 in xml_method or expected2 in xml_method, xml_method)

    # properties in introspection are not supported by dbus-python right now
    def test_introspection_properties(self):
        '''dynamically added properties appear in introspection'''

        self.dbus_mock.AddProperty('', 'Color', 'yellow')
        self.dbus_mock.AddProperty('org.freedesktop.Test.Sub', 'Count', 5)

        xml = self.obj_test.Introspect()

        self.assertIn('<interface name="org.freedesktop.Test.Main">', xml)
        self.assertIn('<interface name="org.freedesktop.Test.Sub">', xml)
        # various Python versions use different attribute ordering
        self.assertTrue('<property access="readwrite" name="Color" type="s" />' in xml or
                        '<property name="Color" type="s" access="readwrite" />' in xml, xml)
        self.assertTrue('<property access="readwrite" name="Count" type="i" />' in xml or
                        '<property name="Count" type="i" access="readwrite" />' in xml, xml)

    def test_objects_map(self):
        '''access global objects map'''

        self.dbus_mock.AddMethod('', 'EnumObjs', '', 'ao', 'ret = objects.keys()')
        self.assertEqual(self.dbus_test.EnumObjs(), ['/'])

        self.dbus_mock.AddObject('/obj1', 'org.freedesktop.Test.Sub', {}, [])
        self.assertEqual(set(self.dbus_test.EnumObjs()), {'/', '/obj1'})

    def test_signals(self):
        '''emitting signals'''

        def do_emit():
            self.dbus_mock.EmitSignal('', 'SigNoArgs', '', [])
            self.dbus_mock.EmitSignal('org.freedesktop.Test.Sub',
                                      'SigTwoArgs',
                                      'su', ['hello', 42])
            self.dbus_mock.EmitSignal('org.freedesktop.Test.Sub',
                                      'SigTypeTest',
                                      'iuvao',
                                      [-42, 42, dbus.String('hello', variant_level=1), ['/a', '/b']])

        caught = []
        ml = GLib.MainLoop()

        def catch(*args, **kwargs):
            if kwargs['interface'].startswith('org.freedesktop.Test'):
                caught.append((args, kwargs))
            if len(caught) == 3:
                # we caught everything there is to catch, don't wait for the
                # timeout
                ml.quit()

        self.dbus_con.add_signal_receiver(catch,
                                          interface_keyword='interface',
                                          path_keyword='path',
                                          member_keyword='member')

        GLib.timeout_add(200, do_emit)
        # ensure that the loop quits even when we catch fewer than 2 signals
        GLib.timeout_add(3000, ml.quit)
        ml.run()

        # check SigNoArgs
        self.assertEqual(caught[0][0], ())
        self.assertEqual(caught[0][1]['member'], 'SigNoArgs')
        self.assertEqual(caught[0][1]['path'], '/')
        self.assertEqual(caught[0][1]['interface'], 'org.freedesktop.Test.Main')

        # check SigTwoArgs
        self.assertEqual(caught[1][0], ('hello', 42))
        self.assertEqual(caught[1][1]['member'], 'SigTwoArgs')
        self.assertEqual(caught[1][1]['path'], '/')
        self.assertEqual(caught[1][1]['interface'], 'org.freedesktop.Test.Sub')

        # check data types in SigTypeTest
        self.assertEqual(caught[2][1]['member'], 'SigTypeTest')
        self.assertEqual(caught[2][1]['path'], '/')
        args = caught[2][0]
        self.assertEqual(args[0], -42)
        self.assertEqual(type(args[0]), dbus.Int32)
        self.assertEqual(args[0].variant_level, 0)

        self.assertEqual(args[1], 42)
        self.assertEqual(type(args[1]), dbus.UInt32)
        self.assertEqual(args[1].variant_level, 0)

        self.assertEqual(args[2], 'hello')
        self.assertEqual(type(args[2]), dbus.String)
        self.assertEqual(args[2].variant_level, 1)

        self.assertEqual(args[3], ['/a', '/b'])
        self.assertEqual(type(args[3]), dbus.Array)
        self.assertEqual(args[3].variant_level, 0)
        self.assertEqual(type(args[3][0]), dbus.ObjectPath)
        self.assertEqual(args[3][0].variant_level, 0)

        # check correct logging
        with open(self.mock_log.name, encoding="UTF-8") as f:
            log = f.read()
        self.assertRegex(log, '[0-9.]+ emit / org.freedesktop.Test.Main.SigNoArgs\n')
        self.assertRegex(log, '[0-9.]+ emit / org.freedesktop.Test.Sub.SigTwoArgs "hello" 42\n')
        self.assertRegex(log, '[0-9.]+ emit / org.freedesktop.Test.Sub.SigTypeTest -42 42')
        self.assertRegex(log, r'[0-9.]+ emit / org.freedesktop.Test.Sub.SigTypeTest -42 42 "hello" \["/a", "/b"\]\n')

    def test_signals_type_mismatch(self):
        '''emitting signals with wrong arguments'''

        def check(signature, args, err):
            try:
                self.dbus_mock.EmitSignal('', 's', signature, args)
                self.fail(f'EmitSignal did not raise an error for signature "{signature}" and arguments {args}')
            except dbus.exceptions.DBusException as e:
                self.assertEqual(e.get_dbus_name(), 'org.freedesktop.DBus.Error.InvalidArgs')
                self.assertIn(err, str(e))

        # not enough arguments
        check('i', [], 'More items found')
        check('is', [1], 'More items found')

        # too many arguments
        check('', [1], 'Fewer items found')
        check('i', [1, 'hello'], 'Fewer items found')

        # type mismatch
        check('u', [-1], 'convert negative value to unsigned')
        check('i', ['hello'], 'dbus.String')
        check('i', ['hello'], 'integer')
        check('s', [1], 'Expected a string')

    def test_dbus_get_log(self):
        '''query call logs over D-Bus'''

        self.assertEqual(self.dbus_mock.ClearCalls(), None)
        self.assertEqual(self.dbus_mock.GetCalls(), dbus.Array([]))

        self.dbus_mock.AddMethod('', 'Do', '', '', '')
        self.assertEqual(self.dbus_test.Do(), None)
        mock_log = self.dbus_mock.GetCalls()
        self.assertEqual(len(mock_log), 1)
        self.assertGreater(mock_log[0][0], 10000)  # timestamp
        self.assertEqual(mock_log[0][1], 'Do')
        self.assertEqual(mock_log[0][2], [])

        self.assertEqual(self.dbus_mock.ClearCalls(), None)
        self.assertEqual(self.dbus_mock.GetCalls(), dbus.Array([]))

        self.dbus_mock.AddMethod('', 'Wop', 's', 's', 'ret="hello"')
        self.assertEqual(self.dbus_test.Wop('foo'), 'hello')
        self.assertEqual(self.dbus_test.Wop('bar'), 'hello')
        mock_log = self.dbus_mock.GetCalls()
        self.assertEqual(len(mock_log), 2)
        self.assertGreater(mock_log[0][0], 10000)  # timestamp
        self.assertEqual(mock_log[0][1], 'Wop')
        self.assertEqual(mock_log[0][2], ['foo'])
        self.assertEqual(mock_log[1][1], 'Wop')
        self.assertEqual(mock_log[1][2], ['bar'])

        self.assertEqual(self.dbus_mock.ClearCalls(), None)
        self.assertEqual(self.dbus_mock.GetCalls(), dbus.Array([]))

    def test_dbus_get_method_calls(self):
        '''query method call logs over D-Bus'''

        self.dbus_mock.AddMethod('', 'Do', '', '', '')
        self.assertEqual(self.dbus_test.Do(), None)
        self.assertEqual(self.dbus_test.Do(), None)

        self.dbus_mock.AddMethod('', 'Wop', 's', 's', 'ret="hello"')
        self.assertEqual(self.dbus_test.Wop('foo'), 'hello')
        self.assertEqual(self.dbus_test.Wop('bar'), 'hello')

        mock_calls = self.dbus_mock.GetMethodCalls('Do')
        self.assertEqual(len(mock_calls), 2)
        self.assertEqual(mock_calls[0][1], [])
        self.assertEqual(mock_calls[1][1], [])

        mock_calls = self.dbus_mock.GetMethodCalls('Wop')
        self.assertEqual(len(mock_calls), 2)
        self.assertGreater(mock_calls[0][0], 10000)  # timestamp
        self.assertEqual(mock_calls[0][1], ['foo'])
        self.assertGreater(mock_calls[1][0], 10000)  # timestamp
        self.assertEqual(mock_calls[1][1], ['bar'])

    def test_dbus_method_called(self):
        '''subscribe to MethodCalled signal'''

        loop = GLib.MainLoop()
        caught_signals = []

        def method_called(method, args, **_):
            caught_signals.append((method, args))
            loop.quit()

        self.dbus_mock.AddMethod('', 'Do', 's', '', '')
        self.dbus_mock.connect_to_signal('MethodCalled', method_called)
        self.assertEqual(self.dbus_test.Do('foo'), None)

        GLib.timeout_add(5000, loop.quit)
        loop.run()

        self.assertEqual(len(caught_signals), 1)
        method, args = caught_signals[0]
        self.assertEqual(method, 'Do')
        self.assertEqual(len(args), 1)
        self.assertEqual(args[0], 'foo')

    def test_reset(self):
        '''resetting to pristine state'''

        self.dbus_mock.AddMethod('', 'Do', '', '', '')
        self.dbus_mock.AddProperty('', 'propone', True)
        self.dbus_mock.AddProperty('org.Test.Other', 'proptwo', 1)
        self.dbus_mock.AddObject('/obj1', '', {}, [])

        self.dbus_mock.Reset()

        # resets properties and keeps the initial object
        self.assertEqual(self.dbus_props.GetAll(''), {})
        # resets methods
        self.assertRaises(dbus.exceptions.DBusException, self.dbus_test.Do)
        # resets other objects
        obj1 = self.dbus_con.get_object('org.freedesktop.Test', '/obj1')
        self.assertRaises(dbus.exceptions.DBusException, obj1.GetAll, '')


class TestTemplates(dbusmock.DBusTestCase):
    '''Test template API'''

    @classmethod
    def setUpClass(cls):
        cls.start_session_bus()
        cls.start_system_bus()

    def test_local(self):
        '''Load a local template *.py file'''

        with tempfile.NamedTemporaryFile(prefix='answer_', suffix='.py') as my_template:
            my_template.write(b'''import dbus
BUS_NAME = 'universe.Ultimate'
MAIN_OBJ = '/'
MAIN_IFACE = 'universe.Ultimate'
SYSTEM_BUS = False

def load(mock, parameters):
    mock.AddMethods(MAIN_IFACE, [('Answer', 's', 'i', 'ret = 42')])
''')
            my_template.flush()
            (p_mock, dbus_ultimate) = self.spawn_server_template(
                my_template.name, stdout=subprocess.PIPE)
            self.addCleanup(p_mock.wait)
            self.addCleanup(p_mock.terminate)
            self.addCleanup(p_mock.stdout.close)

            # ensure that we don't use/write any .pyc files, they are dangerous
            # in a world-writable directory like /tmp
            self.assertFalse(os.path.exists(my_template.name + 'c'))
            self.assertFalse(os.path.exists(importlib.util.cache_from_source(my_template.name)))

        loop = GLib.MainLoop()
        caught_signals = []

        def method_called(method, args, **_):
            caught_signals.append((method, args))
            loop.quit()

        dbus_mock = dbus.Interface(dbus_ultimate, dbusmock.MOCK_IFACE)
        dbus_mock.connect_to_signal('MethodCalled', method_called)

        self.assertEqual(dbus_ultimate.Answer("foo"), 42)
        self.assertEqual(dbus_ultimate.Answer("bar"), 42)

        # should appear in introspection
        xml = dbus_ultimate.Introspect()
        self.assertIn('<interface name="universe.Ultimate">', xml)
        self.assertIn('<method name="Answer">', xml)

        # should not have ObjectManager API by default
        self.assertRaises(dbus.exceptions.DBusException,
                          dbus_ultimate.GetManagedObjects)

        # Call should have been registered
        mock_calls = dbus_mock.GetMethodCalls('Answer')
        self.assertEqual(len(mock_calls), 2)
        self.assertEqual(mock_calls[0][1], ['foo'])
        self.assertEqual(mock_calls[1][1], ['bar'])

        # Check signals
        GLib.timeout_add(5000, loop.quit)
        loop.run()

        #  only one signal because we call loop.quit() in the handler
        self.assertEqual(len(caught_signals), 1)
        method, args = caught_signals[0]
        self.assertEqual(method, 'Answer')
        self.assertEqual(len(args), 1)
        self.assertEqual(args[0], 'foo')

    def test_static_method(self):
        '''Static method in a template'''

        with tempfile.NamedTemporaryFile(prefix='answer_', suffix='.py') as my_template:
            my_template.write(b'''import dbus
BUS_NAME = 'universe.Ultimate'
MAIN_OBJ = '/'
MAIN_IFACE = 'universe.Ultimate'
SYSTEM_BUS = False

def load(mock, parameters):
    pass

@dbus.service.method(MAIN_IFACE,
                     in_signature='s',
                     out_signature='i')
def Answer(self, string):
    return 42
''')
            my_template.flush()
            (p_mock, dbus_ultimate) = self.spawn_server_template(
                my_template.name, stdout=subprocess.PIPE)
            self.addCleanup(p_mock.wait)
            self.addCleanup(p_mock.terminate)
            self.addCleanup(p_mock.stdout.close)

        loop = GLib.MainLoop()
        caught_signals = []

        def method_called(method, args, **_):
            caught_signals.append((method, args))
            loop.quit()

        dbus_mock = dbus.Interface(dbus_ultimate, dbusmock.MOCK_IFACE)
        dbus_mock.connect_to_signal('MethodCalled', method_called)

        self.assertEqual(dbus_ultimate.Answer("foo"), 42)
        self.assertEqual(dbus_ultimate.Answer("bar"), 42)
        # should appear in introspection
        xml = dbus_ultimate.Introspect()
        self.assertIn('<interface name="universe.Ultimate">', xml)
        self.assertIn('<method name="Answer">', xml)

        # Call should have been registered
        mock_calls = dbus_mock.GetMethodCalls('Answer')
        self.assertEqual(len(mock_calls), 2)
        self.assertEqual(mock_calls[0][1], ['foo'])
        self.assertEqual(mock_calls[1][1], ['bar'])

        # Check signals
        GLib.timeout_add(5000, loop.quit)
        loop.run()

        #  only one signal because we call loop.quit() in the handler
        self.assertEqual(len(caught_signals), 1)
        method, args = caught_signals[0]
        self.assertEqual(method, 'Answer')
        self.assertEqual(len(args), 1)
        self.assertEqual(args[0], 'foo')

    def test_local_nonexisting(self):
        self.assertRaises(ImportError, self.spawn_server_template, '/non/existing.py')

    def test_explicit_bus_(self):
        '''Explicitly set the bus for a template that does not specify SYSTEM_BUS'''

        with tempfile.NamedTemporaryFile(prefix='answer_', suffix='.py') as my_template:
            my_template.write(b'''import dbus
BUS_NAME = 'universe.Ultimate'
MAIN_OBJ = '/'
MAIN_IFACE = 'universe.Ultimate'

def load(mock, parameters):
    mock.AddMethods(MAIN_IFACE, [('Answer', '', 'i', 'ret = 42')])
''')
            my_template.flush()
            (p_mock, dbus_ultimate) = self.spawn_server_template(
                my_template.name, stdout=subprocess.PIPE, system_bus=False)
            self.addCleanup(p_mock.wait)
            self.addCleanup(p_mock.terminate)
            self.addCleanup(p_mock.stdout.close)

        self.wait_for_bus_object('universe.Ultimate', '/')
        self.assertEqual(dbus_ultimate.Answer(), 42)

    def test_override_bus_(self):
        '''Override the bus for a template'''

        with tempfile.NamedTemporaryFile(prefix='answer_', suffix='.py') as my_template:
            my_template.write(b'''import dbus
BUS_NAME = 'universe.Ultimate'
MAIN_OBJ = '/'
MAIN_IFACE = 'universe.Ultimate'
SYSTEM_BUS = True

def load(mock, parameters):
    mock.AddMethods(MAIN_IFACE, [('Answer', '', 'i', 'ret = 42')])
''')
            my_template.flush()
            (p_mock, dbus_ultimate) = self.spawn_server_template(
                my_template.name, stdout=subprocess.PIPE, system_bus=False)
            self.addCleanup(p_mock.wait)
            self.addCleanup(p_mock.terminate)
            self.addCleanup(p_mock.stdout.close)

        self.wait_for_bus_object('universe.Ultimate', '/')
        self.assertEqual(dbus_ultimate.Answer(), 42)

    def test_object_manager(self):
        '''Template with ObjectManager API'''

        with tempfile.NamedTemporaryFile(prefix='objmgr_', suffix='.py') as my_template:
            my_template.write(b'''import dbus
BUS_NAME = 'org.test.Things'
MAIN_OBJ = '/org/test/Things'
IS_OBJECT_MANAGER = True
SYSTEM_BUS = False

def load(mock, parameters):
    mock.AddObject('/org/test/Things/Thing1', 'org.test.Do', {'name': 'one'}, [])
    mock.AddObject('/org/test/Things/Thing2', 'org.test.Do', {'name': 'two'}, [])
    mock.AddObject('/org/test/Peer', 'org.test.Do', {'name': 'peer'}, [])
''')
            my_template.flush()
            (p_mock, dbus_objmgr) = self.spawn_server_template(
                my_template.name, stdout=subprocess.PIPE)
            self.addCleanup(p_mock.wait)
            self.addCleanup(p_mock.terminate)
            self.addCleanup(p_mock.stdout.close)

        # should have the two Things, but not the Peer
        self.assertEqual(dbus_objmgr.GetManagedObjects(),
                         {'/org/test/Things/Thing1': {'org.test.Do': {'name': 'one'}},
                          '/org/test/Things/Thing2': {'org.test.Do': {'name': 'two'}}})

        # should appear in introspection
        xml = dbus_objmgr.Introspect()
        self.assertIn('<interface name="org.freedesktop.DBus.ObjectManager">', xml)
        self.assertIn('<method name="GetManagedObjects">', xml)
        self.assertIn('<node name="Thing1" />', xml)
        self.assertIn('<node name="Thing2" />', xml)

    def test_reset(self):
        '''Reset() puts the template back to pristine state'''

        (p_mock, obj_logind) = self.spawn_server_template(
            'logind', stdout=subprocess.PIPE)
        self.addCleanup(p_mock.wait)
        self.addCleanup(p_mock.terminate)
        self.addCleanup(p_mock.stdout.close)

        # do some property, method, and object changes
        obj_logind.Set('org.freedesktop.login1.Manager', 'IdleAction', 'frob')
        mock_logind = dbus.Interface(obj_logind, dbusmock.MOCK_IFACE)
        mock_logind.AddProperty('org.Test.Other', 'walk', 'silly')
        mock_logind.AddMethod('', 'DoWalk', '', '', '')
        mock_logind.AddObject('/obj1', '', {}, [])

        mock_logind.Reset()

        # keeps the objects from the template
        dbus_con = self.get_dbus(system_bus=True)
        obj_logind = dbus_con.get_object('org.freedesktop.login1',
                                         '/org/freedesktop/login1')
        self.assertEqual(obj_logind.CanSuspend(), 'yes')

        # resets properties
        self.assertRaises(dbus.exceptions.DBusException,
                          obj_logind.GetAll, 'org.Test.Other')
        self.assertEqual(
            obj_logind.Get('org.freedesktop.login1.Manager', 'IdleAction'),
            'ignore')
        # resets methods
        self.assertRaises(dbus.exceptions.DBusException, obj_logind.DoWalk)
        # resets other objects
        obj1 = dbus_con.get_object('org.freedesktop.login1', '/obj1')
        self.assertRaises(dbus.exceptions.DBusException, obj1.GetAll, '')


class TestCleanup(dbusmock.DBusTestCase):
    '''Test cleanup of resources'''

    def test_mock_terminates_with_bus(self):
        '''Spawned mock processes exit when bus goes down'''

        self.start_session_bus()
        p_mock = self.spawn_server('org.freedesktop.Test',
                                   '/',
                                   'org.freedesktop.Test.Main')
        self.stop_dbus(self.session_bus_pid)

        # give the mock 2 seconds to terminate
        timeout = 20
        while timeout > 0:
            if p_mock.poll() is not None:
                break
            timeout -= 1
            time.sleep(0.1)

        if p_mock.poll() is None:
            # clean up manually
            p_mock.terminate()
            p_mock.wait()
            self.fail('mock process did not terminate after 2 seconds')

        self.assertEqual(p_mock.wait(), 0)


class TestSubclass(dbusmock.DBusTestCase):
    '''Test subclassing DBusMockObject'''

    @classmethod
    def setUpClass(cls):
        cls.start_session_bus()

    def test_ctor(self):
        '''Override DBusMockObject constructor'''

        class MyMock(dbusmock.mockobject.DBusMockObject):
            def __init__(self):
                bus_name = dbus.service.BusName('org.test.MyMock',
                                                dbusmock.testcase.DBusTestCase.get_dbus())
                dbusmock.mockobject.DBusMockObject.__init__(
                    self, bus_name, '/', 'org.test.A', {}, os.devnull)
                self.AddMethod('', 'Ping', '', 'i', 'ret = 42')

        m = MyMock()
        self.assertEqual(m.Ping(), 42)  # pylint: disable=no-member

    def test_none_props(self):
        '''object with None properties argument'''

        class MyMock(dbusmock.mockobject.DBusMockObject):
            def __init__(self):
                bus_name = dbus.service.BusName('org.test.MyMock',
                                                dbusmock.testcase.DBusTestCase.get_dbus())
                dbusmock.mockobject.DBusMockObject.__init__(
                    self, bus_name, '/mymock', 'org.test.MyMockI', None, os.devnull)
                self.AddMethod('', 'Ping', '', 'i', 'ret = 42')

        m = MyMock()
        self.assertEqual(m.Ping(), 42)  # pylint: disable=no-member
        self.assertEqual(m.GetAll('org.test.MyMockI'), {})

        m.AddProperty('org.test.MyMockI', 'blurb', 5)
        self.assertEqual(m.GetAll('org.test.MyMockI'), {'blurb': 5})


class TestServiceAutostart(dbusmock.DBusTestCase):
    '''Test service starting DBusMockObject'''

    @classmethod
    def setUpClass(cls):
        cls.xdg_data_dir = tempfile.mkdtemp(prefix='dbusmock_xdg_')
        cls.addClassCleanup(shutil.rmtree, cls.xdg_data_dir)

        os.environ['XDG_DATA_DIRS'] = cls.xdg_data_dir

        os.mkdir(os.path.join(cls.xdg_data_dir, 'dbus-1'))
        system_dir = os.path.join(cls.xdg_data_dir, 'dbus-1', 'system-services')
        session_dir = os.path.join(cls.xdg_data_dir, 'dbus-1', 'services')
        os.mkdir(system_dir)
        os.mkdir(session_dir)

        with open(os.path.join(system_dir, 'org.TestSystem.service'), 'w', encoding='ascii') as s:
            s.write('[D-BUS Service]\n' +
                    'Name=org.TestSystem\n'
                    'Exec=/usr/bin/python3 -c "import sys; from gi.repository import GLib, Gio; '
                    '     Gio.bus_own_name(Gio.BusType.SYSTEM, \'org.TestSystem\', 0, None, None, lambda *args: sys.exit(0)); '
                    '     GLib.MainLoop().run()"\n'
                    'User=root')

        with open(os.path.join(session_dir, 'org.TestSession.service'), 'w', encoding='ascii') as s:
            s.write('[D-BUS Service]\n'
                    'Name=org.TestSession\n'
                    'Exec=/usr/bin/python3 -c "import sys; from gi.repository import GLib, Gio; '
                    '     Gio.bus_own_name(Gio.BusType.SESSION, \'org.TestSession\', 0, None, None, lambda *args: sys.exit(0)); '
                    '     GLib.MainLoop().run()"\n'
                    'User=root')

        cls.start_system_bus()
        cls.start_session_bus()

    def test_session_service_function_raise(self):
        with self.assertRaises(AssertionError):
            self.enable_service('does-not-exist')

        with self.assertRaises(AssertionError):
            self.disable_service('does-not-exist')

    def test_session_service_isolation(self):
        dbus_con = self.get_dbus(system_bus=False)
        dbus_obj = dbus_con.get_object('org.freedesktop.DBus', '/org/freedesktop/DBus')
        dbus_if = dbus.Interface(dbus_obj, 'org.freedesktop.DBus')

        self.assertEqual(dbus_if.ListActivatableNames(), ['org.freedesktop.DBus'])
        self.enable_service('org.TestSession')
        self.addCleanup(self.disable_service, 'org.TestSession')
        self.assertEqual(dbus_if.ListActivatableNames(), ['org.freedesktop.DBus', 'org.TestSession'])

    def test_system_service_isolation(self):
        dbus_con = self.get_dbus(system_bus=True)
        dbus_obj = dbus_con.get_object('org.freedesktop.DBus', '/org/freedesktop/DBus')
        dbus_if = dbus.Interface(dbus_obj, 'org.freedesktop.DBus')

        self.assertEqual(dbus_if.ListActivatableNames(), ['org.freedesktop.DBus'])
        self.enable_service('org.TestSystem', system_bus=True)
        self.addCleanup(self.disable_service, 'org.TestSystem', system_bus=True)
        self.assertEqual(dbus_if.ListActivatableNames(), ['org.freedesktop.DBus', 'org.TestSystem'])

    def test_session_service_activation(self):
        dbus_con = self.get_dbus(system_bus=False)
        dbus_obj = dbus_con.get_object('org.freedesktop.DBus', '/org/freedesktop/DBus')
        dbus_if = dbus.Interface(dbus_obj, 'org.freedesktop.DBus')

        self.enable_service('org.TestSession')
        self.addCleanup(self.disable_service, 'org.TestSession')

        dbus_if.StartServiceByName('org.TestSession', 0)

    def test_system_service_activation(self):
        dbus_con = self.get_dbus(system_bus=True)
        dbus_obj = dbus_con.get_object('org.freedesktop.DBus', '/org/freedesktop/DBus')
        dbus_if = dbus.Interface(dbus_obj, 'org.freedesktop.DBus')

        self.enable_service('org.TestSystem', system_bus=True)
        self.addCleanup(self.disable_service, 'org.TestSystem', system_bus=True)

        dbus_if.StartServiceByName('org.TestSystem', 0)


if __name__ == '__main__':
    # avoid writing to stderr
    unittest.main(testRunner=unittest.TextTestRunner(stream=sys.stdout))
